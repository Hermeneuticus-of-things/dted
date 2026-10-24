"""Teste pentru alegerea modelului de transcriere (v0.1.2)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dictare_transcriere_romana import cai, config, constante


def _aseaza(radacina: Path, nume: str) -> None:
    folder = radacina / "model" / nume
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "model.bin").write_bytes(b"x")
    (folder / "tokenizer.json").write_bytes(b"{}")


def test_auto_prefera_modelul_romanesc(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        radacina = Path(folder)
        _aseaza(radacina, "large-v3-turbo-ct2")
        _aseaza(radacina, "large-v3-turbo-ro-ct2")
        monkeypatch.setattr(cai, "director_model", lambda: radacina)
        assert cai.fisier_model("auto").name == "large-v3-turbo-ro-ct2"
        # fără nicio preferință dată, la fel
        assert cai.fisier_model(None).name == "large-v3-turbo-ro-ct2"


def test_caderea_pe_modelul_standard_cand_cel_romanesc_lipseste(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        radacina = Path(folder)
        _aseaza(radacina, "large-v3-turbo-ct2")
        monkeypatch.setattr(cai, "director_model", lambda: radacina)
        assert cai.fisier_model("auto").name == "large-v3-turbo-ct2"


def test_preferinta_explicita_este_respectata(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        radacina = Path(folder)
        _aseaza(radacina, "large-v3-turbo-ct2")
        _aseaza(radacina, "large-v3-turbo-ro-ct2")
        monkeypatch.setattr(cai, "director_model", lambda: radacina)
        assert cai.fisier_model("large-v3-turbo-ct2").name == "large-v3-turbo-ct2"


def test_config_si_constante():
    cfg = config.Config()
    assert cfg.model_preferat == "auto"
    assert constante.MODELE_TRANSCRIBERE[constante.WHISPER_NUME_RO].startswith("Îmbunătățit")
    assert "beta" in constante.VERSIUNE_COMPLETA
