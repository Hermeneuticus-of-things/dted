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
        self.nivel_bar = QProgressBar()
        self.nivel_bar.setObjectName("nivel")
        self.nivel_bar.setProperty("chunk", "verde")
        self.nivel_bar.setRange(0, 1000)
        self.nivel_bar.setValue(0)
        self.nivel_bar.setTextVisible(False)
        self.nivel_bar.setMinimumHeight(18)
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
        from ..inregistrare import Microfon, EroareMicrofon

        try:
            test = Microfon()
            test.porneste()
            test.opreste()
            self.eticheta_nivel.setText("Microfonul este gata. Apasă „Dictează”.")
            seteaza_rol(self.eticheta_nivel, "succes")
        except EroareMicrofon as exc:
            self.eticheta_nivel.setText("Microfonul nu este disponibil.")
            seteaza_rol(self.eticheta_nivel, "pericol")
            jurnal.atentionare(f"Microfon: {exc}")

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

        self._activ = True
        self._anulat.clear()
        self._timp_start = time.monotonic()
        self._secunde_audio = 0.0
        self._semnuri = []
        self._dictare_sunet = None
        self.buton_semn.set_activ(True)

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

    def _opreste(self) -> None:
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

        self._anulat.set()
        self._activ = False
        if hasattr(self, "_timer_nivel"):
            self._timer_nivel.stop()
        self._sunet('stop')

        self.buton_start.set_text("● Dictează")
        self.buton_start._fel = "principal"
        self.buton_start._aplica_stil()
        self.buton_start.set_activ(True)
        self.buton_opreste.set_activ(False)
        self.buton_semn.set_activ(False)
        self.nivel_bar.setValue(0)
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
        self.nivel_bar.setValue(0)
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
        if self._microfon is None:
            return
        nivel = min(1000, int(self._microfon.nivel * 1000))
        self.nivel_bar.setValue(nivel)
        text, rol = text_nivel(nivel)
        if self.nivel_bar.property("chunk") != rol:
            self.nivel_bar.setProperty("chunk", rol)
            self.nivel_bar.style().unpolish(self.nivel_bar)
            self.nivel_bar.style().polish(self.nivel_bar)
        # Textul de stare („Te aud” / „Prea încet” / „Prea tare” / „Doar zgomot”).
        self.eticheta_nivel.setText(f"● {text}")
        rol_eticheta = {"verde": "verde", "galben": "atentie", "rosu": "pericol"}[rol]
        seteaza_rol(self.eticheta_nivel, rol_eticheta)
        self.eticheta_nivel_cifra.setText(f"{nivel // 10}%")

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

            try:
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

    def _adauga_text(self, fragment: str) -> None:
        # Textul dictat se inserează la cursor, cu un singur Ctrl+Z per fragment
        # (cerința 48): nu mai înlocuim tot textul prin set_text.
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
