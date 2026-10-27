"""Dictarea lungă (long_dictation_layer): Silero VAD + ferestre 30 s / 7,5 s + commit stabil.

Strat în jurul motorului ASR existent (Whisper / Parakeet), fără să-i schimbe greutățile.
Oglindește în Python exact fluxul nativ din ``cpp/native/src/dted_native_main.cpp``
(clasa ``Run``) și ``cpp/audio_engine`` (RingBuffer / VadGate / WindowChunker):

    microfon 16 kHz mono
      → cadre de 512 eșantioane (32 ms = un pas Silero)
      → RingBuffer 1000 ms
      → VadGate: pre-roll 250 ms, hangover 600 ms, prag Silero 0,5
      → WindowChunker: maxim 30 s, suprapunere 7,5 s (pe fiecare enunț)
      → asr_fn(fereastră, text_anterior)  (motorul existent, injectat)
      → CommitEngine (LCP pe suprapunere, ``commit_native``: C++ dacă e compilat)
      → session.jsonl (``session_native``: C++ dacă e compilat) + callback ``la_commit``

Detectorul de vorbire (``creeaza_vad``), în ordinea ``auto``:

1. ``silero-ggml`` – același ``libdted_silero.dll`` + ``models/vad/silero-vad.gguf`` ca
   ``dted_native.exe`` (C ABI ``dted_silero_*`` prin ctypes);
2. ``silero-onnx`` – ``silero_vad_v6.onnx`` livrat cu faster-whisper (onnxruntime, CPU);
3. ``energie`` – pragul de energie al stub-ului C++ (fără modele).

``$DTED_VAD_BACKEND`` (auto/ggml/onnx/energie) forțează alegerea. Ideile: un enunț nou
care începe după cel puțin ``pauza_idee_s`` secunde de liniște deschide o idee nouă
(paragraf în editor). ASR-ul rămâne pluggable; dispozitivul ASR (CPU/GPU,
``DTED_ASR_DEVICE``) nu e atins aici.

Smoke test fără microfon::

    python -m dictare_transcriere_romana.dictare_lunga --wav fisier.wav --asr none
    python -m dictare_transcriere_romana.dictare_lunga --wav fisier.wav --asr whisper --session out.jsonl
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

SAMPLE_RATE = 16_000
FRAME = 512                 # 32 ms, un pas Silero
RING_MS = 1000
PREROLL_MS = 250
HANGOVER_MS = 600           # ca dted_native (header-ul C++ are 200, nativul rulează cu 600)
VAD_THRESHOLD = 0.5
WINDOW_MAX_S = 30.0
WINDOW_OVERLAP_S = 7.5
MIN_FLUSH_S = 0.4
PAUZA_IDEE_S = 2.0

AsrFn = Callable[[np.ndarray, str], str]


# ---------------------------------------------------------------------------- buffere


class RingBuffer:
    """Ultimele ``capacity_ms`` de sunet (ca ``dted::RingBuffer``)."""

    def __init__(self, capacity_ms: int = RING_MS, sample_rate: int = SAMPLE_RATE):
        self.capacity = max(1, int(sample_rate * capacity_ms / 1000))
        self._buf = np.zeros(self.capacity, dtype=np.float32)
        self._head = 0
        self._filled = 0

    def write(self, samples: np.ndarray) -> None:
        s = np.asarray(samples, dtype=np.float32).reshape(-1)
        if s.size >= self.capacity:
            self._buf[:] = s[-self.capacity:]
            self._head, self._filled = 0, self.capacity
            return
        end = self._head + s.size
        if end <= self.capacity:
            self._buf[self._head:end] = s
        else:
            k = self.capacity - self._head
            self._buf[self._head:] = s[:k]
            self._buf[: s.size - k] = s[k:]
        self._head = end % self.capacity
        self._filled = min(self.capacity, self._filled + s.size)

    def snapshot(self) -> np.ndarray:
        if self._filled < self.capacity:
            return self._buf[: self._filled].copy()
        return np.concatenate([self._buf[self._head:], self._buf[: self._head]])

    def clear(self) -> None:
        self._head = self._filled = 0

    def size(self) -> int:
        return self._filled


@dataclass
class Fereastra:
    samples: np.ndarray
    start_sample: int
    end_sample: int
    window_id: int


class WindowChunker:
    """Ferestre de maxim ``max_s`` cu suprapunere ``overlap_s`` (ca ``dted::WindowChunker``)."""

    def __init__(self, max_s: float = WINDOW_MAX_S, overlap_s: float = WINDOW_OVERLAP_S,
                 sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.max_n = int(sample_rate * max_s)
        self.overlap_n = int(sample_rate * overlap_s)
        self.hop_n = self.max_n - self.overlap_n if self.max_n > self.overlap_n else self.max_n
        self._buf = np.zeros(0, dtype=np.float32)
        self._abs_start = 0
        self._next_id = 0

    def push(self, samples: np.ndarray) -> list[Fereastra]:
        s = np.asarray(samples, dtype=np.float32).reshape(-1)
        out: list[Fereastra] = []
        if not s.size:
            return out
        self._buf = np.concatenate([self._buf, s])
        while self._buf.size >= self.max_n:
            out.append(Fereastra(self._buf[: self.max_n].copy(), self._abs_start,
                                 self._abs_start + self.max_n, self._next_id))
            self._next_id += 1
            self._buf = self._buf[self.hop_n:]
            self._abs_start += self.hop_n
        return out

    def flush(self) -> Optional[Fereastra]:
        if self._buf.size < int(self.sample_rate * MIN_FLUSH_S):
            self._buf = np.zeros(0, dtype=np.float32)
            return None
        w = Fereastra(self._buf.copy(), self._abs_start, self._abs_start + self._buf.size, self._next_id)
        self._next_id += 1
        self._abs_start = w.end_sample
        self._buf = np.zeros(0, dtype=np.float32)
        return w


# ---------------------------------------------------------------------------- VAD


class EnergyVad:
    """Stub-ul de energie din C++: probabilitatea = RMS (prag 0,5 → RMS 0,02)."""

    name = "energie"

    def prob(self, frame: np.ndarray) -> float:
        f = np.asarray(frame, dtype=np.float64)
        rms = float(np.sqrt(np.mean(f * f))) if f.size else 0.0
        return min(1.0, rms / 0.04)  # 0.5 ↔ 0.02 RMS, ca `threshold * 0.04` din vad_gate.cpp

    def reset(self) -> None:
        pass


class SileroOnnx:
    """Silero v6 ONNX în flux (stare h/c + context 64 eșantioane), cel livrat cu faster-whisper."""

    name = "silero-onnx"
    CONTEXT = 64

    def __init__(self, path: str | os.PathLike | None = None):
        import onnxruntime  # noqa: PLC0415

        if path is None:
            from faster_whisper.utils import get_assets_path  # noqa: PLC0415

            path = os.path.join(get_assets_path(), "silero_vad_v6.onnx")
        if not Path(path).is_file():
            raise FileNotFoundError(str(path))
        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 4
        self.session = onnxruntime.InferenceSession(str(path), providers=["CPUExecutionProvider"],
                                                    sess_options=opts)
        self.path = str(path)
        self.reset()

    def reset(self) -> None:
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._ctx = np.zeros(self.CONTEXT, dtype=np.float32)

    def prob(self, frame: np.ndarray) -> float:
        f = np.asarray(frame, dtype=np.float32).reshape(-1)
        if f.size < FRAME:
            f = np.pad(f, (0, FRAME - f.size))
        x = np.concatenate([self._ctx, f[:FRAME]])[None, :]
        out, self._h, self._c = self.session.run(None, {"input": x, "h": self._h, "c": self._c})
        self._ctx = f[FRAME - self.CONTEXT: FRAME].copy()
        return float(np.asarray(out).reshape(-1)[0])


def _candidati_silero_dll() -> list[Path]:
    c: list[Path] = []
    env = os.environ.get("DTED_SILERO_DLL", "").strip()
    if env:
        c.append(Path(env))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        c.append(Path(meipass) / "libdted_silero.dll")
    radacina = Path(__file__).resolve().parent.parent
    c.append(radacina / "cpp" / "native" / "build" / "libdted_silero.dll")
    return c


def _candidati_silero_gguf() -> list[Path]:
    c: list[Path] = []
    env = os.environ.get("DTED_VAD_MODEL", "").strip()
    if env:
        c.append(Path(env))
    md = os.environ.get("DTED_MODELS_DIR", "").strip()
    if md:
        c.append(Path(md) / "vad" / "silero-vad.gguf")
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        c.append(Path(meipass) / "models" / "vad" / "silero-vad.gguf")
    la = os.environ.get("LOCALAPPDATA", "")
    if la:
        c.append(Path(la) / "DTED" / "models" / "vad" / "silero-vad.gguf")
    c.append(Path.home() / ".local" / "share" / "dted" / "models" / "vad" / "silero-vad.gguf")
    return c


class SileroGgml:
    """Același Silero ggml ca ``dted_native.exe`` (``libdted_silero.dll``, C ABI)."""

    name = "silero-ggml"

    def __init__(self, dll: str | os.PathLike | None = None, gguf: str | os.PathLike | None = None,
                 n_threads: int = 1):
        dll_p = Path(dll) if dll else next((p for p in _candidati_silero_dll() if p.is_file()), None)
        gguf_p = Path(gguf) if gguf else next((p for p in _candidati_silero_gguf() if p.is_file()), None)
        if dll_p is None or not dll_p.is_file():
            raise FileNotFoundError("libdted_silero.dll lipsește")
        if gguf_p is None or not gguf_p.is_file():
            raise FileNotFoundError("silero-vad.gguf lipsește")
        self._dll_dir = None
        if hasattr(os, "add_dll_directory"):
            self._dll_dir = os.add_dll_directory(str(dll_p.parent))  # libstdc++ / libgomp lângă DLL
        lib = ctypes.CDLL(str(dll_p))
        lib.dted_silero_open.restype = ctypes.c_void_p
        lib.dted_silero_open.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t]
        lib.dted_silero_feed.restype = ctypes.c_int
        lib.dted_silero_feed.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_size_t,
                                         ctypes.POINTER(ctypes.c_float)]
        lib.dted_silero_reset.argtypes = [ctypes.c_void_p]
        lib.dted_silero_close.argtypes = [ctypes.c_void_p]
        err = ctypes.create_string_buffer(512)
        h = lib.dted_silero_open(str(gguf_p).encode("utf-8"), int(n_threads), err, len(err))
        if not h:
            raise RuntimeError(f"dted_silero_open: {err.value.decode('utf-8', 'replace')}")
        self._lib, self._h = lib, h
        self.dll, self.gguf = str(dll_p), str(gguf_p)
        self._last = 0.0

    def prob(self, frame: np.ndarray) -> float:
        f = np.ascontiguousarray(frame, dtype=np.float32).reshape(-1)
        p = ctypes.c_float(self._last)
        n = self._lib.dted_silero_feed(self._h, f.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), f.size,
                                       ctypes.byref(p))
        if n > 0:
            self._last = float(p.value)
        return self._last

    def reset(self) -> None:
        self._last = 0.0
        if self._h:
            self._lib.dted_silero_reset(self._h)

    def close(self) -> None:
        if getattr(self, "_h", None):
            self._lib.dted_silero_close(self._h)
            self._h = None

    def __del__(self):  # noqa: D105
        try:
            self.close()
        except Exception:
            pass


def creeaza_vad(backend: str | None = None, log: Callable[[str], None] | None = None):
    """Primul detector care pornește: ggml → onnx → energie (sau cel cerut)."""
    cerut = (backend or os.environ.get("DTED_VAD_BACKEND", "") or "auto").strip().lower()
    ordine = {"ggml": ["ggml"], "onnx": ["onnx"], "energie": ["energie"], "energy": ["energie"]}.get(
        cerut, ["ggml", "onnx", "energie"])
    for fel in ordine:
        try:
            if fel == "ggml":
                return SileroGgml()
            if fel == "onnx":
                return SileroOnnx()
            return EnergyVad()
        except Exception as exc:  # noqa: BLE001
            if log:
                log(f"Dictare lungă: VAD {fel} indisponibil ({exc}).")
    return EnergyVad()


class VadGate:
    """Poarta de vorbire, identică cu ``dted::VadGate::process`` (pre-roll + hangover)."""

    def __init__(self, threshold: float = VAD_THRESHOLD, preroll_ms: int = PREROLL_MS,
                 hangover_ms: int = HANGOVER_MS, sample_rate: int = SAMPLE_RATE):
        self.threshold = float(threshold)
        self.preroll_n = int(sample_rate * preroll_ms / 1000)
        self.hangover_n = int(sample_rate * hangover_ms / 1000)
        self.in_speech = False
        self.last_prob = 0.0
        self._hang_left = 0
        self._preroll = np.zeros(0, dtype=np.float32)

    def process(self, frame: np.ndarray, prob: float) -> np.ndarray:
        f = np.asarray(frame, dtype=np.float32).reshape(-1)
        self.last_prob = float(prob)
        voce = prob >= self.threshold
        parti: list[np.ndarray] = []
        if not self.in_speech:
            if voce:
                parti += [self._preroll, f]
                self._preroll = np.zeros(0, dtype=np.float32)
                self.in_speech = True
                self._hang_left = self.hangover_n
            else:
                self._preroll = np.concatenate([self._preroll, f])[-self.preroll_n:] if self.preroll_n else \
                    np.zeros(0, dtype=np.float32)
        else:
            if voce:
                parti.append(f)
                self._hang_left = self.hangover_n
            elif self._hang_left > 0:
                take = min(f.size, self._hang_left)
                parti.append(f[:take])
                self._hang_left -= take
                if self._hang_left == 0:
                    self.in_speech = False
            else:
                self.in_speech = False
                self._preroll = f[-self.preroll_n:].copy() if self.preroll_n else np.zeros(0, dtype=np.float32)
        return np.concatenate(parti) if parti else np.zeros(0, dtype=np.float32)


# ---------------------------------------------------------------------------- stratul


@dataclass
class Commit:
    """Un text stabil, gata de pus în editor / session.jsonl."""

    text: str
    t0: float
    t1: float
    idee: int
    idee_noua: bool
    enunt: int
    seq: int = 0


@dataclass
class Statistici:
    audio_s: float = 0.0
    enunturi: int = 0
    ferestre: int = 0
    commits: int = 0
    asr_ms: float = 0.0
    vad_ms: float = 0.0
    idei: int = 0
    vad: str = ""
    erori_asr: int = 0
    extra: dict = field(default_factory=dict)


class DictareLunga:
    """Strat de dictare lungă. Apelează ``push(pcm16k)`` din firul de dictare, ``finish()`` la oprire.

    * ``asr_fn(audio, text_anterior) -> text`` – motorul existent (Whisper/Parakeet);
    * ``la_commit(Commit)`` – text stabil (după LCP pe suprapunere), în ordine;
    * ``context_fn() -> str`` – opțional, textul anterior pentru prompt (implicit: niciunul,
      ca dictarea pe bucăți; ``"commit"`` = coada stabilă din CommitEngine);
    * ``sesiune`` – cale ``.jsonl`` (``session_native``); ``None`` = nu scrie (ex. când
      ``MemorieDictare`` scrie deja session.jsonl).
    """

    def __init__(self, asr_fn: AsrFn, la_commit: Callable[[Commit], None] | None = None, *,
                 vad=None, prag_vad: float = VAD_THRESHOLD, preroll_ms: int = PREROLL_MS,
                 hangover_ms: int = HANGOVER_MS, fereastra_s: float = WINDOW_MAX_S,
                 suprapunere_s: float = WINDOW_OVERLAP_S, pauza_idee_s: float = PAUZA_IDEE_S,
                 context_fn: Callable[[], str] | str | None = None,
                 sesiune: str | os.PathLike | None = None, model_id: str = "",
                 la_eveniment: Callable[[dict], None] | None = None,
                 log: Callable[[str], None] | None = None):
        from . import commit_native  # noqa: PLC0415

        self.asr_fn = asr_fn
        self.la_commit = la_commit
        self.la_eveniment = la_eveniment
        self._log = log or (lambda _m: None)
        self.vad = vad if vad is not None else creeaza_vad(log=self._log)
        self.gate = VadGate(prag_vad, preroll_ms, hangover_ms)
        self.ring = RingBuffer()
        self.fereastra_s = float(fereastra_s)
        self.suprapunere_s = float(suprapunere_s)
        self.pauza_idee_s = float(pauza_idee_s)
        self.context_fn = context_fn
        self.model_id = model_id
        self.commit = commit_native.CommitEngine()
        self.stats = Statistici(vad=getattr(self.vad, "name", type(self.vad).__name__))
        self.texte: list[str] = []
        self.commits: list[Commit] = []
        self._rest = np.zeros(0, dtype=np.float32)
        self._chunker: WindowChunker | None = None
        self._clock = 0
        self._utt_start = 0
        self._seg = 0
        self._ultim_sfarsit: int | None = None
        self._idee = 0
        self._idee_noua = False
        self._win_start_s = 0.0
        self._store = None
        self.cale_sesiune = Path(sesiune) if sesiune else None
        if self.cale_sesiune is not None:
            from . import session_native  # noqa: PLC0415

            self.cale_sesiune.parent.mkdir(parents=True, exist_ok=True)
            self._store = session_native.SessionStore(self.cale_sesiune)

    # ------------------------------------------------------------------ intrare

    def push(self, pcm: np.ndarray) -> list[Commit]:
        """Sunet 16 kHz mono float32, orice lungime. Întoarce commit-urile produse acum."""
        s = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if not s.size:
            return []
        self.stats.audio_s += s.size / SAMPLE_RATE
        buf = np.concatenate([self._rest, s]) if self._rest.size else s
        n_full = (buf.size // FRAME) * FRAME
        self._rest = buf[n_full:].copy()
        noi: list[Commit] = []
        for off in range(0, n_full, FRAME):
            noi += self._feed_frame(buf[off: off + FRAME])
        return noi

    def finish(self) -> list[Commit]:
        """La oprire: cadrul parțial, apoi închiderea enunțului (coada + finalize)."""
        noi: list[Commit] = []
        if self._rest.size:
            frame, self._rest = self._rest, np.zeros(0, dtype=np.float32)
            noi += self._feed_frame(frame)
        noi += self._end_utterance()
        return noi

    def text(self) -> str:
        return " ".join(self.texte)

    def close(self) -> None:
        if self._store is not None and hasattr(self._store, "close"):
            try:
                self._store.close()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ intern

    def _feed_frame(self, frame: np.ndarray) -> list[Commit]:
        self.ring.write(frame)
        self._clock += frame.size
        t = time.perf_counter()
        p = float(self.vad.prob(frame))
        self.stats.vad_ms += (time.perf_counter() - t) * 1000
        era = self.gate.in_speech
        gated = self.gate.process(frame, p)
        noi: list[Commit] = []
        if gated.size:
            noi += self._on_gated(gated)
        if era and not self.gate.in_speech:
            noi += self._end_utterance()
        return noi

    def _on_gated(self, audio: np.ndarray) -> list[Commit]:
        if self._chunker is None:
            self._chunker = WindowChunker(self.fereastra_s, self.suprapunere_s)
            self._utt_start = max(0, self._clock - audio.size)
            self.stats.enunturi += 1
            pauza = None if self._ultim_sfarsit is None else (self._utt_start - self._ultim_sfarsit) / SAMPLE_RATE
            if self._idee == 0 or (pauza is not None and pauza >= self.pauza_idee_s):
                self._idee += 1
                self.stats.idei = self._idee
                self._idee_noua = self._idee > 1
                self._event({"ev": "idee", "idee": self._idee, "t0": round(self._utt_start / SAMPLE_RATE, 2),
                             "pauza_s": None if pauza is None else round(pauza, 2)})
        ov = int(self.suprapunere_s * 1000)
        noi: list[Commit] = []
        for w in self._chunker.push(audio):
            noi += self._run_window(w, 0 if w.window_id == 0 else ov)
        return noi

    def _end_utterance(self) -> list[Commit]:
        if self._chunker is None:
            return []
        ov = int(self.suprapunere_s * 1000)
        noi: list[Commit] = []
        tail = self._chunker.flush()
        if tail is not None:
            noi += self._run_window(tail, 0 if tail.window_id == 0 else ov)
        r = self.commit.finalize()
        noi += self._commit_texts(_stable(r))
        self._chunker = None
        self._ultim_sfarsit = self._clock
        self._event({"ev": "sfarsit_enunt", "enunt": self.stats.enunturi, "t1": round(self._clock / SAMPLE_RATE, 2)})
        try:
            self.vad.reset()
        except Exception:  # noqa: BLE001
            pass
        return noi

    def _prior(self) -> str:
        if self.context_fn == "commit":
            return self.commit.prior_text()
        if callable(self.context_fn):
            try:
                return self.context_fn() or ""
            except Exception:  # noqa: BLE001
                return ""
        return ""

    def _run_window(self, w: Fereastra, overlap_ms: int) -> list[Commit]:
        t = time.perf_counter()
        try:
            text = (self.asr_fn(w.samples, self._prior()) or "").strip()
        except Exception as exc:  # noqa: BLE001 - o fereastră ratată nu oprește dictarea
            if type(exc).__name__ == "Anulat":
                raise
            self.stats.erori_asr += 1
            self._log(f"Dictare lungă: ASR a eșuat pe fereastra {w.window_id}: {exc}")
            text = ""
        ms = (time.perf_counter() - t) * 1000
        self.stats.asr_ms += ms
        self.stats.ferestre += 1
        self._win_start_s = (self._utt_start + w.start_sample) / SAMPLE_RATE
        self._event({"ev": "fereastra", "win": self.stats.ferestre, "start_s": round(self._win_start_s, 2),
                     "dur_s": round(w.samples.size / SAMPLE_RATE, 2), "asr_ms": round(ms), "text": text})
        self._seg += 1
        r = self.commit.on_window(self._seg, text, overlap_ms)
        return self._commit_texts(_stable(r))

    def _commit_texts(self, stable: list[str]) -> list[Commit]:
        noi: list[Commit] = []
        for t in stable:
            t = (t or "").strip()
            if not t:
                continue
            c = Commit(t, self._win_start_s, self._clock / SAMPLE_RATE, self._idee, self._idee_noua,
                       self.stats.enunturi)
            self._idee_noua = False
            if self._store is not None:
                try:
                    c.seq = int(self._store.append_commit({
                        "text": t, "timestamp_ms": int(time.time() * 1000), "model_id": self.model_id,
                        "source": f"dictare_lunga#idee={c.idee}",
                    }))
                except Exception as exc:  # noqa: BLE001
                    self._log(f"Dictare lungă: session.jsonl nu s-a scris ({exc}).")
            self.texte.append(t)
            self.commits.append(c)
            self.stats.commits += 1
            noi.append(c)
            if self.la_commit is not None:
                self.la_commit(c)
        return noi

    def _event(self, ev: dict) -> None:
        if self.la_eveniment is not None:
            try:
                self.la_eveniment(ev)
            except Exception:  # noqa: BLE001
                pass


def _stable(r) -> list[str]:
    if isinstance(r, dict):
        return list(r.get("stable_commits") or [])
    return list(getattr(r, "stable_commits", []) or [])


def activ(config) -> bool:
    """Dictarea lungă e pornită din setări (``dictare_lunga``) sau din ``$DTED_DICTARE_LUNGA=1``."""
    env = os.environ.get("DTED_DICTARE_LUNGA", "").strip().lower()
    if env in ("1", "true", "da", "on"):
        return True
    if env in ("0", "false", "nu", "off"):
        return False
    return getattr(config, "dictare_lunga", False) is True


def din_config(config, asr_fn: AsrFn, la_commit=None, **kw) -> DictareLunga:
    """Construiește stratul cu pragurile din setări (``expert_vad_prag``, ``dictare_lunga_*``)."""
    def f(cheie, implicit):
        try:
            return float(getattr(config, cheie, implicit))
        except (TypeError, ValueError):
            return implicit

    vad = kw.pop("vad", None)
    if vad is None:
        vad = creeaza_vad(str(getattr(config, "dictare_lunga_vad", "auto") or "auto"), log=kw.get("log"))
    return DictareLunga(
        asr_fn, la_commit, vad=vad,
        prag_vad=max(0.1, min(0.9, f("expert_vad_prag", VAD_THRESHOLD))),
        fereastra_s=max(5.0, min(30.0, f("dictare_lunga_fereastra_sec", WINDOW_MAX_S))),
        suprapunere_s=max(0.0, min(15.0, f("dictare_lunga_suprapunere_sec", WINDOW_OVERLAP_S))),
        pauza_idee_s=max(0.5, min(30.0, f("dictare_lunga_pauza_idee_sec", PAUZA_IDEE_S))),
        **kw,
    )


def cale_sesiune_noua() -> Path:
    from . import cai  # noqa: PLC0415

    return cai.director_instalare() / "sesiuni" / f"dictare-lunga-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"


# ---------------------------------------------------------------------------- CLI (smoke)


def _citeste_wav(cale: str) -> np.ndarray:
    import wave  # noqa: PLC0415

    try:
        with wave.open(cale, "rb") as w:
            if w.getsampwidth() == 2:
                pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
                if w.getnchannels() > 1:
                    pcm = pcm.reshape(-1, w.getnchannels()).mean(axis=1)
                if w.getframerate() != SAMPLE_RATE:
                    from .inregistrare import reesantioneaza  # noqa: PLC0415

                    pcm = reesantioneaza(pcm, w.getframerate(), SAMPLE_RATE)
                return pcm.astype(np.float32)
    except Exception:  # noqa: BLE001 - alt format: decodorul programului
        pass
    from . import motor  # noqa: PLC0415

    return np.asarray(motor.incarca_audio(cale), dtype=np.float32)


def main(argv: list[str] | None = None) -> int:
    import argparse  # noqa: PLC0415

    ap = argparse.ArgumentParser(prog="dictare_lunga", description=__doc__.split("\n")[0])
    ap.add_argument("--wav", help="fișier audio (16 kHz mono ideal; altfel se reeșantionează)")
    ap.add_argument("--mic", action="store_true", help="captură de la microfon")
    ap.add_argument("--secunde", type=float, default=60.0, help="cât ascultă --mic")
    ap.add_argument("--asr", choices=["none", "whisper"], default="none",
                    help="none = doar VAD/ferestre (text = intervalul); whisper = motorul programului")
    ap.add_argument("--model", default=None, help="model Whisper (implicit: setările)")
    ap.add_argument("--device", default=None, help="auto / cpu / cuda (implicit: setările)")
    ap.add_argument("--vad", default=None, help="auto / ggml / onnx / energie")
    ap.add_argument("--session", default=None, help="session.jsonl de scris (implicit: nu)")
    ap.add_argument("--bloc-ms", type=int, default=100, help="mărimea blocurilor simulate de microfon")
    a = ap.parse_args(argv)
    if not a.wav and not a.mic:
        ap.error("--wav sau --mic")
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

    def emit(d: dict) -> None:
        print(json.dumps(d, ensure_ascii=False), flush=True)

    if a.asr == "whisper":
        from .motor import MotorWhisper  # noqa: PLC0415

        m = MotorWhisper()
        try:
            from . import config as _cfg  # noqa: PLC0415

            m.aplica_setari(_cfg.incarca())
        except Exception:  # noqa: BLE001 - setări ilizibile: implicitele motorului
            pass
        if a.model:
            m.model_preferat = a.model
        if a.device:
            m.dispozitiv_preferat = a.device

        def asr(audio, prior):
            opt = {"text_anterior": prior} if prior else {}
            return m.transcrie(audio, limba="ro", termeni="", progres=None, faza=None, **opt).text
    else:
        def asr(audio, _prior):
            return f"[{audio.size / SAMPLE_RATE:.2f}s]"

    strat = DictareLunga(asr, lambda c: emit({"ev": "commit", "idee": c.idee, "idee_noua": c.idee_noua,
                                               "t0": round(c.t0, 2), "t1": round(c.t1, 2), "text": c.text}),
                         vad=creeaza_vad(a.vad, log=lambda m_: emit({"ev": "warn", "msg": m_})),
                         sesiune=a.session, la_eveniment=emit, model_id=a.asr,
                         log=lambda m_: emit({"ev": "warn", "msg": m_}))
    emit({"ev": "ready", "vad": strat.stats.vad, "asr": a.asr, "session": a.session})
    t0 = time.perf_counter()
    if a.wav:
        pcm = _citeste_wav(a.wav)
        n = max(FRAME, int(SAMPLE_RATE * a.bloc_ms / 1000))
        for off in range(0, pcm.size, n):
            strat.push(pcm[off: off + n])
    else:
        from .inregistrare import Microfon  # noqa: PLC0415

        mic = Microfon()
        mic.porneste()
        try:
            while time.perf_counter() - t0 < a.secunde:
                time.sleep(0.1)
                strat.push(mic.preia())
        finally:
            strat.push(mic.opreste().pcm)
    strat.finish()
    strat.close()
    s = strat.stats
    emit({"ev": "done", "audio_s": round(s.audio_s, 2), "vad": s.vad, "vad_ms": round(s.vad_ms),
          "enunturi": s.enunturi, "idei": s.idei, "ferestre": s.ferestre, "commits": s.commits,
          "asr_ms": round(s.asr_ms), "wall_ms": round((time.perf_counter() - t0) * 1000), "text": strat.text()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
