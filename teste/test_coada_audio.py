"""Teste pentru coada de fișiere (35/47) și pregătirea sunetului (51/52)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from dictare_transcriere_romana import biblioteca, cai, codecuri, config


def test_config_are_cheile_noi_oprite_implicit():
    cfg = config.Config()
    assert cfg.scurteaza_pauze is False
    assert cfg.pregateste_audio is False
    assert cfg.scurtaturi_globale is False
    assert cfg.asistent_microfon_vazut is False


def test_registrul_de_fișiere_transcrise(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setattr(cai, "director_instalare", lambda: Path(folder))
        audio = Path(folder) / "inregistrare.mp3"
        audio.write_bytes(b"sunet de proba")

        assert biblioteca.a_fost_transcris(audio) is False
        assert biblioteca.noteaza_transcris(audio) is True
        assert biblioteca.a_fost_transcris(audio) is True

        # același fișier, altă dimensiune (înregistrat din nou): e „nou”
        audio.write_bytes(b"sunet de proba mai lung")
        assert biblioteca.a_fost_transcris(audio) is False

        # cerința 47: „uită” îl pune iar la rând
        biblioteca.noteaza_transcris(audio)
        biblioteca.uita_transcris(audio)
        assert biblioteca.a_fost_transcris(audio) is False


def test_normalizeaza_ridică_sunetul_prea_încet():
    incet = np.full(1600, 0.05, dtype=np.float32)
    ridicat = codecuri.normalizeaza(incet)
    assert abs(float(np.max(np.abs(ridicat))) - 0.95) < 0.02

    tare = np.full(1600, 0.995, dtype=np.float32)
    assert codecuri.normalizeaza(tare) is tare  # deja la maxim: neatins

    gol = np.zeros(0, dtype=np.float32)
    assert codecuri.normalizeaza(gol).size == 0


def test_scurtează_pauzele_numai_peste_doua_secunde():
    rate = 16000
    sunet = np.concatenate(
        [
            np.full(rate, 0.3, dtype=np.float32),   # 1 s vorbire
            np.zeros(rate * 4, dtype=np.float32),   # 4 s tăcere (se taie)
            np.full(rate, 0.3, dtype=np.float32),   # 1 s vorbire
            np.zeros(rate, dtype=np.float32),       # 1 s tăcere (rămâne)
            np.full(rate, 0.3, dtype=np.float32),   # 1 s vorbire
        ]
    )
    scurtat = codecuri.scurteaza_pauzele(sunet, rate=rate)
    assert scurtat.size < sunet.size
    durata = scurtat.size / rate
    assert 2.5 < durata < 4.5  # cele 3 secunde de vorbire + pauza scurtă

    # fără tăceri lungi: sunetul rămâne intact
    doar_vorbire = np.full(rate * 2, 0.3, dtype=np.float32)
    assert codecuri.scurteaza_pauzele(doar_vorbire, rate=rate) is doar_vorbire


def test_importa_doar_fisiere_audio_noi_si_arhiveaza_terminate(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        rad = Path(tmp) / "doc"
        sursa = Path(tmp) / "import"
        sursa.mkdir(parents=True)
        monkeypatch.setattr(cai, "director_instalare", lambda: Path(tmp))
        monkeypatch.setattr(cai, "director_iesiri", lambda: rad)

        f1 = sursa / "unu.wav"
        f2 = sursa / "doi.mp3"
        f_txt = sursa / "ignora.txt"
        f1.write_bytes(b"WAV1111")
        f2.write_bytes(b"MP32222")
        f_txt.write_text("nu e audio", encoding="utf-8")

        # f2 e deja marcat ca transcris -> trebuie sărit (cerința 47)
        biblioteca.noteaza_transcris(f2)
        importate, sarite = biblioteca.importa_audio_noi(sursa, rad)
        assert len(importate) == 1
        assert importate[0].name == "unu.wav"
        assert sarite == 1

        # Al doilea import din același folder sare și peste unu.wav (deja în Audio)
        importate2, sarite2 = biblioteca.importa_audio_noi(sursa, rad)
        assert importate2 == []
        assert sarite2 == 2

        # Cerința 41: mută în arhiva „Terminate”
        reusit, mesaj = biblioteca.muta_la_terminate(importate[0], rad)
        assert reusit and not mesaj
        assert not importate[0].exists()
        terminate = biblioteca.listeaza("terminate", rad)
        assert len(terminate) == 1 and terminate[0].nume == "unu.wav"


def test_recuperare_audio_pe_bucati(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(cai, "director_recuperare", lambda: Path(tmp))
        assert biblioteca.citeste_recuperare_audio() is None

        esantioane = np.linspace(-0.5, 0.5, 8000, dtype=np.float32)
        cale = biblioteca.scrie_recuperare_audio(esantioane, 16000)
        assert cale is not None and cale.exists()
        assert biblioteca.citeste_recuperare_audio() == cale

        biblioteca.sterge_recuperare()
        assert biblioteca.citeste_recuperare_audio() is None


def test_procesare_audio_doar_la_ascultare():
    original = np.full(1600, 0.1, dtype=np.float32) + 0.05
    copie_inainte = original.copy()
    filtrat = codecuri.pregateste_pentru_ascultare(original, 16000)
    # Tabloul original (pentru motor) rămâne neatins (cerința 39)
    assert np.array_equal(original, copie_inainte)
    assert filtrat.shape == original.shape
    assert abs(float(np.mean(filtrat))) < 0.01


def test_fisier_proba_audio_exista():
    proba = cai.fisier_proba_audio()
    assert proba is not None and proba.exists() and proba.name == "_test_audio_ro.mp3"
