"""Motorul de transcriere: Whisper large-v3-turbo, rulat local.

Modelul este încărcat dintr-un fișier local (``model/large-v3-turbo.pt``),
deci după instalare nu mai este nevoie de internet. Dacă există o placă
video NVIDIA compatibilă, se folosește automat; altfel se folosește procesorul.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import cai, jurnal
from .constante import PROMPT_ROMANA


class EroareMotor(RuntimeError):
    """Transcrierea nu poate rula; mesajul este pentru utilizator."""


class Anulat(Exception):
    """Transcrierea a fost oprită de utilizator."""


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Rezultat:
    text: str
    limba: str
    segmente: list[Segment] = field(default_factory=list)
    dispozitiv: str = "cpu"
    secunde_audio: float = 0.0
    secunde_calcul: float = 0.0

    @property
    def cuvinte(self) -> int:
        return len(self.text.split())


# --------------------------------------------------------------------------- ffmpeg


def pregateste_ffmpeg() -> str:
    """Pune ffmpeg-ul inclus în PATH, ca Whisper să poată citi orice format.

    imageio-ffmpeg aduce un binar static, fără instalare și fără drepturi de
    administrator; astfel merge și pe calculatoare unde ffmpeg nu e instalat.
    """
    try:
        import imageio_ffmpeg

        executabil = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""
    folder = str(Path(executabil).parent)
    cale = os.environ.get("PATH", "")
    if folder not in cale.split(os.pathsep):
        os.environ["PATH"] = folder + os.pathsep + cale
    return executabil


def biblioteci_disponibile() -> bool:
    """Adevărat dacă interpretorul curent poate importa Whisper și microfonul.

    Este o verificare ieftină, folosită de interfață la pornire. Nu încarcă
    modelul, deci nu consumă memorie.
    """
    try:
        import sounddevice  # noqa: F401
        import whisper  # noqa: F401

        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- motor

class MotorWhisper:
    """Încarcă modelul o singură dată și transcrie fișiere sau sunet din memorie."""

    def __init__(self, dispozitiv: str = "auto"):
        self.dispozitiv_preferat = dispozitiv
        self._model = None
        self._dispozitiv = "cpu"
        self._blocare = threading.Lock()
        self._anulat = threading.Event()

    # ------------------------------------------------------------------ stare

    @property
    def incarcat(self) -> bool:
        return self._model is not None

    @property
    def dispozitiv(self) -> str:
        return self._dispozitiv

    def anuleaza(self) -> None:
        """Cere oprirea transcrierii în curs."""
        self._anulat.set()

    def elibereaza(self) -> None:
        """Scoate modelul din memorie."""
        with self._blocare:
            self._model = None
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    # ------------------------------------------------------------------ încărcare

    def _alege_dispozitiv(self) -> str:
        if self.dispozitiv_preferat == "cpu":
            return "cpu"
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def incarca(self) -> None:
        """Încarcă modelul, dacă nu este deja în memorie."""
        if self._model is not None:
            return
        fisier = cai.fisier_model()
        if not fisier.exists():
            raise EroareMotor(
                "Modelul de transcriere lipsește. Rulează din nou instalarea programului "
                "(sau «Verifică instalarea» din meniu) ca să fie descărcat."
            )
        try:
            import whisper
        except Exception as exc:  # pragma: no cover - depinde de instalare
            raise EroareMotor(
                "Programul de transcriere nu este instalat corect. "
                "Rulează din nou instalarea programului."
            ) from exc

        pregateste_ffmpeg()
        self._dispozitiv = self._alege_dispozitiv()
        jurnal.info(f"Încarc modelul {fisier.name} pe {self._dispozitiv}…")
        try:
            self._model = whisper.load_model(str(fisier), device=self._dispozitiv)
        except Exception as exc:
            if self._dispozitiv == "cuda":
                jurnal.atentionare(f"Placa video nu a putut fi folosită ({exc}); trec pe procesor.")
                self._dispozitiv = "cpu"
                try:
                    self._model = whisper.load_model(str(fisier), device="cpu")
                except Exception as exc2:
                    raise EroareMotor(
                        "Modelul de transcriere nu a putut fi încărcat. "
                        "Memoria calculatorului poate fi insuficientă: închide alte programe "
                        "și încearcă din nou."
                    ) from exc2
            else:
                raise EroareMotor(
                    "Modelul de transcriere nu a putut fi încărcat. "
                    "Memoria calculatorului poate fi insuficientă: închide alte programe "
                    "și încearcă din nou."
                ) from exc
        jurnal.info(f"Model încărcat pe {self._dispozitiv}.")

    # ------------------------------------------------------------------ transcriere

    def transcrie(
        self,
        sursa: str | Path | "object",
        limba: str = "ro",
        progres: Callable[[float], None] | None = None,
        faza: Callable[[str], None] | None = None,
    ) -> Rezultat:
        """Transcrie un fișier audio sau un tablou numpy mono float32.

        ``progres`` primește o fracțiune 0..1; ``faza`` primește mesaje scurte.
        """
        import time

        if faza:
            faza("Pregătesc modelul de transcriere…")
        self.incarca()
        self._anulat.clear()

        limba_whisper = None if limba in ("auto", "", None) else limba
        optiuni = {
            "language": limba_whisper,
            "task": "transcribe",
            "verbose": False,
            "fp16": self._dispozitiv == "cuda",
            "condition_on_previous_text": False,
            "word_timestamps": False,
        }
        if limba_whisper == "ro":
            optiuni["initial_prompt"] = PROMPT_ROMANA

        if faza:
            faza("Transcriu…")

        start = time.time()
        try:
            rezultat_brut = self._ruleaza(sursa, optiuni, progres)
        except Anulat:
            raise
        except Exception as exc:
            if self._dispozitiv == "cuda":
                jurnal.atentionare(f"Transcrierea pe placă video a eșuat ({exc}); reiau pe procesor.")
                self._dispozitiv = "cpu"
                try:
                    import torch

                    self._model = self._model.to("cpu")
                except Exception:
                    self._model = None
                    self.incarca()
                optiuni["fp16"] = False
                rezultat_brut = self._ruleaza(sursa, optiuni, progres)
            else:
                raise EroareMotor(
                    "Transcrierea nu a putut fi făcută. Verifică dacă fișierul audio "
                    "se aude corect și încearcă din nou.\n"
                    f"Detaliu: {exc}"
                ) from exc
        durata = time.time() - start

        segmente = [
            Segment(float(s.get("start", 0.0)), float(s.get("end", 0.0)), str(s.get("text", "")).strip())
            for s in rezultat_brut.get("segments", [])
        ]
        text = (rezultat_brut.get("text") or "").strip()
        if not text:
            text = " ".join(s.text for s in segmente).strip()

        secunde_audio = 0.0
        if segmente:
            secunde_audio = max(s.end for s in segmente)
        elif hasattr(sursa, "__len__") and not isinstance(sursa, (str, Path)):
            try:
                secunde_audio = len(sursa) / 16_000  # Whisper lucrează la 16 kHz
            except TypeError:
                secunde_audio = 0.0

        if faza:
            faza("Gata.")
        if progres:
            progres(1.0)
        return Rezultat(
            text=text,
            limba=str(rezultat_brut.get("language") or limba),
            segmente=segmente,
            dispozitiv=self._dispozitiv,
            secunde_audio=secunde_audio,
            secunde_calcul=durata,
        )

    def _ruleaza(self, sursa, optiuni: dict, progres: Callable[[float], None] | None) -> dict:
        """Rulează Whisper, cu bară de progres legată la interfață."""
        import sys

        import whisper.transcribe  # noqa: F401 - asigură încărcarea modulului

        # ``whisper.transcribe`` este umbrit de funcția cu același nume din
        # pachet, deci luăm modulul direct din sys.modules.
        modul = sys.modules["whisper.transcribe"]

        if isinstance(sursa, (str, Path)):
            audio = self._incarca_audio(str(sursa))
        else:
            audio = sursa

        original = getattr(modul, "tqdm", None)
        modul.tqdm = _shim_progres(progres, self._anulat)
        try:
            return self._model.transcribe(audio, **optiuni)
        finally:
            if original is not None:
                modul.tqdm = original

    @staticmethod
    def _incarca_audio(cale: str):
        import whisper

        pregateste_ffmpeg()
        try:
            return whisper.load_audio(cale)
        except Exception as exc:
            nume = Path(cale).name
            raise EroareMotor(
                f"Fișierul „{nume}” nu a putut fi citit. Formatele acceptate sunt: "
                "MP3, WAV, M4A, OGG, FLAC. Verifică dacă fișierul nu este deteriorat "
                "sau protejat cu parolă."
            ) from exc


# --------------------------------------------------------------------------- progres


class _Bara:
    """Înlocuitor minimal pentru bara de progres din Whisper."""

    def __init__(self, progres, anulat, total=0, **_: object):
        self._progres = progres
        self._anulat = anulat
        self.total = float(total or 0)
        self.valoare = 0.0

    def __enter__(self):
        return self

    def __exit__(self, *_: object):
        return False

    def update(self, n: float = 1) -> None:
        if self._anulat.is_set():
            raise Anulat()
        self.valoare += float(n)
        if self._progres and self.total > 0:
            self._progres(min(1.0, self.valoare / self.total))

    def close(self) -> None:
        pass


class _Shim:
    """Obiect care imită modulul tqdm, ca Whisper să folosească bara noastră."""

    def __init__(self, progres, anulat):
        def fabrica(*args, total=0, **kwargs):  # noqa: ANN001
            return _Bara(progres, anulat, total=total, **kwargs)

        self.tqdm = fabrica


def _shim_progres(progres, anulat) -> _Shim:
    return _Shim(progres, anulat)
