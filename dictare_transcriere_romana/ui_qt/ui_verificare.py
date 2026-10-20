"""Pagina Verificare PySide6: verifică calculatorul și resursele.

Înlocuiește PaginaVerificare din ui_principal.py (Tkinter).
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .comun import fonturi, seteaza_rol


class PaginaVerificare(QWidget):
    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        lbl = QLabel("Verifică calculatorul")
        lbl.setFont(fonturi("titlu"))
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        txt = QLabel(
            "Aici poți verifica dacă calculatorul tău îndeplinește cerințele "
            "pentru rularea programului: sistem de operare, procesor, RAM, "
            "spațiu pe disc și placă video."
        )
        txt.setFont(fonturi("baza"))
        seteaza_rol(txt, "secundar")
        txt.setWordWrap(True)
        layout.addWidget(txt)

        # Starea plăcii video, citită la fiecare afișare (motor.STARE_PLACA_VIDEO).
        self.eticheta_placa = QLabel("")
        self.eticheta_placa.setFont(fonturi("baza"))
        self.eticheta_placa.setWordWrap(True)
        layout.addWidget(self.eticheta_placa)
        self.buton_cuda = QPushButton("Descarcă bibliotecile pentru placa video (aprox. 1,2 GB)")
        self.buton_cuda.setFont(fonturi("baza"))
        self.buton_cuda.clicked.connect(self._descarca_cuda)
        rand = QHBoxLayout()
        rand.addWidget(self.buton_cuda)
        rand.addStretch(1)
        layout.addLayout(rand)
        layout.addStretch(1)
        self.actualizeaza_placa_video()

    def _descarca_cuda(self) -> None:
        functie = getattr(self.aplicatie, "descarca_cuda_la_cerere", None)
        if callable(functie):
            functie()

    def actualizeaza_placa_video(self) -> None:
        from .. import motor, pregatire

        try:
            text = motor.descriere_placa_video()
            extra = pregatire.text_stare_cuda(getattr(self.aplicatie, "configurare", None))
            self.eticheta_placa.setText(text + ("\n" + extra if extra else ""))
            self.buton_cuda.setVisible(bool(extra))
        except Exception as exc:
            self.eticheta_placa.setText(f"Placa video: nu am putut verifica ({exc}).")
            self.buton_cuda.setVisible(False)

    def showEvent(self, event) -> None:  # la fiecare deschidere a ecranului
        self.actualizeaza_placa_video()
        super().showEvent(event)