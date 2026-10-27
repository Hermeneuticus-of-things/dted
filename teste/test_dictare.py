"""Regresii pentru fluxul de dictare pe bucăți."""

from __future__ import annotations

import os
import queue
import sys
import threading
from pathlib import Path
from threading import Event
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from dictare_transcriere_romana.ui_qt.ui_dictare import PaginaDictare, _gata_de_transcris


def test_fragmentul_sub_patru_secunde_se_proceseaza_dupa_oprire():
    assert not _gata_de_transcris(1.9, False)
    assert _gata_de_transcris(1.9, True)
    assert not _gata_de_transcris(0.34, True)

    audio_final = [0.0] * 16_000

    class MicrofonTest:
        def scurgere(self):
            return len(audio_final) / 16_000 if audio_final else 0.0

        def preia(self):
            sunet = audio_final[:]
            audio_final.clear()
            return sunet

    class MotorTest:
        def __init__(self):
            self.lungimi = []

        def transcrie(self, sunet, **_optiuni):
            self.lungimi.append(len(sunet))
            return SimpleNamespace(text="Bună ziua, România.")

    class CoadaTest:
        def trimite(self, functie, *argumente):
            functie(*argumente)

    class DictareTest:
        def __init__(self):
            self._microfon = MicrofonTest()
            self._anulat = Event()
            self._anulat.set()  # utilizatorul a apăsat deja „Oprește”
            self._secunde_audio = 0.0
            self._activ = True
            self._text_dictare = ""
            self._marca_dictare = "test"
            self._ultima_provizor = 0.0
            self.config = SimpleNamespace(limba="ro", termeni="")
            self.motor = MotorTest()
            self.aplicatie = SimpleNamespace(
                _motor=self.motor,
                coada=CoadaTest(),
            )
            self.fragmente = []
            self.finalizata = False
            # Firul de transcriere real: _bucla predă bucata în coadă, firul o transcrie.
            self._coada_transcriere = queue.Queue(maxsize=3)
            self._fir_transcriere = threading.Thread(
                target=PaginaDictare._bucla_transcriere, args=(self,), daemon=True
            )
            self._fir_transcriere.start()
            # Obiectul de test nu e un PaginaDictare complet: predicăm doar predarea.
            self._preda_transcriere = self._coada_transcriere.put

        def _adauga_text(self, fragment):
            self.fragmente.append(fragment)

        def _opreste(self):
            self.finalizata = True

    dictare = DictareTest()
    PaginaDictare._bucla(dictare)
    dictare._fir_transcriere.join(timeout=30)

    assert dictare.motor.lungimi == [16_000]
    assert dictare.fragmente == ["Bună ziua, România."]
    assert dictare.finalizata


def test_afisare_live_cuvant_cu_cuvant_in_editor():
    from PySide6.QtWidgets import QApplication
    from dictare_transcriere_romana.ui_qt.ui_editor import Editor
    from dictare_transcriere_romana import stare as stare_modul

    _app = QApplication.instance() or QApplication([])
    ed = Editor(None, stare_modul.Stare())
    ed.set_text("Început.")
    # Cuvintele apar live pe măsură ce sunt rostite
    ed.arata_provizoriu("mama")
    assert ed.text() == "Început. mama"
    ed.arata_provizoriu("mama are")
    assert ed.text() == "Început. mama are"
    ed.arata_provizoriu("mama are mere")
    assert ed.text() == "Început. mama are mere"
    # La finalizarea bucății, textul provizoriu este înlocuit curat cu forma finală
    ed.insereaza("Mama are mere.")
    assert ed.text() == "Început. Mama are mere."


def test_flux_streaming_cuvinte_pagina_dictare():
    from PySide6.QtWidgets import QApplication
    from dictare_transcriere_romana.ui_qt.ui_editor import Editor
    from dictare_transcriere_romana import stare as stare_modul

    _app = QApplication.instance() or QApplication([])
    stare = stare_modul.Stare()
    ed = Editor(None, stare)

    class DummyApp:
        pass

    dummy = DummyApp()
    dummy.stare = stare
    dummy.configurare = SimpleNamespace(asistent_microfon_vazut=True, blocare_dictare="nimic")
    dummy.editor = ed
    dummy.coada = SimpleNamespace(trimite=lambda f, *a, **k: f(*a, **k))

    pagina = PaginaDictare(None, dummy)
    # Adăugăm un fragment cu mai multe cuvinte
    pagina._adauga_text("Ana are mere.")
    pagina._goleste_coada_cuvinte()
    assert "Ana" in ed.text()
    assert "are" in ed.text()
    assert "mere." in ed.text()


def test_pauza_microfon_nu_mai_strange_sunet():
    """Pauză rapidă: fluxul rulează, dar programul nu strânge sunetul."""
    import numpy as np

    from dictare_transcriere_romana.inregistrare import Microfon

    m = Microfon()
    date = np.full((1600, 1), 0.25, dtype=np.float32)  # 0,1 s la 16 kHz, sunet real

    m._primeste(date, 1600, None, "running")
    assert m.scurgere() > 0.0
    assert m.nivel > 0.0

    inainte = m.scurgere()
    m.pauza = True
    m._primeste(date, 1600, None, "running")
    assert m.scurgere() == inainte  # nimic nou strâns în pauză
    assert m.nivel == 0.0  # vumetrul arată liniște — se vede clar că e pauză

    m.pauza = False
    m._primeste(date, 1600, None, "running")
    assert m.scurgere() > inainte  # reluarea strânge din nou


def test_calea_rapida_de_dictare_fara_timpi_si_beam_unu():
    """La dictare: beam 1, fără timpii de cuvinte; la fișiere: calitate maximă."""
    import numpy as np

    from dictare_transcriere_romana.motor import MotorWhisper

    apeluri: list[dict] = []

    class ModelTest:
        def transcribe(self, audio, **kwargs):
            apeluri.append(kwargs)
            return iter([]), SimpleNamespace(language="ro")

    m = MotorWhisper()
    m._model = ModelTest()
    m._anulat = Event()
    audio = np.zeros(32_000, dtype=np.float32)

    m._ruleaza(audio, "ro", "", None, rapid=True, provizoriu=False)
    m._ruleaza(audio, "ro", "", None, rapid=True, provizoriu=True)
    m._ruleaza(audio, "ro", "", None, rapid=False, provizoriu=False)

    assert apeluri[0]["beam_size"] == 1 and apeluri[0]["word_timestamps"] is False
    assert apeluri[0]["vad_filter"] is True  # bucata finală păstrează filtrul de liniște
    assert apeluri[1]["vad_filter"] is False  # fereastra provizorie: fără VAD, ca să nu taie
    assert apeluri[2]["beam_size"] == 5 and apeluri[2]["word_timestamps"] is True


def test_text_provizoriu_se_inlocuieste_la_final_si_pauza_ascunde_provizorii():
    """Provizoriul apare doar cât dictarea e activă; finalul îl înlocuiește."""
    from PySide6.QtWidgets import QApplication
    from dictare_transcriere_romana.ui_qt.ui_editor import Editor
    from dictare_transcriere_romana import stare as stare_modul

    _app = QApplication.instance() or QApplication([])
    stare = stare_modul.Stare()
    ed = Editor(None, stare)

    class DummyApp:
        pass

    dummy = DummyApp()
    dummy.stare = stare
    dummy.configurare = SimpleNamespace(asistent_microfon_vazut=True, blocare_dictare="nimic")
    dummy.editor = ed
    dummy.coada = SimpleNamespace(trimite=lambda f, *a, **k: f(*a, **k))

    pagina = PaginaDictare(None, dummy)
    pagina._activ = True
    pagina._adauga_text_live("Ana are")
    assert ed.text() == "Ana are"  # apare live, provizoriu
    pagina._adauga_text("Ana are mere.")
    pagina._goleste_coada_cuvinte()
    assert ed.text() == "Ana are mere."  # finalul a înlocuit provizoriul

    pagina._activ = False
    pagina._adauga_text_live("rest târziu")
    assert ed.text() == "Ana are mere."  # după oprire nu mai apar provizorii


def test_fraza_de_la_capat_si_idee_noua_in_editor():
    """F6 șterge fraza neterminată; Shift+F6 o șterge și deschide paragraf cu tab."""
    from PySide6.QtWidgets import QApplication
    from dictare_transcriere_romana.ui_qt.ui_editor import Editor
    from dictare_transcriere_romana import stare as stare_modul

    _app = QApplication.instance() or QApplication([])
    ed = Editor(None, stare_modul.Stare())

    ed.set_text("Prima frază e gata. A doua frază")
    assert ed.sterge_ultima_fraza() is True
    assert ed.text() == "Prima frază e gata."

    # Fără frază neterminată (textul se termină cu punct): nimic de șters.
    assert ed.sterge_ultima_fraza() is False

    ed.set_text("Text încheiat.\n\n\t")
    assert ed.idee_noua() is True  # curăță paragraful vechi și deschide altul
    assert ed.text() == "Text încheiat.\n\n\t"

    # Provizoriul live dispare odată cu fraza ștearsă.
    ed.set_text("Fraza veche. ")
    ed.arata_provizoriu("cvint neterminat alambicat")
    assert ed.text() == "Fraza veche. cvint neterminat alambicat"
    ed.sterge_ultima_fraza()
    assert ed.text() == "Fraza veche. "  # spațiul de după punct rămâne (era în textul de bază)
    ed.insereaza("Fraza refăcută corect.")
    assert ed.text() == "Fraza veche. Fraza refăcută corect."
