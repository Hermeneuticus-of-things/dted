"""Teste pentru descărcare și verificarea sumelor SHA-256 (fără rețea)."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from transcriere_locala.descarcare import SumaGresita, sha256_fisier, text_progres  # noqa: E402


class TestSume(unittest.TestCase):
    def test_suma_cunoscuta(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="suma_"))
        fisier = folder / "probă.txt"
        fisier.write_bytes(b"salut")
        asteptat = hashlib.sha256(b"salut").hexdigest()
        self.assertEqual(sha256_fisier(fisier), asteptat)

    def test_progres_primeste_total(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="suma_"))
        fisier = folder / "mare.bin"
        fisier.write_bytes(b"x" * 3_000_000)
        apeluri: list[tuple[int, int]] = []
        sha256_fisier(fisier, lambda citit, total: apeluri.append((citit, total)))
        self.assertTrue(apeluri)
        self.assertEqual(apeluri[-1][0], apeluri[-1][1])

    def test_mesaj_suma_gresita_explica(self) -> None:
        exc = SumaGresita("model.pt", "a" * 64, "b" * 64)
        text = str(exc)
        self.assertIn("nu este cel oficial", text)
        self.assertIn("oprită", text)

    def test_text_progres_prietenos(self) -> None:
        mesaj = text_progres(50 * 1024**2, 100 * 1024**2, "Descarc modelul")
        self.assertIn("50%", mesaj)
        self.assertIn("Descarc modelul", mesaj)


if __name__ == "__main__":
    unittest.main(verbosity=2)
