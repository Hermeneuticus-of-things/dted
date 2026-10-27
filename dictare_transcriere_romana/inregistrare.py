"""Înregistrare de la microfon și redare prin difuzoare sau căști.

Partea de sunet este folosită de dictare, de ecranul „Verifică sunetul” și de
redarea probelor. Sunetul este adus întotdeauna la **16 kHz mono**, adică exact
ce primește modelul Whisper, ca transcrierea să pornească imediat.

Toate mesajele de eroare sunt scrise în română simplă, ca utilizatorul să știe
ce s-a întâmplat și ce are de făcut.
"""

from __future__ import annotations

import io
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import jurnal

#: Rata de eșantionare cerută de Whisper.
RATA_WHISPER = 16_000


class EroareMicrofon(RuntimeError):
    """Microfonul nu poate fi folosit; mesajul este pentru utilizator."""


class EroareRedare(RuntimeError):
    """Sunetul nu poate fi redat; mesajul este pentru utilizator."""


@dataclass
class Inregistrare:
    """Sunet mono, float32, în intervalul [-1, 1], la 16 kHz."""

    pcm: np.ndarray
    rata: int = RATA_WHISPER

    @property
    def secunde(self) -> float:
        return len(self.pcm) / float(self.rata or 1)

    @property
    def nivel_maxim(self) -> float:
        """Cât de tare a fost sunetul înregistrat (0 = liniște)."""
        if not len(self.pcm):
            return 0.0
        return float(np.max(np.abs(self.pcm)))

    def wav_bytes(self) -> bytes:
        """Împachetează sunetul ca fișier WAV 16 biți, pentru Whisper."""
        date = np.clip(self.pcm, -1.0, 1.0)
        intregi = (date * 32767.0).astype("<i2")
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as fisier:
            fisier.setnchannels(1)
            fisier.setsampwidth(2)
            fisier.setframerate(self.rata)
            fisier.writeframes(intregi.tobytes())
        return buffer.getvalue()

    def scrie_wav(self, cale: Path) -> Path:
        """Salvează înregistrarea ca fișier WAV."""
        cale = Path(cale)
        cale.parent.mkdir(parents=True, exist_ok=True)
        cale.write_bytes(self.wav_bytes())
        return cale


# --------------------------------------------------------------------------- ajutoare


def _sd():
    """Import întârziat, ca programul să pornească și fără pachetul de sunet."""
    try:
        import sounddevice as sd  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depinde de instalare
        raise EroareMicrofon(
            "Părțile de sunet nu sunt instalate. Rulează din nou instalarea "
            "programului, apoi încearcă iar."
        ) from exc
    return sd


def reesantioneaza(pcm: np.ndarray, rata_sursa: int, rata_tinta: int = RATA_WHISPER) -> np.ndarray:
    """Aduce sunetul la rata cerută, prin interpolare simplă (fără biblioteci).

    Unele microfoane nu merg la 16 kHz; înregistrăm la rata lor, apoi aducem
    sunetul la 16 kHz mono, ca să fie primit direct de Whisper.
    """
    if not len(pcm) or rata_sursa == rata_tinta:
        return np.asarray(pcm, dtype=np.float32)
    lungime_noua = max(1, int(round(len(pcm) * rata_tinta / float(rata_sursa))))
    pozitii = np.linspace(0.0, len(pcm) - 1.0, lungime_noua)
    return np.interp(pozitii, np.arange(len(pcm)), pcm).astype(np.float32)


def _nume_purtator(sd, date: dict) -> str:
    """Numele sistemului audio (WASAPI, DirectSound…) al dispozitivului."""
    try:
        purtatori = list(sd.query_hostapis())
        index = int(date.get("hostapi", -1))
        if 0 <= index < len(purtatori):
            return str(purtatori[index].get("name", "")).strip()
    except Exception:
        pass
    return ""


def _index_dispozitiv(dispozitiv) -> int | None:
    """Transformă un dispozitiv (număr, nume sau obiect) în numărul lui.

    Când dispozitivul are și sistemul audio, se potrivește amândouă, ca să nu
    se nimerească alt dispozitiv cu același nume de pe alt sistem audio.
    """
    if dispozitiv is None:
        return None
    if isinstance(dispozitiv, int):
        return dispozitiv
    nume = getattr(dispozitiv, "nume_brut", None) or str(dispozitiv)
    purtator = getattr(dispozitiv, "purtator", "") or ""
    try:
        sd = _sd()
        for index, date in enumerate(sd.query_devices()):
            if str(date.get("name", "")).strip() != str(nume).strip():
                continue
            if purtator:
                nume_purtator = _nume_purtator(sd, date)
                if nume_purtator and purtator.lower() not in nume_purtator.lower():
                    continue
            return index
    except Exception:
        return None
    return None


def combinatii_rate(
    rata_implicita: int, rata_dorita: int = RATA_WHISPER
) -> list[tuple[int, int]]:
    """Combinațiile (rata, canale) cerute unui dispozitiv, în ordinea încercării.

    Se pornește de la rata cerută de program (16 kHz, cea folosită de Whisper),
    apoi de la rata pe care o cere dispozitivul, apoi de la ratele obișnuite.
    Nu se presupune niciodată o singură rată de sunet.
    """
    rate: list[int] = []
    for rata in (rata_dorita, rata_implicita, 48_000, 44_100, 22_050):
        if rata and int(rata) not in rate:
            rate.append(int(rata))
    combinatii = [(rata, 1) for rata in rate]
    combinatii += [(rata, 2) for rata in rate[:3]]
    return combinatii


# --------------------------------------------------------------------------- microfon


class Microfon:
    """Înregistrează de la microfonul ales, până la oprire.

    Se încearcă, în ordine, mai multe combinații de rată și canale, ca să
    funcționeze pe orice calculator; sunetul ajunge mereu la 16 kHz mono.
    """

    def __init__(self, dispozitiv=None, rata: int = RATA_WHISPER):
        self.dispozitiv = dispozitiv
        self.rata = rata
        self._flux = None
        self._bucati: list[np.ndarray] = []
        self._tot: list[np.ndarray] = []  # tot sunetul, pentru redare/săritură (cerințele 32/38)
        self._blocare = threading.Lock()
        self.nivel = 0.0
        self.activ = False
        self.rata_reala = rata
        self.ultima_eroare = ""

    # ------------------------------------------------------------------ pornire

    def _configuratii(self) -> list[tuple[int, int]]:
        """Combinații cerute dispozitivului, de la cea ideală la cea sigură.

        Rata cerută de program este 16 kHz, dar se încearcă și rata cerută de
        dispozitiv, apoi ratele obișnuite: unele microfoane nu merg la 16 kHz.
        """
        return combinatii_rate(self._rata_dispozitiv())

    def _rata_dispozitiv(self) -> int:
        """Rata de sunet cerută de dispozitivul ales (citită de la Windows)."""
        try:
            sd = _sd()
            date = sd.query_devices(_index_dispozitiv(self.dispozitiv))
            return max(8000, int(float(date.get("default_samplerate", 0) or 48_000)))
        except Exception:
            return 48_000

    def porneste(self) -> None:
        if self.activ:
            return
        sd = _sd()  # aruncă EroareMicrofon cu mesaj simplu dacă lipsește pachetul
        index = _index_dispozitiv(self.dispozitiv)
        self._bucati = []
        self._tot = []
        self.nivel = 0.0
        ultima_eroare: Exception | None = None
        for rata, canale in self._configuratii():
            try:
                flux = sd.InputStream(
                    samplerate=rata,
                    channels=canale,
                    dtype="float32",
                    device=index,
                    callback=self._primeste,
                )
                flux.start()
            except Exception as exc:  # încercăm următoarea combinație
                ultima_eroare = exc
                continue
            self._flux = flux
            self.rata_reala = rata
            self.activ = True
            jurnal.info(f"Înregistrez de la microfon (dispozitiv {index}, {rata} Hz, {canale} canal(e)).")
            return
        self.ultima_eroare = str(ultima_eroare)
        raise EroareMicrofon(
            "Nu găsesc microfonul. Verifică dacă e conectat, dacă nu este oprit "
            "din setările Windows (Confidențialitate → Microfon) și încearcă din nou."
        )

    # ------------------------------------------------------------------ captură

    def _primeste(self, date, cadre, timp, stare) -> None:  # noqa: ANN001
        bloc = np.asarray(date, dtype=np.float32)
        if bloc.ndim > 1:
            bloc = bloc.mean(axis=1)
        with self._blocare:
            copie = bloc.copy()
            self._bucati.append(copie)
            self._tot.append(copie)
        if bloc.size:
            self.nivel = min(1.0, float(np.sqrt(np.mean(np.square(bloc)))) * 6.0)

    # ------------------------------------------------------------------ citire în timpul mersului

    def preia(self) -> np.ndarray:
        """Ia sunetul adunat până acum (16 kHz mono), fără a opri înregistrarea.

        Se folosește la dictarea cu text în timp real: bucățile de sunet sunt
        transcrise pe rând, iar restul rămâne în flux până la următoarea citire.
        """
        with self._blocare:
            bucati, self._bucati = self._bucati, []
        if not bucati:
            return np.zeros(0, dtype=np.float32)
        sunet = np.concatenate(bucati).astype(np.float32)
        return reesantioneaza(sunet, self.rata_reala, RATA_WHISPER)

    def scurgere(self) -> float:
        """Câte secunde de sunet sunt adunate dar netranscrise încă."""
        with self._blocare:
            esantioane = sum(len(bloc) for bloc in self._bucati)
        return esantioane / float(self.rata_reala or RATA_WHISPER)

    def tot(self) -> Inregistrare:
        """Întregul sunet de la pornire, la 16 kHz mono (pentru redare/săritură).

        Spre deosebire de ``preia()`` (care consumă bucățile la transcriere),
        aceasta păstrează tot sunetul, ca după oprirea dictării să poți să-l
        redai de la un semn (cerințele 32 / 38).
        """
        with self._blocare:
            bucati = list(self._tot)
        if not bucati:
            return Inregistrare(np.zeros(0, dtype=np.float32))
        sunet = np.concatenate(bucati).astype(np.float32)
        return Inregistrare(
            reesantioneaza(sunet, self.rata_reala, RATA_WHISPER), RATA_WHISPER
        )

    # ------------------------------------------------------------------ oprire

    def opreste(self) -> Inregistrare:
        """Oprește înregistrarea și întoarce sunetul, la 16 kHz mono."""
        if not self.activ:
            return Inregistrare(np.zeros(0, dtype=np.float32))
        self.activ = False
        if self._flux is not None:
            try:
                self._flux.stop()
                self._flux.close()
            finally:
                self._flux = None
        with self._blocare:
            bucati, self._bucati = self._bucati, []
        self.nivel = 0.0
        if not bucati:
            return Inregistrare(np.zeros(0, dtype=np.float32))
        sunet = np.concatenate(bucati).astype(np.float32)
        sunet = reesantioneaza(sunet, self.rata_reala, RATA_WHISPER)
        return Inregistrare(sunet, RATA_WHISPER)

    def anuleaza(self) -> None:
        """Oprește fără a păstra sunetul."""
        if self._flux is not None:
            try:
                self._flux.stop()
                self._flux.close()
            finally:
                self._flux = None
        with self._blocare:
            self._bucati = []
            self._tot = []
        self.activ = False
        self.nivel = 0.0


# --------------------------------------------------------------------------- redare


def reda(pcm: np.ndarray, rata: int = RATA_WHISPER, dispozitiv=None, asteapta: bool = False) -> None:
    """Redă un sunet prin ieșirea aleasă (implicit: cea din Windows)."""
    try:
        sd = _sd()
    except EroareMicrofon as exc:
        raise EroareRedare(str(exc)) from exc
    index = _index_dispozitiv(dispozitiv)
    if pcm is None or not len(pcm):
        raise EroareRedare("Nu am ce să redau: înregistrarea este goală.")
    try:
        sd.play(np.asarray(pcm, dtype=np.float32), rata, device=index)
        if asteapta:
            sd.wait()
    except Exception as exc:
        raise EroareRedare(
            "Nu am putut reda sunetul. Verifică dacă difuzoarele sau căștile sunt "
            "conectate și dacă sunetul nu este oprit din Windows."
        ) from exc


def opreste_redarea() -> None:
    """Oprește imediat orice sunet care se redă."""
    try:
        _sd().stop()
    except Exception:
        pass


def sunet_proba(unde: str = "stereo", secunde: float = 1.2, rata: int = 44_100):
    """Sunet de probă scurt și plăcut, pentru difuzoare sau căști.

    ``unde`` poate fi ``„stereo”`` (ambele părți), ``„stanga”`` sau ``„dreapta”``
    (pentru verificarea căștilor, întâi o ureche, apoi cealaltă). ``rata`` este
    rata ieșirii alese, citită de la Windows, nu una presupusă.
    """
    n = int(secunde * rata)
    timp = np.linspace(0.0, secunde, n, endpoint=False)

    # Două note calde, una după alta (la 3 / 5), ca sunetul să fie ușor de recunoscut.
    frecventa = np.where(timp < secunde / 2, 587.33, 880.0)
    faza = np.cumsum(2 * np.pi * frecventa / rata)
    sunet = 0.28 * np.sin(faza)

    # Apar și dispar treptat, ca să nu pocnească.
    rampa = int(0.05 * rata)
    if rampa * 2 < n:
        sunet[:rampa] *= np.linspace(0.0, 1.0, rampa)
        sunet[-rampa:] *= np.linspace(1.0, 0.0, rampa)

    if unde in ("stanga", "dreapta"):
        stereo = np.zeros((n, 2), dtype=np.float32)
        coloana = 0 if unde == "stanga" else 1
        stereo[:, coloana] = sunet
        return stereo
    stereo = np.zeros((n, 2), dtype=np.float32)
    stereo[:, 0] = sunet
    stereo[:, 1] = sunet
    return stereo


def reda_proba(unde: str = "stereo", dispozitiv=None, asteapta: bool = True) -> str:
    """Redă sunetul de probă prin ieșirea aleasă, la rata și canalele ei.

    Întoarce ``„stereo”`` dacă ieșirea poate reda separat stânga și dreapta și
    ``„mono”`` dacă are un singur canal (atunci proba stânga/dreapta nu se
    poate face, iar interfața explică asta simplu).
    """
    index = _index_dispozitiv(dispozitiv)
    rata, canale = _rata_si_canale_iesire(index)
    fel = "stereo" if canale >= 2 else "mono"
    unde_efectiv = unde if (fel == "stereo" and unde in ("stanga", "dreapta")) else "stereo"
    sunet = sunet_proba(unde_efectiv, rata=rata)
    reda(sunet, rata, dispozitiv=dispozitiv, asteapta=asteapta)
    return fel


def _rata_si_canale_iesire(index: int | None) -> tuple[int, int]:
    """Rata și numărul de canale ale ieșirii, citite de la Windows."""
    try:
        sd = _sd()
        date = sd.query_devices(index) if index is not None else sd.query_devices(kind="output")
        rata = max(8000, int(float(date.get("default_samplerate", 0) or 48_000)))
        canale = int(date.get("max_output_channels", 0) or 1)
        return rata, max(1, canale)
    except Exception:
        return 48_000, 2
