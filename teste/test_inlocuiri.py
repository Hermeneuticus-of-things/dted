"""Teste pentru dicționarul de corecturi învățate (inlocuiri.py)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dictare_transcriere_romana import cai, inlocuiri


def test_adauga_accepta_doar_cuvinte_singure(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setattr(cai, "director_instalare", lambda: Path(folder))
        assert inlocuiri.adauga("dragostae", "dragoste")
        assert inlocuiri.adauga("Anaf", "ANAF") is False          # doar majusculă
        assert inlocuiri.adauga("el merge", "el venea") is False  # fraze, nu cuvinte
        assert inlocuiri.adauga("ab", "abc") is False             # prea scurt
        perechi = inlocuiri.incarca()
        assert perechi == {"dragostae": "dragoste"}


def test_aplica_pastreaza_majuscula_si_marginea_cuvantului(monkeypatch):
    text = "Dragostae e un cuvânt greșit, dar dragostaei nu se atinge."
    aplicat = inlocuiri.aplica(text, {"dragostae": "dragoste"})
    assert aplicat.startswith("Dragoste e")
    assert "dragostaei" in aplicat  # parte din alt cuvânt: neatinsă
    assert "dragostae " not in aplicat


def test_diferentele_invata_doar_inlocuirile_de_un_cuvant():
    perechi = inlocuiri.diferente_cuvinte(
        "El merge la dragostae acuma", "El merge la dragoste acum"
    )
    assert ("dragostae", "dragoste") in perechi
    assert ("acuma", "acum") in perechi
    # adăugare (dictare care continuă) și ștergere: nimic de învățat
    assert inlocuiri.diferente_cuvinte("a b c", "a b c d") == []
    assert inlocuiri.diferente_cuvinte("a b c d", "a b c") == []
    # înlocuire masivă: ignorată
    assert inlocuiri.diferente_cuvinte("a b c d e", "x y z") == []


def test_importul_din_text_si_fisier(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setattr(cai, "director_instalare", lambda: Path(folder))
        puse, respinse = inlocuiri.importa(
            "dragostae -> dragoste\nacuma, acum\n# comentariu\nbun = rău\nFraza întreagă refuzată\n"
        )
        assert (puse, respinse) == (3, 1)
        assert inlocuiri.incarca() == {
            "dragostae": "dragoste",
            "acuma": "acum",
            "bun": "rău",
        }

        fisier = Path(folder) / "dictionar.json"
        fisier.write_text('{"vreo": "foarte"}', encoding="utf-8")
        puse, _ = inlocuiri.importa_din_fisier(fisier)
        assert puse == 1
        assert inlocuiri.incarca()["vreo"] == "foarte"

        text_export = inlocuiri.exporta_text(inlocuiri.incarca())
        assert "dragostae -> dragoste" in text_export


def test_curățarea_repetitiilor_din_bâlbâiala():
    from dictare_transcriere_romana import text_ro

    assert text_ro.curata_repetari("Și, nu, nu, nu, nu, nu.") == "Și, nu."
    assert text_ro.curata_repetari("foarte, foarte bun") == "foarte, foarte bun"
    assert text_ro.curata_repetari("capra capra capra piatra") == "capra piatra"
    assert text_ro.curata_repetari("") == ""
