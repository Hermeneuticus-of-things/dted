"""Actualizări din program, pe componente (cerința 8 / N-2).

Actualizarea este **opțională** și pornește doar la apăsarea butonului „Caută
actualizări” din Setări → „Instalare și actualizări”. Programul nu caută și nu
face nimic în fundal singur (0.8.2). Kitul offline rămâne instalarea implicită
(0.8.4).

Cum funcționează (PyInstaller nu poate schimba pachete cu pip, deci lucrăm pe
**dosare de componente**, nu cu pip):

1. Local, în ``versiuni.json``, stă versiunea fiecărei componente instalate.
2. La „Caută”, se citește un **manifest** (aceeași formă), cu versiunea nouă,
   adresa de descărcare și suma SHA-256 a fiecărei componente.
3. ``ce_s_a_schimbat`` compară și întoarce DOAR componentele schimbate, cu
   versiunea veche, cea nouă și dimensiunea (0.8.3).
4. Utilizatorul confirmă; ``descarca`` ia doar componenta schimbată și verifică
   SHA-256 („nu s-a stricat pe drum”).
5. ``aplica`` face **backup** la componenta veche, apoi înlocuiește doar acea
   componentă. Dacă programul nu pornește după actualizare sau proba pică,
   ``revine`` restaurează automat varianta veche (0.8.6).

Siguranța e pe primul plan: nimic nu se șterge (componenta veche merge în
``_backup``), iar revenirea e doar o copiere înapoi.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import cai

#: Numele fișierului cu versiunile instalate.
FISIER_VERSIUNI = "versiuni.json"
#: Folderul sub care stau copiile de siguranță ale componentelor vechi.
FOLDER_BACKUP = "_backup"

#: Componentele actualizabile (nume → dosar din folderul de instalare).
COMPONENTE = {
    "program": "program",   # motorul de dictare/transcriere
    "model": "model",       # modelul de transcriere
    "mediu": "mediu",       # bibliotecile mari (Python + pachete)
}


@dataclass
class Schimbare:
    """O componentă care are o versiune nouă."""

    nume: str
    veche: str
    noua: str
    dimensiune: int = 0

    @property
    def eticheta(self) -> str:
        return f"{self.nume}: {self.veche} → {self.noua}"


# --------------------------------------------------------------------------- manifest


def fisier_versiuni() -> Path:
    return cai.director_instalare() / FISIER_VERSIUNI


def versiuni_instalate() -> dict[str, dict]:
    """Versiunile instalate, citite din ``versiuni.json`` (gol dacă lipsește)."""
    try:
        date = json.loads(fisier_versiuni().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {nume: dict(val) for nume, val in (date or {}).items() if isinstance(val, dict)}


def scrie_versiuni(versiuni: dict[str, dict]) -> None:
    fisier = fisier_versiuni()
    fisier.parent.mkdir(parents=True, exist_ok=True)
    fisier.write_text(json.dumps(versiuni, ensure_ascii=False, indent=2), encoding="utf-8")


def tuplu_versiune(versiune: str) -> tuple[int, ...]:
    """Transformă „0.6.1-beta” în ``(0, 6, 1)`` pentru comparare corectă."""
    import re

    numere = [int(x) for x in re.findall(r"\d+", str(versiune or ""))]
    return tuple(numere)


def sincronizeaza_versiuni_curente() -> dict[str, dict]:
    """Se asigură că ``versiuni.json`` reflectă cel puțin versiunea rulată acum."""
    from . import constante

    instalate = versiuni_instalate()
    modificat = False
    v_prog = str(instalate.get("program", {}).get("versiune", "")).strip()
    if not v_prog or tuplu_versiune(constante.VERSIUNE) > tuplu_versiune(v_prog):
        instalate["program"] = {"versiune": constante.VERSIUNE}
        modificat = True
    try:
        folder_model = cai.fisier_model().parent
        if folder_model.exists() and "model" not in instalate:
            instalate["model"] = {"versiune": folder_model.name}
            modificat = True
    except Exception:
        pass
    if modificat:
        try:
            scrie_versiuni(instalate)
        except OSError:
            pass
    return instalate


def ce_s_a_schimbat(manifest: dict[str, dict]) -> list[Schimbare]:
    """Compară versiunile instalate cu manifestul; întoarce DOAR schimbările mai noi."""
    instalate = versiuni_instalate()
    schimbari: list[Schimbare] = []
    for nume, meta in (manifest or {}).items():
        if not isinstance(meta, dict):
            continue
        noua = str(meta.get("versiune", "")).strip()
        if not noua:
            continue
        veche = str(instalate.get(nume, {}).get("versiune", "")).strip()
        if noua == veche:
            continue
        # Pentru versiuni numerice (ex. 0.6.1 vs 0.6.0), propunem doar dacă e mai nouă.
        t_noua = tuplu_versiune(noua)
        t_veche = tuplu_versiune(veche)
        if veche and t_noua and t_veche and not (noua.isalpha() or veche.isalpha()):
            if t_noua <= t_veche and nume == "program":
                continue
        schimbari.append(
            Schimbare(
                nume=nume,
                veche=veche or "—",
                noua=noua,
                dimensiune=int(meta.get("dimensiune", 0)),
            )
        )
    return schimbari


# --------------------------------------------------------------------------- sume + descărcare


def sha256_al_fisierului(cale: Path) -> str:
    """Suma SHA-256 a unui fișier (verificare după descărcare)."""
    suma = hashlib.sha256()
    with cale.open("rb") as fisier:
        for bucata in iter(lambda: fisier.read(1024 * 1024), b""):
            suma.update(bucata)
    return suma.hexdigest()


def _componenta_folder(nume: str) -> Path:
    return cai.director_instalare() / COMPONENTE.get(nume, nume)


def descarca(
    url: str,
    destinatie: Path,
    sha256: str = "",
    progres: Callable[[int, int], None] | None = None,
) -> bool:
    """Descarcă ``url`` în ``destinatie`` și verifică SHA-256 (dacă e dat).

    ``progres`` primește (octeți_primiți, total) pe măsură ce fișierul coboară.
    Întoarce ``False`` la greșeală de rețea sau sumă nepotrivită (afișată de apelant).
    """
    destinatie = Path(destinatie)
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    try:
        cerere = urllib.request.Request(url, headers={"User-Agent": "D&TED-Updater/1.0"})
        with urllib.request.urlopen(cerere, timeout=120) as raspuns:
            total = int(raspuns.headers.get("Content-Length", 0))
            primiti = 0
            temporar = destinatie.with_name(destinatie.name + ".part")
            with temporar.open("wb") as fisier:
                while True:
                    bucata = raspuns.read(1024 * 1024)
                    if not bucata:
                        break
                    fisier.write(bucata)
                    primiti += len(bucata)
                    if progres:
                        progres(primiti, total)
            os.replace(temporar, destinatie)
    except Exception:
        return False
    if sha256 and sha256_al_fisierului(destinatie) != sha256.lower():
        destinatie.unlink(missing_ok=True)
        return False
    return True


# --------------------------------------------------------------------------- backup / aplicare / revenire


def backup_componenta(nume: str, versiune: str) -> Path | None:
    """Copiază componenta veche în ``_backup/<nume>-<versiune>`` (idempotent)."""
    sursa = _componenta_folder(nume)
    destinatie = cai.director_instalare() / FOLDER_BACKUP / f"{nume}-{versiune}"
    if sursa.exists():
        if destinatie.exists():
            shutil.rmtree(destinatie, ignore_errors=True)
        shutil.copytree(sursa, destinatie)
        return destinatie
    # Dacă e prima actualizare a componentei „program” și dosarul „program” nu exista încă,
    # salvăm pachetul curent dictare_transcriere_romana ca backup pentru revenire.
    if nume == "program":
        pachet_curent = Path(__file__).resolve().parent
        if pachet_curent.is_dir():
            if destinatie.exists():
                shutil.rmtree(destinatie, ignore_errors=True)
            shutil.copytree(
                pachet_curent,
                destinatie / "dictare_transcriere_romana",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.bak*"),
            )
            return destinatie
    return None


def restaureaza(nume: str, versiune: str) -> bool:
    """Aduce înapoi componenta din backup (folosit de „revino la versiunea precedentă”)."""
    backup = cai.director_instalare() / FOLDER_BACKUP / f"{nume}-{versiune}"
    if not backup.exists():
        return False
    tinta = _componenta_folder(nume)
    if tinta.exists():
        shutil.rmtree(tinta, ignore_errors=True)
    shutil.copytree(backup, tinta)
    return True


def aplica(nume: str, versiune_noua: str, pachet_descarcat: Path) -> bool:
    """Backup la vechea versiune, apoi înlocuiește componenta cu cea descărcată.

    Acceptă atât un dosar deja despachetat, cât și o arhivă ``.zip`` descărcată
    de pe GitHub Releases.
    """
    import zipfile

    pachet_descarcat = Path(pachet_descarcat)
    instalate = versiuni_instalate()
    veche = instalate.get(nume, {}).get("versiune", "")
    backup_componenta(nume, veche) if veche else None
    tinta = _componenta_folder(nume)
    if tinta.exists():
        shutil.rmtree(tinta, ignore_errors=True)
    if pachet_descarcat.is_dir():
        shutil.copytree(pachet_descarcat, tinta)
    elif pachet_descarcat.is_file() and zipfile.is_zipfile(pachet_descarcat):
        tinta.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(pachet_descarcat, "r") as arhiva:
            arhiva.extractall(tinta)
    else:
        return False
    instalate[nume] = {"versiune": versiune_noua}
    scrie_versiuni(instalate)
    return True


def revine(nume: str, versiune: str) -> bool:
    """Revino la versiunea anterioară (dacă programul nu pornește după actualizare)."""
    instalate = versiuni_instalate()
    if restaureaza(nume, versiune):
        instalate[nume] = {"versiune": versiune}
        scrie_versiuni(instalate)
        return True
    return False