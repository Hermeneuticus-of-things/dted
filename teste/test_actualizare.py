"""Teste pentru actualizare.py — logică pură (fără rețea)."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dictare_transcriere_romana import actualizare as act
from dictare_transcriere_romana import cai


def _cu_director_temp(functie):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        original = cai.director_instalare
        cai.director_instalare = lambda: tmp
        try:
            functie(tmp)
        finally:
            cai.director_instalare = original


def test_ce_s_a_schimbat(tmp_dummy):
    def corp(tmp):
        act.scrie_versiuni({"program": {"versiune": "1.0"}, "model": {"versiune": "v1"}})
        manifest = {
            "program": {"versiune": "1.1", "dimensiune": 100},
            "model": {"versiune": "v1"},          # neschimbat
            "mediu": {"versiune": "3.13", "dimensiune": 500},  # nou
        }
        sch = {s.nume: s for s in act.ce_s_a_schimbat(manifest)}
        assert set(sch) == {"program", "mediu"}
        assert sch["program"].veche == "1.0" and sch["program"].noua == "1.1"
        assert sch["mediu"].veche == "—" and sch["mediu"].dimensiune == 500
    _cu_director_temp(corp)
    print("ce_s_a_schimbat OK")


def test_backup_aplicare_revenire(tmp_dummy):
    def corp(tmp):
        comp = tmp / "program"
        comp.mkdir(parents=True)
        (comp / "motor.py").write_text("vechi", encoding="utf-8")

        # backup
        backup = act.backup_componenta("program", "1.0")
        assert backup and (backup / "motor.py").read_text(encoding="utf-8") == "vechi"

        # aplica (pachet descărcat)
        pachet = tmp / "pachet_nou"
        pachet.mkdir()
        (pachet / "motor.py").write_text("nou", encoding="utf-8")
        assert act.aplica("program", "1.1", pachet)
        assert (comp / "motor.py").read_text(encoding="utf-8") == "nou"
        assert act.versiuni_instalate()["program"]["versiune"] == "1.1"

        # revine
        assert act.revine("program", "1.0")
        assert (comp / "motor.py").read_text(encoding="utf-8") == "vechi"
        assert act.versiuni_instalate()["program"]["versiune"] == "1.0"
    _cu_director_temp(corp)
    print("backup + aplica + revine OK")


def test_sha256(tmp_dummy):
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "x.bin"
        f.write_bytes(b"abc\n")
        assert act.sha256_al_fisierului(f) == act.sha256_al_fisierului(f)
        assert len(act.sha256_al_fisierului(f)) == 64
    print("sha256 OK")


if __name__ == "__main__":
    test_ce_s_a_schimbat(None)
    test_backup_aplicare_revenire(None)
    test_sha256(None)
    print("TOATE OK")