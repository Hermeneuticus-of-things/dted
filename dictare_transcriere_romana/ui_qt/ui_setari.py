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

Trei niveluri (comutatorul de sus, stil Fluent 2):

* **Bază** — tot ce are nevoie oricine: motorul (procesor / placă video),
  modelul, cu explicații pe înțelesul tuturor și „Recomandat pentru acest
  calculator”, plus secțiunile obișnuite de mai sus;
* **Descărcări** — modelele instalate / lipsă, cu descărcare și bară de
  progres (``pregatire.asigura_model``), bibliotecile plăcii video și
  „Caută actualizări” (``actualizare``) — doar la buton, nimic în fundal;
* **Expert** — pliat implicit: pragul VAD, tamponul audio, fereastra și
  suprapunerea, contextul din textul anterior, beam size, felul de calcul,
  pragul de activare vocală, oprirea după tăcere și „Revino la implicit”.
"""

from __future__ import annotations

import os

from dataclasses import asdict
from pathlib import Path

import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QProgressBar,
    QSpinBox,
    QInputDialog,
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
from . import comun, fluent
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
    ("Motor și model", ("_rand_transcriere", "_rand_model")),
    ("Documente", ("_rand_folder",)),
    ("Limbă și termeni", ("_rand_limba", "_rand_termeni", "_rand_dictionar")),
    ("Sunet", ("_rand_microfon", "_rand_difuzor", "_rand_dictare")),
    ("Salvare și program", ("_rand_salvare", "_rand_program")),
    ("Parolă și criptare", ("_rand_parola",)),
    ("Confidențialitate", ("_rand_blocare",)),
    ("Aspect", ("_rand_afisare", "_rand_aspect")),
    ("Descărcări și actualizări", ("_rand_descarcari", "_rand_actualizari")),
    ("Expert", ("_rand_expert",)),
)

#: Nivelurile comutatorului de sus și secțiunile din fiecare (restul = „Bază”).
NIVELURI: tuple[str, ...] = ("Bază", "Descărcări", "Expert")
NIVEL_SECTIUNE: dict[str, int] = {"Descărcări și actualizări": 1, "Expert": 2}


def nivel_sectiune(titlu: str) -> int:
    """0 = Bază, 1 = Descărcări, 2 = Expert."""
    return NIVEL_SECTIUNE.get(titlu, 0)


#: Explicațiile modelelor, pe înțelesul tuturor: (nume scurt, ce câștigi / ce pierzi).
INFO_MODELE: dict[str, tuple[str, str]] = {
    "auto": (
        "Automat",
        "Programul folosește modelul optimizat pentru română (singurul model activ).",
    ),
    constante.WHISPER_NUME_EEK: (
        "Optimizat pentru română",
        "Greșește cel mai puțin la română (cam 6 cuvinte din 100) și înțelege și engleza. "
        "Ocupă 820 MB și merge repede și pe procesor. Licență liberă (MIT).",
    ),
    # Modelele arhivate (standard turbo, TransferRapid RO) nu mai apar în Setări:
    # vezi docs/MODELS_ARHIVA.md.
}


def model_instalat(nume: str) -> bool:
    """Adevărat dacă modelul ``nume`` e în kit (``_MEIPASS``) sau în folderul de instalare."""
    import sys as _sys

    radacini = []
    ambalat = getattr(_sys, "_MEIPASS", None)
    if ambalat:
        radacini.append(Path(ambalat))
    radacini.append(cai.director_model())
    return any((radacina / "model" / nume / "model.bin").is_file() for radacina in radacini)


def marime_model_mb(nume: str) -> int:
    """Cât se descarcă pentru modelul ``nume`` (MB; 0 dacă nu știm)."""
    from .. import pregatire

    manifest = pregatire._manifest(Path(nume))
    if not manifest:
        return 0
    return int(round(sum(m for m, _ in manifest[0].values()) / 1_000_000))


def recomandare_pc(
    are_nvidia: bool, ram_gb: float, limba: str = "ro"
) -> tuple[str, str, str]:
    """(dispozitiv, model, motiv) recomandate pentru acest calculator.

    Funcție pură (testabilă): primește ce s-a citit despre calculator.
    """
    limba = (limba or "ro").lower()
    # Un singur model activ (eek); limba rămâne parametru pentru compatibilitate.
    model = constante.WHISPER_NUME_EEK
    nume_model = INFO_MODELE[model][0].lower()
    if are_nvidia:
        motiv = (
            f"Ai placă video NVIDIA: lasă „Automat” (folosește placa video, cel mai rapid) "
            f"și modelul {nume_model}."
        )
        return "auto", model, motiv
    ram = f"{ram_gb:.0f} GB RAM" if ram_gb > 0 else "memoria necunoscută"
    if 0 < ram_gb < constante.WHISPER_MIN_RAM_GB:
        motiv = (
            f"Fără placă video NVIDIA și cu {ram}: procesorul și modelul {nume_model}; "
            "închide alte programe cât dictezi (în Expert, felul de calcul „int8” folosește mai puțină memorie)."
        )
    else:
        motiv = f"Fără placă video NVIDIA ({ram}): procesorul și modelul {nume_model}."
    return "cpu", model, motiv


def stare_motor_audio() -> str:
    """Textul despre motorul audio (C++ nativ sau Python, de rezervă)."""
    try:
        from .. import audio_engine_native

        stare = audio_engine_native.status()
    except Exception:
        return "Motorul audio: Python (obișnuit)."
    if stare.get("backend") == "cpp":
        return "Motorul audio: nativ (C++), cu întârziere mică."
    return "Motorul audio: Python (obișnuit). Motorul nativ C++ nu e instalat — nu e nevoie de el."


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

        # Nivelurile (Fluent: comutator segmentat): Bază / Descărcări / Expert.
        self.comutator_nivel = fluent.ComutatorSegmentat(NIVELURI, self)
        self.comutator_nivel.schimbat.connect(self._arata_nivel)
        layout.addWidget(self.comutator_nivel, 0, Qt.AlignmentFlag.AlignLeft)
        self.coada = comun.CoadaUI(self)
        self._descarcare_activa = False

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
        self._arata_nivel(0)

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

    def _arata_nivel(self, nivel: int) -> None:
        """Arată în listă doar secțiunile nivelului ales (Bază / Descărcări / Expert)."""
        primul = -1
        for rand, (titlu, _metode) in enumerate(SECTIUNI):
            ascuns = nivel_sectiune(titlu) != nivel
            self.lista_sectiuni.setRowHidden(rand, ascuns)
            if not ascuns and primul < 0:
                primul = rand
        curent = self.lista_sectiuni.currentRow()
        if curent < 0 or self.lista_sectiuni.isRowHidden(curent):
            if primul >= 0:
                self.lista_sectiuni.setCurrentRow(primul)
                self._arata_sectiune(primul)
        if nivel == 1:
            self._reimprospateaza_descarcari()

    def arata_sectiunea(self, titlu: str) -> bool:
        """Deschide direct o secțiune (și nivelul ei); întoarce False dacă nu există."""
        for rand, (nume, _metode) in enumerate(SECTIUNI):
            if nume == titlu:
                self.comutator_nivel.alege(nivel_sectiune(nume), emite=False)
                self._arata_nivel(nivel_sectiune(nume))
                self.lista_sectiuni.setCurrentRow(rand)
                self._arata_sectiune(rand)
                return True
        return False

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
        # Memoria dictărilor lungi (rezumatorul OpenLLM-Ro, memorie_dictare.py) — oprită implicit.
        card_rezumat = self._card(
            "Memorie la dictări lungi",
            "La dictările lungi, programul ține minte pe scurt ce ai spus până acum, ca "
            "frazele noi să se lege mai bine. Rezumatul se face pe calculator, în fundal, și "
            "se folosește doar dacă se potrivește cuvânt cu cuvânt cu ce ai dictat; altfel "
            "se ia simplu finalul textului. Oprit implicit.",
        )
        self.var_rezumat = getattr(self.config, "rezumat_activ", False) is True
        self._rand_da_nu(
            card_rezumat,
            "var_rezumat",
            "Folosește memoria la dictări lungi (rezumat verificat al textului deja dictat)",
            self.var_rezumat,
        )
        # Dictarea lungă (dictare_lunga.py): Silero VAD → ferestre 30 s / 7,5 s → commit stabil.
        # Oprită implicit; $DTED_DICTARE_LUNGA=1/0 are prioritate față de bifă.
        card_lunga = self._card(
            "Dictare lungă",
            "Pentru dictări lungi, fără cuvinte tăiate: programul aude când vorbești (detector "
            "de vorbire Silero), trimite bucăți de până la 30 de secunde care se suprapun și scrie "
            "doar textul care nu se mai schimbă. După o pauză de peste 2 secunde începe un paragraf "
            "nou. Oprită implicit — dictarea obișnuită rămâne neschimbată.",
        )
        self.var_dictare_lunga = getattr(self.config, "dictare_lunga", False) is True
        self._rand_da_nu(
            card_lunga,
            "var_dictare_lunga",
            "Folosește dictarea lungă (ferestre de 30 s cu suprapunere, paragraf nou după pauză)",
            self.var_dictare_lunga,
        )
        env_lunga = (os.environ.get("DTED_DICTARE_LUNGA") or "").strip()
        self.eticheta_dictare_lunga_mediu = self._valoare(
            card_lunga,
            (
                f"Atenție: DTED_DICTARE_LUNGA={env_lunga} e setată în Windows și are prioritate "
                "față de această bifă."
            )
            if env_lunga
            else "",
        )

    # ------------------------------------------------------- parolă și criptare

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
            "Pe ce lucrează transcrierea",
            "„Automat” merge bine pe aproape orice calculator: folosește placa video "
            "dacă există, altfel procesorul.",
        )
        valoare = self.config.dispozitiv if self.config.dispozitiv in ("auto", "cpu", "cuda") else "auto"
        self.var_dispozitiv = valoare
        self._casute_dispozitiv: list[tuple[str, QCheckBox]] = []
        for cod, text, explicatie in OPTIUNI_TRANSCRIERE:
            rand = QHBoxLayout()
            rb = QCheckBox(text)
            rb.setFont(fonturi("baza"))
            rb.setChecked(cod == valoare)
            rb.setMinimumWidth(280)
            rb.toggled.connect(lambda checked, c=cod: self._seteaza_dispozitiv(c, checked))
            rand.addWidget(rb)
            self._casute_dispozitiv.append((cod, rb))
            et = QLabel(explicatie)
            et.setFont(fonturi("mica"))
            seteaza_rol(et, "secundar")
            et.setWordWrap(True)
            et.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            rand.addWidget(et, 1)
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
        self.eticheta_motor_audio = QLabel(stare_motor_audio())
        self.eticheta_motor_audio.setFont(fonturi("mica"))
        seteaza_rol(self.eticheta_motor_audio, "secundar")
        self.eticheta_motor_audio.setWordWrap(True)
        card.layout().addWidget(self.eticheta_motor_audio)
        self.actualizeaza_placa_video()

    def _rand_model(self) -> None:
        card = self._card(
            "Modelul de transcriere",
            "„Creierul” care ascultă și scrie. Cele marcate „(lipsește)” se pot descărca "
            "din „Descărcări”.",
        )
        # Modelul de transcriere (v0.1.2): cel îmbunătățit pentru română, dacă există.
        rand_model = QHBoxLayout()
        et_model = QLabel("Modelul de transcriere:")
        et_model.setFont(fonturi("baza"))
        rand_model.addWidget(et_model)
        self.combo_model = QComboBox()
        self.combo_model.setFont(fonturi("baza"))
        self.combo_model.setAccessibleName("Modelul de transcriere")
        self._umple_modele()
        rand_model.addWidget(self.combo_model, 1)
        card.layout().addLayout(rand_model)
        self.eticheta_model_info = QLabel("")
        self.eticheta_model_info.setFont(fonturi("baza"))
        self.eticheta_model_info.setWordWrap(True)
        seteaza_rol(self.eticheta_model_info, "secundar")
        card.layout().addWidget(self.eticheta_model_info)
        self.combo_model.currentIndexChanged.connect(self._arata_info_model)
        self._arata_info_model()
        # „Recomandat pentru acest calculator”.
        rand_rec = QHBoxLayout()
        self.eticheta_recomandare = QLabel("")
        self.eticheta_recomandare.setFont(fonturi("baza"))
        self.eticheta_recomandare.setWordWrap(True)
        seteaza_rol(self.eticheta_recomandare, "principal")
        rand_rec.addWidget(self.eticheta_recomandare, 1)
        self.buton_recomandare = Buton(
            card, "Folosește recomandarea", self._aplica_recomandarea, latime=220, inaltime=36
        )
        rand_rec.addWidget(self.buton_recomandare)
        card.layout().addLayout(rand_rec)
        self._calculeaza_recomandarea()

    def _calculeaza_recomandarea(self) -> None:
        from .. import pregatire, resurse

        try:
            nvidia = bool(pregatire.are_placa_nvidia())
        except Exception:
            nvidia = False
        try:
            ram = float(resurse.memorie_ram_gb())
        except Exception:
            ram = 0.0
        self._recomandare = recomandare_pc(nvidia, ram, getattr(self.config, "limba", "ro"))
        dispozitiv, model, motiv = self._recomandare
        lipsa = "" if model_instalat(model) else " (modelul trebuie descărcat întâi — vezi „Descărcări”)"
        self.eticheta_recomandare.setText(f"Recomandat pentru acest calculator: {motiv}{lipsa}")

    def _aplica_recomandarea(self) -> None:
        dispozitiv, model, _motiv = getattr(self, "_recomandare", ("auto", "auto", ""))
        for cod, rb in self._casute_dispozitiv:
            rb.setChecked(cod == dispozitiv)
        self.var_dispozitiv = dispozitiv
        if model_instalat(model):
            self._alege_model(model)
        else:
            self._alege_model("auto")
            self.arata_sectiunea("Descărcări și actualizări")
        self.linie_stare.arata("Recomandare", "am ales motorul potrivit; apasă «Salvează setările».", "normal")

    def _alege_model(self, nume: str) -> None:
        for index in range(self.combo_model.count()):
            if self.combo_model.itemData(index) == nume:
                self.combo_model.setCurrentIndex(index)
                return

    def _arata_info_model(self, *_args) -> None:
        nume = self.combo_model.currentData() or "auto"
        titlu, text = INFO_MODELE.get(nume, ("", ""))
        self.eticheta_model_info.setText(f"{titlu}: {text}" if titlu else "")

    def _umple_modele(self) -> None:
        """Populează lista de modele instalate (kitul sau folderul de instalare)."""
        from ..constante import MODELE_TRANSCRIBERE

        ales_acum = self.combo_model.currentData() if self.combo_model.count() else None
        self.combo_model.blockSignals(True)
        self.combo_model.clear()
        self.combo_model.addItem("Automat — românescul, dacă există", "auto")
        for nume, descriere in MODELE_TRANSCRIBERE.items():
            instalat = model_instalat(nume)
            self.combo_model.addItem(descriere if instalat else f"{descriere} (lipsește)", nume)
            if not instalat:
                model_index = self.combo_model.count() - 1
                self.combo_model.model().item(model_index).setEnabled(False)
        preferat = ales_acum or getattr(self.config, "model_preferat", "auto") or "auto"
        for index in range(self.combo_model.count()):
            if self.combo_model.itemData(index) == preferat:
                self.combo_model.setCurrentIndex(index)
                break
        self.combo_model.blockSignals(False)

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
        self.var_accent_sistem = bool(getattr(self.config, "accent_sistem", True))
        self._rand_da_nu(
            card,
            "var_accent_sistem",
            "Butoanele principale iau culoarea de accent din Windows",
            self.var_accent_sistem,
        )
        self.var_pastila = bool(getattr(self.config, "pastila_inregistrare", True))
        self._rand_da_nu(
            card,
            "var_pastila",
            "Arată pastila plutitoare „Înregistrez” când fereastra e ascunsă în timpul dictării",
            self.var_pastila,
        )

    def _aplica_mod(self, val: str) -> None:
        try:
            self.config.mod_afisare = val
            comun.aplica_tema(val, accent=bool(getattr(self, "var_accent_sistem", True)))
        except Exception as exc:
            jurnal.atentionare(f"Modul de afișare nu a putut fi aplicat: {exc}")

    # ------------------------------------------------------------------ Descărcări

    def _rand_descarcari(self) -> None:
        card = self._card(
            "Modele de transcriere",
            "Ce e instalat și ce se mai poate descărca. Fiecare fișier se verifică (SHA-256); "
            "totul rămâne în folderul programului, fără drepturi de administrator.",
        )
        self._randuri_model: dict[str, dict] = {}
        from ..constante import MODELE_TRANSCRIBERE

        for nume in MODELE_TRANSCRIBERE:
            cadru = QFrame(card)
            cadru.setObjectName("rand_model")
            vertical = QVBoxLayout(cadru)
            vertical.setContentsMargins(0, 4, 0, 4)
            rand = QHBoxLayout()
            titlu = QLabel(INFO_MODELE.get(nume, (nume, ""))[0])
            titlu.setFont(fonturi("baza"))
            titlu.setStyleSheet("font-weight: 600;")
            rand.addWidget(titlu)
            stare = QLabel("")
            stare.setFont(fonturi("mica"))
            rand.addWidget(stare, 1)
            buton = Buton(cadru, "Descarcă", lambda n=nume: self._descarca_model(n), latime=150, inaltime=34)
            buton.setIcon(fluent.iconita("descarca", "#0F6CBD"))
            rand.addWidget(buton)
            vertical.addLayout(rand)
            bara = QProgressBar(cadru)
            bara.setRange(0, 1000)
            bara.setTextVisible(False)
            bara.setFixedHeight(6)
            bara.setVisible(False)
            vertical.addWidget(bara)
            detaliu = QLabel("")
            detaliu.setFont(fonturi("mica"))
            seteaza_rol(detaliu, "secundar")
            detaliu.setWordWrap(True)
            detaliu.setVisible(False)
            vertical.addWidget(detaliu)
            card.layout().addWidget(cadru)
            self._randuri_model[nume] = {
                "stare": stare, "buton": buton, "bara": bara, "detaliu": detaliu,
            }
        # Placa video (CUDA): starea și butonul de descărcare, aceleași ca în „Bază”.
        self.eticheta_cuda_descarcari = QLabel("")
        self.eticheta_cuda_descarcari.setFont(fonturi("baza"))
        self.eticheta_cuda_descarcari.setWordWrap(True)
        card.layout().addWidget(self.eticheta_cuda_descarcari)
        self.buton_cuda_descarcari = Buton(
            card, "Descarcă bibliotecile pentru placa video", self._descarca_cuda, latime=380, inaltime=36
        )
        card.layout().addWidget(self.buton_cuda_descarcari)
        self._reimprospateaza_descarcari()

    def _reimprospateaza_descarcari(self) -> None:
        """Recitește ce modele sunt instalate (după o descărcare sau la deschidere)."""
        from .. import pregatire

        for nume, rand in getattr(self, "_randuri_model", {}).items():
            instalat = model_instalat(nume)
            descarcabil = pregatire.model_descarcabil(nume)
            marime = marime_model_mb(nume)
            if instalat:
                text, rol = "✔ Instalat", "verde"
                rand["buton"].setText("Verifică / repară")
            elif descarcabil:
                text = "Disponibil" + (f" — {marime:,} MB".replace(",", ".") if marime else "")
                rol = "secundar"
                rand["buton"].setText("Descarcă")
            else:
                text, rol = "Doar în kitul offline (nu se descarcă din program)", "secundar"
            rand["stare"].setText(text)
            seteaza_rol(rand["stare"], rol)
            rand["buton"].setVisible(descarcabil)
            rand["buton"].setEnabled(not self._descarcare_activa)
        try:
            extra = pregatire.text_stare_cuda(self.config)
        except Exception:
            extra = ""
        if hasattr(self, "eticheta_cuda_descarcari"):
            aplicatie = self._aplicatia_principala()
            self.eticheta_cuda_descarcari.setText(
                "Placa video: " + (extra or "nu e nevoie de biblioteci în plus.")
            )
            self.buton_cuda_descarcari.setVisible(bool(extra) and aplicatie is not None)

    def _descarca_model(self, nume: str) -> None:
        """Descarcă (sau repară) modelul ``nume`` într-un fir, cu bară de progres."""
        from .. import pregatire

        if self._descarcare_activa or nume not in self._randuri_model:
            return
        rand = self._randuri_model[nume]
        self._descarcare_activa = True
        for alt in self._randuri_model.values():
            alt["buton"].setEnabled(False)
        rand["bara"].setValue(0)
        rand["bara"].setVisible(True)
        rand["detaliu"].setVisible(True)
        rand["detaliu"].setText("Pornesc descărcarea…")
        folder = pregatire.folder_descarcare_model(nume)

        def progres(text: str, fractie: float) -> None:
            self.coada.trimite(self._progres_model, nume, text, fractie)

        def lucru() -> None:
            try:
                pregatire.asigura_model(progres, 0.0, 1.0, folder=folder)
                gresite = pregatire.fisiere_model_gresite(folder=folder)
                self.coada.trimite(self._dupa_descarcare_model, nume, not gresite, "")
            except Exception as exc:
                self.coada.trimite(self._dupa_descarcare_model, nume, False, str(exc))

        threading.Thread(target=lucru, name=f"descarca-{nume}", daemon=True).start()

    def _progres_model(self, nume: str, text: str, fractie: float) -> None:
        rand = self._randuri_model.get(nume)
        if not rand:
            return
        rand["bara"].setValue(int(max(0.0, min(1.0, float(fractie))) * 1000))
        rand["detaliu"].setText(text)

    def _dupa_descarcare_model(self, nume: str, reusit: bool, eroare: str) -> None:
        self._descarcare_activa = False
        rand = self._randuri_model.get(nume)
        if rand:
            rand["bara"].setVisible(False)
            if reusit:
                rand["detaliu"].setText("Gata: modelul e descărcat și verificat.")
                seteaza_rol(rand["detaliu"], "verde")
            else:
                rand["detaliu"].setText(
                    "Descărcarea nu a reușit"
                    + (f" ({eroare})" if eroare else "")
                    + ". Verifică internetul și încearcă din nou; ce era bun a rămas pe disc."
                )
                seteaza_rol(rand["detaliu"], "pericol")
        self._umple_modele()
        self._reimprospateaza_descarcari()
        if hasattr(self, "eticheta_recomandare"):
            self._calculeaza_recomandarea()

    # ------------------------------------------------------------------ Actualizări

    def _rand_actualizari(self) -> None:
        card = self._card(
            "Actualizări",
            "Programul NU caută nimic singur. La buton, compară versiunile instalate cu lista "
            "oficială și descarcă doar ce s-a schimbat; versiunea veche se păstrează.",
        )
        self.eticheta_versiuni = QLabel(self._text_versiuni())
        self.eticheta_versiuni.setFont(fonturi("baza"))
        self.eticheta_versiuni.setWordWrap(True)
        card.layout().addWidget(self.eticheta_versiuni)
        self.btn_actualizari = Buton(
            card, "Caută actualizări", self._cauta_actualizari, fel="principal", latime=220, inaltime=38
        )
        self.btn_actualizari.setIcon(fluent.iconita("reincarca", "#FFFFFF"))
        rand_buton = QHBoxLayout()
        rand_buton.addWidget(self.btn_actualizari)
        rand_buton.addStretch(1)
        card.layout().addLayout(rand_buton)
        self.bara_actualizari = QProgressBar(card)
        self.bara_actualizari.setRange(0, 1000)
        self.bara_actualizari.setTextVisible(False)
        self.bara_actualizari.setFixedHeight(6)
        self.bara_actualizari.setVisible(False)
        card.layout().addWidget(self.bara_actualizari)
        self.et_actualizari = QLabel("")
        self.et_actualizari.setFont(fonturi("baza"))
        self.et_actualizari.setWordWrap(True)
        card.layout().addWidget(self.et_actualizari)

    def _text_versiuni(self) -> str:
        from .. import actualizare

        try:
            instalate = actualizare.versiuni_instalate()
        except Exception:
            instalate = {}
        parti = [f"Programul: {constante.VERSIUNE}"]
        for nume, meta in instalate.items():
            if nume != "program":
                parti.append(f"{nume}: {meta.get('versiune', '—')}")
        return "Instalat acum — " + "; ".join(parti) + "."

    def _cauta_actualizari(self) -> None:
        """Caută DOAR la buton: descarcă manifestul și compară (ca în Întreținere)."""
        import json

        self.btn_actualizari.setEnabled(False)
        self.bara_actualizari.setVisible(True)
        self.bara_actualizari.setRange(0, 0)  # nedeterminat cât timp citim lista
        self.et_actualizari.setText("Se caută actualizări pe internet…")
        seteaza_rol(self.et_actualizari, "secundar")

        def lucru() -> None:
            from .. import actualizare as act

            try:
                if not act.versiuni_instalate():
                    instalate: dict[str, dict] = {"program": {"versiune": constante.VERSIUNE}}
                    try:
                        folder_model = cai.fisier_model().parent
                        if folder_model.exists():
                            instalate["model"] = {"versiune": folder_model.name}
                    except Exception:
                        pass
                    act.scrie_versiuni(instalate)
                temporar = act.fisier_versiuni().parent / "manifest-descarcat.json"
                if not act.descarca(constante.URL_MANIFEST_ACTUALIZARI, temporar):
                    self.coada.trimite(self._eroare_actualizari)
                    return
                try:
                    manifest = json.loads(temporar.read_text(encoding="utf-8"))
                finally:
                    temporar.unlink(missing_ok=True)
                self.coada.trimite(self._dupa_cautare_actualizari, act.ce_s_a_schimbat(manifest), manifest)
            except Exception:
                self.coada.trimite(self._eroare_actualizari)

        threading.Thread(target=lucru, name="cauta-actualizari-setari", daemon=True).start()

    def _eroare_actualizari(self) -> None:
        self.btn_actualizari.setEnabled(True)
        self.bara_actualizari.setVisible(False)
        self.bara_actualizari.setRange(0, 1000)
        self.et_actualizari.setText(
            "Nu am putut căuta actualizări: fie nu e internet, fie lista oficială nu răspunde. "
            "Nimic nu s-a schimbat."
        )
        seteaza_rol(self.et_actualizari, "pericol")

    def _dupa_cautare_actualizari(self, schimbari: list, manifest: dict) -> None:
        self.btn_actualizari.setEnabled(True)
        self.bara_actualizari.setVisible(False)
        self.bara_actualizari.setRange(0, 1000)
        if not schimbari:
            self.et_actualizari.setText("Ești la zi: toate componentele au ultima versiune.")
            seteaza_rol(self.et_actualizari, "verde")
            return
        descarcabile = [
            s for s in schimbari if str((manifest or {}).get(s.nume, {}).get("url", "")).strip()
        ]
        lista = "\n".join(f"• {s.eticheta}" for s in schimbari)
        if not descarcabile:
            self.et_actualizari.setText("Update-uri disponibile:\n" + lista)
            seteaza_rol(self.et_actualizari, "secundar")
            return
        raspuns = QMessageBox.question(
            self,
            "Instalez actualizările?",
            f"{lista}\n\nDescarc și înlocuiesc doar aceste componente?\n"
            "Cele vechi se păstrează și poți reveni oricând la ele (Întreținere).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if raspuns != QMessageBox.StandardButton.Yes:
            self.et_actualizari.setText("Update-uri disponibile:\n" + lista + "\n\nNimic nu s-a descărcat.")
            seteaza_rol(self.et_actualizari, "secundar")
            return
        self._aplica_actualizari(descarcabile, manifest)

    def _aplica_actualizari(self, schimbari: list, manifest: dict) -> None:
        self.btn_actualizari.setEnabled(False)
        self.bara_actualizari.setValue(0)
        self.bara_actualizari.setVisible(True)

        def progres(primiti: int, total: int) -> None:
            if total > 0:
                self.coada.trimite(self._progres_actualizari, primiti / total)

        def lucru() -> None:
            from .. import actualizare as act

            rapoarte: list[str] = []
            for schimbare in schimbari:
                meta = (manifest or {}).get(schimbare.nume, {})
                pachet = cai.director_descarcari() / f"{schimbare.nume}-{schimbare.noua}"
                ok = act.descarca(
                    str(meta.get("url", "")), pachet, str(meta.get("sha256", "")), progres=progres
                )
                if not ok:
                    rapoarte.append(f"✘ {schimbare.nume}: descărcarea a eșuat (sumă sau rețea)")
                    continue
                try:
                    act.aplica(schimbare.nume, schimbare.noua, pachet)
                    rapoarte.append(f"✔ {schimbare.eticheta} — instalat")
                except Exception as exc:
                    rapoarte.append(f"✘ {schimbare.nume}: instalarea a eșuat ({exc})")
            self.coada.trimite(self._dupa_actualizari, rapoarte)

        threading.Thread(target=lucru, name="aplica-actualizari-setari", daemon=True).start()

    def _progres_actualizari(self, fractie: float) -> None:
        self.bara_actualizari.setValue(int(max(0.0, min(1.0, fractie)) * 1000))
        self.et_actualizari.setText(f"Se descarcă… {fractie * 100:.0f}%")

    def _dupa_actualizari(self, rapoarte: list[str]) -> None:
        self.btn_actualizari.setEnabled(True)
        self.bara_actualizari.setVisible(False)
        self.et_actualizari.setText("\n".join(rapoarte))
        rol = "pericol" if any(r.startswith("✘") for r in rapoarte) else "verde"
        seteaza_rol(self.et_actualizari, rol)
        self.eticheta_versiuni.setText(self._text_versiuni())
        self._umple_modele()
        self._reimprospateaza_descarcari()

    # ------------------------------------------------------------------ Expert

    #: (cheie config, etichetă, explicație, pas, zecimale; 0 = număr întreg).
    _CAMPURI_EXPERT: tuple[tuple[str, str, str, float, int], ...] = (
        ("expert_vad_prag", "Prag de vorbire (VAD)",
         "Cât de sigur trebuie să fie că e vorbire (0,1–0,9). Mai mare = ignoră mai mult zgomotul.", 0.05, 2),
        ("prag_activare_db", "Activare vocală (dB)",
         "Sub acest nivel, microfonul e socotit liniște (−70 … −5 dB).", 1, 0),
        ("expert_timp_tacere_sec", "Oprește după tăcere (s)",
         "Dictarea se oprește singură după atâtea secunde de liniște; 0 = niciodată.", 5, 0),
        ("expert_fereastra_sec", "Fereastră de dictare (s)",
         "Cât sunet se transcrie o dată. Mai mare = mai precis, dar textul apare mai târziu.", 0.5, 1),
        ("expert_suprapunere_sec", "Suprapunere (s)",
         "Cât se reia din bucata anterioară — doar cu motorul audio nativ.", 0.25, 2),
        ("expert_ring_buffer_ms", "Tampon audio (ms)",
         "Cât sunet ține minte motorul audio nativ (ring buffer).", 100, 0),
        ("expert_buget_text_anterior", "Context din textul anterior (caractere)",
         "Câte caractere din ce s-a scris deja primește modelul ca indiciu; 0 = deloc.", 20, 0),
        ("expert_beam_size", "Beam size",
         "Câte variante încearcă modelul (1–10). Mai mare = puțin mai precis, mai lent.", 1, 0),
    )

    def _rand_expert(self) -> None:
        card = self._card(
            "Expert",
            "Pentru cine știe ce face. Valorile implicite merg bine pentru aproape oricine; "
            "„Revino la valorile implicite” le pune la loc.",
        )
        self.pliabil_expert = fluent.SectiunePliabila("Setări pentru cunoscători", card, deschisa=False)
        card.layout().addWidget(self.pliabil_expert)
        formular = QFormLayout()
        formular.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.pliabil_expert.continut_layout.addLayout(formular)
        self._spinuri_expert: dict[str, QSpinBox | QDoubleSpinBox] = {}
        for cheie, eticheta_text, explicatie, pas, zecimale in self._CAMPURI_EXPERT:
            minim, maxim = config_modul.LIMITE_EXPERT[cheie]
            if zecimale:
                spin: QSpinBox | QDoubleSpinBox = QDoubleSpinBox()
                spin.setDecimals(zecimale)
            else:
                spin = QSpinBox()
                minim, maxim, pas = int(minim), int(maxim), int(pas)
            spin.setRange(minim, maxim)
            spin.setSingleStep(pas)
            spin.setValue(getattr(self.config, cheie))
            spin.setToolTip(explicatie)
            spin.setAccessibleName(eticheta_text)
            spin.setAccessibleDescription(explicatie)
            spin.setMinimumWidth(120)
            eticheta_camp = QLabel(eticheta_text)
            eticheta_camp.setFont(fonturi("baza"))
            eticheta_camp.setToolTip(explicatie)
            formular.addRow(eticheta_camp, spin)
            self._spinuri_expert[cheie] = spin
        self.combo_calcul = QComboBox()
        self.combo_calcul.addItems(list(config_modul.FELURI_CALCUL))
        self.combo_calcul.setCurrentText(getattr(self.config, "expert_compute_type", "auto"))
        self.combo_calcul.setToolTip(
            "Felul de calcul (compute_type). „auto” = float32 pe procesor, float16 pe placa video; „int8” = mai puțină memorie."
        )
        self.combo_calcul.setAccessibleName("Felul de calcul")
        formular.addRow(QLabel("Felul de calcul (compute_type)"), self.combo_calcul)
        self.bifa_text_anterior = QCheckBox("Ține cont de textul anterior (condition_on_previous_text)")
        self.bifa_text_anterior.setChecked(bool(getattr(self.config, "expert_text_anterior", False)))
        self.bifa_text_anterior.setToolTip(
            "Mai coerent la fraze lungi, dar o greșeală se poate repeta. Implicit oprit."
        )
        formular.addRow(self.bifa_text_anterior)
        self.btn_expert_implicit = Buton(
            card, "Revino la valorile implicite", self._expert_implicit, latime=280, inaltime=36
        )
        self.btn_expert_implicit.setIcon(fluent.iconita("reincarca", "#5C5C5C"))
        rand_implicit = QHBoxLayout()
        rand_implicit.addWidget(self.btn_expert_implicit)
        rand_implicit.addStretch(1)
        self.pliabil_expert.continut_layout.addLayout(rand_implicit)
        nota = QLabel(
            "Suprapunerea și tamponul audio se folosesc doar cu motorul audio nativ (C++); "
            "felul de calcul și modelul se schimbă la următoarea transcriere."
        )
        nota.setFont(fonturi("mica"))
        nota.setWordWrap(True)
        seteaza_rol(nota, "secundar")
        self.pliabil_expert.continut_layout.addWidget(nota)

    def _expert_implicit(self) -> None:
        """„Revino la valorile implicite” pentru toate setările Expert."""
        implicite = config_modul.valori_expert_implicite()
        for cheie, spin in self._spinuri_expert.items():
            spin.setValue(implicite[cheie])
        self.combo_calcul.setCurrentText(implicite.get("expert_compute_type", "auto"))
        self.bifa_text_anterior.setChecked(bool(implicite.get("expert_text_anterior", False)))
        self.linie_stare.arata("Expert", "valorile implicite sunt puse; apasă «Salvează setările».", "normal")

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
            self.config.rezumat_activ = bool(self.var_rezumat)
        except (AttributeError,):
            pass
        try:
            self.config.dictare_lunga = bool(self.var_dictare_lunga)
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
        try:
            self.config.accent_sistem = bool(self.var_accent_sistem)
            self.config.pastila_inregistrare = bool(self.var_pastila)
        except AttributeError:
            pass
        try:
            for cheie, spin in self._spinuri_expert.items():
                setattr(self.config, cheie, spin.value())
            self.config.expert_compute_type = self.combo_calcul.currentText()
            self.config.expert_text_anterior = self.bifa_text_anterior.isChecked()
        except AttributeError:
            pass
        config_modul.limiteaza_expert(self.config)

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
