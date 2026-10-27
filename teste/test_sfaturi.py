"""Regresii pentru bara de sfaturi inteligente contextuale."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))


def _fereastra():
    from PySide6.QtWidgets import QApplication
    from dictare_transcriere_romana.ui_qt.principal import Aplicatie

    _app = QApplication.instance() or QApplication([])
    f = Aplicatie({"interfata": True})
    f.configurare.tur_vazut = True
    return f


def test_bara_sfaturi_exista_si_arata_un_sfat():
    f = _fereastra()
    assert hasattr(f, "_bara_sfaturi")
    f._da_sfat()
    assert f._eticheta_sfat.text().startswith("💡")
    assert f._bara_sfaturi.isVisibleTo(f) or f._bara_sfaturi.isHidden() is False


def test_sfatul_se_schimba_cu_contextul():
    f = _fereastra()
    f._da_sfat()
    f._are_sunet = True
    f._sfat_index = 0
    f._da_sfat()
    assert "Ascultă" in f._eticheta_sfat.text() or "corectezi" in f._eticheta_sfat.text()
    f.close()


def test_ascundere_si_setare():
    f = _fereastra()
    f._ascunde_sfaturi()
    assert f._bara_sfaturi.isHidden()

    # setarea oprită → bara rămâne ascunsă chiar și la refresh
    f.configurare.arata_sfaturi = False
    f._da_sfat()
    assert f._bara_sfaturi.isHidden()
    f.configurare.arata_sfaturi = True  # close() salvează setările: nu contaminăm configul real
    f.close()


def test_comuta_sfatul_cu_butonul():
    f = _fereastra()
    f._da_sfat()
    inainte = f._eticheta_sfat.text()
    f._alt_sfat()
    dupa = f._eticheta_sfat.text()
    assert inainte != dupa
    f.close()  # (configul rămâne neatins: doar în memorie)
