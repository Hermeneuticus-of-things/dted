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
