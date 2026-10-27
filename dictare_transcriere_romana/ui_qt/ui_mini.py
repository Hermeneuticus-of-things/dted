"""Fereastra mică „mereu deasupra”: pornire + vumetru + oprire, în timpul dictării.

Înlocuiește nimic în Tkinter (cerința 40 / D-8). Stă deasupra celorlalte
ferestre, ca să pornești dictarea, să vezi nivelul microfonului și să oprești
dictarea chiar când lucrezi în alt program.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .comun import Buton, fonturi, seteaza_rol, text_nivel


class FereastraMini(QWidget):
    """Fereastră mică, mereu deasupra, legată de ecranul de dictare."""

    def __init__(self, sursa):
        super().__init__(None)
        self.sursa = sursa  # PaginaDictare (nivel_microfon + _opreste)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowTitle("Dictare — mică, mereu deasupra")
        self.setMinimumSize(340, 130)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        rand = QHBoxLayout()
        titlu = QLabel("🎤 Dictează")
        titlu.setFont(fonturi("buton"))
        rand.addWidget(titlu)
        rand.addStretch(1)
        self.eticheta_nivel = QLabel("Microfonul este oprit.")
        self.eticheta_nivel.setFont(fonturi("baza"))
        seteaza_rol(self.eticheta_nivel, "secundar")
        rand.addWidget(self.eticheta_nivel)
        layout.addLayout(rand)

        self.nivel_bar = QProgressBar()
        self.nivel_bar.setObjectName("nivel")
        self.nivel_bar.setProperty("chunk", "verde")
        self.nivel_bar.setRange(0, 1000)
        self.nivel_bar.setValue(0)
        self.nivel_bar.setTextVisible(False)
        self.nivel_bar.setMinimumHeight(12)
        layout.addWidget(self.nivel_bar)

        rand_butoane = QHBoxLayout()
        rand_butoane.setSpacing(8)
        self.buton_porneste = Buton(
            self, "● Pornește dictarea", self._porneste, fel="principal", inaltime=36
        )
        self.buton_opreste = Buton(
            self, "■ Oprește dictarea", self._opreste, fel="pericol", inaltime=36
        )
        self.buton_opreste.set_activ(False)
        self.buton_pauza = Buton(
            self, "⏸ Pauză", self._pauza, inaltime=36
        )
        self.buton_pauza.set_activ(False)
        rand_butoane.addWidget(self.buton_porneste)
        rand_butoane.addWidget(self.buton_opreste)
        rand_butoane.addWidget(self.buton_pauza)
        layout.addLayout(rand_butoane)

        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._actualizeaza)
        self._timer.start()

    def _actualizeaza(self) -> None:
        activ = self.sursa is not None and getattr(self.sursa, "_activ", False)
        # Butonul de pornire e activ doar când microfonul NU dictează; oprirea, dimpotrivă.
        self.buton_porneste.set_activ(not activ)
        self.buton_opreste.set_activ(activ)
        # Pauza de microfon: activă doar în timpul dictării, cu text după stare.
        pauza = bool(getattr(getattr(self.sursa, "_microfon", None), "pauza", False))
        self.buton_pauza.set_activ(activ)
        self.buton_pauza.set_text("⏵ Reprenește" if pauza else "⏸ Pauză")
        nivel = self.sursa.nivel_microfon if activ else 0.0
        valoare = min(1000, int(nivel * 1000))
        self.nivel_bar.setValue(valoare)

        text, rol = text_nivel(valoare)
        if activ:
            self.eticheta_nivel.setText(f"● {text}")
            seteaza_rol(self.eticheta_nivel, {"verde": "verde", "galben": "atentie", "rosu": "pericol"}[rol])
        else:
            self.eticheta_nivel.setText("Microfonul este oprit.")
            seteaza_rol(self.eticheta_nivel, "secundar")

        if self.nivel_bar.property("chunk") != rol:
            self.nivel_bar.setProperty("chunk", rol)
            self.nivel_bar.style().unpolish(self.nivel_bar)
            self.nivel_bar.style().polish(self.nivel_bar)

    def _porneste(self) -> None:
        """Pornește dictarea din fereastra mică (doar când microfonul nu e activ)."""
        if self.sursa is not None and not getattr(self.sursa, "_activ", False):
            self.sursa._porneste()

    def _opreste(self) -> None:
        if self.sursa is not None and getattr(self.sursa, "_activ", False):
            self.sursa._opreste()

    def _pauza(self) -> None:
        """Pauză / reluare microfon din fereastra mică (doar în timpul dictării)."""
        if self.sursa is None or not getattr(self.sursa, "_activ", False):
            return
        comuta = getattr(self.sursa, "_comuta_pauza", None)
        if comuta is not None:
            comuta()