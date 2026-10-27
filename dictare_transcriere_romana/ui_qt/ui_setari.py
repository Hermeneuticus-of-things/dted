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
10. Parolă și criptare — parolă pentru documente + criptare la salvare
11. Confidențialitate — blocarea căilor de ieșire în timpul dictării
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
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
    ("Limbă și termeni", ("_rand_limba", "_rand_termeni", "_rand_dictionar")),
    ("Sunet", ("_rand_microfon", "_rand_difuzor", "_rand_dictare")),
    ("Comenzi vocale", ("_rand_comenzi_vocale",)),
    ("Transcriere și salvare", ("_rand_transcriere", "_rand_salvare", "_rand_program")),
    ("Taste rapide", ("_rand_taste_rapide",)),
    ("Parolă și criptare", ("_rand_parola",)),
    ("Confidențialitate", ("_rand_blocare",)),
    ("Aspect", ("_rand_afisare", "_rand_aspect")),
    ("Actualizări", ("_rand_actualizari",)),
)


#: Tastele rapide pe care utilizatorul le poate schimba: nume stabil → etichetă în română.
TASTE_RAPIDE: tuple[tuple[str, str], ...] = (
    ("dictare", "Dictează / oprește dictarea (⏺ roșu)"),
    ("asculta", "Ascultă de la semn / pauză"),
    ("stop_asculta", "Oprește ascultarea"),
    ("inapoi_5", "Derulează înapoi 5 secunde"),
    ("inainte_5", "Derulează înainte 5 secunde"),
    ("viteza_normala", "Redare cu viteză normală"),
    ("viteza_lenta", "Redare lentă"),
    ("viteza_rapida", "Redare rapidă"),
    ("de_la_capat", "Ia fraza de la capăt (șterge fraza neterminată)"),
    ("idee_noua", "Idee nouă (șterge fraza + paragraf cu tab)"),
    ("semn", "Semnul [mm:ss] în text"),
)


class PrindeTasta(QPushButton):
    """Buton care prinde combinația de taste apăsată de utilizator.

    Clic pe buton → „Apasă tastele…”, utilizatorul apasă combinația și ea
    rămâne scrisă pe buton. Esc anulează; se poate reveni la valoarea din
    fabrică oricând.
    """

    def __init__(self, secventa: str, parinte: QWidget | None = None):
        super().__init__(secventa or "—", parinte)
        self.secventa = (secventa or "").strip()
        self._prinde = False
        self.setMinimumWidth(210)
        self.clicked.connect(self._porneste_prinderea)

    def _porneste_prinderea(self) -> None:
        self._prinde = True
        self.setText("Apasă tastele…")
        self.setFocus()

    def keyPressEvent(self, eveniment) -> None:  # noqa: ANN001
        if not self._prinde:
            super().keyPressEvent(eveniment)
            return
        tasta = eveniment.key()
        if tasta in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
            return  # modificatorii singuri nu sunt o combinație
        self._prinde = False
        if tasta == Qt.Key.Key_Escape:
            self.setText(self.secventa or "—")  # anulat
            return
        try:
            combinatie = eveniment.modifiers() | Qt.Key(tasta)
        except (TypeError, ValueError):
            combinatie = None
        secventa = QKeySequence(combinatie).toString() if combinatie is not None else ""
        if not secventa:
            try:
                secventa = QKeySequence(Qt.Key(tasta)).toString()
            except (TypeError, ValueError):
                secventa = ""
        if secventa:
            self.secventa = secventa
        self.setText(self.secventa or "—")

    def pune_implicit(self, secventa: str) -> None:
        """Revenire la valoarea din fabrică (butonul „Pune tot la fel ca la început”)."""
        self.secventa = secventa
        self.setText(secventa or "—")


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
        self.lista_sectiuni.setMinimumWidth(220)
        self.lista_sectiuni.setMaximumWidth(250)
        self.lista_sectiuni.setSpacing(3)
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
            zona = ZonaDerulare(pagina, latime_minima=520)
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

    def _rand_dictionar(self) -> None:
        card = self._card(
            "Dicționar de corecturi",
            "Când corectezi un cuvânt greșit scris de program (îl ștergi și scrii "
            "corect), perechea se reține singură și se aplică de la următoarea "
            "transcriere. Lista poate fi adusă și dintr-un fișier (import).",
        )
        self.eticheta_dictionar = self._valoare(card, "")
        rand = QHBoxLayout()
        rand.addWidget(Buton(card, "Import din fișier…", self._importa_dictionar, latime=220, inaltime=40))
        rand.addWidget(Buton(card, "Export în fișier…", self._exporta_dictionar, latime=220, inaltime=40))
        rand.addStretch(1)
        card.layout().addLayout(rand)
        self._arata_dictionar()

    def _arata_dictionar(self) -> None:
        from .. import inlocuiri

        try:
            numar = len(inlocuiri.incarca())
        except Exception:
            numar = 0
        if numar:
            self.eticheta_dictionar.setText(f"Corecturi învățate: {numar}.")
        else:
            self.eticheta_dictionar.setText(
                "Corecturi învățate: niciuna încă — apar singure când corectezi textul."
            )

    def _importa_dictionar(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        from .. import inlocuiri

        cale, _ = QFileDialog.getOpenFileName(
            self,
            "Import dicționar de corecturi",
            "",
            "Dicționar (*.txt *.json *.csv);;Toate fișierele (*.*)",
        )
        if not cale:
            return
        puse, respinse = inlocuiri.importa_din_fisier(Path(cale))
        self._arata_dictionar()
        mesaj = f"{puse} perechi au fost puse în dicționar."
        if respinse:
            mesaj += (
                f"\n\n{respinse} rânduri au fost ignorate: nu erau perechi simple "
                "de un cuvânt (se acceptă „greșit -> corect”, JSON sau CSV)."
            )
        anunta(self, "Import terminat", mesaj)

    def _exporta_dictionar(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        from .. import inlocuiri

        perechi = inlocuiri.incarca()
        if not perechi:
            anunta(
                self,
                "Dicționarul e gol",
                "Nu ai încă nicio corectură învățată, deci nu e nimic de exportat.",
            )
            return
        cale, _ = QFileDialog.getSaveFileName(
            self, "Export dicționar de corecturi", "dictionar-dted.txt", "Text (*.txt);;JSON (*.json)"
        )
        if not cale:
            return
        try:
            Path(cale).write_text(inlocuiri.exporta_text(perechi), encoding="utf-8")
        except OSError:
            anunta(self, "Nu am putut scrie fișierul", "Fișierul nu s-a putut salva pe disc.")
            return
        anunta(self, "Export terminat", f"{len(perechi)} perechi au fost scrise în {Path(cale).name}.")

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

    def _rand_dictare(self) -> None:
        card = self._card(
            "Cum se aude dictarea",
            "Ajustări opționale pentru sunetul dictat; toate sunt oprite la început, "
            "ca textul să rămână întocmai ce s-a auzit.",
        )
        self.var_activare_vocala = bool(getattr(self.config, "activare_vocala", False))
        self._rand_da_nu(
            card,
            "var_activare_vocala",
            "Pornește singură dictarea când începi să vorbești (activare vocală, ca la Express Dictate)",
            self.var_activare_vocala,
        )
        self.var_auto_volum = bool(getattr(self.config, "auto_volum", True))
        self._rand_da_nu(
            card,
            "var_auto_volum",
            "Aduce singur nivelul microfonului ca să nu se distorsioneze (0 dB) și să se audă bine",
            self.var_auto_volum,
        )
        self.var_pauze = bool(getattr(self.config, "scurteaza_pauze", False))
        self._rand_da_nu(
            card,
            "var_pauze",
            "Sare peste pauzele lungi de peste 2 secunde (cerința 52)",
            self.var_pauze,
        )
        self.var_pregateste = bool(getattr(self.config, "pregateste_audio", False))
        self._rand_da_nu(
            card,
            "var_pregateste",
            "Aduce volumul la un nivel potrivit, dacă s-a vorbit prea încet (cerința 51)",
            self.var_pregateste,
        )
        self.var_scurtaturi = bool(getattr(self.config, "scurtaturi_globale", False))
        self._rand_da_nu(
            card,
            "var_scurtaturi",
            "Scurtătură globală Ctrl+Alt+D pornește/oprește dictarea din orice program (cerința 53)",
            self.var_scurtaturi,
        )

    # ------------------------------------------------------- parolă și criptare

    def _rand_comenzi_vocale(self) -> None:
        """Setări → „Comenzi vocale”: lista scurtă + pauzele care structurează textul."""
        card = self._card(
            "Comenzi rostite în timpul dictării",
            "Rostește comanda clar, cu o pauză scurtă înainte și după, ca programul să o "
            "deosebească de text. Variantele cu și fără diacritice merg la fel de bine:",
            "• structură: „paragraf nou”; „rând nou” (sau „linie nouă”);",
            "• punctuație: „punct”; „virgulă” (sau „virgula”); „punct și virgulă” (sau „punct si virgula”);",
            "  „două puncte” (sau „doua puncte”); „semn de întrebare” (sau „semn de intrebare”, „semnul întrebării”);",
            "  „semn de exclamare” (sau „semnul exclamării”);",
            "• ghilimele: „deschide ghilimele” / „închide ghilimele”;",
            "• paranteze: „deschide paranteză” / „închide paranteză”;",
            "• linii și simboluri: „cratimă”; „linie de dialog”; „linie de pauză”; „procent”; „slash”;",
            "  „ampersand” (sau „și comercial”). Lista completă și exemple: F1 → Comenzi vocale.",
        )
        card.layout().addWidget(QLabel(
            "Pauzele lungi de voce structurează singure textul: alegi aici după câte secunde "
            "de liniște continuă programul pune singur rândul nou, respectiv paragraful nou."
        ))
        rand_praguri = QHBoxLayout()
        et_rand = QLabel("Rând nou după (secunde de liniște):")
        et_rand.setFont(fonturi("baza"))
        rand_praguri.addWidget(et_rand)
        self.spin_pauza_rand = QSpinBox()
        self.spin_pauza_rand.setRange(1, 30)
        self.spin_pauza_rand.setValue(int(getattr(self.config, "pauza_rand_sec", 4) or 4))
        self.spin_pauza_rand.setSuffix(" s")
        self.spin_pauza_rand.setToolTip("Peste atâta liniște continuă, textul trece pe un rând nou")
        rand_praguri.addWidget(self.spin_pauza_rand)
        et_paragraf = QLabel("Paragraf nou după (secunde):")
        et_paragraf.setFont(fonturi("baza"))
        rand_praguri.addWidget(et_paragraf)
        self.spin_pauza_paragraf = QSpinBox()
        self.spin_pauza_paragraf.setRange(2, 60)
        self.spin_pauza_paragraf.setValue(int(getattr(self.config, "pauza_paragraf_sec", 8) or 8))
        self.spin_pauza_paragraf.setSuffix(" s")
        self.spin_pauza_paragraf.setToolTip("Peste atâta liniște continuă, începe un paragraf nou")
        rand_praguri.addWidget(self.spin_pauza_paragraf)
        rand_praguri.addStretch(1)
        card.layout().addLayout(rand_praguri)

    def _rand_taste_rapide(self) -> None:
        """Secțiunea „Taste rapide”: fiecare comandă principală are tasta ei."""
        alese = config_modul.scurtaturi(self.config)
        card = self._card(
            "Tastele rapide ale programului",
            "Clic pe un buton, apoi apasă combinația de taste pe care o vrei. "
            "Tastele noi se folosesc după ce salvezi și repornești programul. "
            "Butonul de jos pune totul la fel ca la început.",
        )
        for nume, eticheta in TASTE_RAPIDE:
            rand = QHBoxLayout()
            et = QLabel(eticheta)
            et.setFont(fonturi("baza"))
            rand.addWidget(et, stretch=1)
            buton = PrindeTasta(alese.get(nume, ""), card)
            setattr(self, f"_tasta_{nume}", buton)
            rand.addWidget(buton)
            card.layout().addLayout(rand)
        rand_implicit = QHBoxLayout()
        btn_implicit = Buton(
            card, "Pune tot la fel ca la început", self._taste_implicit, latime=300, inaltime=40
        )
        rand_implicit.addWidget(btn_implicit)
        rand_implicit.addStretch(1)
        card.layout().addLayout(rand_implicit)

    def _taste_implicit(self) -> None:
        """Revenirea la tastele din fabrică pentru TOATE comenzile."""
        for nume, _eticheta in TASTE_RAPIDE:
            buton = getattr(self, f"_tasta_{nume}", None)
            if buton is not None:
                buton.pune_implicit(config_modul.SCURTATURI_IMPLICIT.get(nume, ""))

    def _rand_parola(self) -> None:
        from .. import parola

        self._modul_parola = parola
        card = self._card(
            "Parola și criptarea documentelor",
            "Cu o parolă pusă, documentele salvate pot fi criptate (AES-256): fără parolă, "
            "conținutul lor nu se poate citi în alt program. La schimbarea parolei "
            "documentele deja criptate NU se rescriu — cheia lor rămâne aceeași.",
        )
        self.eticheta_parola = self._valoare(card, "")
        self.var_cripteaza = QCheckBox("Criptează documentele salvate")
        self.var_cripteaza.setFont(fonturi("baza"))
        self.var_cripteaza.setChecked(
            bool(getattr(self.config, "cripteaza_documente", False)) and parola.seif_definit()
        )
        card.layout().addWidget(self.var_cripteaza)
        rand = QHBoxLayout()
        rand.addWidget(Buton(card, "Pune o parolă", self._pune_parola, latime=200, inaltime=40))
        rand.addWidget(Buton(card, "Schimbă parola", self._schimba_parola_setari, latime=220, inaltime=40))
        rand.addWidget(Buton(card, "Scoate parola", self._scoate_parola, latime=200, inaltime=40))
        rand.addStretch(1)
        card.layout().addLayout(rand)
        self._arata_parola()

    def _arata_parola(self) -> None:
        try:
            definit = self._modul_parola.seif_definit()
        except Exception:
            definit = False
        if definit:
            text = "Parolă pusă. Documentele se pot cripta la salvare."
        else:
            text = "Nicio parolă pusă. Documentele se salvează normale (oricine le poate citi)."
        self.eticheta_parola.setText(text)
        self.var_cripteaza.setEnabled(definit)
        if not definit:
            self.var_cripteaza.setChecked(False)

    def _cere_parola(self, titlu: str, eticheta: str, precompletat: str = "") -> str | None:
        text, ok = QInputDialog.getText(
            self, titlu, eticheta, QLineEdit.EchoMode.Password, precompletat
        )
        return (text or "").strip() if ok else None

    def _pune_parola(self) -> None:
        parola = self._modul_parola
        if parola.seif_definit():
            anunta(
                self,
                "Există deja o parolă",
                "Ai deja o parolă pusă. Ca să o schimbi, apasă «Schimbă parola».",
            )
            return
        prima = self._cere_parola(
            "Pune o parolă",
            "Scrie parola (cel puțin 4 semne).\nParola implicită „Dictare” e deja scrisă — poți rămâne la ea:",
            constante.PAROLA_IMPLICITA,
        )
        if prima is None:
            return
        if len(prima) < 4:
            anunta(self, "Parola e prea scurtă", "Parola trebuie să aibă cel puțin 4 semne.")
            return
        a_doua = self._cere_parola(
            "Pune o parolă", "Scrie parola încă o dată, ca să fie sigur:", prima
        )
        if a_doua is None:
            return
        if prima != a_doua:
            anunta(self, "Parolele nu se potrivesc", "Cele două parole scrise nu sunt la fel. Încearcă din nou.")
            return
        seif, recuperare, _cheie = parola.defineste(prima)
        if not parola.salveaza_seif(seif):
            anunta(
                self,
                "Parola nu s-a putut păstra",
                "Seiful nu a putut fi scris pe disc (folder protejat sau disc plin). Parola NU a fost pusă.",
            )
            return
        anunta(
            self,
            "Cheia de recuperare — scrie-o pe hârtie",
            "Dacă uiți parola, documentele criptate se pot deschide NUMAI cu cheia de recuperare de mai jos.\n\n"
            f"{recuperare}\n\n"
            "Această cheie se arată o singură dată. Scrie-o pe hârtie și ține-o la loc sigur.",
        )
        self.var_cripteaza.setEnabled(True)
        self.var_cripteaza.setChecked(True)
        self._arata_parola()
        self.linie_stare.arata(
            "Gata", "parola e pusă. Bifează «Criptează documentele salvate» și apasă «Salvează setările».", "bine"
        )

    def _schimba_parola_setari(self) -> None:
        parola = self._modul_parola
        seif = parola.incarca_seif()
        if seif is None:
            anunta(self, "Nicio parolă pusă", "Nu ai încă o parolă. Apasă întâi «Pune o parolă».")
            return
        veche = self._cere_parola("Schimbă parola", "Scrie parola veche:")
        if veche is None:
            return
        try:
            parola.deschide_cu_parola(seif, veche)  # doar verificăm parola veche
        except parola.ParolaGresita:
            anunta(self, "Parola nu este corectă", "Parola veche scrisă nu este corectă. Încearcă din nou.")
            return
        noua = self._cere_parola("Schimbă parola", "Scrie parola nouă (cel puțin 4 semne):")
        if noua is None or len(noua) < 4:
            if noua is not None:
                anunta(self, "Parola e prea scurtă", "Parola trebuie să aibă cel puțin 4 semne.")
            return
        seif_nou = parola.schimba_parola(seif, veche, noua)
        if not parola.salveaza_seif(seif_nou):
            anunta(self, "Parola nouă nu s-a putut păstra", "Scrierea pe disc a eșuat. Parola veche rămâne valabilă.")
            return
        self.linie_stare.arata("Gata", "parola s-a schimbat. Documentele deja criptate se deschid în continuare.", "bine")

    def _scoate_parola(self) -> None:
        parola = self._modul_parola
        seif = parola.incarca_seif()
        if seif is None:
            anunta(self, "Nicio parolă pusă", "Nu ai încă o parolă de scos.")
            return
        raspuns = dialog(
            self,
            "Scoți parola?",
            "Dacă scoți parola, documentele DEJA criptate nu se mai pot deschide "
            "nici cu parola, nici cu vreo cheie — rămân pentru totdeauna încuiate.\n\n"
            "Documentele noi se vor salva normale (necriptate).",
            [("Scoate parola", "pericol"), ("Renunță", "secundar")],
            implicit=1,
            anulare=1,
        )
        if raspuns != 0:
            return
        cere = self._cere_parola("Scoate parola", "Scrie parola, ca să fie sigur:")
        if cere is None:
            return
        try:
            parola.deschide_cu_parola(seif, cere)
        except parola.ParolaGresita:
            anunta(self, "Parola nu este corectă", "Parola scrisă nu este corectă. Parola rămâne pusă.")
            return
        parola.sterge_seif()
        self.config.cripteaza_documente = False
        self._arata_parola()
        self.linie_stare.arata("Gata", "parola s-a scos. Apasă «Salvează setările».", "bine")

    # ------------------------------------------------------- confidențialitate

    def _rand_blocare(self) -> None:
        card = self._card(
            "Blocarea căilor de ieșire la dictare",
            "Cât timp dictezi, programul poate tăia căile pe care textul ar putea pleca "
            "din calculator, ca nimeni să nu-l poată asculta de departe. "
            "La oprirea dictării, totul revine exact așa cum era.",
        )
        self.var_blocare = getattr(self.config, "blocare_dictare", "nimic") or "nimic"
        if self.var_blocare not in ("nimic", "program", "tot"):
            self.var_blocare = "nimic"
        optiuni = (
            ("nimic", "Fără blocare — lasă calculatorul așa cum e"),
            ("program", "Blochează doar D&TED (regulă de firewall doar pe acest program)"),
            ("tot", "Blochează tot calculatorul (internet + USB + Bluetooth)"),
        )
        self._casute_blocare: list[tuple[str, QCheckBox]] = []
        for cod, text in optiuni:
            rb = QCheckBox(text)
            rb.setFont(fonturi("baza"))
            rb.setChecked(cod == self.var_blocare)
            rb.toggled.connect(lambda checked, c=cod: self._seteaza_blocare(c, checked))
            self._casute_blocare.append((cod, rb))
            card.layout().addWidget(rb)
        nota = QLabel(
            "„Tot calculatorul” cere o confirmare Windows (fereastră albastră) la pornirea "
            "dictării, pentru că schimbă regulile de rețea. Dacă răspunzi «Nu», dictarea "
            "pornește oricum, doar fără blocare."
        )
        nota.setFont(fonturi("mica"))
        seteaza_rol(nota, "secundar")
        nota.setWordWrap(True)
        card.layout().addWidget(nota)
        self.var_avertizari = all(
            bool(getattr(self.config, cheie, True))
            for cheie in (
                "avertizeaza_internet",
                "avertizeaza_wifi",
                "avertizeaza_bluetooth",
                "avertizeaza_stick",
            )
        )
        self._rand_da_nu(
            card,
            "var_avertizari",
            "Avertizarea roșie când internetul e pornit (o poți opri și din fereastra ei)",
            self.var_avertizari,
        )

    def _seteaza_blocare(self, cod: str, checked: bool) -> None:
        if not checked:
            return
        self.var_blocare = cod
        for c, rb in self._casute_blocare:
            if c != cod:
                rb.blockSignals(True)
                rb.setChecked(False)
                rb.blockSignals(False)

    def _rand_transcriere(self) -> None:
        card = self._card(
            "Cum transcrie",
            "Ce folosește programul la transcriere. „Automat” merge bine pe aproape orice calculator.",
        )
        valoare = self.config.dispozitiv if self.config.dispozitiv in ("auto", "cpu", "cuda") else "auto"
        self.var_dispozitiv = valoare
        self._casute_dispozitiv: list[tuple[str, QCheckBox]] = []
        for cod, text, explicatie in OPTIUNI_TRANSCRIERE:
            rand_opt = QHBoxLayout()
            rand_opt.setSpacing(10)
            rb = QCheckBox(text)
            rb.setFont(fonturi("baza"))
            rb.setChecked(cod == valoare)
            rb.toggled.connect(lambda checked, c=cod: self._seteaza_dispozitiv(c, checked))
            self._casute_dispozitiv.append((cod, rb))
            rand_opt.addWidget(rb)
            et = QLabel(f"— {explicatie}")
            et.setFont(fonturi("mica"))
            seteaza_rol(et, "secundar")
            et.setWordWrap(True)
            rand_opt.addWidget(et, 1)
            card.layout().addLayout(rand_opt)
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
        # Modelul de transcriere (v0.1.2): cel îmbunătățit pentru română, dacă există.
        rand_model = QHBoxLayout()
        et_model = QLabel("Modelul de transcriere:")
        et_model.setFont(fonturi("baza"))
        rand_model.addWidget(et_model)
        self.combo_model = QComboBox()
        self.combo_model.setFont(fonturi("baza"))
        self._umple_modele()
        rand_model.addWidget(self.combo_model, 1)
        card.layout().addLayout(rand_model)
        # Descărcarea modelului ales (doar la buton, cu progres în etichetă).
        self.et_model_stare = QLabel("")
        self.et_model_stare.setFont(fonturi("baza"))
        self.et_model_stare.setWordWrap(True)
        seteaza_rol(self.et_model_stare, "secundar")
        card.layout().addWidget(self.et_model_stare)
        self.buton_model = QPushButton("Descarcă modelul ales (internet)")
        self.buton_model.setFont(fonturi("baza"))
        self.buton_model.clicked.connect(self._descarca_model_ales)
        card.layout().addWidget(self.buton_model)
        self.actualizeaza_placa_video()

    def _umple_modele(self) -> None:
        """Populează lista de modele instalate (kitul sau folderul de instalare)."""
        import sys as _sys

        from .. import cai
        from ..constante import MODELE_TRANSCRIBERE

        radacini = []
        ambalat = getattr(_sys, "_MEIPASS", None)
        if ambalat:
            radacini.append(Path(ambalat))
        radacini.append(cai.director_model())

        def instalat(nume: str) -> bool:
            return any(
                (radacina / "model" / nume / "model.bin").is_file() for radacina in radacini
            )

        self.combo_model.addItem("Automat — românescul, dacă există", "auto")
        for nume, descriere in MODELE_TRANSCRIBERE.items():
            self.combo_model.addItem(descriere if instalat(nume) else f"{descriere} (lipsește)", nume)
            if not instalat(nume):
                model_index = self.combo_model.count() - 1
                self.combo_model.model().item(model_index).setEnabled(False)
        preferat = getattr(self.config, "model_preferat", "auto") or "auto"
        for index in range(self.combo_model.count()):
            if self.combo_model.itemData(index) == preferat:
                self.combo_model.setCurrentIndex(index)
                break

    def _descarca_model_ales(self) -> None:
        """Descarcă modelul ales din listă (doar la buton; progres în etichetă).

        „Automat” aduce modelul standard (sursa sigură, publică). Eek și
        standardul au surse oficiale; fine-tunatul RO primește o explicație.
        """
        import threading

        from .. import pregatire
        from ..constante import WHISPER_NUME

        nume = self.combo_model.currentData() or "auto"
        if nume in ("", "auto"):
            nume = WHISPER_NUME
        self.buton_model.setEnabled(False)
        self.combo_model.setEnabled(False)
        self._model_progres_text = "Se pregătește descărcarea…"

        def lucrare() -> None:
            try:
                pregatire.descarca_model(
                    nume, progres=lambda mesaj, _fractie: setattr(
                        self, "_model_progres_text", mesaj
                    )
                )
                self._model_rezultat = ("ok", "Modelul a fost descărcat și verificat. Alege-l din listă.")
            except Exception as exc:
                self._model_rezultat = ("eroare", str(exc))

        if not hasattr(self, "_model_rezultat"):
            self._model_rezultat = ("", "")
        self._model_rezultat = ("", "")
        threading.Thread(target=lucrare, name="descarca-model", daemon=True).start()

        # Eticheta de progres se actualizează din firul interfeței (sigur în Qt).
        from PySide6.QtCore import QTimer

        def citește() -> None:
            stare, mesaj = self._model_rezultat
            if stare:
                self._timer_model.stop()
                self.buton_model.setEnabled(True)
                self.combo_model.setEnabled(True)
                self._umple_modele()
                seteaza_rol(self.et_model_stare, "succes" if stare == "ok" else "pericol")
                self.et_model_stare.setText(mesaj)
                return
            self.et_model_stare.setText(self._model_progres_text)

        if getattr(self, "_timer_model", None) is None:
            self._timer_model = QTimer(self)
        self._timer_model.timeout.connect(citește)
        self._timer_model.start(300)

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
        if not checked:
            return
        self.var_dispozitiv = cod
        for c, rb in getattr(self, "_casute_dispozitiv", ()):
            if c != cod:
                rb.blockSignals(True)
                rb.setChecked(False)
                rb.blockSignals(False)

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
        """Un rând de setare cu o SINGURĂ bifă (UX-22/redesign): bifat = activat.

        A înlocuit perechea de casete „Da / Nu”, care ocupa loc degeaba.
        """
        bifa = QCheckBox(text)
        bifa.setFont(fonturi("baza"))
        bifa.setChecked(bool(valoare))
        bifa.toggled.connect(lambda bifat: setattr(self, cheie, bifat))
        parinte.layout().addWidget(bifa)

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

        self.var_sfaturi = QCheckBox("Arată sfaturile inteligente în interfață")
        self.var_sfaturi.setChecked(bool(getattr(self.config, "arata_sfaturi", True)))
        self.var_sfaturi.setFont(fonturi("baza"))
        card.layout().addWidget(self.var_sfaturi)

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
        card.layout().addWidget(self.eticheta_preview)

        btn_reset = Buton(card, "Revino la setările inițiale", self._reset_afisare, latime=260, inaltime=36)
        card.layout().addWidget(btn_reset)

    def _rand_actualizari(self) -> None:
        """Secțiunea „Actualizări” direct în Setări (N-2 / UX-17)."""
        card = self._card(
            "Actualizări și componente",
            f"Versiunea curentă a programului este {constante.VERSIUNE_COMPLETA}. "
            "Poți verifica dacă a apărut o versiune nouă pe GitHub sau poți reveni "
            "la o versiune anterioară păstrată în copia de siguranță.",
        )
        rand = QHBoxLayout()
        rand.setSpacing(10)
        rand.addWidget(
            Buton(
                card,
                "Deschide Instalare și actualizări",
                self._deschide_actualizari_din_setari,
                fel="principal",
                latime=280,
                inaltime=40,
            )
        )
        rand.addStretch(1)
        card.layout().addLayout(rand)

    def _deschide_actualizari_din_setari(self) -> None:
        aplicatie = self._aplicatia_principala()
        self.accept()
        if aplicatie is not None and hasattr(aplicatie, "arata_ecran"):
            aplicatie.arata_ecran("instalare")

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
        # Tastele rapide alese de utilizator (Setări → „Taste rapide”).
        try:
            self.config.scurtaturi = {
                nume: getattr(self, f"_tasta_{nume}").secventa
                for nume, _et in TASTE_RAPIDE
                if (getattr(self, f"_tasta_{nume}", None) is not None)
                and getattr(self, f"_tasta_{nume}").secventa
            }
        except (AttributeError,):
            pass
        try:
            self.config.dispozitiv = self.var_dispozitiv
        except (AttributeError,):
            pass
        try:
            self.config.model_preferat = self.combo_model.currentData() or "auto"
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
            self.config.arata_sfaturi = self.var_sfaturi.isChecked()
            self.config.pauza_rand_sec = max(1, int(self.spin_pauza_rand.value()))
            paragraf = max(2, int(self.spin_pauza_paragraf.value()))
            self.config.pauza_paragraf_sec = max(paragraf, self.config.pauza_rand_sec + 1)
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
        try:
            self.config.cripteaza_documente = self.var_cripteaza.isChecked()
        except (AttributeError,):
            pass
        try:
            self.config.blocare_dictare = self.var_blocare
        except (AttributeError,):
            pass
        try:
            self.config.activare_vocala = self.var_activare_vocala
        except (AttributeError,):
            pass
        try:
            self.config.auto_volum = self.var_auto_volum
        except (AttributeError,):
            pass
        try:
            self.config.scurteaza_pauze = self.var_pauze
        except (AttributeError,):
            pass
        try:
            self.config.pregateste_audio = self.var_pregateste
        except (AttributeError,):
            pass
        try:
            self.config.scurtaturi_globale = self.var_scurtaturi
        except (AttributeError,):
            pass
        try:
            avertizari = self.var_avertizari
            for cheie in (
                "avertizeaza_internet",
                "avertizeaza_wifi",
                "avertizeaza_bluetooth",
                "avertizeaza_stick",
            ):
                setattr(self.config, cheie, avertizari)
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
