"""Ecranul „Verifică sunetul” PySide6: microfon, difuzoare, căști.

Înlocuiește ``ui_sunet.py`` (Tkinter). Probele: microfon 5 secunde (cu vumetru
verde/galben/roșu), difuzor (sunet scurt + întrebare), căști (stânga/dreapta).
"""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .. import dispozitive, inregistrare, jurnal
from . import comun
from .comun import Buton, fonturi, seteaza_rol

#: Cât ține proba microfonului, în secunde.
SECUNDE_PROBA = 5


class FereastraSunet(QWidget):
    """Verificarea sunetului: microfon, difuzor și căști (cerința 7 / H.23)."""

    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie
        self.coada = comun.CoadaUI(self)
        self._microfon_activ: inregistrare.Microfon | None = None
        self._test_in_curs = False
        self._microfon: dispozitive.Dispozitiv | None = None
        self._difuzor: dispozitive.Dispozitiv | None = None
        self._casti: dispozitive.Dispozitiv | None = None
        self._randuri: dict[str, dict] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(10)
        self._layout = layout

        titlu = QLabel("Verifică sunetul — microfon, difuzoare, căști")
        titlu.setFont(fonturi("titlu"))
        titlu.setWordWrap(True)
        layout.addWidget(titlu)

        exp = QLabel(
            "Aici verifici dacă programul aude și se aude. Vorbește la proba microfonului, "
            "apoi ascultă sunetul de probă din difuzoare sau din căști."
        )
        exp.setFont(fonturi("baza"))
        exp.setWordWrap(True)
        seteaza_rol(exp, "secundar")
        layout.addWidget(exp)

        self._rand("microfon", "Microfonul", "Testează microfonul (5 secunde)", self._testeaza_microfon)
        self._rand("difuzor", "Difuzorul", "Testează difuzorul", self._testeaza_difuzor)
        self._rand("casti", "Căștile", "Testează căștile", self._testeaza_casti)

        layout.addStretch(1)

        self._timer_nivel = QTimer(self)
        self._timer_nivel.setInterval(60)
        self._timer_nivel.timeout.connect(self._actualizeaza_nivel)

        self._reimprospateaza()

    # ------------------------------------------------------------------ construcție

    def _rand(self, cheie: str, titlu: str, text_buton: str, comanda) -> None:
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(6)

        rand_titlu = QHBoxLayout()
        rand_titlu.setSpacing(10)
        et_titlu = QLabel(titlu)
        et_titlu.setFont(fonturi("buton"))
        rand_titlu.addWidget(et_titlu)
        et_dispozitiv = QLabel("")
        et_dispozitiv.setFont(fonturi("baza"))
        seteaza_rol(et_dispozitiv, "secundar")
        et_dispozitiv.setWordWrap(True)
        rand_titlu.addWidget(et_dispozitiv, 1)
        cl.addLayout(rand_titlu)

        et_stare = QLabel("●  Netestat")
        et_stare.setFont(fonturi("baza"))
        cl.addWidget(et_stare)

        if cheie == "microfon":
            bara = QProgressBar()
            bara.setObjectName("nivel")
            bara.setProperty("chunk", "verde")
            bara.setRange(0, 1000)
            bara.setValue(0)
            bara.setTextVisible(False)
            bara.setMaximumHeight(10)
            cl.addWidget(bara)
            self._bar_microfon = bara

        cl.addWidget(Buton(card, text_buton, comanda, latime=340, inaltime=38))

        self._randuri[cheie] = {"dispozitiv": et_dispozitiv, "stare": et_stare}
        self._layout.addWidget(card)

    def _reimprospateaza(self) -> None:
        microfoane = dispozitive.microfoane()
        iesiri = dispozitive.iesiri()
        casti = dispozitive.casti()
        difuzoare = [d for d in iesiri if d not in casti]

        self._microfon = microfoane[0] if microfoane else None
        self._difuzor = difuzoare[0] if difuzoare else (iesiri[0] if iesiri else None)
        self._casti = casti[0] if casti else None

        self._arata_dispozitiv("microfon", self._microfon)
        self._arata_dispozitiv("difuzor", self._difuzor)
        self._arata_dispozitiv("casti", self._casti)

    def _arata_dispozitiv(self, cheie: str, dispozitiv) -> None:
        rand = self._randuri[cheie]
        if dispozitiv is None:
            text = "Niciunul găsit."
        else:
            text = dispozitiv.descriere()
        rand["dispozitiv"].setText(text)

    def _arata_stare(self, cheie: str, stare: str) -> None:
        culori = {
            "merge": ("●  Merge", "verde"),
            "nu_merge": ("●  Nu merge", "pericol"),
            "lipseste": ("●  Lipsește", "atentie"),
        }
        text, rol = culori.get(stare, ("●  " + stare, "secundar"))
        self._randuri[cheie]["stare"].setText(text)
        seteaza_rol(self._randuri[cheie]["stare"], rol)

    # ------------------------------------------------------------------ microfon

    def _testeaza_microfon(self) -> None:
        if self._test_in_curs or self._microfon is None:
            if self._microfon is None:
                comun.anunta(self, "Microfon", "Nu am găsit niciun microfon pe acest calculator.")
            return
        self._test_in_curs = True
        self._arata_stare("microfon", "Ascult…")
        if self._timer_nivel is not None:
            self._timer_nivel.start()

        def lucru() -> None:
            microfon = inregistrare.Microfon(self._microfon)
            try:
                microfon.porneste()
            except Exception as exc:
                jurnal.atentionare(f"Proba microfonului nu a pornit: {exc}")
                self.coada.trimite(self._microfon_nu_merge, str(exc))
                return
            self._microfon_activ = microfon
            niveluri: list[float] = []
            try:
                for _ in range(SECUNDE_PROBA):
                    time.sleep(1.0)
                    if microfon.nivel is not None:
                        niveluri.append(float(microfon.nivel))
                inregistrat = microfon.opreste()
            except Exception as exc:
                jurnal.atentionare(f"Proba microfonului a eșuat: {exc}")
                inregistrat = None
            finally:
                self._microfon_activ = None
            self.coada.trimite(self._dupa_proba_microfon, inregistrat, max(niveluri) if niveluri else 0.0)

        threading.Thread(target=lucru, name="proba-microfon", daemon=True).start()

    def _actualizeaza_nivel(self) -> None:
        microfon = self._microfon_activ
        if microfon is None or self._bar_microfon is None:
            return
        nivel = int(min(1.0, max(0.0, getattr(microfon, "nivel", 0.0) or 0.0)) * 1000)
        self._bar_microfon.setValue(nivel)
        _, chunk = comun.text_nivel(nivel)
        if self._bar_microfon.property("chunk") != chunk:
            self._bar_microfon.setProperty("chunk", chunk)
            stil = self._bar_microfon.style()
            if stil is not None:
                stil.unpolish(self._bar_microfon)
                stil.polish(self._bar_microfon)

    def _microfon_nu_merge(self, detalii: str) -> None:
        if self._timer_nivel is not None:
            self._timer_nivel.stop()
        self._test_in_curs = False
        self._arata_stare("microfon", "nu_merge")
        comun.dialog_eroare(
            self,
            "Microfonul nu a putut fi pornit",
            detalii,
        )

    def _dupa_proba_microfon(self, inregistrat, nivel_maxim: float) -> None:
        if self._timer_nivel is not None:
            self._timer_nivel.stop()
        self._test_in_curs = False
        if inregistrat is None or nivel_maxim <= 0.0:
            self._arata_stare("microfon", "nu_merge")
            comun.anunta(
                self,
                "Microfonul nu aude",
                "În cele 5 secunde nu am primit niciun sunet de la microfon.\n\n"
                "Verifică dacă microfonul nu este astupat sau oprit, apoi încearcă din nou.",
            )
            return
        self._arata_stare("microfon", "merge")
        iesire = self._difuzor or self._casti
        try:
            inregistrare.reda(inregistrat, dispozitiv=iesire, asteapta=False)
        except Exception as exc:
            jurnal.atentionare(f"Redarea probei microfonului a eșuat: {exc}")

    # ------------------------------------------------------------------ difuzor / căști

    def _testeaza_difuzor(self) -> None:
        if self._difuzor is None:
            comun.anunta(self, "Difuzor", "Nu am găsit niciun difuzor pe acest calculator.")
            return
        self._reda_si_intreaba("difuzor", "stereo", self._difuzor,
                               "S-a auzit un sunet scurt, ca un clopoțel, din difuzor?")

    def _testeaza_casti(self) -> None:
        if self._casti is None:
            comun.anunta(self, "Căști", "Nu am găsit căști conectate la acest calculator.")
            return
        self._reda_si_intreaba("casti", "stanga", self._casti,
                               "S-a auzit un sunet scurt în casca din stânga?")

    def _reda_si_intreaba(self, cheie: str, unde: str, dispozitiv, intrebare: str) -> None:
        if self._test_in_curs:
            return
        self._test_in_curs = True
        self._arata_stare(cheie, "Se redă…")

        def lucru() -> None:
            try:
                inregistrare.reda_proba(unde, dispozitiv, asteapta=True)
            except Exception as exc:
                jurnal.atentionare(f"Redarea probei pentru {cheie} a eșuat: {exc}")
                self.coada.trimite(self._dupa_proba_fail, cheie)
                return
            self.coada.trimite(self._dupa_proba_redare, cheie, intrebare)

        threading.Thread(target=lucru, name=f"proba-{cheie}", daemon=True).start()

    def _dupa_proba_redare(self, cheie: str, intrebare: str) -> None:
        self._test_in_curs = False
        auzit = comun.intreaba(self, "Ai auzit sunetul?", intrebare)
        self._arata_stare(cheie, "merge" if auzit else "nu_merge")

    def _dupa_proba_fail(self, cheie: str) -> None:
        self._test_in_curs = False
        self._arata_stare(cheie, "nu_merge")