"""Teste pentru interfața CLI D&TED, fără încărcarea modelului."""

from __future__ import annotations

import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from dictare_transcriere_romana import config, motor
from dictare_transcriere_romana import __main__ as intrare


def test_format_neacceptat_este_respins_inainte_de_incarcarea_modelului():
    with tempfile.TemporaryDirectory() as folder:
        fisier = Path(folder) / "inregistrare.wav"
        fisier.write_bytes(b"audio de test")
        argumente = SimpleNamespace(transcrie=str(fisier), format="csv", limba="ro")
        iesire = io.StringIO()

        with patch.object(config, "incarca") as incarca_setari, patch.object(
            motor, "MotorWhisper"
        ) as porneste_motor, redirect_stdout(iesire):
            cod = intrare._transcrie(argumente)

    assert cod == 2
    assert "Formatul „csv” nu este acceptat" in iesire.getvalue()
    incarca_setari.assert_not_called()
    porneste_motor.assert_not_called()


def test_ajutorul_cli_enumera_formatele_suportate():
    iesire = io.StringIO()
    with redirect_stdout(iesire):
        try:
            intrare._argumente(["--help"])
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("--help trebuia să închidă parserul")

    ajutor = iesire.getvalue().lower()
    for extensie in ("docx", "odt", "txt", "rtf", "html", "htm", "srt", "vtt", "pdf"):
        assert extensie in ajutor
