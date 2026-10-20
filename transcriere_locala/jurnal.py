"""Jurnal simplu, în fișier și pe ecran.

Jurnalul de instalare păstrează toate deciziile (inclusiv „sari peste
verificare”), ca o problemă să poată fi înțeleasă ulterior.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable

from . import cai

_ascultatori: list[Callable[[str], None]] = []


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
        with open(cale, "a", encoding="utf-8") as fisier:
            fisier.write(linie + "\n")
    except OSError:
        # Jurnalul nu trebuie să oprească niciodată programul.
        pass


def _linie(nivel: str, mesaj: str) -> str:
    moment = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"[{moment}] {nivel:<8} {mesaj}"


def _anunta(text: str) -> None:
    for functie in list(_ascultatori):
        try:
            functie(text)
        except Exception:
            pass
    if sys.stdout and not sys.stdout.closed:
        try:
            print(text, flush=True)
        except Exception:
            pass


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
    _anunta(mesaj)


def instalare(mesaj: str) -> None:
    """Linie în jurnalul de instalare (păstrat separat, ușor de trimis)."""
    linie = _linie("INSTALARE", mesaj)
    _scrie(cai.fisier_jurnal_instalare(), linie)
    _scrie(cai.fisier_jurnal_aplicatie(), linie)
    _anunta(mesaj)


def goleste_jurnal_instalare() -> None:
    try:
        cai.fisier_jurnal_instalare().unlink(missing_ok=True)
    except OSError:
        pass
