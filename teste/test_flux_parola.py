"""Teste pentru fluxul parolă + criptare documente (N-5/N-6): seiful pe disc,
cheia maestră și criptarea unui document cu cheia din seif.

Se sar pe non-Windows (criptarea folosește CNG / bcrypt.dll din Windows).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform != "win32":
    import unittest

    raise unittest.SkipTest("criptare folosește CNG (bcrypt.dll), disponibil doar pe Windows")

from dictare_transcriere_romana import cai, config, constante, criptare, parola


def test_parola_implicita_este_dictare():
    assert constante.PAROLA_IMPLICITA == "Dictare"


def test_seiful_se_salveaza_si_incarca_de_pe_disc(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setattr(cai, "director_instalare", lambda: Path(folder))
        assert not parola.seif_definit()

        seif, _recuperare, cheie = parola.defineste(constante.PAROLA_IMPLICITA)
        assert parola.salveaza_seif(seif)
        assert parola.seif_definit()

        incarcat = parola.incarca_seif()
        assert incarcat is not None
        assert parola.deschide_cu_parola(incarcat, "Dictare") == cheie

        try:
            parola.deschide_cu_parola(incarcat, "alta parola")
        except parola.ParolaGresita:
            pass
        else:
            raise AssertionError("parola greșită trebuia respinsă")

        assert parola.sterge_seif()
        assert not parola.seif_definit()
        assert parola.incarca_seif() is None


def test_document_criptat_cu_cheia_din_seif_se_citeste_inapoi(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setattr(cai, "director_instalare", lambda: Path(folder))
        seif, _recuperare, cheie = parola.defineste("Dictare")

        with tempfile.TemporaryDirectory() as folder_doc:
            document = Path(folder_doc) / "test.txt"
            document.write_text("Text de probă cu diacritice:ă â î ș ț.", encoding="utf-8")
            assert not criptare.este_criptat(document)

            criptare.cripteaza_fisier(cheie, document, document)
            assert criptare.este_criptat(document)
            assert document.read_bytes() != "Text de probă".encode("utf-8")

            decriptat = Path(folder_doc) / "decriptat.txt"
            criptare.decripteaza_fisier(cheie, document, decriptat)
            assert decriptat.read_text(encoding="utf-8") == "Text de probă cu diacritice:ă â î ș ț."


def test_schimbarea_parolei_pastreaza_cheia_si_documentele(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setattr(cai, "director_instalare", lambda: Path(folder))
        seif, _recuperare, cheie = parola.defineste("Dictare")

        with tempfile.TemporaryDirectory() as folder_doc:
            document = Path(folder_doc) / "test.txt"
            document.write_text("secret", encoding="utf-8")
            criptare.cripteaza_fisier(cheie, document, document)

            seif_nou = parola.schimba_parola(seif, "Dictare", "parola nouă")
            assert parola.deschide_cu_parola(seif_nou, "parola nouă") == cheie

            decriptat = Path(folder_doc) / "decriptat.txt"
            criptare.decripteaza_fisier(cheie, document, decriptat)
            assert decriptat.read_text(encoding="utf-8") == "secret"


def test_config_are_cheile_noi():
    cfg = config.Config()
    assert cfg.cripteaza_documente is False
    assert cfg.blocare_dictare == "nimic"
