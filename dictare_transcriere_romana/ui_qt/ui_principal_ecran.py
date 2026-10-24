"""Ecran de bun venit („Ecranul de start” din Instrumente).

Redesign UX: fără butoane care dublează bara de sus — acolo e un singur loc
pentru fiecare acțiune (Dictează, Transcrie, Ascultă), ca în aplicațiile
profesionale. Aici e doar un ghid scurt: cum merge programul, în trei pași.
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
from .comun import fonturi, seteaza_rol


class PaginaPrincipala(QWidget):
    """Ghid scurt de trei pași; acțiunile sunt doar în bara de sus."""

    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        titlu = QLabel(f"{NUME_AFISAT} ({NUME_SCURT})")
        titlu.setTextFormat(Qt.TextFormat.PlainText)
        titlu.setFont(fonturi("titlu"))
        layout.addWidget(titlu)

        subtitlu = QLabel(SUBTITLU_RO)
        subtitlu.setFont(fonturi("baza"))
        seteaza_rol(subtitlu, "secundar")
        subtitlu.setWordWrap(True)
        layout.addWidget(subtitlu)

        layout.addSpacing(8)
        pași = QLabel("Cum merge, în trei pași")
        pași.setFont(fonturi("buton"))
        layout.addWidget(pași)

        for număr, text, detaliu in (
            ("1", "Vorbește", "apasă „🎤 Dictează” din bara de sus (sau Ctrl+Space) și dictează calm; semnele [mm:ss] se pun cu Ctrl+B"),
            ("2", "Corectează ascultând", "pune cursorul lângă un semn și apasă Ctrl+R — redau exact bucata aia din înregistrare"),
            ("3", "Salvează", "Ctrl+S salvează documentul (DOCX, ODT, TXT, PDF…); criptarea cu parolă e din Setări"),
        ):
            rand = QHBoxLayout()
            rand.setSpacing(12)
            numar = QLabel(număr)
            numar.setFont(fonturi("titlu"))
            numar.setMinimumWidth(22)
            seteaza_rol(numar, "secundar")
            rand.addWidget(numar, 0, Qt.AlignmentFlag.AlignTop)
            coloana = QVBoxLayout()
            coloana.setSpacing(2)
            nume = QLabel(text)
            nume.setFont(fonturi("buton"))
            coloana.addWidget(nume)
            explicatie = QLabel(detaliu)
            explicatie.setFont(fonturi("baza"))
            explicatie.setWordWrap(True)
            seteaza_rol(explicatie, "secundar")
            coloana.addWidget(explicatie)
            rand.addLayout(coloana, 1)
            layout.addLayout(rand)

        layout.addSpacing(6)
        nota = QLabel(
            "Restul uneltelor (sunet, fișiere, confidențialitate, instalare) sunt în "
            "meniul „Instrumente ▾” din dreapta sus."
        )
        nota.setFont(fonturi("mica"))
        seteaza_rol(nota, "secundar")
        nota.setWordWrap(True)
        layout.addWidget(nota)
        layout.addStretch(1)

    def sincronizeaza_din_stare(self) -> None:
        pass
