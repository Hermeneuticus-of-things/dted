"""Ecranul „Fișierele mele” PySide6: sunete, texte transcrise și documente.

Înlocuiește ``ui_fisiere.py`` (Tkinter). Listează fișierele din folderele
programului pe trei file, cu acțiuni: deschide, arată în folder, redenumește,
mută la Coșul de reciclare (niciodată șters definitiv).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from PySide6.QtGui import QKeySequence, QShortcut
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
FILE: dict[str, str] = {
    "audio": "Sunete",
    "text": "Texte",
    "document": "Documente",
    "terminate": "Terminate",
}


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
        for fel in ("audio", "text", "document", "terminate"):
            btn = Buton(
                self,
                FILE[fel],
                lambda f=fel: self._alege_fila(f),
                fel="secundar",
                latime=150,
                inaltime=40,
            )
            self._butoane_file[fel] = btn
            rand_file.addWidget(btn)
        self.btn_importa = Buton(
            self,
            "Importă fișiere noi…",
            self._importa_fisiere_noi,
            latime=200,
            inaltime=40,
        )
        rand_file.addWidget(self.btn_importa)
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
        self.btn_deschide = Buton(self, "Deschide", self._deschide_selectat, fel="principal", latime=150, inaltime=40)
        self.btn_coada = Buton(self, "Transcrie / În coadă", self._trimite_in_coada, latime=190, inaltime=40)
        self.btn_folder = Buton(self, "Arată în folder", self._arata_in_folder, latime=180, inaltime=40)
        self.btn_redenum = Buton(self, "Redenumește (F2)", self._redenumeste, latime=180, inaltime=40)
        self.btn_gunoi = Buton(self, "Mută la Coș", self._la_gunoi, latime=160, inaltime=40)
        self.btn_arhiveaza = Buton(self, "Arhivează", self._arhiveaza, latime=160, inaltime=40)
        for buton in (
            self.btn_deschide,
            self.btn_coada,
            self.btn_folder,
            self.btn_redenum,
            self.btn_gunoi,
            self.btn_arhiveaza,
        ):
            rand_actiuni.addWidget(buton)
        rand_actiuni.addStretch(1)
        layout.addLayout(rand_actiuni)

        # Scurtătura F2 pentru redenumire (cerința 56).
        QShortcut(QKeySequence("F2"), self, self._redenumeste)

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
        el = self._selectat()
        are = el is not None
        for buton in (self.btn_deschide, self.btn_folder, self.btn_redenum, self.btn_gunoi):
            buton.setEnabled(are)
        self.btn_arhiveaza.setEnabled(are and self.fila != "terminate")
        self.btn_coada.setEnabled(are and (self.fila == "audio" or (el is not None and el.fel == "audio")))

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

    def _arhiveaza(self) -> None:
        """Cerință 41: Mută fișierul în arhiva „Terminate" (nu se șterge)."""
        el = self._selectat()
        if el is None:
            return
        intrebare = (
            f"Fișierul „{el.nume}” va fi mutat în arhiva „Terminate”.\n\n"
            "Arhiva stă separat de fișierele în lucru, ca să nu îngreuneze lista.\n\n"
            "Fișierul nu se șterge — îl găsești oricând în folderul „Terminate” "
            "din Documente\\Dictare&Transcriere Română.\n\nVrei să-l arhivezi acum?"
        )
        if not comun.intreaba(self, "Arhivează fișierul în „Terminate”?", intrebare):
            self.aplicatie.bara_stare.arata("Neschimbat", "fișierul a rămas unde era.", "normal")
            return
        reusit, mesaj = biblioteca.muta_la_terminate(el.cale)
        if not reusit:
            comun.anunta(
                self,
                "Fișierul nu a putut fi arhivat",
                mesaj or "Nu am putut muta fișierul în arhiva „Terminate”. Încearcă din nou.",
            )
            return
        self.aplicatie.bara_stare.arata("Arhivat", f"am mutat „{el.nume}” în arhiva „Terminate”.", "succes")
        self._reincarca()

    def _trimite_in_coada(self) -> None:
        """Cerința 35: Trimite fișierul audio ales în coada ecranului de transcriere."""
        el = self._selectat()
        if el is None:
            return
        biblioteca.uita_transcris(el.cale)
        self.aplicatie.arata_ecran("transcriere")
        pagina = self.aplicatie._ia_pagina("transcriere")
        if hasattr(pagina, "_primeste_fisiere"):
            pagina._primeste_fisiere([el.cale])

    def _importa_fisiere_noi(self) -> None:
        """Cerințele 35 și 47: Importă doar fișierele audio noi dintr-un folder local."""
        folder_ales = comun.alege_folder(
            self,
            "Alege folderul din care importăm fișierele audio noi",
            biblioteca.folder("audio"),
        )
        if not folder_ales:
            return
        importate, sarite = biblioteca.importa_audio_noi(folder_ales)
        if not importate:
            comun.anunta(
                self,
                "Niciun fișier nou",
                f"Nu am găsit fișiere audio noi în acel folder ({sarite} deja importate sau transcrise).",
            )
            return
        self._alege_fila("audio")
        self.aplicatie.bara_stare.arata(
            "Importat",
            f"am adus {len(importate)} fișier(e) noi ({sarite} sărite).",
            "succes",
        )
        if comun.intreaba(
            self,
            "Transcriem fișierele noi?",
            f"Am importat {len(importate)} fișier(e) audio noi"
            + (f" ({sarite} deja cunoscute au fost sărite)." if sarite else ".")
            + "\n\nVrei să le pun în coada de transcriere acum?",
        ):
            self.aplicatie.arata_ecran("transcriere")
            pagina = self.aplicatie._ia_pagina("transcriere")
            if hasattr(pagina, "_primeste_fisiere"):
                pagina._primeste_fisiere(importate)