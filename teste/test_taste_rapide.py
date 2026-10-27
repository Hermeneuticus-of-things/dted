"""Regresii pentru tastele rapide configurabile (Setări → „Taste rapide”)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from dictare_transcriere_romana import config as modul_config


def test_scurtaturi_implicit_si_mesor_potrivit():
    implicite = modul_config.SCURTATURI_IMPLICIT
    assert implicite["dictare"] == "F5"
    assert implicite["de_la_capat"] == "F6"
    assert implicite["idee_noua"] == "Shift+F6"

    # Config cu o tastă schimbată + o secțiune parțială: restul rămân implicite.
    config = modul_config.Config(scurtaturi={"dictare": "Ctrl+F5", "inventata": "X"})
    alese = modul_config.scurtaturi(config)
    assert alese["dictare"] == "Ctrl+F5"  # aleasă de utilizator
    assert alese["asculta"] == "F9"  # neschimbată → implicit
    assert "inventata" not in implicite  # chei străine: păstrate doar în alese
    assert modul_config.scurtaturi(modul_config.Config())["dictare"] == "F5"


def test_pagina_taste_rapide_se_construieste_si_salveaza():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from dictare_transcriere_romana.ui_qt.ui_setari import FereastraSetari, PrindeTasta

    _app = QApplication.instance() or QApplication([])
    config = modul_config.Config()
    fereastra = FereastraSetari(None, config)
    # Secțiunea există în listă și are un buton pentru fiecare comandă.
    titluri = [fereastra.lista_sectiuni.item(i).text() for i in range(fereastra.lista_sectiuni.count())]
    assert "Taste rapide" in titluri
    buton_dictare = getattr(fereastra, "_tasta_dictare")
    assert buton_dictare.secventa == "F5"

    # Captură: apăsarea Shift+F6 pe buton o face combinația aleasă.
    buton_idee = getattr(fereastra, "_tasta_idee_noua")
    buton_idee._porneste_prinderea()
    eveniment = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F6, Qt.KeyboardModifier.ShiftModifier)
    buton_idee.keyPressEvent(eveniment)
    assert buton_idee.secventa == "Shift+F6"

    # Esc anulează (păstrează valoarea veche).
    buton_idee.secventa = "Alt+N"
    buton_idee._porneste_prinderea()
    eveniment_esc = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    buton_idee.keyPressEvent(eveniment_esc)
    assert buton_idee.secventa == "Alt+N"

    # Revenirea la valorile din fabrică.
    getattr(fereastra, "_tasta_dictare").secventa = "Alt+X"
    fereastra._taste_implicit()
    assert getattr(fereastra, "_tasta_dictare").secventa == "F5"
    assert getattr(fereastra, "_tasta_idee_noua").secventa == "Shift+F6"

    # Salvarea scrie alegerile în config (ca _aduna).
    getattr(fereastra, "_tasta_dictare").secventa = "Ctrl+Alt+D2"
    fereastra._aduna()
    assert config.scurtaturi["dictare"] == "Ctrl+Alt+D2"
    fereastra.deleteLater()


def test_prinde_tasta_afiseaza_valoarea():
    from PySide6.QtWidgets import QApplication
    from dictare_transcriere_romana.ui_qt.ui_setari import PrindeTasta

    _app = QApplication.instance() or QApplication([])
    buton = PrindeTasta("F9")
    assert buton.text() == "F9"
    buton.pune_implicit("F10")
    assert buton.text() == "F10" and buton.secventa == "F10"
