"""Regresii pentru motorul de focus Ionuț ADL și etichetele SR complete."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from dictare_transcriere_romana.ui_qt.focus_motor import EroareFocus, FocusMotor


def test_motor_stiva_push_pop_switch():
    m = FocusMotor()
    m.inregistreaza("fereastra.principal", nivel="fereastră")
    m.inregistreaza("editor.document", nivel="suprafață", parinte="fereastra.principal")
    m.inregistreaza("dialog.setari", nivel="dialog", parinte="fereastra.principal", modal=True)

    m.apasa("editor.document")
    assert m.suprafata_activa() == "editor.document"
    m.apasa("dialog.setari")
    assert m.suprafata_activa() == "dialog.setari"
    m.scoate("dialog.setari")
    assert m.suprafata_activa() == "editor.document"  # revenire exactă (ADL §2)
    m.scoate("editor.document")
    assert m.suprafata_activa() is None

    # comanda pe suprafață neînregistrată → eroare clară
    try:
        m.apasa("inexistent")
        assert False
    except EroareFocus:
        pass


def test_motor_comanda_bubbling_activ_parinte_radacina():
    apelate = []
    m = FocusMotor()
    m.inregistreaza("fereastra.principal", nivel="fereastră",
                    comenzi={"salvează": lambda: apelate.append("fereastră")})
    m.inregistreaza("editor.document", nivel="suprafață", parinte="fereastra.principal",
                    comenzi={"găsește": lambda: apelate.append("editor")})
    m.apasa("editor.document")

    assert m.comanda("găsește") is True          # local suprafeței active
    assert apelate[-1] == "editor"
    assert m.comanda("salvează") is True         # bubbling către părinte
    assert apelate[-1] == "fereastră"
    assert m.comanda("comandă-inexistentă") is False


def test_onfocus_onblur_chimate_la_tranzitii():
    evenimente = []
    m = FocusMotor()
    m.inregistreaza("a", onFocus=lambda: evenimente.append("focus-a"),
                    onBlur=lambda: evenimente.append("blur-a"))
    m.inregistreaza("b", onFocus=lambda: evenimente.append("focus-b"))
    m.apasa("a")
    m.apasa("b")
    assert evenimente == ["focus-a", "blur-a", "focus-b"]


def test_accesibilitate_completa_pe_aplicatie():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    if QApplication.instance() is None:
        QApplication([])

    from dictare_transcriere_romana import pregatire

    pregatire.fisiere_model_lipsa = lambda *a, **k: []
    pregatire.cuda_de_propus = lambda *a, **k: False
    from dictare_transcriere_romana.ui_qt.principal import Aplicatie

    f = Aplicatie({"interfata": True})
    f.configurare.tur_vazut = True
    # fiecare buton din interfață are nume accesibil (SR îl citește)
    from PySide6.QtWidgets import QPushButton
    fără_nume = [
        b for b in f.findChildren(QPushButton)
        if not b.accessibleName() and not b.text() and not b.toolTip()
    ]
    assert fără_nume == [], f"butoane fără nume accesibil: {fără_nume}"
    # motorul de focus există și editorul e activ
    assert f.focus_motor.suprafata_activa() == "editor.document"
    f.close()
