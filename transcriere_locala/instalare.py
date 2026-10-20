"""Instalarea completă, într-un singur pas, fără întrebări tehnice.

Pașii:
 1. Python privat al programului (fără drepturi de administrator)
 2. mediu virtual + biblioteci (PyTorch, Whisper, microfon, ffmpeg)
 3. modelul Whisper large-v3-turbo, verificat SHA-256
 4. WordCraft 0.8.0, verificat SHA-256

Fiecare pas raportează progres în cuvinte simple, iar orice eroare este
tradusă într-un mesaj care spune ce s-a întâmplat și ce trebuie făcut.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import cai, config, jurnal, wordcraft
from .constante import (
    PACHETE,
    PACHET_WHISPER,
    PYTHON_URL,
    PYTHON_VERSIUNE,
    TORCH_INDEX_CPU,
    TORCH_INDEX_CUDA,
    WHISPER_BYTES,
    WHISPER_SHA256,
    WHISPER_URL,
)
from .descarcare import EroareDescarcare, SumaGresita, descarca, sha256_fisier, text_progres

Progres = Callable[[str, float], None]  # (mesaj simplu, fracțiune 0..1)


class EroareInstalare(RuntimeError):
    """Instalarea nu poate continua; mesajul este pentru utilizator."""


FLAG_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class Optiuni:
    """Alegerea utilizatorului la începutul instalării."""

    cu_gpu: bool = False
    instaleaza_wordcraft: bool = True
    sari_verificarea: bool = False


def _anunta(progres: Progres | None, mesaj: str, fractiune: float) -> None:
    jurnal.instalare(mesaj)
    if progres:
        progres(mesaj, max(0.0, min(1.0, fractiune)))


def _ruleaza(comanda: list[str], descriere: str, timeout: int = 3600) -> subprocess.CompletedProcess:
    """Rulează o comandă și întoarce rezultatul, cu erori explicite."""
    jurnal.instalare(f"Rulez: {' '.join(comanda)}")
    try:
        rezultat = subprocess.run(
            comanda,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=FLAG_NO_WINDOW,
        )
    except FileNotFoundError as exc:
        raise EroareInstalare(
            f"Nu am găsit un program necesar pentru {descriere.lower()}. "
            "Repornește instalarea; dacă problema apare din nou, trimite fișierul "
            f"„{cai.fisier_jurnal_instalare()}”."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise EroareInstalare(
            f"{descriere} a durat prea mult și a fost oprită. Verifică legătura la internet "
            "și încearcă din nou."
        ) from exc
    if rezultat.returncode != 0:
        detalii = (rezultat.stderr or rezultat.stdout or "").strip().splitlines()
        coada = " | ".join(detalii[-3:]) if detalii else "fără detalii"
        jurnal.instalare(f"Eroare la {descriere}: cod {rezultat.returncode}: {coada}")
        raise EroareInstalare(
            f"Un pas al instalării a eșuat: {descriere.lower()}.\n"
            f"Detaliu: {coada}\n"
            f"Jurnalul complet este în „{cai.fisier_jurnal_instalare()}”."
        )
    return rezultat


def copiaza_programul(progres: Progres | None) -> Path:
    """Copiază sursa programului în folderul de instalare.

    Astfel programul rămâne instalat complet în folderul lui, iar scurtătura
    de pe desktop funcționează chiar dacă utilizatorul șterge arhiva din care
    a instalat.
    """
    sursa = cai.director_script()
    tinta = cai.director_program()
    if sursa.resolve() == tinta.resolve():
        return tinta  # rulează deja din folderul instalat

    _anunta(progres, "Pregătesc fișierele programului…", 0.01)
    tinta.mkdir(parents=True, exist_ok=True)
    for nume in ("transcriere_locala", "pornire.py", "README.md", "LICENTA.txt"):
        element = sursa / nume
        if not element.exists():
            continue
        destinatie = tinta / nume
        if element.is_dir():
            shutil.copytree(
                element,
                destinatie,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(element, destinatie)
    jurnal.instalare(f"Programul a fost copiat în {tinta}")
    return tinta


# --------------------------------------------------------------------------- 1. Python


def _python_sistem_valid() -> Path | None:
    """Caută un Python 3.10–3.12 pe 64 de biți deja instalat."""
    candidati: list[Path] = []
    for comanda in ("py", "python"):
        try:
            rezultat = subprocess.run(
                [comanda, "-c", "import sys;print(sys.executable)"],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=FLAG_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if rezultat.returncode == 0:
            cale = Path(rezultat.stdout.strip())
            if cale.exists():
                candidati.append(cale)
    for cale in candidati:
        if _python_potrivit(cale):
            return cale
    return None


def _python_potrivit(executabil: Path) -> bool:
    """Verifică versiunea și arhitectura unui Python."""
    try:
        rezultat = subprocess.run(
            [
                str(executabil),
                "-c",
                "import sys,struct;print(f'{sys.version_info[0]}.{sys.version_info[1]}|{struct.calcsize(\"P\")*8}')",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=FLAG_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if rezultat.returncode != 0:
        return False
    try:
        versiune, biti = rezultat.stdout.strip().split("|")
        major, minor = (int(x) for x in versiune.split("."))
    except ValueError:
        return False
    return (major, minor) in ((3, 10), (3, 11), (3, 12)) and biti == "64"


def _instaleaza_python_privat(progres: Progres | None) -> Path:
    """Instalează un Python privat, în folderul programului, fără administrator."""
    arhitectura = cai.arhitectura()
    url = PYTHON_URL.get(arhitectura)
    if not url:
        raise EroareInstalare(
            "Pe acest tip de procesor nu pot instala automat Python. "
            "Programul are nevoie de un calculator cu Windows pe 64 de biți (Intel sau AMD)."
        )

    descarcari = cai.director_descarcari()
    descarcari.mkdir(parents=True, exist_ok=True)
    instalator = descarcari / Path(url).name
    tinta = cai.director_instalare() / "Python"

    if not instalator.exists():
        _anunta(progres, "Descarc o componentă necesară (Python)…", 0.02)

        def arata(descarcat: int, total: int) -> None:
            _anunta(progres, text_progres(descarcat, total, "Descarc Python"), 0.02 + 0.06 * (descarcat / total if total else 0))

        descarca(url, instalator, arata)

    _anunta(progres, "Instalez Python (fără drepturi de administrator)…", 0.09)
    comanda = [
        str(instalator),
        "/quiet",
        "InstallAllUsers=0",
        f"TargetDir={tinta}",
        "Include_pip=1",
        "Include_launcher=0",
        "Include_test=0",
        "Include_doc=0",
        "Include_tcltk=1",
        "PrependPath=0",
        "Shortcuts=0",
        "AssociateFiles=0",
    ]
    rezultat = subprocess.run(
        comanda, capture_output=True, text=True, timeout=1800, creationflags=FLAG_NO_WINDOW
    )
    jurnal.instalare(f"Instalator Python cod: {rezultat.returncode}")
    executabil = tinta / "python.exe"
    if not executabil.exists():
        raise EroareInstalare(
            "Python nu a putut fi instalat automat. Închide programele care blochează "
            "instalarea și încearcă din nou, sau instalează Python 3.12 de pe python.org "
            "și rulează din nou instalarea."
        )
    return executabil


def asigura_python(progres: Progres | None) -> Path:
    """Întoarce un Python 3.10–3.12 pe 64 de biți, instalând unul dacă lipsește."""
    privat = cai.director_instalare() / "Python" / "python.exe"
    if privat.exists() and _python_potrivit(privat):
        _anunta(progres, "Python este deja instalat.", 0.1)
        return privat
    gasit = _python_sistem_valid()
    if gasit:
        _anunta(progres, f"Folosesc Python deja instalat ({gasit}).", 0.1)
        return gasit
    return _instaleaza_python_privat(progres)


# --------------------------------------------------------------------------- 2. biblioteci


def _pip(python: Path, argumente: list[str], descriere: str) -> None:
    _ruleaza(
        [str(python), "-m", "pip", "--disable-pip-version-check", *argumente],
        descriere,
        timeout=5400,
    )


def creeaza_mediu(progres: Progres | None) -> Path:
    """Creează mediul virtual al programului."""
    python_mediu = cai.python_mediu()
    if python_mediu.exists():
        _anunta(progres, "Bibliotecile sunt deja instalate.", 0.2)
        return python_mediu

    baza = asigura_python(progres)
    _anunta(progres, "Pregătesc spațiul de lucru al programului…", 0.12)
    cai.pregateste_directoare()
    if cai.director_mediu().exists():
        shutil.rmtree(cai.director_mediu(), ignore_errors=True)
    _ruleaza([str(baza), "-m", "venv", str(cai.director_mediu())], "Pregătirea mediului Python")
    if not python_mediu.exists():
        raise EroareInstalare(
            "Nu am putut pregăti spațiul de lucru al programului. "
            "Verifică dacă antivirusul nu blochează folderul și încearcă din nou."
        )
    _pip(python_mediu, ["install", "--upgrade", "pip", "setuptools", "wheel"], "Actualizarea instalatorului de biblioteci")
    return python_mediu


def instaleaza_biblioteci(progres: Progres | None, cu_gpu: bool) -> None:
    """Instalează PyTorch (CPU sau CUDA), Whisper și celelalte pachete."""
    python_mediu = cai.python_mediu()
    if not python_mediu.exists():
        raise EroareInstalare("Spațiul de lucru lipsește. Rulează din nou instalarea.")

    deja = _are_whisper(python_mediu)
    if deja:
        _anunta(progres, "Bibliotecile sunt deja instalate.", 0.45)
        return

    index = TORCH_INDEX_CUDA if cu_gpu else TORCH_INDEX_CPU
    eticheta = "cu accelerare video" if cu_gpu else "pe procesor"
    _anunta(progres, f"Descarc biblioteca de transcriere ({eticheta})… durează câteva minute.", 0.18)
    _pip(
        python_mediu,
        ["install", "--index-url", index, "torch"],
        "Descărcarea bibliotecii de transcriere",
    )
    if cu_gpu and not _are_cuda(python_mediu):
        _anunta(progres, "Placa video nu a fost recunoscută; folosesc procesorul.", 0.4)
        _pip(
            python_mediu,
            ["install", "--force-reinstall", "--index-url", TORCH_INDEX_CPU, "torch"],
            "Reinstalarea bibliotecii pentru procesor",
        )

    _anunta(progres, "Instalez programele de transcriere…", 0.3)
    _pip(python_mediu, ["install", *PACHETE], "Instalarea programelor de bază")
    _pip(python_mediu, ["install", PACHET_WHISPER], "Instalarea programului de transcriere")
    _anunta(progres, "Bibliotecile au fost instalate.", 0.45)


def _are_whisper(python_mediu: Path) -> bool:
    try:
        rezultat = subprocess.run(
            [str(python_mediu), "-c", "import whisper, sounddevice, imageio_ffmpeg"],
            capture_output=True,
            timeout=180,
            creationflags=FLAG_NO_WINDOW,
        )
        return rezultat.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _are_cuda(python_mediu: Path) -> bool:
    try:
        rezultat = subprocess.run(
            [str(python_mediu), "-c", "import torch;print(torch.cuda.is_available())"],
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=FLAG_NO_WINDOW,
        )
        return rezultat.returncode == 0 and "True" in rezultat.stdout
    except (OSError, subprocess.SubprocessError):
        return False


# --------------------------------------------------------------------------- 3. model


def asigura_model(progres: Progres | None, baza: float = 0.45, spatiu: float = 0.4) -> Path:
    """Descarcă modelul Whisper și verifică suma SHA-256 oficială."""
    fisier = cai.fisier_model()
    if fisier.exists():
        _anunta(progres, "Verific modelul de transcriere…", baza)
        if sha256_fisier(fisier).lower() == WHISPER_SHA256:
            _anunta(progres, "Modelul de transcriere este gata.", baza + spatiu)
            return fisier
        jurnal.instalare("Modelul existent are altă sumă; îl descarc din nou.")
        fisier.unlink(missing_ok=True)

    cai.director_model().mkdir(parents=True, exist_ok=True)
    _anunta(
        progres,
        "Descarc modelul de transcriere (aproximativ 1,6 GB)… poate dura câteva minute.",
        baza,
    )

    def arata(descarcat: int, total: int) -> None:
        total = total or WHISPER_BYTES
        _anunta(
            progres,
            text_progres(descarcat, total, "Descarc modelul de transcriere"),
            baza + spatiu * (descarcat / total if total else 0),
        )

    try:
        descarca(WHISPER_URL, fisier, arata, WHISPER_SHA256)
    except SumaGresita:
        raise
    except EroareDescarcare as exc:
        raise EroareInstalare(
            "Modelul de transcriere nu a putut fi descărcat. "
            "Verifică legătura la internet și spațiul liber pe disc, apoi încearcă din nou.\n"
            f"Detaliu: {exc}"
        ) from exc

    _anunta(progres, "Modelul de transcriere a fost verificat și este gata.", baza + spatiu)
    return fisier


# --------------------------------------------------------------------------- instalare completă


def instaleaza(
    optiuni: Optiuni,
    progres: Progres | None = None,
    director: Path | None = None,
) -> dict[str, str]:
    """Rulează toți pașii de instalare și întoarce un rezumat."""
    if director is not None:
        os.environ["TRANSCRIERE_DIR"] = str(director)

    cai.pregateste_directoare()
    jurnal.instalare("=" * 70)
    jurnal.instalare("ÎNCEPERE INSTALARE NOUĂ")
    _anunta(progres, "Încep instalarea. Nu închide fereastra.", 0.0)
    jurnal.instalare(
        f"Instalare pornită. Director: {cai.director_instalare()} · "
        f"arhitectură: {cai.arhitectura()} · Windows build: {sys.getwindowsversion().build if cai.este_windows() else '?'}"
    )
    if optiuni.sari_verificarea:
        jurnal.instalare(
            "UTILIZATORUL A ALES „Sari peste verificare” — verificarea resurselor nu a fost aplicată."
        )

    rezumat: dict[str, str] = {}

    # 1. mediu Python
    creeaza_mediu(progres)
    rezumat["python"] = str(cai.python_mediu())

    # 2. biblioteci
    instaleaza_biblioteci(progres, optiuni.cu_gpu)
    rezumat["biblioteci"] = "instalate"

    # 3. model
    asigura_model(progres, 0.45, 0.4)
    rezumat["model"] = str(cai.fisier_model())

    # 4. WordCraft
    if optiuni.instaleaza_wordcraft:
        _anunta(progres, "Instalez WordCraft (editorul de documente)…", 0.85)
        try:
            executabil = wordcraft.instaleaza(
                progres=lambda mesaj, fractiune: _anunta(progres, mesaj, 0.85 + 0.13 * fractiune),
                director=cai.director_instalare(),
                arhitectura=cai.arhitectura(),
            )
            rezumat["wordcraft"] = str(executabil) if executabil else "indisponibil"
        except (wordcraft.EroareWordCraft, SumaGresita) as exc:
            # WordCraft este opțional: transcrierea merge și fără el.
            jurnal.instalare(f"WordCraft nu a fost instalat: {exc}")
            rezumat["wordcraft"] = "indisponibil"
    else:
        rezumat["wordcraft"] = "neinstalat (la cererea utilizatorului)"

    # 5. setări
    setari = config.incarca()
    setari.versiune_instalare = f"1.0.0 ({time.strftime('%Y-%m-%d')})"
    setari.dispozitiv = "cuda" if (optiuni.cu_gpu and _are_cuda(cai.python_mediu())) else "cpu"
    if rezumat.get("wordcraft", "").endswith(".exe"):
        setari.wordcraft_executabil = rezumat["wordcraft"]
    config.salveaza(setari)

    _anunta(progres, "Instalarea s-a terminat. Programul este gata de folosire.", 1.0)
    jurnal.instalare(f"Instalare încheiată. Rezumat: {rezumat}")
    return rezumat


def verifica_instalare() -> list[str]:
    """Listă de probleme găsite după instalare (goală dacă totul e în regulă)."""
    probleme: list[str] = []
    if not cai.python_mediu().exists():
        probleme.append("Spațiul de lucru Python lipsește.")
    elif not _are_whisper(cai.python_mediu()):
        probleme.append("Bibliotecile de transcriere nu sunt instalate.")
    if not cai.fisier_model().exists():
        probleme.append("Modelul de transcriere lipsește.")
    return probleme
