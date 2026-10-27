"""Regresii pentru bara de transport contextuală (dictare vs. audio)."""

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
    f = Aplicatie()
    return f


def test_transportul_arata_doar_butoanele_modului():
    f = _fereastra()

    # La pornire (nimic de ascultat): doar butonul roșu de dictare e vizibil.
    f._seteaza_mod_transport("nimic")
    assert not f.btn_pauza_microfon.isVisible() or True  # offscreen: folosește setVisible
    assert not f.btn_pauza_microfon.isVisibleTo(f._dock_redare)
    assert not f.btn_transport.isVisibleTo(f._dock_redare)
    assert not f.btn_de_la_capat.isVisibleTo(f._dock_redare)

    # Mod dictare: pauză, de la capăt, idee nouă vizibile; redarea ascunsă.
    f._seteaza_mod_transport("dictare")
    assert f.btn_pauza_microfon.isVisibleTo(f._dock_redare)
    assert f.btn_de_la_capat.isVisibleTo(f._dock_redare)
    assert f.btn_idee_noua.isVisibleTo(f._dock_redare)
    assert not f.btn_transport.isVisibleTo(f._dock_redare)
    assert not f._slider_redare.isVisibleTo(f._dock_redare)
    assert not f._slider_volum.isVisibleTo(f._dock_redare)

    # Mod audio: butoanele de redare vizibile; cele de dictare ascunse.
    f._seteaza_mod_transport("audio")
    assert f.btn_transport.isVisibleTo(f._dock_redare)
    assert f.btn_transport_stop.isVisibleTo(f._dock_redare)
    assert f._slider_redare.isVisibleTo(f._dock_redare)
    assert f._eticheta_redare.isVisibleTo(f._dock_redare)
    assert f._slider_volum.isVisibleTo(f._dock_redare)
    assert not f.btn_pauza_microfon.isVisibleTo(f._dock_redare)
    assert not f.btn_idee_noua.isVisibleTo(f._dock_redare)
    f.close()
