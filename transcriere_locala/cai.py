"""Toate căile folosite de program, calculate la rulare.

Nu există litere de disc sau căi fixe: totul pornește din variabile de mediu
și din folderul utilizatorului, deci merge pe orice calculator Windows,
inclusiv cu nume de utilizator cu diacritice sau spații.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

NUME_FOLDER = "TranscriereLocala"


def _local_appdata() -> Path:
    """Folderul LOCALAPPDATA, cu rezervă dacă variabila lipsește."""
    valoare = os.environ.get("LOCALAPPDATA")
    if valoare:
        return Path(valoare)
    return Path.home() / "AppData" / "Local"


def director_instalare() -> Path:
    """Folderul principal al programului (fără drepturi de administrator).

    Poate fi schimbat cu variabila de mediu TRANSCRIERE_DIR sau cu
    argumentul ``--director`` din linia de comandă.
    """
    valoare = os.environ.get("TRANSCRIERE_DIR")
    if valoare:
        return Path(valoare).expanduser().resolve()
    return _local_appdata() / NUME_FOLDER


def director_mediu() -> Path:
    """Mediul Python propriu al programului (venv)."""
    return director_instalare() / "mediu"


def python_mediu() -> Path:
    return director_mediu() / "Scripts" / "python.exe"


def pythonw_mediu() -> Path:
    return director_mediu() / "Scripts" / "pythonw.exe"


def director_model() -> Path:
    return director_instalare() / "model"


def fisier_model() -> Path:
    from .constante import WHISPER_NUME

    return director_model() / f"{WHISPER_NUME}.pt"


def director_descarcari() -> Path:
    return director_instalare() / "descarcari"


def director_wordcraft() -> Path:
    """WordCraft instalat portabil de acest program (fără administrator)."""
    return director_instalare() / "WordCraft"


def fisier_config() -> Path:
    return director_instalare() / "config.json"


def director_jurnale() -> Path:
    return director_instalare() / "jurnale"


def fisier_jurnal_instalare() -> Path:
    return director_jurnale() / "instalare.log"


def fisier_jurnal_aplicatie() -> Path:
    return director_jurnale() / "aplicatie.log"


def director_iesiri() -> Path:
    """Unde se salvează documentele create (implicit: Documente/Transcrieri)."""
    valoare = os.environ.get("TRANSCRIERE_IESIRI")
    if valoare:
        return Path(valoare).expanduser().resolve()
    documente = Path.home() / "Documents"
    if not documente.exists():
        # Unele conturi nu au folderul "Documents" redenumit; folosim profilul.
        documente = Path.home()
    return documente / "Transcrieri"


def pregateste_directoare() -> None:
    """Creează folderele de care are nevoie programul."""
    for folder in (
        director_instalare(),
        director_model(),
        director_descarcari(),
        director_jurnale(),
        director_iesiri(),
    ):
        folder.mkdir(parents=True, exist_ok=True)


def director_script() -> Path:
    """Folderul din care rulează sursa programului."""
    return Path(__file__).resolve().parent.parent


def arhitectura() -> str:
    """Arhitectura procesorului: AMD64, ARM64 sau x86.

    Se bazează pe variabilele de mediu Windows, ca să funcționeze corect și
    când Python e pe 32 de biți pe un Windows pe 64 de biți.
    """
    arh = (os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ.get("PROCESSOR_ARCHITECTURE") or "").upper()
    if arh in ("AMD64", "X86"):
        return "AMD64" if arh == "AMD64" else "x86"
    if arh == "ARM64":
        return "ARM64"
    import platform

    masina = platform.machine().upper()
    if masina in ("AMD64", "X86_64"):
        return "AMD64"
    if masina in ("ARM64", "AARCH64"):
        return "ARM64"
    return "x86"


def este_windows() -> bool:
    return sys.platform.startswith("win")


def cale_sigura(text: str) -> str:
    """Pune ghilimele în jurul unei căi, pentru afișare sau comenzi."""
    return f'"{text}"' if " " in text else text
