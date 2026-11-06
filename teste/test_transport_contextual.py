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
    assert not f.btn_pauza_microfon.isVisibleTo(f._dock_redare)
    assert not f.btn_transport.isVisibleTo(f._dock_redare)

    # Mod dictare: pauza de microfon vizibilă; redarea ascunsă.
    f._seteaza_mod_transport("dictare")
    assert f.btn_pauza_microfon.isVisibleTo(f._dock_redare)
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
    f.close()


def test_alineatele_raman_din_editor_si_comenzi_vocale():
    """P/I alineat au fost scoase ca butoane: nu mai există în interfață.

    Paragrafele noi se fac din editor (Enter) și din comenzi vocale
    („paragraf nou”, „rând nou”) + pauzele lungi configurabile.
    """
    f = _fereastra()
    assert not hasattr(f, "btn_de_la_capat")
    assert not hasattr(f, "btn_idee_noua")
    f.close()
