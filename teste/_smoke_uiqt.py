import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from dictare_transcriere_romana.ui_qt import comun
    comun.pregateste_fonturi(None)
    for mod in ("luminos", "intunecat"):
        comun.aplica_tema(mod)
        c = comun.CULORI
        print("tema", mod, "fundal=", c.fundal, "succes=", c.succes,
              "principal_accent=", c.principal_accent,
              "pericol_accent=", c.pericol_accent, "succes_accent=", c.succes_accent)
    from dictare_transcriere_romana.ui_qt import (
        ui_setari, ui_internet, ui_dictare, ui_principal_ecran, ui_tur, ui_sunet,
    )
    print("imports OK")
    from dictare_transcriere_romana import config as config_modul
    cfg = config_modul.Config()
    fw = ui_setari.FereastraSetari(None, cfg, la_salvare=lambda c: None)
    print("FereastraSetari OK")
    fa = ui_internet.FereastraAvertisment(None, cfg, pentru_dictare=False)
    fa.reimprospateaza()
    print("FereastraAvertisment OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)