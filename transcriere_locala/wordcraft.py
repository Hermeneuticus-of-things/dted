"""Instalarea și lansarea WordCraft 0.8.0.

Se preferă varianta portabilă (fără drepturi de administrator). Dacă nu este
disponibilă pentru arhitectura calculatorului, se folosește pachetul MSI.

Toate fișierele sunt verificate cu suma SHA-256 din SHA256SUMS.txt publicat
oficial în aceeași pagină de release.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Callable

from . import cai, jurnal
from .constante import (
    WORDCRAFT_MSI,
    WORDCRAFT_PORTABIL,
    WORDCRAFT_RELEASE,
    WORDCRAFT_SUME_URL,
    WORDCRAFT_VERSIUNE,
)
from .descarcare import EroareDescarcare, SumaGresita, descarca

Progres = Callable[[str, float], None]  # (mesaj, fracțiune 0..1)


class EroareWordCraft(RuntimeError):
    """WordCraft nu a putut fi instalat sau pornit."""


# --------------------------------------------------------------------------- sume oficiale


def citeste_sume(text: str) -> dict[str, str]:
    """Transformă conținutul SHA256SUMS.txt într-un dicționar nume → sumă."""
    sume: dict[str, str] = {}
    for linie in text.splitlines():
        linie = linie.strip()
        if not linie or linie.startswith("#"):
            continue
        parti = linie.split()
        if len(parti) >= 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parti[0]):
            nume = parti[-1].lstrip("*")
            sume[nume] = parti[0].lower()
    return sume


def descarca_sume(destinatie: Path) -> dict[str, str]:
    """Descarcă lista oficială de sume și o citește."""
    if not destinatie.exists():
        descarca(WORDCRAFT_SUME_URL, destinatie)
    text = destinatie.read_text(encoding="utf-8", errors="replace")
    sume = citeste_sume(text)
    if not sume:
        raise EroareWordCraft(
            "Lista oficială de sume pentru WordCraft nu a putut fi citită. "
            "Verifică legătura la internet și încearcă din nou."
        )
    return sume


def alege_fisier(arhitectura: str, sume: dict[str, str]) -> tuple[str, bool]:
    """Alege pachetul potrivit: (nume fișier, este portabil)."""
    portabil = WORDCRAFT_PORTABIL.get(arhitectura)
    if portabil and portabil in sume:
        return portabil, True
    msi = WORDCRAFT_MSI.get(arhitectura)
    if msi and msi in sume:
        return msi, False
    raise EroareWordCraft(
        f"Nu există o versiune WordCraft {WORDCRAFT_VERSIUNE} pentru acest tip de procesor "
        f"({arhitectura}). Programul de transcriere poate fi folosit, dar fișierele "
        "vor putea fi salvate doar ca DOCX sau ODT, fără deschidere directă în WordCraft."
    )


# --------------------------------------------------------------------------- instalare


def gaseste_executabil(folder: Path) -> Path | None:
    """Caută wordcraft.exe în folderul dat (inclusiv subfoldere)."""
    candidat = folder / "wordcraft.exe"
    if candidat.exists():
        return candidat
    for cale in folder.rglob("wordcraft.exe"):
        return cale
    return None


def _extrage_zip(arhiva: Path, destinatie: Path) -> Path:
    destinatie.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(arhiva) as zip_fisier:
        # Protecție împotriva arhivelor care încearcă să scrie în afara folderului.
        baza = destinatie.resolve()
        for membru in zip_fisier.infolist():
            tinta = (destinatie / membru.filename).resolve()
            if not str(tinta).startswith(str(baza)):
                raise EroareWordCraft("Arhiva WordCraft conține căi neobișnuite; instalarea a fost oprită.")
        zip_fisier.extractall(destinatie)
    return destinatie


def instaleaza(
    progres: Progres | None = None,
    director: Path | None = None,
    arhitectura: str | None = None,
) -> Path | None:
    """Descarcă și instalează WordCraft. Întoarce calea către wordcraft.exe."""
    arhitectura = arhitectura or cai.arhitectura()
    director = director or cai.director_instalare()
    descarcari = director / "descarcari"
    descarcari.mkdir(parents=True, exist_ok=True)

    def anunta(mesaj: str, fractiune: float = 0.0) -> None:
        jurnal.instalare(mesaj)
        if progres:
            progres(mesaj, fractiune)

    anunta("Verific lista oficială de sume pentru WordCraft…", 0.02)
    sume = descarca_sume(descarcari / "SHA256SUMS.txt")

    nume_fisier, portabil = alege_fisier(arhitectura, sume)
    suma = sume[nume_fisier]
    url = f"{WORDCRAFT_RELEASE}/{nume_fisier}"
    arhiva = descarcari / nume_fisier

    anunta(f"Descarc WordCraft {WORDCRAFT_VERSIUNE} ({nume_fisier})…", 0.05)
    if arhiva.exists():
        from .descarcare import sha256_fisier

        if sha256_fisier(arhiva) != suma:
            arhiva.unlink(missing_ok=True)

    if not arhiva.exists():
        def progres_descarcare(descarcat: int, total: int) -> None:
            if total:
                anunta(
                    f"Descarc WordCraft: {min(99, int(descarcat * 100 / total))}%",
                    0.05 + 0.35 * descarcat / total,
                )

        try:
            descarca(url, arhiva, progres_descarcare, suma)
        except SumaGresita:
            raise
        except EroareDescarcare as exc:
            raise EroareWordCraft(
                "WordCraft nu a putut fi descărcat. Programul de transcriere merge și fără el: "
                "poți salva fișierele ca DOCX sau ODT. Detalii: " + str(exc)
            ) from exc

    anunta("Verific suma fișierului WordCraft…", 0.42)
    from .descarcare import sha256_fisier

    if sha256_fisier(arhiva) != suma:
        raise SumaGresita(nume_fisier, suma, sha256_fisier(arhiva))

    if portabil:
        anunta("Instalez WordCraft (fără drepturi de administrator)…", 0.5)
        tinta = director / "WordCraft"
        if tinta.exists():
            shutil.rmtree(tinta, ignore_errors=True)
        _extrage_zip(arhiva, tinta)
        executabil = gaseste_executabil(tinta)
        if not executabil:
            raise EroareWordCraft(
                "Arhiva WordCraft nu conține programul așteptat. "
                "Descarcă din nou WordCraft sau continuă fără el."
            )
        anunta("WordCraft a fost instalat.", 0.6)
        return executabil

    # Varianta MSI: instalare per utilizator, fără drepturi de administrator.
    anunta("Instalez WordCraft cu pachetul oficial (poate dura un minut)…", 0.5)
    folder_ales = director / "WordCraft"
    comanda = [
        "msiexec",
        "/i",
        str(arhiva),
        "/qn",
        "/norestart",
        f"INSTALLDIR={folder_ales}",
        "MSIINSTALLPERUSER=1",
        "ALLUSERS=2",
    ]
    try:
        rezultat = subprocess.run(
            comanda,
            capture_output=True,
            text=True,
            timeout=600,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        jurnal.instalare(f"Instalarea MSI a eșuat: {exc}")
        rezultat = None

    executabil = gaseste_executabil(folder_ales) if folder_ales.exists() else None
    if executabil:
        anunta("WordCraft a fost instalat.", 0.6)
        return executabil

    gasit = gaseste_wordcraft_instalat()
    if gasit:
        anunta("WordCraft era deja instalat pe calculator.", 0.6)
        return gasit

    cod = getattr(rezultat, "returncode", "necunoscut")
    jurnal.instalare(f"MSI WordCraft nu a produs un executabil (cod {cod}).")
    raise EroareWordCraft(
        "WordCraft nu a putut fi instalat automat pe acest calculator "
        f"(cod {cod}). Poți continua: fișierele se salvează ca DOCX sau ODT. "
        "Dacă vrei WordCraft, îl poți instala manual de pe pagina oficială GitHub."
    )


# --------------------------------------------------------------------------- găsire și lansare


def _locatii_wordcraft() -> list[Path]:
    """Locuri în care poate fi WordCraft, fără căi fixe."""
    locatii: list[Path] = [cai.director_wordcraft()]
    for variabila in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"):
        radacina = os.environ.get(variabila)
        if radacina:
            locatii.append(Path(radacina) / "WordCraft")
            locatii.append(Path(radacina) / "Programs" / "WordCraft")
    return locatii


def gaseste_wordcraft_instalat() -> Path | None:
    """Caută wordcraft.exe în locurile obișnuite și în registru."""
    for locatie in _locatii_wordcraft():
        executabil = gaseste_executabil(locatie)
        if executabil:
            return executabil

    # Registru: cheile de dezinstalare, doar citire.
    try:
        import winreg

        chei = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
        ]
        for radacina, cale in chei:
            try:
                with winreg.OpenKey(radacina, cale) as cheie:
                    for index in range(winreg.QueryInfoKey(cheie)[0]):
                        try:
                            nume_subcheie = winreg.EnumKey(cheie, index)
                            with winreg.OpenKey(cheie, nume_subcheie) as subcheie:
                                nume = str(winreg.QueryValueEx(subcheie, "DisplayName")[0])
                                if "wordcraft" in nume.lower():
                                    locatie = Path(
                                        str(winreg.QueryValueEx(subcheie, "InstallLocation")[0])
                                    )
                                    executabil = gaseste_executabil(locatie)
                                    if executabil:
                                        return executabil
                        except OSError:
                            continue
            except OSError:
                continue
    except ImportError:
        pass
    return None


def deschide(executabil: Path, document: Path | None = None) -> None:
    """Deschide WordCraft, eventual cu un document."""
    if not executabil.exists():
        raise EroareWordCraft(
            "Nu găsesc programul WordCraft. Reinstalează-l din pagina oficială GitHub "
            "sau salvează documentul ca DOCX și deschide-l manual."
        )
    comanda = [str(executabil)]
    if document:
        comanda.append(str(document))
    try:
        subprocess.Popen(comanda, close_fds=True)
    except OSError as exc:
        raise EroareWordCraft(
            f"WordCraft nu a pornit ({exc}). Salvează documentul și deschide-l manual."
        ) from exc
