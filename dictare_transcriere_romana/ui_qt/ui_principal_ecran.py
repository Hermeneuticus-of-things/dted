"""Ecran principal PySide6: un rând compact de acțiuni rapide.

Înlocuiește PaginaPrincipala din ui_principal.py (Tkinter). Comenzile apar
și în bara de sus, deci aici e doar un rând scurt, ca editorul să ocupe
cel mai mult spațiu (cerințele 15 și 17).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..constante import NUME_AFISAT, NUME_SCURT, SUBTITLU_RO
from .comun import Buton, fonturi, seteaza_rol


class PaginaPrincipala(QWidget):
    """Ecranul de pornire: antet + acțiuni rapide pe un singur rând."""

    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(6)

        # Antet compact, un singur rând: numele (D&TED) + subtitlul, mai mic.
        antet = QHBoxLayout()
        antet.setSpacing(12)
        titlu = QLabel(f"{NUME_AFISAT} ({NUME_SCURT})")
        titlu.setTextFormat(Qt.TextFormat.PlainText)
        titlu.setFont(fonturi("buton"))
        antet.addWidget(titlu)
        subtitlu = QLabel(SUBTITLU_RO)
        subtitlu.setFont(fonturi("mica"))
        seteaza_rol(subtitlu, "secundar")
        antet.addWidget(subtitlu, 0, Qt.AlignmentFlag.AlignBottom)
        antet.addStretch(1)
        layout.addLayout(antet)

        # Acțiunile principale, pe un singur rând compact.
        rand = QHBoxLayout()
        rand.setSpacing(8)
        rand.addWidget(Buton(self, "🎤 Dictează", lambda: aplicatie.arata_ecran("dictare"), fel="principal", latime=120, inaltime=36))
        rand.addWidget(Buton(self, "📂 Transcrie un fișier", lambda: aplicatie.arata_ecran("transcriere"), latime=170, inaltime=36))
        rand.addWidget(Buton(self, "✏️ Scrie / corectează", lambda: aplicatie.arata_ecran("editor"), latime=160, inaltime=36))
        rand.addWidget(Buton(self, "🗂 Fișierele mele", lambda: aplicatie.arata_ecran("fisiere"), latime=140, inaltime=36))
        rand.addWidget(Buton(self, "🔊 Verifică sunetul", lambda: aplicatie.arata_ecran("sunet"), latime=150, inaltime=36))
        rand.addWidget(Buton(self, "🔍 Verifică calculatorul", lambda: aplicatie.arata_ecran("verificare"), latime=160, inaltime=36))
        rand.addStretch(1)
        layout.addLayout(rand)

    def sincronizeaza_din_stare(self) -> None:
        pass