"""Teste UI (offscreen) pentru secțiunile noi din Setări și ecranul de actualizări."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from PySide6.QtWidgets import QApplication

from dictare_transcriere_romana import config
from dictare_transcriere_romana.ui_qt.ui_setari import SECTIUNI, FereastraSetari


def _app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_sectiunile_noi_exista_in_lista():
    titluri = [titlu for titlu, _ in SECTIUNI]
    assert "Parolă și criptare" in titluri
    assert "Confidențialitate" in titluri
    assert titluri.index("Parolă și criptare") < titluri.index("Aspect")


def test_fereastra_setari_se_construieste_cu_noile_rânduri():
    _app()
    cfg = config.Config()
    dlg = FereastraSetari(None, cfg)
    try:
        # pagina „Parolă și criptare”
        assert dlg.var_cripteaza is not None
        assert dlg.var_cripteaza.isChecked() is False  # implicit: fără criptare
        assert not dlg.var_cripteaza.isEnabled()  # fără parolă pusă, caseta e stinsă
        assert dlg.eticheta_parola.text().startswith("Nicio parolă")
        # pagina „Confidențialitate”
        assert dlg.var_blocare == "nimic"
        coduri = [cod for cod, _ in dlg._casute_blocare]
        assert coduri == ["nimic", "program", "tot"]
        # numărul de pagini = numărul de secțiuni
        assert dlg.stack.count() == len(SECTIUNI)
        assert dlg.lista_sectiuni.count() == len(SECTIUNI)
    finally:
        dlg.deleteLater()


def test_alegerea_blocarii_exclusiva():
    _app()
    cfg = config.Config()
    dlg = FereastraSetari(None, cfg)
    try:
        casute = dict(dlg._casute_blocare)
        casute["tot"].setChecked(True)  # semnalul apelează singur _seteaza_blocare
        assert dlg.var_blocare == "tot"
        bife = {cod: casuta.isChecked() for cod, casuta in dlg._casute_blocare}
        assert bife == {"nimic": False, "program": False, "tot": True}
        casute["program"].setChecked(True)
        assert dlg.var_blocare == "program"
        bife = {cod: casuta.isChecked() for cod, casuta in dlg._casute_blocare}
        assert bife["program"] is True and bife["tot"] is False
    finally:
        dlg.deleteLater()


def test_aduna_pastreaza_alegerile_noi():
    _app()
    cfg = config.Config()
    dlg = FereastraSetari(None, cfg)
    try:
        dlg.var_blocare = "program"
        dlg._aduna()
        assert dlg.config.blocare_dictare == "program"
        assert dlg.config.cripteaza_documente is False
    finally:
        dlg.deleteLater()
