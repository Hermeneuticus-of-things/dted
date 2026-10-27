# DTED - Parakeet (eek ro-en) productization - DESIGN ONLY

Date: 2026-10-27 (Europe/Paris). Status: **design, not shipped**. Item C of the owner-approved DTE batch.
Source facts: `C:\Users\Ionut\diskscan\DTED_PARAKEET_GPU_ALTERNATIVES_2026-10-27.md`, stress-ro run `ro_20261027_0152`
(`C:\Users\Ionut\diskscan\DTE_STRESS_RO_REPORT_ro_20261027_0152.md`), local tree `src\cpp\native\` (HpHavis).

## 0. Explicit NON-goals
- No full ship: no installer/portable rebuild here (that is A10, separate), no release, no upload.
- No git commit / push / PR here (B2 is separate, on its own branch, never on Pneuma PR #24).
- No change of model weights (`parakeet-tdt-0.6b-ro-en.q8_0.gguf`, Whisper, OpenLLM-Ro stay as they are).
- No production default that forces CUDA on every user without a setting; Whisper stays the default ASR engine
  until a decision based on data (see 6).
- No in-process CUDA load into `dted_native.exe` (DLL ABI clash, see 2).
- No DirectML / OpenCL work.
- No Rust rewrite now (sequencing: Havis OS imports the DTE voice engine only after DTE is complete + tested,
  and then rewrites it in Rust - recorded by Grok Bot in Clona-Havis docs).

## 1. Current state (verified on HpHavis)
| Piece | State |
|---|---|
| `dted_native.exe` (src\cpp\native\build) | New build: device chain CUDA host -> Vulkan (async off) -> CPU; ready JSON reports `asr_backend` + `asr_fallback`. |
| `dted_asr_cuda_host.exe` + `asr-cuda\` (~127 MB, ggml-cuda.dll ~106 MB, cuBLAS shim, MSVC runtime) | Built from prebuilt NeMo-Speech v0.2.0 windows-x86_64-cuda (sha256 verified). Deterministic == CPU text; ~10-15x faster than CPU (113 s audio: ~0.79 s vs ~11.5 s). |
| `asr-gpu\` (Vulkan) | Works only with `GGML_VK_DISABLE_ASYNC=1` (set automatically unless `DTED_ASR_VK_ASYNC=1`); then 20/20 == CPU, ~+15 % time, not faster than CPU on this box; cold shader warm-up ~6.8 s. |
| Accuracy (stress-ro, WER) | whisper-cpu 0.0433, whisper-gpu 0.0437, eek-cpu 0.0504, eek-gpu 0.0728 (eek-gpu number was taken with the OLD exe, Vulkan async race ON -> unreliable; must be re-run with backend=cuda). |
| Packaging (`dist\build_pkg_cuda.ps1`) | Copies only top-level `*.dll` + `dted_native.exe` from `src\cpp\native\build` -> **`asr-cuda\` and `asr-gpu\` subfolders are NOT packaged**. 0.6.0-cuda portable (26 Oct) predates all of this. |
| Python app | Engine choice for Parakeet lives in the native path; Python `config.dispozitiv` = auto/cpu/cuda (Whisper). No Romanian UI setting for "ASR engine" or "GPU backend" yet. |

## 2. Architecture
```
DTED UI (Qt, Python)
  -> serviciu / dted_native.exe --serviciu   (JSON lines on stdin/stdout; Silero VAD + commit + session + llama.cpp summarizer)
       -> ParakeetAsr::open(device)
            tier 1  CudaAsrHost  ->  asr-cuda\dted_asr_cuda_host.exe  (separate process, pipes)
                                      LoadLibraryEx nemo_speech_asr_c.dll from its own dir (SetDllDirectory)
                                      protocol: "OK <ms>" | "ERR <msg>"; req u32 n + f32 PCM 16 kHz; reply u32 status, u32 len, UTF-8
            tier 2  in-process ggml-Vulkan (asr-gpu\), GGML_VK_DISABLE_ASYNC=1
            tier 3  in-process CPU
```
Why out-of-process for CUDA: `dted_native` already loads llama b11890 `ggml*.dll`/`llama.dll`/`cublas64_13.dll`;
NeMo-Speech CUDA uses ggml b11151 ABI with the same DLL names. A separate process with its own DLL directory is the
only clean way without rebuilding either side (no nvcc/MSVC/admin on this machine).

Lifecycle rules (already in code, keep): host started lazily at `open`, stays warm in `--serviciu` mode
(~30 ms per 14 s window), stderr -> NUL unless `DTED_ASR_HOST_VERBOSE=1`, clean quit (0xFFFFFFFF) then
terminate in destructor, no orphan processes (verified with `--asr-gpu 7`).
To add before ship: host watchdog (if the pipe breaks mid-session -> restart once, then drop to tier 2/3 and emit
`asr_fallback` event), and a per-request timeout.

## 3. Default device chain (proposed, unchanged in code today)
`--asr-device auto|gpu` : CUDA host -> Vulkan (async disabled) -> CPU. `--asr-device cpu` : CPU only.
Override env: `DTED_ASR_GPU_BACKEND=auto|cuda|vulkan`, `DTED_ASR_VK_ASYNC=1` (debug only).
Selection rules:
1. CUDA tier only if `asr-cuda\` exists next to the exe AND host replies `OK` (driver must support CUDA 13).
2. Vulkan tier only if `asr-gpu\` exists; always with async disabled.
3. CPU is always the last tier and must always work.
4. Every fallback is reported (`asr_backend`, `asr_fallback`) and logged; the UI shows it read-only (see 5).
Engine default stays **Whisper** (best WER 0.0433). Parakeet becomes an opt-in engine until the GPU leg of
stress-ro is re-run with backend=cuda and shows WER within agreed margin of Whisper (proposal: <= Whisper + 0.005).

## 4. Packaging notes (for A10 / later release - not done here)
- Extend `dist\build_pkg_cuda.ps1` to copy `src\cpp\native\build\asr-cuda\` -> `_internal\asr-cuda\` and
  `asr-gpu\` -> `_internal\asr-gpu\` (recursive, preserve layout; host must sit next to its DLLs).
- Size: +~127 MB (CUDA) per package. Options: (a) only in the "cuda" flavour (Standard/Offline-cuda, Portable-cuda);
  (b) optional download component like the GGUF models in Bootstrap. Recommend (a) for 0.6.x, (b) later.
- Record sha256 of `nemo-speech-0.2.0-windows-x86_64-cuda.zip` and of each copied DLL in the package manifest;
  include NeMo-Speech / ggml / cuBLAS license texts (third_party notices).
- Antivirus: a second exe spawning with pipes may be flagged by HP Wolf/Sure Sense or Defender heuristics -
  sign both exes the same way as `dted_native.exe` and test a clean install on a machine with HP Wolf active.
- No admin needed at runtime; no system-wide CUDA install; relies on the NVIDIA driver only.
- Non-NVIDIA machines: `asr-cuda\` present but host returns ERR -> falls back silently (verified path).

## 5. UI / settings implications (Romanian labels, Setari -> Sunet or Expert)
Proposed config fields (all optional, defaults keep today's behaviour):
- `motor_asr: str = "whisper"`  ("whisper" | "parakeet") - label: "Motorul de recunoastere a vorbirii".
- `asr_gpu_backend: str = "auto"` ("auto" | "cuda" | "vulkan" | "cpu") - Expert only;
  label: "Placa video pentru Parakeet (Automat recomandat)". Maps to `--asr-device` / `DTED_ASR_GPU_BACKEND`.
- Read-only status line from ready JSON: "Parakeet ruleaza pe: placa NVIDIA (CUDA) / placa video (Vulkan) / procesor".
- If fallback happened: short Romanian explanation from `asr_fallback` (no raw error dump).
- `hardware.setari_recomandate` may pre-select `asr_gpu_backend="cuda"` for levels A/B/C, but only as a
  recommendation shown in Setari, never forcing `motor_asr="parakeet"`.
- Env variables keep priority over settings (same pattern as `DTED_DICTARE_LUNGA`) and the UI shows a warning
  when an env override is active (same as the A9 checkbox).
- Long dictation (`dictare_lunga`) stays engine-agnostic: ASR is pluggable; with CUDA host warm, consider shorter
  windows for lower live latency (measure first, do not change the 30 s / 7.5 s defaults blindly).

## 6. Validation plan before any ship
1. Re-run stress-ro GPU leg with new exe, backend=cuda (local, no cloud). Compare WER eek-cuda vs eek-cpu vs whisper.
2. Determinism: 20 runs smoke + x8 clip, md5 == CPU.
3. Long session: 30-60 min `--serviciu` with host warm; memory/handle leak check; kill host mid-session -> fallback works.
4. Fresh-machine install (portable + standard) with/without NVIDIA; HP Wolf/Defender active.
5. Owner live mic pass (A8 style) with Parakeet selected.

## 7. Risks
| Risk | Mitigation |
|---|---|
| NVIDIA driver too old for CUDA 13 on user PCs | Host ERR -> Vulkan/CPU fallback; show reason in UI. |
| Prebuilt NeMo-Speech binary is a third-party artifact (supply chain) | Pin version + sha256; vendor in `third_party\`; plan source build when toolchain available. |
| Package size +127 MB | CUDA flavour only / optional component. |
| Vulkan async race returns if env is cleared or ggml updated | Keep forced `GGML_VK_DISABLE_ASYNC=1`; regression test comparing md5 to CPU; report upstream. |
| AV flags host process | Code-sign, test with HP Wolf active. |
| Parakeet WER worse than Whisper on Romanian | Keep Whisper default; Parakeet opt-in until data says otherwise. |
| Two ggml versions to maintain | Host isolates them; document versions in manifest. |
| Future Rust rewrite in Havis OS | Keep the host protocol small and documented (above) so it can be reimplemented 1:1. |

## 8. Open questions (owner / later)
1. Should Parakeet ever become default on NVIDIA machines, and with what WER margin?
2. One "cuda" package flavour vs optional download component for `asr-cuda\`?
3. Upstream bug report for the ggml-Vulkan async race - allowed to post publicly? (external action, needs owner OK)
4. Code-signing certificate availability for the second exe.
5. Is a source CUDA build (nvcc/MSVC) wanted later to drop the prebuilt dependency?

## 9. Rollback
Copy `dted_native.exe.pre-vkasync-20261027` over `dted_native.exe`, or `DTED_ASR_GPU_BACKEND=vulkan`, or `--asr-device cpu`.