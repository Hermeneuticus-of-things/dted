"""Capturile README pentru v0.6.3: interfața cu bara contextuală + Taste rapide.

Rulează pe platforma grafică reală (ferestrele apar pe ecran câteva secunde,
cât se face captura), ca textul să iasă cu fonturile reale ale Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from dictare_transcriere_romana import pregatire  # noqa: E402

pregatire.fisiere_model_lipsa = lambda *a, **k: []
pregatire.cuda_de_propus = lambda *a, **k: False

from dictare_transcriere_romana.ui_qt.principal import Aplicatie  # noqa: E402

app = QApplication.instance() or QApplication([])

folder = ROOT / "docs" / "img"
folder.mkdir(parents=True, exist_ok=True)

f = Aplicatie({"interfata": True})
f.configurare.tur_vazut = True
f.resize(1280, 800)
# Fără dictările reale în poze (date personale): ascundem lista.
f.lista_dictari.hide()
f._eticheta_lista.hide()
f.show()
app.processEvents()

# Text de probă în editor, ca poza să arate o dictare adevărată.
f.editor.set_text(
    "Capitolul întâi [00:12]\n\n"
    "Probă de dictare: programul scrie cuvânt cu cuvânt, pe măsură ce vorbesc, "
    "și nu mă mai așteaptă. Dacă mă încurc, apasă „↺ De la capăt”, iar pentru "
    "o idee nouă apasă „⇥ Idee nouă”.\n\n"
    "Vorbește liniștit cu cineva? „⏸ Pauză microfon” oprește ascultarea până la reluare."
)
app.processEvents()

# 1) Interfața principală, în modul dictare (bara arată doar butoanele de dictare).
f._seteaza_mod_transport("dictare")
f.btn_pauza_microfon.setEnabled(True)
app.processEvents()
f.grab().save(str(folder / "interfata-v063.png"))
print("salvat interfata-v063.png")

# 2) Modul de redare: după o dictare, bara arată doar butoanele audio.
f._are_sunet = True
f._seteaza_mod_transport("audio")
f.btn_transport.setEnabled(True)
f.btn_transport_stop.setEnabled(True)
f._eticheta_redare.setText("00:42 / 03:10")
f._slider_redare.setValue(220)
app.processEvents()
f.grab().save(str(folder / "transport-redare-v063.png"))
print("salvat transport-redare-v063.png")
f.close()

# 3) Setări → „Taste rapide”.
from dictare_transcriere_romana import config as modul_config  # noqa: E402
from dictare_transcriere_romana.ui_qt.ui_setari import FereastraSetari  # noqa: E402

dlg = FereastraSetari(None, modul_config.Config())
for i in range(dlg.lista_sectiuni.count()):
    if dlg.lista_sectiuni.item(i).text() == "Taste rapide":
        dlg.lista_sectiuni.setCurrentRow(i)
        break
dlg.show()
app.processEvents()
dlg.grab().save(str(folder / "taste-rapide-v063.png"))
print("salvat taste-rapide-v063.png")
dlg.close()
print("GATA")
