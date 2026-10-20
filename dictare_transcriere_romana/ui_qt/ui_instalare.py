"""Ecranul „Instalare” PySide6: arată starea instalării.

Înlocuiește ``ui_instalare.py`` (Tkinter, asistentul de instalare în 10 pași).
Aici, în programul care deja rulează, arătăm doar starea, fără acțiuni care
șterg sau schimbă ceva: versiunea, componentele și o verificare completă.
"""

from __future__ import annotations

import threading

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .. import cai, instalare, libreoffice
from ..constante import NUME_AFISAT, NUME_SCURT, VERSIUNE_COMPLETA
from . import comun
from .comun import Buton, fonturi, seteaza_rol


class FereastraInstalare(QWidget):
    """Verificarea stării instalării (numai citire)."""

    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie
        self.coada = comun.CoadaUI(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        titlu = QLabel("Instalare și actualizări")
        titlu.setFont(fonturi("titlu"))
        layout.addWidget(titlu)

        versiune = QLabel(f"{NUME_AFISAT} ({NUME_SCURT}) — versiunea {VERSIUNE_COMPLETA}")
        versiune.setFont(fonturi("baza"))
        versiune.setWordWrap(True)
        layout.addWidget(versiune)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(6)
        et = QLabel("Starea componentelor")
        et.setFont(fonturi("buton"))
        cl.addWidget(et)

        self.et_model = self._rand_componenta(cl, "Modelul de transcriere (Whisper)")
        self.et_scris = self._rand_componenta(cl, "Programul de scris (LibreOffice)")

        layout.addWidget(card)

        self.et_detalii = QLabel("")
        self.et_detalii.setFont(fonturi("baza"))
        self.et_detalii.setWordWrap(True)
        layout.addWidget(self.et_detalii)

        rand = QHBoxLayout()
        rand.setSpacing(8)
        self.btn_verifica = Buton(self, "Verifică din nou", self._verifica, fel="principal", latime=220, inaltime=40)
        rand.addWidget(self.btn_verifica)
        rand.addStretch(1)
        layout.addLayout(rand)
        layout.addStretch(1)

        self._verifica()

    @staticmethod
    def _rand_componenta(col: QVBoxLayout, nume: str) -> QLabel:
        rand = QHBoxLayout()
        lab = QLabel(nume)
        lab.setFont(fonturi("baza"))
        rand.addWidget(lab, 1)
        stare = QLabel("se verifică…")
        stare.setFont(fonturi("baza"))
        seteaza_rol(stare, "secundar")
        rand.addWidget(stare)
        col.addLayout(rand)
        return stare

    def _verifica(self) -> None:
        self.btn_verifica.setEnabled(False)
        for eticheta in (self.et_model, self.et_scris):
            eticheta.setText("se verifică…")
            seteaza_rol(eticheta, "secundar")
        self.et_detalii.setText("")

        def lucru() -> None:
            model_ok = cai.fisier_model().exists()
            try:
                scris_ok = libreoffice.stare().gasit
            except Exception:
                scris_ok = False
            try:
                probleme = instalare.verifica_instalare()
            except Exception as exc:
                probleme = [f"Verificarea completă a eșuat: {exc}"]
            self.coada.trimite(self._dupa_verificare, model_ok, scris_ok, probleme)

        threading.Thread(target=lucru, name="verificare-instalare", daemon=True).start()

    def _dupa_verificare(self, model_ok: bool, scris_ok: bool, probleme: list[str]) -> None:
        self.btn_verifica.setEnabled(True)
        self._pune(self.et_model, model_ok)
        self._pune(self.et_scris, scris_ok)
        if not probleme:
            self.et_detalii.setText("Totul este în regulă: programul are tot ce îi trebuie.")
            seteaza_rol(self.et_detalii, "verde")
        else:
            self.et_detalii.setText("• " + "\n• ".join(probleme))
            seteaza_rol(self.et_detalii, "pericol")

    @staticmethod
    def _pune(eticheta: QLabel, ok: bool) -> None:
        eticheta.setText(("✔  instalat" if ok else "✘  lipsește"))
        seteaza_rol(eticheta, "verde" if ok else "pericol")