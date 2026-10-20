"""Descărcare de fișiere cu progres și verificare SHA-256.

Se folosește doar biblioteca standard, ca să nu depindă de pachete externe
înainte de instalare.
"""

from __future__ import annotations

import hashlib
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import jurnal

Progres = Callable[[int, int], None]  # (bytes descărcați, bytes totali)


class EroareDescarcare(RuntimeError):
    """Descărcarea a eșuat dintr-un motiv explicabil utilizatorului."""


class SumaGresita(RuntimeError):
    """Fișierul descărcat nu corespunde sumei SHA-256 oficiale."""

    def __init__(self, nume: str, asteptat: str, gasit: str):
        self.nume = nume
        self.asteptat = asteptat
        self.gasit = gasit
        super().__init__(
            f"Fișierul „{nume}” nu este cel oficial.\n"
            f"S-a așteptat suma {asteptat},\n dar s-a primit {gasit}.\n"
            "Instalarea a fost oprită. Fișierul poate fi corupt sau poate proveni din altă sursă."
        )


def sha256_fisier(cale: Path, progres: Progres | None = None) -> str:
    """Calculează suma SHA-256 a unui fișier."""
    hasher = hashlib.sha256()
    total = cale.stat().st_size
    citit = 0
    with open(cale, "rb") as fisier:
        while True:
            bloc = fisier.read(1024 * 1024)
            if not bloc:
                break
            hasher.update(bloc)
            citit += len(bloc)
            if progres:
                progres(citit, total)
    return hasher.hexdigest()


def _nume_fisier(url: str) -> str:
    return url.split("?")[0].rstrip("/").split("/")[-1]


def descarca(
    url: str,
    destinatie: Path,
    progres: Progres | None = None,
    suma_asteptata: str | None = None,
    reincercari: int = 3,
) -> Path:
    """Descarcă un fișier, apoi verifică suma SHA-256 dacă este dată."""
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    partial = destinatie.with_suffix(destinatie.suffix + ".partial")
    ultima_eroare: Exception | None = None

    for incercare in range(1, reincercari + 1):
        try:
            _descarca_o_data(url, partial, progres)
            break
        except EroareDescarcare as exc:
            ultima_eroare = exc
            jurnal.instalare(f"Descărcare eșuată ({incercare}/{reincercari}) pentru {url}: {exc}")
            if incercare == reincercari:
                raise
            time.sleep(1.5 * incercare)
    else:  # pragma: no cover - bucla acoperă cazul
        raise ultima_eroare or EroareDescarcare("Descărcarea nu a putut fi finalizată.")

    if suma_asteptata:
        suma_gasita = sha256_fisier(partial, progres)
        if suma_gasita.lower() != suma_asteptata.lower():
            partial.unlink(missing_ok=True)
            raise SumaGresita(_nume_fisier(url), suma_asteptata, suma_gasita)

    partial.replace(destinatie)
    return destinatie


def _descarca_o_data(url: str, partial: Path, progres: Progres | None) -> None:
    cerere = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TranscriereLocala/1.0 (+offline transcription installer)",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(cerere, timeout=60) as raspuns:
            total = int(raspuns.headers.get("Content-Length") or 0)
            descarcat = 0
            with open(partial, "wb") as fisier:
                while True:
                    bloc = raspuns.read(256 * 1024)
                    if not bloc:
                        break
                    fisier.write(bloc)
                    descarcat += len(bloc)
                    if progres:
                        progres(descarcat, total)
    except urllib.error.HTTPError as exc:
        raise EroareDescarcare(
            f"Serverul a refuzat descărcarea (cod {exc.code}). "
            "Verifică legătura la internet și încearcă din nou."
        ) from exc
    except urllib.error.URLError as exc:
        raise EroareDescarcare(
            "Nu am putut lua legătura cu internetul. "
            "Verifică legătura la internet, apoi apasă «Verifică din nou»."
        ) from exc
    except TimeoutError as exc:
        raise EroareDescarcare(
            "Descărcarea s-a oprit din cauza unei pauze de internet. "
            "Încearcă din nou; fișierele deja descărcate rămân salvate."
        ) from exc
    except OSError as exc:
        raise EroareDescarcare(
            f"Nu am putut scrie fișierul pe disc ({exc}). "
            "Verifică spațiul liber și permisiunile folderului."
        ) from exc


def text_progres(descarcat: int, total: int, eticheta: str) -> str:
    """Mesaj prietenos, fără cifre tehnice."""
    mb = descarcat / 1024**2
    if total:
        procent = min(100, int(descarcat * 100 / total))
        return f"{eticheta}: {procent}% ({mb:.0f} MB din {total / 1024**2:.0f} MB)"
    return f"{eticheta}: {mb:.0f} MB descărcați"


def copiaza_sau_muta(sursa: Path, destinatie: Path) -> None:
    """Mută un fișier, cu rezervă la copiere între discuri diferite."""
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    try:
        sursa.replace(destinatie)
    except OSError:
        shutil.copy2(sursa, destinatie)
        sursa.unlink(missing_ok=True)


@dataclass
class PachetDescarcare:
    """O componentă care trebuie descărcată la instalare."""

    nume: str
    url: str
    nume_fisier: str
    suma_sha256: str | None
    aproximativ_mb: float
