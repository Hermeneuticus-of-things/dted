"""Regresii pentru fluxul de dictare pe bucăți."""

from __future__ import annotations

import os
import sys
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
            self.config = SimpleNamespace(limba="ro", termeni="")
            self.motor = MotorTest()
            self.aplicatie = SimpleNamespace(
                _motor=self.motor,
                coada=CoadaTest(),
            )
            self.fragmente = []
            self.finalizata = False

        def _adauga_text(self, fragment):
            self.fragmente.append(fragment)

        def _opreste(self):
            self.finalizata = True

    dictare = DictareTest()
    PaginaDictare._bucla(dictare)

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
