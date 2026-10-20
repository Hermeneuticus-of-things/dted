"""Programele de scris de pe calculator (LibreOffice rămâne implicit).

LibreOffice este programul de scris implicit, instalat și setat în română.
Dacă pe calculator există și alt program de scris (de exemplu Microsoft Word),
programul îl găsește singur, fără internet, și îl oferă ca variantă.

Căutarea se face prin Windows, nu prin căi fixe:

* din asocierile de fișiere pentru ``.docx`` și ``.odt``
  (``HKCU\\...\\Explorer\\FileExts`` și ``HKCR``);
* din lista de programe pentru fișiere executabile
  (``App Paths`` din registru).

Nu se caută și nu se propune WordCraft sau OpenOffice, iar programele
găsite nu sunt instalate, configurate sau modificate în vreun fel.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import jurnal
from .libreoffice import gaseste_libreoffice

FLAG_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Cuvinte care arată că un program nu trebuie propus.
_EXCLUSE = ("wordcraft", "openoffice", "open office")

#: Nume cunoscute, pentru un text pe înțeles în listă.
_NUME_CUNOSCUTE = {
    "winword.exe": "Microsoft Word",
    "soffice.exe": "LibreOffice Writer",
    "swriter.exe": "Apache OpenOffice Writer",
    "wordpad.exe": "WordPad",
    "notepad.exe": "Notepad",
    "notepad++.exe": "Notepad++",
    "wps.exe": "WPS Writer",
    "hwp.exe": "Hangul",
    "abiword.exe": "AbiWord",
    "textmaker.exe": "TextMaker",
}


@dataclass
class ProgramScris:
    """Un program de scris găsit pe calculator."""

    cheie: str
    nume: str
    executabil: Path
    implicit: bool = False

    def descriere(self) -> str:
        """Textul din listă, cu mențiunea pentru programul implicit."""
        return f"{self.nume} (implicit)" if self.implicit else self.nume


# --------------------------------------------------------------------------- căutare


def _nume_prietenos(executabil: Path) -> str:
    """Un nume pe înțeles pentru utilizator, pornind de la fișier."""
    nume_fisier = executabil.name.lower()
    if nume_fisier in _NUME_CUNOSCUTE:
        return _NUME_CUNOSCUTE[nume_fisier]
    # Numele din informațiile fișierului, dacă Windows îl are.
    try:
        cale = str(executabil)
        nume = Path(executabil).stem.replace("_", " ").replace("-", " ").strip()
        if not nume:
            raise ValueError
        return nume[0].upper() + nume[1:]
    except Exception:
        return str(nume_fisier)


def _este_exclus(executabil: Path) -> bool:
    text = str(executabil).lower()
    return any(cuvant in text for cuvant in _EXCLUSE)


def _curata_comanda(comanda: str) -> Path | None:
    """Scoate calea executabilului dintr-o comandă de tip „"C:\\...\\app.exe" "%1"”."""
    comanda = comanda.strip()
    if not comanda:
        return None
    comanda = os.path.expandvars(comanda)
    if comanda.startswith('"'):
        sfarsit = comanda.find('"', 1)
        if sfarsit == -1:
            return None
        cale = comanda[1:sfarsit]
    else:
        cale = comanda.split(" ")[0]
    # Scurtăturile „rundll32” și comenzile speciale nu sunt programe de scris.
    if cale.lower().endswith(".dll") or "rundll32" in cale.lower():
        return None
    fisier = Path(cale)
    return fisier if fisier.exists() else None


def _din_asociere(extensie: str) -> Path | None:
    """Executabilul asociat în Windows cu o extensie (.docx, .odt)."""
    try:
        import winreg  # type: ignore[import-not-found]
    except Exception:
        return None

    prog_id = ""
    # 1. alegerea utilizatorului pentru extensie
    try:
        cale = rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{extensie}\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cale) as handle:
            prog_id = str(winreg.QueryValueEx(handle, "ProgId")[0])
    except OSError:
        prog_id = ""
    # 2. asocierea generală
    if not prog_id:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, extensie) as handle:
                prog_id = str(winreg.QueryValueEx(handle, "")[0])
        except OSError:
            prog_id = ""
    if not prog_id:
        return None

    for ramura in ("shell\\open\\command", "shell\\Edit\\command"):
        for radacina in (winreg.HKEY_CLASSES_ROOT, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(radacina, f"{prog_id}\\{ramura}") as handle:
                    comanda = str(winreg.QueryValueEx(handle, "")[0])
            except OSError:
                continue
            executabil = _curata_comanda(comanda)
            if executabil:
                return executabil
    return None


def _din_app_paths(nume_executabil: str) -> Path | None:
    """Executabilul unui program cunoscut, citit din lista Windows „App Paths”."""
    try:
        import winreg  # type: ignore[import-not-found]
    except Exception:
        return None

    cale = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{nume_executabil}"
    variante = [
        (winreg.HKEY_CURRENT_USER, 0),
        (winreg.HKEY_LOCAL_MACHINE, 0),
        (winreg.HKEY_LOCAL_MACHINE, getattr(winreg, "KEY_WOW64_64KEY", 0)),
    ]
    for radacina, flag in variante:
        for nume_valoare in ("", "Path"):
            try:
                with winreg.OpenKey(radacina, cale, 0, winreg.KEY_READ | flag) as handle:
                    valoare = str(winreg.QueryValueEx(handle, nume_valoare)[0])
            except OSError:
                continue
            candidat = Path(os.path.expandvars(valoare))
            if candidat.is_file():
                return candidat
            executabil = candidat / nume_executabil
            if executabil.is_file():
                return executabil
    return None


def gaseste_programe() -> list[ProgramScris]:
    """Toate programele de scris disponibile, cu LibreOffice primul."""
    gasite: list[ProgramScris] = []
    vazute: set[str] = set()

    def adauga(executabil: Path | None, implicit: bool = False) -> None:
        if not executabil or _este_exclus(executabil):
            return
        cheie = str(executabil).lower()
        if cheie in vazute:
            return
        vazute.add(cheie)
        gasite.append(
            ProgramScris(cheie=cheie, nume=_nume_prietenos(executabil), executabil=executabil, implicit=implicit)
        )

    adauga(gaseste_libreoffice(), implicit=True)
    for extensie in (".docx", ".odt", ".rtf", ".txt"):
        adauga(_din_asociere(extensie))
    for nume in ("WINWORD.EXE", "soffice.exe", "wps.exe", "notepad++.exe", "wordpad.exe"):
        adauga(_din_app_paths(nume))

    # LibreOffice rămâne primul în listă, chiar dacă a fost găsit mai târziu.
    gasite.sort(key=lambda program: (not program.implicit, program.nume.lower()))
    jurnal.info(
        "Programe de scris găsite: "
        + (", ".join(program.nume for program in gasite) if gasite else "niciunul")
    )
    return gasite


def alte_programe() -> list[ProgramScris]:
    """Programele de scris în care se poate deschide documentul, în afară de implicit."""
    return [program for program in gaseste_programe() if not program.implicit]


def dupa_cheie(cheie: str) -> ProgramScris | None:
    """Găsește un program după cheia (calea) salvată în setări."""
    if not cheie:
        return None
    for program in gaseste_programe():
        if program.cheie == cheie:
            return program
    return None


def deschide(cale: Path, program: ProgramScris | None = None) -> tuple[bool, str]:
    """Deschide documentul în programul ales.

    Dacă programul ales nu mai există sau nu pornește, se explică simplu și
    documentul este deschis în LibreOffice.
    """
    from . import libreoffice

    if program is None:
        return libreoffice.deschide_in_writer(cale)

    if not program.executabil.exists():
        mesaj = (
            f"Programul „{program.nume}” nu mai este pe calculator. "
            "Deschid documentul în LibreOffice."
        )
        jurnal.atentionare(mesaj)
        ok, _ = libreoffice.deschide_in_writer(cale)
        return ok, mesaj

    try:
        subprocess.Popen(
            [str(program.executabil), str(cale)], creationflags=FLAG_NO_WINDOW
        )
        return True, ""
    except OSError as exc:
        mesaj = (
            f"Programul „{program.nume}” nu a pornit ({exc}). "
            "Îl deschid în LibreOffice."
        )
        jurnal.atentionare(mesaj)
        ok, _ = libreoffice.deschide_in_writer(cale)
        return ok, mesaj


def rezumat_pentru_utilizator() -> str:
    """Text simplu despre programele de scris găsite."""
    programe = gaseste_programe()
    if not programe:
        return "Nu am găsit niciun program de scris pe acest calculator."
    if len(programe) == 1:
        return f"Programul de scris folosit este {programe[0].nume}."
    return (
        "Programul de scris implicit este LibreOffice Writer. "
        "Mai sunt disponibile: " + ", ".join(program.nume for program in programe[1:]) + "."
    )
