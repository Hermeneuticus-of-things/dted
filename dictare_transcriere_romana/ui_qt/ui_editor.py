"""Editor integrat PySide6: zona de text mare cu toolbar și linie de stare.

Înlocuiește ``ui_editor.py`` (Tkinter). Logica (undo, diacritice, căutare)
se păstrează; controlul este QTextEdit în locul tk.Text.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import comun
from .comun import Buton, fonturi


class Editor(QWidget):
    """Editor de text simplu, folosit pe ecranele de dictare/transcriere."""

    def __init__(self, parinte: QWidget, stare, la_actiune=None, inaltime=13):
        super().__init__(parinte)
        self.stare = stare
        self._la_actiune = la_actiune

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toolbar sus.
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)

        self.btn_anuleaza = Buton(self, "↶ Anulează (Ctrl+Z)", self._anuleaza, latime=120, inaltime=32)
        toolbar.addWidget(self.btn_anuleaza)

        self.btn_refac = Buton(self, "↷ Refă (Ctrl+Y)", self._refac, latime=100, inaltime=32)
        toolbar.addWidget(self.btn_refac)

        toolbar.addStretch(1)

        self.btn_copiază = Buton(self, "📋 Copiază tot", self._copiază_tot, latime=120, inaltime=32)
        toolbar.addWidget(self.btn_copiază)

        self.btn_caută = Buton(self, "🔍 Caută", self._caută, latime=100, inaltime=32)
        toolbar.addWidget(self.btn_caută)

        toolbar.addStretch(1)

        self.btn_mic = Buton(self, "A−", self._micșorează, latime=50, inaltime=32)
        toolbar.addWidget(self.btn_mic)

        self.btn_mare = Buton(self, "A+", self._mărește, latime=50, inaltime=32)
        toolbar.addWidget(self.btn_mare)

        layout.addLayout(toolbar)

        # Zona text (creată înainte, referită de scurtături).
        self._control = QPlainTextEdit()
        self._control.setObjectName("editor")
        self._control.setFont(fonturi("baza"))
        self._control.setPlaceholderText("Aici apare textul transcris sau scris de tine.")
        self._control.textChanged.connect(self._dupa_modificare)

        # Bară de căutare (ascunsă până la „🔍 Caută” / Ctrl+F), deasupra textului.
        self._bara_cautare = QLineEdit()
        self._bara_cautare.setPlaceholderText("Caută în text… (Enter = următorul, Esc = închide)")
        self._bara_cautare.setVisible(False)
        self._bara_cautare.textChanged.connect(self._găsește)
        self._bara_cautare.returnPressed.connect(self._găsește_următorul)
        layout.addWidget(self._bara_cautare)
        layout.addWidget(self._control, stretch=1)
        QShortcut(QKeySequence("Ctrl+F"), self._control, self._caută)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self._bara_cautare, self._inchide_cautare)

        self._diacritice_activ = False

        # Corecturile învățate: la 0,8 s după ce tastarea se oprește, comparăm
        # textul cu cel dinainte și reținem cuvintele rescrise de mână.
        self._text_ultim = self._control.toPlainText()
        self._timer_corecturi = QTimer(self)
        self._timer_corecturi.setSingleShot(True)
        self._timer_corecturi.setInterval(800)
        self._timer_corecturi.timeout.connect(self._invata_corecturi)

    def wheelEvent(self, eveniment) -> None:
        """Ctrl + rotița mouse-ului: scris mai mare sau mai mic (mai ușor decât butoanele)."""
        from PySide6.QtCore import Qt

        if eveniment.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if eveniment.angleDelta().y() > 0:
                self._mărește()
            else:
                self._micșorează()
            eveniment.accept()
            return
        super().wheelEvent(eveniment)

    def _dupa_modificare(self) -> None:
        self._timer_corecturi.start()
        if self._la_actiune:
            self._la_actiune()

    def _invata_corecturi(self) -> None:
        """Un cuvânt rescris de mână se salvează ca înlocuire pentru viitor."""
        from .. import inlocuiri

        curent = self._control.toPlainText()
        try:
            perechi = inlocuiri.diferente_cuvinte(self._text_ultim, curent)
        except Exception:
            perechi = []
        self._text_ultim = curent
        for gresit, corect in perechi:
            try:
                inlocuiri.adauga(gresit, corect)
            except Exception:
                pass

    def _toggle_diacritice(self) -> None:
        self._diacritice_activ = not self._diacritice_activ

    def _anuleaza(self) -> None:
        self._control.undo()

    def _refac(self) -> None:
        self._control.redo()

    def _copiază_tot(self) -> None:
        self._control.selectAll()
        self._control.copy()
        self._control.textCursor().clearSelection()

    def _caută(self) -> None:
        """Deschide/închide bara de căutare."""
        vizibil = self._bara_cautare.isVisible()
        self._bara_cautare.setVisible(not vizibil)
        if not vizibil:
            self._bara_cautare.setFocus()
            self._bara_cautare.selectAll()
        self._găsește()

    def _inchide_cautare(self) -> None:
        """Închide bara de căutare și golește selecția."""
        self._bara_cautare.clear()
        self._bara_cautare.setVisible(False)
        self._control.setFocus()

    def _găsește(self) -> None:
        """Caută textul din bara de căutare de la începutul textului."""
        text = self._bara_cautare.text()
        cursor = self._control.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self._control.setTextCursor(cursor)
        if text:
            self._control.find(text)

    def _găsește_următorul(self) -> None:
        """Trece la următoarea apariție; la capăt reia de la început."""
        text = self._bara_cautare.text()
        if not text:
            return
        if not self._control.find(text):
            cursor = self._control.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self._control.setTextCursor(cursor)
            self._control.find(text)

    def _micșorează(self) -> None:
        font = self._control.font()
        marime = max(8, font.pointSize() - 2)
        font.setPointSize(marime)
        self._control.setFont(font)

    def _mărește(self) -> None:
        font = self._control.font()
        marime = font.pointSize() + 2
        font.setPointSize(marime)
        self._control.setFont(font)

    def actualizeaza_etichete(self) -> None:
        """Actualizează etichetele butoanelor după schimbarea temei/fontului."""
        pass

    def actualizeaza_font(self) -> None:
        """Reîncarcă fontul după schimbarea mărimei scrisului (Ctrl+plus/minus)."""
        self._control.setFont(fonturi("baza"))

    def set_text(self, text: str) -> None:
        self._control.setPlainText(text)
        # Schimbarea integrală (text nou transcris) nu se învață ca „corecturi”.
        self._text_ultim = self._control.toPlainText()

    def insereaza(self, text: str, spatiu_auto: bool = True) -> None:
        """Inserează text la poziția cursorului, cu un singur pas de anulare (Ctrl+Z).

        Spre deosebire de ``set_text`` (care înlocuiește tot și resetează istoricul de
        anulare), aici textul se adaugă la cursor; un singur Ctrl+Z anulează toată
        inserția (un edit block). Când ``spatiu_auto`` e activ și cursorul nu e la
        început de rând și nu urmează deja un spațiu, se pune un spațiu înainte —
        folosit pentru fragmentele de dictare și semnele [mm:ss] (cerințele 37/48).
        """
        text = (text or "").strip()
        if not text:
            return
        cursor = self._control.textCursor()
        prefix = ""
        if spatiu_auto and not cursor.hasSelection() and not cursor.atBlockStart():
            temporar = QTextCursor(cursor)
            temporar.movePosition(
                QTextCursor.MoveOperation.PreviousCharacter,
                QTextCursor.MoveMode.KeepAnchor,
            )
            precedent = temporar.selectedText()
            if precedent and not precedent[-1].isspace():
                prefix = " "
        cursor.beginEditBlock()
        cursor.insertText(prefix + text)
        cursor.endEditBlock()
        self._control.setTextCursor(cursor)
        self._control.setFocus()

    def sari_la(self, text: str) -> None:
        """Du cursorul la prima apariție a textului (folosit la „Mergi la semn”)."""
        if not text:
            return
        cursor = self._control.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self._control.setTextCursor(cursor)
        self._control.find(text)
        self._control.setFocus()

    def cursor_pozitie(self) -> int:
        """Poziția cursorului în text (pentru redarea de la semnul de lângă el)."""
        return self._control.textCursor().position()

    def text(self) -> str:
        return self._control.toPlainText()

    def cuvinte(self) -> int:
        return len([c for c in self.text().split() if c])

    def focus(self) -> None:
        self._control.setFocus()
