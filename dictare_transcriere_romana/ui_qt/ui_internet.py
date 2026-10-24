"""Avertizarea de confidențialitate PySide6 (cerință 12).

Indicator mic cu 4 pictograme (Internet, Wi-Fi, Bluetooth, Stick) și fereastra
roșă ce arată căile deschise. Programul NU trimite nimic pe internet; acesta
doar le arată pe cele care sunt deschise și cere utilizatorului să le închide
înainte de dictare/transcriere.
"""

from __future__ import annotations

import datetime as dt
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import jurnal, securitate
from . import comun
from .comun import Buton, fonturi, seteaza_rol

#: Cât timp nu mai arătăm fereastra roșă de la sine (10 minute).
PAUZA_DUPA_AVERTISMENT = 600.0

#: Titlul mare al ferestrei.
TEXT_AVERTISMENT = "Ai lăsat ceva deschis"

#: Explicația de sus, aceeași pentru toate căile.
TEXT_INTRODUCERE = (
    "Dictarea și transcrierea se fac numai pe acest calculator. Programul NU trimite nimic "
    "nicăieri: nici pe internet, nici prin Bluetooth, nici pe stick. Dar acum ai ceva "
    "deschis, iar dacă lucrezi cu lucruri personale sau secrete, e mai bine să închizi."
)

#: Vorbele arătate de indicator când totul este închis.
TEXT_LINISTIT = "Totul e închis – lucrezi în siguranță."


def _nume_scurt(cheie: str) -> str:
    return {
        "internet": "Internet",
        "wifi": "Wi-Fi",
        "bluetooth": "Bluetooth",
        "stick": "Stick",
    }.get(cheie, cheie)


# --------------------------------------------------------------------------- pictograme


def _semn_pixmap(cheie: str, deschisa: bool, marime: int = 26) -> QLabel:
    """Returnează o etichetă cu un pictogram text pentru o cale."""
    simbol = {
        "internet": "🌐" if deschisa else "🔒",
        "wifi": "📶" if deschisa else "📴",
        "bluetooth": "📳" if deschisa else "🔇",
        "stick": "💾" if deschisa else "🗑️",
    }.get(cheie, "●")
    lbl = QLabel(simbol)
    lbl.setMinimumSize(marime, marime)
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    font = QFont()
    font.setPointSizeF(marime * 0.65)
    lbl.setFont(font)
    seteaza_rol(lbl, "succes" if deschisa else "pericol")
    return lbl


# --------------------------------------------------------------------------- indicator


class IndicatorCai(QWidget):
    """Semnul mic, mereu vizibil: patru pictograme și vorbele potrivite."""

    def __init__(
        self,
        parinte: QWidget | None = None,
        configurare=None,
        pentru_dictare: bool = False,
    ):
        super().__init__(parinte)
        self.configurare = configurare
        self.pentru_dictare = pentru_dictare
        self.stare = securitate.StareCai()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        self.setObjectName("indicator")

        self._semne: dict[str, QLabel] = {}
        for cheie in ("internet", "wifi", "bluetooth", "stick"):
            coloana = QVBoxLayout()
            coloana.setSpacing(2)
            semn = _semn_pixmap(cheie, False)
            eticheta = QLabel(_nume_scurt(cheie))
            eticheta.setFont(fonturi("mica"))
            seteaza_rol(eticheta, "secundar")
            eticheta.setAlignment(Qt.AlignmentFlag.AlignCenter)
            eticheta.setWordWrap(True)
            coloana.addWidget(semn)
            coloana.addWidget(eticheta)
            layout.addLayout(coloana)
            self._semne[cheie] = semn

        self.eticheta_stare = QLabel("Se verifică…")
        self.eticheta_stare.setFont(fonturi("mica"))
        seteaza_rol(self.eticheta_stare, "secundar")
        self.eticheta_stare.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.eticheta_stare)

        for semn in self._semne.values():
            semn.setCursor(Qt.CursorShape.PointingHandCursor)
            semn.mousePressEvent = lambda _e: self.deschide_explicatia()
        self.eticheta_stare.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eticheta_stare.mousePressEvent = lambda _e: self.deschide_explicatia()

        self.actualizeaza()

    def actualizeaza(self) -> securitate.StareCai:
        """Citește acum starea celor patru căi și arată semnele potrivite."""
        try:
            self.stare = securitate.stare(pentru_dictare=self.pentru_dictare)
        except Exception as exc:  # pragma: no cover - depinde de Windows
            jurnal.atentionare(f"Starea căilor de securitate nu a putut fi citită: {exc}")
            return self.stare
        for cheie in ("internet", "wifi", "bluetooth", "stick"):
            cale = self.stare.despre(cheie)
            deschisa = bool(cale and cale.deschisa and cale.exista)
            semn = self._semne[cheie]
            seteaza_rol(semn, "succes" if deschisa else "pericol")
            font = semn.font()
            font.setPointSizeF(16.0)
            semn.setFont(font)
        if self.stare.toate_inchise:
            self.eticheta_stare.setText(TEXT_LINISTIT)
            seteaza_rol(self.eticheta_stare, "pericol")
        else:
            self.eticheta_stare.setText(self.stare.pe_scurt())
            seteaza_rol(self.eticheta_stare, "succes")
        return self.stare

    def deschide_explicatia(self) -> None:
        """Un clic pe indicator deschide fereastra cu explicații."""
        deschide_fereastra(self, self.configurare, self.pentru_dictare)


def indicator(
    parinte: QWidget, configurare, pentru_dictare: bool = False
) -> IndicatorCai:
    """Semnul mic, gata de așezat în colțul de sus al ecranului."""
    return IndicatorCai(parinte, configurare, pentru_dictare)


# --------------------------------------------------------------------------- fereastra roșă


class FereastraAvertisment(QDialog):
    """Fereastra roșă cu toate căile deschise, una sub alta."""

    def __init__(
        self, parinte: QWidget, configurare, pentru_dictare: bool = False
    ):
        super().__init__(parinte)
        self.configurare = configurare
        self.pentru_dictare = pentru_dictare
        self.setWindowTitle(TEXT_AVERTISMENT)
        self.setMinimumSize(760, 420)
        self.setModal(False)
        self._id_ceas: QTimer | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Antet.
        antet = QHBoxLayout()
        semn = QLabel("⚠")
        semn.setMinimumSize(64, 64)
        semn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        font_semn = QFont()
        font_semn.setPointSizeF(32.0)
        semn.setFont(font_semn)
        seteaza_rol(semn, "pericol")
        antet.addWidget(semn)
        titlu = QLabel(TEXT_AVERTISMENT)
        titlu.setFont(fonturi("titlu"))
        seteaza_rol(titlu, "rosu")
        antet.addWidget(titlu, stretch=1)
        layout.addLayout(antet)

        introducere = QLabel(TEXT_INTRODUCERE)
        introducere.setFont(fonturi("baza"))
        introducere.setWordWrap(True)
        layout.addWidget(introducere)

        # Zona căi (scroll).
        self.zona_cai = QScrollArea()
        self.zona_cai.setWidgetResizable(True)
        self.zona_cai.setFrameShape(QFrame.Shape.NoFrame)
        self.interior_cai = QWidget()
        self.interior_layout = QVBoxLayout(self.interior_cai)
        self.interior_layout.setContentsMargins(0, 0, 0, 0)
        self.interior_layout.setSpacing(8)
        self.zona_cai.setWidget(self.interior_cai)
        layout.addWidget(self.zona_cai, stretch=1)

        # Butoane jos.
        jos = QHBoxLayout()
        self.buton_avion = Buton(
            self,
            "Închide totul deodată (Modul avion)",
            self._mod_avion,
            fel="principal",
            latime=340,
            inaltime=40,
        )
        jos.addWidget(self.buton_avion)
        self.buton_continua = Buton(
            self, "Am înțeles, continuă", self.accept, fel="succes", latime=220, inaltime=40
        )
        jos.addWidget(self.buton_continua)
        jos.addWidget(Buton(self, "Nu mai afișa azi", self._ascunde_azi, latime=200, inaltime=40))
        jos.addWidget(
            Buton(self, "Nu mai afișa deloc", self._nu_mai_afisa_deloc, latime=200, inaltime=40)
        )
        jos.addStretch(1)
        layout.addLayout(jos)

        self._construieste_randurile()
        self.reimprospateaza()
        self._id_ceas = QTimer(self)
        self._id_ceas.timeout.connect(self._ceas)
        self._id_ceas.start(2000)

    # ------------------------------------------------------------------ rânduri

    def _construieste_randurile(self) -> None:
        self._randuri: dict[str, tuple[QFrame, QLabel, QLabel, Buton]] = {}
        for cheie in ("internet", "wifi", "bluetooth", "stick"):
            rand = QFrame()
            rand.setObjectName("rand-cale")
            rl = QHBoxLayout(rand)
            rl.setContentsMargins(12, 8, 12, 8)
            rl.setSpacing(10)

            semn = QLabel("●")
            semn.setMinimumSize(40, 40)
            semn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            semn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            font_semn = QFont()
            font_semn.setPointSizeF(24.0)
            semn.setFont(font_semn)
            rl.addWidget(semn)

            coloana = QVBoxLayout()
            coloana.setSpacing(2)
            titlu = QLabel("")
            titlu.setFont(fonturi("buton"))
            text = QLabel("")
            text.setFont(fonturi("mica"))
            text.setWordWrap(True)
            coloana.addWidget(titlu)
            coloana.addWidget(text)
            rl.addLayout(coloana, stretch=1)

            buton = Buton(self, "…", lambda c=cheie: self._apasa(c), fel="principal")
            rl.addWidget(buton)

            self.interior_layout.addWidget(rand)
            self._randuri[cheie] = (rand, titlu, text, buton, semn)

    def _pune_stare_cale(self, rand: QFrame, stare: str) -> None:
        """Setează fundalul rândului (ok/pericol/nimic) prin QSS-ul central."""
        if rand.property("stare") == stare:
            return
        rand.setProperty("stare", stare)
        stil = rand.style()
        if stil is not None:
            stil.unpolish(rand)
            stil.polish(rand)

    def reimprospateaza(self) -> None:
        """Recitește starea și arată fiecare cale."""
        try:
            stare = securitate.stare(pentru_dictare=self.pentru_dictare)
        except Exception as exc:  # pragma: no cover - depinde de Windows
            jurnal.atentionare(f"Starea căilor nu a putut fi citită: {exc}")
            return
        for cheie in ("internet", "wifi", "bluetooth", "stick"):
            cale = stare.despre(cheie)
            if cale is None:
                continue
            rand, titlu, text, buton, semn = self._randuri[cheie]
            deschisa = bool(cale.deschisa and cale.exista)
            if not cale.exista:
                self._pune_stare_cale(rand, "ok")
                titlu.setText(f"{_nume_scurt(cheie)}: nu există pe acest calculator")
                seteaza_rol(titlu, "succes")
                text.setText("Aici e totul în regulă.")
                seteaza_rol(text, "verde")
                buton.set_activ(False)
                buton.set_text("Nu e nevoie de nimic")
                seteaza_rol(semn, "succes")
            elif not cale.masurata:
                self._pune_stare_cale(rand, "")
                titlu.setText(f"{_nume_scurt(cheie)}: se verifică…")
                seteaza_rol(titlu, "secundar")
                text.setText("")
                seteaza_rol(text, "")
                buton.set_activ(False)
                buton.set_text("Se verifică…")
                seteaza_rol(semn, "secundar")
            elif deschisa:
                self._pune_stare_cale(rand, "pericol")
                titlu.setText(cale.titlu)
                seteaza_rol(titlu, "rosu")
                text.setText(cale.text)
                seteaza_rol(text, "")
                buton.set_activ(True)
                buton.set_text(cale.buton)
                seteaza_rol(semn, "pericol")
            else:
                self._pune_stare_cale(rand, "ok")
                titlu.setText(f"{_nume_scurt(cheie)}: gata, e închis.")
                seteaza_rol(titlu, "succes")
                text.setText("Aici e totul în regulă.")
                seteaza_rol(text, "verde")
                buton.set_activ(False)
                buton.set_text("Închis")
                seteaza_rol(semn, "succes")
        if stare.toate_inchise:
            self.buton_avion.set_activ(False)
            self.buton_avion.set_text("Totul e închis")
        else:
            self.buton_avion.set_activ(True)

    # ------------------------------------------------------------------ ceas

    def _ceas(self) -> None:
        if not self.isVisible():
            if self._id_ceas is not None:
                self._id_ceas.stop()
                self._id_ceas = None
            return
        try:
            self.reimprospateaza()
        except Exception:
            pass

    # ------------------------------------------------------------------ butoane

    def _apasa(self, cheie: str) -> None:
        """Butonul mare al unei căi."""
        if cheie == "stick":
            self._scoate_stickurile()
            return
        if cheie == "internet":
            explica(self, self.configurare, cheie="internet")
            return
        if securitate.deschide_setarea(cheie):
            self._anunta_deschidere(cheie)
            return
        explica(self, self.configurare, cheie=cheie)

    def _anunta_deschidere(self, cheie: str) -> None:
        rezultat = comun.dialog(
            self,
            f"Cum oprești {securitate.NUME_CAI.get(cheie, cheie)}",
            (
                f"Am deschis setările Windows pentru {securitate.NUME_CAI.get(cheie, cheie)}. "
                "Apasă pe butonul de pornit/oprit din pagina care s-a deschis, apoi întoarce-te "
                "aici: rândul devine verde singur, în două secunde."
            ),
            [("Am oprit, verifică acum", "principal"), ("Mai târziu", "secundar")],
            implicit=0,
            anulare=1,
        )
        if rezultat == 0:
            self.reimprospateaza()

    def _scoate_stickurile(self) -> None:
        stare = securitate.stare(pentru_dictare=self.pentru_dictare)
        cale = stare.despre("stick")
        if cale is None or not cale.stickuri:
            self.reimprospateaza()
            return
        nume = ", ".join(stick.descriere() for stick in cale.stickuri)
        raspuns = comun.dialog(
            self,
            "Scoaterea stickului în siguranță",
            (
                f"Scot în siguranță {nume}. Închide programele care folosesc fișiere de pe stick "
                "(de exemplu, o fereastră deschisă pe stick), apoi apasă „Scoate-l acum”."
            ),
            [("Scoate-l acum", "principal"), ("Nu acum", "secundar")],
            implicit=0,
            anulare=1,
        )
        if raspuns != 0:
            return
        mesaje = []
        for stick in cale.stickuri:
            reusit, mesaj = securitate.scoate_in_siguranta(stick.litera)
            mesaje.append(mesaj)
        comun.anunta(self, "Stickul", "\n".join(dict.fromkeys(mesaje)))
        self.reimprospateaza()

    def _mod_avion(self) -> None:
        """Închide totul deodată: internet, Wi-Fi și Bluetooth (Modul avion)."""
        raspuns = comun.dialog(
            self,
            "Închid totul deodată",
            (
                "Se deschide pagina „Mod avion” din Windows. Dacă îl pornești, se închid internetul, "
                "Wi-Fi-ul și Bluetooth-ul deodată. Programul nu schimbă nimic singur: alegi tu în "
                "pagina care se deschide."
            ),
            [("Deschide pagina", "principal"), ("Nu acum", "secundar")],
            implicit=0,
            anulare=1,
        )
        if raspuns == 0 and securitate.deschide_modul_avion():
            self.reimprospateaza()

    def _ascunde_azi(self) -> None:
        ascunde_azi(self.configurare)
        comun.anunta_ascundere(self)
        self.reject()

    def _nu_mai_afisa_deloc(self) -> None:
        """Oprește avertizările de confidențialitate pentru totdeauna.

        Se pot porni la loc din Setări → „Confidențialitate”.
        """
        for cheie in (
            "avertizeaza_internet",
            "avertizeaza_wifi",
            "avertizeaza_bluetooth",
            "avertizeaza_stick",
        ):
            setattr(self.configurare, cheie, False)
        from .. import config as config_modul

        config_modul.salveaza(self.configurare)
        self.reject()

    def reject(self) -> None:
        if self._id_ceas is not None:
            self._id_ceas.stop()
            self._id_ceas = None
        super().reject()


def anunta_ascundere(parinte: QWidget) -> None:
    """Spune simplu că fereastra nu mai apare până mâine."""
    comun.dialog(
        parinte,
        "Nu mai arăt fereastra azi",
        (
            "Bine. Nu mai arăt fereastra roșă până mâine. Semnul mic din colț rămâne acolo și "
            "se face roșu dacă ceva se deschide, ca să știi mereu cum stai."
        ),
        [("Am înțeles", "principal")],
    )


# --------------------------------------------------------------------------- arătarea


def _fereastra_deschisa(parinte: QWidget) -> FereastraAvertisment | None:
    """Fereastra roșă, dacă este deschisă deja."""
    for copil in parinte.children():
        if isinstance(copil, FereastraAvertisment) and copil.isVisible():
            return copil
    return None


def _cai_de_arătat(configurare, stare: securitate.StareCai) -> list[securitate.Cale]:
    """Căile deschise pentru care utilizatorul vrea să fie avertizat."""
    de_arătat = []
    for cale in stare.deschise:
        camp = securitate.CAMP_SETARE.get(cale.cheie, "")
        if camp and not getattr(configurare, camp, True):
            continue
        de_arătat.append(cale)
    return de_arătat


def este_ascuns_azi(configurare) -> bool:
    """Adevărat dacă utilizatorul a ales „Nu mai afișa azi”."""
    azi = dt.date.today().isoformat()
    return (getattr(configurare, "fara_avertisment_azi", "") or "") == azi


def ascunde_azi(configurare) -> None:
    """Ține minte că utilizatorul nu mai vrea fereastra până mâine."""
    from .. import config as config_modul

    configurare.fara_avertisment_azi = dt.date.today().isoformat()
    config_modul.salveaza(configurare)
    jurnal.info("Fereastra de avertizare nu va mai apărea până mâine.")


_ULTIMA_ARATARE: dict[str, float] = {}
_ULTIMELE_CAI: dict[str, tuple[str, ...]] = {}


def avertizeaza(
    parinte: QWidget,
    configurare,
    pentru_dictare: bool = False,
    fortat: bool = False,
    la_continuare=None,
) -> FereastraAvertisment | None:
    """Arată fereastra roșă dacă vreo cale este deschisă.

    Se cheamă la pornire, la începutul dictării/transcrierii. Dacă utilizatorul
    a închis-o de curând și nimic nou nu s-a deschis, nu o mai arată.
    """
    try:
        stare = securitate.stare(pentru_dictare=pentru_dictare)
    except Exception as exc:  # pragma: no cover - depinde de Windows
        jurnal.atentionare(f"Verificarea căilor de securitate a eșuat: {exc}")
        return None
    de_arătat = _cai_de_arătat(configurare, stare)
    if not de_arătat:
        return None
    if este_ascuns_azi(configurare) and not fortat:
        return None
    cheie_fereastra = id(parinte)
    cheie = f"{cheie_fereastra}-{pentru_dictare}"
    cai_acum = tuple(sorted(cale.cheie for cale in de_arătat))
    acum = time.monotonic()
    ultima = _ULTIMA_ARATARE.get(cheie, 0.0)
    cai_vechi = _ULTIMELE_CAI.get(cheie, ())
    if not fortat and cai_acum == cai_vechi and acum - ultima < PAUZA_DUPA_AVERTISMENT:
        return None
    _ULTIMA_ARATARE[cheie] = acum
    _ULTIMELE_CAI[cheie] = cai_acum
    fereastra = deschide_fereastra(parinte, configurare, pentru_dictare=pentru_dictare)
    if fereastra is not None and la_continuare is not None:
        vechiul_comanda = fereastra.buton_continua

        def combina() -> None:
            try:
                fereastra.accept()
            finally:
                la_continuare()

        fereastra.buton_continua.clicked.disconnect()
        fereastra.buton_continua.clicked.connect(combina)
    return fereastra


def deschide_fereastra(
    parinte: QWidget, configurare, pentru_dictare: bool = False, fortat: bool = True
) -> FereastraAvertisment | None:
    """Deschide fereastra roșă cu toate căile deschise."""
    existenta = _fereastra_deschisa(parinte)
    if existenta is not None:
        existenta.reimprospateaza()
        try:
            existenta.raise_()
            existenta.activateWindow()
        except Exception:
            pass
        return existenta
    fereastra = FereastraAvertisment(parinte, configurare, pentru_dictare=pentru_dictare)
    fereastra.show()
    return fereastra


# --------------------------------------------------------------------------- explicații


def explica(parinte: QWidget, configurare=None, cheie: str = "internet") -> None:
    """Ajutorul simplu: ce este calea respectivă și cum o închizi."""
    fereastra = QDialog(parinte)
    fereastra.setWindowTitle("Cum închizi ce e deschis")
    fereastra.setMinimumSize(760, 560)
    layout = QVBoxLayout(fereastra)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)

    titlu = QLabel("Cum închizi ce e deschis")
    titlu.setFont(fonturi("titlu"))
    layout.addWidget(titlu)

    intro = QLabel(
        "Alege calea care te interesează. Programul nu oprește nimic singur: îți arată pe ce să "
        "apeși, iar tu hotărăști. Tot ce este scris aici se face pe calculatorul tău."
    )
    intro.setFont(fonturi("baza"))
    seteaza_rol(intro, "secundar")
    intro.setWordWrap(True)
    layout.addWidget(intro)

    zona = QScrollArea()
    zona.setWidgetResizable(True)
    zona.setFrameShape(QFrame.Shape.NoFrame)
    interior = QWidget()
    interior.setAutoFillBackground(False)
    il = QVBoxLayout(interior)
    il.setContentsMargins(0, 0, 0, 0)
    il.setSpacing(10)
    zona.setWidget(interior)
    layout.addWidget(zona, stretch=1)

    _card_cale(il, "internet", "Internetul – legătura prin care calculatorul intră în rețea",
               "Sunt patru căi ca să închizi internetul. Alege-o pe cea mai simplă pentru tine:",
               (
                   "Wi-Fi: apasă pe lângă ceas (jos, în dreapta) pe semnul rețelei, apoi pe „Wi-Fi oprit”.",
                   "Cablu: dacă ai un cablu de la router în calculator, scoate-l din calculator.",
                   "Mod avion: în aceeași listă de lângă ceas, apasă „Mod avion” — se oprește tot deodată.",
                   "Telefonul: dacă ții telefonul legat la calculator (Bluetooth sau cablu USB) și îi dai internet, oprește partajarea din telefon ori scoate cablu.",
               ),
               setare="internet")
    _card_cale(il, "wifi", "Wi-Fi-ul – legătura fără fir",
               "Wi-Fi-ul poate fi pornit chiar dacă nu ești conectat la nimic. Cum îl închizi:",
               (
                   "Apasă pe lângă ceas (jos, în dreapta) pe semnul rețelei.",
                   "Apasă pe butonul „Wi-Fi” (se face gri) sau pe „Wi-Fi oprit”.",
                   "Pe laptop mai este și o tastă cu semnul antenei, care oprește Wi-Fi-ul de tot.",
               ),
               setare="wifi")
    _card_cale(il, "bluetooth", "Bluetooth-ul – legătura fără fir cu aparate din apropiere",
               "Bluetooth-ul lasă calculatorul să vorbească cu telefoane, căști sau boxe mici. Cum îl închizi:",
               (
                   "Apasă pe lângă ceas (jos, în dreapta) pe semnul rețelei, apoi pe semnul Bluetooth.",
                   "Se face gri, adică este oprit.",
                   "Dacă folosești căști Bluetooth pentru dictare, lasă-l pornit: este normal.",
               ),
               setare="bluetooth")
    _card_stick(il)

    rand = QHBoxLayout()
    Buton(
        fereastra,
        "Pornește Modul avion (închide internet, Wi-Fi și Bluetooth)",
        lambda: securitate.deschide_modul_avion(),
        fel="principal",
        latime=420,
        inaltime=40,
    ).setParent(fereastra)
    rand.addWidget(
        Buton(
            fereastra,
            "Pornește Modul avion (închide internet, Wi-Fi și Bluetooth)",
            lambda: securitate.deschide_modul_avion(),
            fel="principal",
            latime=420,
            inaltime=40,
        )
    )
    rand.addWidget(Buton(fereastra, "Închide explicația", fereastra.reject, latime=220, inaltime=40))
    rand.addStretch(1)
    layout.addLayout(rand)

    fereastra.exec()


def _card_cale(
    parinte: QWidget,
    cheie: str,
    titlu: str,
    explicatie: str,
    pasi: tuple[str, ...],
    setare: str = "",
) -> None:
    exterior = QFrame()
    exterior.setObjectName("card-cale")
    el = QVBoxLayout(exterior)
    el.setContentsMargins(12, 10, 12, 10)
    el.setSpacing(6)

    sus = QHBoxLayout()
    semn = _semn_pixmap(cheie, False, marime=40)
    sus.addWidget(semn)
    t = QLabel(titlu)
    t.setFont(fonturi("buton"))
    sus.addWidget(t, stretch=1)
    el.addLayout(sus)

    et = QLabel(explicatie)
    et.setFont(fonturi("baza"))
    et.setWordWrap(True)
    el.addWidget(et)

    for pas in pasi:
        p = QLabel("• " + pas)
        p.setFont(fonturi("baza"))
        seteaza_rol(p, "secundar")
        p.setWordWrap(True)
        el.addWidget(p)

    if setare:
        Buton(
            exterior,
            f"Deschide setarea Windows ({titlu.split('–')[0].strip()})",
            lambda: securitate.deschide_setarea(cheie),
            latime=420,
            inaltime=36,
        ).setParent(exterior)
        el.addWidget(
            Buton(
                exterior,
                f"Deschide setarea Windows ({titlu.split('–')[0].strip()})",
                lambda: securitate.deschide_setarea(cheie),
                latime=420,
                inaltime=36,
            )
        )

    parinte.layout().addWidget(exterior)


def _card_stick(parinte: QWidget) -> None:
    exterior = QFrame()
    exterior.setObjectName("card-cale")
    el = QVBoxLayout(exterior)
    el.setContentsMargins(12, 10, 12, 10)
    el.setSpacing(6)

    sus = QHBoxLayout()
    semn = _semn_pixmap("stick", False, marime=40)
    sus.addWidget(semn)
    t = QLabel("Stickul sau cardul de memorie")
    t.setFont(fonturi("buton"))
    sus.addWidget(t, stretch=1)
    el.addLayout(sus)

    et = QLabel("Pe stick se pot copia fișiere ușor. Cum îl scoți:")
    et.setFont(fonturi("baza"))
    et.setWordWrap(True)
    el.addWidget(et)

    for pas in (
        "Închide ferestrele în care vezi fișiere de pe stick.",
        "Apasă butonul „Scoate stickul în siguranță” din fereastra roșă.",
        "Când îți scrie „Acum poți scoate stickul din calculator.”, trage-l afară.",
    ):
        p = QLabel("• " + pas)
        p.setFont(fonturi("baza"))
        seteaza_rol(p, "secundar")
        p.setWordWrap(True)
        el.addWidget(p)

    stare = securitate.stare()
    cale = stare.despre("stick")
    nume = ", ".join(stick.descriere() for stick in (cale.stickuri if cale else ())) or "niciunul acum"
    pn = QLabel(f"Acum în calculator: {nume}")
    pn.setFont(fonturi("mica"))
    seteaza_rol(pn, "secundar")
    pn.setWordWrap(True)
    el.addWidget(pn)

    if cale is not None and cale.stickuri:
        Buton(
            exterior,
            "Scoate stickul în siguranță",
            lambda: _scoate_din_explicatie(parinte, cale),
            fel="principal",
            latime=340,
            inaltime=36,
        ).setParent(exterior)
        el.addWidget(
            Buton(
                exterior,
                "Scoate stickul în siguranță",
                lambda: _scoate_din_explicatie(parinte, cale),
                fel="principal",
                latime=340,
                inaltime=36,
            )
        )

    parinte.layout().addWidget(exterior)


def _scoate_din_explicatie(parinte: QWidget, cale) -> None:
    mesaje = []
    for stick in cale.stickuri:
        _reusit, mesaj = securitate.scoate_in_siguranta(stick.litera)
        mesaje.append(mesaj)
    comun.anunta(parinte, "Stickul", "\n".join(dict.fromkeys(mesaje)))
