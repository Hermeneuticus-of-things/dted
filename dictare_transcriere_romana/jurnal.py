"""Jurnal simplu, în fișier și pe ecran.

Jurnalul de instalare păstrează toate deciziile (inclusiv „Sari peste
verificare”), ca o problemă apărută mai târziu să poată fi înțeleasă.
Jurnalul nu oprește niciodată programul: dacă nu poate scrie, tace.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable

from . import cai

_ascultatori: list[Callable[[str], None]] = []
_MAXIM_LINII = 4000  # păstrăm jurnalul mic, ca să poată fi trimis ușor


def adauga_ascultator(functie: Callable[[str], None]) -> None:
    """Înregistrează o funcție care primește fiecare linie de jurnal."""
    if functie not in _ascultatori:
        _ascultatori.append(functie)


def scoate_ascultator(functie: Callable[[str], None]) -> None:
    if functie in _ascultatori:
        _ascultatori.remove(functie)


def _scrie(cale: Path, linie: str) -> None:
    try:
        cale.parent.mkdir(parents=True, exist_ok=True)
        if cale.exists() and cale.stat().st_size > 512_000:
            # Rotim jurnalul: păstrăm doar ultimele linii.
            continut = cale.read_text(encoding="utf-8", errors="replace").splitlines()
            cale.write_text("\n".join(continut[-_MAXIM_LINII:]) + "\n", encoding="utf-8")
        with open(cale, "a", encoding="utf-8") as fisier:
            fisier.write(linie + "\n")
    except OSError:
        pass


def _linie(nivel: str, mesaj: str) -> str:
    moment = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"[{moment}] {nivel:<9} {mesaj}"


def _anunta(text: str) -> None:
    for functie in list(_ascultatori):
        try:
            functie(text)
        except Exception:
            # Un ascultător defect nu trebuie să oprească programul.
            pass
    strm = sys.stdout
    if strm and not strm.closed:
        try:
            print(text, flush=True)
        except Exception:
            # Consola poate refuza diacriticele; jurnalul rămâne corect.
            pass


def detaliu(mesaj: str) -> None:
    """Detaliu tehnic (scris doar în jurnal, fără anunț pe ecran)."""
    linie = _linie("DETALIU", mesaj)
    _scrie(cai.fisier_jurnal_aplicatie(), linie)


def info(mesaj: str) -> None:
    linie = _linie("INFO", mesaj)
    _scrie(cai.fisier_jurnal_aplicatie(), linie)
    _anunta(mesaj)


def atentionare(mesaj: str) -> None:
    linie = _linie("ATENȚIE", mesaj)
    _scrie(cai.fisier_jurnal_aplicatie(), linie)
    _anunta(mesaj)


def eroare(mesaj: str) -> None:
    linie = _linie("EROARE", mesaj)
    _scrie(cai.fisier_jurnal_aplicatie(), linie)
    _scrie(cai.fisier_jurnal_instalare(), linie)
    _anunta(mesaj)
    for functie in list(_observatori_eroare):
        try:
            functie(mesaj)
        except Exception:
            pass


def instalare(mesaj: str) -> None:
    """Linie în jurnalul de instalare (păstrat separat, ușor de trimis)."""
    linie = _linie("INSTALARE", mesaj)
    _scrie(cai.fisier_jurnal_instalare(), linie)
    _scrie(cai.fisier_jurnal_aplicatie(), linie)
    _anunta(mesaj)


_observatori_eroare: list[Callable[[str], None]] = []


def adauga_observator_eroare(functie: Callable[[str], None]) -> None:
    """Funcție chemată când programul prinde singur o eroare (pt. „Trimite raportul?”)."""
    if functie not in _observatori_eroare:
        _observatori_eroare.append(functie)


def scoate_observator_eroare(functie: Callable[[str], None]) -> None:
    if functie in _observatori_eroare:
        _observatori_eroare.remove(functie)


def ultimele_erori(cate: int = 5) -> list[str]:
    """Ultimele linii de EROARE/ATENȚIE din jurnalul aplicației (cea mai nouă la sfârșit).

    Sunt detaliile tehnice cu care se deschide fereastra „Raportează o problemă”.
    """
    try:
        linii = cai.fisier_jurnal_aplicatie().read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except OSError:
        return []
    erori = [
        linie for linie in linii
        if "] EROARE " in linie or "] ATENȚIE " in linie
    ]
    return erori[-cate:]


def ultimele_linii(cate: int = 200) -> list[str]:
    """Ultimele linii din jurnalul de instalare, pentru fereastra de eroare."""
    try:
        return cai.fisier_jurnal_instalare().read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()[-cate:]
    except OSError:
        return []


def goleste_jurnal_instalare() -> None:
    try:
        cai.fisier_jurnal_instalare().unlink(missing_ok=True)
    except OSError:
        pass
