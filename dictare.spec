# -*- mode: python ; coding: utf-8 -*-
# PyInstaller, mod folder (onedir): dist\DTED\DTED.exe + _internal\
# Dictate & Transcription Express Digital (D&TED) – Dictare și transcriere în limba română
#
# În pachet: Python, PySide6, faster-whisper, ctranslate2, PyAV, numpy, sounddevice
# și ffmpeg (imageio-ffmpeg). Sunt incluse și torch (2.14.1+cpu), openai-whisper
# (20250625) și customtkinter (6.0.0) — kit offline complet (cerința 9 / N-7 V1).
# Modelul (~1,6 GB) și bibliotecile CUDA (cuBLAS 12 + cuDNN 9, ~1,9 GB) sunt
# ÎMPACHETATE în kitul offline: programul le folosește local, fără nicio descărcare
# la prima pornire (cai.fisier_model() și motor.foldere_biblioteci_cuda() le găsesc
# în bundle, în sys._MEIPASS).

import os
import sysconfig

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

# Căi către datele de împachetat (kit offline complet, cerința 9 / N-7 V1).
_SITE = sysconfig.get_paths()["purelib"]  # .venv/Lib/site-packages
_LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
# v0.1.2: kitul poartă modelul STANDARD (cel mai bun pe text lung de carte,
# măsurat WER 15% vs 37% pentru fine-tunatul RO); dacă lipsește pe disc,
# se împachetează fine-tunatul românesc.
_MODELE_KIT = [
    ("large-v3-turbo-ct2", "large-v3-turbo-ct2"),
    ("large-v3-turbo-ro-ct2", "large-v3-turbo-ro-ct2"),
]

datas = [('dictare_transcriere_romana/iconita_dictare.ico', 'dictare_transcriere_romana')]
datas += collect_data_files('faster_whisper')      # filtrul VAD (silero, .onnx)
datas += collect_data_files('imageio_ffmpeg')      # ffmpeg.exe inclus
datas += collect_data_files('customtkinter')       # temele (JSON)
datas += collect_data_files('tiktoken')            # fișierele BPE pentru openai-whisper

# Modelul de transcriere (~1,6 GB) împachetat lângă program: cai.fisier_model()
# îl citește din bundle când programul e construit, deci fără descărcare la pornire.
for _folder_model, _destinatie_model in _MODELE_KIT:
    _radacina_model = os.path.join(_LOCALAPPDATA, "Dictare&Transcriere Română", "model", _folder_model)
    _gasite = 0
    for _fisier_model in ("config.json", "preprocessor_config.json", "tokenizer.json",
                          "vocabulary.json", "model.bin"):
        _cale_model = os.path.join(_radacina_model, _fisier_model)
        if os.path.isfile(_cale_model):
            datas += [(_cale_model, "model/" + _destinatie_model)]
            _gasite += 1
    if _gasite:
        break

# Bibliotecile CUDA (cuBLAS 12 + cuDNN 9), doar folderul bin, exact cum le caută
# motor.foldere_biblioteci_cuda() în bundle (sys._MEIPASS/nvidia/*/bin).
for _pachet_cuda in ("cublas", "cudnn"):
    _bin_cuda = os.path.join(_SITE, "nvidia", _pachet_cuda, "bin")
    if os.path.isdir(_bin_cuda):
        datas += [(_bin_cuda, os.path.join("nvidia", _pachet_cuda, "bin"))]

binaries = []
binaries += collect_dynamic_libs('ctranslate2')
binaries += collect_dynamic_libs('sounddevice')    # PortAudio
binaries += collect_dynamic_libs('_sounddevice_data')

a = Analysis(
    ['pornire.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'faster_whisper', 'ctranslate2', 'av', 'sounddevice', 'numpy', 'imageio_ffmpeg',
        'onnxruntime', 'tokenizers', 'huggingface_hub',
        'dictare_transcriere_romana.pregatire',
        'torch',          # kit offline complet: pachetele cerute, chiar dacă programul
        'whisper',        # folosește faster-whisper; incluse pentru reproducere exactă
        'customtkinter',
    ] + collect_submodules('whisper') + collect_submodules('customtkinter'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'tkinter.ttk', 'tkinter.font',
        'PyQt5', 'PyQt6', 'matplotlib', 'scipy', 'pandas',
        # 'nvidia' nu mai e exclus: bibliotecile CUDA sunt împachetate în kitul offline.
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,      # onedir: bibliotecile merg în COLLECT, nu în exe
    name='DTED',                # fără „&” în numele fișierului
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='dictare_transcriere_romana/iconita_dictare.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='DTED',
)
