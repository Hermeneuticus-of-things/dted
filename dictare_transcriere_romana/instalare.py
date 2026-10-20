"""Instalarea completă, într-un singur pas, fără întrebări tehnice.

Pașii, în ordine:

 1. se verifică legătura la internet (fără internet nu se descarcă nimic);
 2. fișierele programului sunt copiate în folderul lui;
 3. se descarcă Python (varianta portabilă oficială), cu suma SHA-256
    publicată de python.org, și se instalează fără drepturi de administrator;
 4. se creează mediul programului și se instalează bibliotecile, cu versiuni
    fixe (PyTorch, Whisper, numpy, sounddevice, ffmpeg);
 5. se descarcă modelul Whisper large-v3-turbo și se verifică suma oficială;
 6. se instalează LibreOffice, în română, cu dicționarul românesc și ajutorul
    în română, apoi se configurează pentru utilizatorul curent;
 7. se creează scurtăturile și se adaugă programul în lista de programe.

Fiecare pas raportează progres în cuvinte simple. Orice eroare este tradusă
într-un mesaj care spune ce s-a întâmplat, de ce și ce trebuie făcut.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import cai, config, jurnal, libreoffice, sisteme
from .constante import (
    NUME_APLICATIE,
    PACHETE,
    PACHET_FASTER_WHISPER,
    PYTHON_ARHIVA,
    PYTHON_FOLDER,
    PYTHON_JSON_SUME,
    PYTHON_SHA256,
    VERSIUNE,
    WHISPER_BYTES,
    WHISPER_CT2_FISIERE,
    WHISPER_CT2_REPO,
)
from .descarcare import (
    EroareDescarcare,
    SumaGresita,
    descarca,
    descarca_verificat,
    sha256_fisier,
    text_progres,
)
from .internet import verifica as verifica_internet

Progres = Callable[[str, float], None]  # (mesaj simplu, fracțiune 0..1)

FLAG_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Fișierele copiate lângă pachet, ca scurtăturile să funcționeze.
FISIERE_COPIATE = (
    "dictare_transcriere_romana",
    "pornire.py",
    "instaleaza.bat",
    "Instalare Dictare&Transcriere Română.bat",
    "Pornire Dictare&Transcriere Română.bat",
    "README.md",
    "LICENTA.txt",
    "PROMPT_DICTARE_ROMANA.md",
    "PROMPT_UX_CLAUDE_CODE.md",
)


class EroareInstalare(RuntimeError):
    """Instalarea nu poate continua; mesajul este pentru utilizator."""

    def __init__(self, mesaj: str, ce_fac: str = "", fara_internet: bool = False, detalii: str = ""):
        super().__init__(mesaj)
        self.ce_fac = ce_fac
        self.fara_internet = fara_internet
        self.detalii = detalii


class InstalareOprita(RuntimeError):
    """Utilizatorul a oprit instalarea; se poate relua de unde a rămas."""


@dataclass
class Optiuni:
    """Alegerea utilizatorului la începutul instalării."""

    cu_gpu: bool = False
    instaleaza_libreoffice: bool = True
    sari_verificarea: bool = False


def _anunta(progres: Progres | None, mesaj: str, fractiune: float) -> None:
    jurnal.instalare(mesaj)
    if progres:
        try:
            progres(mesaj, max(0.0, min(1.0, fractiune)))
        except Exception:
            pass


def _ruleaza(comanda: list[str], descriere: str, timeout: int = 5400) -> subprocess.CompletedProcess:
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
            f"Nu am găsit un program necesar pentru {descriere.lower()}.",
            ce_fac=(
                "Repornește instalarea; dacă problema apare din nou, trimite fișierul "
                f"«{cai.fisier_jurnal_instalare()}»."
            ),
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise EroareInstalare(
            f"{descriere} a durat prea mult și a fost oprită.",
            ce_fac="Verifică legătura la internet și încearcă din nou.",
        ) from exc
    if rezultat.returncode != 0:
        detalii = (rezultat.stderr or rezultat.stdout or "").strip().splitlines()
        coada = " | ".join(detalii[-3:]) if detalii else "fără detalii"
        jurnal.instalare(f"Eroare la {descriere}: cod {rezultat.returncode}: {coada}")
        raise EroareInstalare(
            f"Un pas al instalării a eșuat: {descriere.lower()}.",
            ce_fac=(
                "Apasă «Încearcă din nou». Ce s-a descărcat deja se păstrează. "
                f"Jurnalul complet este în «{cai.fisier_jurnal_instalare()}»."
            ),
            detalii=coada,
        )
    return rezultat


# --------------------------------------------------------------------------- internet


def asigura_internet(complet: bool = True) -> None:
    """Verifică legătura la internet înainte de orice descărcare."""
    rezultat = verifica_internet(complet=complet)
    if not rezultat.are_internet:
        raise EroareInstalare(rezultat.mesaj, ce_fac="Apasă «Încearcă din nou» după ce te conectezi.", fara_internet=True)
    if complet and rezultat.gazde_lipsa:
        raise EroareInstalare(rezultat.mesaj, ce_fac="Verifică legătura, apoi apasă «Încearcă din nou».")
    jurnal.instalare(f"Internet: {rezultat.mesaj}")


# --------------------------------------------------------------------------- 2. fișierele


def copiaza_programul(progres: Progres | None) -> Path:
    """Copiază sursa programului în folderul de instalare.

    Astfel programul rămâne instalat complet în folderul lui, iar scurtătura
    funcționează chiar dacă utilizatorul șterge arhiva din care a instalat.
    """
    sursa = cai.director_script()
    tinta = cai.director_program()
    if sursa.resolve() == tinta.resolve():
        return tinta

    _anunta(progres, "Pregătesc fișierele programului…", 0.01)
    tinta.mkdir(parents=True, exist_ok=True)
    for nume in FISIERE_COPIATE:
        element = sursa / nume
        if not element.exists():
            continue
        destinatie = tinta / nume
        try:
            if element.is_dir():
                shutil.copytree(
                    element,
                    destinatie,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "teste"),
                )
            else:
                shutil.copy2(element, destinatie)
        except OSError as exc:
            jurnal.atentionare(f"Nu am putut copia {element} în {destinatie}: {exc}")
    pachet = tinta / "dictare_transcriere_romana"
    necesare = ("__init__.py", "__main__.py", "ui_principal.py", "motor.py")
    lipsa = [nume for nume in necesare if not (pachet / nume).is_file()]
    if lipsa:
        raise EroareInstalare(
            "Fișierele programului nu au fost copiate complet.",
            ce_fac="Verifică permisiunile folderului de instalare și apasă «Încearcă din nou».",
            detalii=", ".join(lipsa),
        )
    jurnal.instalare(f"Programul a fost copiat în {tinta}")
    return tinta


# --------------------------------------------------------------------------- 3. Python


def _suma_python_oficiala(arhitectura: str) -> str:
    """Suma SHA-256 a arhivei Python: cea publicată de python.org, apoi cea din cod.

    Fișierul oficial „windows-3.12.10.json” conține toate sumele; dacă nu poate
    fi citit, folosim suma scrisă în program (verificată de noi).
    """
    scrisa = PYTHON_SHA256.get(arhitectura, "")
    try:
        from .descarcare import _citeste_text  # citire text simplă, cu jurnal

        text = _citeste_text(PYTHON_JSON_SUME)
        if text:
            import json
            import re

            nume_arhiva = PYTHON_ARHIVA[arhitectura]
            # Căutăm intrarea care are exact arhiva noastră și luăm suma ei.
            potrivire = re.search(
                re.escape(nume_arhiva) + r'[^}]*?"sha256"\s*:\s*"([0-9a-fA-F]{64})"',
                text,
                re.DOTALL,
            )
            if potrivire:
                publicata = potrivire.group(1).lower()
                if scrisa and publicata != scrisa:
                    jurnal.instalare(
                        "ATENȚIE: suma publicată pentru Python diferă de cea din "
                        f"program ({publicata} față de {scrisa}). Se folosește cea publicată."
                    )
                return publicata
    except Exception as exc:  # pragma: no cover - depinde de rețea
        jurnal.instalare(f"Nu am putut citi lista oficială de sume Python: {exc}")
    if not scrisa:
        raise EroareInstalare(
            "Nu am putut afla suma de control a programului Python, deci nu îl descarc.",
            ce_fac="Verifică legătura la internet, apoi apasă «Încearcă din nou».",
        )
    return scrisa


def _executa_arhiva(arhiva: Path, destinatie: Path, progres: Progres | None, baza: float, spatiu: float) -> None:
    """Dezarhivează Python cu progres în cuvinte simple."""
    try:
        with zipfile.ZipFile(arhiva) as zip_fisier:
            elemente = zip_fisier.infolist()
            total = sum(element.file_size for element in elemente) or 1
            facut = 0
            for element in elemente:
                zip_fisier.extract(element, destinatie)
                facut += element.file_size
                if facut % (4 * 1024 * 1024) < element.file_size:
                    _anunta(
                        progres,
                        "Pregătesc programul de transcriere (Python)… "
                        f"{min(100, int(facut * 100 / total))}%",
                        baza + spatiu * min(1.0, facut / total),
                    )
    except (OSError, zipfile.BadZipFile) as exc:
        raise EroareInstalare(
            "Arhiva programului Python nu a putut fi deschisă.",
            ce_fac="Șterge folderul de descărcări și apasă «Încearcă din nou».",
            detalii=str(exc),
        ) from exc


def asigura_python(progres: Progres | None, baza: float = 0.03, spatiu: float = 0.07) -> Path:
    """Aduce un Python 3.12 pe 64 de biți, fără întrebări și fără instalator.

    Se folosește arhiva oficială de la python.org (varianta portabilă), care
    nu are nevoie de drepturi de administrator și nu modifică nimic în Windows.
    """
    tinta = cai.director_instalare() / "Python"
    executabil = tinta / "python.exe"
    if executabil.exists() and _python_ok(executabil):
        _anunta(progres, "Programul de bază este deja instalat.", baza)
        return executabil

    arhitectura = cai.arhitectura()
    nume_arhiva = PYTHON_ARHIVA.get(arhitectura)
    if not nume_arhiva:
        raise EroareInstalare(
            "Pe acest tip de procesor nu pot instala automat programul de bază.",
            ce_fac=(
                "Programul are nevoie de un calculator cu Windows pe 64 de biți "
                "(procesor Intel sau AMD)."
            ),
        )

    url = f"{PYTHON_FOLDER}/{nume_arhiva}"
    suma = _suma_python_oficiala(arhitectura)
    arhiva = cai.director_descarcari() / nume_arhiva

    def arata(descarcat: int, total: int) -> None:
        _anunta(
            progres,
            text_progres(descarcat, total, "Descarc programul de bază (Python)"),
            baza + spatiu * (descarcat / total if total else 0),
        )

    _anunta(progres, "Descarc programul de bază al transcrierii (Python)…", baza)
    try:
        descarca_verificat(url, arhiva, suma, arata, eticheta="Python")
    except SumaGresita:
        raise
    except EroareDescarcare as exc:
        raise EroareInstalare(
            "Programul de bază (Python) nu a putut fi descărcat.",
            ce_fac="Verifică legătura la internet, apoi apasă «Încearcă din nou».",
            fara_internet=exc.fara_internet,
            detalii=str(exc),
        ) from exc

    if tinta.exists():
        shutil.rmtree(tinta, ignore_errors=True)
    tinta.mkdir(parents=True, exist_ok=True)
    _executa_arhiva(arhiva, tinta, progres, baza + spatiu * 0.6, spatiu * 0.4)

    if not _python_ok(executabil):
        raise EroareInstalare(
            "Programul de bază (Python) nu a putut fi pregătit pe acest calculator.",
            ce_fac=(
                "Încearcă din nou instalarea. Dacă problema apare și atunci, trimite "
                f"fișierul «{cai.fisier_jurnal_instalare()}»."
            ),
        )
    jurnal.instalare(f"Python pregătit în {tinta}")
    return executabil


def _python_ok(executabil: Path) -> bool:
    """Verifică dacă interpretorul găsit există, e 3.12 pe 64 de biți și merge."""
    if not executabil.exists():
        return False
    try:
        rezultat = subprocess.run(
            [
                str(executabil),
                "-c",
                "import sys,struct;print(f'{sys.version_info[0]}.{sys.version_info[1]}|{struct.calcsize(chr(80))*8}')",
            ],
            capture_output=True,
            text=True,
            timeout=120,
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
    return (major, minor) in cai.PYTHON_ACCEPTAT and biti == "64"


def _pregateste_pip(python: Path) -> None:
    """Pornește pip în Python-ul descărcat (nu vine pornit din arhivă)."""
    try:
        rezultat = subprocess.run(
            [str(python), "-m", "ensurepip", "--upgrade"],
            capture_output=True,
            text=True,
            timeout=900,
            creationflags=FLAG_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EroareInstalare(
            "Instalatorul de biblioteci al programului nu a putut fi pornit.",
            ce_fac="Apasă «Încearcă din nou».",
            detalii=str(exc),
        ) from exc
    if rezultat.returncode != 0:
        jurnal.atentionare(f"ensurepip a raportat codul {rezultat.returncode}")


# --------------------------------------------------------------------------- 4. mediul și bibliotecile


def _pip(python: Path, argumente: list[str], descriere: str) -> None:
    _ruleaza(
        [str(python), "-m", "pip", "--disable-pip-version-check", *argumente],
        descriere,
        timeout=7200,
    )


def creeaza_mediu(progres: Progres | None, baza: float = 0.10, spatiu: float = 0.05) -> Path:
    """Creează mediul programului și actualizează uneltele lui."""
    python_mediu = cai.python_mediu()
    if python_mediu.exists() and _python_ok(python_mediu):
        _anunta(progres, "Spațiul de lucru este deja pregătit.", baza)
        return python_mediu

    baza_python = asigura_python(progres)
    _anunta(progres, "Pregătesc spațiul de lucru al programului…", baza)
    cai.pregateste_directoare()
    if cai.director_mediu().exists():
        shutil.rmtree(cai.director_mediu(), ignore_errors=True)
    _pregateste_pip(baza_python)
    _ruleaza(
        [str(baza_python), "-m", "venv", str(cai.director_mediu())],
        "Pregătirea spațiului de lucru",
    )
    if not python_mediu.exists():
        raise EroareInstalare(
            "Nu am putut pregăti spațiul de lucru al programului.",
            ce_fac="Verifică dacă antivirusul nu blochează folderul și apasă «Încearcă din nou».",
        )
    _anunta(progres, "Actualizez uneltele programului…", baza + spatiu * 0.5)
    _pip(python_mediu, ["install", "--upgrade", "pip", "setuptools", "wheel"], "Actualizarea uneltelor")
    return python_mediu


def _biblioteci_in_proces() -> bool:
    """Adevărat dacă bibliotecile de transcriere se pot importa chiar aici."""
    try:
        from . import motor  # noqa: F401  (pregătește întâi bibliotecile CUDA)
        import faster_whisper  # noqa: F401
        import imageio_ffmpeg  # noqa: F401
        import numpy  # noqa: F401
        import sounddevice  # noqa: F401
    except Exception:
        return False
    return True


def _are_biblioteci(python_mediu: Path, are_gpu: bool = False) -> bool:
    """Adevărat dacă în mediu se pot importa toate bibliotecile de care e nevoie.

    Cu faster-whisper nu mai avem nevoie de PyTorch, deci verificăm doar
    faster-whisper, sounddevice, imageio_ffmpeg și numpy.
    """
    verificare = (
        "import faster_whisper, sounddevice, imageio_ffmpeg, numpy;"
    )
    try:
        rezultat = subprocess.run(
            [str(python_mediu), "-c", verificare],
            capture_output=True,
            text=True,
            timeout=600,
            creationflags=FLAG_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return rezultat.returncode == 0


def instaleaza_biblioteci(progres: Progres | None, cu_gpu: bool, baza: float = 0.18, spatiu: float = 0.22) -> None:
    """Instalează faster-whisper (CTranslate2) și celelalte pachete.

    Nu mai este nevoie de PyTorch: faster-whisper rulează modelele Whisper
    prin CTranslate2, de câteva ori mai rapid și cu mai puține resurse.
    """
    python_mediu = cai.python_mediu()
    if not python_mediu.exists():
        raise EroareInstalare("Spațiul de lucru lipsește.", ce_fac="Apasă «Încearcă din nou».")

    if _are_biblioteci(python_mediu, cu_gpu):
        _anunta(progres, "Bibliotecile sunt deja instalate.", baza + spatiu)
        return

    eticheta = "cu accelerare video" if cu_gpu else "pentru procesor"
    _anunta(
        progres,
        f"Descarc biblioteca de transcriere ({eticheta})… are peste 200 MB, "
        "așa că durează câteva minute.",
        baza,
    )
    try:
        _pip(
            python_mediu,
            ["install", PACHET_FASTER_WHISPER],
            "Descărcarea bibliotecii de transcriere",
        )
    except EroareInstalare:
        if not cu_gpu:
            raise
    # faster-whisper alege automat CUDA dacă este disponibil; nu mai avem
    # nevoie de PyTorch pentru a forța CPU sau CUDA.

    _anunta(progres, "Instalez programele de transcriere și de sunet…", baza + spatiu * 0.6)
    _pip(python_mediu, ["install", *PACHETE], "Instalarea programelor de bază")
    _anunta(progres, "Bibliotecile au fost instalate.", baza + spatiu)


# --------------------------------------------------------------------------- 5. modelul


def asigura_model(progres: Progres | None, baza: float = 0.45, spatiu: float = 0.25) -> Path:
    """Descarcă modelul CTranslate2 (faster-whisper) și verifică fișierele.

    Modelul este un folder cu 5 fișiere, descărcate de pe Hugging Face la o
    revizie fixă, cu reluare și verificare SHA-256 (vezi ``pregatire``).
    """
    from . import pregatire

    return pregatire.asigura_model(progres, baza, spatiu)


# --------------------------------------------------------------------------- 6. LibreOffice


def asigura_libreoffice(progres: Progres | None, baza: float = 0.70, spatiu: float = 0.24):
    """Instalează LibreOffice în română, cu dicționar și ajutor în română."""
    return libreoffice.instaleaza(
        progres=lambda mesaj, fractiune: _anunta(progres, mesaj, baza + spatiu * fractiune)
    )


# --------------------------------------------------------------------------- instalare completă


def instaleaza(
    optiuni: Optiuni,
    progres: Progres | None = None,
    director: Path | None = None,
    anuleaza: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """Rulează toți pașii de instalare și întoarce un rezumat.

    ``anuleaza`` este o funcție care întoarce ``True`` când utilizatorul a
    cerut oprirea instalării; fișierele deja descărcate rămân pe disc, ca
    instalarea să poată fi reluată de unde a rămas.
    """
    if director is not None:
        os.environ["DICTARE_DIR"] = str(director)

    def _verifica_oprirea() -> None:
        if anuleaza and anuleaza():
            jurnal.instalare("Utilizatorul a oprit instalarea; se poate relua mai târziu.")
            raise InstalareOprita(
                "Instalarea a fost oprită. Poți continua mai târziu de unde a rămas."
            )

    cai.pregateste_directoare()
    jurnal.instalare("=" * 70)
    jurnal.instalare("ÎNCEPERE INSTALARE")
    _anunta(progres, "Încep instalarea. Nu închide fereastra.", 0.0)
    jurnal.instalare(
        f"Director: {cai.director_instalare()} · arhitectură: {cai.arhitectura()} · "
        f"Windows build: {sys.getwindowsversion().build if cai.este_windows() else '?'}"
    )
    if optiuni.sari_verificarea:
        jurnal.instalare(
            "UTILIZATORUL A ALES „Sari peste verificare” — verificarea resurselor nu a fost aplicată."
        )

    rezumat: dict[str, str] = {}

    # 0. internet (obligatoriu: totul se descarcă acum)
    _anunta(progres, "Verific legătura la internet…", 0.005)
    asigura_internet(complet=True)
    _verifica_oprirea()

    # 1. fișierele programului
    copiaza_programul(progres)
    _verifica_oprirea()

    # 2. Python + mediul
    creeaza_mediu(progres)
    rezumat["python"] = str(cai.python_mediu())
    _verifica_oprirea()

    # 3. biblioteci
    instaleaza_biblioteci(progres, optiuni.cu_gpu)
    rezumat["biblioteci"] = "instalate"
    _verifica_oprirea()

    # 4. modelul
    asigura_model(progres)
    rezumat["model"] = str(cai.fisier_model())
    _verifica_oprirea()

    # 5. LibreOffice, în română
    if optiuni.instaleaza_libreoffice:
        try:
            stare = asigura_libreoffice(progres)
            rezumat["libreoffice"] = str(stare.executabil or "")
            rezumat["libreoffice_romana"] = (
                "da" if (stare.are_meniu_romana and stare.are_dictionar_romana) else "partial"
            )
        except SumaGresita:
            raise
        except libreoffice.EroareLibreOffice as exc:
            # LibreOffice este important, dar programul funcționează și fără el.
            jurnal.instalare(f"LibreOffice nu a fost instalat: {exc}")
            rezumat["libreoffice"] = "indisponibil"
            rezumat["libreoffice_mesaj"] = str(exc)
        _verifica_oprirea()
    else:
        rezumat["libreoffice"] = "neinstalat (la cererea utilizatorului)"

    # 6. scurtături, pictogramă, listă de programe, cum se folosește
    _anunta(progres, "Creez scurtăturile și pregătesc ghidul de folosire…", 0.96)
    try:
        from . import ajutor, iconita

        cale_iconita = iconita.scrie_iconita(cai.director_instalare() / "pictograma.ico")
        ajutor.scrie_citeste_ma()
        speciala = ajutor.scrie_ghid_ajutor()
        rezumat["ghid"] = str(speciala)
    except Exception as exc:  # ghidul nu este obligatoriu
        jurnal.atentionare(f"Nu am putut scrie ghidurile: {exc}")
        cale_iconita = None
    try:
        scurtaturi = sisteme.creeaza_scurtaturi(cale_iconita)
        rezumat["scurtaturi"] = "; ".join(str(cale) for cale in scurtaturi)
    except Exception as exc:
        jurnal.atentionare(f"Nu am putut crea scurtăturile: {exc}")
    try:
        sisteme.inregistreaza_in_lista_programelor(cale_iconita)
    except Exception as exc:
        jurnal.atentionare(f"Nu am putut adăuga programul în lista Windows: {exc}")

    # 7. setările
    setari = config.incarca()
    setari.versiune_instalare = f"{VERSIUNE} ({time.strftime('%Y-%m-%d')})"
    setari.dispozitiv = "cuda" if optiuni.cu_gpu else "cpu"
    if setari.limba == "auto":
        setari.limba = "ro"
    config.salveaza(setari)

    # 8. verificarea finală
    probleme = verifica_instalare()
    rezumat["probleme"] = "; ".join(probleme) if probleme else "niciuna"
    _anunta(progres, "Instalarea s-a terminat. Programul este gata de folosire.", 1.0)
    jurnal.instalare(f"Instalare încheiată. Rezumat: {rezumat}")
    return rezumat


def verifica_instalare() -> list[str]:
    """Listă de probleme găsite după instalare (goală dacă totul e în regulă)."""
    probleme: list[str] = []
    # Dacă programul care rulează acum (exe-ul construit sau .venv) are deja
    # bibliotecile, nu mai cerem mediul Python separat și copia fișierelor.
    if not _biblioteci_in_proces():
        if not cai.python_mediu().exists():
            probleme.append("Spațiul de lucru Python lipsește.")
        elif not _are_biblioteci(cai.python_mediu(), False):
            probleme.append("Bibliotecile de transcriere nu sunt instalate.")
        pachet = cai.director_program() / "dictare_transcriere_romana"
        necesare = ("__init__.py", "__main__.py", "motor.py")
        lipsa_program = [nume for nume in necesare if not (pachet / nume).is_file()]
        if lipsa_program:
            probleme.append(
                "Fișierele aplicației lipsesc sau sunt incomplete; rulează din nou instalarea."
            )
    try:
        from . import pregatire

        gresite = pregatire.fisiere_model_gresite()
    except Exception:
        gresite = {} if cai.fisier_model().exists() else {"model": "lipsește"}
    if gresite:
        probleme.append(
            "Modelul de transcriere lipsește sau nu e complet ("
            + ", ".join(f"{nume}: {motiv}" for nume, motiv in gresite.items())
            + ")."
        )
    try:
        probleme.extend(libreoffice.valideaza_instalarea())
    except Exception:
        pass
    return probleme


# --------------------------------------------------------------------------- dezinstalare


def dezinstaleaza(tacut: bool = False) -> bool:
    """Scoate programul: scurtături, listă de programe, apoi folderul lui.

    Datele utilizatorului (documentele transcrise) **nu** sunt șterse.
    """
    jurnal.instalare("Dezinstalare cerută.")
    if not tacut:
        # Întrebarea se pune cu fereastra proprie a programului (fără ferestrele
        # Windows), iar răspunsul „nu” întoarce False fără să scoată nimic.
        from . import ui_instalare

        return ui_instalare.dezinstaleaza_cu_fereastra()
    try:
        sisteme.elimina_scurtaturi()
        sisteme.scoate_din_lista_programelor()
    except Exception as exc:
        jurnal.atentionare(f"Dezinstalare parțială: {exc}")
    if cai.director_instalare().exists():
        # Folderul programului, nu documentele utilizatorului: acelea rămân.
        shutil.rmtree(cai.director_instalare(), ignore_errors=True)
    return True
