"""Teste pentru fereastra „Raportează o problemă” (ui_raport.py)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from PySide6.QtWidgets import QApplication

from dictare_transcriere_romana.ui_qt import ui_raport


def test_căile_personale_sunt_anonimizate():
    text = (
        r"Eroare la C:\Users\Nume\Documente\carte.docx și "
        r"D:\Proiecte\Dictare\motor.py"
    )
    anonim = ui_raport.anonimizeaza(text)
    assert "Nume" not in anonim
    assert "Proiecte" not in anonim
    assert "%UTILIZATOR%" in anonim or "%PROIECT%" in anonim


def test_raportul_conține_descrierea_și_eroarea_dar_nu_căi_complete():
    raport = ui_raport.creeaza_raport(
        "dictam capitolul trei",
        [r"[2026-10-24 12:00:00] EROARE    Ceva la C:\Users\X\Y.py"],
    )
    assert "dictam capitolul trei" in raport
    assert "EROARE" in raport
    assert r"C:\Users\X" not in raport
    assert "Versiune:" in raport


def test_raportul_fără_eroare_spune_asta():
    raport = ui_raport.creeaza_raport("doar o întrebare", [])
    assert "nu conține erori recente" in raport


def test_fereastra_se_construiește_cu_eroarea_pre_completată():
    app = QApplication.instance() or QApplication([])
    fereastra = ui_raport.FereastraRaport(
        None, erori=["[2026-10-24 12:00:00] EROARE    test de probă"]
    )
    detalii = fereastra.edit_detalii.toPlainText()
    assert "test de probă" in detalii
    raport = fereastra._text_raport()
    assert "test de probă" in raport
    assert "Versiune:" in raport
    fereastra.deleteLater()


def test_urlul_de_fallback_este_pregătit():
    url = ui_raport._url_prefill("Titlu probă", "Corp raport")
    assert "issues/new" in url
    assert "Titlu" in url
