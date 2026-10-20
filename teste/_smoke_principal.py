import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from dictare_transcriere_romana.ui_qt import principal

    a = principal.Aplicatie(None)
    print("Aplicatie construit:", type(a).__name__)
    # Meniul Fișier trebuie să aibă submeniul „Recente”.
    print("menu_recente există:", a.menu_recente.title())
    # starea butonului dictare + vumetru (fără a porni microfonul)
    a._actualizeaza_buton_dictare()
    print("btn_dictare text:", repr(a.btn_dictare.text()))
    a._actualizeaza_vumetru()
    print("vumetru text:", repr(a.vumetru_text.text()))
    print("OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)