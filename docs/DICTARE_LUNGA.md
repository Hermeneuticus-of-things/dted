# Dictarea lungă (long_dictation_layer)

Modul: `dictare_transcriere_romana/dictare_lunga.py`. **Oprită implicit**; dictarea clasică
(bucăți fixe de `expert_fereastra_sec`) rămâne neschimbată.

## Flux (identic cu `dted_native.exe`)
microfon 16 kHz → cadre 512 (32 ms) → **Silero VAD** (prag `expert_vad_prag`, pre-roll 250 ms,
hangover 600 ms) → enunț → **ferestre max 30 s, suprapunere 7,5 s** → ASR (motorul existent:
Whisper pe CPU/GPU, neschimbat) → **CommitEngine (LCP pe suprapunere)** → text stabil →
editor / `session.jsonl`. O pauză ≥ `dictare_lunga_pauza_idee_sec` (2 s) = **idee nouă** = paragraf nou.

VAD: `ggml` (libdted_silero.dll + models/vad/silero-vad.gguf, din cpp/native/build) →
`onnx` (silero_vad_v6.onnx din faster-whisper) → `energie` (stub). `DTED_VAD_BACKEND` / `dictare_lunga_vad`.
Căi: `DTED_SILERO_DLL`, `DTED_VAD_MODEL`, `DTED_MODELS_DIR`.

## Pornire
* setări (JSON): `"dictare_lunga": true` (opțional `dictare_lunga_vad`, `dictare_lunga_pauza_idee_sec`,
  `dictare_lunga_fereastra_sec`, `dictare_lunga_suprapunere_sec`);
* sau mediu: `DTED_DICTARE_LUNGA=1` (are prioritate; `=0` forțează oprit);
* serviciu: `{"cmd":"dictare_start","id":"d1","lunga":true,"vad":"auto"}` → `fragment` (+`idee`,
  `idee_noua`) și evenimente `idee`.

## Smoke (fără microfon)
```
cd C:\Users\Ionut\dted-build\src
..\venv\Scripts\python.exe -m dictare_transcriere_romana.dictare_lunga --wav cpp\parakeet\ro_smoke_x8_16k.wav --asr none --vad ggml
..\venv\Scripts\python.exe -m dictare_transcriere_romana.dictare_lunga --wav ..\ld_gaps_16k.wav --asr whisper --device cpu --session ..\ld.jsonl
..\venv\Scripts\python.exe -m dictare_transcriere_romana.dictare_lunga --mic --secunde 60 --asr whisper
..\venv\Scripts\python.exe -m pytest teste\test_dictare_lunga.py -q
```
