"""Teste pentru paragrafele comandate vocal și viteza de redare (v0.6.0)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from dictare_transcriere_romana import config, redare, text_ro


def test_paragraf_nou_face_rând_gol():
    text = text_ro.marcaje_paragraf("Sfârșit de frază. Paragraf nou. Apoi continuă.")
    assert text == "Sfârșit de frază\n\nApoi continuă."


def test_rând_nou_face_trecerea_pe_rând():
    text = text_ro.marcaje_paragraf("prima linie. Rând nou a doua linie.")
    assert text == "prima linie\na doua linie."


def test_fara_comenzi_textul_rămâne_intact():
    assert text_ro.marcaje_paragraf("fără comenzi, normal.") == "fără comenzi, normal."
    assert text_ro.marcaje_paragraf("") == ""
    # cuvintele care conțin „paragraf” nu se ating
    assert "paragrafului" in text_ro.marcaje_paragraf("la sfârșitul paragrafului.")


def test_viteza_de_redare_se_aplică():
    fake = _Fake()
    player = redare.Redare(porneste_sunet=fake.porneste, opreste_sunet=fake.opreste)
    player.incarca(np.zeros(16000 * 4, dtype=np.float32), 16000)  # 4 s

    assert player.viteza() == 1.0
    player.seteaza_viteza("rapid")
    assert player.viteza() == redare.VITEZE["rapid"]
    player.porneste(0.0)
    # la viteza 1,4, bucata redată e mai scurtă: 4 s → ~2,9 s
    lungime_rapid = fake.piese[-1][0]
    player.pauza()
    player.seteaza_viteza("normal")
    player.porneste(0.0)
    lungime_normal = fake.piese[-1][0]
    assert lungime_rapid < lungime_normal * 0.8
    assert abs(lungime_normal - 64000) < 100  # 4 s × 16 kHz neatins la viteza 1


def test_viteza_influențează_poziția():
    import time as _t

    fake = _Fake()
    player = redare.Redare(porneste_sunet=fake.porneste, opreste_sunet=fake.opreste)
    player.incarca(np.zeros(16000 * 4, dtype=np.float32), 16000)
    player.seteaza_viteza("rapid")
    player.porneste(0.0)
    _t.sleep(0.4)
    pozitie_rapid = player.pozitie()
    player.pauza()
    assert pozitie_rapid > 0.4  # avansează mai repede decât ceasul real


def test_config_are_activarea_vocala():
    cfg = config.Config()
    assert cfg.activare_vocala is False
    assert cfg.prag_activare_db == -35


class _Fake:
    def __init__(self):
        self.piese = []
        self.oprit = 0

    def porneste(self, pcm, rata):
        self.piese.append((len(pcm), rata))

    def opreste(self):
        self.oprit += 1
