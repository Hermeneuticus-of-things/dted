"""Înlocuiri învățate din corecturile utilizatorului.

Când corectezi manual un cuvânt greșit — îl ștergi și scrii altul, sau îl
selectezi și rescrii — perechea „greșit → corect" se salvează automat în
``inlocuiri.json``, lângă instalare, și se aplică singură în textele scrise
de transcriere de acum încolo.

Reguli simple, ca să nu se învețe prostii:

- ambele părți trebuie să fie un singur cuvânt (minim 3 semne, doar litere,
  cratimă sau apostrof) — frazele refăcute nu se învață;
- perechile „același cuvânt" (doar altă majusculă) nu se învață;
- lista e limitată la 1000 de perechi (cele mai recente rămân).
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

#: Un cuvânt singur: începe cu literă și continuă cu litere, cratimă, apostrof.
_CUVANT = re.compile(r"^[A-Za-zĂÂÎȘȚăâîșț][A-Za-zĂÂÎȘȚăâîșț\-'’]{2,39}$")

#: Semnele de punctuație care se pot lipi de cuvinte și se ignoră.
_SEMNE = ".,;:!?„”\"«»()[]{}…"

#: Câte perechi se păstrează multum.
LIMITA = 1000


def fisier() -> Path:
    """Unde stau perechile pe disc: ``inlocuiri.json`` în folderul de instalare."""
    from . import cai

    return cai.director_instalare() / "inlocuiri.json"


def incarca() -> dict[str, str]:
    """Perechile învățate (dict gol dacă fișierul lipsește sau e deteriorat)."""
    try:
        date = json.loads(fisier().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(date, dict):
        return {}
    return {g: c for g, c in date.items() if isinstance(g, str) and isinstance(c, str)}


def salveaza(perechi: dict[str, str]) -> bool:
    """Scrie perechile pe disc; ``False`` dacă scrierea eșuează."""
    try:
        fisier_ = fisier()
        fisier_.parent.mkdir(parents=True, exist_ok=True)
        fisier_.write_text(
            json.dumps(perechi, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True
    except OSError:
        return False


def _este_cuvant(text: str) -> bool:
    return bool(_CUVANT.match(text))


def _curata(cuvant: str) -> str:
    """Scoate semnele de punctuație de la capetele cuvântului."""
    return cuvant.strip(_SEMNE)


def adauga(gresit: str, corect: str) -> bool:
    """Pune perechea (validată) în listă. Întoarce ``False`` dacă nu se merită."""
    gresit = _curata((gresit or "").strip())
    corect = _curata((corect or "").strip())
    if not _este_cuvant(gresit) or not _este_cuvant(corect):
        return False
    if gresit.lower() == corect.lower():
        return False
    perechi = incarca()
    perechi[gresit.lower()] = corect
    if len(perechi) > LIMITA:
        perechi = dict(list(perechi.items())[-LIMITA:])
    return salveaza(perechi)


def diferente_cuvinte(vechi: str, nou: str) -> list[tuple[str, str]]:
    """Perechile (greșit, corect) din diferența a două versiuni de text.

    Se uită doar la înlocuirile de un singur cuvânt cu un singur cuvânt;
    adăugările și ștergerile (dictarea care continuă, tăieri de fraze) nu
    produc nimic. Schimbările masive (text înlocuit integral) sunt ignorate.
    """
    if not vechi or not nou or vechi == nou:
        return []
    cuvinte_vechi = vechi.split()
    cuvinte_noi = nou.split()
    if abs(len(cuvinte_vechi) - len(cuvinte_noi)) > 4:
        return []
    perechi: list[tuple[str, str]] = []
    potrivire = SequenceMatcher(None, cuvinte_vechi, cuvinte_noi, autojunk=False)
    for op, i1, i2, j1, j2 in potrivire.get_opcodes():
        if op != "replace" or (i2 - i1) != (j2 - j1):
            # doar înlocuiri cu același număr de cuvinte; blocurile inegale
            # sunt fraze refăcute, nu corecturi de cuvinte
            continue
        # corecturi alăturate („greșit acuma” → „corect acum”) cad în același
        # bloc: le desperechem cuvânt cu cuvânt
        for pas in range(i2 - i1):
            gresit = _curata(cuvinte_vechi[i1 + pas])
            corect = _curata(cuvinte_noi[j1 + pas])
            if not gresit or not corect or gresit.lower() == corect.lower():
                continue
            if _este_cuvant(gresit) and _este_cuvant(corect):
                perechi.append((gresit, corect))
    return perechi


def aplica(text: str, perechi: dict[str, str] | None = None) -> str:
    """Aplică perechile învățate pe un text (majuscula de început se păstrează).

    Se înlocuiește doar cuvântul întreg (nu și părți din alte cuvinte).
    """
    if perechi is None:
        perechi = incarca()
    if not perechi or not text:
        return text
    for gresit, corect in perechi.items():
        if not gresit or not corect:
            continue

        def _schimba(potrivire, _corect=corect):
            gasit = potrivire.group(0)
            if gasit[:1].isupper():
                return _corect[:1].upper() + _corect[1:]
            return _corect

        sablon = rf"(?<![\w]){re.escape(gresit)}(?![\w])"
        text = re.sub(sablon, _schimba, text, flags=re.IGNORECASE)
    return text


#: Separatorii acceptați într-un rând de dicționar importat.
_SEPARATOARE = ("->", "→", "=", ";", ",", "\t")


def importa(text: str) -> tuple[int, int]:
    """Adaugă perechi dintr-un text: JSON ``{"greșit": "corect"}`` sau rânduri
    „greșit -> corect", „greșit = corect", „greșit, corect" ori „greșit<TAB>corect".

    Rândurile care încep cu „#” se ignoră. Întoarce (câte perechi s-au pus,
    câte rânduri au fost respinse).
    """
    text = (text or "").strip()
    if not text:
        return 0, 0
    puse = respinse = 0
    if text.startswith("{"):
        try:
            date = json.loads(text)
        except ValueError:
            return 0, 1
        if not isinstance(date, dict):
            return 0, 1
        for gresit, corect in date.items():
            if isinstance(corect, str) and adauga(str(gresit), corect):
                puse += 1
            else:
                respinse += 1
        return puse, respinse
    for rand in text.splitlines():
        rand = rand.strip()
        if not rand or rand.startswith("#"):
            continue
        for separator in _SEPARATOARE:
            if separator in rand:
                gresit, corect = rand.split(separator, 1)
                if adauga(gresit, corect):
                    puse += 1
                else:
                    respinse += 1
                break
        else:
            respinse += 1
    return puse, respinse


def importa_din_fisier(cale: Path) -> tuple[int, int]:
    """Importă perechile dintr-un fișier text sau JSON (vezi ``importa``)."""
    try:
        text = Path(cale).read_text(encoding="utf-8-sig")
    except OSError:
        return 0, 0
    return importa(text)


def exporta_text(perechi: dict[str, str]) -> str:
    """Dicționarul ca text simplu, rând cu rând (pentru salvat/trimis)."""
    randuri = [f"{gresit} -> {corect}" for gresit, corect in sorted(perechi.items())]
    return "\n".join(randuri) + ("\n" if randuri else "")
