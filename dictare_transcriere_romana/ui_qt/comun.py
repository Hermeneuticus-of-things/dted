"""Fundația interfeței PySide6: culori, fonturi, butoane, dialoguri, scalare.

Înlocuiește ``ui_comun.py`` (Tkinter). Aici sunt:

* **Culori** — perechi verificate cu contrast WCAG, teme luminos / întunecat / Windows.
* **Buton** — QPushButton cu stil standard, înălțime ~32 px, text 10 puncte (ca Windows).
* **Etichetă, Card, BaraStare, ZonaDerulare** — componente de bază.
* **Dialoguri** — QDialog cu butoane în română, eroare cu 3 părți (ce / ce fac / detalii).
* **CoadaUI** — actualizări fire-safe din fire de fundal (pyqtSignal + invokeMethod).
* **Scalare** — Qt se ocupă singur de DPI; nu avem calcule manuale de pixeli.
"""

from __future__ import annotations

import datetime as dt
import os
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    QObject,
    QPoint,
    QSize,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSizePolicy,
    QStyleFactory,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..constante import NUME_APLICATIE

# --------------------------------------------------------------------------- culori


@dataclass
class Culori:
    """Culorile programului (fiecare pereche are contrast suficient)."""

    fundal: str = "#FFFFFF"
    card: str = "#F5F7FA"
    text: str = "#1A1A1A"
    text_secundar: str = "#555555"
    principal: str = "#2563EB"
    principal_text: str = "#FFFFFF"
    verde_fundal: str = "#DCFCE7"
    verde_text: str = "#166534"
    galben_fundal: str = "#FEF9C3"
    galben_text: str = "#713F12"
    rosu_fundal: str = "#FEE2E2"
    rosu_text: str = "#991B1B"
    dezactivat_fundal: str = "#E5E7EB"
    dezactivat_text: str = "#9CA3AF"
    chenar: str = "#D1D5DB"
    chenar_focus: str = "#2563EB"
    pericol: str = "#DC2626"
    pericol_text: str = "#FFFFFF"
    succes: str = "#15803D"
    succes_text: str = "#FFFFFF"
    # Culori pentru TEXT/iconițe „principal”/„pericol”/„succes” pe fundal normal
    # (unu/doi), nu pe butoane. Pe tema întunecată sunt mai deschise decât
    # fundalurile de buton, ca textul să aibă contrast >= 4,5:1 pe fundal.
    principal_accent: str = "#2563EB"
    # „pericol” ca text (nu buton): roșu puțin mai închis, ca pe cardul deschis
    # (#F5F7FA) contrastul să rămână peste 4,5:1 (cerința de accesibilitate).
    pericol_accent: str = "#B91C1C"
    succes_accent: str = "#15803D"

    def copiaza_din(self, alta: "Culori") -> None:
        """Împrumută valorile dintr-o altă instanță, păstrând același obiect.

        Modulele care fac ``from .comun import CULORI`` țin referința la obiectul
        de la import; realocarea unui obiect nou i-ar lăsa cu valori vechi.
        """
        for camp in Culori.__dataclass_fields__:  # type: ignore[attr-defined]
            setattr(self, camp, getattr(alta, camp))


# Tema întunecată (valorile inversate, suficient de contrastate).
_TEMA_INTUNECATA = Culori(
    fundal="#1F2937",
    card="#374151",
    text="#F9FAFB",
    text_secundar="#D1D5DB",
    principal="#2563EB",
    principal_text="#FFFFFF",
    verde_fundal="#064E3B",
    verde_text="#86EFAC",
    galben_fundal="#713F12",
    galben_text="#FEF3C7",
    rosu_fundal="#7F1D1D",
    rosu_text="#FECACA",
    dezactivat_fundal="#4B5563",
    dezactivat_text="#9CA3AF",
    chenar="#4B5563",
    chenar_focus="#60A5FA",
    pericol="#DC2626",
    pericol_text="#FFFFFF",
    succes="#15803D",
    succes_text="#FFFFFF",
    principal_accent="#93C5FD",
    pericol_accent="#FCA5A5",
    succes_accent="#86EFAC",
)

CULORI = Culori()
_MOD_APLICAT = "luminos"


def citeste_tema_windows() -> str:
    """Citește din Windows dacă e pe luminos sau întunecat (fallback: luminos)."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as cheie:
            valoare, _ = winreg.QueryValueEx(cheie, "AppsUseLightTheme")
        return "luminos" if int(valoare) else "intunecat"
    except Exception:
        return "luminos"


def mod_efectiv(mod: str = "") -> str:
    ales = (mod or "windows").lower()
    if ales == "intunecat":
        return "intunecat"
    if ales == "luminos":
        return "luminos"
    return citeste_tema_windows()


def aplica_tema(mod: str = "windows") -> str:
    """Aplică culorile modului cerut pe aplicația curentă (QApplication)."""
    global CULORI, _MOD_APLICAT
    dorit = mod_efectiv(mod)
    sursa = _TEMA_INTUNECATA if dorit == "intunecat" else Culori()
    # Actualizăm obiectul existent, nu îl realocăm: alte module păstrează
    # referința la ``CULORI`` de la import, iar realocarea i-ar lăsa stricați.
    CULORI.copiaza_din(sursa)
    _MOD_APLICAT = dorit
    _aplica_paleta_globala()
    _aplica_qss_central()
    return dorit


def paleta_din_culori(c: Culori) -> QPalette:
    """Construiește o paletă QPalette completă și explicită din Culori.

    Acoperă toate rolurile cerute: Window, WindowText, Base, AlternateBase,
    Text, Button, ButtonText, Highlight, HighlightedText, ToolTipBase,
    ToolTipText, PlaceholderText, plus starea Disabled.
    """
    paleta = QPalette()
    intrari = {
        QPalette.ColorRole.Window: c.fundal,
        QPalette.ColorRole.WindowText: c.text,
        QPalette.ColorRole.Base: c.fundal,
        QPalette.ColorRole.AlternateBase: c.card,
        QPalette.ColorRole.Text: c.text,
        QPalette.ColorRole.Button: c.card,
        QPalette.ColorRole.ButtonText: c.text,
        QPalette.ColorRole.Highlight: c.principal,
        QPalette.ColorRole.HighlightedText: c.principal_text,
        QPalette.ColorRole.ToolTipBase: c.card,
        QPalette.ColorRole.ToolTipText: c.text,
        QPalette.ColorRole.PlaceholderText: c.text_secundar,
        QPalette.ColorRole.BrightText: c.text,
        QPalette.ColorRole.Link: c.principal,
    }
    for rol, culoare in intrari.items():
        paleta.setColor(QPalette.ColorGroup.Normal, rol, QColor(culoare))
        paleta.setColor(QPalette.ColorGroup.Active, rol, QColor(culoare))
        paleta.setColor(QPalette.ColorGroup.Inactive, rol, QColor(culoare))
    # Starea dezactivată: text estompat, fundal dezactivat, dar încă lizibil.
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(c.dezactivat_text))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c.dezactivat_text))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(c.dezactivat_text))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor(c.dezactivat_fundal))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor(c.dezactivat_fundal))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, QColor(c.fundal))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(c.dezactivat_fundal))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(c.dezactivat_text))
    return paleta


def _aplica_paleta_globala() -> None:
    """Pune stilul Fusion și paleta completă pe aplicația curentă."""
    aplicatie = QApplication.instance()
    if aplicatie is None:
        return
    try:
        stil = QStyleFactory.create("Fusion")
        if stil is not None:
            aplicatie.setStyle(stil)
    except Exception:
        pass
    aplicatie.setPalette(paleta_din_culori(CULORI))


def _aplica_qss_central() -> None:
    """Pune un singur QSS central, derivat din CULORI, pe aplicația curentă.

    Toate culorile interfeței vin de aici; modulele nu mai lipesc culori în
    ``setStyleSheet``. La schimbarea temei, Qt restilizează automat widgeturile
    care n-au stil propriu, deci totul se recolorează dintr-o singură sursă.
    """
    aplicatie = QApplication.instance()
    if aplicatie is None:
        return
    c = CULORI
    principal_hover = _luminozitate(c.principal, -0.12)
    principal_apasat = _luminozitate(c.principal, -0.22)
    pericol_hover = _luminozitate(c.pericol, -0.12)
    succes_hover = _luminozitate(c.succes, -0.12)
    aplicatie.setStyleSheet(
        f"""
        QWidget {{
            color: {c.text};
        }}
        QLabel {{
            background: transparent;
        }}
        QLabel[rol="secundar"] {{ color: {c.text_secundar}; }}
        QLabel[rol="succes"] {{ color: {c.succes_accent}; }}
        QLabel[rol="pericol"] {{ color: {c.pericol_accent}; }}
        QLabel[rol="rosu"] {{ color: {c.rosu_text}; }}
        QLabel[rol="verde"] {{ color: {c.verde_text}; }}
        QLabel[rol="atentie"] {{ color: {c.galben_text}; }}
        QLabel[rol="principal"] {{ color: {c.principal_accent}; }}
        QLabel[rol="titlu"] {{ font-weight: bold; }}
        QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox, QListWidget {{
            background-color: {c.fundal};
            color: {c.text};
            border: 1px solid {c.chenar};
            border-radius: 4px;
            padding: 3px;
        }}
        QPlainTextEdit#editor, QTextEdit#editor {{
            border-radius: 6px;
            padding: 8px;
            selection-background-color: {c.principal};
            selection-color: {c.principal_text};
        }}
        QComboBox QAbstractItemView, QListWidget {{
            background-color: {c.fundal};
            color: {c.text};
            selection-background-color: {c.principal};
            selection-color: {c.principal_text};
        }}
        QMenu {{
            background-color: {c.fundal};
            color: {c.text};
            border: 1px solid {c.chenar};
        }}
        QMenu::item:selected {{
            background-color: {c.principal};
            color: {c.principal_text};
        }}
        QCheckBox, QRadioButton {{
            color: {c.text};
        }}
        QMessageBox, QDialog {{
            background-color: {c.fundal};
        }}
        QToolTip {{
            background-color: {c.card};
            color: {c.text};
            border: 1px solid {c.chenar};
        }}
        QToolBar#toolbar {{
            background-color: {c.card};
            border-bottom: 1px solid {c.chenar};
            spacing: 6px;
            padding: 4px;
        }}
        QToolBar#toolbar QToolButton {{
            background-color: transparent;
            color: {c.text};
            border: 1px solid transparent;
            border-radius: 6px;
            padding: 4px 10px;
            min-height: 40px;
            min-width: 90px;
        }}
        QToolBar#toolbar QToolButton:hover {{
            background-color: {c.dezactivat_fundal};
            border-color: {c.chenar};
        }}
        QToolBar#toolbar QToolButton:pressed {{
            background-color: {c.chenar_focus};
        }}
        QToolBar#toolbar QToolButton::menu-indicator {{
            image: none;
        }}
        QToolBar#toolbar QToolButton#btn_dictare {{
            background-color: {c.principal};
            color: {c.principal_text};
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 6px 18px;
            min-height: 44px;
            min-width: 150px;
            font-weight: bold;
            font-size: 11pt;
        }}
        QToolBar#toolbar QToolButton#btn_dictare:hover {{
            background-color: {principal_hover};
        }}
        QToolBar#toolbar QToolButton#btn_dictare:pressed {{
            background-color: {principal_apasat};
        }}
        QToolBar#toolbar QToolButton#btn_dictare[dictare="true"] {{
            background-color: {c.pericol};
            color: {c.pericol_text};
        }}
        QLabel#vumetru_text {{
            min-width: 90px;
            color: {c.text_secundar};
        }}
        QFrame#jos {{
            background-color: {c.card};
            border-top: 1px solid {c.chenar};
        }}
        QFrame#card {{
            background-color: {c.card};
            border: 1px solid {c.chenar};
            border-radius: 8px;
        }}
        QWidget#indicator {{
            background-color: {c.card};
            border: 1px solid {c.chenar};
            border-radius: 6px;
        }}
        QFrame#rand-cale {{
            background-color: {c.card};
            border: 1px solid {c.chenar};
            border-radius: 6px;
        }}
        QFrame#rand-cale[stare="ok"] {{
            background-color: {c.verde_fundal};
        }}
        QFrame#rand-cale[stare="pericol"] {{
            background-color: {c.rosu_fundal};
        }}
        QFrame#card-cale {{
            background-color: {c.card};
            border: 1px solid {c.chenar};
            border-radius: 6px;
        }}
        QFrame#drop {{
            background-color: {c.galben_fundal};
            border: 2px dashed {c.galben_text};
            border-radius: 8px;
        }}
        QFrame#drop[stare="verde"] {{
            background-color: {c.verde_fundal};
            border: 2px solid {c.verde_text};
        }}
        QFrame#zona-finala {{
            background-color: {c.verde_fundal};
            border-radius: 8px;
        }}
        QFrame#cardClickabil:hover {{
            border-color: {c.principal};
        }}
        QProgressBar#progres {{
            border: 1px solid {c.chenar};
            border-radius: 4px;
            text-align: center;
            height: 22px;
        }}
        QProgressBar#progres::chunk {{
            background-color: {c.principal};
            border-radius: 3px;
        }}
        QProgressBar#nivel {{
            border: 1px solid {c.chenar};
            border-radius: 5px;
            background: {c.dezactivat_fundal};
        }}
        QProgressBar#nivel::chunk {{
            border-radius: 4px;
        }}
        QProgressBar#nivel[chunk="verde"]::chunk {{
            background-color: {c.verde_text};
        }}
        QProgressBar#nivel[chunk="galben"]::chunk {{
            background-color: {c.galben_text};
        }}
        QProgressBar#nivel[chunk="rosu"]::chunk {{
            background-color: {c.pericol};
        }}
        QProgressBar#nivel[sus="true"] {{
            min-height: 16px;
            height: 16px;
        }}
        QPushButton {{
            background-color: {c.card};
            color: {c.text};
            border: none;
            border-radius: 6px;
            padding: 4px 12px;
        }}
        QPushButton:hover {{ background-color: {c.dezactivat_fundal}; }}
        QPushButton:pressed {{ background-color: {c.chenar}; }}
        QPushButton:disabled {{
            background-color: {c.dezactivat_fundal};
            color: {c.dezactivat_text};
        }}
        QPushButton[fel="principal"] {{
            background-color: {c.principal};
            color: {c.principal_text};
        }}
        QPushButton[fel="principal"]:hover {{ background-color: {principal_hover}; }}
        QPushButton[fel="principal"]:pressed {{ background-color: {principal_apasat}; }}
        QPushButton[fel="pericol"] {{
            background-color: {c.pericol};
            color: {c.pericol_text};
        }}
        QPushButton[fel="pericol"]:hover {{ background-color: {pericol_hover}; }}
        QPushButton[fel="succes"] {{
            background-color: {c.succes};
            color: {c.succes_text};
        }}
        QPushButton[fel="succes"]:hover {{ background-color: {succes_hover}; }}
        QScrollBar:vertical {{
            background: {c.dezactivat_fundal};
            width: 12px;
        }}
        QScrollBar::handle:vertical {{
            background: {c.chenar};
            min-height: 20px;
        }}
        QScrollBar:horizontal {{
            background: {c.dezactivat_fundal};
            height: 12px;
        }}
        QScrollBar::handle:horizontal {{
            background: {c.chenar};
            min-width: 20px;
        }}
        """
    )


def mod_aplicat() -> str:
    return _MOD_APLICAT


# --------------------------------------------------------------------------- fonturi


_FONTURI: dict[str, QFont] = {}


def pregateste_fonturi(fereastra: QWidget | None = None) -> None:
    """Încarcă fonturile de bază (Segoe UI, 10 puncte la 100%)."""
    baza = QFont("Segoe UI", 10)
    mica = QFont("Segoe UI", 9)
    buton = QFont("Segoe UI", 10)
    titlu = QFont("Segoe UI", 14, QFont.Weight.Bold)
    _FONTURI.update({"baza": baza, "mica": mica, "buton": buton, "titlu": titlu})


def fonturi(tip: str = "baza") -> QFont:
    return _FONTURI.get(tip, QFont("Segoe UI", 10))


def mareste_scris(factor: float) -> None:
    """Mărește toate fonturile cu un factor (pentru Ctrl+plus/minus)."""
    for tip, font in _FONTURI.items():
        marime = max(8, int(round(font.pointSize() * factor)))
        font.setPointSize(marime)


# --------------------------------------------------------------------------- componente


def eticheta(
    parinte: QWidget,
    text: str,
    stil: str = "baza",
    fundal: str | None = None,
    aliniare: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
) -> QLabel:
    """Etichetă cu text, aliniere și stil de font (culorile vin din QSS-ul central)."""
    if not isinstance(parinte, QWidget):
        parinte = None  # un layout nu poate fi părinte; eticheta intră în layout la addWidget
    lbl = QLabel(text, parinte)
    lbl.setFont(fonturi(stil))
    lbl.setAlignment(aliniare)
    lbl.setWordWrap(True)
    return lbl


class Buton(QPushButton):
    """Buton standard Qt, înălțime aproximativ 32 px, text 10 puncte.

    Înlocuiește butonul desenat pe Canvas din ui_comun.py. Stilul vine din
    QSS-ul central (după proprietatea ``fel``), ca tema să se poată schimba.
    """

    def __init__(
        self,
        parinte: QWidget,
        text: str,
        comanda: Callable | None = None,
        fel: str = "secundar",
        latime: int | None = None,
        inaltime: int | None = 32,
        scurtatura: str = "",
        imagine=None,
    ):
        super().__init__(text, parinte)
        if scurtatura:
            self.setText(f"{text} ({scurtatura})")
        if comanda is not None:
            self.clicked.connect(comanda)
        self._fel = fel
        self.setProperty("fel", fel)
        self.setMinimumHeight(inaltime or 32)
        if latime is not None:
            self.setMinimumWidth(latime)
        self.setFont(fonturi("buton"))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._aplica_stil()

    def _aplica_stil(self) -> None:
        # Culorile vin din QSS-ul central; aici doar reîmprospătăm stilul.
        self.style().unpolish(self)
        self.style().polish(self)

    def set_activ(self, activ: bool) -> None:
        self.setEnabled(activ)
        self._aplica_stil()

    def set_text(self, text: str) -> None:
        """Schimbă textul butonului, pătrunzând scurtătura dacă există."""
        curent = self.text()
        if " (" in curent:
            scurt = curent[curent.index(" ("):]
            self.setText(f"{text}{scurt}")
        else:
            self.setText(text)


def _luminozitate(hex_culoare: str, factor: float) -> str:
    """Îndreaptă o culoare hex cu un factor (-1..1)."""
    hex_culoare = hex_culoare.lstrip("#")
    r = int(hex_culoare[0:2], 16)
    g = int(hex_culoare[2:4], 16)
    b = int(hex_culoare[4:6], 16)
    r = max(0, min(255, int(r * (1 + factor))))
    g = max(0, min(255, int(g * (1 + factor))))
    b = max(0, min(255, int(b * (1 + factor))))
    return f"#{r:02x}{g:02x}{b:02x}"


class Card(QFrame):
    """Cadru cu colțuri rotunjite și chenar subtil (stil din QSS-ul central)."""

    def __init__(self, parinte: QWidget | None = None, fundal: str | None = None):
        super().__init__(parinte)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)


def seteaza_rol(widget: QWidget, rol: str) -> None:
    """Setează rolul de culoare al unui widget (QSS-ul central îl colorează)."""
    widget.setProperty("rol", rol)
    stil = widget.style()
    if stil is not None:
        stil.unpolish(widget)
        stil.polish(widget)


def text_nivel(nivel_0_1000: int) -> tuple[str, str]:
    """Întoarce (text, chunk) pentru vumetrul microfonului (cerința 36 / D-6).

    Nivelul e un număr 0..1000. „chunk” e una din „verde”/„galben”/„rosu”,
    folosită de QSS-ul central (``QProgressBar#nivel[chunk=...]``).
    """
    if nivel_0_1000 < 40:
        return "Doar zgomot", "verde"
    if nivel_0_1000 < 300:
        return "Prea încet", "verde"
    if nivel_0_1000 < 760:
        return "Te aud", "verde"
    if nivel_0_1000 < 900:
        return "Prea tare", "galben"
    return "Prea tare", "rosu"


class BaraStare(QWidget):
    """Linia de stare jos: semn (pictogramă + cuvânt) + mesaj."""

    def __init__(self, parinte: QWidget | None = None):
        super().__init__(parinte)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        self._semn = QLabel("ℹ")
        self._semn.setFont(fonturi("baza"))
        self._mesaj = QLabel("")
        self._mesaj.setFont(fonturi("mica"))
        seteaza_rol(self._mesaj, "secundar")

        layout.addWidget(self._semn)
        layout.addWidget(self._mesaj, stretch=1)

    def arata(self, semn: str, mesaj: str, fel: str = "normal") -> None:
        roluri_semn = {
            "normal": "text",
            "atentie": "atentie",
            "pericol": "pericol",
            "succes": "succes",
            "lucru": "principal",
        }
        roluri_mesaj = {
            "normal": "secundar",
            "atentie": "atentie",
            "pericol": "pericol",
            "succes": "succes",
            "lucru": "principal",
        }
        self._semn.setText(semn)
        seteaza_rol(self._semn, roluri_semn.get(fel, "text"))
        self._mesaj.setText(mesaj)
        seteaza_rol(self._mesaj, roluri_mesaj.get(fel, "secundar"))


class ZonaDerulare(QScrollArea):
    """Zona cu derulare (scroll), echivalentul Tkinter scrollable frame."""

    def __init__(self, parinte: QWidget | None = None, latime_minima: int = 0):
        super().__init__(parinte)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.interior = QWidget()
        self.interior.setLayout(QVBoxLayout())
        self.interior.layout().setContentsMargins(0, 0, 0, 0)
        self.interior.layout().setSpacing(8)
        self.setWidget(self.interior)
        if latime_minima > 0:
            self.interior.setMinimumWidth(latime_minima)


class BaraProgres(QProgressBar):
    """Bara de progres simplă (stil din QSS-ul central)."""

    def __init__(self, parinte: QWidget | None = None):
        super().__init__(parinte)
        self.setObjectName("progres")
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(True)

    def seteaza(self, fractiune: float, mesaj: str = "") -> None:
        self.setValue(int(max(0.0, min(1.0, fractiune)) * 100))
        if mesaj:
            self.setFormat(mesaj)

    def gata(self, mesaj: str = "Gata.") -> None:
        self.setValue(100)
        self.setFormat(mesaj)

    def reseteaza(self) -> None:
        self.setValue(0)
        self.setFormat("")


# --------------------------------------------------------------------------- coadă UI (fire-safe)


class CoadaUI(QObject):
    """Trimite actualizări din fire de fundal în firul interfeței (pyqtSignal).

    Înlocuiește coada Tkinter (after + queue). Lucrătorii pune funcții în coadă;
    fereastra le execulează în ritmul propriu (la fiecare 60 ms).
    """

    ruleaza_in_fir = Signal(object, object, object)  # functie, args, kwargs

    def __init__(self, fereastra: QObject, interval: int = 60):
        super().__init__(fereastra)
        self.coada: queue.Queue = queue.Queue()
        self.interval = interval
        self._oprit = threading.Event()
        self._timer = QTimer(fereastra)
        self._timer.timeout.connect(self._goleste)
        self._timer.start(interval)

    def _goleste(self) -> None:
        while True:
            try:
                functie, argumente, numite = self.coada.get_nowait()
            except queue.Empty:
                break
            try:
                functie(*argumente, **numite)
            except Exception as exc:  # nicio eroare din interfață nu închide programul
                from .. import jurnal

                jurnal.eroare(f"Eroare în interfață: {type(exc).__name__}: {exc}")

    def trimite(self, functie, *argumente, **numite) -> None:
        """Cere ca funcția să fie rulată în firul interfeței."""
        self.coada.put((functie, argumente, numite))

    def opreste(self) -> None:
        self._oprit.set()
        self._timer.stop()


# --------------------------------------------------------------------------- dialoguri


class _Dialog(QDialog):
    """Dialog personalizat cu butoane în română."""

    def __init__(
        self,
        parinte: QWidget,
        titlu: str,
        mesaj: str,
        butoane: list[tuple[str, str]],
        implicit: int = 0,
        anulare: int | None = None,
        detalii: str = "",
    ):
        super().__init__(parinte)
        self.setWindowTitle(titlu)
        self.setMinimumWidth(420)
        self._rezultat = implicit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        et = QLabel(mesaj)
        et.setFont(fonturi("baza"))
        et.setWordWrap(True)
        layout.addWidget(et)

        if detalii:
            det = QTextEdit(detalii)
            det.setObjectName("detalii")
            det.setReadOnly(True)
            det.setMaximumHeight(120)
            det.setFont(fonturi("mica"))
            layout.addWidget(det)

        box = QDialogButtonBox()
        for i, (text, stil) in enumerate(butoane):
            btn = Buton(self, text, fel=stil)
            if i == implicit:
                btn.setDefault(True)
            box.addButton(
                btn,
                QDialogButtonBox.ButtonRole.AcceptRole
                if stil in ("principal", "succes")
                else QDialogButtonBox.ButtonRole.RejectRole,
            )
            btn.clicked.connect(lambda _, idx=i: self._apasa(idx))
        layout.addWidget(box)

    def _apasa(self, index: int) -> None:
        self._rezultat = index
        self.accept()

    def rezultat(self) -> int:
        return self._rezultat


def dialog(
    parinte: QWidget,
    titlu: str,
    mesaj: str,
    butoane: list[tuple[str, str]],
    implicit: int = 0,
    anulare: int | None = None,
    detalii: str = "",
) -> int:
    """Dialog cu butoane personalizate. Returnează indexul butonului apasat."""
    dlg = _Dialog(parinte, titlu, mesaj, butoane, implicit, anulare, detalii)
    dlg.exec()
    return dlg.rezultat()


def intreaba(
    parinte: QWidget,
    titlu: str,
    mesaj: str,
    da_nu: bool = True,
) -> bool:
    """Întrebare Da/Nu. Returnează True pentru Da."""
    butoane = [("Da", "principal"), ("Nu", "secundar")] if da_nu else [("OK", "principal")]
    rezultat = dialog(parinte, titlu, mesaj, butoane, implicit=0, anulare=1 if da_nu else 0)
    return rezultat == 0


def anunta(parinte: QWidget, titlu: str, mesaj: str) -> None:
    """Notificare simplă cu buton OK."""
    dialog(parinte, titlu, mesaj, [("OK", "principal")], implicit=0)


def dialog_eroare(
    parinte: QWidget,
    titlu: str,
    eroare,
    detalii: str = "",
) -> None:
    """Eroare în 3 părți: ce s-a întâmplat, ce trebuie facut, detalii tehnice."""
    mesaj = str(getattr(eroare, "ce_s_a_intamplat", str(eroare)))
    de_ce = str(getattr(eroare, "de_ce", "") or "")
    if de_ce:
        mesaj += f"\n\nProbabil pentru că: {de_ce}"
    ce_fac = str(getattr(eroare, "ce_faci_acum", "") or getattr(eroare, "ce_fac", "") or "")
    det = detalii or str(getattr(eroare, "detalii", ""))
    dialog(parinte, titlu, mesaj, [("OK", "secundar")], implicit=0, detalii=f"{ce_fac}\n\n{det}".strip())


# --------------------------------------------------------------------------- fereprincipal


def seteaza_titlu(fereastra: QMainWindow | QWidget, parte: str = "") -> None:
    """Pune titlul „D&TED – …” pe fereastră (numele complet dacă nu e altă parte)."""
    from ..constante import NUME_SCURT, TITLU_FEREASTRA

    text = TITLU_FEREASTRA if not parte else f"{NUME_SCURT} – {parte}"
    fereastra.setWindowTitle(text)


def centrat(fereastra: QWidget, latime: int | None = None, inaltime: int | None = None) -> None:
    """Așază fereastra în mijlocul ecranului."""
    if latime is None and inaltime is None and not fereastra.testAttribute(Qt.WidgetAttribute.WA_Resized):
        fereastra.adjustSize()
    l = latime or fereastra.width()
    i = inaltime or fereastra.height()
    screen = QApplication.primaryScreen().availableGeometry()
    x = max(0, (screen.width() - l) // 2)
    y = max(0, (screen.height() - i) // 3)
    fereastra.resize(l, i)
    fereastra.move(x, y)


def maxim_ecran(procent: float = 0.9) -> QSize:
    """Dimensiunea maximă recomandată, ca procent din ecran."""
    screen = QApplication.primaryScreen().geometry()
    return QSize(int(screen.width() * procent), int(screen.height() * procent))


# --------------------------------------------------------------------------- fișiere / foldere


def cai_documente() -> Path:
    """Folderul „Documente” al utilizatorului."""
    from .. import cai

    return cai.director_iesiri()


def alege_fisier_audio(
    parinte: QWidget,
    folder: Path | None = None,
    titlu: str = "Alege fișierul audio",
    multiple: bool = False,
) -> Path | list[Path] | None:
    """Alege un fișier audio (sau mai multe, pentru coada de transcris).

    Cu ``multiple=True`` se poate bifi mai multe fișiere odată (cerința 35)
    și se întoarce o listă (goală la renunțare).
    """
    foldere = [
        "MP3 (*.mp3)",
        "WAV (*.wav)",
        "M4A (*.m4a)",
        "OGG (*.ogg)",
        "FLAC (*.flac)",
        "Opus (*.opus)",
        "Toate fișierele audio (*.mp3 *.wav *.m4a *.ogg *.flac *.opus)",
        "Toate fișierele (*.*)",
    ]
    cale_initiala = str(folder or cai_documente())
    if multiple:
        caile, _ = QFileDialog.getOpenFileNames(
            parinte,
            titlu,
            cale_initiala,
            ";;".join(foldere),
        )
        return [Path(cale) for cale in caile]
    cale, _ = QFileDialog.getOpenFileName(
        parinte,
        titlu,
        cale_initiala,
        ";;".join(foldere),
    )
    if not cale:
        return None
    return Path(cale)


def alege_folder(
    parinte: QWidget,
    titlu: str = "Alege folderul",
    initial: Path | None = None,
) -> Path | None:
    """Alege un folder cu QFileDialog."""
    cale_initiala = str(initial or cai_documente())
    cale = QFileDialog.getExistingDirectory(parinte, titlu, cale_initiala)
    if not cale:
        return None
    return Path(cale)


# --------------------------------------------------------------------------- zona progres cu ETA


class ZonaProgres(QWidget):
    """Zona de progres cu procent, ETA și mesaj de fază.

    Înlocuiește BaraProgres din Tkinter.
    """

    def __init__(self, parinte: QWidget | None = None, titlu: str = ""):
        super().__init__(parinte)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        if titlu:
            et_titlu = QLabel(titlu)
            et_titlu.setFont(fonturi("baza"))
            layout.addWidget(et_titlu)

        self.bar = QProgressBar()
        self.bar.setObjectName("progres")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        layout.addWidget(self.bar)

        self.et_procent = QLabel("0%")
        self.et_procent.setFont(fonturi("mica"))
        seteaza_rol(self.et_procent, "secundar")
        layout.addWidget(self.et_procent)

        self.et_ramas = QLabel("")
        self.et_ramas.setFont(fonturi("mica"))
        seteaza_rol(self.et_ramas, "secundar")
        layout.addWidget(self.et_ramas)

        self.et_faza = QLabel("")
        self.et_faza.setFont(fonturi("mica"))
        seteaza_rol(self.et_faza, "secundar")
        layout.addWidget(self.et_faza)

        self._inceput = 0.0
        self._facut = 0

    def incepe(self, titlu: str, curent: int, total: int) -> None:
        """Pornește progresul: titlu, pas curent, total."""
        self._inceput = time.time()
        self._facut = curent
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(curent)
        self.et_procent.setText(f"{int(100 * curent / max(1, total))}%")
        self.et_ramas.setText("")
        self.et_faza.setText(titlu)

    def seteaza(self, fractiune: float, mesaj: str = "") -> None:
        """Actualizează progresul (fractiune 0..1) și mesajul de fază."""
        valoare = int(max(0.0, min(1.0, fractiune)) * self.bar.maximum())
        self.bar.setValue(valoare)
        self.et_procent.setText(f"{int(100 * fractiune)}%")
        if mesaj:
            self.et_faza.setText(mesaj)
        # ETA aproximativ
        if fractiune > 0.05 and self._inceput > 0:
            trecut = time.time() - self._inceput
            total_estimata = trecut / fractiune
            ramane = max(0, total_estimata - trecut)
            self.et_ramas.setText(f"rămâne aproximativ {int(ramane)} s")

    def gata(self, mesaj: str = "Gata.") -> None:
        self.bar.setValue(self.bar.maximum())
        self.et_procent.setText("100%")
        self.et_faza.setText(mesaj)
        self.et_ramas.setText("")

    def reseteaza(self) -> None:
        self.bar.setValue(0)
        self.et_procent.setText("0%")
        self.et_faza.setText("")
        self.et_ramas.setText("")


def anunta_ascundere(parinte: QWidget) -> None:
    """Spune simplu că fereastra nu mai apare până mâine."""
    dialog(
        parinte,
        "Nu mai arăt fereastra azi",
        (
            "Bine. Nu mai arăt fereastra roșă până mâine. Semnul mic din colț rămâne acolo și "
            "se face roșu dacă ceva se deschide, ca să știi mereu cum stai."
        ),
        [("Am înțeles", "principal")],
    )
