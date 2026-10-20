"""Ecranul „Setări” PySide6: toate alegerile programului, pe rânduri ușor de citit.

Înlocuiește ``ui_setari.py`` (Tkinter). Logica este aceeași:

1. Unde se salvează documentele — folder + schimbă/revino/deschide
2. Limba vorbită — lista de limbi
3. Microfonul folosit — „Automat” sau un microfon anume
4. Difuzorul folosit — „Automat” sau o ieșire de sunet anume
5. Cum transcrie — automat / doar procesor / doar placă video
6. Salvare automată — text de siguranță + document final
7. Programul de scris — LibreOffice sau altul
8. Afișarea textului — mărime, wrap, font, spațiere, lățime, margină
9. Aspect — luminos / întunecat / ca Windows
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import (
    biblioteca,
    cai,
    config as config_modul,
    constante,
    dispozitive,
    erori,
    jurnal,
    libreoffice,
    programe_scris,
    sisteme,
)
from . import comun
from .comun import (
    BaraStare,
    Buton,
    ZonaDerulare,
    alege_fisier_audio,
    alege_folder,
    anunta,
    dialog,
    dialog_eroare,
    eticheta,
    fonturi,
    seteaza_rol,
)
from ..constante import LIMBI

#: Din câte în câte secunde se salvează singur textul de siguranță.
SECUNDE_SALVARE_AUTOMATA = 30

#: Opțiunile de transcriere.
OPTIUNI_TRANSCRIERE: tuple[tuple[str, str, str], ...] = (
    ("auto", "Automat (recomandat)", "Programul alege singur ce merge mai bine."),
    ("cpu", "Doar procesorul (fără placă video)", "Mai încet, dar merge pe orice calculator."),
    ("cuda", "Doar placa video", "Cel mai rapid, dacă placa video are driver instalat."),
)

#: Textul pentru alegerea automată a unui dispozitiv de sunet.
AUTOMAT = "Automat (cel ales de Windows)"

#: Secțiunile ferestrei de setări (listă stânga + pagini dreapta, UX-17).
#: Fiecare secțiune e o listă de metode ``_rand_*`` care îi construiesc rândurile.
SECTIUNI: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Documente", ("_rand_folder",)),
    ("Limbă și termeni", ("_rand_limba", "_rand_termeni")),
    ("Sunet", ("_rand_microfon", "_rand_difuzor")),
    ("Transcriere și salvare", ("_rand_transcriere", "_rand_salvare", "_rand_program")),
    ("Aspect", ("_rand_afisare", "_rand_aspect")),
)


class _DialogAlegere(QDialog):
    """Dialog propriu de alegere dintr-o listă (limbă, dispozitiv, program)."""

    def __init__(
        self,
        parinte: QWidget,
        titlu: str,
        text: str,
        optiuni: list[tuple[str, str]],
        ales: str = "",
    ):
        super().__init__(parinte)
        self.setWindowTitle(titlu)
        self.setMinimumWidth(500)
        self.rezultat: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        et_titlu = QLabel(titlu)
        et_titlu.setFont(fonturi("titlu"))
        layout.addWidget(et_titlu)

        et_text = QLabel(text)
        et_text.setFont(fonturi("baza"))
        seteaza_rol(et_text, "secundar")
        et_text.setWordWrap(True)
        layout.addWidget(et_text)

        self.lista = QListWidget()
        self.lista.setFont(fonturi("baza"))
        self._chei: list[str] = []
        for eticheta, cheie in optiuni:
            self.lista.addItem(eticheta)
            self._chei.append(cheie)
            if ales and cheie == ales:
                self.lista.setCurrentItem(self.lista.item(self.lista.count() - 1))
        self.lista.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.lista, stretch=1)

        butoane = QDialogButtonBox()
        btn_alege = Buton(self, "Alege", self.accept, fel="principal", latime=200, inaltime=40)
        btn_renunta = Buton(self, "Renunță", self.reject, latime=190, inaltime=40)
        butoane.addButton(btn_alege, QDialogButtonBox.ButtonRole.AcceptRole)
        butoane.addButton(btn_renunta, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(butoane)

    def accept(self) -> None:
        item = self.lista.currentItem()
        if item is not None:
            index = self.lista.row(item)
            if 0 <= index < len(self._chei):
                self.rezultat = self._chei[index]
        super().accept()


def _alege_din_lista(
    parinte: QWidget, titlu: str, text: str, optiuni: list[tuple[str, str]], ales: str = ""
) -> str | None:
    if not optiuni:
        return None
    dlg = _DialogAlegere(parinte, titlu, text, optiuni, ales)
    dlg.exec()
    return dlg.rezultat


class FereastraSetari(QDialog):
    """Fereastra „Setări”, cu toate alegerile programului pe rânduri."""

    def __init__(self, parinte: QWidget, config_obj=None, la_salvare=None):
        super().__init__(parinte)
        self.config = config_obj if config_obj is not None else config_modul.Config()
        self.la_salvare = la_salvare
        self._stare_inceput = self._copie()
        self.setWindowTitle("Setări")
        self.setMinimumSize(620, 400)
        self.resize(1040, 720)
        comun.centrat(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        titlu = QLabel("Setări")
        titlu.setFont(fonturi("titlu"))
        layout.addWidget(titlu)

        et = eticheta(
            self,
            "Schimbă doar ce ai nevoie; fiecare rând spune pe scurt la ce folosește. "
            "La sfârșit apasă «Salvează setările».",
            "baza",
        )
        et.setWordWrap(True)
        layout.addWidget(et)

        # Listă stânga (secțiuni) + pagini dreapta (UX-17).
        rand_central = QHBoxLayout()
        rand_central.setSpacing(10)

        self.lista_sectiuni = QListWidget()
        self.lista_sectiuni.setObjectName("lista_sectiuni")
        self.lista_sectiuni.setMaximumWidth(200)
        self.lista_sectiuni.setFont(fonturi("buton"))
        self.lista_sectiuni.currentRowChanged.connect(self._arata_sectiune)
        rand_central.addWidget(self.lista_sectiuni)

        self.stack = QStackedWidget()
        rand_central.addWidget(self.stack, stretch=1)
        layout.addLayout(rand_central, stretch=1)

        for titlu, metode in SECTIUNI:
            pagina = QWidget()
            page_layout = QVBoxLayout(pagina)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(0)
            zona = ZonaDerulare(pagina, latime_minima=680)
            page_layout.addWidget(zona)
            self.stack.addWidget(pagina)
            self.lista_sectiuni.addItem(titlu)

            self._corp_layout = zona.interior.layout()
            self._corp_layout.setSpacing(10)
            for metoda in metode:
                getattr(self, metoda)()
            self._corp_layout.addStretch(1)

        self.lista_sectiuni.setCurrentRow(0)
        self._arata_sectiune(0)

        self.linie_stare = BaraStare(self)
        layout.addWidget(self.linie_stare)

        jos = QHBoxLayout()
        btn_salveaza = Buton(self, "Salvează setările", self._salveaza, fel="principal", latime=300, inaltime=40)
        btn_inchide = Buton(self, "Închide", self.reject, latime=190, inaltime=40)
        btn_ajutor = Buton(self, "Ajutor pentru acest ecran", self._ajutor, scurtatura="F1", latime=170, inaltime=40)
        jos.addWidget(btn_salveaza)
        jos.addWidget(btn_inchide)
        jos.addStretch(1)
        jos.addWidget(btn_ajutor)
        layout.addLayout(jos)

        self._arata_toate()

    # ------------------------------------------------------------------ construcție rânduri

    def _arata_sectiune(self, index: int) -> None:
        """Afișează pagina din dreapta pentru secțiunea aleasă în listă."""
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)

    def _card(self, titlu: str, explicatie: str) -> QWidget:
        """Un rând de setare: titlu, explicație și un container pentru controale."""
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(6)

        et_titlu = QLabel(titlu)
        et_titlu.setFont(fonturi("buton"))
        seteaza_rol(et_titlu, "titlu")
        cl.addWidget(et_titlu)

        et_exp = QLabel(explicatie)
        et_exp.setFont(fonturi("baza"))
        seteaza_rol(et_exp, "secundar")
        et_exp.setWordWrap(True)
        cl.addWidget(et_exp)

        self._corp_layout.addWidget(card)
        return card

    def _valoare(self, parinte: QWidget, text: str = "") -> QLabel:
        """Eticheta care arată valoarea aleasă acum pe un rând."""
        et = QLabel(text)
        et.setFont(fonturi("buton"))
        et.setWordWrap(True)
        parinte.layout().addWidget(et)
        return et

    def _rand_folder(self) -> None:
        card = self._card(
            "Unde se salvează documentele",
            "Aici ajung documentele noi pe care le salvezi. Locul se poate schimba oricând.",
        )
        self.eticheta_folder = self._valoare(card, "")
        rand = QHBoxLayout()
        btn_schimba = Buton(card, "Schimbă folderul", self._schimba_folder, latime=250, inaltime=40)
        btn_implicit = Buton(card, "Revino la locul implicit", self._folder_implicit, latime=290, inaltime=40)
        btn_deschide = Buton(card, "Deschide folderul", self._deschide_folder, latime=220, inaltime=40)
        rand.addWidget(btn_schimba)
        rand.addWidget(btn_implicit)
        rand.addWidget(btn_deschide)
        rand.addStretch(1)
        card.layout().addLayout(rand)

    def _rand_limba(self) -> None:
        card = self._card(
            "Limba vorbită",
            "În ce limbă vorbești, ca programul să scrie corect.",
        )
        self.eticheta_limba = self._valoare(card, "")
        btn = Buton(card, "Alege limba", self._schimba_limba, latime=220, inaltime=40)
        card.layout().addWidget(btn)

    def _rand_termeni(self) -> None:
        card = self._card(
            "Nume și termeni",
            "Numele și cuvintele pe care le folosești des (persoane, localități, "
            "termeni tehnici), despărțite prin virgulă. Ajută programul să le scrie corect.",
        )
        self.edit_termeni = QLineEdit()
        self.edit_termeni.setPlaceholderText("ex.: Ion Popescu, Cluj-Napoca, hipotermie, ANAF")
        self.edit_termeni.setClearButtonEnabled(True)
        self.edit_termeni.setFont(fonturi("baza"))
        card.layout().addWidget(self.edit_termeni)

    def _rand_microfon(self) -> None:
        card = self._card(
            "Microfonul folosit",
            "Microfonul de la dictare. Alegerea „Automat” însemnă că îl alege Windows.",
        )
        self.eticheta_microfon = self._valoare(card, "")
        btn = Buton(card, "Alege microfonul", self._schimba_microfon, latime=250, inaltime=40)
        card.layout().addWidget(btn)

    def _rand_difuzor(self) -> None:
        card = self._card(
            "Difuzorul folosit",
            "Unde se aude sunetul de probă și ce s-a înregistrat. „Automat” înseamnă că îl alege Windows.",
        )
        self.eticheta_difuzor = self._valoare(card, "")
        btn = Buton(card, "Alege difuzorul", self._schimba_difuzor, latime=250, inaltime=40)
        card.layout().addWidget(btn)

    def _rand_transcriere(self) -> None:
        card = self._card(
            "Cum transcrie",
            "Ce folosește programul la transcriere. „Automat” merge bine pe aproape orice calculator.",
        )
        valoare = self.config.dispozitiv if self.config.dispozitiv in ("auto", "cpu", "cuda") else "auto"
        self.var_dispozitiv = valoare
        rand = QHBoxLayout()
        for cod, text, explicatie in OPTIUNI_TRANSCRIERE:
            rb = QCheckBox(text)
            rb.setFont(fonturi("baza"))
            rb.setChecked(cod == valoare)
            rb.toggled.connect(lambda checked, c=cod: self._seteaza_dispozitiv(c, checked))
            rand.addWidget(rb)
            et = QLabel(explicatie)
            et.setFont(fonturi("mica"))
            seteaza_rol(et, "secundar")
            et.setWordWrap(True)
            et.setMinimumWidth(400)
            et.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
            rand.addWidget(et)
            rand.addStretch(1)
        card.layout().addLayout(rand)
        # Starea plăcii video, citită acum (motor.STARE_PLACA_VIDEO).
        from .. import motor

        try:
            text_placa = motor.descriere_placa_video()
        except Exception as exc:
            text_placa = f"Placa video: nu am putut verifica ({exc})."
        self.eticheta_placa = QLabel(text_placa)
        self.eticheta_placa.setFont(fonturi("baza"))
        self.eticheta_placa.setWordWrap(True)
        card.layout().addWidget(self.eticheta_placa)
        from PySide6.QtWidgets import QPushButton

        self.buton_cuda = QPushButton("Descarcă bibliotecile pentru placa video (aprox. 1,2 GB)")
        self.buton_cuda.setFont(fonturi("baza"))
        self.buton_cuda.clicked.connect(self._descarca_cuda)
        card.layout().addWidget(self.buton_cuda)
        self.actualizeaza_placa_video()

    def _aplicatia_principala(self):
        widget = self.parent()
        while widget is not None and not hasattr(widget, "descarca_cuda_la_cerere"):
            widget = widget.parent()
        return widget

    def _descarca_cuda(self) -> None:
        aplicatie = self._aplicatia_principala()
        if aplicatie is not None:
            aplicatie.descarca_cuda_la_cerere()
        self.actualizeaza_placa_video()

    def actualizeaza_placa_video(self) -> None:
        """Recitește motor.STARE_PLACA_VIDEO și starea salvată a bibliotecilor."""
        from .. import motor, pregatire

        try:
            text = motor.descriere_placa_video()
            extra = pregatire.text_stare_cuda(self.config)
            self.eticheta_placa.setText(text + ("\n" + extra if extra else ""))
            self.buton_cuda.setVisible(bool(extra) and self._aplicatia_principala() is not None)
        except Exception as exc:
            self.eticheta_placa.setText(f"Placa video: nu am putut verifica ({exc}).")
            self.buton_cuda.setVisible(False)

    def _seteaza_dispozitiv(self, cod: str, checked: bool) -> None:
        if checked:
            self.var_dispozitiv = cod

    def _rand_salvare(self) -> None:
        card = self._card(
            "Salvare automată",
            "Cât de des se păstrează textul ca să nu se piardă nimic, și dacă documentul final se salvează singur după transcriere.",
        )
        try:
            salveaza_singur = int(self.config.salvare_automata_secunde) > 0
        except (TypeError, ValueError):
            salveaza_singur = True
        self.var_salvare_auto = salveaza_singur
        self._rand_da_nu(
            card,
            "salvare_auto",
            f"Salvează singur textul, din {SECUNDE_SALVARE_AUTOMATA} în {SECUNDE_SALVARE_AUTOMATA} de secunde",
            salveaza_singur,
        )
        self.var_document_singur = bool(self.config.salveaza_automat)
        self._rand_da_nu(
            card,
            "document_singur",
            "Salvează documentul final singur, imediat după transcriere",
            self.var_document_singur,
        )

    def _rand_da_nu(self, parinte: QWidget, cheie: str, text: str, valoare: bool) -> None:
        rand = QHBoxLayout()
        et = QLabel(text)
        et.setFont(fonturi("baza"))
        et.setWordWrap(True)
        et.setMinimumWidth(500)
        et.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        rand.addWidget(et)
        rb_da = QCheckBox("Da")
        rb_nu = QCheckBox("Nu")
        rb_da.setFont(fonturi("baza"))
        rb_nu.setFont(fonturi("baza"))
        rb_da.setChecked(valoare)
        rb_nu.setChecked(not valoare)

        def da_toggled(checked):
            if checked:
                rb_nu.setChecked(False)
            setattr(self, cheie, checked)

        def nu_toggled(checked):
            if checked:
                rb_da.setChecked(False)
            setattr(self, cheie, not checked)

        rb_da.toggled.connect(da_toggled)
        rb_nu.toggled.connect(nu_toggled)
        rand.addWidget(rb_da)
        rand.addWidget(rb_nu)
        rand.addStretch(1)
        parinte.layout().addLayout(rand)

    def _rand_program(self) -> None:
        card = self._card(
            "Programul de scris",
            "În ce program se deschid documentele finale. Programul de la început este LibreOffice Writer.",
        )
        self.eticheta_program = self._valoare(card, "")
        rand = QHBoxLayout()
        btn_schimba = Buton(card, "Alege alt program", self._schimba_program, latime=260, inaltime=40)
        btn_implicit = Buton(card, "Revino la LibreOffice", self._program_implicit, latime=290, inaltime=40)
        rand.addWidget(btn_schimba)
        rand.addWidget(btn_implicit)
        rand.addStretch(1)
        card.layout().addLayout(rand)

    def _rand_afisare(self) -> None:
        card = self._card(
            "Afișarea textului",
            "Cum se vede textul în editor: mărimea scrisului, fontul, rândurile lungi, spațierea și marginile.",
        )

        # Mărimea scrisului
        rand = QHBoxLayout()
        et_lab = QLabel("Mărimea scrisului:")
        et_lab.setFont(fonturi("baza"))
        rand.addWidget(et_lab)
        self.slider_marime = QSlider(Qt.Orientation.Horizontal)
        self.slider_marime.setRange(80, 200)
        self.slider_marime.setValue(int(getattr(self.config, "marire_scris", 100)))
        self.slider_marime.setMinimumWidth(220)
        self.slider_marime.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rand.addWidget(self.slider_marime)
        et_pct = QLabel("%")
        et_pct.setFont(fonturi("baza"))
        seteaza_rol(et_pct, "secundar")
        rand.addWidget(et_pct)
        btn_minus = Buton(card, "A-", lambda: self._schimba_marime(-10), latime=80, inaltime=36)
        btn_plus = Buton(card, "A+", lambda: self._schimba_marime(+10), latime=80, inaltime=36)
        rand.addWidget(btn_minus)
        rand.addWidget(btn_plus)
        rand.addStretch(1)
        card.layout().addLayout(rand)

        self.var_wrap = QCheckBox("Rândurile lungi trec pe rândul următor")
        self.var_wrap.setChecked(bool(getattr(self.config, "wrap_text", True)))
        self.var_wrap.setFont(fonturi("baza"))
        card.layout().addWidget(self.var_wrap)

        rand2 = QHBoxLayout()
        et_font = QLabel("Tipul de scris:")
        et_font.setFont(fonturi("baza"))
        rand2.addWidget(et_font)
        self.combo_font = QComboBox()
        self.combo_font.addItems(["Implicit", "Segoe UI", "Arial", "Tahoma", "Calibri"])
        font_curent = getattr(self.config, "font_text", "") or "Implicit"
        self.combo_font.setCurrentText(font_curent)
        self.combo_font.setMinimumWidth(180)
        self.combo_font.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        rand2.addWidget(self.combo_font)
        rand2.addStretch(1)
        card.layout().addLayout(rand2)

        rand3 = QHBoxLayout()
        et_sp = QLabel("Distanța dintre rânduri:")
        et_sp.setFont(fonturi("baza"))
        rand3.addWidget(et_sp)
        self.combo_spatiere = QComboBox()
        self.combo_spatiere.addItems(["normal", "mare", "foarte_mare"])
        self.combo_spatiere.setCurrentText(getattr(self.config, "spatiere_linii", "normal"))
        self.combo_spatiere.setMinimumWidth(160)
        self.combo_spatiere.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        rand3.addWidget(self.combo_spatiere)
        rand3.addStretch(1)
        card.layout().addLayout(rand3)

        rand4 = QHBoxLayout()
        et_lat = QLabel("Lățimea maximă a rândului:")
        et_lat.setFont(fonturi("baza"))
        rand4.addWidget(et_lat)
        self.combo_latime = QComboBox()
        self.combo_latime.addItems(["tot", "îngust"])
        self.combo_latime.setCurrentText(getattr(self.config, "latime_max_rand", "tot"))
        self.combo_latime.setMinimumWidth(120)
        self.combo_latime.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        rand4.addWidget(self.combo_latime)
        rand4.addStretch(1)
        card.layout().addLayout(rand4)

        rand5 = QHBoxLayout()
        et_marg = QLabel("Marginile textului (px):")
        et_marg.setFont(fonturi("baza"))
        rand5.addWidget(et_marg)
        from PySide6.QtWidgets import QSpinBox
        self.spin_margini = QSpinBox()
        self.spin_margini.setRange(0, 40)
        self.spin_margini.setValue(int(getattr(self.config, "margini_text", 8)))
        self.spin_margini.setMinimumWidth(60)
        self.spin_margini.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        rand5.addWidget(self.spin_margini)
        rand5.addStretch(1)
        card.layout().addLayout(rand5)

        self.eticheta_preview = QLabel("Știința și înțelepciunea țăranului român.")
        self.eticheta_preview.setFont(fonturi("baza"))
        seteaza_rol(self.eticheta_preview, "secundar")
        self.eticheta_preview.setWordWrap(True)
        self.eticheta_preview.setMinimumWidth(600)
        self.eticheta_preview.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        card.layout().addWidget(self.eticheta_preview)

        btn_reset = Buton(card, "Revino la setările inițiale", self._reset_afisare, latime=260, inaltime=36)
        card.layout().addWidget(btn_reset)

    def _schimba_marime(self, delta: int) -> None:
        val = self.slider_marime.value() + delta
        val = max(80, min(200, val))
        self.slider_marime.setValue(val)

    def _reset_afisare(self) -> None:
        self.slider_marime.setValue(100)
        self.var_wrap.setChecked(True)
        self.combo_font.setCurrentText("Implicit")
        self.combo_spatiere.setCurrentText("normal")
        self.combo_latime.setCurrentText("tot")
        self.spin_margini.setValue(8)

    def _rand_aspect(self) -> None:
        card = self._card(
            "Aspect",
            "Modul de afișare: luminos, întunecat sau ca Windows.",
        )
        rand = QHBoxLayout()
        et_lab = QLabel("Mod de afișare:")
        et_lab.setFont(fonturi("baza"))
        rand.addWidget(et_lab)
        self.combo_mod = QComboBox()
        self.combo_mod.addItems(["windows", "luminos", "întunecat"])
        self.combo_mod.setCurrentText(getattr(self.config, "mod_afisare", "windows"))
        self.combo_mod.setMinimumWidth(160)
        self.combo_mod.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.combo_mod.currentTextChanged.connect(self._aplica_mod)
        rand.addWidget(self.combo_mod)
        rand.addStretch(1)
        card.layout().addLayout(rand)

    def _aplica_mod(self, val: str) -> None:
        try:
            self.config.mod_afisare = val
            comun.aplica_tema(val)
        except Exception as exc:
            jurnal.atentionare(f"Modul de afișare nu a putut fi aplicat: {exc}")

    # ------------------------------------------------------------------ arătare valori

    def _arata_toate(self) -> None:
        self._arata_folder()
        self._arata_limba()
        self._arata_termeni()
        self._arata_microfon()
        self._arata_difuzor()
        self._arata_program()

    def _arata_termeni(self) -> None:
        self.edit_termeni.setText(getattr(self.config, "termeni", "") or "")

    def _arata_folder(self) -> None:
        try:
            cale = config_modul.director_iesiri(self.config)
        except Exception:
            cale = cai.director_iesiri()
        text = f"Se salvează în: {cale}"
        if not (getattr(self.config, "director_iesiri", "") or "").strip():
            text += "\n(locul de la început: folderul „Documente”)"
        self.eticheta_folder.setText(text)

    def _arata_limba(self) -> None:
        nume = {cod: eticheta for eticheta, cod in LIMBI}
        aleasa = nume.get(self.config.limba, self.config.limba or "Română")
        self.eticheta_limba.setText(f"Acum: {aleasa}")

    def _arata_microfon(self) -> None:
        cheie = (getattr(self.config, "microfon_preferat", "") or "").strip()
        if not cheie:
            self.eticheta_microfon.setText(f"Acum: {AUTOMAT}")
            return
        gasit = self._dispozitiv_dupa_cheie(cheie, este_intrare=True)
        if gasit is not None:
            self.eticheta_microfon.setText(f"Acum: {gasit.descriere()}")
            return
        self.eticheta_microfon.setText(
            "Acum: microfonul ales mai înainte nu se vede pe calculator.\nSe folosește cel ales de Windows."
        )

    def _arata_difuzor(self) -> None:
        cheie = (getattr(self.config, "difuzor_preferat", "") or "").strip()
        if not cheie:
            self.eticheta_difuzor.setText(f"Acum: {AUTOMAT}")
            return
        gasit = self._dispozitiv_dupa_cheie(cheie, este_intrare=False)
        if gasit is not None:
            self.eticheta_difuzor.setText(f"Acum: {gasit.descriere()}")
            return
        self.eticheta_difuzor.setText(
            "Acum: difuzorul ales mai înainte nu se vede pe calculator.\nSe folosește cel ales de Windows."
        )

    def _arata_program(self) -> None:
        cheie = (getattr(self.config, "program_scris_preferat", "") or "").strip()
        if cheie:
            program = None
            try:
                program = programe_scris.dupa_cheie(cheie)
            except Exception as exc:
                jurnal.atentionare(f"Nu am putut verifica programul de scris ales: {exc}")
            if program is not None:
                self.eticheta_program.setText(f"Programul ales: {program.nume} (ales de tine)")
                return
            nume = getattr(self.config, "program_scris_nume", "") or "Programul ales mai înainte"
            self.eticheta_program.setText(
                f"Programul ales: {nume} nu mai este pe calculator.\nSe folosește programul de la început."
            )
            return
        text = libreoffice.nume_pentru_utilizator()
        try:
            stare = libreoffice.stare()
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut verifica LibreOffice: {exc}")
            stare = None
        if stare is None:
            self.eticheta_program.setText(f"Programul ales: {text}")
            return
        if not stare.gasit:
            self.eticheta_program.setText(f"Programul ales: {text}\n(nu este instalat încă)")
            return
        versiune = f", versiunea {stare.versiune}" if stare.versiune else ""
        self.eticheta_program.setText(f"Programul ales: {text} (instalat{versiune})")

    # ------------------------------------------------------------------ dispozitive

    def _optiuni_microfoane(self) -> list[tuple[str, str]]:
        optiuni: list[tuple[str, str]] = [(AUTOMAT, "")]
        for dispozitiv in self._dispozitive(este_intrare=True):
            optiuni.append((dispozitiv.descriere(), dispozitiv.cheie))
        return optiuni

    def _optiuni_difuzoare(self) -> list[tuple[str, str]]:
        optiuni: list[tuple[str, str]] = [(AUTOMAT, "")]
        for dispozitiv in self._dispozitive(este_intrare=False):
            optiuni.append((dispozitiv.descriere(), dispozitiv.cheie))
        return optiuni

    def _dispozitive(self, este_intrare: bool) -> list:
        try:
            return list(dispozitive.microfoane() if este_intrare else dispozitive.iesiri())
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut citi dispozitivele de sunet: {exc}")
            return []

    def _dispozitiv_dupa_cheie(self, cheie: str, este_intrare: bool):
        try:
            return dispozitive.alege_dupa_cheie(
                cheie, self._dispozitive(este_intrare), este_intrare=este_intrare
            )
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut verifica dispozitivul ales: {exc}")
            return None

    # ------------------------------------------------------------------ schimbări

    def _schimba_folder(self) -> None:
        cale = alege_folder(self, self._folder_curent())
        if cale is None:
            return
        se_poate_scrie, mesaj = biblioteca.verificare_folder(cale)
        if not se_poate_scrie:
            self.linie_stare.arata("Neschimbat", "folderul a rămas cel de dinainte.", "atentie")
            dialog_eroare(
                self,
                "Folderul nu poate fi folosit",
                erori.folder_nu_se_poate_scrie(str(cale), detalii=mesaj),
            )
            return
        self.config.director_iesiri = str(cale)
        self._arata_folder()
        self.linie_stare.arata(
            "Schimbat",
            f"documentele noi se salvează în {cale}. Apasă «Salvează setările» ca să rămână așa.",
            "bine",
        )

    def _dupa_eroare_folder(self, fel: str) -> None:
        if fel == erori.INCERCARE_DIN_NOU:
            self._schimba_folder()
        elif fel == erori.DESCHIDE_FOLDER:
            self._deschide_folder()

    def _folder_implicit(self) -> None:
        self.config.director_iesiri = ""
        self._arata_folder()
        self.linie_stare.arata(
            "Schimbat", "documentele se salvează iar în folderul „Documente”.", "bine"
        )

    def _deschide_folder(self) -> None:
        if sisteme.deschide_folder(self._folder_curent()):
            self.linie_stare.arata("Arătat", "am deschis folderul documentelor.", "normal")
            return
        anunta(
            self,
            "Folderul nu s-a deschis",
            "Windows nu a putut deschide folderul acum.\n\n"
            "Probabil pentru că: folderul a fost mutat sau șters între timp.\n\n"
            "Ce faci acum: apasă «Schimbă folderul» și alege alt loc, sau încearcă din nou peste o clipă.",
        )

    def _folder_curent(self) -> Path:
        try:
            return config_modul.director_iesiri(self.config)
        except Exception:
            return cai.director_iesiri()

    def _schimba_limba(self) -> None:
        optiuni = [(eticheta, cod) for eticheta, cod in LIMBI]
        cod = _alege_din_lista(
            self,
            "Limba vorbită",
            "Alege limba în care vorbești, ca programul să scrie corect.",
            optiuni,
            self.config.limba,
        )
        if cod is None:
            return
        self.config.limba = cod
        self._arata_limba()
        nume = {cod_limba: eticheta for eticheta, cod_limba in LIMBI}
        self.linie_stare.arata(
            "Schimbat", f"limba aleasă este {nume.get(cod, cod)}.", "bine"
        )

    def _schimba_microfon(self) -> None:
        optiuni = self._optiuni_microfoane()
        if len(optiuni) <= 1:
            self._fara_dispozitive("microfoane", "microfonul")
            return
        cheie = _alege_din_lista(
            self,
            "Microfonul folosit",
            "Alege microfonul la care vorbești.",
            optiuni,
            self.config.microfon_preferat or "",
        )
        if cheie is None:
            return
        self.config.microfon_preferat = cheie
        self._arata_microfon()
        self.linie_stare.arata(
            "Schimbat",
            "microfonul ales se folosește de acum. Apasă «Salvează setările» ca să rămână așa.",
            "bine",
        )

    def _schimba_difuzor(self) -> None:
        optiuni = self._optiuni_difuzoare()
        if len(optiuni) <= 1:
            self._fara_dispozitive("difuzoare", "difuzorul")
            return
        cheie = _alege_din_lista(
            self,
            "Difuzorul folosit",
            "Alege unde vrei să se audă sunetul.",
            optiuni,
            self.config.difuzor_preferat or "",
        )
        if cheie is None:
            return
        self.config.difuzor_preferat = cheie
        self._arata_difuzor()
        self.linie_stare.arata(
            "Schimbat",
            "difuzorul ales se folosește de acum. Apasă «Salvează setările» ca să rămână așa.",
            "bine",
        )

    def _fara_dispozitive(self, ce_lipseste: str, cum_se_numește: str) -> None:
        anunta(
            self,
            f"Nu am găsit {ce_lipseste}",
            f"Pe acest calculator nu se vede acum niciun {cum_se_numește}.\n\n"
            "Probabil pentru că: dispozitivul nu este conectat sau lipsește driverul lui de sunet.\n\n"
            f"Ce faci acum: conectează {cum_se_numește} și apasă din nou butonul de alegere; "
            "verificarea sunetului se poate face din ecranul de început.",
        )

    def _schimba_program(self) -> None:
        try:
            programe = list(programe_scris.gaseste_programe())
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut căuta programele de scris: {exc}")
            programe = []
        if not programe:
            anunta(
                self,
                "Nu am găsit programe de scris",
                "Pe acest calculator nu am găsit niciun program de scris.\n\n"
                "Probabil pentru că: nu este instalat niciunul, sau este instalat într-un loc "
                "pe care Windows nu îl știe.\n\n"
                "Ce faci acum: documentele se salvează oricum (ca DOCX, ODT sau PDF) și se pot "
                "deschide cu dublu-clic.",
            )
            return
        optiuni = [(program.descriere(), program.cheie) for program in programe]
        cheie = _alege_din_lista(
            self,
            "Programul de scris",
            "Alege programul în care să se deschidă documentele finale.",
            optiuni,
            self.config.program_scris_preferat or "",
        )
        if not cheie:
            return
        program = programe_scris.dupa_cheie(cheie)
        if program is None:
            return
        if getattr(program, "implicit", False):
            self._program_implicit()
            return
        self.config.program_scris_preferat = program.cheie
        self.config.program_scris_nume = program.nume
        self._arata_program()
        self.linie_stare.arata(
            "Schimbat",
            f"documentele se deschid în {program.nume}. Apasă «Salvează setările» ca să rămână așa.",
            "bine",
        )

    def _program_implicit(self) -> None:
        self.config.program_scris_preferat = ""
        self.config.program_scris_nume = ""
        self._arata_program()
        self.linie_stare.arata(
            "Schimbat", "documentele se deschid iar în LibreOffice Writer.", "bine"
        )

    # ------------------------------------------------------------------ salvare

    def _copie(self) -> dict:
        try:
            return asdict(self.config)
        except Exception:
            return {}

    def _aduna(self) -> None:
        try:
            self.config.dispozitiv = self.var_dispozitiv
        except (AttributeError,):
            pass
        try:
            if self.var_salvare_auto:
                try:
                    cat = int(getattr(self.config, "salvare_automata_secunde", 0))
                except (TypeError, ValueError):
                    cat = 0
                if cat <= 0:
                    self.config.salvare_automata_secunde = SECUNDE_SALVARE_AUTOMATA
            else:
                self.config.salvare_automata_secunde = 0
        except (AttributeError,):
            pass
        try:
            self.config.salveaza_automat = self.var_document_singur
        except (AttributeError,):
            pass
        try:
            self.config.mod_afisare = self.combo_mod.currentText()
        except (AttributeError,):
            pass
        try:
            self.config.marire_scris = self.slider_marime.value()
        except (AttributeError,):
            pass
        try:
            self.config.wrap_text = self.var_wrap.isChecked()
        except (AttributeError,):
            pass
        try:
            font = self.combo_font.currentText()
            self.config.font_text = "" if font == "Implicit" else font
        except (AttributeError,):
            pass
        try:
            self.config.spatiere_linii = self.combo_spatiere.currentText()
        except (AttributeError,):
            pass
        try:
            self.config.latime_max_rand = self.combo_latime.currentText()
        except (AttributeError,):
            pass
        try:
            self.config.margini_text = self.spin_margini.value()
        except (AttributeError, ValueError,):
            pass
        try:
            self.config.termeni = (self.edit_termeni.text() or "").strip()
        except (AttributeError,):
            pass

    def _schimbari(self) -> bool:
        try:
            self._aduna()
            return self._copie() != self._stare_inceput
        except Exception:
            return False

    def _salveaza(self) -> None:
        self._aduna()
        if not config_modul.salveaza(self.config):
            self.linie_stare.arata(
                "Nepăstrat", "setările nu au putut fi scrise pe disc.", "problema"
            )
            comun.dialog(
                self,
                "Setările nu au putut fi păstrate.",
                "Setările nu au putut fi păstrate.\n\n"
                "Probabil pentru că: folderul programului este protejat sau discul este plin.\n\n"
                "Ce faci acum: Încearcă din nou. Dacă tot nu merge, închide programul, pornește-l "
                "din nou și schimbă doar o setare o dată.",
                [("Încearcă din nou", "principal"), ("Închide", "secundar")],
                implicit=0,
                anulare=1,
            )
            return
        self._stare_inceput = self._copie()
        self.linie_stare.arata("Salvat", "setările s-au păstrat și se folosesc de acum.", "bine")
        if self.la_salvare is not None:
            try:
                self.la_salvare(self.config)
            except Exception as exc:
                jurnal.atentionare(f"Ce urma după salvarea setărilor a eșuat: {exc}")

    def _dupa_eroare_salvare(self, fel: str) -> None:
        if fel == erori.INCERCARE_DIN_NOU:
            self._salveaza()

    def _ajutor(self) -> None:
        try:
            from .ui_ajutor import FereastraAjutor
            FereastraAjutor(self, "setari").exec()
        except Exception as exc:
            jurnal.eroare(f"Ajutorul nu s-a putut deschide: {exc}")
            anunta(self, "Ajutor", "Ajutorul nu s-a putut deschide acum. Încearcă din nou.")

    def reject(self) -> None:
        if self._schimbari():
            rezultat = dialog(
                self,
                "Setări schimbate",
                "Ai schimbat niște setări. Vrei să le păstrei înainte de a închide?",
                [
                    ("Păstrează setările", "principal"),
                    ("Nu le păstra", "secundar"),
                    ("Înapoi", "secundar"),
                ],
                implicit=0,
                anulare=2,
            )
            if rezultat is None or rezultat == 2:
                return
            if rezultat == 0:
                self._salveaza()
        super().reject()
