"""Pagina Verificare PySide6: verifică calculatorul și resursele.

Înlocuiește PaginaVerificare din ui_principal.py (Tkinter).
"""

from __future__ import annotations

import threading
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import comun
from .comun import Buton, fonturi, seteaza_rol


class PaginaVerificare(QWidget):
    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie
        self.coada = comun.CoadaUI(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        lbl = QLabel("Verifică programul și calculatorul")
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

        card_hw = QFrame()
        card_hw.setObjectName("card")
        cl_hw = QVBoxLayout(card_hw)
        cl_hw.setContentsMargins(16, 12, 16, 12)
        cl_hw.setSpacing(6)
        et_hw = QLabel("Resursele calculatorului")
        et_hw.setFont(fonturi("buton"))
        cl_hw.addWidget(et_hw)
        self.eticheta_resurse = QLabel("Se verifică resursele calculatorului…")
        self.eticheta_resurse.setFont(fonturi("baza"))
        self.eticheta_resurse.setWordWrap(True)
        cl_hw.addWidget(self.eticheta_resurse)
        layout.addWidget(card_hw)

        # Starea plăcii video, citită la fiecare afișare (motor.STARE_PLACA_VIDEO).
        card_gpu = QFrame()
        card_gpu.setObjectName("card")
        cl_gpu = QVBoxLayout(card_gpu)
        cl_gpu.setContentsMargins(16, 12, 16, 12)
        cl_gpu.setSpacing(6)
        et_gpu = QLabel("Placa video (accelerare CUDA)")
        et_gpu.setFont(fonturi("buton"))
        cl_gpu.addWidget(et_gpu)
        self.eticheta_placa = QLabel("")
        self.eticheta_placa.setFont(fonturi("baza"))
        self.eticheta_placa.setWordWrap(True)
        cl_gpu.addWidget(self.eticheta_placa)
        self.buton_cuda = QPushButton("Descarcă bibliotecile pentru placa video (aprox. 1,2 GB)")
        self.buton_cuda.setFont(fonturi("baza"))
        self.buton_cuda.clicked.connect(self._descarca_cuda)
        rand = QHBoxLayout()
        rand.addWidget(self.buton_cuda)
        rand.addStretch(1)
        cl_gpu.addLayout(rand)
        layout.addWidget(card_gpu)

        rand_act = QHBoxLayout()
        self.btn_reverifica = Buton(self, "Verifică din nou", self._verifica_resurse, fel="principal", latime=200, inaltime=40)
        rand_act.addWidget(self.btn_reverifica)
        rand_act.addStretch(1)
        layout.addLayout(rand_act)

        layout.addStretch(1)
        self.actualizeaza_placa_video()
        self._verifica_resurse()

    def _verifica_resurse(self) -> None:
        self.eticheta_resurse.setText("Se verifică resursele calculatorului…")

        def lucru() -> None:
            from .. import resurse

            try:
                rap = resurse.verifica()
                linii = [
                    f"{c.simbol}  {c.nume}: {c.gasit} (cerință: {c.cerinta})"
                    for c in rap.cerinte
                ]
                text = "\n".join(linii) if linii else "Calculatorul îndeplinește cerințele."
            except Exception as exc:
                text = f"Nu am putut citi resursele: {exc}"
            self.coada.trimite(self.eticheta_resurse.setText, text)

        threading.Thread(target=lucru, name="verifica-hw", daemon=True).start()

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