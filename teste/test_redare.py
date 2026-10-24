"""Teste pentru redarea în editor (32/34/35): semne, pauză, poziție."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dictare_transcriere_romana import redare


def test_marca_în_secunde():
    assert redare.secunde_din_marca("[01:23]") == 83
    assert redare.secunde_din_marca("00:00") == 0
    assert redare.secunde_din_marca("[1:02:03]") == 3723
    assert redare.secunde_din_marca("abc") is None
    assert redare.marca_din_secunde(83) == "01:23"


def test_semnul_de_lângă_cursor():
    text = "Început [00:10] mijloc [01:30] sfârșit"
    # cursor imediat după primul semn → primul semn
    assert redare.semn_la_cursor(text, text.index("]") + 1) == 10
    # cursor la final → ultimul semn
    assert redare.semn_la_cursor(text, len(text)) == 90
    # cursor înainte de orice semn → nimic (redare de la început)
    assert redare.semn_la_cursor(text, 3) is None


class _Fake:
    """Sunet fals: reține ce i s-a cerut să redea."""

    def __init__(self):
        self.piese = []
        self.oprit = 0

    def porneste(self, pcm, rata):
        self.piese.append((len(pcm), rata))

    def opreste(self):
        self.oprit += 1


def test_redarea_cu_pauză_și_poziție():
    import numpy as np

    fake = _Fake()
    player = redare.Redare(porneste_sunet=fake.porneste, opreste_sunet=fake.opreste)
    assert not player.are()
    assert not player.porneste()

    sunet = np.zeros(16000 * 4, dtype=np.float32)  # 4 secunde
    player.incarca(sunet, 16000)
    assert player.are() and abs(player.durata() - 4.0) < 0.01

    assert player.porneste(2.0)          # de la 2 s
    assert fake.piese == [(32000, 16000)]
    assert player.ruleaza()
    assert 2.0 <= player.pozitie() < 2.5

    player.pauza()                        # ține poziția
    assert not player.ruleaza()
    assert 2.0 <= player.pozitie() < 2.6
    assert fake.oprit >= 1                # incarca() oprește și o redare veche

    assert player.porneste()              # continuă de unde a rămas
    assert fake.piese[-1][0] >= 16000     # restul de ~2 s
    player.opreste()
    assert player.pozitie() == 0.0


def test_la_capăt_se_oprește_singur():
    import numpy as np
    import time as _t

    fake = _Fake()
    player = redare.Redare(porneste_sunet=fake.porneste, opreste_sunet=fake.opreste)
    player.incarca(np.zeros(16000, dtype=np.float32), 16000)  # 1 s
    player.porneste(0.9)                 # (pornirea se clampează la 0,2 s de final)
    _t.sleep(0.35)
    assert player.la_capat()
