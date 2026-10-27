"""Dictarea lungă (dictare_lunga.py): VAD → ferestre 30 s / 7,5 s → commit LCP, fără microfon.

Rulare:
    python -m pytest teste/test_dictare_lunga.py -q
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

import numpy as np

RADACINA = Path(__file__).resolve().parent.parent
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from dictare_transcriere_romana import dictare_lunga as dl  # noqa: E402

SR = dl.SAMPLE_RATE
BLOC = 0.5  # secunde per „cuvânt” sintetic


def liniste(sec: float) -> np.ndarray:
    return np.zeros(int(SR * sec), dtype=np.float32)


def vorbire(sec: float, k0: int = 0) -> np.ndarray:
    """„Vorbire” sintetică: blocuri de 0,5 s cu nivel constant 0,1+0,001·k → cuvântul w{k}."""
    n = int(sec / BLOC)
    return np.concatenate([np.full(int(SR * BLOC), 0.1 + 0.001 * (k0 + i), dtype=np.float32) for i in range(n)])


def asr_sintetic(audio: np.ndarray, _prior: str = "") -> str:
    """ASR fals determinist: fiecare bloc de 0,5 s cu sunet devine cuvântul lui."""
    cuvinte = []
    pas = int(SR * BLOC)
    for off in range(0, audio.size, pas):
        b = audio[off: off + pas]
        b = b[np.abs(b) > 0.05]
        if b.size >= pas // 2:
            cuvinte.append(f"w{int(round((float(b.mean()) - 0.1) / 0.001))}")
    return " ".join(cuvinte)


def strat(**kw) -> dl.DictareLunga:
    kw.setdefault("vad", dl.EnergyVad())
    return dl.DictareLunga(kw.pop("asr", asr_sintetic), kw.pop("la_commit", None), **kw)


def ruleaza(s: dl.DictareLunga, pcm: np.ndarray, bloc_s: float = 0.1) -> None:
    n = int(SR * bloc_s)
    for off in range(0, pcm.size, n):
        s.push(pcm[off: off + n])
    s.finish()


class TestComponente(unittest.TestCase):
    def test_ring_buffer_pastreaza_ultima_secunda(self):
        r = dl.RingBuffer(capacity_ms=100)  # 1600 eșantioane
        r.write(np.arange(1000, dtype=np.float32))
        r.write(np.arange(1000, 2000, dtype=np.float32))
        snap = r.snapshot()
        self.assertEqual(snap.size, 1600)
        np.testing.assert_array_equal(snap, np.arange(400, 2000, dtype=np.float32))
        r.clear()
        self.assertEqual(r.size(), 0)

    def test_chunker_ferestre_30s_suprapunere_7_5s(self):
        c = dl.WindowChunker()
        ferestre = c.push(np.zeros(SR * 70, dtype=np.float32))
        self.assertEqual([w.start_sample / SR for w in ferestre], [0.0, 22.5])
        self.assertTrue(all(w.samples.size == 30 * SR for w in ferestre))
        coada = c.flush()
        self.assertEqual(coada.start_sample / SR, 45.0)
        self.assertAlmostEqual(coada.samples.size / SR, 25.0)
        self.assertIsNone(c.flush())

    def test_chunker_coada_prea_scurta_se_arunca(self):
        c = dl.WindowChunker()
        c.push(np.zeros(int(SR * 0.3), dtype=np.float32))
        self.assertIsNone(c.flush())

    def test_poarta_preroll_si_hangover(self):
        g = dl.VadGate(0.5, preroll_ms=250, hangover_ms=600)
        f = np.ones(dl.FRAME, dtype=np.float32)
        for _ in range(20):  # liniște: doar pre-roll-ul se ține minte
            self.assertEqual(g.process(f * 0, 0.0).size, 0)
        prim = g.process(f, 0.9)
        self.assertEqual(prim.size, 4000 + dl.FRAME)  # 250 ms pre-roll + cadrul curent
        self.assertTrue(g.in_speech)
        iesit = 0
        while g.in_speech:
            iesit += g.process(f * 0, 0.0).size
        self.assertEqual(iesit, int(SR * 0.6))  # 600 ms hangover

    def test_vad_energie(self):
        v = dl.EnergyVad()
        self.assertEqual(v.prob(np.zeros(dl.FRAME)), 0.0)
        self.assertGreaterEqual(v.prob(np.full(dl.FRAME, 0.1)), 0.5)

    def test_creeaza_vad_energie_si_auto_nu_arunca(self):
        self.assertEqual(dl.creeaza_vad("energie").name, "energie")
        v = dl.creeaza_vad("auto")
        self.assertIn(v.name, ("silero-ggml", "silero-onnx", "energie"))
        self.assertTrue(0.0 <= float(v.prob(np.zeros(dl.FRAME, dtype=np.float32))) <= 1.0)


class TestDictareLunga(unittest.TestCase):
    def test_enunt_lung_fara_dubluri_pe_suprapunere(self):
        """70 s vorbite fără pauză → 3 ferestre suprapuse; LCP lasă fiecare cuvânt o singură dată."""
        commits = []
        s = strat(la_commit=commits.append)
        ruleaza(s, np.concatenate([vorbire(70.0), liniste(1.0)]))
        self.assertEqual(s.stats.enunturi, 1)
        self.assertEqual(s.stats.ferestre, 3)
        asteptat = " ".join(f"w{k}" for k in range(140))
        self.assertEqual(" ".join(s.text().split()), asteptat)
        self.assertEqual(" ".join(c.text for c in commits), s.text())

    def test_pauza_lunga_incepe_idee_noua(self):
        commits = []
        evenimente = []
        s = strat(la_commit=commits.append, la_eveniment=evenimente.append)
        pcm = np.concatenate([
            vorbire(3.0, 0), liniste(3.0),     # pauză 3 s ≥ 2 s → idee nouă
            vorbire(3.0, 100), liniste(0.9),   # pauză scurtă → aceeași idee
            vorbire(3.0, 200), liniste(1.0),
        ])
        ruleaza(s, pcm)
        self.assertEqual(s.stats.enunturi, 3)
        self.assertEqual(s.stats.idei, 2)
        self.assertEqual([c.idee for c in commits], [1, 2, 2])
        self.assertEqual([c.idee_noua for c in commits], [False, True, False])
        self.assertEqual(commits[1].text.split()[0], "w100")
        self.assertEqual([e["idee"] for e in evenimente if e["ev"] == "idee"], [1, 2])
        self.assertEqual(sum(e["ev"] == "sfarsit_enunt" for e in evenimente), 3)

    def test_linistea_nu_ajunge_la_asr(self):
        apeluri = []
        s = strat(asr=lambda a, p: apeluri.append(a.size) or "x")
        ruleaza(s, liniste(20.0))
        self.assertEqual(apeluri, [])
        self.assertEqual(s.stats.enunturi, 0)
        self.assertEqual(s.text(), "")

    def test_blocuri_de_orice_marime(self):
        pcm = np.concatenate([vorbire(5.0), liniste(1.0)])
        texte = []
        for bloc in (0.013, 0.1, 1.7):
            s = strat()
            ruleaza(s, pcm, bloc)
            texte.append(s.text())
        self.assertEqual(len(set(texte)), 1, texte)
        self.assertEqual(texte[0], " ".join(f"w{k}" for k in range(10)))

    def test_session_jsonl(self):
        with TemporaryDirectory() as d:
            cale = Path(d) / "sub" / "session.jsonl"
            s = strat(sesiune=cale, model_id="test")
            ruleaza(s, np.concatenate([vorbire(2.0), liniste(3.0), vorbire(2.0, 50), liniste(1.0)]))
            s.close()
            randuri = [json.loads(r) for r in cale.read_text(encoding="utf-8").splitlines() if r.strip()]
            commits = [r for r in randuri if r.get("type", "commit") == "commit"]
            self.assertEqual(len(commits), 2)
            self.assertEqual([r["source"] for r in commits], ["dictare_lunga#idee=1", "dictare_lunga#idee=2"])
            self.assertEqual(commits[1]["text"].split()[0], "w50")

    def test_eroare_asr_nu_opreste_dictarea(self):
        n = {"i": 0}

        def asr(a, p):
            n["i"] += 1
            if n["i"] == 1:
                raise RuntimeError("bum")
            return asr_sintetic(a)

        s = strat(asr=asr)
        ruleaza(s, np.concatenate([vorbire(2.0), liniste(1.0), vorbire(2.0, 10), liniste(1.0)]))
        self.assertEqual(s.stats.erori_asr, 1)
        self.assertEqual(s.text(), "w10 w11 w12 w13")

    def test_anularea_trece_mai_departe(self):
        Anulat = type("Anulat", (Exception,), {})

        def asr(a, p):
            raise Anulat()

        s = strat(asr=asr)
        with self.assertRaises(Exception) as ctx:
            ruleaza(s, np.concatenate([vorbire(2.0), liniste(1.0)]))
        self.assertEqual(type(ctx.exception).__name__, "Anulat")

    def test_context_commit_trimite_textul_stabil(self):
        prioruri = []

        def asr(a, p):
            prioruri.append(p)
            return asr_sintetic(a)

        s = strat(asr=asr, context_fn="commit")
        ruleaza(s, np.concatenate([vorbire(2.0), liniste(1.0), vorbire(2.0, 10), liniste(1.0)]))
        self.assertEqual(prioruri[0], "")
        self.assertIn("w3", prioruri[1])


class TestSetari(unittest.TestCase):
    def test_config_implicit_oprit(self):
        from dictare_transcriere_romana import config

        c = config.Config()
        self.assertFalse(c.dictare_lunga)
        self.assertEqual(c.dictare_lunga_vad, "auto")
        self.assertEqual(c.dictare_lunga_fereastra_sec, 30.0)
        self.assertEqual(c.dictare_lunga_suprapunere_sec, 7.5)

    def test_activ_din_setari_si_mediu(self):
        with mock.patch.dict(os.environ, {"DTED_DICTARE_LUNGA": ""}):
            self.assertFalse(dl.activ(SimpleNamespace(dictare_lunga=False)))
            self.assertTrue(dl.activ(SimpleNamespace(dictare_lunga=True)))
            self.assertFalse(dl.activ(None))
        with mock.patch.dict(os.environ, {"DTED_DICTARE_LUNGA": "1"}):
            self.assertTrue(dl.activ(SimpleNamespace(dictare_lunga=False)))
        with mock.patch.dict(os.environ, {"DTED_DICTARE_LUNGA": "0"}):
            self.assertFalse(dl.activ(SimpleNamespace(dictare_lunga=True)))

    def test_din_config_limiteaza_valorile(self):
        cfg = SimpleNamespace(expert_vad_prag=5, dictare_lunga_fereastra_sec=999,
                              dictare_lunga_suprapunere_sec=-3, dictare_lunga_pauza_idee_sec="x",
                              dictare_lunga_vad="energie")
        s = dl.din_config(cfg, asr_sintetic)
        self.assertEqual(s.gate.threshold, 0.9)
        self.assertEqual(s.fereastra_s, 30.0)
        self.assertEqual(s.suprapunere_s, 0.0)
        self.assertEqual(s.pauza_idee_s, dl.PAUZA_IDEE_S)
        self.assertEqual(s.stats.vad, "energie")


class MotorSintetic:
    incarcat = True
    dispozitiv = "cpu"

    def anuleaza(self):
        pass

    def transcrie(self, sursa, limba="ro", termeni="", progres=None, faza=None):
        return SimpleNamespace(text=asr_sintetic(np.asarray(sursa, dtype=np.float32)), segmente=[])


class MicrofonSintetic:
    """Dă la fiecare preia() următoarele 0,5 s dintr-un semnal fix (vorbire, pauză, vorbire)."""

    def __init__(self, pcm):
        self.pcm = pcm
        self.poz = 0
        self.nivel = 0.2
        self.anulat = False

    def porneste(self):
        pass

    def scurgere(self):
        return 1.0

    def preia(self):
        bucata = self.pcm[self.poz: self.poz + SR // 2]
        self.poz += bucata.size
        return bucata

    def opreste(self):
        rest = self.pcm[self.poz:]
        self.poz = self.pcm.size
        return SimpleNamespace(pcm=rest)

    def anuleaza(self):
        self.anulat = True


class TestServiciuLunga(unittest.TestCase):
    def test_dictare_start_lunga(self):
        from dictare_transcriere_romana import serviciu

        pcm = np.concatenate([vorbire(2.0), liniste(3.0), vorbire(2.0, 20), liniste(1.0)])
        mic = MicrofonSintetic(pcm)
        mesaje = []
        s = serviciu.Serviciu(mesaje.append, motor_fabrica=lambda *a: MotorSintetic(),
                              microfon_fabrica=lambda: mic, secunde_bucata=0.5)
        s.executa({"cmd": "dictare_start", "id": "d1", "lunga": True, "vad": "energie"})
        limita = time.time() + 20
        while mic.poz < pcm.size and time.time() < limita:
            time.sleep(0.05)
        s.executa({"cmd": "dictare_stop", "id": "d1"})
        s.asteapta(20)
        fragmente = [m for m in mesaje if m.get("ev") == "fragment"]
        self.assertEqual([f["text"] for f in fragmente], ["w0 w1 w2 w3", "w20 w21 w22 w23"])
        self.assertEqual([f["idee_noua"] for f in fragmente], [False, True])
        self.assertEqual([m["idee"] for m in mesaje if m.get("ev") == "idee"], [1, 2])
        oprita = [m for m in mesaje if m.get("ev") == "dictare_oprita"]
        self.assertEqual(oprita[-1]["text"], "w0 w1 w2 w3 w20 w21 w22 w23")
        self.assertFalse([m for m in mesaje if m.get("ev") == "eroare"])


class TestUiDictareLunga(unittest.TestCase):
    """Bucla din ui_dictare pe calea lungă, cu microfon și motor sintetice (fără fereastră)."""

    def test_bucla_lunga_paragraf_la_idee_noua(self):
        import types

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from dictare_transcriere_romana.ui_qt import ui_dictare
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"PySide6 indisponibil: {exc}")
        P = ui_dictare.PaginaDictare
        pcm = np.concatenate([vorbire(2.0), liniste(3.0), vorbire(2.0, 20), liniste(1.0)])
        anulat = threading.Event()

        class Mic(MicrofonSintetic):
            def preia(self_m):
                b = super().preia()
                if self_m.poz >= self_m.pcm.size:
                    anulat.set()  # ca „Oprește”: ultimul preia() ia și coada
                return b

        apeluri = []
        cfg = SimpleNamespace(dictare_lunga=True, dictare_lunga_vad="energie", rezumat_activ=False,
                              limba="ro", termeni="", expert_fereastra_sec=4.0)
        fals = SimpleNamespace(
            _microfon=Mic(pcm), config=cfg, _anulat=anulat, _secunde_audio=0.0,
            aplicatie=SimpleNamespace(_motor=MotorSintetic(),
                                      coada=SimpleNamespace(trimite=lambda f, *a, **k: apeluri.append((f, a)))),
            _sunet=lambda *_: None, _eroare_microfon_qt=lambda *_: None,
            _adauga_text_idee="adauga", _opreste="opreste", _spune_procesare="procesare",
        )
        fals._bucla_lunga = types.MethodType(P._bucla_lunga, fals)
        with TemporaryDirectory() as d, mock.patch.dict(os.environ, {"DTED_DICTARE_LUNGA": ""}), \
                mock.patch.object(dl, "cale_sesiune_noua", lambda: Path(d) / "s.jsonl"):
            P._bucla(fals)
            self.assertTrue((Path(d) / "s.jsonl").exists())
        adaugate = [a for f, a in apeluri if f == "adauga"]
        self.assertEqual(adaugate, [("w0 w1 w2 w3", False), ("w20 w21 w22 w23", True)])
        self.assertEqual(apeluri[-1][0], "opreste")
        self.assertAlmostEqual(fals._secunde_audio, pcm.size / SR)

    def test_editor_paragraf_nou(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtWidgets import QApplication

            from dictare_transcriere_romana.ui_qt.ui_editor import Editor
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"PySide6 indisponibil: {exc}")
        app = QApplication.instance() or QApplication([])  # noqa: F841
        e = Editor(None, SimpleNamespace(text=""))
        e.insereaza("Prima idee.")
        e.paragraf_nou()
        e.paragraf_nou()  # nu dublează rândul gol
        e.insereaza("A doua idee.")
        self.assertEqual(e.text(), "Prima idee.\n\nA doua idee.")


WAV_SMOKE = RADACINA / "cpp" / "parakeet" / "ro_smoke_16k.wav"


@unittest.skipUnless(WAV_SMOKE.exists(), "lipsește ro_smoke_16k.wav")
class TestSileroReal(unittest.TestCase):
    """Silero adevărat (ggml sau ONNX), pe vorbire reală + pauze sintetice. Fără microfon."""

    def _wav(self):
        with wave.open(str(WAV_SMOKE), "rb") as w:
            return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

    def _verifica(self, backend):
        v = dl.creeaza_vad(backend)
        if v.name == "energie":
            self.skipTest(f"Silero {backend} indisponibil aici")
        a = self._wav()
        s = strat(vad=v, asr=lambda x, p: f"[{x.size / SR:.1f}]")
        ruleaza(s, np.concatenate([a, liniste(3.0), a, liniste(0.9), a, liniste(1.0)]))
        self.assertEqual(s.stats.enunturi, 3, s.text())
        self.assertEqual(s.stats.idei, 2)

    def test_silero_ggml(self):
        self._verifica("ggml")

    def test_silero_onnx(self):
        self._verifica("onnx")


class TestSetariDictareLunga(unittest.TestCase):
    """A9: bifa din Setări → Sunet scrie ``config.dictare_lunga``; mediul tot are prioritate."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("PySide6 indisponibil")
        cls.app = QApplication.instance() or QApplication([])

    def _dlg(self, cfg):
        from dictare_transcriere_romana.ui_qt.ui_setari import FereastraSetari
        return FereastraSetari(None, cfg)

    def test_bifa_implicit_oprita_si_salvata(self):
        from dictare_transcriere_romana import config as config_modul
        with mock.patch.dict(os.environ, {"DTED_DICTARE_LUNGA": ""}):
            cfg = config_modul.Config()
            dlg = self._dlg(cfg)
            try:
                self.assertFalse(dlg.var_dictare_lunga)
                self.assertEqual(dlg.eticheta_dictare_lunga_mediu.text(), "")
                dlg.var_dictare_lunga = True
                dlg._aduna()
                self.assertTrue(dlg.config.dictare_lunga)
                self.assertTrue(dl.activ(dlg.config))
                dlg.var_dictare_lunga = False
                dlg._aduna()
                self.assertFalse(dlg.config.dictare_lunga)
                self.assertFalse(dl.activ(dlg.config))
            finally:
                dlg.deleteLater()

    def test_bifa_reflecta_config_si_avertizeaza_mediul(self):
        from dictare_transcriere_romana import config as config_modul
        with mock.patch.dict(os.environ, {"DTED_DICTARE_LUNGA": "0"}):
            cfg = config_modul.Config(dictare_lunga=True)
            dlg = self._dlg(cfg)
            try:
                self.assertTrue(dlg.var_dictare_lunga)
                self.assertIn("DTED_DICTARE_LUNGA=0", dlg.eticheta_dictare_lunga_mediu.text())
                self.assertFalse(dl.activ(cfg))  # mediul câștigă față de bifă
            finally:
                dlg.deleteLater()

    def test_salvare_incarcare_pastreaza_bifa(self):
        from dictare_transcriere_romana import cai, config as config_modul
        with TemporaryDirectory() as d:
            f = Path(d) / "config.json"
            with mock.patch.object(cai, "fisier_config", lambda: f):
                cfg = config_modul.Config(dictare_lunga=True)
                config_modul.salveaza(cfg)
                self.assertTrue(config_modul.incarca().dictare_lunga)


if __name__ == "__main__":
    unittest.main()
