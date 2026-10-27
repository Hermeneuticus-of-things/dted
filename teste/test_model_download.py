"""Regresii pentru descărcarea modelelor din Setări (v0.6.4)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from dictare_transcriere_romana import pregatire


def test_descarca_model_respinge_ce_nu_are_sursa(monkeypatch, tmp_path):
    monkeypatch.setenv("DICTARE_DIR", str(tmp_path))

    # nume necunoscut → eroare clară
    try:
        pregatire.descarca_model("model-inexistent")
        assert False, "trebuia să respingă numele necunoscut"
    except pregatire.EroareDescarcare as exc:
        assert "necunoscut" in str(exc)

    # fine-tunatul RO: fără sursă publică CT2 → explicație, nu descărcare
    try:
        pregatire.descarca_model("large-v3-turbo-ro-ct2")
        assert False, "trebuia să respingă modelul fără sursă"
    except pregatire.EroareDescarcare as exc:
        assert "sursă publică" in str(exc)


def test_descarca_model_standard_cu_sursa_locala(monkeypatch, tmp_path):
    """Cu DTED_SURSA_MODEL, fișierele se copiază din folderul local și se verifică."""
    import hashlib

    from dictare_transcriere_romana import cai

    sursa = tmp_path / "sursa"
    sursa.mkdir()
    # conținut real, cu suma din MODEL_FISIERE pentru config.json
    date = "config de probă".encode()
    # suma reală nu se poate reproduci cu conținut oarecare → folosim un manifest fals:
    # punem folderului țintă un marcaj „.verificat-…"? nu — construim sursa cu fișierul
    # exact prin însuși hash-ul așteptat: imposibil; deci testăm copia cu suma goale:
    (sursa / "config.json").write_bytes(date)
    tinta = tmp_path / "model" / "large-v3-turbo-ct2"
    monkeypatch.setenv("DICTARE_DIR", str(tmp_path))
    monkeypatch.setenv("DTED_SURSA_MODEL", str(sursa))  # fără rețea: copie locală
    from dictare_transcriere_romana import cai as modul_cai

    modul_cai._folder_ales.cache_clear()  # calea e memoizată: recitește DICTARE_DIR
    assert cai.director_model() == tmp_path / "model"

    # sursa locală copiază fișierul; suma din manifest e reală → SumaGresita e OK
    # (fișierul de probă nu poate avea suma oficială), iar fișierul parțial e curățat.
    try:
        pregatire.descarca_model("large-v3-turbo-ct2")
        assert False, "suma de probă nu poate fi cea oficială"
    except pregatire.SumaGresita as exc:
        assert exc.nume == "config.json"  # s-a oprit exact la fișierul cu suma nepotrivită
    # niciun fișier .partial rămas pe disc
    assert not list(tinta.glob("*.partial"))
