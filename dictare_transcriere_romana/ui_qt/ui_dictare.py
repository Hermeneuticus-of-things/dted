"""Ecranul „Dictează” PySide6: microfon + transcriere în timp real.

Înlocuiește ``ui_dictare.py`` (Tkinter). Logica:

* pornește microfonul (16 kHz mono) la apasați „Dictează”;
* transcriere pe bucăți, textul apare în editor pe rând;
* nivoul sunetului arată că microfonul funcționează;
* „Oprește” salvează textul și îl lasă în editor.
"""

from __future__ import annotations

import queue
import threading
import time
try:
    import winsound
except ImportError:
    winsound = None  # type: ignore
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import biblioteca, erori, jurnal, motor, stare as stare_modul, text_ro
from . import comun
from .comun import (
    BaraStare,
    Buton,
    ZonaDerulare,
    anunta,
    dialog_eroare,
    eticheta,
    fonturi,
    seteaza_rol,
    text_nivel,
)
from .ui_editor import Editor
from .ui_internet import avertizeaza

#: Cât de des se transcriere când vorbirea este continuă (secunde).
SECUNDE_BUCATA = 2.0
#: Minimul pentru a declanșa transcrierea la o pauză scurtă de vorbire (secunde).
SECUNDE_MINIME_PAUZA = 0.8
#: Pragul de pauză în sunet (RMS pe ultimele ~200 ms).
PRAG_RMS_LINISTE = 0.018
#: Fragmentele mai scurte se păstrează la oprire, dacă au suficientă vorbire.
SECUNDE_MINIME_LA_OPRIRE = 0.35
#: Din câte secunde de vorbire se cere afișarea provizorie live (cuvânt cu cuvânt).
SECUNDE_PROVIZORIU = 1.0
#: Intervalul minim între două transcrieri provizorii (secunde).
INTERVAL_PROVIZORIU = 0.9
#: Pragul de nivel microfon, pentru animație.
NIVEL_MAX = 1.0


def _gata_de_transcris(secunde: float, oprita: bool) -> bool:
    """La oprire, descarcă și coada mai scurtă decât o bucată normală."""
    return secunde >= SECUNDE_BUCATA or (oprita and secunde >= SECUNDE_MINIME_LA_OPRIRE)


class PaginaDictare(QWidget):
    """Ecranul „Dictează”."""

    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie
        self.stare = aplicatie.stare
        self.config = aplicatie.configurare
        self.editor: Editor = aplicatie.editor

        self._fir: threading.Thread | None = None
        self._fir_transcriere: threading.Thread | None = None
        self._coada_transcriere: "queue.Queue" = queue.Queue(maxsize=3)
        self._microfon = None
        self._anulat = threading.Event()
        self._activ = False
        self._timp_start = 0.0
        self._secunde_audio = 0.0
        self._semnuri: list[str] = []
        self._dictare_sunet = None  # Inregistrare completă (pentru „Mergi la semn", cerința 38)
        self._mini = None  # FereastraMini mereu deasupra (cerința 40 / D-8)
        self._text_dictare = ""  # textul final, pentru recuperarea la cădere (cerința 61)
        self._ultima_provizor = 0.0
        self._anulat_pana = 0.0  # „de la capăt”/„alineat”: bucățile începute înainte de acest moment se aruncă
        self._liniste_secunde = 0.0  # cât timp continuu e liniște (pentru structura automată)
        self._pauza_recenta = 0.0  # pauza de voce dinaintea bucății curente

        self._coada_cuvinte: list[str] = []
        self._timer_cuvinte = QTimer(self)
        self._timer_cuvinte.timeout.connect(self._emite_cuvant_urmator)
        self._timer_cuvinte.start(35)

        self._construieste()
        QTimer.singleShot(100, self._verifica_microfon)

    @property
    def nivel_microfon(self) -> float:
        """Nivelul curent al microfonului (0..1); 0 când microfonul e închis."""
        m = self._microfon
        return 0.0 if m is None else min(1.0, max(0.0, getattr(m, "nivel", 0.0)))

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        zona = ZonaDerulare(self, latime_minima=900)
        layout.addWidget(zona, stretch=1)

        corp = QWidget()
        cl = QVBoxLayout(corp)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(10)
        zona.interior.layout().addWidget(corp)

        # Titlu.
        titlu = eticheta(corp, "Dictează", "titlu")
        cl.addWidget(titlu)

        # Nivel microfon (animatie): bară vizibilă, cu trei culori și text.
        self.nivel_bar = comun.VumetruDb()
        self.nivel_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        cl.addWidget(self.nivel_bar)

        rand_nivel = QHBoxLayout()
        self.eticheta_nivel = eticheta(corp, "Microfonul este oprit.", "baza")
        rand_nivel.addWidget(self.eticheta_nivel, stretch=1)
        self.eticheta_nivel_cifra = eticheta(corp, "", "mica")
        seteaza_rol(self.eticheta_nivel_cifra, "secundar")
        rand_nivel.addWidget(self.eticheta_nivel_cifra)
        cl.addLayout(rand_nivel)

        # Buton start/stop.
        rand_buton = QHBoxLayout()
        self.buton_start = Buton(
            corp, "● Dictează", self._toggle, fel="principal", latime=180, inaltime=48
        )
        rand_buton.addWidget(self.buton_start)
        self.buton_opreste = Buton(
            corp, "Oprește", self._opreste, fel="pericol", latime=160, inaltime=48
        )
        self.buton_opreste.set_activ(False)
        rand_buton.addWidget(self.buton_opreste)
        self.buton_pauza = Buton(
            corp, "⏸ Pauză microfon", self._comuta_pauza, latime=220, inaltime=48
        )
        self.buton_pauza.set_activ(False)
        rand_buton.addWidget(self.buton_pauza)
        self.buton_semn = Buton(
            corp, "⏱ Semn", self._insereaza_semn, scurtatura="Ctrl+B", latime=200, inaltime=48
        )
        self.buton_semn.set_activ(False)
        rand_buton.addWidget(self.buton_semn)
        self.buton_mergi = Buton(
            corp, "Mergi la semn", self._mergi_la_semn, latime=180, inaltime=48
        )
        rand_buton.addWidget(self.buton_mergi)
        rand_buton.addStretch(1)
        cl.addLayout(rand_buton)

        # Text transcris (editor este adăugat de Aplicatie în zona de jos).
        et = eticheta(corp, "Textul apare aici pe măsură ce vorbești.", "mica")
        et.setWordWrap(True)
        cl.addWidget(et)

        # Butoane jos.
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
                "⧉ Fereastră mică",
                self._toggle_mini,
                latime=220,
                inaltime=40,
            )
        )
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
        cl.addLayout(rand_jos)

    # ------------------------------------------------------------------ microfon

    def _verifica_microfon(self) -> None:
        """Verifică microfonul ÎN FUNDAL (bug-hunt: încercarea configurațiilor
        audio poate dura secunde și ar îngheța interfața dacă rula aici)."""
        import threading

        self.eticheta_nivel.setText("Verific microfonul…")
        seteaza_rol(self.eticheta_nivel, "secundar")

        def lucru() -> None:
            from ..inregistrare import Microfon, EroareMicrofon

            try:
                test = Microfon()
                test.porneste()
                test.opreste()
                mesaj, rol = "Microfonul este gata. Apasă „Dictează”.", "succes"
            except EroareMicrofon as exc:
                mesaj, rol = "Microfonul nu este disponibil.", "pericol"
                jurnal.atentionare(f"Microfon: {exc}")
            except Exception as exc:
                mesaj, rol = "Microfonul nu este disponibil.", "pericol"
                jurnal.atentionare(f"Microfon: {exc}")
            self.aplicatie.coada.trimite(
                self._dupe_verificare_microfon, mesaj, rol
            )

        threading.Thread(target=lucru, name="verificare-microfon", daemon=True).start()

    def _dupe_verificare_microfon(self, mesaj: str, rol: str) -> None:
        self.eticheta_nivel.setText(mesaj)
        seteaza_rol(self.eticheta_nivel, rol)

    def _toggle(self) -> None:
        if self._activ:
            self._opreste()
        else:
            self._porneste()

    def _toggle_mini(self) -> None:
        """Deschide sau închide fereastra mică mereu deasupra (cerința 40 / D-8)."""
        from .ui_mini import FereastraMini

        if self._mini is None:
            self._mini = FereastraMini(self)
        if self._mini.isVisible():
            self._mini.hide()
        else:
            self._mini.show()
            self._mini.raise_()

    def _sunet(self, fel: str) -> None:
        """Cerinta 54: sunet scurt la start/stop/eroare (winsound)."""
        if winsound is None:
            return
        try:
            if fel == 'start':
                winsound.PlaySound('SystemAsterisk', winsound.SND_ALIAS | winsound.SND_ASYNC)
            elif fel == 'stop':
                winsound.PlaySound('SystemExit', winsound.SND_ALIAS | winsound.SND_ASYNC)
            elif fel == 'eroare':
                winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass


    def _porneste(self, automat: bool = False) -> None:
        from ..inregistrare import Microfon, EroareMicrofon

        if not automat:
            if not avertizeaza(self, self.aplicatie.configurare, pentru_dictare=True, fortat=True):
                # Nu avem avertizare (totul e închis) sau utilizatorul a continuat.
                pass

            # Cerinta 42: avertisment spatiu pe disc inainte de dictare.
            try:
                from .. import resurse, constante
                liber = resurse.spatiu_liber_gb(str(Path.home()))
                if liber < constante.DISC_MINIM_GB:
                    from PySide6.QtWidgets import QMessageBox
                    raspuns = QMessageBox.question(
                        self,
                        "Spatiu pe disc",
                        f"Mai ai doar {liber:.1f} GB liberi. Pentru dictare si salvare sunt recomandate cel putin {constante.DISC_MINIM_GB:.0f} GB.\n\nContinui?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if raspuns != QMessageBox.StandardButton.Yes:
                        return
            except Exception:
                pass

        if motor.biblioteci_disponibile() is False:
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

        try:
            if automat and getattr(self, "_va_microfon", None) is not None:
                self._microfon = self._va_microfon  # deja pornit (activare vocală)
                self._va_microfon = None
            else:
                self._microfon = Microfon()
                self._microfon.porneste()
        except EroareMicrofon as exc:
            dialog_eroare(self, "Microfonul nu poate fi deschis", exc)
            return

        # Cerința 52: la prima dictare, un mic asistent arată cum se aude microfonul.
        if not automat and not getattr(self.config, "asistent_microfon_vazut", False):
            self._asistent_microfon()
            try:
                from .. import config as config_modul

                self.config.asistent_microfon_vazut = True
                config_modul.salveaza(self.config)
            except Exception:
                pass

        self._activ = True
        self._anulat.clear()
        self._timp_start = time.monotonic()
        self._secunde_audio = 0.0
        self._semnuri = []
        self._dictare_sunet = None
        self._text_dictare = ""
        self._ultima_provizor = 0.0
        self._liniste_secunde = 0.0
        self._pauza_recenta = 0.0  # fiecare dictare începe curat, fără structură moștenită
        self._marca_dictare = biblioteca.marca_acum()
        self.stare.marca = self._marca_dictare
        self.buton_semn.set_activ(True)
        self.buton_pauza.set_text("⏸ Pauză microfon")
        self.buton_pauza.set_activ(True)

        # N-3/cerința 5: blocarea căilor de ieșire cât timp se dictează.
        self._blocat_de_noi = False
        mod_blocare = getattr(self.aplicatie.configurare, "blocare_dictare", "nimic") or "nimic"
        if mod_blocare in ("program", "tot"):
            from .. import blocare as modul_blocare

            try:
                self._blocat_de_noi = modul_blocare.blocheaza(mod_blocare)
            except Exception:
                self._blocat_de_noi = False
            if self._blocat_de_noi:
                self.aplicatie.bara_stare.arata(
                    "Blocat",
                    "căile de ieșire sunt tăiate cât timp dictezi.",
                    "lucru",
                )

        self.buton_start.set_text("◼ Dictează…")
        self.buton_start.set_activ(True)
        self.buton_start._fel = "pericol"
        self.buton_start._aplica_stil()
        self.buton_opreste.set_activ(True)
        self.aplicatie.bara_stare.arata("Dictează", "Vorbește în microfon.", "lucru")

        self._coada_transcriere = queue.Queue(maxsize=3)
        self._fir_transcriere = threading.Thread(
            target=self._bucla_transcriere, name="transcriere-dictare", daemon=True
        )
        self._fir_transcriere.start()
        self._fir = threading.Thread(target=self._bucla, name="dictare", daemon=True)
        self._fir.start()

        # Animația nivelului (60 ms).
        self._timer_nivel = QTimer(self)
        self._timer_nivel.timeout.connect(self._actualizeaza_nivel)
        self._timer_nivel.start(60)
        self._sunet('start')
        actualizeaza = getattr(self.aplicatie, "_actualizeaza_buton_dictare", None)
        if actualizeaza is not None:
            try:
                actualizeaza()
            except Exception:
                pass

    def _asistent_microfon(self) -> None:
        """Cerința 52: prima dată când se dictează, arată cum se aude microfonul."""
        from PySide6.QtWidgets import QDialog, QProgressBar

        dialog = QDialog(self)
        dialog.setWindowTitle("Să vedem microfonul")
        dialog.setMinimumWidth(460)
        layout = QVBoxLayout(dialog)
        eticheta_text = QLabel(
            "Spune ceva natural, de exemplu:\n„Azi este o zi frumoasă.\"\n\n"
            "Bara de mai jos arată cât de tare te aude programul. Dacă stă jos "
            "în loc să se miște, apropie-te de microfon."
        )
        eticheta_text.setFont(fonturi("baza"))
        eticheta_text.setWordWrap(True)
        layout.addWidget(eticheta_text)
        bara = QProgressBar()
        bara.setRange(0, 100)
        layout.addWidget(bara)
        microfon = self._microfon

        def citeste() -> None:
            try:
                bara.setValue(min(100, int((microfon.nivel or 0.0) * 120)))
            except Exception:
                pass

        timer = QTimer(dialog)
        timer.timeout.connect(citeste)
        timer.start(80)
        QTimer.singleShot(6000, dialog.accept)
        dialog.exec()

    def armare_va(self) -> None:
        """Activare vocală: ține microfonul deschis și pornește dictarea la voce.

        Ca la Express Dictate („Voice Activate Level”): când nivelul trece de
        pragul din Setări, dictarea pornește singură. Pragul e în dB (0 = tare).
        """
        from ..inregistrare import Microfon

        if not getattr(self.config, "activare_vocala", False):
            return
        if getattr(self, "_va_microfon", None) is not None or self._activ:
            return
        try:
            self._va_microfon = Microfon()
            self._va_microfon.porneste()
        except Exception as exc:
            jurnal.atentionare(f"Activare vocală: microfonul nu s-a putut deschide: {exc}")
            return
        if getattr(self, "_timer_va", None) is None:
            self._timer_va = QTimer(self)
            self._timer_va.timeout.connect(self._verifica_va)
            self._timer_va.start(250)
        self.aplicatie.bara_stare.arata(
            "Activare vocală", "vorbește și dictarea pornește singură.", "normal"
        )

    def _verifica_va(self) -> None:
        from .. import nivele

        if self._activ or getattr(self, "_va_microfon", None) is None:
            return
        if not getattr(self.config, "activare_vocala", False):
            return
        prag = float(getattr(self.config, "prag_activare_db", -35) or -35)
        db = nivele.amplitudine_in_db(float(getattr(self._va_microfon, "nivel", 0.0)))
        if db >= prag:
            jurnal.info(f"Activare vocală: nivel {db:.1f} dB ≥ prag {prag:.0f} dB.")
            self._porneste(automat=True)

    def _comuta_pauza(self) -> None:
        """Pauză rapidă de microfon: vorbești cu altcineva, programul nu scrie.

        Fluxul rămâne deschis (repornirea e instant), dar nu se mai strânge
        sunet; la reluare dictarea continuă exact de unde a rămas.
        """
        m = self._microfon
        if m is None:
            return
        m.pauza = not m.pauza
        if m.pauza:
            self.buton_pauza.set_text("⏵ Reprenește microfonul")
            self.nivel_bar.pune_db(-60.0)
            self.aplicatie.bara_stare.arata(
                "Pauză",
                "microfonul nu mai ascultă — vorbește liniștit. Apasă din nou ca să continui dictarea.",
                "atentie",
            )
        else:
            self.buton_pauza.set_text("⏸ Pauză microfon")
            self.aplicatie.bara_stare.arata(
                "Dictează", "microfonul ascultă din nou.", "lucru"
            )
        # Bara de transport din fereastra principală arată aceeași stare (dacă există).
        actualizeaza = getattr(self.aplicatie, "_actualizeaza_buton_dictare", None)
        if actualizeaza is not None:
            try:
                actualizeaza()
            except Exception:
                pass

    def _opreste(self) -> None:
        if self._microfon is None and not self._activ:
            # Al doilea apel (de la firul de dictare, după ce butonul a oprit
            # deja totul) — nu repetăm salvarea și mesajele.
            return
        # Oprim captarea înaintea semnalului, ca firul de dictare să poată
        # transcrie apoi tot ce a rămas în coada microfonului.
        if self._microfon is not None:
            try:
                inreg = self._microfon.opreste()
                # Păstrează tot sunetul dictării, pentru „Mergi la semn" (cerința 38).
                self._dictare_sunet = self._microfon.tot()
            except Exception:
                inreg = None
            self._microfon = None
            if inreg is not None:
                self._secunde_audio = inreg.secunde
            # Golește orice cuvânt rămas în coada de streaming direct în editor
            self._goleste_coada_cuvinte()
            # 32/34/35: sunetul rămâne disponibil pentru „▶ Ascultă” din editor
            try:
                self.aplicatie.primeste_inregistrarea(self._dictare_sunet)
            except Exception:
                pass
            # Cerința 61: salvează sunetul și textul dictării și curăță fișierele de recuperare.
            try:
                marca = getattr(self, "_marca_dictare", "") or getattr(self.stare, "marca", "") or biblioteca.marca_acum()
                if self._dictare_sunet is not None and len(getattr(self._dictare_sunet, "pcm", ())):
                    biblioteca.scrie_audio(self._dictare_sunet.pcm, marca)
                text_final = self.editor.text() if hasattr(self, "editor") else ""
                if text_final.strip():
                    biblioteca.scrie_text_legat(text_final, marca)
                biblioteca.sterge_recuperare()
                if hasattr(self.aplicatie, "_reimprospateaza_ultimele"):
                    self.aplicatie._reimprospateaza_ultimele()
            except Exception:
                pass

        self._anulat.set()
        self._activ = False
        if hasattr(self, "_timer_nivel"):
            self._timer_nivel.stop()
        self._sunet('stop')

        # Activare vocală: rearăm microfonul pentru următoarea dictare.
        if getattr(self.config, "activare_vocala", False):
            self.armare_va()

        # N-3: dacă am blocat căile de ieșire la pornirea dictării, le aducem înapoi.
        if getattr(self, "_blocat_de_noi", False):
            from .. import blocare as modul_blocare

            self._blocat_de_noi = False
            try:
                modul_blocare.deblocheaza_acum()
            except Exception:
                pass

        self.buton_start.set_text("● Dictează")
        self.buton_start._fel = "principal"
        self.buton_start._aplica_stil()
        self.buton_start.set_activ(True)
        self.buton_opreste.set_activ(False)
        self.buton_pauza.set_text("⏸ Pauză microfon")
        self.buton_pauza.set_activ(False)
        self.buton_semn.set_activ(False)
        from .. import nivele as _nivele

        self.nivel_bar.pune_db(_nivele.DB_MINIM)
        self.eticheta_nivel.setText("Dictarea s-a oprit.")
        actualizeaza = getattr(self.aplicatie, "_actualizeaza_buton_dictare", None)
        if actualizeaza is not None:
            try:
                actualizeaza()
            except Exception:
                pass
        self.aplicatie.bara_stare.arata(
            "Gata", f"Dictarea s-a terminat ({self._secunde_audio:.1f} s).", "succes"
        )

    def _eroare_microfon_qt(self, exc: Exception) -> None:
        """Cerinta 58: microfon deconectat -> oprire curata + salvare text."""
        self._activ = False
        if hasattr(self, "_timer_nivel"):
            self._timer_nivel.stop()
        if self._microfon is not None:
            try:
                inreg = self._microfon.opreste()
            except Exception:
                inreg = None
            self._microfon = None
        self.buton_start.set_text("▶ Dictează")
        self.buton_start._fel = "principal"
        self.buton_start._aplica_stil()
        self.buton_start.set_activ(True)
        self.buton_opreste.set_activ(False)
        self.buton_semn.set_activ(False)
        from .. import nivele as _nivele

        self.nivel_bar.pune_db(_nivele.DB_MINIM)
        self.eticheta_nivel.setText("Microfonul s-a deconectat.")
        self.aplicatie.bara_stare.arata(
            "Eroare microfon",
            "Microfonul s-a deconectat. Textul transcris pana acum a fost salvat.",
            "problema",
        )
        # Salvare automata a textului (cerinta 58)
        try:
            from .. import biblioteca
            text = self.aplicatie.editor.text() if hasattr(self.aplicatie, "editor") else ""
            if text.strip():
                marca = biblioteca.marca_acum()
                biblioteca.scrie_text(text, marca)
        except Exception:
            pass

    def _actualizeaza_nivel(self) -> None:
        from .. import nivele

        if self._microfon is None:
            return
        amplitudine = min(1.0, float(self._microfon.nivel))
        db = nivele.amplitudine_in_db(amplitudine)
        self.nivel_bar.pune_db(db)
        text, rol = text_nivel(int(amplitudine * 1000))
        # Textul de stare („Te aud” / „Prea încet” / „Prea tare” / „Doar zgomot”) + dB.
        self.eticheta_nivel.setText(f"● {text}")
        rol_eticheta = {"verde": "verde", "galben": "atentie", "rosu": "pericol"}[rol]
        seteaza_rol(self.eticheta_nivel, rol_eticheta)
        self.eticheta_nivel_cifra.setText(nivele.text_db(db))
        self._auto_volum(db)

    def _auto_volum(self, db: float) -> None:
        """Aduce SINGURĂ volumul microfonului când e risc de distorsiune (0 dB)
        sau când abia se aude — cerința utilizatorului: anti-distorsiune automată."""
        from .. import nivele

        self._varf_fereastra = max(getattr(self, "_varf_fereastra", -99.0), db)
        # Distorsiunea se oprește IMEDIAT (nu așteptăm fereastra).
        if self._varf_fereastra >= nivele.DB_ATENTIE:
            self._varf_fereastra = -99.0
            self._regleaza_volumul("coboara")
            return
        acum = time.monotonic()
        if acum - getattr(self, "_ultima_evaluare_auto", 0.0) < 2.0:
            return
        self._ultima_evaluare_auto = acum
        decizie = nivele.decizie_volum(self._varf_fereastra)
        self._varf_fereastra = -99.0
        if decizie:
            self._regleaza_volumul(decizie)

    def _regleaza_volumul(self, decizie: str) -> None:
        """Schimbă efectiv volumul Windows al microfonului (cu limite și pauze)."""
        from .. import nivele

        if not getattr(self.config, "auto_volum", True):
            return
        if time.monotonic() - getattr(self, "_ultimul_reglaj_volum", 0.0) < 3.0:
            return
        self._ultimul_reglaj_volum = time.monotonic()
        nou = nivele.aplica_decizia(decizie)
        if nou is None:
            return
        mesaj = (
            "am coborât nivelul microfonului ca să nu se distorsioneze"
            if decizie == "coboara"
            else "am urcat nivelul microfonului — abia se auzea"
        )
        self.aplicatie.bara_stare.arata(
            "Microfon", f"Automat: {mesaj} (acum {int(round(nou * 100))}%).", "lucru"
        )

    # ------------------------------------------------------------------ bucla dictare

    def _bucla(self) -> None:
        """Captură sunet și predarea bucăților firului de transcriere, în fundal.

        Captura NU mai așteaptă după model: când o bucată e gata (pauză scurtă
        sau 2,0 s de vorbire continuă), e predată firului „transcriere-dictare”
        și captura continuă imediat — dicția non-stop nu se mai blochează.
        """
        from ..inregistrare import Microfon

        # Copie locală: „Oprește” pune self._microfon = None din firul interfeței.
        microfon = self._microfon
        if microfon is None:
            return
        microfon.pauza = False
        # Pragurile de structură sunt alese de utilizator (Setări → Comenzi vocale).
        prag_rand = max(1.0, float(getattr(self.config, "pauza_rand_sec", 4) or 4))
        prag_paragraf = max(prag_rand + 1.0, float(getattr(self.config, "pauza_paragraf_sec", 8) or 8))

        while True:
            # Așteaptă până când utilizatorul face o pauză scurtă (>= 200 ms) după cel puțin 0.8s
            # sau când s-a atins durata maximă a bucății (2.0s la vorbire continuă fără oprire).
            pauza_detectata = False
            liniste_secunde = getattr(self, "_liniste_secunde", 0.0)
            pauza_recenta = getattr(self, "_pauza_recenta", 0.0)
            while not self._anulat.is_set():
                time.sleep(0.04)
                sec_curent = microfon.scurgere()
                # Pauzele lungi structurează singure textul: liniște > 4 s →
                # linie nouă; > 8 s → paragraf nou (bucata următoare le primește).
                try:
                    import numpy as _np

                    fen = microfon.fereastra_curenta()
                    if len(fen) >= int(0.2 * 16_000):
                        coada_sil = fen[-int(0.2 * 16_000):]
                        if float(_np.sqrt(_np.mean(coada_sil ** 2))) < PRAG_RMS_LINISTE:
                            liniste_secunde += 0.04
                        else:
                            if liniste_secunde >= prag_rand:
                                pauza_recenta = liniste_secunde  # pauza s-a încheiat: o ținem minte
                            liniste_secunde = 0.0
                except Exception:
                    pass
                if sec_curent >= SECUNDE_MINIME_PAUZA and hasattr(microfon, "fereastra_curenta"):
                    try:
                        import numpy as np

                        fereastra = microfon.fereastra_curenta()
                        if len(fereastra) >= int(SECUNDE_MINIME_PAUZA * 16_000):
                            coada_liniste = fereastra[-int(0.20 * 16_000):]
                            rms_coada = float(np.sqrt(np.mean(coada_liniste ** 2)))
                            rms_peak = float(np.sqrt(np.mean(fereastra ** 2)))
                            if rms_coada < PRAG_RMS_LINISTE or (rms_peak > 0.03 and rms_coada < 0.22 * rms_peak):
                                pauza_detectata = True
                                break
                    except Exception:
                        pass
                if sec_curent >= SECUNDE_BUCATA:
                    break
                # Afișare provizorie live: cuvintele apar pe ecran cât timp
                # vorbim, înainte ca bucata să fie închisă și confirmată.
                if sec_curent >= SECUNDE_PROVIZORIU:
                    self._cere_provizoriu(microfon)

            secunde_buffer = microfon.scurgere()
            oprita = self._anulat.is_set()
            if not (_gata_de_transcris(secunde_buffer, oprita) or (pauza_detectata and secunde_buffer >= SECUNDE_MINIME_LA_OPRIRE)):
                if oprita:
                    break
                continue

            try:
                sunet = microfon.preia()
            except Exception as exc:
                jurnal.atentionare(f"Microfonul s-a oprit in timpul dictarii: {exc}")
                self._sunet('eroare')
                self.aplicatie.coada.trimite(self._eroare_microfon_qt, exc)
                self._anulat.set()
                break
            if len(sunet) < int(SECUNDE_MINIME_LA_OPRIRE * 16_000):  # prea puțin pentru recunoaștere
                if self._anulat.is_set():
                    break
                continue
            try:
                import numpy as _np

                rms_tot = float(_np.sqrt(_np.mean(sunet ** 2))) if len(sunet) else 0.0
            except Exception:
                rms_tot = 1.0
            if rms_tot < PRAG_RMS_LINISTE and not self._anulat.is_set():
                continue  # doar liniște: nimic de transcris; pauza se numără singură
            self._secunde_audio += len(sunet) / 16_000.0
            prefix = ""
            if pauza_recenta >= prag_paragraf:
                prefix = "\n\n"  # pauză lungă: idee nouă
            elif pauza_recenta >= prag_rand:
                prefix = "\n"     # pauză medie: rând nou
            pauza_recenta = 0.0

            # Cerința 61: salvează pe bucăți sunetul înregistrat până acum, pentru recuperare la cădere.
            if hasattr(microfon, "tot"):
                try:
                    tot_acum = microfon.tot()
                    if tot_acum is not None and len(getattr(tot_acum, "pcm", ())):
                        biblioteca.scrie_recuperare_audio(tot_acum.pcm, getattr(tot_acum, "rata", 16000) or 16000)
                except Exception:
                    pass

            # Pregătirea sunetului, opțională (51/52): întâi volumul, apoi pauzele.
            if getattr(self.config, "pregateste_audio", False) or getattr(
                self.config, "scurteaza_pauze", False
            ):
                from .. import codecuri

                if getattr(self.config, "pregateste_audio", False):
                    sunet = codecuri.normalizeaza(sunet)
                if getattr(self.config, "scurteaza_pauze", False):
                    sunet = codecuri.scurteaza_pauzele(sunet, rate=16_000)

            # Feedback imediat: utilizatorul știe că programul „scrie”, nu s-a oprit.
            try:
                self.aplicatie.coada.trimite(self._spune_procesare, len(sunet) / 16_000.0)
            except Exception:
                pass
            # Predă bucata firului de transcriere — captura reia imediat.
            try:
                self._preda_transcriere(("final", sunet, time.monotonic(), prefix))
            except Exception as exc:
                jurnal.atentionare(f"Eroare transcriere dictare: {exc}")
                continue

        self._liniste_secunde = liniste_secunde
        self._pauza_recenta = pauza_recenta
        # La ieșire: firul de transcriere termină tot ce a primit, apoi salvarea.
        if self._fir_transcriere is not None:
            try:
                self._coada_transcriere.put(("gata", None, 0.0, ""))
            except Exception:
                pass
            self._fir_transcriere.join(timeout=180)
        self.aplicatie.coada.trimite(self._opreste)

    def _bucla_transcriere(self) -> None:
        """Fir de transcriere: preia bucățile din coadă și le scrie în editor.

        Bucățile finale înlocuiesc afișarea provizorie (care a arătat deja
        cuvintele pe măsură ce erau rostite). Tot aici se ține textul pentru
        recuperarea la cădere (cerința 61).
        """
        while True:
            try:
                fel, sunet, predat_la, prefix = self._coada_transcriere.get()
            except Exception:
                return
            if fel == "gata" or sunet is None:
                return
            if predat_la <= self._anulat_pana:
                # „P alineat”/„I alineat” au șters textul dintre timp: bucata asta
                # ar re-scrie fraza pe care utilizatorul tocmai a anulat-o.
                continue
            motor_local = self.aplicatie._motor
            if motor_local is None:
                continue
            try:
                rezultat = motor_local.transcrie(
                    sunet,
                    limba=getattr(self.config, "limba", "ro") or "ro",
                    termeni=getattr(self.config, "termeni", "") or "",
                    progres=None,
                    faza=None,
                    rapid=True,
                    provizoriu=(fel == "provizoriu"),
                )
            except motor.Anulat:
                continue
            except Exception as exc:
                jurnal.atentionare(f"Eroare transcriere dictare: {exc}")
                continue
            fragment = (rezultat.text or "").strip()
            if not fragment:
                continue
            if prefix:
                fragment = prefix + fragment  # pauza lungă a decis structura
            if fel == "provizoriu":
                self.aplicatie.coada.trimite(self._adauga_text_live, fragment)
            else:
                from .. import inlocuiri, text_ro

                curatat = text_ro.marcaje_paragraf(
                    text_ro.curata_repetari(inlocuiri.aplica(fragment))
                )
                if curatat:
                    self._text_dictare += (" " if self._text_dictare else "") + curatat
                    try:
                        biblioteca.scrie_recuperare(
                            self._text_dictare,
                            getattr(self, "_marca_dictare", "") or "dictare",
                        )
                    except Exception:
                        pass
                    self.aplicatie.coada.trimite(self._adauga_text, curatat)

    def _cere_provizoriu(self, microfon) -> None:
        """Cere o transcriere provizorie a ferestrei curente, fără s-o golească.

        Se întâmplă doar când modelul e „în pas” cu dictarea (coada goală) —
        pe calculatoare mai lente afișarea provizorie cedează automat locul
        bucatelor finale, ca dictarea să nu rămână în urmă.
        """
        acum = time.monotonic()
        if acum - self._ultima_provizor < INTERVAL_PROVIZORIU:
            return
        if not self._coada_transcriere.empty():
            return
        try:
            fereastra = microfon.fereastra_curenta()
        except Exception:
            return
        if len(fereastra) < int(SECUNDE_PROVIZORIU * 16_000):
            return
        self._ultima_provizor = acum
        try:
            self._coada_transcriere.put_nowait(("provizoriu", fereastra, time.monotonic(), ""))
        except queue.Full:
            pass

    def _preda_transcriere(self, element) -> None:
        """Pune bucata în coada firului de transcriere, fără să piardă sunet.

        Dacă modelul rămâne în urmă (procesor lent), captura așteaptă până se
        face loc — niciun cuvânt dictat nu se pierde.
        """
        limita = time.monotonic() + 180.0
        while True:
            try:
                self._coada_transcriere.put(element, timeout=0.2)
                return
            except queue.Full:
                if time.monotonic() > limita:
                    jurnal.atentionare("Coada de transcriere nu se golește; renunț la bucată.")
                    return

    def _spune_procesare(self, secunde: float) -> None:
        """Arată în bara de stare că ultimele secunde se transformă în text."""
        if self._activ:
            self.aplicatie.bara_stare.arata(
                "Scriu…", f"Scriu ultimele {secunde:.0f} secunde spuse. Poți vorbi mai departe.", "lucru"
            )

    def _emite_cuvant_urmator(self) -> None:
        """Emite cuvintele pe ecran în flux continuu (efect de mașină de scris / streaming)."""
        if not getattr(self, "_coada_cuvinte", None):
            return
        viteza = 1
        if len(self._coada_cuvinte) > 12:
            viteza = 3
        elif len(self._coada_cuvinte) > 6:
            viteza = 2
        for _ in range(viteza):
            if not self._coada_cuvinte:
                break
            t = self._coada_cuvinte.pop(0)
            if t == "\n\n":
                if hasattr(self, "editor") and hasattr(self.editor, "_control"):
                    c = self.editor._control.textCursor()
                    c.insertText("\n\n")
            else:
                if hasattr(self, "editor"):
                    self.editor.insereaza(t)
        if hasattr(self, "editor"):
            self.stare.text = self.editor.text()

    def _goleste_coada_cuvinte(self) -> None:
        """Golește imediat toate cuvintele rămase în editor (la oprire sau teste)."""
        while getattr(self, "_coada_cuvinte", None):
            t = self._coada_cuvinte.pop(0)
            if t == "\n\n":
                if hasattr(self, "editor") and hasattr(self.editor, "_control"):
                    c = self.editor._control.textCursor()
                    c.insertText("\n\n")
            else:
                if hasattr(self, "editor"):
                    self.editor.insereaza(t)
        if hasattr(self, "editor"):
            self.stare.text = self.editor.text()

    def _adauga_text_live(self, fragment: str) -> None:
        """Afișează provizoriu pe ecran cuvintele pe măsură ce sunt rostite („mama… are… mere…”)."""
        from .. import inlocuiri, text_ro

        if not self._activ:
            return  # dictarea s-a oprit între timp: nu mai afișăm provizorii rămași
        fragment = text_ro.marcaje_paragraf(text_ro.curata_repetari(inlocuiri.aplica(fragment)))
        if not fragment:
            return
        if hasattr(self.editor, "arata_provizoriu"):
            self.editor.arata_provizoriu(fragment)

    def _adauga_text(self, fragment: str) -> None:
        """Textul dictat este împărțit în cuvinte și afișat cuvânt cu cuvânt pe ecran."""
        from .. import inlocuiri, text_ro

        fragment = text_ro.marcaje_paragraf(text_ro.curata_repetari(inlocuiri.aplica(fragment)))
        if not fragment:
            return
        parag = fragment.split("\n\n")
        if not hasattr(self, "_coada_cuvinte"):
            self._coada_cuvinte = []
        for idx, p in enumerate(parag):
            words = [w for w in p.split(" ") if w]
            self._coada_cuvinte.extend(words)
            if idx < len(parag) - 1:
                self._coada_cuvinte.append("\n\n")
        # Dacă timerul nu rulează (ex. în teste fără buclă de evenimente), golește imediat:
        if not getattr(self, "_timer_cuvinte", None) or not self._timer_cuvinte.isActive():
            self._goleste_coada_cuvinte()

    # ------------------------------------------------------------------ comenzi

    def _ia_de_la_capat(self) -> None:
        """F6 — „⏎ P alineat”: șterge fraza neterminată și deschide un paragraf
        nou care începe direct de la margine, fără alineat (stilul de pe web).

        Merge și în timpul dictării, și după: cuvintele care așteaptă încă în
        coada de afișare se aruncă, iar bucățile începute între timp sunt
        anulate pe momentul predării — fraza ștearsă nu mai reapare.
        """
        self._anulat_pana = time.monotonic()
        if getattr(self, "_coada_cuvinte", None):
            self._coada_cuvinte.clear()
        if hasattr(self, "editor"):
            try:
                self.editor.paragraf_nou(cu_alineat=False)
            except Exception:
                pass
            self.stare.text = self.editor.text()
        self.aplicatie.bara_stare.arata(
            "P alineat", "fraza ștearsă — scrii într-un paragraf nou, fără alineat.", "lucru"
        )

    def _idee_noua(self) -> None:
        """Shift+F6 — „⇥ I alineat”: șterge fraza curentă și deschide un paragraf
        nou cu alineat (tab în față), ca în cărțile tipărite."""
        self._anulat_pana = time.monotonic()
        if getattr(self, "_coada_cuvinte", None):
            self._coada_cuvinte.clear()
        if hasattr(self, "editor"):
            try:
                self.editor.paragraf_nou(cu_alineat=True)
            except Exception:
                pass
            self.stare.text = self.editor.text()
        self.aplicatie.bara_stare.arata(
            "I alineat", "fraza ștearsă — scrii într-un paragraf nou, cu alineat (tab).", "lucru"
        )

    def salveaza(self) -> None:
        text = self.editor.text()
        if not text.strip():
            anunta(self, "Fără text", "Nu există text de salvat.")
            return
        from .. import documente

        destinatie = biblioteca.nume_unic(
            biblioteca.folder("documente"),
            biblioteca.nume_legat("dictare", ".docx"),
        )
        documente.salveaza(text, destinatie, titlu="Dictare")
        anunta(self, "Salvat", f"Documentul a fost salvat: {destinatie.name}")

    def _ajutor(self) -> None:
        self.aplicatie.arata_ajutor("dictare")

    # ------------------------------------------------------------------ semne (Ctrl+B)

    def _insereaza_semn(self) -> None:
        """Adaugă un semn [mm:ss] în text, la cursor, fără să se piardă Undo (cerința 37)."""
        if not self._activ:
            return
        secunde = max(0, int(time.monotonic() - self._timp_start))
        marca = f"{secunde // 60:02d}:{secunde % 60:02d}"
        self._semnuri.append(marca)
        self.editor.insereaza(f"[{marca}]")
        self.stare.text = self.editor.text()
        self.aplicatie.bara_stare.arata("Semn", f"semn adăugat la {marca}.", "lucru")

    def _mergi_la_semn(self) -> None:
        """Sare la un semn de-a lungul textului, și în sunet (cerința 38)."""
        if not self._semnuri:
            anunta(self, "Fără semne", "Nu ai adăugat încă niciun semn (Ctrl+B).")
            return
        aleasa, ok = QInputDialog.getItem(
            self, "Mergi la semn", "Alege la care semn să mergi:", self._semnuri, 0, False
        )
        if ok and aleasa:
            self.editor.sari_la(f"[{aleasa}]")
            self._reda_din_semn(aleasa)

    def _reda_din_semn(self, marca: str) -> None:
        """Redă înregistrarea dictării de la semnul [mm:ss] încolo (cerința 38)."""
        try:
            minute, sec = marca.split(":")
            secunde = int(minute) * 60 + int(sec)
        except (ValueError, TypeError):
            return
        sunet = self._dictare_sunet
        if sunet is None or not len(sunet.pcm) or sunet.rata <= 0:
            anunta(self, "Fără redare", "Nu există înregistrarea dictării de redat.")
            return
        start = int(secunde * sunet.rata)
        if start >= len(sunet.pcm):
            anunta(self, "În afara sunetului", "Semnul este după sfârșitul înregistrării.")
            return
        from .. import inregistrare
        inregistrare.opreste_redarea()
        inregistrare.reda(sunet.pcm[start:], sunet.rata)
        self.aplicatie.bara_stare.arata("Redare", f"Redau de la semnul {marca}.", "lucru")
