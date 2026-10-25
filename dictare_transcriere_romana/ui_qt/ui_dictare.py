"""Ecranul „Dictează” PySide6: microfon + transcriere în timp real.

Înlocuiește ``ui_dictare.py`` (Tkinter). Logica:

* pornește microfonul (16 kHz mono) la apasați „Dictează”;
* transcriere pe bucăți, textul apare în editor pe rând;
* nivoul sunetului arată că microfonul funcționează;
* „Oprește” salvează textul și îl lasă în editor.
"""

from __future__ import annotations

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

#: Cât de des se transcriere (secunde).
SECUNDE_BUCATA = 4.0
#: Fragmentele mai scurte se păstrează la oprire, dacă au suficientă vorbire.
SECUNDE_MINIME_LA_OPRIRE = 0.5
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
        self._microfon = None
        self._anulat = threading.Event()
        self._activ = False
        self._timp_start = 0.0
        self._secunde_audio = 0.0
        self._semnuri: list[str] = []
        self._dictare_sunet = None  # Inregistrare completă (pentru „Mergi la semn", cerința 38)
        self._mini = None  # FereastraMini mereu deasupra (cerința 40 / D-8)

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

        # Ctrl+B = adaugă un semn de dictare (D-7 / cerința 37).
        QShortcut(QKeySequence("Ctrl+B"), self, self._insereaza_semn)

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


    def _porneste(self) -> None:
        from ..inregistrare import Microfon, EroareMicrofon

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
            self._microfon = Microfon()
            self._microfon.porneste()
        except EroareMicrofon as exc:
            dialog_eroare(self, "Microfonul nu poate fi deschis", exc)
            return

        # Cerința 52: la prima dictare, un mic asistent arată cum se aude microfonul.
        if not getattr(self.config, "asistent_microfon_vazut", False):
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
        self.buton_semn.set_activ(True)

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

        self._fir = threading.Thread(target=self._bucla, name="dictare", daemon=True)
        self._fir.start()

        # Animația nivelului (60 ms).
        self._timer_nivel = QTimer(self)
        self._timer_nivel.timeout.connect(self._actualizeaza_nivel)
        self._timer_nivel.start(60)
        self._sunet('start')

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

    def _opreste(self) -> None:        # Oprim captarea înaintea semnalului, ca firul de dictare să poată
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
            # 32/34/35: sunetul rămâne disponibil pentru „▶ Ascultă” din editor
            try:
                self.aplicatie.primeste_inregistrarea(self._dictare_sunet)
            except Exception:
                pass

        self._anulat.set()
        self._activ = False
        if hasattr(self, "_timer_nivel"):
            self._timer_nivel.stop()
        self._sunet('stop')

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
        self.buton_semn.set_activ(False)
        from .. import nivele as _nivele

        self.nivel_bar.pune_db(_nivele.DB_MINIM)
        self.eticheta_nivel.setText("Dictarea s-a oprit.")
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
        """Captură sunet și transcriere pe bucăți, în fundal."""
        from ..inregistrare import Microfon

        # Copie locală: „Oprește” pune self._microfon = None din firul interfeței.
        microfon = self._microfon
        if microfon is None:
            return
        text_acum = ""

        while True:
            # Așteaptă o bucată completă, dar la oprire descarcă și restul scurt.
            while microfon.scurgere() < SECUNDE_BUCATA and not self._anulat.is_set():
                time.sleep(0.1)
            secunde_buffer = microfon.scurgere()
            oprita = self._anulat.is_set()
            if not _gata_de_transcris(secunde_buffer, oprita):
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
            self._secunde_audio += len(sunet) / 16_000.0

            # Pregătirea sunetului, opțională (51/52): întâi volumul, apoi pauzele.
            if getattr(self.config, "pregateste_audio", False) or getattr(
                self.config, "scurteaza_pauze", False
            ):
                from .. import codecuri

                if getattr(self.config, "pregateste_audio", False):
                    sunet = codecuri.normalizeaza(sunet)
                if getattr(self.config, "scurteaza_pauze", False):
                    sunet = codecuri.scurteaza_pauzele(sunet, rate=16_000)

            try:
                # Feedback imediat: utilizatorul știe că programul „scrie”, nu s-a oprit.
                try:
                    self.aplicatie.coada.trimite(self._spune_procesare, len(sunet) / 16_000.0)
                except Exception:
                    pass
                motor_local = self.aplicatie._motor
                rezultat = motor_local.transcrie(
                    sunet,
                    limba=getattr(self.config, "limba", "ro") or "ro",
                    termeni=getattr(self.config, "termeni", "") or "",
                    progres=None,
                    faza=None,
                )
            except motor.Anulat:
                break
            except Exception as exc:
                jurnal.atentionare(f"Eroare transcriere dictare: {exc}")
                continue

            fragment = (rezultat.text or "").strip()
            if fragment:
                text_acum += (" " if text_acum else "") + fragment
                self.aplicatie.coada.trimite(self._adauga_text, fragment)

        self.aplicatie.coada.trimite(self._opreste)

    def _spune_procesare(self, secunde: float) -> None:
        """Arată în bara de stare că ultimele secunde se transformă în text."""
        if self._activ:
            self.aplicatie.bara_stare.arata(
                "Scriu…", f"Scriu ultimele {secunde:.0f} secunde spuse. Poți vorbi mai departe.", "lucru"
            )

    def _adauga_text(self, fragment: str) -> None:
        # Textul dictat se inserează la cursor, cu un singur Ctrl+Z per fragment
        # (cerința 48): nu mai înlocuim tot textul prin set_text.
        from .. import inlocuiri, text_ro

        fragment = text_ro.curata_repetari(inlocuiri.aplica(fragment))
        if not fragment:
            return
        self.editor.insereaza(fragment)
        self.stare.text = self.editor.text()

    # ------------------------------------------------------------------ comenzi

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
