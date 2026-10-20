"""Valori fixe ale programului: linkuri oficiale, sume de control și praguri.

Toate pragurile de resurse sunt derivate din cerințele modelului
Whisper large-v3-turbo (809 M parametri, checkpoint de ~1,6 GB) și din
spațiul necesar pentru Python, biblioteci, ffmpeg și WordCraft.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- aplicație

NUME_APLICATIE = "Transcriere locală"
VERSIUNE = "1.0.0"

# --------------------------------------------------------------------------- Whisper

WHISPER_NUME = "large-v3-turbo"

# Suma SHA-256 este chiar numele folderului din linkul oficial OpenAI.
# Link: https://openaipublic.azureedge.net/main/whisper/models/<SHA>/large-v3-turbo.pt
WHISPER_SHA256 = "aff26ae408abcba5fbf8813c21e62b0941638c5f6eebfb145be0c9839262a19a"
WHISPER_URL = (
    "https://openaipublic.azureedge.net/main/whisper/models/"
    f"{WHISPER_SHA256}/{WHISPER_NUME}.pt"
)
WHISPER_BYTES = 1_617_941_637  # dimensiunea oficială a fișierului
WHISPER_MIN_RAM_GB = 8.0       # sub această valoare modelul nu încape în memorie
WHISPER_RECOMANDAT_RAM_GB = 16.0
WHISPER_MIN_VRAM_MB = 6000     # fp16 pe GPU are nevoie de ~6 GB
WHISPER_MIN_DRIVER = 525       # driver NVIDIA minim pentru PyTorch cu CUDA 12.4

# --------------------------------------------------------------------------- WordCraft

WORDCRAFT_VERSIUNE = "0.8.0"
WORDCRAFT_RELEASE = (
    "https://github.com/storytold/wordcraft/releases/download/"
    f"v{WORDCRAFT_VERSIUNE}"
)
WORDCRAFT_SUME_URL = f"{WORDCRAFT_RELEASE}/SHA256SUMS.txt"

# Numele fișierelor din pagina oficială de release, pe arhitecturi.
WORDCRAFT_MSI = {
    "AMD64": f"wordcraft-{WORDCRAFT_VERSIUNE}-windows-x64.msi",
    "ARM64": f"wordcraft-{WORDCRAFT_VERSIUNE}-windows-arm64.msi",
    "x86": f"wordcraft-{WORDCRAFT_VERSIUNE}-windows-x86.msi",
}
WORDCRAFT_PORTABIL = {
    "AMD64": f"wordcraft-{WORDCRAFT_VERSIUNE}-windows-x64-portable.zip",
    "ARM64": f"wordcraft-{WORDCRAFT_VERSIUNE}-windows-arm64-portable.zip",
    "x86": f"wordcraft-{WORDCRAFT_VERSIUNE}-windows-x86-portable.zip",
}

# --------------------------------------------------------------------------- resurse

WINDOWS_BUILD_MINIM = 17763          # Windows 10 versiunea 1809
DISC_REZERVA_GB = 2.0                # rezervă pentru fișiere temporare
DISC_MINIM_GB = 6.0                  # calculat mai jos, rotunjit în sus
DISC_MINIM_CU_GPU_GB = 8.0

# Componente descărcate/instalate, folosite la explicarea spațiului necesar.
DIMENSIUNI_GB = {
    "model": WHISPER_BYTES / 1024**3,   # ~1,51 GiB
    "wordcraft": 0.30,                  # MSI + instalare
    "program": 1.30,                    # mediu Python + biblioteci (CPU)
    "program_gpu": 3.20,                # biblioteci CUDA
    "ffmpeg": 0.12,
    "rezerva": DISC_REZERVA_GB,
}

# --------------------------------------------------------------------------- limbi

# Perechi (etichetă în română, cod ISO 639-1 pentru Whisper).
LIMBI = [
    ("Română", "ro"),
    ("Engleză", "en"),
    ("Franceză", "fr"),
    ("Germană", "de"),
    ("Italiană", "it"),
    ("Spaniolă", "es"),
    ("Portugheză", "pt"),
    ("Olandeză", "nl"),
    ("Poloneză", "pl"),
    ("Rusă", "ru"),
    ("Ucraineană", "uk"),
    ("Turcă", "tr"),
    ("Maghiară", "hu"),
    ("Bulgară", "bg"),
    ("Greacă", "el"),
    ("Automat (detectează limba)", "auto"),
]

# Prompt care ajută modelul să scrie diacriticele românești corect.
PROMPT_ROMANA = (
    "Aceasta este o transcriere în limba română, cu diacritice corecte: "
    "ă, â, î, ș, ț."
)

# --------------------------------------------------------------------------- diverse

FORMATE_AUDIO = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus", ".webm", ".mp4", ".aac", ".wma")

# Versiunea de Python folosită la instalare (torch/numba nu au încă wheels pentru 3.13).
PYTHON_VERSIUNE = "3.12.10"
PYTHON_URL = {
    "AMD64": f"https://www.python.org/ftp/python/{PYTHON_VERSIUNE}/python-{PYTHON_VERSIUNE}-amd64.exe",
    "ARM64": f"https://www.python.org/ftp/python/{PYTHON_VERSIUNE}/python-{PYTHON_VERSIUNE}-arm64.exe",
}

# Indexurile oficiale PyTorch.
TORCH_INDEX_CPU = "https://download.pytorch.org/whl/cpu"
TORCH_INDEX_CUDA = "https://download.pytorch.org/whl/cu124"

# Pachetele aplicației (instalate în mediul propriu, nu în Python-ul sistemului).
PACHETE = [
    "numpy<3",
    "sounddevice>=0.4.6",
    "imageio-ffmpeg>=0.4.9",
]
PACHET_WHISPER = "openai-whisper==20250625"  # versiunea verificată
