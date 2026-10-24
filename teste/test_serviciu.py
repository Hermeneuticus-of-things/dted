"""Modul serviciu (D&TED folosit de Scribner): protocolul JSON pe linii, cu motor și microfon falși.

Rulare:
    python -m unittest teste.test_serviciu -v
"""

from __future__ import annotations

import io
import json
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

RADACINA = Path(__file__).resolve().parent.parent
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from dictare_transcriere_romana import serviciu  # noqa: E402


class MotorFals:
    incarcat = True
    dispozitiv = "cpu"

    def __init__(self, eroare: Exception | None = None, intarziere: float = 0.0):
        self.eroare = eroare
        self.intarziere = intarziere
        self.anulat = threading.Event()

    def anuleaza(self):
        self.anulat.set()

    def transcrie(self, sursa, limba="ro", termeni="", progres=None, faza=None):
        if faza:
            faza("Transcriu…")
        if self.eroare:
            raise self.eroare
        limita = time.time() + self.intarziere
        while time.time() < limita:
            if self.anulat.is_set():
                raise type("Anulat", (Exception,), {})()
            time.sleep(0.01)
        if progres:
            progres(0.5)
        if isinstance(sursa, str):
            return SimpleNamespace(text=f"text din {sursa}", segmente=[SimpleNamespace(start=0.0, end=1.5, text=f"text din {sursa}")], secunde_audio=1.5, dispozitiv="cpu")
        return SimpleNamespace(text=f"bucată {len(sursa)}", segmente=[], secunde_audio=len(sursa) / 16000, dispozitiv="cpu")


class MicrofonFals:
    """Dă câte o secundă de „sunet” (o listă) la fiecare preia()."""

    def __init__(self, eroare_la_pornire=False):
        self.eroare_la_pornire = eroare_la_pornire
        self.nivel = 0.3
        self.pornit = False
        self.anulat = False

    def porneste(self):
        if self.eroare_la_pornire:
            raise RuntimeError("Nu găsesc microfonul.")
        self.pornit = True

    def scurgere(self):
        return 1.0

    def preia(self):
        return [0.0] * 16000

    def opreste(self):
        return SimpleNamespace(pcm=[0.0] * 12000)

    def anuleaza(self):
        self.anulat = True


def porneste(**optiuni):
    mesaje: list[dict] = []
    s = serviciu.Serviciu(mesaje.append, secunde_bucata=0.5, **optiuni)
    return s, mesaje


def asteapta(mesaje, ev, secunde=5.0):
    limita = time.time() + secunde
    while time.time() < limita:
        gasite = [m for m in mesaje if m.get("ev") == ev]
        if gasite:
            return gasite
        time.sleep(0.02)
    raise AssertionError(f"lipsește {ev}: {mesaje}")


class TestServiciu(unittest.TestCase):
    def test_stare(self):
        s, mesaje = porneste(motor_fabrica=MotorFals)
        s.executa({"cmd": "stare"})
        self.assertEqual(mesaje[0]["ev"], "stare")
        self.assertEqual(mesaje[0]["protocol"], serviciu.PROTOCOL)
        self.assertFalse(mesaje[0]["model_incarcat"])

    def test_transcrie_fisier(self):
        s, mesaje = porneste(motor_fabrica=MotorFals)
        s.executa({"cmd": "transcrie", "id": "t1", "cale": "interviu.mp3"})
        rez = asteapta(mesaje, "rezultat")[0]
        self.assertEqual(rez["id"], "t1")
        self.assertEqual(rez["text"], "text din interviu.mp3")
        self.assertEqual(rez["segmente"], [{"start": 0.0, "end": 1.5, "text": "text din interviu.mp3"}])
        self.assertTrue(any(m["ev"] == "progres" for m in mesaje))
        self.assertTrue(any(m["ev"] == "faza" for m in mesaje))

    def test_transcriere_fara_fisier_si_cu_eroare(self):
        s, mesaje = porneste(motor_fabrica=lambda: MotorFals(eroare=RuntimeError("Fișierul nu a putut fi citit.")))
        s.executa({"cmd": "transcrie", "id": "a"})
        s.executa({"cmd": "transcrie", "id": "b", "cale": "x.wav"})
        erori = asteapta(mesaje, "eroare")
        s.asteapta(5)
        erori = [m for m in mesaje if m["ev"] == "eroare"]
        self.assertEqual({e["id"] for e in erori}, {"a", "b"})
        self.assertIn("nu a putut fi citit", [e for e in erori if e["id"] == "b"][0]["mesaj"])

    def test_anulare_transcriere(self):
        motor = MotorFals(intarziere=3.0)
        s, mesaje = porneste(motor_fabrica=lambda: motor)
        s.executa({"cmd": "transcrie", "id": "t", "cale": "lung.mp3"})
        time.sleep(0.2)
        s.executa({"cmd": "anuleaza", "id": "t"})
        asteapta(mesaje, "anulat")
        self.assertFalse(any(m["ev"] == "rezultat" for m in mesaje))

    def test_dictare_fragmente_si_oprire(self):
        microfon = MicrofonFals()
        s, mesaje = porneste(motor_fabrica=MotorFals, microfon_fabrica=lambda: microfon)
        s.executa({"cmd": "dictare_start", "id": "d"})
        asteapta(mesaje, "fragment")
        s.executa({"cmd": "dictare_stop", "id": "d"})
        final = asteapta(mesaje, "dictare_oprita")[0]
        fragmente = [m["text"] for m in mesaje if m["ev"] == "fragment"]
        self.assertEqual(fragmente[-1], "bucată 12000")  # ultimul sunet, de la oprire
        self.assertEqual(final["text"], " ".join(fragmente))
        self.assertEqual(mesaje[0]["ev"], "dictare_pornita")

    def test_dictare_a_doua_oara_si_anulare(self):
        microfon = MicrofonFals()
        s, mesaje = porneste(motor_fabrica=MotorFals, microfon_fabrica=lambda: microfon)
        s.executa({"cmd": "dictare_start", "id": "d"})
        s.executa({"cmd": "dictare_start", "id": "e"})
        self.assertEqual([m for m in mesaje if m["ev"] == "eroare"][0]["id"], "e")
        s.executa({"cmd": "anuleaza", "id": "d"})
        asteapta(mesaje, "anulat")
        self.assertTrue(microfon.anulat)
        self.assertFalse(any(m["ev"] == "dictare_oprita" for m in mesaje))
        # după anulare se poate porni din nou
        s.executa({"cmd": "dictare_start", "id": "f"})
        self.assertEqual([m for m in mesaje if m["ev"] == "dictare_pornita"][-1]["id"], "f")
        s.executa({"cmd": "dictare_stop", "id": "f"})
        s.asteapta(5)

    def test_repornire_imediata_dupa_stop(self):
        s, mesaje = porneste(motor_fabrica=MotorFals, microfon_fabrica=MicrofonFals)
        s.executa({"cmd": "dictare_start", "id": "a"})
        s.executa({"cmd": "dictare_stop", "id": "a"})
        s.executa({"cmd": "dictare_start", "id": "b"})
        self.assertFalse(any(m["ev"] == "eroare" for m in mesaje))
        s.executa({"cmd": "dictare_stop", "id": "b"})
        s.asteapta(5)
        self.assertEqual({m["id"] for m in mesaje if m["ev"] == "dictare_oprita"}, {"a", "b"})

    def test_anularea_unei_cereri_in_asteptare_nu_opreste_cererea_in_curs(self):
        motor = MotorFals(intarziere=0.6)
        s, mesaje = porneste(motor_fabrica=lambda: motor)
        s.executa({"cmd": "transcrie", "id": "a", "cale": "a.mp3"})
        time.sleep(0.1)
        s.executa({"cmd": "transcrie", "id": "b", "cale": "b.mp3"})
        s.executa({"cmd": "anuleaza", "id": "b"})
        s.asteapta(5)
        self.assertEqual([m["id"] for m in mesaje if m["ev"] == "rezultat"], ["a"])
        self.assertEqual([m["id"] for m in mesaje if m["ev"] == "anulat"], ["b"])

    def test_un_singur_motor_la_cereri_simultane(self):
        create = []

        def fabrica():
            time.sleep(0.05)
            create.append(1)
            return MotorFals()

        s, mesaje = porneste(motor_fabrica=fabrica)
        for i in range(4):
            s.executa({"cmd": "transcrie", "id": i, "cale": f"{i}.mp3"})
        s.asteapta(5)
        self.assertEqual(len(create), 1)

    def test_fara_microfon(self):
        s, mesaje = porneste(motor_fabrica=MotorFals, microfon_fabrica=lambda: MicrofonFals(eroare_la_pornire=True))
        s.executa({"cmd": "dictare_start", "id": "d"})
        self.assertEqual(mesaje[0]["ev"], "eroare")
        self.assertIn("microfon", mesaje[0]["mesaj"])
        self.assertTrue(mesaje[0]["ce_fac"])

    def test_bucla_json(self):
        intrare = io.StringIO('{"cmd":"stare"}\nnu e json\n{"cmd":"necunoscut","id":7}\n{"cmd":"iesire"}\n{"cmd":"stare"}\n')
        iesire = io.StringIO()
        cod = serviciu.ruleaza(intrare, iesire, motor_fabrica=MotorFals)
        self.assertEqual(cod, 0)
        mesaje = [json.loads(l) for l in iesire.getvalue().splitlines()]
        self.assertEqual([m["ev"] for m in mesaje], ["gata", "stare", "eroare", "eroare"])
        self.assertEqual(mesaje[3]["id"], 7)


if __name__ == "__main__":
    unittest.main()
