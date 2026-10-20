"""Teste pentru logica de verificare a resurselor, fără a depinde de hardware.

Se folosesc rapoarte construite manual, ca testele să treacă pe orice
calculator (inclusiv pe cele fără placă video sau cu RAM puțină).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from transcriere_locala.resurse import Cerinta, Raport  # noqa: E402


def _raport(stare_gpu: str = "optioanala", ram_ok: bool = True) -> Raport:
    raport = Raport()
    raport.cerinte = [
        Cerinta("os", "Sistem de operare", "Windows 10/11", "Windows 11", "ok"),
        Cerinta("cpu", "Procesor", "x64", "Intel", "ok"),
        Cerinta(
            "ram",
            "Memorie RAM",
            "8 GB",
            "16 GB" if ram_ok else "4 GB",
            "ok" if ram_ok else "lipsa",
        ),
        Cerinta("disc", "Spațiu liber", "8 GB", "100 GB", "ok"),
        Cerinta(
            "gpu",
            "Placă video (opțională)",
            "NVIDIA 6 GB",
            "fără",
            stare_gpu,  # type: ignore[arg-type]
            obligatorie=False,
        ),
    ]
    raport.are_gpu = stare_gpu == "ok"
    return raport


class TestVerdict(unittest.TestCase):
    def test_totul_bine(self) -> None:
        raport = _raport("ok")
        self.assertTrue(raport.poate_instala)
        self.assertFalse(raport.doar_gpu_lipsa)
        self.assertEqual(raport.blocante, [])

    def test_fara_gpu_nu_blocheaza(self) -> None:
        raport = _raport("optioanala")
        self.assertTrue(raport.poate_instala)
        self.assertTrue(raport.doar_gpu_lipsa)
        self.assertIn("fără accelerare video", raport.rezumat())

    def test_ram_insuficienta_blocheaza(self) -> None:
        raport = _raport("ok", ram_ok=False)
        self.assertFalse(raport.poate_instala)
        self.assertEqual(len(raport.blocante), 1)
        self.assertIn("obligatorii", raport.rezumat())

    def test_cerinta_optionala_nu_blocheaza(self) -> None:
        raport = _raport("optioanala", ram_ok=False)
        raport.cerinte[-1].stare = "lipsa"  # chiar și marcată lipsă, e opțională
        chei = [c.cheie for c in raport.blocante]
        self.assertEqual(chei, ["ram"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
