"""Teste pentru verificările pachetelor instalate de D&TED."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from dictare_transcriere_romana import constante, instalare


def test_pyav_este_fixat_la_o_versiune_compatibila():
    assert constante.PACHET_PYAV == "av==17.1.0"
    assert constante.PACHET_PYAV in constante.PACHETE


def test_verificarea_versiunii_pyav_accepta_doar_versiuni_sub_18():
    assert instalare.pyav_compatibil("17.1.0")
    assert not instalare.pyav_compatibil("18.0.0")
    assert not instalare.pyav_compatibil("19.0.1")
    assert not instalare.pyav_compatibil("versiune-necunoscuta")


def test_verificarea_mediului_respinge_pyav_18_sau_mai_nou():
    apel = {}

    def ruleaza(comanda, **optiuni):
        apel["comanda"] = comanda
        return SimpleNamespace(returncode=1)

    with patch.object(instalare.subprocess, "run", side_effect=ruleaza):
        assert not instalare._are_biblioteci(Path("python.exe"))

    verificare = apel["comanda"][2]
    assert ", av;" in verificare
    assert "av.__version__" in verificare
    assert ">= 18" in verificare
