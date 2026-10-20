"""Detectarea automată a microfoanelor, difuzoarelor și căștilor.

Utilizatorul nu trebuie să știe nimic despre calculatoare, deci aici:

* se citesc dispozitivele de sunet direct de la Windows (prin biblioteca
  ``sounddevice``), fără nume, numere sau căi fixe;
* fiecare dispozitiv primește un nume pe înțeles în română
  („Microfonul laptopului”, „Microfonul căștilor”, „Difuzoarele calculatorului”);
* microfonul corect se alege automat: cel setat implicit în Windows sau cel
  care chiar primește sunet (se măsoară scurt nivelul fiecăruia);
* schimbările din timpul folosirii (căști conectate sau scoase) sunt observate
  și anunțate simplu, fără să blocheze programul.

Nimic din acest fișier nu presupune ce dispozitive are calculatorul.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from . import jurnal

#: Cât se ascultă fiecare microfon la alegerea automată (secunde).
SECUNDE_PROBA = 0.35


class EroareSunet(RuntimeError):
    """Partea de sunet nu poate fi folosită; mesajul este pentru utilizator."""


@dataclass
class Dispozitiv:
    """Un dispozitiv de sunet, așa cum îl vede utilizatorul."""

    index: int
    nume_brut: str
    nume: str
    este_intrare: bool
    este_iesire: bool
    canale: int
    rata: float
    implicit: bool = False
    purtator: str = ""            # sistemul audio din Windows (de exemplu WASAPI)

    @property
    def cheie(self) -> str:
        """Identificatorul folosit pentru a ține minte alegerea utilizatorului.

        Conține și sistemul audio, nu doar numele: același nume poate apărea de
        mai multe ori pe purtătoare diferite, iar alegerea trebuie să fie exactă.
        """
        parti = ["in" if self.este_intrare else "out"]
        if self.purtator:
            parti.append(self.purtator)
        parti.append(self.nume_brut)
        return ":".join(parti)

    def descriere(self) -> str:
        """Textul din liste: numele pe înțeles, plus numele tehnic, dacă diferă."""
        if self.nume.lower() in self.nume_brut.lower():
            return self.nume
        return f"{self.nume} — {self.nume_brut}"

    def este_casti(self) -> bool:
        """Adevărat dacă numele arată că dispozitivul este o pereche de căști."""
        return _pare_casti(self.nume_brut) or _pare_casti(self.nume)


# --------------------------------------------------------------------------- nume prietenoase

#: Perechi (cuvânt din numele Windows, cum îi spunem noi). Se verifică în ordine.
_EXPLICATII: tuple[tuple[str, str], ...] = (
    ("microphone array", "Microfonul laptopului"),
    ("internal microphone", "Microfonul laptopului"),
    ("built-in mic", "Microfonul laptopului"),
    ("micrófono", "Microfonul laptopului"),
    ("integrat", "Microfonul laptopului"),
    ("headset", "Căștile cu microfon"),
    ("headphone", "Căștile"),
    ("earphone", "Căștile"),
    ("airpods", "Căștile Bluetooth"),
    ("buds", "Căștile Bluetooth"),
    ("bluetooth", "Dispozitivul Bluetooth"),
    ("wireless", "Dispozitivul fără fir"),
    ("webcam", "Microfonul camerei web"),
    ("camera", "Microfonul camerei web"),
    ("usb", "Dispozitivul USB"),
    ("hdmi", "Sunetul prin HDMI (monitor)"),
    ("display", "Sunetul prin HDMI (monitor)"),
    ("speaker", "Difuzoarele calculatorului"),
    ("monitor", "Difuzoarele calculatorului"),
    ("line out", "Ieșirea de linie"),
    ("line in", "Intrarea de linie"),
    ("microphone", "Microfon"),
    ("mic", "Microfon"),
)

_TRADUCERI = {"microphone": "microfon", "speakers": "difuzoare", "speaker": "difuzor",
              "headphones": "căști", "headset": "căști cu microfon", "default": "implicit"}


def _pare_casti(nume: str) -> bool:
    """Adevărat dacă numele primit seamănă a căști (fără diacritice în cod)."""
    text = nume.lower()
    cuvinte = ("headset", "headphone", "earphone", "buds", "airpods", "căști", "casti")
    return any(cuvant in text for cuvant in cuvinte)


def nume_prietenos(nume_brut: str, este_intrare: bool) -> str:
    """Traduce numele tehnic al dispozitivului într-un nume pe înțeles."""
    text = (nume_brut or "").strip()
    if not text:
        return "Microfon" if este_intrare else "Difuzoare"
    jos = text.lower()
    for cuvânt, explicatie in _EXPLICATII:
        if cuvânt in jos:
            if explicatie == "Microfon":
                return "Microfonul " + _curata(text) if text else "Microfon"
            return explicatie
    # Fără potrivire: folosim numele dispozitivului, dar fără părțile tehnice.
    return _curata(text)


def _curata(text: str) -> str:
    """Scoate din numele dispozitivului părțile care nu ajută pe nimeni."""
    curatat = text
    for tehnic in (
        "High Definition Audio",
        "High Definition Audio Device",
        "WDM",
        "Wave",
        "(R)",
        "®",
        "TM",
    ):
        curatat = curatat.replace(tehnic, " ")
    for englez, roman in _TRADUCERI.items():
        curatat = curatat.replace(englez, roman)
        curatat = curatat.replace(englez.capitalize(), roman.capitalize())
    curatat = " ".join(curatat.split()).strip(" -–,")
    return curatat or text


# --------------------------------------------------------------------------- citirea listelor


def _sd():
    """Import întârziat al bibliotecii de sunet, cu mesaj simplu dacă lipsește."""
    try:
        import sounddevice as sd  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depinde de instalare
        raise EroareSunet(
            "Părțile de sunet nu sunt instalate. Rulează din nou instalarea programului, "
            "apoi încearcă iar."
        ) from exc
    return sd


def _indexuri_implicite() -> tuple[int, int]:
    """Numerele dispozitivelor alese implicit în Windows (intrare, ieșire)."""
    try:
        sd = _sd()
        intrare, iesire = sd.default.device
        return int(intrare if intrare is not None else -1), int(iesire if iesire is not None else -1)
    except Exception:
        return -1, -1


#: Purtătoarele de cuvânt (sistemele audio) din Windows, în ordinea preferată.
#: Se folosește unul singur, ca lista de dispozitive să nu aibă dubluri.
_PURTATOARE_PREFERATE = ("wasapi", "directsound", "wdm-ks", "mme")

#: Dispozitive care nu sunt reale: Windows le arată ca soluții de rezervă.
_NUME_ASCUNSE = ("microsoft sound mapper", "primary sound driver", "driver de sunet primar")


def _purtator_preferat(sd) -> int | None:
    """Alege sistemul audio folosit pentru liste (de preferat WASAPI)."""
    try:
        purtatori = list(sd.query_hostapis())
    except Exception:
        return None
    for preferat in _PURTATOARE_PREFERATE:
        for index, purtator in enumerate(purtatori):
            nume = str(purtator.get("name", "")).lower()
            if preferat in nume.replace(" ", "") or preferat in nume:
                if purtator.get("devices"):
                    return index
    # Nimic potrivit: se folosește purtătorul cu cele mai multe dispozitive.
    if purtatori:
        return int(max(range(len(purtatori)), key=lambda i: len(purtatori[i].get("devices", []))))
    return None


def _nume_purtator(sd, date: dict) -> str:
    """Numele sistemului audio al unui dispozitiv („Windows WASAPI” etc.)."""
    try:
        purtatori = list(sd.query_hostapis())
        index = int(date.get("hostapi", -1))
        if 0 <= index < len(purtatori):
            return str(purtatori[index].get("name", "")).strip()
    except Exception:
        pass
    return ""


def listeaza() -> tuple[list[Dispozitiv], list[Dispozitiv]]:
    """Toate microfoanele și toate ieșirile de sunet, cu nume pe înțeles.

    Se citește un singur sistem audio (de preferat WASAPI), ca fiecare
    dispozitiv să apară o singură dată, iar dispozitivele „de rezervă” ale
    Windows sunt ascunse. Întoarce ``(microfoane, ieșiri)``.
    """
    try:
        sd = _sd()
        dispozitive = list(sd.query_devices())
    except Exception as exc:
        jurnal.atentionare(f"Nu am putut citi lista dispozitivelor de sunet: {exc}")
        return [], []

    purtator = _purtator_preferat(sd)
    implicit_in, implicit_out = _indexuri_implicite()
    intrari: list[Dispozitiv] = []
    iesiri: list[Dispozitiv] = []
    vazute: set[str] = set()
    for index, date in enumerate(dispozitive):
        nume_brut = str(date.get("name", "")).strip()
        if not nume_brut:
            continue
        nume_mic = nume_brut.lower()
        if any(ascuns in nume_mic for ascuns in _NUME_ASCUNSE):
            continue
        if purtator is not None and int(date.get("hostapi", -1)) != purtator:
            continue
        canale_in = int(date.get("max_input_channels", 0) or 0)
        canale_out = int(date.get("max_output_channels", 0) or 0)
        rata = float(date.get("default_samplerate", 0) or 0)
        nume_purtator = _nume_purtator(sd, date)
        if canale_in > 0 and f"in:{nume_mic}" not in vazute:
            vazute.add(f"in:{nume_mic}")
            intrari.append(
                Dispozitiv(
                    index,
                    nume_brut,
                    nume_prietenos(nume_brut, True),
                    True,
                    canale_out > 0,
                    canale_in,
                    rata,
                    index == implicit_in,
                    nume_purtator,
                )
            )
        if canale_out > 0 and f"out:{nume_mic}" not in vazute:
            vazute.add(f"out:{nume_mic}")
            iesiri.append(
                Dispozitiv(
                    index,
                    nume_brut,
                    nume_prietenos(nume_brut, False),
                    False,
                    True,
                    canale_out,
                    rata,
                    index == implicit_out,
                    nume_purtator,
                )
            )
    if not intrari and not iesiri:
        # Purtătorul ales nu are nimic: se reia citirea cu toate dispozitivele.
        jurnal.atentionare("Sistemul audio preferat nu are dispozitive; citesc toate.")
        return _listeaza_toate(sd, dispozitive, implicit_in, implicit_out)
    jurnal.info(
        f"Dispozitive de sunet găsite: {len(intrari)} microfoane, {len(iesiri)} ieșiri."
    )
    return intrari, iesiri


def _listeaza_toate(sd, dispozitive: list, implicit_in: int, implicit_out: int) -> tuple[list[Dispozitiv], list[Dispozitiv]]:
    """Citire de rezervă: toate dispozitivele, fără să ascundă nimic real."""
    intrari: list[Dispozitiv] = []
    iesiri: list[Dispozitiv] = []
    for index, date in enumerate(dispozitive):
        nume_brut = str(date.get("name", "")).strip()
        if not nume_brut:
            continue
        nume_mic = nume_brut.lower()
        if any(ascuns in nume_mic for ascuns in _NUME_ASCUNSE):
            continue
        canale_in = int(date.get("max_input_channels", 0) or 0)
        canale_out = int(date.get("max_output_channels", 0) or 0)
        rata = float(date.get("default_samplerate", 0) or 0)
        nume_purtator = _nume_purtator(sd, date)
        if canale_in > 0:
            intrari.append(
                Dispozitiv(index, nume_brut, nume_prietenos(nume_brut, True), True,
                           canale_out > 0, canale_in, rata, index == implicit_in, nume_purtator)
            )
        if canale_out > 0:
            iesiri.append(
                Dispozitiv(index, nume_brut, nume_prietenos(nume_brut, False), False,
                           True, canale_out, rata, index == implicit_out, nume_purtator)
            )
    return intrari, iesiri


def microfoane() -> list[Dispozitiv]:
    return listeaza()[0]


def iesiri() -> list[Dispozitiv]:
    return listeaza()[1]


def difuzoare() -> list[Dispozitiv]:
    """Doar ieșirile care nu par a fi căști."""
    return [d for d in iesiri() if not d.este_casti()]


def casti() -> list[Dispozitiv]:
    """Ieșirile care par a fi căști."""
    return [d for d in iesiri() if d.este_casti()]


# --------------------------------------------------------------------------- alegere automată


def _rata_implicita(dispozitiv: Dispozitiv | int) -> int:
    """Rata de sunet pe care o cere dispozitivul (citită de la Windows)."""
    if isinstance(dispozitiv, Dispozitiv) and dispozitiv.rata:
        return max(8000, int(dispozitiv.rata))
    try:
        sd = _sd()
        index = dispozitiv.index if isinstance(dispozitiv, Dispozitiv) else int(dispozitiv)
        date = sd.query_devices(index)
        return max(8000, int(float(date.get("default_samplerate", 0) or 48000)))
    except Exception:
        return 48_000


def masoara_nivel(dispozitiv: Dispozitiv | int, secunde: float = SECUNDE_PROBA) -> float:
    """Cât de tare se aude sunetul primit de un microfon (0 = liniște).

    Nu se presupune nici o rată de sunet: se încearcă, în ordine, rata cerută
    de dispozitiv și alte rate obișnuite, exact ca la înregistrare.
    """
    try:
        import numpy as np

        from .inregistrare import combinatii_rate

        sd = _sd()
        index = dispozitiv.index if isinstance(dispozitiv, Dispozitiv) else int(dispozitiv)
        ultima_eroare: Exception | None = None
        for rata, canale in combinatii_rate(_rata_implicita(dispozitiv)):
            try:
                date = sd.rec(
                    max(1, int(secunde * rata)),
                    samplerate=rata,
                    channels=canale,
                    dtype="float32",
                    device=index,
                )
                sd.wait()
            except Exception as exc:
                ultima_eroare = exc
                continue
            if date is None or not len(date):
                continue
            bloc = np.asarray(date, dtype=np.float32)
            if bloc.ndim > 1:
                bloc = bloc.mean(axis=1)
            return float(np.sqrt(np.mean(np.square(bloc))))
        if ultima_eroare is not None:
            jurnal.info(f"Nu am putut măsura microfonul {dispozitiv}: {ultima_eroare}")
        return 0.0
    except Exception as exc:
        jurnal.info(f"Nu am putut măsura microfonul {dispozitiv}: {exc}")
        return 0.0


def alege_microfon(preferat: str = "") -> Dispozitiv | None:
    """Alege microfonul potrivit: cel cerut, cel implicit sau cel care „aude”.

    Ordinea:
     1. microfonul ales de utilizator (dacă mai există);
     2. microfonul setat implicit în Windows;
     3. microfonul care primește cel mai mult sunet (se măsoară scurt);
     4. primul microfon din listă.
    """
    lista = microfoane()
    if not lista:
        return None
    if preferat:
        potrivit = alege_dupa_cheie(preferat, lista)
        if potrivit:
            return potrivit
    for dispozitiv in lista:
        if dispozitiv.implicit:
            return dispozitiv
    # Niciunul implicit: cântărim scurt fiecare microfon.
    cel_mai_bun = None
    nivel_maxim = 0.0
    for dispozitiv in lista[:4]:  # cel mult patru, ca pornirea să rămână rapidă
        nivel = masoara_nivel(dispozitiv)
        if nivel > nivel_maxim:
            cel_mai_bun, nivel_maxim = dispozitiv, nivel
    if cel_mai_bun is not None and nivel_maxim > 0.001:
        jurnal.info(f"Am ales microfonul care primește sunet: {cel_mai_bun.nume_brut}")
        return cel_mai_bun
    return lista[0]


def alege_iesire(preferat: str = "") -> Dispozitiv | None:
    """Alege ieșirea de sunet: cea cerută, cea implicită sau prima din listă."""
    lista = iesiri()
    if not lista:
        return None
    if preferat:
        potrivit = alege_dupa_cheie(preferat, lista, este_intrare=False)
        if potrivit:
            return potrivit
    for dispozitiv in lista:
        if dispozitiv.implicit:
            return dispozitiv
    return lista[0]


def alege_dupa_cheie(cheie: str, lista: list[Dispozitiv] | None = None,
                     este_intrare: bool = True) -> Dispozitiv | None:
    """Găsește dispozitivul ținut minte în setări, dacă mai este conectat.

    Cheia poate fi cea completă (cu sistemul audio), doar numele dispozitivului
    sau o formă veche a cheii; toate sunt acceptate.
    """
    if not cheie:
        return None
    lista = lista if lista is not None else (microfoane() if este_intrare else iesiri())
    for dispozitiv in lista:
        forme = {
            dispozitiv.cheie,
            dispozitiv.nume_brut,
            f"{dispozitiv.purtator}:{dispozitiv.nume_brut}",
            f"{'in' if dispozitiv.este_intrare else 'out'}:{dispozitiv.nume_brut}",
        }
        if cheie in forme:
            return dispozitiv
    return None


def stare_pentru_utilizator() -> str:
    """Text simplu despre ce dispozitive are calculatorul acum."""
    intrari, ieșiri_ = listeaza()
    if not intrari and not ieșiri_:
        return (
            "Nu găsesc niciun dispozitiv de sunet. Poți folosi programul cu un fișier "
            "audio deja înregistrat; pentru dictare este nevoie de un microfon."
        )
    parti: list[str] = []
    if intrari:
        parti.append(f"{len(intrari)} microfon(oane)")
    else:
        parti.append("niciun microfon")
    if ieșiri_:
        parti.append(f"{len(ieșiri_)} ieșiri de sunet")
    else:
        parti.append("nicio ieșire de sunet")
    return "Am găsit: " + " și ".join(parti) + "."


# --------------------------------------------------------------------------- urmărirea schimbărilor


class UrmaritorDispozitive:
    """Observă, în fundal, conectarea și scoaterea dispozitivelor de sunet.

    Nu folosește numere fixe: compară lista de dispozitive la câteva secunde și
    anunță doar diferențele, printr-un mesaj simplu, în română.
    """

    def __init__(self, anunta: Callable[[str], None], interval: float = 3.0):
        self.anunta = anunta
        self.interval = max(1.0, float(interval))
        self._oprire = threading.Event()
        self._fir = threading.Thread(target=self._bucla, daemon=True)
        self._cunoscute: set[str] = set()

    # ------------------------------------------------------------------ control

    def porneste(self) -> None:
        self._cunoscute = self._snapshot()
        self._fir.start()

    def opreste(self) -> None:
        self._oprire.set()

    # ------------------------------------------------------------------ lucru

    def _snapshot(self) -> set[str]:
        try:
            intrari, ieșiri_ = listeaza()
        except Exception:
            return set()
        return {d.nume_brut for d in intrari} | {d.nume_brut for d in ieșiri_}

    def _bucla(self) -> None:
        while not self._oprire.wait(self.interval):
            try:
                acum = self._snapshot()
            except Exception:
                continue
            if not acum:
                continue
            adaugate = acum - self._cunoscute
            scoase = self._cunoscute - acum
            self._cunoscute = acum
            for nume in sorted(adaugate):
                self._anunta_sigur(
                    f"Am găsit un dispozitiv nou: {nume_prietenos(nume, True)}. "
                    "Îl poți alege din lista de microfoane."
                )
            for nume in sorted(scoase):
                self._anunta_sigur(
                    f"Un dispozitiv a fost scos: {nume_prietenos(nume, True)}. "
                    "Folosesc în continuare dispozitivul disponibil."
                )

    def _anunta_sigur(self, mesaj: str) -> None:
        jurnal.info(mesaj)
        try:
            self.anunta(mesaj)
        except Exception:
            pass


def asteapta(secunde: float) -> None:
    """Pauză scurtă, folosită de probele de sunet."""
    time.sleep(max(0.0, secunde))
