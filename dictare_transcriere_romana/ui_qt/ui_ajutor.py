"""Fereastra ajutor PySide6: conținut de ajutor per ecran.

Înlocuiește ``ui_ajutor.py`` (Tkinter). Redă „Ghidul” din ``ajutor.py``
(ce vezi / ce faci / ce urmează / probleme frecvente).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import ajutor
from .comun import Buton, fonturi, seteaza_rol


class FereastraAjutor(QDialog):
    """Fereastra de ajutor pentru un ecran (cheia din ``ajutor.ghid``)."""

    def __init__(self, parinte, cheie: str = "principal"):
        super().__init__(parinte)
        self.setWindowTitle("Ajutor")
        self.setMinimumSize(560, 460)

        ghid = ajutor.ghid(cheie)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(8)

        titlu = QLabel(ghid.titlu)
        titlu.setFont(fonturi("titlu"))
        titlu.setWordWrap(True)
        layout.addWidget(titlu)

        derulare = QScrollArea()
        derulare.setWidgetResizable(True)
        derulare.setFrameShape(QFrame.Shape.NoFrame)
        continut = QWidget()
        col = QVBoxLayout(continut)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(8)

        self._sectiune(col, "Ce vezi", ghid.ce_vezi)
        self._sectiune(col, "Ce faci", ghid.ce_faci)
        if ghid.urmeaza:
            self._sectiune(col, "Ce urmează", ghid.urmeaza)
        if ghid.probleme:
            et = QLabel("Probleme frecvente")
            et.setFont(fonturi("buton"))
            col.addWidget(et)
            for intrebare, raspuns in ghid.probleme:
                q = QLabel(intrebare)
                q.setFont(fonturi("buton"))
                q.setWordWrap(True)
                col.addWidget(q)
                a = QLabel(raspuns)
                a.setFont(fonturi("baza"))
                a.setWordWrap(True)
                seteaza_rol(a, "secundar")
                col.addWidget(a)
        col.addStretch(1)

        derulare.setWidget(continut)
        layout.addWidget(derulare, stretch=1)

        rand = QHBoxLayout()
        rand.addStretch(1)
        rand.addWidget(Buton(self, "Am înțeles, încep", self.accept, fel="principal"))
        layout.addLayout(rand)

    @staticmethod
    def _sectiune(col: QVBoxLayout, titlu: str, randuri: list[str]) -> None:
        if not randuri:
            return
        et = QLabel(titlu)
        et.setFont(fonturi("buton"))
        col.addWidget(et)
        for rand in randuri:
            lbl = QLabel(f"•  {rand}")
            lbl.setFont(fonturi("baza"))
            lbl.setWordWrap(True)
            col.addWidget(lbl)