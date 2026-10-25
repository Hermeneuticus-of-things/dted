"""Fereastra principală PySide6: ecranul de început și comutarea între ecrane.

Înlocuiește ``ui_principal.py`` (Tkinter). Logica este aceeași:
* starea lucrului (text, sunet, document) și setările;
* ecranul de început cu trei carduri mari (Dictează, Transcrie un fișier audio,
  Scrie sau corectează textul);
* editor integrat — zona mare, central, întotdeauna vizibil;
* trecere de la un ecran la altul, ajutor (F1), salvare DOCX/ODT/PDF,
  deschidere în LibreOffice, observare modificări externe.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import (
    biblioteca,
    blocare,
    cai,
    codecuri,
    config as config_modul,
    constante,
    dispozitive,
    documente,
    drivere,
    erori,
    inregistrare,
    instalare,
    jurnal,
    libreoffice,
    motor,
    operatiuni,
    programe_scris,
    resurse,
    securitate,
    stare as stare_modul,
    text_ro,
)
from ..constante import NUME_AFISAT, NUME_APLICATIE, NUME_SCURT, PROMPT_ROMANA, SUBTITLU_RO, TITLU_FEREASTRA
from . import comun
from .comun import BaraStare, Buton, Card, ZonaDerulare
from .ui_ajutor import FereastraAjutor
from .ui_editor import Editor
from .ui_internet import IndicatorCai, avertizeaza
from .ui_tur import TurPrimulRulez

# Ecrane care arată și editorul integrat, jos.
ECRANE_CU_EDITOR = ("dictare", "transcriere", "editor")


class Aplicatie(QMainWindow):
    """Fereastra principală. Tot ce fac ecranele trece prin metodele de aici."""

    def __init__(self, optiuni=None):
        super().__init__()
        self.optiuni = optiuni or {}
        self.setWindowTitle(TITLU_FEREASTRA)

        # Pictograma ferestrei.
        ico = Path(__file__).parent.parent / "iconita_dictare.ico"
        if not ico.exists():
            ico = Path(__file__).parent / "iconita_dictare.ico"
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))

        # Configurare, tema, fonturi.
        self.configurare = config_modul.incarca()
        self.config = self.configurare
        comun.aplica_tema(getattr(self.configurare, "mod_afisare", "windows"))
        comun.pregateste_fonturi(self)
        comun.mareste_scris(getattr(self.configurare, "marire_scris", 100) / 100.0)

        # Geometria ferestrei de la pornirea anterioară.
        geometrie = getattr(self.configurare, "geometrie_fereastra", "")
        if geometrie:
            try:
                self.restoreGeometry(geometrie.encode("latin-1"))
            except Exception:
                pass
        else:
            # Implicit: aproximativ 1280 x 800, centrat, ne-maximizată.
            self.resize(1280, 800)
            comun.centrat(self)

        self.stare = stare_modul.Stare(config=self.configurare)
        self.coada = comun.CoadaUI(self)
        self._motor: motor.MotorWhisper | None = motor.MotorWhisper(
            getattr(self.configurare, "dispozitiv", "auto"),
            getattr(self.configurare, "model_preferat", "auto"),
        )
        self._pagini: dict[str, QWidget] = {}
        self._pagina_aleasa = ""
        self._ultimele_randuri: list = []
        self._primul_click_editor = False
        self._mod_anterior = comun.mod_aplicat()
        self._cale_document_urmarit: Path | None = None
        self._amprenta_document: tuple[float, int] = (0.0, 0)
        self._inceput_urmarire = 0.0
        self._instalare_in_curs = False
        self._se_inchide = False

        # Timer salvare automată.
        self._timer_salvare_automata = QTimer(self)
        self._timer_salvare_automata.timeout.connect(self._salvare_automata)
        self._interval_salvare_automata = int(getattr(self.configurare, "salvare_automata_secunde", 0) or 0)
        if self._interval_salvare_automata > 0:
            self._timer_salvare_automata.start(self._interval_salvare_automata * 1000)

        self._construieste()

        # Scurtături tastatură.
        QShortcut(QKeySequence("Ctrl+D"), self, self._toggle_dictare)
        QShortcut(QKeySequence("Ctrl+T"), self, lambda: self.arata_ecran("transcriere"))
        QShortcut(QKeySequence("Ctrl++"), self, self.mareste_scrisul)
        QShortcut(QKeySequence("Ctrl+="), self, self.mareste_scrisul)
        QShortcut(QKeySequence("Ctrl+-"), self, self.micsoreaza_scrisul)
        QShortcut(QKeySequence("Ctrl+0"), self, self.reseteaza_scrisul)
        QShortcut(QKeySequence("Ctrl+,"), self, lambda: self.arata_ecran_setari())
        QShortcut(QKeySequence("Ctrl+Space"), self, self._toggle_dictare)
        QShortcut(QKeySequence("Ctrl+R"), self, self._comanda_asculta)  # 34: taste de redare
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, self._opreste_ascultarea)
        QShortcut(QKeySequence("F5"), self, self._toggle_dictare)
        QShortcut(QKeySequence("F9"), self, self._comanda_asculta)
        QShortcut(QKeySequence("Home"), self, lambda: self._sare_redare(0.0))
        QShortcut(QKeySequence("End"), self, self._sare_la_capat)
        QShortcut(QKeySequence("F7"), self, lambda: self._sare_redare(-5.0))
        QShortcut(QKeySequence("F8"), self, lambda: self._sare_redare(+5.0))
        QShortcut(QKeySequence("Escape"), self, self.close)  # D-3: �nchidere cu Esc (trece prin closeEvent)

        self._la_pornire()

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra de comenzi (toolbar) — un singur rând, ca în Paint/Notepad.
        self.toolbar = self.addToolBar("Comenzi")
        self.toolbar.setObjectName("toolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)

        # Meniu „Fișier ▾”
        self.menu_fisier = QMenu(self)
        self.menu_fisier.addAction("&Nou", lambda: self.editor.set_text(""), QKeySequence("Ctrl+N"))
        self.menu_fisier.addSeparator()
        self.menu_fisier.addAction("&Deschide fișier audio…", self.transcrie_fisier_ales, QKeySequence("Ctrl+O"))
        self.menu_fisier.addAction("Deschide &document…", self._deschide_document, QKeySequence("Ctrl+Shift+O"))
        self.menu_recente = self.menu_fisier.addMenu("&Recente")
        self.menu_fisier.addSeparator()
        self.menu_fisier.addAction("&Salvează", lambda: self.salveaza_document("docx"), QKeySequence("Ctrl+S"))
        self.menu_fisier.addAction("Salvează &ca…", self._salveaza_ca, QKeySequence("Ctrl+Shift+S"))
        self.menu_fisier.addSeparator()
        self.menu_fisier.addAction("E&xportă PDF", self._exporta_pdf)
        self.menu_fisier.addSeparator()
        self.menu_fisier.addAction("&Ieșire", self.close, QKeySequence("Alt+F4"))

        btn_fisier = QToolButton()
        btn_fisier.setText("&Fișier ▾")
        btn_fisier.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn_fisier.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_fisier.setMenu(self.menu_fisier)
        btn_fisier.setToolTip("Fișier (Ctrl+N, Ctrl+O, Ctrl+S)")
        self.toolbar.addWidget(btn_fisier)

        # Buton mare „🎤 Dictează” (distinct și colorat — vezi QSS #btn_dictare).
        self.btn_dictare = QToolButton()
        self.btn_dictare.setObjectName("btn_dictare")
        self.btn_dictare.setText("🎤 Dictează")
        self.btn_dictare.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_dictare.clicked.connect(self._toggle_dictare)
        self.btn_dictare.setToolTip("Dictează (Ctrl+D / Ctrl+Space)")
        self.toolbar.addWidget(self.btn_dictare)

        # Vumetru cu gradații dB (redesign UX) — vizibil DOAR cât se dictează.
        # 0 dB = distorsiune; verde -30…-6 dB e zona bună de dictare.
        self.vumetru_bar = comun.VumetruDb()
        self.vumetru_bar.hide()
        self.toolbar.addWidget(self.vumetru_bar)
        self.vumetru_text = QLabel("")
        self.vumetru_text.setObjectName("vumetru_text")
        self.vumetru_text.setFont(comun.fonturi("mica"))
        self.vumetru_text.hide()
        self.toolbar.addWidget(self.vumetru_text)

        # Buton mare „📂 Transcrie un fișier…”
        btn_transcrie = QToolButton()
        btn_transcrie.setText("📂")
        btn_transcrie.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn_transcrie.clicked.connect(self.transcrie_fisier_ales)
        btn_transcrie.setToolTip("Transcrie un fișier audio (Ctrl+T)")
        self.toolbar.addWidget(btn_transcrie)

        # Ascultarea înregistrării (32/34/35): apare doar când există o dictare.
        self.btn_asculta = QToolButton()
        self.btn_asculta.setText("▶ Ascultă (Ctrl+R)")
        self.btn_asculta.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_asculta.setToolTip(
            "Ascultă înregistrarea ultimei dictări. "
            "Pune cursorul lângă un semn [mm:ss] și pornește exact de acolo. "
            "Ctrl+R = ascultă/pauză · Ctrl+Shift+R = oprește."
        )
        self.btn_asculta.clicked.connect(self._comanda_asculta)
        self.btn_asculta.hide()
        self.toolbar.addWidget(self.btn_asculta)

        # Spațiu liber
        self.toolbar.addSeparator()
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.toolbar.addWidget(spacer)

        # Meniu „Instrumente ▾” — ce se folosește rar (redesign UX): un singur loc,
        # ca în aplicațiile profesionale; pagina principală rămâne doar cu des folositele.
        self.menu_instrumente = QMenu(self)
        self.menu_instrumente.addAction(
            "🎤 Testează microfonul și boxele", lambda: self.arata_ecran("sunet")
        )
        self.menu_instrumente.addAction(
            "📁 Fișierele mele", lambda: self.arata_ecran("fisiere")
        )
        self.menu_instrumente.addSeparator()
        self.menu_instrumente.addAction(
            "🛡 Internet și confidențialitate", lambda: self.arata_ecran("internet")
        )
        self.menu_instrumente.addAction(
            "📦 Instalare și actualizări", lambda: self.arata_ecran("instalare")
        )
        self.menu_instrumente.addAction(
            "🔍 Verifică programul și calculatorul", lambda: self.arata_ecran("verificare")
        )
        self.menu_instrumente.addSeparator()
        self.menu_instrumente.addAction("🏠 Ecranul de start", lambda: self.arata_ecran("principal"))
        self.menu_instrumente.addAction("📄 Doar textul", self._doar_textul, QKeySequence("Ctrl+E"))

        btn_instrumente = QToolButton()
        btn_instrumente.setText("&Instrumente ▾")
        btn_instrumente.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn_instrumente.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_instrumente.setMenu(self.menu_instrumente)
        btn_instrumente.setToolTip("Uneltele folosite mai rar (sunet, fișiere, confidențialitate…)")
        self.toolbar.addWidget(btn_instrumente)
        self.addActions(self.menu_instrumente.actions())

        # Meniu „Ajutor ▾”
        self.menu_ajutor = QMenu(self)
        self.menu_ajutor.addAction("? &Ajutor", lambda: self._ajutor(), QKeySequence("F1"))
        self.menu_ajutor.addAction("🐞 Raportează o problemă", self._deschide_raport)
        self.menu_ajutor.addAction("🎯 Tur ghidat", self._porneste_tur)
        self.menu_ajutor.addSeparator()
        self.menu_ajutor.addAction(
            "🔍 Verifică programul și calculatorul",
            lambda: self.arata_ecran("verificare"),
        )
        self.menu_ajutor.addSeparator()
        self.menu_ajutor.addAction("ℹ &Despre", self._despre)

        btn_ajutor = QToolButton()
        btn_ajutor.setText("❓")
        btn_ajutor.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn_ajutor.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_ajutor.setMenu(self.menu_ajutor)
        btn_ajutor.setToolTip("Ajutor (F1) — întrebări, tur ghidat, despre")
        self.toolbar.addWidget(btn_ajutor)

        # Buton „⚙ Setări”
        btn_setari = QToolButton()
        btn_setari.setText("⚙")
        btn_setari.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn_setari.setToolTip("Setări (Ctrl+,)")
        btn_setari.clicked.connect(self.arata_ecran_setari)
        self.toolbar.addWidget(btn_setari)

        # Scurtăturile din meniuri merg și când meniul e închis (o singură dată fiecare).
        self.addActions(self.menu_fisier.actions())
        self.addActions(self.menu_ajutor.actions())

        # Zona pagini (centru) - ocupă spațiu minim.
        self._zona_pagini = QWidget()
        self._zona_pagini.setAutoFillBackground(False)
        zona_layout = QVBoxLayout(self._zona_pagini)
        zona_layout.setContentsMargins(0, 0, 0, 0)
        zona_layout.setSpacing(0)
        layout.addWidget(self._zona_pagini, stretch=0)

        # Lista dictărilor (stil Express Dictate) — compactă și pliabilă;
        # zona de text rămâne cea mai mare.
        from .ui_dictari import ListaDictari

        self._eticheta_lista = QLabel("▾ Dictările mele")
        self._eticheta_lista.setFont(comun.fonturi("buton"))
        self._eticheta_lista.setCursor(Qt.CursorShape.PointingHandCursor)
        self._eticheta_lista.mousePressEvent = lambda _e: self._pliaza_lista()
        layout.addWidget(self._eticheta_lista)
        self.lista_dictari = ListaDictari(self, self)
        layout.addWidget(self.lista_dictari)

        # Editor integrat - ocupa cea mai mare parte din fereastră.
        self.editor = Editor(self, self.stare, la_actiune=self._dupa_scriere, inaltime=13)
        self._zona_editor = self.editor
        layout.addWidget(self.editor, stretch=1)

        # Bara de stare jos.
        self._jos = QFrame()
        self._jos.setObjectName("jos")
        jos_layout = QHBoxLayout(self._jos)
        jos_layout.setContentsMargins(14, 4, 14, 4)
        jos_layout.setSpacing(8)

        self.bara_stare = BaraStare(self._jos)
        jos_layout.addWidget(self.bara_stare, stretch=1)

        self._buton_folder = Buton(
            self._jos,
            "Deschide folderul documentelor",
            self._deschide_folderul,
            latime=200,
            inaltime=32,
        )
        jos_layout.addWidget(self._buton_folder)

        # Dock de redare profesionist (stil Express Scribe): transport + poziție.
        # Apare doar când există o înregistrare de ascultat; editorul rămâne regele.
        self._dock_redare = QFrame()
        self._dock_redare.setObjectName("dock_redare")
        dock_rand = QHBoxLayout(self._dock_redare)
        dock_rand.setContentsMargins(14, 6, 14, 6)
        dock_rand.setSpacing(10)

        # Ca la Express Dictate: Record ROȘU, Play VERDE, Stop ALBASTRU.
        self.btn_inregistreaza = Buton(
            self._dock_redare, "⏺ Dictează (F5)", self._toggle_dictare, fel="pericol", latime=150, inaltime=36
        )
        dock_rand.addWidget(self.btn_inregistreaza)

        self.btn_transport = Buton(
            self._dock_redare, "▶ Ascultă", self._comanda_asculta, fel="succes", latime=110, inaltime=36
        )
        self.btn_transport.setToolTip("Ascultă / pauză (F9 sau Ctrl+R)")
        dock_rand.addWidget(self.btn_transport)

        self.btn_transport_stop = Buton(
            self._dock_redare, "⏹ Stop", self._opreste_ascultarea, fel="principal", latime=90, inaltime=36
        )
        self.btn_transport_stop.setToolTip("Oprește (Esc)")
        dock_rand.addWidget(self.btn_transport_stop)

        btn_inapoi = QToolButton()
        btn_inapoi.setText("⏪")
        btn_inapoi.setFixedSize(40, 34)
        btn_inapoi.setToolTip("Înapoi 5 s (F7)")
        btn_inapoi.clicked.connect(lambda: self._sare_redare(-5.0))
        dock_rand.addWidget(btn_inapoi)

        btn_inainte = QToolButton()
        btn_inainte.setText("⏩")
        btn_inainte.setFixedSize(40, 34)
        btn_inainte.setToolTip("Înainte 5 s (F8)")
        btn_inainte.clicked.connect(lambda: self._sare_redare(+5.0))
        dock_rand.addWidget(btn_inainte)

        from PySide6.QtWidgets import QSlider
        self._slider_redare = QSlider(Qt.Orientation.Horizontal)
        self._slider_redare.setRange(0, 1000)
        self._slider_redare.setToolTip("Trage pentru a sări în înregistrare")
        self._slider_redare.sliderReleased.connect(self._cauta_din_slider)
        dock_rand.addWidget(self._slider_redare, stretch=1)

        self._eticheta_redare = QLabel("--:-- / --:--")
        self._eticheta_redare.setFont(comun.fonturi("buton"))
        self._eticheta_redare.setMinimumWidth(110)
        dock_rand.addWidget(self._eticheta_redare)

        # Volumul de ieșire (ca sliderul din Express Dictate).
        from PySide6.QtWidgets import QSlider as _QSlider
        from .. import nivele

        self._slider_volum = _QSlider(Qt.Orientation.Horizontal)
        self._slider_volum.setFixedWidth(120)
        self._slider_volum.setRange(0, 100)
        self._slider_volum.setToolTip("Volumul sunetului")
        _volum_curent = nivele.volum_iesire()
        if _volum_curent is not None:
            self._slider_volum.setValue(int(_volum_curent * 100))
        self._slider_volum.valueChanged.connect(
            lambda valoare: nivele.seteaza_volum_iesire(valoare / 100.0)
        )
        dock_rand.addWidget(self._slider_volum)

        self._dock_redare.hide()
        layout.addWidget(self._dock_redare)

        # Starea rețelei și confidențialitatea — mici, în bara de jos (redesign UX):
        # rareori folosite, deci nu mai stau în bara principală.
        self.btn_retea = QToolButton()
        self.btn_retea.setText("🔌 Offline")
        self.btn_retea.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_retea.setToolTip("Starea rețelei")
        jos_layout.addWidget(self.btn_retea)

        self.btn_confidentialitate = QToolButton()
        self.btn_confidentialitate.setText("🟢 Internet pornit")
        self.btn_confidentialitate.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_confidentialitate.setToolTip(
            "Confidențialitate: nimic blocat.\nApasă pentru a alege modul."
        )
        self.btn_confidentialitate.clicked.connect(self._la_confidentialitate)
        jos_layout.addWidget(self.btn_confidentialitate)

        # Mesajul discret de la eroare: „A apărut o problemă. Trimite raportul?”
        self.buton_raport = QToolButton()
        self.buton_raport.setText("⚠ A apărut o problemă — trimite raportul?")
        self.buton_raport.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.buton_raport.clicked.connect(self._la_eroare_raport)
        self.buton_raport.hide()
        jos_layout.addWidget(self.buton_raport)

        layout.addWidget(self._jos)

        # Redesign UX: pornim direct pe editor — spațiu maxim pentru textul
        # dictat (paginile întregi de corectat). Ecranul de start e în „Instrumente ▾”.
        self._doar_textul()
        self._reimprospateaza_ultimele()
        try:
            self.lista_dictari.reimprospateaza()
        except Exception:
            pass

    def _doar_textul(self) -> None:
        """Ascunde toate ecranele și lasă numai editorul (spațiu maxim)."""
        for pagina in self._pagini.values():
            pagina.hide()
        self._pagina_aleasa = ""

    # ------------------------------------------------------------------ ecrane

    def _ia_pagina(self, nume: str) -> QWidget:
        if nume in self._pagini:
            return self._pagini[nume]
        if nume == "principal":
            from .ui_principal_ecran import PaginaPrincipala
            pagina = PaginaPrincipala(self._zona_pagini, self)
        elif nume == "dictare":
            from .ui_dictare import PaginaDictare
            pagina = PaginaDictare(self._zona_pagini, self)
        elif nume == "transcriere":
            from .ui_transcriere import PaginaTranscriere
            pagina = PaginaTranscriere(self._zona_pagini, self)
        elif nume == "editor":
            from .ui_editor_ecran import PaginaEditor
            pagina = PaginaEditor(self._zona_pagini, self)
        elif nume == "verificare":
            from .ui_verificare import PaginaVerificare
            pagina = PaginaVerificare(self._zona_pagini, self)
        elif nume == "sunet":
            from .ui_sunet import FereastraSunet
            pagina = FereastraSunet(self._zona_pagini, self)
        elif nume == "fisiere":
            from .ui_fisiere import FereastraFisiere
            pagina = FereastraFisiere(self._zona_pagini, self)
        elif nume == "instalare":
            from .ui_instalare import FereastraInstalare
            pagina = FereastraInstalare(self._zona_pagini, self)
        else:
            from .ui_principal_ecran import PaginaPrincipala
            pagina = PaginaPrincipala(self._zona_pagini, self)
        self._pagini[nume] = pagina
        return pagina

    def arata_ecran(self, nume: str) -> None:
        """Trece la ecranul cerut."""
        nume = nume or "principal"
        pagina = self._ia_pagina(nume)

        # Ascunde celelalte.
        for alta in self._pagini.values():
            if alta is not pagina:
                alta.hide()

        pagina.show()
        self._zona_pagini.layout().addWidget(pagina)
        self._pagina_aleasa = nume

        # Editorul este întotdeauna vizibil (e elementul principal, mare).
        self.editor.show()

        if nume == "principal":
            if hasattr(pagina, "sincronizeaza_din_stare"):
                pagina.sincronizeaza_din_stare()
            self._reimprospateaza_ultimele()

        self.bara_stare.arata("Gata", "Programul este pornit. Alege ce vrei să faci.", "normal")

    def arata_ecran_setari(self) -> None:
        """Deschide fereastra de setări ca QDialog separat."""
        from .ui_setari import FereastraSetari
        dlg = FereastraSetari(self, self.configurare, la_salvare=self._dupa_salvare_setari)
        dlg.exec()

    # ------------------------------------------------------------------ comenzi

    def arata_ajutor(self, cheie: str = "principal") -> None:
        """Deschide fereastra de ajutor pentru ecranul dat."""
        self._ajutor_ecran(cheie)

    def _ajutor(self) -> None:
        self.arata_ajutor(self._pagina_aleasa or "principal")

    def _ajutor_ecran(self, cheie: str) -> None:
        dlg = FereastraAjutor(self, cheie)
        dlg.exec()

    def transcrie_fisier_ales(self) -> None:
        """„📂 Transcrie un fișier…”: arată ecranul de transcriere și deschide direct
        dialogul de alegere a fișierului audio."""
        self.arata_ecran("transcriere")
        pagina = self._pagini.get("transcriere")
        if pagina is not None and hasattr(pagina, "_alege_fisier"):
            pagina._alege_fisier()

    def _deschide_document(self) -> None:
        """„Fisier > Deschide” (Ctrl+O): alege un document și îl deschide în editor."""
        cale, _ = QFileDialog.getOpenFileName(
            self,
            "Deschide document",
            str(biblioteca.folder("documente")),
            "Documente (*.docx *.odt *.txt *.rtf *.md *.html *.markdown);;Toate fișierele (*.*)",
        )
        if cale:
            self._deschide_document_ales(Path(cale))

    def _deschide_document_ales(self, cale: Path) -> None:
        """Deschide un document text (docx/odt/txt/…) în editorul integrat.

        Documentele criptate (N-5) se deschid cu parola: se decriptează într-un
        fișier temporar care se șterge imediat după citire.
        """
        from .. import criptare, documente

        if criptare.este_criptat(cale):
            cheie = self._cheie_criptare()
            if cheie is None:
                self.bara_stare.arata(
                    "Încuiat", "documentul e criptat și nu s-a putut deschide fără parolă.", "problema"
                )
                return
            import tempfile

            with tempfile.TemporaryDirectory() as folder:
                temporar = Path(folder) / cale.name
                try:
                    criptare.decripteaza_fisier(cheie, cale, temporar)
                    text = documente.citeste_text(temporar)
                except Exception as exc:
                    comun.dialog_eroare(self, "Nu am putut deschide documentul", exc)
                    return
        else:
            try:
                text = documente.citeste_text(cale)
            except Exception as exc:
                comun.dialog_eroare(self, "Nu am putut deschide documentul", exc)
                return
        self.editor.set_text(text)
        self.stare.text = text
        self.stare.document_cale = Path(cale)
        self.stare.marca = biblioteca.marca_din_nume(Path(cale))
        self.stare.marcheaza_salvat()
        self.bara_stare.arata("Succes", f"Document deschis: {Path(cale).name}", "succes")

    def salveaza_document(self, fel: str = "docx") -> None:
        text = self.editor.text()
        if not text.strip():
            self.bara_stare.arata("ℹ", "Nu există text de salvat.", "normal")
            return
        from .. import documente
        destinatie = biblioteca.nume_unic(
            biblioteca.folder("documente"),
            biblioteca.nume_legat(self.stare.marca or "document", f".{fel}"),
        )
        documente.salveaza(text, destinatie, titlu=self.stare.marca or "Document")
        if self._cripteaza_daca_cere(destinatie):
            self.bara_stare.arata(
                "Succes", f"Document salvat și criptat: {destinatie.name}", "succes"
            )
        else:
            self.bara_stare.arata(
                "Succes", f"Document salvat: {destinatie.name}", "succes"
            )
        self._salvare_automata_fisier(destinatie)

    def _cheie_criptare(self) -> bytes | None:
        """Cheia maestră a seifului; cere parola o singură dată pe sesiune (N-5/N-6)."""
        if getattr(self, "_cheie_seif", None):
            return self._cheie_seif
        from .. import parola as modul_parola

        seif = modul_parola.incarca_seif()
        if seif is None:
            return None
        from PySide6.QtWidgets import QInputDialog, QLineEdit

        for incercare in range(3):
            from ..constante import PAROLA_IMPLICITA

            text, ok = QInputDialog.getText(
                self,
                "Parola documentelor",
                "Scrie parola cu care s-au criptat documentele\n"
                "(parola implicită „Dictare” e deja scrisă):",
                QLineEdit.EchoMode.Password,
                PAROLA_IMPLICITA if incercare == 0 else "",
            )
            if not ok:
                return None
            try:
                self._cheie_seif = modul_parola.deschide_cu_parola(seif, text)
                return self._cheie_seif
            except modul_parola.ParolaGresita:
                if incercare == 2:
                    comun.anunta(
                        self,
                        "Parola nu este corectă",
                        "Trei încercări fără succes. Încearcă din nou mai târziu "
                        "sau folosește cheia de recuperare din Setări.",
                    )
        return None

    def _cripteaza_daca_cere(self, destinatie: Path) -> bool:
        """Criptează pe loc documentul abia salvat, dacă e setat (N-5)."""
        if not getattr(self.configurare, "cripteaza_documente", False):
            return False
        cheie = self._cheie_criptare()
        if cheie is None:
            return False
        from .. import criptare

        criptare.cripteaza_fisier(cheie, destinatie, destinatie)
        return True

    def _salveaza_ca(self) -> None:
        from .comun import alege_folder
        cale = alege_folder(self, "Alege folderul în care salvez", biblioteca.folder("documente"))
        if cale:
            text = self.editor.text()
            if not text.strip():
                self.bara_stare.arata("ℹ", "Nu există text de salvat.", "normal")
                return
            from .. import documente
            import time
            marca = biblioteca.marca_din_nume(self.stare.marca or "document")
            destinatie = biblioteca.nume_unic(Path(cale), f"{marca}.docx")
            documente.salveaza(text, destinatie, titlu=self.stare.marca or "Document")
            if self._cripteaza_daca_cere(destinatie):
                self.bara_stare.arata(
                    "Succes", f"Document salvat și criptat: {destinatie.name}", "succes"
                )
            else:
                self.bara_stare.arata(
                    "Succes", f"Document salvat: {destinatie.name}", "succes"
                )

    def _exporta_pdf(self) -> None:
        text = self.editor.text()
        if not text.strip():
            self.bara_stare.arata("ℹ", "Nu există text de exportat.", "normal")
            return
        from .. import documente
        import time
        marca = biblioteca.marca_din_nume(self.stare.marca or "document")
        destinatie = biblioteca.nume_unic(
            biblioteca.folder("documente"),
            biblioteca.nume_legat(marca, ".pdf"),
        )
        # PDF direct din Qt (documente.salveaza nu scrie PDF).
        from PySide6.QtGui import QPdfWriter, QTextDocument
        doc = QTextDocument()
        doc.setPlainText(text)
        doc.setDefaultFont(self.editor.font())
        scriitor = QPdfWriter(str(destinatie))
        scriitor.setTitle(self.stare.marca or "Document")
        doc.print_(scriitor)
        del scriitor
        self.bara_stare.arata(
            "Succes", f"Document salvat: {destinatie.name}", "succes"
        )

    def _despre(self) -> None:
        from html import escape

        # Text bogat (HTML): „&” se scrie &amp;, deci apare corect în etichetă.
        comun.anunta(
            self,
            f"Despre {NUME_SCURT}",
            f"<div style='font-size:15pt; font-weight:bold'>{escape(NUME_AFISAT)} ({escape(NUME_SCURT)})</div>"
            f"<div style='font-size:10pt'>{escape(SUBTITLU_RO)}</div>"
            "<div style='font-size:8pt; color:gray'>Inspirat de Express Dictate și Express Scribe "
            "(NCH Software). D&amp;TED nu este afiliat cu NCH Software; mărcile aparțin "
            "proprietarilor lor.</div><br>"
            "Versiunea 1.0.0<br><br>"
            "Program de dictare și transcriere text, 100% local,<br>"
            "cu modelul Whisper large-v3-turbo.<br><br>"
            "Toate prelucrările se fac pe calculatorul tău.<br>"
            "Nicio informație nu este trimisă pe internet.",
        )

    def _deschide_folderul(self) -> None:
        from .. import sisteme
        sisteme.deschide_folder(biblioteca.folder("documente"))

    def mareste_scrisul(self) -> None:
        """Mărește scrisul doar pentru textul transcrit (Ctrl+plus)."""
        comun.mareste_scris(1.15)
        self.editor.actualizeaza_font()

    def micsoreaza_scrisul(self) -> None:
        """Micărește scrisul doar pentru textul transcrit (Ctrl+minus)."""
        comun.mareste_scris(1 / 1.15)
        self.editor.actualizeaza_font()

    def reseteaza_scrisul(self) -> None:
        comun.mareste_scris(1.0)
        self.editor.actualizeaza_font()

    def _toggle_dictare(self) -> None:
        """Porneste/opreste dictarea (F5 / Ctrl+Space)."""
        # Găsește pagina de dictare și apasă butonul ei
        pagina = self._pagini.get("dictare")
        if pagina is None:
            pagina = self._ia_pagina("dictare")
        if hasattr(pagina, "buton_start"):
            pagina.buton_start.click()
        self._actualizeaza_buton_dictare()

    def _actualizeaza_buton_dictare(self) -> None:
        """Schimbă textul și stilul butonului „Dictează” după starea dictării."""
        pagina = self._pagini.get("dictare")
        activ = bool(pagina is not None and getattr(pagina, "_activ", False))
        if activ:
            self.btn_dictare.setText("⏹ Oprește dictarea")
            if hasattr(self, "btn_inregistreaza"):
                self.btn_inregistreaza.set_text("⏹ Oprește (F5)")
            self.btn_dictare.setToolTip("Oprește dictarea (Ctrl+Space)")
        else:
            self.btn_dictare.setText("🎤 Dictează")
            if hasattr(self, "btn_inregistreaza"):
                self.btn_inregistreaza.set_text("⏺ Dictează (F5)")
            self.btn_dictare.setToolTip("Dictează (Ctrl+D / Ctrl+Space)")
        self.btn_dictare.setProperty("dictare", "true" if activ else "false")
        stil = self.btn_dictare.style()
        if stil is not None:
            stil.unpolish(self.btn_dictare)
            stil.polish(self.btn_dictare)
        self._porneste_vumetru(activ)

    def _porneste_vumetru(self, activ: bool) -> None:
        """Pornește/oprește vumetrul din bara de sus; când e oprit, îl golește
        și îl ascunde (redesign UX: bara de sus rămâne doar cu des folositele)."""
        if not hasattr(self, "_timer_vumetru"):
            self._timer_vumetru = QTimer(self)
            self._timer_vumetru.timeout.connect(self._actualizeaza_vumetru)
        self.vumetru_bar.setVisible(activ)
        self.vumetru_text.setVisible(activ)
        if activ:
            self._timer_vumetru.start(60)  # ~16 actualizări pe secundă
        else:
            self._timer_vumetru.stop()
            from .. import nivele as _nivele

            self.vumetru_bar.pune_db(_nivele.DB_MINIM)
            self.vumetru_text.setText("microfon oprit")
            # rămâne vizibil 6 s și după oprire, ca să-l observi liniștit
            def ascunde_daca_inactiv() -> None:
                pagina = self._pagini.get("dictare")
                inactiv = pagina is None or not getattr(pagina, "_activ", False)
                if inactiv:
                    self.vumetru_bar.hide()
                    self.vumetru_text.hide()

            QTimer.singleShot(6000, ascunde_daca_inactiv)

    def _actualizeaza_vumetru(self) -> None:
        """Citește nivelul microfonului și afișează bara + textul, în dB (cerința 36)."""
        from .. import nivele

        pagina = self._pagini.get("dictare")
        amplitudine = 0.0
        if pagina is not None:
            amplitudine = float(min(1.0, getattr(pagina, "nivel_microfon", 0.0)))
        db = nivele.amplitudine_in_db(amplitudine)
        self.vumetru_bar.pune_db(db)
        self.vumetru_text.setText(nivele.text_db(db))
        chunk = {"verde": "verde", "galben": "galben", "roșu": "roșu"}[nivele.zona_db(db)]
        if self.vumetru_bar.property("chunk") != chunk:
            self.vumetru_bar.setProperty("chunk", chunk)
            stil = self.vumetru_bar.style()
            if stil is not None:
                stil.unpolish(self.vumetru_bar)
                stil.polish(self.vumetru_bar)

    # ------------------------------------------------------------------ confidențialitate (5/9)

    def _actualizeaza_bara_confidentialitate(self) -> None:
        """Leagă iconița de confidențialitate de starea REALĂ de blocare (N-3, §5.2)."""
        try:
            mod = blocare.starea_activa()
            nivel = blocare.nivelul(mod)
        except Exception:
            nivel = blocare.NIVEL_VERDE
        texte = {
            blocare.NIVEL_VERDE: ("🟢 Internet pornit", "nimic blocat"),
            blocare.NIVEL_PORTOCALIU: ("🟠 Program izolat", "doar D&TED e oprit de la internet"),
            blocare.NIVEL_ROSU: ("🔴 Totul tăiat", "internet + USB + Bluetooth + Wi-Fi blocate"),
        }
        text, descriere = texte.get(nivel, texte[blocare.NIVEL_VERDE])
        activ = nivel != blocare.NIVEL_VERDE
        self.btn_confidentialitate.setText(text)
        self.btn_confidentialitate.setToolTip(
            f"Confidențialitate: {descriere}.\n"
            + ("Apasă pentru a OPRI blocarea." if activ else "Apasă pentru a alege modul.")
        )
        culoare = {
            blocare.NIVEL_VERDE: "#15803D",
            blocare.NIVEL_PORTOCALIU: "#B45309",
            blocare.NIVEL_ROSU: "#B91C1C",
        }[nivel]
        self.btn_confidentialitate.setStyleSheet(
            f"QToolButton {{ color: {culoare}; font-weight: 600; }}"
        )

    def _actualizeaza_indicator_retea(self) -> None:
        """UX-31: indicatorul de rețea arată starea REALĂ (verificarea în fundal)."""
        def lucru() -> None:
            from .. import internet

            try:
                conectat = internet.are_internet()
            except Exception:
                conectat = None
            self.coada.trimite(self._pune_indicator_retea, conectat)

        threading.Thread(target=lucru, name="stare-retea", daemon=True).start()

    def _pune_indicator_retea(self, conectat) -> None:
        if conectat is None:
            self.btn_retea.setText("🔌 Rețea neprecizată")
            self.btn_retea.setToolTip("Nu am putut verifica starea internetului chiar acum.")
            culoare = "#6B7280"
        elif conectat:
            self.btn_retea.setText("🌐 Internet pornit")
            self.btn_retea.setToolTip(
                "Internetul este pornit. Programul NU trimite nimic pe internet; "
                "dacă lucrezi cu informații sensibile, îl poți opri."
            )
            culoare = "#B45309"
        else:
            self.btn_retea.setText("🔌 Fără internet")
            self.btn_retea.setToolTip("Nicio legătură cu internetul — lucrezi în siguranță.")
            culoare = "#15803D"
        self.btn_retea.setStyleSheet(f"QToolButton {{ color: {culoare}; font-weight: 600; }}")

    # ------------------------------------------------------------------ scurtături globale (53)

    def _porneste_scurtaturile_globale(self, pornite: bool | None = None) -> None:
        """Ctrl+Alt+D pornește/oprește dictarea din orice program.

        Înregistrată DOAR dacă utilizatorul a bifat-o în Setări — oprită implicit.
        """
        if sys.platform != "win32":
            return
        import ctypes

        if pornite is None:
            pornite = bool(getattr(self.configurare, "scurtaturi_globale", False))
        if pornite and getattr(self, "_hotkey_id", None) is None:
            # MOD_ALT (1) + MOD_CONTROL (2), tasta virtuală „D” (0x44), id 1.
            if ctypes.windll.user32.RegisterHotKey(None, 1, 0x0003, 0x44):
                self._hotkey_id = 1
                self._instaleaza_filtru_hotkey()
        elif not pornite and getattr(self, "_hotkey_id", None) is not None:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self._hotkey_id)
            except Exception:
                pass
            self._hotkey_id = None

    def _instaleaza_filtru_hotkey(self) -> None:
        """Prinde mesajul WM_HOTKEY din coada ferestrei și apelează comanda."""
        from PySide6.QtCore import QAbstractNativeEventFilter

        class _FiltruHotkey(QAbstractNativeEventFilter):
            def __init__(self, la_apasare):
                super().__init__()
                self._la_apasare = la_apasare

            def nativeEventFilter(self, tip, mesaj):
                try:
                    if int(mesaj):
                        import ctypes.wintypes

                        structura = ctypes.wintypes.MSG.from_address(int(mesaj))
                        if structura.message == 0x0312 and structura.wParam == 1:
                            self._la_apasare()
                except Exception:
                    pass
                return False

        if getattr(self, "_filtru_hotkey", None) is None:
            self._filtru_hotkey = _FiltruHotkey(self._la_scurtatura_globala)
            aplicatie = QApplication.instance()
            if aplicatie is not None:
                aplicatie.installNativeEventFilter(self._filtru_hotkey)

    # ------------------------------------------------------------- ascultare (32/34/35)

    def _player_ascultare(self):
        """„Reportofonul” editorului (creat o singură dată, cu sunetul real)."""
        if not hasattr(self, "_ascultator"):
            from .. import inregistrare, redare

            self._ascultator = redare.Redare(
                porneste_sunet=lambda pcm, rata: inregistrare.reda(pcm, rata),
                opreste_sunet=inregistrare.opreste_redarea,
            )
        return self._ascultator

    def primeste_inregistrarea(self, inregistrare_dictata) -> None:
        """Dictarea s-a oprit: păstrează sunetul pentru „▶ Ascultă”."""
        try:
            pcm = getattr(inregistrare_dictata, "pcm", None)
            rata = getattr(inregistrare_dictata, "rata", 16000) or 16000
            if pcm is not None and len(pcm):
                self._player_ascultare().incarca(pcm, rata)
                self.btn_asculta.show()
                self.btn_asculta.setText("▶ Ascultă (Ctrl+R)")
                self._dock_redare.show()
                self._arata_stare_redare()
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut păstra înregistrarea pentru ascultare: {exc}")

    def _comanda_asculta(self) -> None:
        """Ctrl+R: ascultă de la semnul de lângă cursor, sau pauză/continuare."""
        from .. import redare as modul_redare

        player = self._player_ascultare()
        if not player.are():
            self.bara_stare.arata("ℹ", "Nu există nicio dictare de ascultat încă.", "normal")
            return
        if player.ruleaza():
            player.pauza()
            self.btn_asculta.setText("▶ Continuă (Ctrl+R)")
            self.btn_transport.set_text("▶ Continuă")
            self.bara_stare.arata("Pauză", "ascultarea e pe pauză (Ctrl+R continuă).", "normal")
            return
        # cerința 32: ascultă zona semnului de lângă cursor
        cursor = self.editor.cursor_pozitie() if hasattr(self.editor, "cursor_pozitie") else -1
        text = self.editor.text()
        de_la = modul_redare.semn_la_cursor(text, cursor) if cursor >= 0 else None
        if player.porneste(de_la):
            self._porneste_ceasul_ascultarii()
            self.btn_asculta.setText("⏸ Pauză (Ctrl+R)")
            self.btn_transport.set_text("⏸ Pauză")
            unde = f"de la semnul {modul_redare.marca_din_secunde(de_la)}" if de_la else "de la început"
            self.bara_stare.arata("Redare", f"Ascult {unde}.", "lucru")

    def _opreste_ascultarea(self) -> None:
        """Ctrl+Shift+R: oprește complet ascultarea."""
        if not hasattr(self, "_ascultator"):
            return
        self._ascultator.opreste()
        self.btn_asculta.setText("▶ Ascultă (Ctrl+R)")
        self.btn_transport.set_text("▶ Ascultă")
        self._arata_stare_redare()
        self.bara_stare.arata("Oprit", "ascultarea s-a oprit.", "normal")

    def _porneste_ceasul_ascultarii(self) -> None:
        self._arata_stare_redare()
        self.btn_transport.setText("⏸")

        def pas() -> None:
            if not hasattr(self, "_ascultator") or not self._ascultator:
                return
            if self._ascultator.ruleaza() and self._ascultator.la_capat():
                self._ascultator.opreste()
                self.btn_asculta.setText("▶ Ascultă (Ctrl+R)")
                self.btn_transport.setText("▶")
            self._arata_stare_redare()
            if self._ascultator.ruleaza():
                QTimer.singleShot(250, pas)

        QTimer.singleShot(250, pas)

    def _arata_stare_redare(self) -> None:
        """Sliderul și eticheta de timp ale dock-ului de redare."""
        from .. import redare as modul_redare

        if not hasattr(self, "_ascultator") or not self._ascultator.are():
            return
        durata = self._ascultator.durata()
        pozitie = self._ascultator.pozitie()
        self._slider_redare.blockSignals(True)
        self._slider_redare.setRange(0, max(1, int(durata * 10)))
        self._slider_redare.setValue(int(pozitie * 10))
        self._slider_redare.blockSignals(False)
        self._eticheta_redare.setText(
            f"{modul_redare.marca_din_secunde(pozitie)} / {modul_redare.marca_din_secunde(durata)}"
        )

    def _cauta_din_slider(self) -> None:
        """Tragerea sliderului = sare în înregistrare (stil program profesionist)."""
        if not hasattr(self, "_ascultator") or not self._ascultator.are():
            return
        secunde = self._slider_redare.value() / 10.0
        rulea = self._ascultator.ruleaza()
        if rulea:
            self._ascultator.pauza()
        self._ascultator._offset = min(secunde, max(0.0, self._ascultator.durata() - 0.2))
        if rulea:
            self._ascultator.porneste()
        self._arata_stare_redare()

    def _pliaza_lista(self) -> None:
        """Ascunde/arată lista dictărilor (zona de text devine și mai mare)."""
        vizibil = self.lista_dictari.isVisible()
        self.lista_dictari.setVisible(not vizibil)
        self._eticheta_lista.setText("▾ Dictările mele" if not vizibil else "▸ Dictările mele")

    def deschide_dictare(self, cale_text, cale_audio) -> None:
        """Un clic în lista dictărilor: textul în editor, sunetul gata de ascultat."""
        from .. import biblioteca

        try:
            text_citit = biblioteca.citeste(Path(cale_text))
        except Exception as exc:
            comun.dialog_eroare(self, "Nu am putut deschide dictarea", exc)
            return
        self.editor.set_text(text_citit)
        self.stare.text = text_citit
        self.stare.document_cale = Path(cale_text)
        self.stare.marca = biblioteca.marca_din_nume(Path(cale_text))
        self.stare.marcheaza_salvat()
        self.bara_stare.arata("Succes", f"Dictare deschisă: {Path(cale_text).stem}", "succes")
        if cale_audio is not None and str(cale_audio).lower().endswith(".wav"):
            try:
                import soundfile as sf

                sunet, rata = sf.read(str(cale_audio), dtype="float32")
                if sunet.ndim > 1:
                    sunet = sunet.mean(axis=1)
                self.primeste_inregistrarea(
                    type("I", (), {"pcm": sunet, "rata": int(rata)})()
                )
            except Exception:
                pass

    def _sare_redare(self, delta: float) -> None:
        """F7/F8: sare înapoi/înainte în înregistrare (± secunde)."""
        if not hasattr(self, "_ascultator") or not self._ascultator.are():
            return
        player = self._ascultator
        rulea = player.ruleaza()
        if rulea:
            player.pauza()
        tinta = min(max(0.0, player.pozitie() + delta), max(0.0, player.durata() - 0.2))
        player._offset = tinta
        if rulea:
            player.porneste()
        self._arata_stare_redare()

    def _sare_la_capat(self) -> None:
        """End: sărește la sfârșitul înregistrării."""
        if hasattr(self, "_ascultator") and self._ascultator.are():
            self._sare_redare(self._ascultator.durata())

    def _deschide_raport(self, descriere: str = "") -> None:
        """Ajutor → Raportează o problemă (detaliile tehnice vin din jurnal)."""
        from .ui_raport import FereastraRaport

        self.buton_raport.hide()
        try:
            FereastraRaport(self, descriere_initiala=descriere).exec()
        except Exception as exc:
            jurnal.atentionare(f"Fereastra de raport nu s-a putut deschide: {exc}")

    def _la_eroare_raport(self) -> None:
        """Un clic pe mesajul discret de eroare → fereastra de raport."""
        self._deschide_raport()

    def _la_eroare_jurnal(self, mesaj: str) -> None:
        """Chemată de jurnal la fiecare EROARE: arată discret butonul de raport.

        Poate veni din orice fir de execuție — trecem în firul interfeței.
        """
        def arata() -> None:
            self.buton_raport.setToolTip(mesaj[:300])
            self.buton_raport.show()
            self.bara_stare.arata(
                "Problemă", "a apărut o eroare (salvată în jurnal). Trimite raportul?",
                "problema",
            )
            QTimer.singleShot(60_000, self.buton_raport.hide)

        try:
            QTimer.singleShot(0, arata)
        except Exception:
            pass

    def _la_scurtatura_globala(self) -> None:
        """Ctrl+Alt+D, apăsat în orice program: adu fereastra și comută dictarea."""
        self.show()
        self.raise_()
        self.activateWindow()
        self.arata_ecran("dictare")
        self._toggle_dictare()

    def _la_confidentialitate(self) -> None:
        """Click pe iconiță: dacă e blocat, oferă oprirea; altfel deschide avertizarea."""
        try:
            mod = blocare.starea_activa()
        except Exception:
            mod = None
        if mod:
            self._opreste_blocarea(mod)
        else:
            avertizeaza(self, self.configurare, pentru_dictare=False, fortat=True)

    def _opreste_blocarea(self, mod: str) -> None:
        """Confirmă și oprește blocarea activă (butonul vizibil de oprire, §9.4)."""
        raspuns = QMessageBox.question(
            self,
            "Confidențialitate",
            "Blocarea este activă. Oprește acum și readă totul la normal "
            "(internet, USB, Bluetooth, Wi-Fi)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if raspuns == QMessageBox.StandardButton.Yes:
            try:
                blocare.deblocheaza_acum()
            except Exception:  # nu blocăm programul pentru asta
                pass
            self._actualizeaza_bara_confidentialitate()

    def _porneste_supravegherea_confidentialitatii(self) -> None:
        """Timer + curățarea blocărilor vechi la pornire (5.5)."""
        self._actualizeaza_bara_confidentialitate()
        if not hasattr(self, "_timer_confidentialitate"):
            self._timer_confidentialitate = QTimer(self)
            self._timer_confidentialitate.timeout.connect(self._actualizeaza_bara_confidentialitate)
            self._timer_confidentialitate.start(5000)
        # UX-31: indicatorul de rețea se citește la pornire și apoi din minut în minut
        # (verificarea atinge rețeaua, deci nu se face la fiecare 5 secunde).
        if not hasattr(self, "_timer_retea"):
            self._timer_retea = QTimer(self)
            self._timer_retea.timeout.connect(self._actualizeaza_indicator_retea)
            self._timer_retea.start(60000)
        self._actualizeaza_indicator_retea()
        self._porneste_scurtaturile_globale()
        jurnal.adauga_observator_eroare(self._la_eroare_jurnal)
        QTimer.singleShot(800, self._anuleaza_blocari_vechi_lapornire)

    def _anuleaza_blocari_vechi_lapornire(self) -> None:
        """Anulează blocările rămase de la o rulare anterioară (5.5)."""
        try:
            blocare.anuleaza_blocuri_vechi()
        except Exception:
            pass
        self._actualizeaza_bara_confidentialitate()

    # ------------------------------------------------------------------ pornire

    def _la_pornire(self) -> None:
        """Ce se face la pornire: verificări, recuperare, tur."""
        self.editor.actualizeaza_etichete()
        self.bara_stare.arata("Gata", "Programul este pornit. Alege ce vrei să faci.", "normal")
        self._porneste_supravegherea_confidentialitatii()

        # Prima pornire: descarcă automat ce lipsește (modelul; CUDA doar cu placă NVIDIA).
        # Fără rețea: doar fișiere locale și starea salvată în setări (cuda_stare).
        if not getattr(self, "_pregatire_incercata", False):
            from .. import pregatire

            self._pregatire_incercata = True
            try:
                lipsa_model = bool(pregatire.fisiere_model_lipsa())
                propune_cuda = pregatire.cuda_de_propus(self.configurare)
            except Exception as exc:
                jurnal.atentionare(f"Nu am putut verifica ce lipsește: {exc}")
                lipsa_model = propune_cuda = False
            if lipsa_model or propune_cuda:
                QTimer.singleShot(
                    300, lambda: self._pregateste_prima_pornire(lipsa_model, propune_cuda)
                )
                return

        # Verificări în fundal (fără rețea).
        threading.Thread(target=self._verifica_instalarea_la_pornire, daemon=True).start()
        threading.Thread(target=self._verifica_codecurile_la_pornire, daemon=True).start()
        QTimer.singleShot(300, self._intreaba_de_text_recuperat)
        QTimer.singleShot(600, self._intreaba_de_lucrul_neterminat)
        QTimer.singleShot(1200, self._verifica_driverele_la_pornire)
        QTimer.singleShot(1500, self._verifica_microfonul_la_pornire)

    def _verifica_microfonul_la_pornire(self) -> None:
        """Cerinta 52: asistent microfon - verifica daca exista microfon."""
        try:
            from .. import dispozitive
            microfoane = dispozitive.microfoane()
            if not microfoane:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "Microfonul nu a fost gasit",
                    "Nu am gasit niciun microfon pe acest calculator.\n\n"
                    "Conecteaza un microfon (USB sau Bluetooth) si redeschide programul, "
                    "sau verifica in Setari -> Sunet.",
                )
        except Exception:
            pass
        if not getattr(self.configurare, "tur_vazut", False):
            QTimer.singleShot(1500, lambda: self._porneste_tur())

    def _confirma_cuda(self) -> bool:
        """Întreabă înainte de descărcarea de ~1,2 GB; „Nu” se ține minte (cuda_stare=refuzat)."""
        from PySide6.QtWidgets import QMessageBox

        from .. import motor, pregatire

        try:
            nume = motor.nume_placa_video() or "NVIDIA"
        except Exception:
            nume = "NVIDIA"
        cutie = QMessageBox(self)
        cutie.setWindowTitle(f"{NUME_SCURT} – Placa video")
        cutie.setIcon(QMessageBox.Icon.Question)
        cutie.setText(
            f"Am găsit placa video {nume}.\n\n"
            "Cu ea, transcrierea merge de câteva ori mai repede. Pentru asta trebuie descărcate "
            f"bibliotecile NVIDIA (cuBLAS și cuDNN): {pregatire.CUDA_MARIME_TEXT}.\n\n"
            "Le descarc acum? Fără ele programul merge pe procesor, doar mai încet."
        )
        da = cutie.addButton("Da, descarcă", QMessageBox.ButtonRole.AcceptRole)
        cutie.addButton("Nu acum", QMessageBox.ButtonRole.RejectRole)
        cutie.exec()
        if cutie.clickedButton() is da:
            return True
        pregatire.salveaza_stare_cuda("refuzat", "", self.configurare)
        self.bara_stare.arata(
            "Placa video",
            "Nu descarc bibliotecile. Le poți descărca oricând din Verificare sau Setări.",
            "normal",
        )
        return False

    def descarca_cuda_la_cerere(self) -> None:
        """Butonul din Verificare/Setări: (re)încearcă descărcarea, cu confirmare."""
        from .. import pregatire

        if getattr(self, "_dlg_pregatire", None) is not None:
            return  # o descărcare e deja în curs
        if not pregatire.trebuie_cuda():
            self.bara_stare.arata("Placa video", "Bibliotecile pentru placa video sunt deja gata.", "succes")
            self._actualizeaza_placa_video()
            return
        if self._confirma_cuda():
            self._porneste_pregatirea(False, True, self._actualizeaza_placa_video, "cuda")
        else:
            self._actualizeaza_placa_video()

    def _actualizeaza_placa_video(self) -> None:
        for widget in [self, *self.findChildren(QWidget)]:
            functie = getattr(widget, "actualizeaza_placa_video", None)
            if callable(functie) and widget is not self:
                try:
                    functie()
                except Exception:
                    pass

    def _pregateste_prima_pornire(self, lipsa_model: bool, propune_cuda: bool) -> None:
        cu_cuda = self._confirma_cuda() if propune_cuda else False
        if not lipsa_model and not cu_cuda:
            self._la_pornire()
            return
        # „Prima pornire” doar dacă programul chiar nu a mai fost folosit (turul nevăzut
        # și modelul lipsă); altfel e o reparare a modelului sau doar placa video.
        if lipsa_model and not getattr(self.configurare, "tur_vazut", False):
            context = "prima"
        elif lipsa_model:
            context = "model"
        else:
            context = "cuda"
        self._porneste_pregatirea(lipsa_model, cu_cuda, self._la_pornire, context)

    _TITLURI_PREGATIRE = {
        "prima": "Prima pornire",
        "model": "Pregătire model de transcriere",
        "cuda": "Pregătire placă video",
    }

    def _porneste_pregatirea(self, lipsa_model: bool, cu_cuda: bool, la_final, context: str = "cuda") -> None:
        """Fereastră de progres (în română); descărcarea rulează în fundal."""
        from PySide6.QtWidgets import QProgressDialog

        from .. import pregatire

        lipsa = []
        if lipsa_model:
            lipsa.append("modelul de transcriere (aproximativ 1,6 GB)")
        if cu_cuda:
            lipsa.append(f"bibliotecile pentru placa video NVIDIA ({pregatire.CUDA_MARIME_TEXT})")
        self._dupa_pregatire = la_final
        self._context_pregatire = context
        self._cuda_cerut = cu_cuda

        dlg = QProgressDialog(self)
        dlg.setWindowTitle(f"{NUME_SCURT} – {self._TITLURI_PREGATIRE.get(context, 'Pregătire')}")
        inceput = (
            "Pregătesc programul pentru prima folosire:" if context == "prima"
            else "Descarc ce lipsește:"
        )
        dlg.setLabelText(
            inceput + "\n– " + "\n– ".join(lipsa)
            + "\n\nEste nevoie de internet doar acum. După aceea programul merge fără internet."
        )
        dlg.setCancelButtonText("Ascunde")
        dlg.setRange(0, 1000)
        dlg.setMinimumWidth(560)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setMinimumDuration(0)
        dlg.show()
        self._dlg_pregatire = dlg
        self.bara_stare.arata(
            "Pregătesc",
            "Descarc bibliotecile pentru placa video…" if context == "cuda"
            else "Descarc ce lipsește pentru folosirea programului…",
            "lucru",
        )

        def progres(mesaj: str, fractiune: float) -> None:
            self.coada.trimite(self._progres_pregatire, mesaj, fractiune)

        def in_fundal() -> None:
            try:
                rezultat = pregatire.pregateste(
                    progres, cu_cuda=cu_cuda, configurare=self.configurare,
                    cu_model=lipsa_model and context != "cuda",
                )
                self.coada.trimite(self._gata_pregatire, None, rezultat)
            except Exception as exc:
                self.coada.trimite(self._gata_pregatire, exc, None)

        threading.Thread(target=in_fundal, name=f"pregatire-{context}", daemon=True).start()

    def _progres_pregatire(self, mesaj: str, fractiune: float) -> None:
        dlg = getattr(self, "_dlg_pregatire", None)
        if dlg is not None and dlg.isVisible():
            dlg.setLabelText(mesaj)
            dlg.setValue(int(fractiune * 1000))
        self.bara_stare.arata("Pregătesc", mesaj, "lucru")

    def _gata_pregatire(self, exc, rezultat=None) -> None:
        dlg = getattr(self, "_dlg_pregatire", None)
        if dlg is not None:
            dlg.close()
        self._dlg_pregatire = None
        la_final = getattr(self, "_dupa_pregatire", None) or self._la_pornire
        self._dupa_pregatire = None
        context = getattr(self, "_context_pregatire", "prima")
        cuda_cerut = getattr(self, "_cuda_cerut", False)
        cuda = str((rezultat or {}).get("cuda", ""))
        if exc is None:
            la_final()  # întâi pornirea obișnuită, apoi mesajul final (să nu fie acoperit)
            if cuda_cerut and cuda != "gata":
                jurnal.atentionare(f"Placa video nu a putut fi pregătită: {cuda}")
                if context == "cuda":
                    mesaj = "Placa video nu a putut fi pregătită; se folosește procesorul."
                else:
                    mesaj = "Programul este pregătit; placa video nu a putut fi pregătită, se folosește procesorul."
                self.bara_stare.arata("Gata", mesaj, "atentie")
            elif context == "cuda":
                self.bara_stare.arata(
                    "Gata", "Placa video este pregătită. Transcrierea va folosi placa video.", "succes"
                )
            else:
                self.bara_stare.arata("Gata", "Programul este pregătit. Poți dicta și transcrie.", "succes")
        elif context == "cuda":
            jurnal.eroare(f"Pregătirea plăcii video a eșuat: {exc}")
            self.bara_stare.arata(
                "Placa video",
                "Bibliotecile pentru placa video nu s-au descărcat; se folosește procesorul. "
                "Poți reîncerca din Verificare sau Setări.",
                "atentie",
            )
            comun.dialog_eroare(self, "Pregătirea plăcii video nu s-a terminat", exc)
            la_final()
        else:
            jurnal.eroare(f"Pregătirea modelului de transcriere a eșuat: {exc}")
            self.bara_stare.arata(
                "Nepregătit",
                "Modelul de transcriere nu s-a descărcat. Deschide internetul și pornește din nou programul.",
                "atentie",
            )
            comun.dialog_eroare(self, "Pregătirea nu s-a terminat", exc)

    def _instalarea_este_completa(self) -> bool:
        try:
            lipsa = instalare.verifica_instalare()
        except Exception as exc:
            jurnal.atentionare(f"Verificarea instalării a eșuat: {exc}")
            return True
        self._probleme_instalare = lipsa
        return not lipsa

    def _verifica_instalarea_la_pornire(self) -> None:
        """Verificare ușoară, fără rețea (fișiere locale); rulează în fundal la pornire."""
        try:
            from .. import pregatire

            if not pregatire.fisiere_model_lipsa() and not pregatire.model_verificat_complet():
                # O singură dată: SHA-256 pe tot modelul (1,6 GB); apoi rămâne marcajul.
                jurnal.info("Verific o dată modelul de transcriere (SHA-256), în fundal…")
                gresite = pregatire.fisiere_model_gresite(complet=True)
                if gresite:
                    jurnal.atentionare(f"Modelul nu se potrivește cu revizia fixată: {gresite}")
                    self.coada.trimite(
                        self._arata_probleme_instalare,
                        [f"Modelul de transcriere nu se potrivește ({', '.join(gresite)})."],
                    )
                else:
                    jurnal.info("Modelul de transcriere a fost verificat (SHA-256).")
        except Exception as exc:
            jurnal.atentionare(f"Verificarea completă a modelului a eșuat: {exc}")
        if not self._instalarea_este_completa():
            probleme = list(getattr(self, "_probleme_instalare", []))
            jurnal.atentionare(f"La pornire: instalare incompletă: {probleme}")
            self.coada.trimite(self._arata_probleme_instalare, probleme)

    def _arata_probleme_instalare(self, probleme: list) -> None:
        if probleme:
            self.bara_stare.arata(
                "Atenție", f"{probleme[0]} Detalii în ecranul „Verificare”.", "atentie"
            )

    def _verifica_codecurile_la_pornire(self) -> None:
        def in_fundal() -> None:
            try:
                are_nevoie = codecuri.are_nevoie()
            except Exception as exc:
                jurnal.atentionare(f"Verificarea părților audio a eșuat: {exc}")
                return
            if are_nevoie:
                self.coada.trimite(self._codecuri_lipsa)

        threading.Thread(target=in_fundal, name="codecuri-pornire", daemon=True).start()

    def _codecuri_lipsa(self) -> None:
        self.bara_stare.arata("Pregătesc", "Programul pregătește fișierele audio.", "lucru")

    def _intreaba_de_text_recuperat(self) -> None:
        """Întreabă utilizatorul dacă vrea să recupereze textul nesalvat."""
        from .. import biblioteca
        try:
            rezultat = biblioteca.citeste_recuperare()
        except Exception:
            rezultat = None
        if rezultat:
            text, marca, moment = rezultat
            raspuns = comun.dialog(
                self,
                "Recuperează textul nesalvat?",
                f"Ai un text nesalvat de la {moment or 'ultima sesiune'}. Vrei să-l recuperezi?",
                [("Recuperează", "principal"), ("Șterge", "secundar"), ("Înapoi", "secundar")],
                implicit=0,
                anulare=2,
            )
            if raspuns == 0:
                self.editor.set_text(text)
                self.stare.text = text
                self.bara_stare.arata(
                    "Recuperat", "Textul nesalvat a fost recunoscut.", "succes"
                )
            elif raspuns == 1:
                try:
                    from .. import biblioteca as bib
                    bib.sterge_recuperare()
                except Exception:
                    pass

    def _intreaba_de_lucrul_neterminat(self) -> None:
        """Verifică dacă există lucru neterminat și informează utilizatorul."""
        if self.stare.text and self.stare.text.strip():
            self.bara_stare.arata(
                "Lucru neterminat",
                f"Ai {self.stare.numara_cuvinte()} cuvinte nesalvate. Salvează documentul.",
                "atentie",
            )

    def _verifica_driverele_la_pornire(self) -> None:
        """Verifică driverele la pornire."""
        try:
            from .. import drivere as drivere_mod
            drivere_mod.verifica()
        except Exception:
            pass

    def _porneste_tur(self) -> None:
        tur = TurPrimulRulez(self, la_final=self._dupa_tur)
        tur.exec()

    def _dupa_tur(self) -> None:
        self.configurare.tur_vazut = True
        config_modul.salveaza(self.configurare)

    def _dupa_salvare_setari(self, config) -> None:
        """Aplică setările după salvare."""
        comun.aplica_tema(getattr(config, "mod_afisare", "windows"))
        comun.pregateste_fonturi(self)
        comun.mareste_scris(getattr(config, "marire_scris", 100) / 100.0)
        self.editor.actualizeaza_font()
        self.editor.actualizeaza_etichete()
        self._porneste_scurtaturile_globale(
            bool(getattr(config, "scurtaturi_globale", False))
        )

    def _reimprospateaza_ultimele(self) -> None:
        """Reîmprospătează „Recente” și lista dictărilor."""
        try:
            self.lista_dictari.reimprospateaza()
        except Exception:
            pass
        self.menu_recente.clear()
        try:
            from .. import biblioteca
            documente = biblioteca.ultimele_documente()
        except Exception:
            documente = []
        if not documente:
            act = self.menu_recente.addAction("(nu există documente încă)")
            act.setEnabled(False)
            self.menu_recente.setEnabled(False)
            return
        self.menu_recente.setEnabled(True)
        for elem in documente:
            cale = Path(elem.cale)
            self.menu_recente.addAction(
                elem.nume, lambda c=cale: self._deschide_document_ales(c)
            )

    def _dupa_scriere(self) -> None:
        """Apelat după ce utilizatorul scrie în editor."""
        self.stare.text = self.editor.text()
        self.stare.marcheaza_modificat()

    def _salvare_automata(self) -> None:
        """Salvează automat textul curent pentru recuperare."""
        text = self.editor.text()
        if text.strip():
            from .. import biblioteca
            try:
                biblioteca.scrie_recuperare(text, self.stare.marca or "autosave")
            except Exception:
                pass

    def _salvare_automata_fisier(self, destinatie) -> None:
        """Șterge copia de siguranță după salvare reală."""
        from .. import biblioteca
        try:
            biblioteca.sterge_recuperare()
        except Exception:
            pass

    def _deschide_in_libreoffice(self, cale: Path) -> bool:
        return libreoffice.deschide_in_writer(cale)[0]

    def closeEvent(self, event) -> None:
        # Protecție la pierderea textului: dacă există text nesalvat, întrebăm.
        if self._text_nesalvat():
            raspuns = comun.dialog(
                self,
                "Text nesalvat",
                "Ai un text nesalvat. Ce vrei să faci înainte de a închide programul?",
                [
                    ("Salvează și închide", "principal"),
                    ("Nu salva", "secundar"),
                    ("Înapoi", "secundar"),
                ],
                implicit=2,
                anulare=2,
            )
            if raspuns == 2 or raspuns is None:
                # Nu se închide; textul rămâne pe ecran.
                event.ignore()
                return
            if raspuns == 0:
                if not self._salveaza_la_inchidere():
                    event.ignore()
                    return
        self._se_inchide = True
        self.coada.opreste()
        try:
            geometrie = self.saveGeometry()
            self.configurare.geometrie_fereastra = geometrie.data().decode("latin-1")
            config_modul.salveaza(self.configurare)
        except Exception:
            pass
        event.accept()

    def _text_nesalvat(self) -> bool:
        """Există text pe ecran care nu a fost salvat ca document."""
        return bool(self.editor.text().strip()) and (
            getattr(self.stare, "nesalvat", False)
            or getattr(self.stare, "document_cale", None) is None
        )

    def _salveaza_la_inchidere(self) -> bool:
        """Salvează documentul la închidere; întoarce True dacă a reușit."""
        text = self.editor.text()
        if not text.strip():
            return True
        from .. import documente
        destinatie = biblioteca.nume_unic(
            biblioteca.folder("documente"),
            biblioteca.nume_legat(self.stare.marca or "document", ".docx"),
        )
        try:
            documente.salveaza(text, destinatie, titlu=self.stare.marca or "Document")
        except Exception as exc:
            comun.dialog_eroare(
                self, "Nu am putut salva documentul", exc
            )
            return False
        self._cripteaza_daca_cere(destinatie)
        self.stare.document_cale = destinatie
        self.stare.marcheaza_salvat()
        return True


def ruleaza(optiuni=None) -> int:
    """Pornește programul: fereastra principală, apoi curățenie la închidere."""
    # Pe Windows, un identificator propriu face ca bara de activități să arate iconița
    # programului, nu pe cea a lui Python (contează mai ales la pornirea cu pythonw.exe).
    # Trebuie setat înainte să apară vreo fereastră; e același ca în instalator\setup.iss.
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DTED.DictareTranscriere")
    except Exception:
        pass
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setApplicationName(NUME_AFISAT)
    # Iconița pentru toate ferestrele programului (și dialogurile), nu doar pentru cea principală.
    ico = Path(__file__).parent.parent / "iconita_dictare.ico"
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))
    aplicatie = Aplicatie(optiuni)
    aplicatie.show()
    return app.exec()
