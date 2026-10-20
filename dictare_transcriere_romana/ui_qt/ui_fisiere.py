"""Ecranul „Fișierele mele” PySide6: sunete, texte transcrise și documente.

Înlocuiește ``ui_fisiere.py`` (Tkinter). Listează fișierele din folderele
programului pe trei file, cu acțiuni: deschide, arată în folder, redenumește,
mută la Coșul de reciclare (niciodată șters definitiv).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import biblioteca, sisteme
from . import comun
from .comun import Buton, fonturi, seteaza_rol

#: Titlurile filelor, pe felul de fișier.
FILE: dict[str, str] = {"audio": "Sunete", "text": "Texte", "document": "Documente"}


class FereastraFisiere(QWidget):
    """Fișierele create de program, cu acțiuni pe viitorul document ales."""

    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie
        self.fila = "audio"
        self._elemente: list[biblioteca.Element] = []
        self._butoane_file: dict[str, Buton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        titlu = QLabel("Fișierele mele")
        titlu.setFont(fonturi("titlu"))
        layout.addWidget(titlu)

        exp = QLabel(
            "Aici sunt sunetele, textele transcrise și documentele finale. Alege o filă, "
            "apoi ce vrei să faci cu fișierul ales."
        )
        exp.setFont(fonturi("baza"))
        exp.setWordWrap(True)
        seteaza_rol(exp, "secundar")
        layout.addWidget(exp)

        rand_file = QHBoxLayout()
        rand_file.setSpacing(8)
        for fel in ("audio", "text", "document"):
            btn = Buton(
                self,
                FILE[fel],
                lambda f=fel: self._alege_fila(f),
                fel="secundar",
                latime=160,
                inaltime=40,
            )
            self._butoane_file[fel] = btn
            rand_file.addWidget(btn)
        rand_file.addStretch(1)
        layout.addLayout(rand_file)

        self.lista = QListWidget()
        self.lista.setObjectName("lista")
        self.lista.setMinimumHeight(160)
        self.lista.itemSelectionChanged.connect(self._actualizeaza_butoane)
        self.lista.itemDoubleClicked.connect(lambda _: self._deschide_selectat())
        layout.addWidget(self.lista, stretch=1)

        rand_actiuni = QHBoxLayout()
        rand_actiuni.setSpacing(8)
        self.btn_deschide = Buton(self, "Deschide", self._deschide_selectat, fel="principal", latime=170, inaltime=40)
        self.btn_folder = Buton(self, "Arată în folder", self._arata_in_folder, latime=200, inaltime=40)
        self.btn_redenum = Buton(self, "Redenumește", self._redenumeste, latime=170, inaltime=40)
        self.btn_gunoi = Buton(self, "Mută la Coș", self._la_gunoi, latime=180, inaltime=40)
        for buton in (self.btn_deschide, self.btn_folder, self.btn_redenum, self.btn_gunoi):
            rand_actiuni.addWidget(buton)
        rand_actiuni.addStretch(1)
        layout.addLayout(rand_actiuni)

        self._alege_fila("audio")

    # ------------------------------------------------------------------ listă

    def _alege_fila(self, fel: str) -> None:
        self.fila = fel
        for cod, buton in self._butoane_file.items():
            buton._fel = "principal" if cod == fel else "secundar"
            buton._aplica_stil()
        self._reincarca()

    def _reincarca(self) -> None:
        self.lista.clear()
        self._elemente = biblioteca.listeaza(self.fila)
        for el in self._elemente:
            self.lista.addItem(QListWidgetItem(self._text_element(el)))
        if not self._elemente:
            gol = QListWidgetItem("Niciun fișier în această categorie încă.")
            gol.setFlags(gol.flags() & ~gol.flags().ItemIsSelectable)
            self.lista.addItem(gol)
        self._actualizeaza_butoane()

    def _text_element(self, el: biblioteca.Element) -> str:
        data = dt.datetime.strftime(el.data, "%d.%m.%Y %H:%M") if el.data else "dată necunoscută"
        detalii = (el.detalii or "").strip()
        parti = [el.nume, data]
        if self.fila == "audio":
            parti.append(f"durată: {detalii}" if detalii else "durată necitită")
        elif detalii:
            parti.append(f"mărime: {detalii}")
        return "   ·   ".join(parti)

    def _selectat(self) -> biblioteca.Element | None:
        rand = self.lista.currentRow()
        if 0 <= rand < len(self._elemente):
            return self._elemente[rand]
        return None

    def _actualizeaza_butoane(self) -> None:
        are = self._selectat() is not None
        for buton in (self.btn_deschide, self.btn_folder, self.btn_redenum, self.btn_gunoi):
            buton.setEnabled(are)

    # ------------------------------------------------------------------ acțiuni

    def _deschide_selectat(self) -> None:
        el = self._selectat()
        if el is None:
            return
        if self.fila == "audio":
            if sisteme.deschide_fisier(el.cale):
                self.aplicatie.bara_stare.arata(
                    "Deschis", f"am deschis „{el.nume}” cu programul potrivit.", "lucru"
                )
            else:
                comun.anunta(
                    self,
                    "Fișierul nu s-a deschis",
                    f"Nu am putut deschide „{el.nume}”.\n\n"
                    "Probabil fișierul a fost mutat sau șters între timp.\n\n"
                    "Apasă „Arată în folder” ca să vezi fișierul și deschide-l cu dublu-clic.",
                )
            return
        if self.fila == "document":
            reusit = False
            try:
                reusit = self.aplicatie._deschide_in_libreoffice(el.cale)
            except Exception:
                reusit = False
            if not reusit and not sisteme.deschide_fisier(el.cale):
                comun.anunta(
                    self,
                    "Documentul nu s-a deschis",
                    f"Nu am găsit niciun program care să deschidă „{el.nume}”.\n\n"
                    "Apasă „Arată în folder” și deschide-l cu dublu-clic.",
                )
            return
        # text → în editorul integrat
        self.aplicatie._deschide_document_ales(el.cale)

    def _arata_in_folder(self) -> None:
        el = self._selectat()
        if el is None:
            return
        if not sisteme.deschide_folder(el.cale.parent):
            comun.anunta(
                self,
                "Folderul nu s-a deschis",
                "Windows nu a putut deschide folderul acum.\n\nÎncearcă din nou peste o clipă.",
            )

    def _redenumeste(self) -> None:
        el = self._selectat()
        if el is None:
            return
        nume_nou, ok = QInputDialog.getText(
            self, "Redenumește fișierul", "Nume nou:", text=el.nume
        )
        if not ok or not (nume_nou or "").strip():
            return
        cale_noua, mesaj = biblioteca.redenumeste(el.cale, nume_nou.strip())
        if cale_noua is None:
            comun.anunta(self, "Numele nu s-a putut schimba", mesaj or "Numele nu a putut fi schimbat.")
            return
        self.aplicatie.bara_stare.arata("Redenumit", f"fișierul se numește acum „{cale_noua.name}”.", "succes")
        self._reincarca()

    def _la_gunoi(self) -> None:
        el = self._selectat()
        if el is None:
            return
        intrebare = (
            f"Fișierul „{el.nume}” ajunge în Coșul de reciclare.\n\n"
            "Nu se șterge definitiv: îl poți readuce oricând din Coșul de reciclare, "
            "dacă te răzgândești.\n\nVrei să îl muți acum?"
        )
        if not comun.intreaba(self, "Muți fișierul la Coșul de reciclare?", intrebare):
            self.aplicatie.bara_stare.arata("Neschimbat", "fișierul a rămas unde era.", "normal")
            return
        reusit, mesaj = biblioteca.la_gunoi(el.cale)
        if not reusit:
            comun.anunta(
                self,
                "Fișierul nu a ajuns la Coșul de reciclare",
                mesaj or "Windows nu a putut muta fișierul. Încearcă din nou.",
            )
            return
        self.aplicatie.bara_stare.arata("Șters", "am mutat fișierul la Coșul de reciclare.", "atentie")
        self._reincarca()