"""Ecranul „Transcriere fișier audio” PySide6: patru pași, cu progres și „Anulează”.

Înlocuiește ``ui_transcriere.py`` (Tkinter). Logica este aceeași:

  1. Alege fișierul — cu butonul sau drag & drop.
  2. Spune ce se face cu textul — înlocuiește / adaugă la textul de pe ecran, limba.
  3. Transcrie — bara de progres, procent, timpul rămas, textul apare pe rând în editor.
     „Anulează” oprește imediat; textul scris până atunci se păstrează.
  4. Gata — banner + cele patru butoane (LibreOffice, DOCX, ODT, alte formate).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .. import (
    biblioteca,
    erori,
    jurnal,
    motor,
    stare as stare_modul,
    text_ro,
)
from .comun import (
    BaraStare,
    Buton,
    ZonaDerulare,
    ZonaProgres,
    alege_fisier_audio,
    anunta,
    dialog,
    dialog_eroare,
    eticheta,
    fonturi,
    seteaza_rol,
)
from .ui_editor import Editor
from .ui_internet import avertizeaza

#: Cât sunet se transcrie o dată (secunde).
SECUNDE_BUCATA = 30.0
#: Cât sunet se suprapune între bucăți.
SECUNDE_SUPRAPUNERE = 2.0
#: Extensiile acceptate.
FORMATE = "MP3, WAV, M4A, OGG sau FLAC"

#: Extensiile pe care le primește zona de drag & drop (aceleași ca la buton).
EXTENSII_DROP = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus"}


def _are_audio(mime) -> bool:
    """``True`` dacă printre fișierele trase există măcar unul audio."""
    if not mime.hasUrls():
        return False
    return any(
        url.toLocalFile() and Path(url.toLocalFile()).suffix.lower() in EXTENSII_DROP
        for url in mime.urls()
    )


class _ZonaDrop(QFrame):
    """Zona „trage fișierul aici” (UX-28): primește cu adevărat fișiere trase cu mausul."""

    def __init__(self, parinte: QWidget | None = None):
        super().__init__(parinte)
        self.setAcceptDrops(True)
        self.la_primire = None      # apelat cu Path când se dă drumul unui fișier audio
        self.la_traversare = None   # apelat cu True/False la intrarea/ieșirea mausului

    def dragEnterEvent(self, eveniment):
        if _are_audio(eveniment.mimeData()):
            eveniment.acceptProposedAction()
            if self.la_traversare:
                self.la_traversare(True)

    def dragLeaveEvent(self, eveniment):
        if self.la_traversare:
            self.la_traversare(False)

    def dropEvent(self, eveniment):
        if self.la_traversare:
            self.la_traversare(False)
        for url in eveniment.mimeData().urls():
            cale = url.toLocalFile()
            if cale and Path(cale).suffix.lower() in EXTENSII_DROP:
                eveniment.acceptProposedAction()
                if self.la_primire:
                    self.la_primire(Path(cale))
                return


class PaginaTranscriere(QWidget):
    """Ecranul „Transcriere fișier audio”."""

    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie
        self.stare = aplicatie.stare
        self.config = aplicatie.configurare
        self.editor: Editor = aplicatie.editor

        self._cale: Path | None = None
        self._info = None
        self._fir: threading.Thread | None = None
        self._anulat = threading.Event()
        self._motor_local: motor.MotorWhisper | None = None
        self._secunde_audio = 0.0
        self._inceput = 0.0
        self._procesat = 0.0
        self._text_brut_anterior = ""
        self._adauga_la_text = False
        self._limba = "ro"
        self._are_gpu = False

        self._construieste()
        QTimer.singleShot(100, self._afla_placa_video)

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        zona = ZonaDerulare(self, latime_minima=900)
        layout.addWidget(zona, stretch=1)

        corp = QWidget()
        corp_layout = QVBoxLayout(corp)
        corp_layout.setContentsMargins(16, 12, 16, 12)
        corp_layout.setSpacing(10)
        zona.interior.layout().addWidget(corp)

        # Titlu.
        titlu = eticheta(corp, "Transcriere fișier audio", "titlu")
        corp_layout.addWidget(titlu)

        et_descriere = eticheta(
            corp,
            "Alegeți un fișier audio (MP3, WAV, M4A, OGG sau FLAC) și programul scrie textul. "
            "Transcrierea se face pe acest calculator: fișierul nu pleacă pe internet.",
            "baza",
        )
        et_descriere.setWordWrap(True)
        corp_layout.addWidget(et_descriere)

        # ---------- pasul 1: fișierul
        card_1, corp_1 = self._card(corp, "1. Alege fișierul audio")
        corp_layout.addWidget(card_1)

        # Zona drop: primește fișierele trase cu mausul (UX-28).
        self.zona_drop = _ZonaDrop()
        self.zona_drop.setObjectName("drop")
        self.zona_drop.setMinimumHeight(120)
        self.zona_drop.la_primire = self._ia_fisierul
        self.zona_drop.la_traversare = self._la_traversare_drop
        drop_layout = QVBoxLayout(self.zona_drop)
        self.eticheta_drop = QLabel(
            "Trage fișierul audio aici, sau folosește butonul „Alege fișierul audio“."
        )
        self.eticheta_drop.setFont(fonturi("buton"))
        self.eticheta_drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        seteaza_rol(self.eticheta_drop, "atentie")
        self.eticheta_drop.setWordWrap(True)
        drop_layout.addWidget(self.eticheta_drop)
        corp_1.layout().addWidget(self.zona_drop)

        rand_alege = QHBoxLayout()
        self.buton_alege = Buton(
            corp_1,
            "Alege fișierul audio",
            self._alege_fisier,
            fel="principal",
            scurtatura="Ctrl+O",
            latime=300,
            inaltime=40,
        )
        rand_alege.addWidget(self.buton_alege)
        self.buton_scoate = Buton(
            corp_1, "Scoate fișierul ales", self._scoate_fisierul, latime=240, inaltime=40
        )
        self.buton_scoate.set_activ(False)
        rand_alege.addWidget(self.buton_scoate)
        rand_alege.addStretch(1)
        corp_1.layout().addLayout(rand_alege)

        self.eticheta_fisier = eticheta(
            corp_1, "Nu ai ales încă niciun fișier audio.", "baza"
        )
        corp_1.layout().addWidget(self.eticheta_fisier)

        self.eticheta_estimare = eticheta(corp_1, "", "baza")
        corp_1.layout().addWidget(self.eticheta_estimare)

        # ---------- pasul 2: ce se face cu textul
        card_2, corp_2 = self._card(corp, "2. Spune ce se face cu textul")
        corp_layout.addWidget(card_2)

        rand_text = QHBoxLayout()
        self.buton_inlocuieste = Buton(
            corp_2,
            "Înlocuiește textul de pe ecran",
            lambda: self._seteaza_mod_text(False),
            fel="principal",
            latime=320,
            inaltime=40,
        )
        rand_text.addWidget(self.buton_inlocuieste)
        self.buton_adauga = Buton(
            corp_2,
            "Adaugă la textul de pe ecran",
            lambda: self._seteaza_mod_text(True),
            latime=320,
            inaltime=40,
        )
        rand_text.addWidget(self.buton_adauga)
        rand_text.addStretch(1)
        corp_2.layout().addLayout(rand_text)

        et_mod = eticheta(
            corp_2,
            "„Adaugă” este bun când ai deja un text scris și vrei să adaugi vorbele din fișier.",
            "mica",
        )
        et_mod.setWordWrap(True)
        corp_2.layout().addWidget(et_mod)

        rand_limba = QHBoxLayout()
        et_limba = eticheta(rand_limba, "Limba vorbită:", "buton")
        rand_limba.addWidget(et_limba)
        self.buton_ro = Buton(
            corp_2, "Română (implicit)", lambda: self._seteaza_limba("ro"), fel="principal", latime=220, inaltime=40
        )
        rand_limba.addWidget(self.buton_ro)
        rand_limba.addStretch(1)
        corp_2.layout().addLayout(rand_limba)

        # ---------- pasul 3: transcrierea
        card_3, corp_3 = self._card(corp, "3. Transcrie")
        corp_layout.addWidget(card_3)

        rand_pornire = QHBoxLayout()
        self.buton_incepe = Buton(
            corp_3,
            "● Începe transcrierea",
            self._incepe,
            fel="principal",
            scurtatura="Ctrl+T",
            latime=340,
            inaltime=48,
        )
        rand_pornire.addWidget(self.buton_incepe)
        self.buton_anuleaza = Buton(
            corp_3, "Anulează", self._anuleaza, fel="pericol", latime=220, inaltime=48
        )
        self.buton_anuleaza.set_activ(False)
        rand_pornire.addWidget(self.buton_anuleaza)
        rand_pornire.addStretch(1)
        corp_3.layout().addLayout(rand_pornire)

        self.zona_progres = ZonaProgres(corp_3, "Pregătesc transcrierea…")
        corp_3.layout().addWidget(self.zona_progres)

        rand_progres = QHBoxLayout()
        self.eticheta_procent = eticheta(rand_progres, "0%", "imens")
        rand_progres.addWidget(self.eticheta_procent)
        self.eticheta_ramas = eticheta(rand_progres, "", "baza")
        rand_progres.addWidget(self.eticheta_ramas)
        rand_progres.addStretch(1)
        corp_3.layout().addLayout(rand_progres)

        self.eticheta_text_nou = eticheta(corp_3, "", "baza")
        self.eticheta_text_nou.setWordWrap(True)
        corp_3.layout().addWidget(self.eticheta_text_nou)

        # ---------- pasul 4: gata (ascuns până la final)
        self.zona_finala = QFrame()
        self.zona_finala.setObjectName("zona-finala")
        self.zona_finala.setVisible(False)
        final_layout = QVBoxLayout(self.zona_finala)
        final_layout.setContentsMargins(16, 12, 16, 12)
        self.eticheta_final = QLabel("Gata! Transcrierea este terminată.")
        self.eticheta_final.setFont(fonturi("buton"))
        seteaza_rol(self.eticheta_final, "verde")
        final_layout.addWidget(self.eticheta_final)

        rand_final_butoane = QHBoxLayout()
        self.buton_docx = Buton(
            self.zona_finala, "Salvează DOCX", lambda: self.salveaza("docx"), fel="principal", latime=160, inaltime=36
        )
        rand_final_butoane.addWidget(self.buton_docx)
        self.buton_odt = Buton(
            self.zona_finala, "Salvează ODT", lambda: self.salveaza("odt"), latime=160, inaltime=36
        )
        rand_final_butoane.addWidget(self.buton_odt)
        self.buton_libreoffice = Buton(
            self.zona_finala, "Deschide în LibreOffice", self._deschide_libreoffice, latime=200, inaltime=36
        )
        rand_final_butoane.addWidget(self.buton_libreoffice)
        rand_final_butoane.addStretch(1)
        final_layout.addLayout(rand_final_butoane)
        corp_3.layout().addWidget(self.zona_finala)

        # Butoane jos (înapoi / ajutor).
        rand_jos = QHBoxLayout()
        rand_jos.addWidget(
            Buton(
                corp,
                "← Înapoi la început",
                lambda: self.aplicatie.arata_ecran("principal"),
                latime=240,
                inaltime=40,
            )
        )
        rand_jos.addStretch(1)
        rand_jos.addWidget(
            Buton(
                corp,
                "Ajutor pentru acest ecran",
                self._ajutor,
                scurtatura="F1",
                latime=300,
                inaltime=40,
            )
        )
        cl_add = corp_layout
        cl_add.addLayout(rand_jos)

    # ------------------------------------------------------------------ ajutoruri UI

    def _card(self, parinte: QWidget, titlu_text: str) -> tuple[QFrame, QWidget]:
        """Creează un card cu titlu și returnează (card, conținut)."""
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(8)
        et = QLabel(titlu_text)
        et.setFont(fonturi("buton"))
        seteaza_rol(et, "titlu")
        cl.addWidget(et)
        corp = QWidget()
        corp_layout = QVBoxLayout(corp)
        corp_layout.setContentsMargins(0, 0, 0, 0)
        corp_layout.setSpacing(8)
        cl.addWidget(corp)
        return card, corp

    def _pune_stare_drop(self, stare: str) -> None:
        """Setează starea zonei de drop (verde/nimic) prin QSS-ul central."""
        if self.zona_drop.property("stare") == stare:
            return
        self.zona_drop.setProperty("stare", stare)
        stil = self.zona_drop.style()
        if stil is not None:
            stil.unpolish(self.zona_drop)
            stil.polish(self.zona_drop)

    def _la_traversare_drop(self, deasupra: bool) -> None:
        """Evidențierea zonei cât timp un fișier e tras deasupra ei."""
        if deasupra:
            self._pune_stare_drop("verde")
        elif self._cale is None:
            self._pune_stare_drop("")

    def _seteaza_mod_text(self, adauga: bool) -> None:
        self._adauga_la_text = bool(adauga)
        self.buton_adauga.set_activ(adauga)
        self.buton_inlocuieste.set_activ(not adauga)
        if adauga:
            self.buton_adauga._fel = "principal"
            self.buton_inlocuieste._fel = "secundar"
        else:
            self.buton_adauga._fel = "secundar"
            self.buton_inlocuieste._fel = "principal"
        self.buton_adauga._aplica_stil()
        self.buton_inlocuieste._aplica_stil()

    def _seteaza_limba(self, limba: str) -> None:
        # Româna e implicită și forțată; nu există opțiune de detectare automată
        # (cerința 0). Alte limbi se aleg, ca opțiune avansată, doar din Setări.
        self._limba = "ro"
        self.buton_ro.set_activ(True)
        self.buton_ro._fel = "principal"
        self.buton_ro._aplica_stil()

    # ------------------------------------------------------------------ pasul 1

    def _alege_fisier(self) -> None:
        cale = alege_fisier_audio(self, titlu="Alege fișierul audio de transcris")
        if cale is None:
            return
        self._ia_fisierul(cale)

    def _ia_fisierul(self, cale: Path) -> None:
        self._cale = cale
        self._pune_stare_drop("verde")
        self.eticheta_drop.setText(f"Fișier ales: {cale.name}")
        seteaza_rol(self.eticheta_drop, "verde")
        self.eticheta_fisier.setText(f"Se transcrie: {cale.name}")
        self.eticheta_estimare.setText("Verific fișierul…")
        self.buton_scoate.set_activ(True)
        threading.Thread(target=self._citeste_informatii, args=(cale,), daemon=True).start()

    def _citeste_informatii(self, cale: Path) -> None:
        info = motor.informatii_audio(cale)
        self.aplicatie.coada.trimite(self._dupa_informatii, info)

    def _dupa_informatii(self, info) -> None:
        self._info = info
        if not info.ok:
            self.eticheta_estimare.setText("")
            dialog_eroare(
                self,
                "Fișierul nu poate fi folosit",
                erori.Eroare(
                    ce_s_a_intamplat=info.mesaj or f"Fișierul nu poate fi folosit.",
                    de_ce="fișierul lipsește, nu este audio sau este deteriorat.",
                    ce_faci_acum=info.ce_fac
                    or f"Alege un fișier audio în formatul {FORMATE}, apoi încearcă din nou.",
                ),
            )
            return
        self._secunde_audio = float(info.secunde or 0.0)
        self._arata_estimarea()

    def _arata_estimarea(self) -> None:
        durata = text_ro.durata_text(self._secunde_audio) if self._secunde_audio else "puțin"
        estimare = text_ro.durata_pentru_transcriere(self._secunde_audio, self._are_gpu)
        self.eticheta_fisier.setText(
            f"Se transcrie: {self._cale.name} — sunet de {durata} "
            f"({(self._info.format or '').upper() or 'audio'})"
        )
        self.eticheta_estimare.setText(
            f"Transcrierea va dura {estimare} (estimare, depinde de calculator)."
        )

    def _scoate_fisierul(self) -> None:
        if self._fir is not None and self._fir.is_alive():
            anunta(
                self,
                "Transcrierea merge",
                "Apasă mai întâi „Anulează”, apoi poți scoate fișierul.",
            )
            return
        self._cale = None
        self._info = None
        self._secunde_audio = 0.0
        self._pune_stare_drop("")
        self.eticheta_drop.setText(
            "Trage fișierul audio aici, sau folosește butonul „Alege fișierul audio“."
        )
        seteaza_rol(self.eticheta_drop, "atentie")
        self.eticheta_fisier.setText("Nu ai ales încă niciun fișier audio.")
        self.eticheta_estimare.setText("")
        self.buton_scoate.set_activ(False)

    # ------------------------------------------------------------------ pasul 2

    # ------------------------------------------------------------------ pasul 3

    def _incepe(self) -> None:
        if self._cale is None:
            rezultat = dialog(
                self,
                "Alege mai întâi fișierul",
                "Nu ai ales încă niciun fișier audio. Îl alegi acum?",
                [("Alege fișierul audio", "principal"), ("Înapoi", "secundar")],
                implicit=0,
                anulare=1,
            )
            if rezultat == 0:
                self._alege_fisier()
            if self._cale is None:
                return
        if self._fir is not None and self._fir.is_alive():
            return

        avertizeaza(self, self.aplicatie.configurare, pentru_dictare=False, fortat=True)

        if not motor.biblioteci_disponibile():
            dialog_eroare(
                self,
                "Părțile de transcriere nu sunt instalate",
                erori.Eroare(
                    ce_s_a_intamplat="Părțile de transcriere nu sunt instalate încă.",
                    de_ce="instalarea programului nu s-a terminat până la capăt.",
                    ce_faci_acum=(
                        "Rulează din nou instalarea programului, apoi încearcă din nou."
                    ),
                ),
            )
            return

        if self._adauga_la_text:
            if not self.editor.text().strip():
                self._adauga_la_text = False
        elif self.editor.text().strip():
            self.editor.set_text("")
            self.zona_finala.setVisible(False)

        self._anulat.clear()
        self._procesat = 0.0
        self._inceput = time.monotonic()
        self.stare.sursa = "fisier"
        self.stare.marca = biblioteca.marca_din_nume(self._cale)
        self.stare.segmente = []
        self.zona_progres.incepe("Pregătesc transcrierea…", 0, 100)
        self.eticheta_procent.setText("0%")
        self.eticheta_ramas.setText("Pregătesc transcrierea…")
        self.eticheta_text_nou.setText("")
        self.buton_incepe.set_text("Se transcrie…")
        self.buton_incepe.set_activ(False)
        self.buton_alege.set_activ(False)
        self.buton_scoate.set_activ(False)
        self.buton_anuleaza.set_activ(True)
        self.aplicatie.bara_stare.arata(
            "Transcriu",
            f"Se transcrie „{self._cale.name}”. Poți apăsa „Anulează” oricând.",
            "lucru",
        )
        self._fir = threading.Thread(target=self._transcrie, name="transcriere-fisier", daemon=True)
        self._fir.start()

    def _anuleaza(self) -> None:
        self._anulat.set()
        try:
            self.aplicatie._motor.anuleaza()
        except Exception as exc:
            jurnal.atentionare(f"Oprirea transcrierii a dat eroare: {exc}")
        self.eticheta_ramas.setText("Opresc… textul scris până acum se păstrează.")

    def _transcrie(self) -> None:
        """Taie sunetul în bucăți și le transcrie pe rând."""
        motor_local = self.aplicatie._motor
        try:
            sunet = motor.incarca_audio(self._cale)
        except Exception as exc:
            self.aplicatie.coada.trimite(self._termina_cu_eroare, exc)
            return
        total = int(len(sunet))
        if total <= 0:
            self.aplicatie.coada.trimite(
                self._termina_cu_eroare,
                motor.EroareMotor(
                    "Fișierul audio nu are sunet.",
                    ce_fac="Verifică fișierul: se aude ceva când îl asculți? Alege alt fișier.",
                ),
            )
            return
        total_secunde = total / 16000.0
        pas = int((SECUNDE_BUCATA - SECUNDE_SUPRAPUNERE) * 16_000)
        lungime_bucata = int(SECUNDE_BUCATA * 16_000)
        start = 0
        text_complet = ""
        while start < total:
            if self._anulat.is_set():
                break
            sfarsit = min(total, start + lungime_bucata)
            bucata = sunet[start:sfarsit]
            try:
                rezultat = motor_local.transcrie(
                    bucata,
                    limba=self._limba,
                    termeni=getattr(self.config, "termeni", "") or "",
                    progres=self._progres_bucata(start, lungime_bucata, total),
                )
            except motor.Anulat:
                break
            except Exception as exc:
                self.aplicatie.coada.trimite(self._termina_cu_eroare, exc)
                return
            fragment = rezultat.text
            if fragment:
                text_complet += (" " if text_complet else "") + fragment
                self.aplicatie.coada.trimite(self._adauga_text, fragment)
            start += pas
        if not self._anulat.is_set():
            self.aplicatie.coada.trimite(self._termina_cu_succes, text_complet)
        else:
            self.aplicatie.coada.trimite(self._termina_anulat)

    def _progres_bucata(self, start: int, lungime: int, total: int):
        def callback(fractiune: float) -> None:
            global_frac = min(1.0, (start + lungime * fractiune) / total)
            self.aplicatie.coada.trimite(self.zona_progres.seteaza, global_frac, "Transcriu…")

        return callback

    def _adauga_text(self, fragment: str) -> None:
        curent = self.editor.text()
        if curent:
            nou = curent + " " + fragment
        else:
            nou = fragment
        self.editor.set_text(nou)
        self.eticheta_text_nou.setText(f"Nou: {fragment[-80:]}")

    def _termina_cu_succes(self, text_complet: str) -> None:
        self.zona_progres.gata("Transcrierea este terminată.")
        self.eticheta_procent.setText("100%")
        self.eticheta_ramas.setText("")
        self.buton_incepe.set_text("Transcrie din nou")
        self.buton_incepe.set_activ(True)
        self.buton_alege.set_activ(True)
        self.buton_scoate.set_activ(True)
        self.buton_anuleaza.set_activ(False)
        self.zona_finala.setVisible(True)
        self.aplicatie.bara_stare.arata(
            "Succes", "Transcrierea este terminată. Poți salva documentul.", "succes"
        )
        self.stare.text = text_complet
        self.editor.set_text(text_complet)

    def _termina_anulat(self) -> None:
        """După „Anulează”: butoanele redevin active, textul scris rămâne."""
        self.zona_progres.reseteaza()
        self.eticheta_ramas.setText("Transcrierea a fost oprită. Textul de până acum a rămas.")
        self.buton_incepe.set_text("● Începe transcrierea")
        self.buton_incepe.set_activ(True)
        self.buton_alege.set_activ(True)
        self.buton_scoate.set_activ(True)
        self.buton_anuleaza.set_activ(False)
        self.aplicatie.bara_stare.arata(
            "Oprit", "Transcrierea a fost oprită. Textul de până acum a rămas.", "atentie"
        )

    def _termina_cu_eroare(self, exc) -> None:
        self.zona_progres.reseteaza()
        self.buton_incepe.set_text("● Începe transcrierea")
        self.buton_incepe.set_activ(True)
        self.buton_alege.set_activ(True)
        self.buton_scoate.set_activ(True)
        self.buton_anuleaza.set_activ(False)
        dialog_eroare(self, "Transcrierea nu a putut fi făcută", exc)
        self.aplicatie.bara_stare.arata(
            "Eroare", "Transcrierea a eșuat. Vezi detaliile mai sus.", "pericol"
        )

    def salveaza(self, fel: str) -> None:
        text = self.editor.text()
        if not text.strip():
            anunta(self, "Fără text", "Nu există text de salvat.")
            return
        from .. import documente

        destinatie = biblioteca.nume_unic(
            biblioteca.folder("documente"), biblioteca.nume_legat(self.stare.marca or "transcriere", f".{fel}")
        )
        documente.salveaza(text, destinatie, titlu=self.stare.marca or "Transcriere")
        anunta(self, "Salvat", f"Documentul a fost salvat: {destinatie.name}")
        self.aplicatie._salvare_automata_fisier(destinatie)

    def _deschide_libreoffice(self) -> None:
        text = self.editor.text()
        if not text.strip():
            anunta(self, "Fără text", "Nu există text de deschis.")
            return
        from .. import documente

        destinatie = biblioteca.nume_unic(
            biblioteca.folder("documente"), biblioteca.nume_legat(self.stare.marca or "transcriere", ".docx")
        )
        documente.salveaza(text, destinatie, titlu=self.stare.marca or "Transcriere")
        ok = self.aplicatie._deschide_in_libreoffice(destinatie)
        if not ok:
            anunta(
                self,
                "LibreOffice",
                f"Documentul a fost salvat ({destinatie.name}), dar LibreOffice nu s-a putut deschide.",
            )

    def _ajutor(self) -> None:
        self.aplicatie.arata_ajutor("transcriere")

    def _afla_placa_video(self) -> None:
        try:
            import ctypes

            ctypes.WinDLL("nvcuda.dll")
            self._are_gpu = True
        except Exception:
            self._are_gpu = False
        if self._info is not None and getattr(self._info, "ok", False):
            self._arata_estimarea()