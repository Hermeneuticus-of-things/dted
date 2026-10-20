"""Integrare cu Windows: scurtături, lista de programe, setările de sunet.

Totul se face în contul utilizatorului curent, deci **nu sunt necesare
drepturi de administrator**. Acolo unde un nume sau o cale conține semnul
„&” (ca în „Dictare&Transcriere Română”), textul este pus între ghilimele
simple sau duble, ca Windows să nu îl interpretească drept comandă.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import cai, jurnal
from .constante import (
    NUME_APLICATIE,
    NUME_PACHET,
    NUME_PUBLICATOR,
    NUME_SCURTATURA,
    SUBTITLU_RO,
    TITLU_FEREASTRA,
    VERSIUNE,
)

FLAG_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Cheia din registru în care Windows ține lista de programe instalate.
CHEIE_DEZINSTALARE = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DictareTranscriereRomana"
)


def _folder_din_registru(nume: str, rezerva: Path) -> Path:
    """Citește un folder special al Windows din registru (Desktop, Start Menu)."""
    try:
        import winreg  # type: ignore[import-not-found]

        cheie = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cheie) as handle:
            valoare, _ = winreg.QueryValueEx(handle, nume)
        cale = Path(os.path.expandvars(str(valoare)))
        if cale.is_absolute():
            return cale
    except Exception:
        pass
    return rezerva


def folder_desktop() -> Path:
    """Folderul Desktop al utilizatorului curent."""
    din_windows = cai.folder_desktop_windows()
    if din_windows:
        return din_windows
    return _folder_din_registru("Desktop", Path.home() / "Desktop")


def folder_start_menu() -> Path:
    """Folderul din meniul Start al utilizatorului curent."""
    din_windows = cai.folder_start_menu_windows()
    if din_windows:
        return din_windows
    return _folder_din_registru(
        "Programs",
        Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    )


# --------------------------------------------------------------------------- scurtături


def _escape_powershell(text: str) -> str:
    """Text sigur pentru PowerShell, între ghilimele simple."""
    return "'" + str(text).replace("'", "''") + "'"


def creeaza_scurtatura(
    destinatie: Path,
    tinta: Path,
    argumente: str = "",
    folder_lucru: Path | None = None,
    descriere: str = "",
    iconita: Path | None = None,
) -> bool:
    """Creează o scurtătură .lnk (fără drepturi de administrator)."""
    if not cai.este_windows():
        return False
    script = [
        "$eroare = $null",
        "$shell = New-Object -ComObject WScript.Shell",
        f"$scurtatura = $shell.CreateShortcut({_escape_powershell(destinatie)})",
        f"$scurtatura.TargetPath = {_escape_powershell(tinta)}",
        f"$scurtatura.Arguments = {_escape_powershell(argumente)}",
        f"$scurtatura.WorkingDirectory = {_escape_powershell(folder_lucru or tinta.parent)}",
        f"$scurtatura.Description = {_escape_powershell(descriere or TITLU_FEREASTRA)}",
    ]
    if iconita:
        script.append(f"$scurtatura.IconLocation = {_escape_powershell(str(iconita))}")
    script.append("$scurtatura.Save()")
    return _ruleaza_powershell(script)


def _ruleaza_powershell(linii: list[str]) -> bool:
    """Rulează un mic script PowerShell scris într-un fișier temporar."""
    import tempfile

    if not cai.este_windows():
        return False
    continut = "\n".join(linii) + "\n"
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".ps1", delete=False, encoding="utf-8-sig"
        ) as fisier:
            fisier.write(continut)
            cale_script = fisier.name
    except OSError:
        return False
    try:
        rezultat = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                cale_script,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=FLAG_NO_WINDOW,
        )
        if rezultat.returncode != 0:
            jurnal.atentionare(
                f"PowerShell a raportat o problemă: {(rezultat.stderr or '').strip()[:300]}"
            )
            return False
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        jurnal.atentionare(f"Nu am putut rula PowerShell: {exc}")
        return False
    finally:
        try:
            Path(cale_script).unlink(missing_ok=True)
        except OSError:
            pass


def _tinta_scurtatura() -> tuple[Path, str, Path, Path] | None:
    """Ce pornește scurtătura: interpretorul programului + pachetul lui."""
    pythonw = cai.pythonw_mediu()
    if pythonw.exists():
        return pythonw, f"-m {NUME_PACHET} --interfata", cai.director_program(), pythonw
    # Dacă programul rulează din sursă (fără instalare), scurtătura pornește
    # totuși programul, prin interpretorul curent.
    executabil = Path(sys.executable)
    pythonw_sursa = executabil.with_name("pythonw.exe")
    if pythonw_sursa.exists():
        return pythonw_sursa, f"-m {NUME_PACHET} --interfata", cai.director_script(), pythonw_sursa
    return None


def creeaza_scurtaturi(iconita: Path | None = None) -> list[Path]:
    """Creează scurtăturile de pe Desktop și din meniul Start."""
    date = _tinta_scurtatura()
    if not date:
        return []
    tinta, argumente, folder_lucru, _ = date
    create: list[Path] = []
    locatii = [
        folder_desktop() / f"{NUME_SCURTATURA}.lnk",
        folder_start_menu() / f"{NUME_SCURTATURA}.lnk",
    ]
    for destinatie in locatii:
        try:
            destinatie.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        if creeaza_scurtatura(
            destinatie,
            tinta,
            argumente,
            folder_lucru,
            descriere=f"{TITLU_FEREASTRA} — {SUBTITLU_RO}",
            iconita=iconita,
        ):
            create.append(destinatie)
    if create:
        jurnal.instalare(
            "Am creat scurtăturile: " + ", ".join(str(cale) for cale in create)
        )
    return create


def elimina_scurtaturi() -> None:
    """Șterge scurtăturile create de program."""
    for cale in (
        folder_desktop() / f"{NUME_SCURTATURA}.lnk",
        folder_start_menu() / f"{NUME_SCURTATURA}.lnk",
        # scurtăturile cu numele vechi, de la versiunile dinainte
        folder_desktop() / f"{NUME_APLICATIE}.lnk",
        folder_start_menu() / f"{NUME_APLICATIE}.lnk",
    ):
        try:
            cale.unlink(missing_ok=True)
        except OSError:
            pass


# --------------------------------------------------------------------------- listă programe


def inregistreaza_in_lista_programelor(iconita: Path | None = None) -> bool:
    """Adaugă programul în lista de programe instalate (fără administrator)."""
    try:
        import winreg  # type: ignore[import-not-found]

        pythonw = cai.pythonw_mediu()
        if not pythonw.exists():
            return False
        dezinstalare = f'"{pythonw}" -m {NUME_PACHET} --dezinstaleaza'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CHEIE_DEZINSTALARE) as cheie:
            valori = {
                "DisplayName": TITLU_FEREASTRA,
                "DisplayVersion": VERSIUNE,
                "Publisher": NUME_PUBLICATOR,
                "InstallLocation": str(cai.director_instalare()),
                "UninstallString": dezinstalare,
                "QuietUninstallString": f'"{pythonw}" -m {NUME_PACHET} --dezinstaleaza --tacut',
                "NoModify": 1,
                "NoRepair": 1,
                "InstallDate": _data_instalare(),
            }
            if iconita:
                valori["DisplayIcon"] = f"{iconita},0"
            for nume, valoare in valori.items():
                winreg.SetValueEx(cheie, nume, 0, winreg.REG_SZ, str(valoare))
            winreg.SetValueEx(
                cheie, "EstimatedSize", 0, winreg.REG_DWORD, _dimensiune_kb()
            )
        jurnal.instalare("Programul a fost adăugat în lista de programe din Windows.")
        return True
    except Exception as exc:  # pragma: no cover - depinde de Windows
        jurnal.atentionare(f"Nu am putut înregistra programul în listă: {exc}")
        return False


def scoate_din_lista_programelor() -> None:
    """Șterge programul din lista de programe instalate."""
    try:
        import winreg  # type: ignore[import-not-found]

        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CHEIE_DEZINSTALARE)
    except Exception:
        pass


def _data_instalare() -> str:
    import time

    return time.strftime("%Y%m%d")


def _dimensiune_kb() -> int:
    """Cât ocupă instalarea, în KB (pentru lista de programe din Windows)."""
    total = 0
    try:
        for cale in cai.director_instalare().rglob("*"):
            try:
                if cale.is_file():
                    total += cale.stat().st_size
            except OSError:
                continue
    except OSError:
        return 0
    return int(total / 1024)


# --------------------------------------------------------------------------- sistem


def deschide_fisier(cale: Path) -> bool:
    """Deschide un fișier cu programul potrivit din Windows."""
    try:
        os.startfile(str(cale))  # type: ignore[attr-defined]
        return True
    except Exception as exc:
        jurnal.atentionare(f"Nu am putut deschide {cale}: {exc}")
        return False


def deschide_folder(cale: Path) -> bool:
    """Deschide un folder în Explorer."""
    try:
        Path(cale).mkdir(parents=True, exist_ok=True)
        os.startfile(str(cale))  # type: ignore[attr-defined]
        return True
    except Exception as exc:
        jurnal.atentionare(f"Nu am putut deschide folderul {cale}: {exc}")
        return False


def deschide_setare(adresa: str) -> bool:
    """Deschide o pagină de setări din Windows (``ms-settings:``)."""
    return _deschide_setare(adresa)


def _deschide_setare(adresa: str) -> bool:
    """Deschide o pagină de setări din Windows (``ms-settings:``)."""
    if not cai.este_windows():
        return False
    try:
        os.startfile(adresa)  # type: ignore[attr-defined]
        return True
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", adresa], creationflags=FLAG_NO_WINDOW)
            return True
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut deschide setările Windows: {exc}")
            return False


def deschide_setari_microfon() -> bool:
    """Deschide pagina de confidențialitate pentru microfon."""
    return _deschide_setare("ms-settings:privacy-microphone")


def deschide_setari_sunet() -> bool:
    """Deschide pagina de sunet din Windows."""
    return _deschide_setare("ms-settings:sound")


def deschide_dispozitive_sunet() -> bool:
    """Deschide lista de dispozitive de sunet din Windows."""
    return _deschide_setare("ms-settings:sound-devices")


def muta_la_gunoi(cale: Path) -> bool:
    """Trimite un fișier la Coșul de reciclare (nu-l șterge definitiv).

    Se folosește chiar funcția Windows pentru Coșul de reciclare, așa că
    utilizatorul își poate recupera fișierul dacă a greșit. Dacă Windows nu
    poate trimite fișierul la Coș (de exemplu, o memorie fără Coș), funcția
    întoarce ``False`` și spune de ce.
    """
    if not cai.este_windows():
        return False
    cale = Path(cale)
    if not cale.exists():
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class _Operatie(ctypes.Structure):
            _fields_ = [
                ("hwing", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004
        FO_DELETE = 0x0003

        operatie = _Operatie()
        operatie.wFunc = FO_DELETE
        operatie.pFrom = str(cale) + "\0\0"
        operatie.pTo = None
        operatie.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
        rezultat = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operatie))
        if rezultat == 0 and not operatie.fAnyOperationsAborted and not cale.exists():
            jurnal.info(f"Fișier trimis la Coșul de reciclare: {cale.name}")
            return True
        jurnal.atentionare(f"Nu am putut trimite la Coșul de reciclare: {cale}")
        return False
    except Exception as exc:
        jurnal.atentionare(f"Nu am putut trimite la Coșul de reciclare: {exc}")
        return False


def porneste_fara_fereastra(comanda: list[str]) -> bool:
    """Pornește un program fără să apară o fereastră neagră."""
    try:
        subprocess.Popen(comanda, creationflags=FLAG_NO_WINDOW)
        return True
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut porni {comanda[0]}: {exc}")
        return False
