"""Captură de ecran headless pentru verificarea contrastului și a vumetrului.

Rulează fără să descarce modelul sau să atingă rețeaua: monkeypatch pe funcțiile
de pregătire. Pornește aplicația, trece prin ecrane și salvează PNG-uri.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402

from dictare_transcriere_romana.ui_qt import comun  # noqa: E402
from dictare_transcriere_romana.ui_qt.principal import Aplicatie  # noqa: E402

# Împiedică descărcarea modelului / CUDA la prima pornire.
from dictare_transcriere_romana import pregatire  # noqa: E402

pregatire.fisiere_model_lipsa = lambda *a, **k: []
pregatire.cuda_de_propus = lambda *a, **k: False


def captureaza(aplicatie: Aplicatie, nume: str, folder: Path) -> None:
    aplicatie.resize(1280, 800)
    aplicatie.show()
    aplicatie.repaint()
    app.processEvents()
    pixmap = aplicatie.grab()
    cale = folder / f"{nume}.png"
    pixmap.save(str(cale))
    print(f"salvat {cale}")


def main() -> int:
    global app
    app = QApplication.instance() or QApplication([])
    aplicatie = Aplicatie({"interfata": True})
    # Oprește turul și alte verificări asincrone care ar deranja captura.
    aplicatie.configurare.tur_vazut = True
    folder = ROOT / "teste" / "capturi"
    folder.mkdir(parents=True, exist_ok=True)

    for mod in ("luminos", "intunecat"):
        comun.aplica_tema(mod)
        aplicatie.actualizeaza_etichete = lambda *a: None
        aplicatie.arata_ecran("principal")
        captureaza(aplicatie, f"principal_{mod}", folder)
        aplicatie.arata_ecran("dictare")
        captureaza(aplicatie, f"dictare_{mod}", folder)
        aplicatie.arata_ecran("transcriere")
        captureaza(aplicatie, f"transcriere_{mod}", folder)
        aplicatie.arata_ecran("setari")
        captureaza(aplicatie, f"setari_{mod}", folder)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())