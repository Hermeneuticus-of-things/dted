"""Descărcare de fișiere cu progres, reluare și verificare SHA-256.

Se folosește doar biblioteca standard, ca programul să poată descărca ce-i
trebuie înainte de a-și instala orice dependență.

Descărcările pot fi reluate: dacă legătura la internet se întrerupe, fișierul
parțial rămâne pe disc („.partial”) și următoarea încercare continuă de unde a
rămas, apoi verifică suma de control a fișierului complet.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from . import jurnal

Progres = Callable[[int, int], None]  # (bytes descărcați, bytes totali)

#: Numele sub care programul se prezintă serverelor oficiale.
AGENT = "DictareTranscriereRomana/1.0 (+instalare locala, fara colectare de date)"


class EroareDescarcare(RuntimeError):
    """Descărcarea a eșuat dintr-un motiv care poate fi explicat utilizatorului."""

    def __init__(self, mesaj: str, fara_internet: bool = False):
        super().__init__(mesaj)
        self.fara_internet = fara_internet


class SumaGresita(RuntimeError):
    """Fișierul descărcat nu corespunde sumei SHA-256 oficiale."""

    def __init__(self, nume: str, asteptat: str, gasit: str):
        self.nume = nume
        self.asteptat = asteptat
        self.gasit = gasit
        super().__init__(
            f"Fișierul „{nume}” nu este cel oficial.\n"
            f"Suma așteptată: {asteptat}\n"
            f"Suma găsită:   {gasit}\n\n"
            "Instalarea a fost oprită, ca să nu se instaleze altceva.\n"
            "Fișierul poate fi corupt la descărcare sau poate proveni din altă "
            "parte. Șterge fișierul din folderul „descarcari” și încearcă din nou."
        )


def _raporteaza(progres: Progres | None, descarcat: int, total: int) -> None:
    """Cheamă progresul fără a lăsa o eroare de afișare să oprească descărcarea."""
    if not progres:
        return
    try:
        progres(descarcat, total)
    except Exception:
        pass


# --------------------------------------------------------------------------- sume


def sha256_fisier(cale: Path, progres: Progres | None = None) -> str:
    """Calculează suma SHA-256 a unui fișier existent."""
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
            _raporteaza(progres, citit, total)
    return hasher.hexdigest()


def suma_din_mirrorlist(url_fisier: str) -> str:
    """Citește suma SHA-256 publicată oficial în pagina „.mirrorlist”.

    The Document Foundation publică, pentru fiecare fișier, o pagină
    ``<link>.mirrorlist`` care conține dimensiunea și suma SHA-256 oficială.
    """
    return _suma_din_text(_citeste_text(url_fisier + ".mirrorlist"), r"SHA-256 Hash:\s*([0-9a-fA-F]{64})")


def suma_din_meta4(url_fisier: str) -> str:
    """Citește suma SHA-256 din fișierul oficial „.meta4” (Metalink)."""
    return _suma_din_text(_citeste_text(url_fisier + ".meta4"), r'sha-256"[^>]*>([0-9a-fA-F]{64})')


def _suma_din_text(text: str, model: str) -> str:
    potrivire = re.search(model, text or "", re.IGNORECASE)
    if not potrivire:
        return ""
    return potrivire.group(1).lower()


def _citeste_text(url: str, timeout: int = 30) -> str:
    cerere = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(cerere, timeout=timeout) as raspuns:
            return raspuns.read().decode("utf-8", errors="replace")
    except Exception as exc:  # rețea, DNS, timeout
        jurnal.instalare(f"Nu am putut citi lista oficială de sume {url}: {exc}")
        return ""


def suma_oficiala(url_fisier: str, suma_scrisa: str = "") -> str:
    """Suma SHA-256 oficială: cea publicată pe site, cu rezervă în cod.

    Se citește întotdeauna pagina oficială. Dacă aceasta nu poate fi citită,
    se folosește suma scrisă în program, iar dacă nici aceea nu există,
    instalarea se oprește.
    """
    publicata = suma_din_mirrorlist(url_fisier) or suma_din_meta4(url_fisier)
    if publicata and suma_scrisa and publicata != suma_scrisa.lower():
        jurnal.instalare(
            f"ATENȚIE: suma publicată pentru {url_fisier} diferă de cea din program "
            f"({publicata} față de {suma_scrisa}). Se folosește suma publicată."
        )
    if publicata:
        return publicata
    if suma_scrisa:
        jurnal.instalare(
            f"Nu am putut citi suma publicată pentru {url_fisier}; folosesc suma scrisă în program."
        )
        return suma_scrisa.lower()
    return ""


# --------------------------------------------------------------------------- descărcare


def _nume_fisier(url: str) -> str:
    return url.split("?")[0].rstrip("/").split("/")[-1]


def dimensiune_la_distanta(url: str, timeout: int = 30) -> int:
    """Dimensiunea fișierului de pe server, dacă serverul o spune."""
    cerere = urllib.request.Request(url, method="HEAD", headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(cerere, timeout=timeout) as raspuns:
            return int(raspuns.headers.get("Content-Length") or 0)
    except Exception:
        return 0


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
            jurnal.instalare(f"Descărcare întreruptă ({incercare}/{reincercari}): {exc}")
            if incercare == reincercari:
                raise
            time.sleep(1.5 * incercare)
    else:  # pragma: no cover - bucla acoperă toate cazurile
        raise ultima_eroare or EroareDescarcare("Descărcarea nu a putut fi terminată.")

    if suma_asteptata:
        suma_gasita = sha256_fisier(partial, progres)
        if suma_gasita.lower() != suma_asteptata.lower():
            partial.unlink(missing_ok=True)
            raise SumaGresita(_nume_fisier(url), suma_asteptata, suma_gasita)

    partial.replace(destinatie)
    return destinatie


def _descarca_o_data(url: str, partial: Path, progres: Progres | None) -> None:
    """Un singur pas de descărcare, cu reluare de unde s-a rămas."""
    inceput = partial.stat().st_size if partial.exists() else 0
    antete = {"User-Agent": AGENT, "Accept": "*/*"}
    if inceput:
        antete["Range"] = f"bytes={inceput}-"
        jurnal.instalare(f"Reiau descărcarea {url} de la {inceput / 1024**2:.1f} MB.")

    cerere = urllib.request.Request(url, headers=antete)
    try:
        with urllib.request.urlopen(cerere, timeout=60) as raspuns:
            reluare = int(getattr(raspuns, "status", 200)) == 206
            lungime = int(raspuns.headers.get("Content-Length") or 0)
            total = (inceput + lungime) if reluare else lungime
            descarcat = inceput if reluare else 0
            mod = "ab" if reluare else "wb"
            with open(partial, mod) as fisier:
                while True:
                    bloc = raspuns.read(256 * 1024)
                    if not bloc:
                        break
                    fisier.write(bloc)
                    descarcat += len(bloc)
                    _raporteaza(progres, descarcat, total)
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            raise EroareDescarcare(
                f"Serverul nu are fișierul cerut (cod {exc.code}). "
                "Verifică dacă ai cea mai nouă versiune a programului."
            ) from exc
        raise EroareDescarcare(
            f"Serverul a refuzat descărcarea (cod {exc.code}). "
            "Verifică legătura la internet și încearcă din nou."
        ) from exc
    except urllib.error.URLError as exc:
        raise EroareDescarcare(
            "S-a întrerupt internetul. Reconectează calculatorul la Wi-Fi sau la "
            "cablu, apoi apasă «Încearcă din nou». Ce s-a descărcat deja se păstrează.",
            fara_internet=True,
        ) from exc
    except TimeoutError as exc:
        raise EroareDescarcare(
            "Descărcarea s-a oprit din cauza unei pauze de internet. "
            "Încearcă din nou; fișierele descărcate parțial se păstrează.",
            fara_internet=True,
        ) from exc
    except OSError as exc:
        raise EroareDescarcare(
            f"Nu am putut scrie fișierul pe disc ({exc}). "
            "Verifică spațiul liber pe disc și încearcă din nou."
        ) from exc


def descarca_verificat(
    url: str,
    destinatie: Path,
    suma_asteptata: str,
    progres: Progres | None = None,
    eticheta: str = "Descarc",
) -> Path:
    """Descarcă un fișier dacă lipsește sau dacă nu corespunde sumei oficiale."""
    if destinatie.exists() and suma_asteptata:
        _raporteaza(progres, 0, destinatie.stat().st_size)
        if sha256_fisier(destinatie).lower() == suma_asteptata.lower():
            jurnal.instalare(f"Fișierul {destinatie.name} există deja și este verificat.")
            return destinatie
        jurnal.instalare(f"Fișierul {destinatie.name} are altă sumă; îl descarc din nou.")
        destinatie.unlink(missing_ok=True)

    if not suma_asteptata:
        raise EroareDescarcare(
            "Nu am putut afla suma oficială a fișierului, deci nu îl pot verifica. "
            "Verifică legătura la internet și încearcă din nou."
        )

    total_estimat = destinatie.stat().st_size if destinatie.exists() else 0

    def cu_eticheta(descarcat: int, total: int) -> None:
        _raporteaza(progres, descarcat, total or total_estimat)

    jurnal.instalare(f"Descarc {eticheta}: {url}")
    return descarca(url, destinatie, cu_eticheta, suma_asteptata)


def text_progres(descarcat: int, total: int, eticheta: str) -> str:
    """Mesaj în cuvinte simple, fără cifre tehnice."""
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
