"""Tur primul rulez PySide6: 4 pași de introducere.

Înlocuiește ``ui_tur.py`` (Tkinter).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton, QHBoxLayout

from ..constante import NUME_AFISAT, NUME_SCURT
from .comun import Buton, fonturi, seteaza_rol


class TurPrimulRulez(QDialog):
    def __init__(self, parinte, la_final=None):
        super().__init__(parinte)
        self.setWindowTitle("Tur de prezentare")
        self.setMinimumSize(500, 400)
        self.la_final = la_final
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        lbl = QLabel(f"Bine ai venit în {NUME_AFISAT} ({NUME_SCURT})!")
        lbl.setTextFormat(Qt.TextFormat.PlainText)
        lbl.setFont(fonturi("titlu"))
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        txt = QLabel(
            "Acest tur îți arată cele mai importante funcții:\n\n"
            "1. Dictează — vorbește în microfon și vezi textul în timp real.\n"
            "2. Transcriere — încarcă un fișier audio și obține textul.\n"
            "3. Editorul — scrie, corectează și salvează documente.\n"
            "4. Setări — alege limba, microfonul și alte opțiuni.\n\n"
            "Pentru a începe, apasă „Am înțeles, încep”."
        )
        txt.setFont(fonturi("baza"))
        seteaza_rol(txt, "secundar")
        txt.setWordWrap(True)
        layout.addWidget(txt)
        layout.addStretch(1)
        rand = QHBoxLayout()
        rand.addStretch(1)
        rand.addWidget(Buton(self, "Am înțeles, încep", self.accept, fel="principal"))
        layout.addLayout(rand)

    def accept(self):
        if self.la_final:
            self.la_final()
        super().accept()