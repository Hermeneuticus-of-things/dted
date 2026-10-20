"""Probă de transcriere (G.18): confirmă că modelul CT2 funcționează înainte de
ștergerea fișierului orfan large-v3-turbo.pt (PyTorch, nefolosit)."""
import sys
import wave
import tempfile
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dictare_transcriere_romana import cai


def _genereaza(cale, secunde=1.5, hertz=440.0, rate=16000):
    import math, struct
    with wave.open(cale, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        cadre = bytearray()
        for i in range(int(rate * secunde)):
            val = int(0.35 * 32767 * math.sin(2 * math.pi * hertz * i / rate))
            cadre += struct.pack("<h", val)
        w.writeframes(bytes(cadre))


def principal():
    import numpy as np
    from faster_whisper import WhisperModel

    path = cai.fisier_model()
    print(f"Încarc modelul: {path.name} (CPU float32)…", flush=True)
    model = WhisperModel(str(path), device="cpu", compute_type="float32")
    # Probă ca tablou numpy mono 16 kHz (calea reală din motor.py: array → transcribe,
    # decodarea audio are deja fallback ffmpeg în _decode_audio).
    rate = 16000
    sec = 2.0
    t = np.arange(int(rate * sec), dtype=np.float32) / rate
    proba = (0.30 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    print("Transcriu proba (2 s, tablou numpy)…", flush=True)
    segmente, info = model.transcribe(proba, language="ro", beam_size=1)
    text = " ".join(s.text for s in segmente).strip()
    print(f"Limba detectată: {info.language} (prob. {info.language_probability:.2f})")
    print(f"Text: {text or '(gol, așteptat pentru un ton pur)'}")
    print("PROBA_OK")
    return 0


if __name__ == "__main__":
    sys.exit(principal())