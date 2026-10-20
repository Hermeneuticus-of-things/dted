"""Înregistrare de la microfon, cu mesaje de eroare în limbaj simplu."""

from __future__ import annotations

import io
import threading
import wave
from dataclasses import dataclass
from typing import Callable

import numpy as np

RATA_IMPLICITA = 16_000  # Whisper lucrează la 16 kHz


class EroareMicrofon(RuntimeError):
    """Microfonul nu poate fi folosit; mesajul este pentru utilizator."""


@dataclass
class Inregistrare:
    """Sunet mono, float32, în intervalul [-1, 1]."""

    pcm: np.ndarray
    rata: int

    @property
    def secunde(self) -> float:
        return len(self.pcm) / float(self.rata or 1)

    def wav_bytes(self) -> bytes:
        """Împachetează sunetul ca fișier WAV 16 biți."""
        date = np.clip(self.pcm, -1.0, 1.0)
        intregi = (date * 32767.0).astype("<i2")
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as fisier:
            fisier.setnchannels(1)
            fisier.setsampwidth(2)
            fisier.setframerate(self.rata)
            fisier.writeframes(intregi.tobytes())
        return buffer.getvalue()

    def salveaza(self, cale) -> None:
        cale.parent.mkdir(parents=True, exist_ok=True)
        cale.write_bytes(self.wav_bytes())


def _sounddevice():
    """Import întârziat, ca verificarea resurselor să meargă și fără pachet."""
    try:
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - depinde de instalare
        raise EroareMicrofon(
            "Partea de microfon nu este instalată. Rulează din nou instalarea programului."
        ) from exc
    return sd


def listeaza_microfoane() -> list[str]:
    """Numele microfoanelor disponibile, pentru alegerea din interfață."""
    try:
        sd = _sounddevice()
        return [
            f"{index}: {dispozitiv['name']}"
            for index, dispozitiv in enumerate(sd.query_devices())
            if dispozitiv.get("max_input_channels", 0) > 0
        ]
    except EroareMicrofon:
        return []
    except Exception:
        return []


class Microfon:
    """Înregistrează continuu, până la oprire."""

    def __init__(self, rata: int = RATA_IMPLICITA, dispozitiv: int | None = None):
        self.rata = rata
        self.dispozitiv = dispozitiv
        self._flux = None
        self._bucati: list[np.ndarray] = []
        self._blocare = threading.Lock()
        self.nivel = 0.0
        self.activ = False
        self.rata_reala = rata

    # ------------------------------------------------------------------ pornire

    def _configuratii(self) -> list[tuple[int, int]]:
        """Combinații încercate, de la cea mai bună la cea mai compatibilă."""
        return [(self.rata, 1), (44_100, 1), (48_000, 1), (44_100, 2), (48_000, 2)]

    def porneste(self) -> None:
        if self.activ:
            return
        try:
            sd = _sounddevice()
        except EroareMicrofon:
            raise
        self._bucati = []
        self.nivel = 0.0
        ultima_eroare: Exception | None = None
        for rata, canale in self._configuratii():
            try:
                flux = sd.InputStream(
                    samplerate=rata,
                    channels=canale,
                    dtype="float32",
                    device=self.dispozitiv,
                    callback=self._primeste,
                )
                flux.start()
            except Exception as exc:  # încercăm următoarea combinație
                ultima_eroare = exc
                continue
            self._flux = flux
            self.rata_reala = rata
            self.activ = True
            return
        raise EroareMicrofon(
            "Nu găsesc microfonul. Verifică dacă e conectat, dacă nu este oprit din "
            "setările Windows (Confidențialitate → Microfon) și încearcă din nou. "
            f"(detaliu tehnic: {ultima_eroare})"
        )

    # ------------------------------------------------------------------ captură

    def _primeste(self, date, cadre, timp, stare) -> None:  # noqa: ANN001
        bloc = np.asarray(date, dtype=np.float32)
        if bloc.ndim > 1:
            bloc = bloc.mean(axis=1)
        with self._blocare:
            self._bucati.append(bloc.copy())
        if bloc.size:
            self.nivel = min(1.0, float(np.sqrt(np.mean(np.square(bloc)))) * 6.0)

    # ------------------------------------------------------------------ oprire

    def opreste(self) -> Inregistrare:
        if not self.activ:
            return Inregistrare(np.zeros(0, dtype=np.float32), self.rata_reala)
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
            return Inregistrare(np.zeros(0, dtype=np.float32), self.rata_reala)
        return Inregistrare(np.concatenate(bucati), self.rata_reala)

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
        self.activ = False
        self.nivel = 0.0


def reda(pcm: np.ndarray, rata: int) -> None:
    """Redă un sunet scurt (folosit la proba microfonului)."""
    try:
        sd = _sounddevice()
        sd.play(pcm, rata)
    except Exception:
        pass
