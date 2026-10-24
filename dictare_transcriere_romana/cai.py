"""Toate căile folosite de program, calculate la rulare.

Nu există litere de disc fixe, căi fixe sau presupuneri despre utilizator:
totul pornește din variabilele de mediu Windows și din folderul profilului,
deci merge și cu nume de utilizator cu diacritice sau spații.

Folderul programului este, în ordine:
 1. valoarea variabilei de mediu ``DICTARE_DIR`` (sau vechea ``TRANSCRIERE_DIR``);
 2. ``%LOCALAPPDATA%\\Dictare&Transcriere Română``;
 3. o variantă fără diacritice sau fără simboluri, dacă Windows sau antivirusul
    nu permit crearea folderului cu diacritice.

Alegerea se face o singură dată, la prima folosire, și se notează în jurnal.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from .constante import (
    NUME_APLICATIE,
    NUME_CITESTE_MA,
    NUME_FOLDER,
    VAR_MEDIU_FOLDER,
    VAR_MEDIU_FOLDER_VECHI,
    VAR_MEDIU_IESIRI,
)

#: Numere de versiune acceptate pentru Python (PyTorch nu are pachete pentru 3.13).
PYTHON_ACCEPTAT = ((3, 10), (3, 11), (3, 12))


def _local_appdata() -> Path:
    """Folderul LOCALAPPDATA, cu rezervă dacă variabila lipsește."""
    valoare = os.environ.get("LOCALAPPDATA")
    if valoare:
        return Path(valoare)
    return Path.home() / "AppData" / "Local"


def folder_cunoscut(identificator: str) -> Path | None:
    """Cere Windows un folder standard, prin interfața oficială (Known Folder).

    ``identificator`` este codul folderului, de forma
    „{FDD39AD0-238F-46AF-ADB4-6C85480369C7}”. Se folosește deci numele real al
    folderului pe calculatorul respectiv, oricare ar fi limba Windows și
    oriunde ar fi mutat folderul (inclusiv în OneDrive).
    """
    if not este_windows():
        return None
    text = identificator.strip("{} ").replace("-", "")
    if len(text) != 32:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        import uuid as modul_uuid

        class _GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        numar = modul_uuid.UUID(text)
        identificator_struct = _GUID(
            numar.time_low,
            numar.time_mid,
            numar.time_hi_version,
            (ctypes.c_ubyte * 8)(*numar.bytes[8:]),
        )
        cale_text = ctypes.c_wchar_p()
        cod = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(identificator_struct), 0, None, ctypes.byref(cale_text)
        )
        if cod == 0 and cale_text.value:
            cale = Path(cale_text.value)
            ctypes.windll.ole32.CoTaskMemFree(cale_text)
            if cale.is_absolute():
                return cale
    except Exception:
        return None
    return None


def _folder_documente_windows() -> Path | None:
    """Folderul „Documente” cerut direct de la Windows (Known Folder API).

    Se folosește interfața oficială a Windows (``SHGetKnownFolderPath``), deci
    merge și când „Documente” a fost mutat în OneDrive sau pe alt disc, și
    când numele utilizatorului conține diacritice ori spații. Nu se
    presupune niciodată calea implicită.
    """
    return folder_cunoscut("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")


def folder_desktop_windows() -> Path | None:
    """Folderul Desktop, cerut de la Windows (nu presupus)."""
    return folder_cunoscut("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}")


def folder_start_menu_windows() -> Path | None:
    """Folderul „Programs” din meniul Start, cerut de la Windows."""
    return folder_cunoscut("{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}")


def are_drepturi_administrator() -> bool:
    """Adevărat dacă programul rulează cu drepturi de administrator.

    Se citește de la Windows, la fiecare apel; programul nu presupune niciodată
    că utilizatorul are sau nu are aceste drepturi.
    """
    if not este_windows():
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _folder_din_registry() -> Path | None:
    """Folderul „Documente” real al utilizatorului, citit din Windows.

    `Windows` poate muta „Documente” (de exemplu în OneDrive), deci nu se
    presupune niciodată calea implicită.
    """
    if not este_windows():
        return None
    try:
        import winreg  # type: ignore[import-not-found]

        cheie = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cheie) as handle:
            valoare, _ = winreg.QueryValueEx(handle, "Personal")
        cale = Path(os.path.expandvars(str(valoare)))
        if cale.is_absolute():
            return cale
    except Exception:
        return None
    return None


def _folder_utilizator() -> Path:
    """Folderul „Documente” al utilizatorului, cu rezerve sigure.

    Ordinea: interfața oficială Windows (Known Folder), registrul, apoi
    variantele obișnuite. Așa funcționează și cu „Documente” mutat în
    OneDrive, și cu nume de utilizator cu diacritice.
    """
    din_windows = _folder_documente_windows()
    if din_windows:
        return din_windows
    din_registry = _folder_din_registry()
    if din_registry:
        return din_registry
    # Nicio cale nu se presupune: dacă Windows nu a putut spune unde este
    # folderul (foarte rar), se folosește folderul utilizatorului.
    return Path.home()


def director_documente() -> Path:
    """Folderul „Documente” al utilizatorului, citit de la Windows."""
    return _folder_utilizator()


def _testeaza_scriere(folder: Path) -> bool:
    """Verifică dacă în folder se poate scrie (fără să lase resturi)."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        proba = folder / ".proba_scriere"
        proba.write_text("ok", encoding="utf-8")
        proba.unlink(missing_ok=True)
        return True
    except OSError:
        return False


@lru_cache(maxsize=1)
def _folder_ales() -> Path:
    """Alege folderul programului, cu rezerve, și îl notează în jurnal."""
    fortat = os.environ.get(VAR_MEDIU_FOLDER) or os.environ.get(VAR_MEDIU_FOLDER_VECHI)
    if fortat:
        return Path(fortat).expanduser().resolve()

    parinte = _local_appdata()
    candidati = [NUME_FOLDER, "Dictare&Transcriere Romana", "DictareTranscriereRomana"]
    for index, nume in enumerate(candidati):
        folder = parinte / nume
        if folder.exists() or _testeaza_scriere(folder):
            if index:
                _nota(
                    f"Folderul cu diacritice nu a putut fi folosit; s-a ales „{nume}”."
                )
            return folder
    # Ultima soluție: folderul temporar al utilizatorului.
    _nota("Nu am putut crea folderul obișnuit; folosesc folderul temporar al utilizatorului.")
    return Path(os.environ.get("TEMP", str(Path.home()))) / "DictareTranscriereRomana"


def _nota(mesaj: str) -> None:
    """Scrie o notă în jurnal fără a depinde de alte module (evită ciclurile)."""
    try:
        from . import jurnal

        jurnal.info(mesaj)
    except Exception:
        pass


# --------------------------------------------------------------------------- instalare


def director_instalare() -> Path:
    """Folderul principal al programului (fără drepturi de administrator)."""
    return _folder_ales()


def director_program() -> Path:
    """Copia instalată a programului (fișierele .py)."""
    return director_instalare() / "program"


def director_mediu() -> Path:
    """Mediul Python propriu al programului (venv)."""
    return director_instalare() / "mediu"


def python_mediu() -> Path:
    return director_mediu() / "Scripts" / "python.exe"


def pythonw_mediu() -> Path:
    return director_mediu() / "Scripts" / "pythonw.exe"


def director_model() -> Path:
    return director_instalare() / "model"


def fisier_model(preferat: str | None = None) -> Path:
    """Folderul cu modelul CTranslate2 (faster-whisper citește un folder).

    În kitul offline (program construit cu PyInstaller onedir), modelul este
    împachetat lângă program (``_internal/model/...``); dacă există acolo, se
    folosește direct, fără nicio descărcare la prima pornire.

    ``preferat`` spune care model se alege (v0.1.2): „auto” ia modelul
    standard (cel mai bun pe text lung de carte, măsurat), un nume explicit
    din ``MODELE_TRANSCRIBERE`` forțează acel model. Preferința are prioritate
    față de loc (kitul sau folderul de instalare).
    """
    from .constante import MODELE_TRANSCRIBERE, WHISPER_NUME, WHISPER_NUME_EEK, WHISPER_NUME_RO

    if preferat in (None, "", "auto"):
        candidate = [WHISPER_NUME_EEK, WHISPER_NUME, WHISPER_NUME_RO]
    elif preferat in MODELE_TRANSCRIBERE:
        candidate = [preferat, WHISPER_NUME_RO, WHISPER_NUME]
    else:
        candidate = [WHISPER_NUME_EEK, WHISPER_NUME, WHISPER_NUME_RO]

    radacini = []
    ambalat = getattr(sys, "_MEIPASS", None)
    if ambalat:
        radacini.append(Path(ambalat))
    radacini.append(director_model())
    for nume in candidate:
        for radacina in radacini:
            cale = radacina / "model" / nume
            if (cale / "model.bin").is_file() and (cale / "tokenizer.json").is_file():
                return cale
    return director_model() / WHISPER_NUME


def director_descarcari() -> Path:
    """Fișierele descărcate (model, LibreOffice, Python)."""
    return director_instalare() / "descarcari"


def director_libreoffice() -> Path:
    """Folderul în care programul ține informații despre LibreOffice."""
    return director_instalare() / "libreoffice"


def fisier_config() -> Path:
    return director_instalare() / "config.json"


def director_jurnale() -> Path:
    return director_instalare() / "jurnale"


def fisier_jurnal_instalare() -> Path:
    return director_jurnale() / "instalare.log"


def fisier_jurnal_aplicatie() -> Path:
    return director_jurnale() / "aplicatie.log"


def director_recuperare() -> Path:
    """Textul salvat automat, ca să nu se piardă la o pană de curent."""
    return director_instalare() / "recuperare"


def fisier_citeste_ma() -> Path:
    """„Citește-mă.txt”, pus lângă program."""
    return director_program() / NUME_CITESTE_MA


def director_iesiri() -> Path:
    """Unde se salvează documentele (implicit: Documente/Dictare&Transcriere Română)."""
    valoare = os.environ.get(VAR_MEDIU_IESIRI)
    if valoare:
        return Path(valoare).expanduser().resolve()
    return _folder_utilizator() / NUME_FOLDER


def pregateste_directoare() -> None:
    """Creează folderele de care are nevoie programul."""
    for folder in (
        director_instalare(),
        director_program(),
        director_model(),
        director_descarcari(),
        director_libreoffice(),
        director_jurnale(),
        director_recuperare(),
    ):
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Folderele se recreează la nevoie; lipsa lor nu oprește programul.
            pass


# --------------------------------------------------------------------------- sistem


def director_script() -> Path:
    """Folderul din care rulează sursa programului."""
    return Path(__file__).resolve().parent.parent


#: Codurile de arhitectură pe care le folosește Windows (IsWow64Process2).
_MASINI = {
    0x014C: "x86",
    0x8664: "AMD64",
    0xAA64: "ARM64",
    0x01C4: "ARM64",
}


def _arhitectura_reala() -> str:
    """Arhitectura reală a calculatorului, citită direct de la Windows.

    Pe calculatoarele ARM, un Python pe x64 rulat prin emulare raportează greșit
    „AMD64”; ``IsWow64Process2`` întoarce arhitectura calculatorului, nu pe cea
    a programului care rulează acum.
    """
    if not este_windows():
        return ""
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        functia = getattr(kernel32, "IsWow64Process2", None)
        if functia is None:
            return ""
        functia.restype = ctypes.c_int
        functia.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ushort),
            ctypes.POINTER(ctypes.c_ushort),
        ]
        proces = ctypes.c_ushort(0)
        masina = ctypes.c_ushort(0)
        # -1 este procesul curent (GetCurrentProcess).
        if not functia(ctypes.c_void_p(-1), ctypes.byref(proces), ctypes.byref(masina)):
            return ""
        return _MASINI.get(int(masina.value), "")
    except Exception:
        return ""


def arhitectura() -> str:
    """Arhitectura procesorului: AMD64, ARM64 sau x86.

    Se citește întâi de la Windows (corect și pe calculatoarele ARM, unde
    emularea arată altfel), apoi din variabilele de mediu și, la nevoie, din
    Python.
    """
    reala = _arhitectura_reala()
    if reala:
        return reala

    arh = (
        os.environ.get("PROCESSOR_ARCHITEW6432")
        or os.environ.get("PROCESSOR_ARCHITECTURE")
        or ""
    ).upper()
    if arh == "AMD64":
        return "AMD64"
    if arh == "ARM64":
        return "ARM64"
    if arh == "X86":
        return "x86"

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
    return f'"{text}"'


def nume_aplicatie() -> str:
    """Numele complet, pentru titluri și mesaje."""
    return NUME_APLICATIE
