"""Teste rapide, fără rețea, pentru părțile care nu depind de model.

Rulare:
    python -m unittest discover -s teste -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from transcriere_locala import documente, resurse, wordcraft  # noqa: E402
from transcriere_locala.wordcraft import citeste_sume  # noqa: E402

TEXT_PROBA = (
    "Primul paragraf cu diacritice: ă â î ș ț, Ă Â Î Ș Ț.\n"
    "\n"
    'Al doilea paragraf, cu ghilimele "drepte" & semne < >.\n'
    "Linia trei."
)


class TestDocumente(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp(prefix="transcriere_test_"))

    def test_docx_este_zip_valid(self) -> None:
        cale = documente.scrie_docx(TEXT_PROBA, self.folder / "test.docx", titlu="Titlu")
        self.assertTrue(cale.exists())
        with zipfile.ZipFile(cale) as arhiva:
            self.assertIsNone(arhiva.testzip())
            nume = arhiva.namelist()
            self.assertIn("word/document.xml", nume)
            self.assertIn("[Content_Types].xml", nume)
            continut = arhiva.read("word/document.xml").decode("utf-8")
        self.assertIn("Primul paragraf", continut)
        self.assertIn("ș", continut)
        # Semnele speciale trebuie escapare, nu brute.
        self.assertIn("&amp;", continut)
        self.assertIn("&lt;", continut)

    def test_odt_este_zip_valid(self) -> None:
        cale = documente.scrie_odt(TEXT_PROBA, self.folder / "test.odt", titlu="Titlu")
        with zipfile.ZipFile(cale) as arhiva:
            self.assertIsNone(arhiva.testzip())
            self.assertEqual(arhiva.namelist()[0], "mimetype")
            info = arhiva.getinfo("mimetype")
            self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(
                arhiva.read("mimetype").decode("utf-8"),
                "application/vnd.oasis.opendocument.text",
            )
            continut = arhiva.read("content.xml").decode("utf-8")
        self.assertIn("Primul paragraf", continut)

    def test_text_gol_nu_crapa(self) -> None:
        cale = documente.scrie_docx("", self.folder / "gol.docx")
        self.assertTrue(cale.exists())
        cale2 = documente.scrie_odt("   \n\n  ", self.folder / "gol.odt")
        self.assertTrue(cale2.exists())

    def test_nume_fisier_sigur(self) -> None:
        nume = documente.nume_sigur('a<b>c:d/e\\f|g?h*i"j')
        for interzis in '<>:"/\\|?*':
            self.assertNotIn(interzis, nume)
        self.assertTrue(nume)

    def test_titlu_din_text(self) -> None:
        titlu = documente.titlu_din_text("Aceasta este prima propoziție. A doua.")
        self.assertEqual(titlu, "Aceasta este prima propoziție.")
        self.assertEqual(documente.titlu_din_text("   "), "")


class TestSumeWordCraft(unittest.TestCase):
    def test_citeste_sume(self) -> None:
        text = (
            "7ca27a11f7122322a2525af4e11308abb70b1cdb2625b5ab95afadcac12d79bb  "
            "wordcraft-0.8.0-windows-x64.msi\n"
            "# comentariu\n"
            "linie invalidă\n"
        )
        sume = citeste_sume(text)
        self.assertIn("wordcraft-0.8.0-windows-x64.msi", sume)
        self.assertEqual(len(sume), 1)

    def test_alege_fisier_pentru_fiecare_arhitectura(self) -> None:
        sume = {
            "wordcraft-0.8.0-windows-x64-portable.zip": "a" * 64,
            "wordcraft-0.8.0-windows-arm64-portable.zip": "b" * 64,
            "wordcraft-0.8.0-windows-x86-portable.zip": "c" * 64,
        }
        for arhitectura in ("AMD64", "ARM64", "x86"):
            nume, portabil = wordcraft.alege_fisier(arhitectura, sume)
            self.assertTrue(portabil)
            self.assertIn(arhitectura.lower().replace("amd64", "x64"), nume)

    def test_arhitectura_necunoscuta_explica(self) -> None:
        with self.assertRaises(wordcraft.EroareWordCraft):
            wordcraft.alege_fisier("MIPS", {})


class TestResurse(unittest.TestCase):
    def test_raportul_are_toate_cerintele(self) -> None:
        raport = resurse.verifica()
        chei = {c.cheie for c in raport.cerinte}
        self.assertEqual(chei, {"os", "cpu", "ram", "disc", "gpu", "microfon"})

    def test_cerintele_optionale_nu_blocheaza(self) -> None:
        raport = resurse.verifica()
        for cerinta in raport.cerinte:
            if not cerinta.obligatorie:
                self.assertNotIn(cerinta, raport.blocante)

    def test_text_consola_are_diacritice(self) -> None:
        raport = resurse.verifica()
        text = resurse.text_pentru_consola(raport)
        self.assertIn("Cerințe minime", text)

    def test_estimare_viteza(self) -> None:
        raport = resurse.verifica()
        self.assertIn("minute", resurse.estimare_viteza(raport))


if __name__ == "__main__":
    unittest.main(verbosity=2)
