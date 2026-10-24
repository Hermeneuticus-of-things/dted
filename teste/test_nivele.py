"""Teste pentru nivele.py (dB + decizie) și vumetrul cu gradații."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dictare_transcriere_romana import config, nivele


def test_amplitudine_in_db_zero_este_distorsiunea():
    assert abs(nivele.amplitudine_in_db(1.0) - 0.0) < 1e-9      # plină scara = 0 dB
    assert abs(nivele.amplitudine_in_db(0.5) + 6.0206) < 0.01   # jumătate ≈ -6 dB
    assert abs(nivele.amplitudine_in_db(0.1) + 20.0) < 0.01     # -20 dB
    assert nivele.amplitudine_in_db(0.0) == nivele.DB_MINIM     # tăcere: fundul scării


def test_cartografierea_db_pe_bara():
    assert nivele.db_in_fractie(nivele.DB_MINIM) == 0.0
    assert nivele.db_in_fractie(0.0) == 1.0
    assert 0.0 < nivele.db_in_fractie(-30.0) < 1.0
    # valorile afară din scară se limitează
    assert nivele.db_in_fractie(-99.0) == 0.0
    assert nivele.db_in_fractie(+5.0) == 1.0


def test_zonele_si_decizia():
    assert nivele.zona_db(-15.0) == "verde"       # zona bună de dictare
    assert nivele.zona_db(-1.0) == "roșu"         # aproape de distorsiune
    assert nivele.zona_db(-50.0) == "galben"      # prea încet

    assert nivele.decizie_volum(-2.0) == "coboara"   # risc de tăiere → se coboară
    assert nivele.decizie_volum(-50.0) == "urca"     # abia se aude → se urcă
    assert nivele.decizie_volum(-15.0) == ""         # e bine așa


def test_textul_pentru_utilizator():
    assert "distorsiune" in nivele.text_db(0.0)
    assert nivele.text_db(-12.35).startswith("-12,4 dB") or "-12,3" in nivele.text_db(-12.35)


def test_config_are_auto_volum_pornit():
    assert config.Config().auto_volum is True


def test_vumetrul_db_se_construieste_si_primeste_nivel():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from dictare_transcriere_romana.ui_qt.comun import VumetruDb

    vumetru = VumetruDb()
    vumetru.pune_db(-12.0)
    assert vumetru.nivel_db() == -12.0
    vumetru.pune_db(3.0)     # se limitează la 0 (distorsiune)
    assert vumetru.nivel_db() == 0.0
    vumetru.pune_db(-99.0)   # se limitează la fundul scării
    assert vumetru.nivel_db() == nivele.DB_MINIM
    vumetru.grab()  # desenează efectiv, offscreen
    assert vumetru.size().width() >= 200
