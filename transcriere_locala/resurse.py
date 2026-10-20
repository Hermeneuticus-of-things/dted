"""Verificarea calculatorului ÎNAINTE de instalare.

Fiecare cerință are un prag scris explicit, o valoare citită de la sistem și
un verdict. Rezultatul este folosit de ecranul de verificare pentru a arăta
bife verzi / X roșii și pentru a bloca instalarea când lipsește ceva
obligatoriu.
"""

from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from . import cai
from .constante import (
    DIMENSIUNI_GB,
    DISC_MINIM_CU_GPU_GB,
    DISC_MINIM_GB,
    WINDOWS_BUILD_MINIM,
    WHISPER_MIN_RAM_GB,
    WHISPER_MIN_VRAM_MB,
    WHISPER_MIN_DRIVER,
    WHISPER_RECOMANDAT_RAM_GB,
)

Stare = Literal["ok", "atentionare", "lipsa", "optioanala"]


@dataclass
class Cerinta:
    """O linie din lista de cerințe minime."""

    cheie: str
    nume: str
    cerinta: str
    gasit: str
    stare: Stare
    obligatorie: bool = True
    detaliu: str = ""
    sfat: str = ""

    @property
    def simbol(self) -> str:
        return {"ok": "✔", "atentionare": "!", "lipsa": "✘", "optioanala": "–"}[self.stare]


@dataclass
class Raport:
    cerinte: list[Cerinta] = field(default_factory=list)
    ram_gb: float = 0.0
    disc_liber_gb: float = 0.0
    disc_necesar_gb: float = 0.0
    are_gpu: bool = False
    gpu_nume: str = ""
    gpu_vram_mb: int = 0
    gpu_driver: int = 0
    arhitectura: str = ""
    build_windows: int = 0
    versiune_windows: str = ""
    procesor: str = ""
    nuclee: int = 0

    # ------------------------------------------------------------------ verdict

    @property
    def blocante(self) -> list[Cerinta]:
        """Cerințele obligatorii care nu sunt îndeplinite."""
        return [c for c in self.cerinte if c.obligatorie and c.stare == "lipsa"]

    @property
    def poate_instala(self) -> bool:
        return not self.blocante

    @property
    def doar_gpu_lipsa(self) -> bool:
        """Adevărat când singura problemă este lipsa accelerării video."""
        return not self.blocante and not self.are_gpu

    def rezumat(self) -> str:
        if not self.poate_instala:
            return f"{len(self.blocante)} cerințe obligatorii nu sunt îndeplinite."
        if not self.are_gpu:
            return "Calculatorul poate rula programul, dar fără accelerare video."
        return "Calculatorul îndeplinește toate cerințele."


# --------------------------------------------------------------------------- citiri sistem


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def memorie_ram_gb() -> float:
    """Memoria RAM totală, în GB (0 dacă nu poate fi citită)."""
    if cai.este_windows():
        try:
            status = _MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.ullTotalPhys / 1024**3
        except Exception:
            pass
    try:
        import os as _os

        if hasattr(_os, "sysconf"):
            return _os.sysconf("SC_PAGE_SIZE") * _os.sysconf("SC_PHYS_PAGES") / 1024**3
    except Exception:
        pass
    return 0.0


def spatiu_liber_gb(cale: Path) -> float:
    """Spațiul liber pe discul care conține calea dată."""
    sonda = Path(cale)
    while not sonda.exists() and sonda != sonda.parent:
        sonda = sonda.parent
    try:
        return shutil.disk_usage(sonda).free / 1024**3
    except OSError:
        return 0.0


def _executa(comanda: list[str], timeout: int = 8) -> str:
    """Rulează o comandă și întoarce ieșirea; gol dacă nu se poate."""
    try:
        rezultat = subprocess.run(
            comanda,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (rezultat.stdout or "") + (rezultat.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return ""


def _detecteaza_gpu_nvidia() -> tuple[str, int, int]:
    """Întoarce (nume, VRAM în MB, versiune driver) pentru primul GPU NVIDIA."""
    iesire = _executa(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    for linie in iesire.splitlines():
        parti = [p.strip() for p in linie.split(",")]
        if len(parti) >= 3 and parti[1].isdigit():
            try:
                driver = int(re.match(r"\d+", parti[2]).group()) if parti[2] else 0
            except (AttributeError, ValueError):
                driver = 0
            return parti[0], int(parti[1]), driver
    return "", 0, 0


def _placi_video() -> list[str]:
    """Numele plăcilor video raportate de Windows (fără a cere drepturi)."""
    iesire = _executa(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-CimInstance Win32_VideoController).Name",
        ],
        timeout=15,
    )
    return [linie.strip() for linie in iesire.splitlines() if linie.strip()]


def _versiune_windows() -> tuple[int, str]:
    """(build, text prietenos) pentru Windows."""
    build = 0
    text = "Windows"
    if cai.este_windows():
        try:
            info = sys.getwindowsversion()
            build = int(getattr(info, "build", 0))
            major, minor = info.major, info.minor
            if major >= 10:
                text = "Windows 11" if build >= 22000 else "Windows 10"
                text += f" (build {build})"
            elif (major, minor) == (6, 3):
                text = f"Windows 8.1 (build {build})"
            elif (major, minor) == (6, 2):
                text = f"Windows 8 (build {build})"
            elif (major, minor) == (6, 1):
                text = f"Windows 7 (build {build})"
            else:
                text = f"Windows {major}.{minor} (build {build})"
        except Exception:
            pass
    else:
        build = 0
        text = platform.platform()
    return build, text


def _nume_procesor() -> str:
    nume = os.environ.get("PROCESSOR_IDENTIFIER", "") or platform.processor() or ""
    return nume.strip() or "Procesor necunoscut"


# --------------------------------------------------------------------------- construirea raportului


def verifica(director: Path | None = None) -> Raport:
    """Verifică toate cerințele și întoarce un raport complet."""
    raport = Raport()
    raport.arhitectura = cai.arhitectura()
    raport.build_windows, raport.versiune_windows = _versiune_windows()
    raport.ram_gb = memorie_ram_gb()
    raport.procesor = _nume_procesor()
    raport.nuclee = os.cpu_count() or 1

    tinta = director or cai.director_instalare()
    raport.disc_liber_gb = spatiu_liber_gb(tinta)

    nume_gpu, vram, driver = _detecteaza_gpu_nvidia()
    raport.gpu_nume, raport.gpu_vram_mb, raport.gpu_driver = nume_gpu, vram, driver
    raport.are_gpu = bool(nume_gpu) and vram >= WHISPER_MIN_VRAM_MB and driver >= WHISPER_MIN_DRIVER

    # Spațiul necesar depinde de prezența unei plăci video compatibile.
    raport.disc_necesar_gb = DISC_MINIM_CU_GPU_GB if raport.are_gpu else DISC_MINIM_GB

    c = raport.cerinte

    # --- 1. Sistem de operare -------------------------------------------------
    if not cai.este_windows():
        c.append(
            Cerinta(
                "os",
                "Sistem de operare",
                "Windows 10 (1809) sau Windows 11, pe 64 de biți",
                platform.platform(),
                "lipsa",
                detaliu="Programul folosește componente Windows (microfon, WordCraft, instalare fără administrator).",
                sfat="Rulează programul pe un calculator cu Windows 10 sau Windows 11 pe 64 de biți.",
            )
        )
    elif raport.build_windows >= WINDOWS_BUILD_MINIM:
        c.append(
            Cerinta(
                "os",
                "Sistem de operare",
                "Windows 10 (1809) sau Windows 11, pe 64 de biți",
                raport.versiune_windows,
                "ok",
            )
        )
    else:
        c.append(
            Cerinta(
                "os",
                "Sistem de operare",
                "Windows 10 (1809) sau Windows 11, pe 64 de biți",
                raport.versiune_windows,
                "lipsa",
                detaliu="Versiunea de Windows este prea veche pentru bibliotecile de transcriere.",
                sfat="Actualizează Windows la versiunea 10 (1809) sau mai nouă, ori folosește alt calculator.",
            )
        )

    # --- 2. Procesor ----------------------------------------------------------
    if raport.arhitectura == "ARM64":
        c.append(
            Cerinta(
                "cpu",
                "Procesor",
                "Intel sau AMD pe 64 de biți (x64)",
                f"{raport.procesor} · ARM64",
                "lipsa",
                detaliu=(
                    "Procesoarele ARM (Snapdragon) nu au versiune Windows a bibliotecii "
                    "PyTorch de care depinde Whisper, deci transcrierea nu poate rula local."
                ),
                sfat=(
                    "Folosește un calculator cu procesor Intel sau AMD pe 64 de biți. "
                    "WordCraft singur ar funcționa pe ARM, dar transcrierea nu."
                ),
            )
        )
    elif raport.arhitectura == "x86":
        c.append(
            Cerinta(
                "cpu",
                "Procesor",
                "Intel sau AMD pe 64 de biți (x64)",
                f"{raport.procesor} · 32 de biți",
                "lipsa",
                detaliu="Un Windows pe 32 de biți nu poate folosi modelele Whisper mari (au nevoie de peste 4 GB de memorie).",
                sfat="Instalează Windows pe 64 de biți sau folosește alt calculator.",
            )
        )
    else:
        c.append(
            Cerinta(
                "cpu",
                "Procesor",
                "Intel sau AMD pe 64 de biți (x64)",
                f"{raport.procesor} · {raport.nuclee} nuclee",
                "ok",
            )
        )

    # --- 3. Memorie RAM -------------------------------------------------------
    ram = raport.ram_gb
    if ram <= 0:
        c.append(
            Cerinta(
                "ram",
                "Memorie RAM",
                f"minimum {WHISPER_MIN_RAM_GB:.0f} GB (recomandat {WHISPER_RECOMANDAT_RAM_GB:.0f} GB)",
                "nu am putut citi memoria",
                "atentionare",
                detaliu="Verificarea nu a putut citi memoria instalată; instalarea poate continua.",
                sfat="Dacă programul merge greu, închide alte programe sau folosește un calculator cu mai multă memorie.",
            )
        )
    elif ram < WHISPER_MIN_RAM_GB:
        c.append(
            Cerinta(
                "ram",
                "Memorie RAM",
                f"minimum {WHISPER_MIN_RAM_GB:.0f} GB (recomandat {WHISPER_RECOMANDAT_RAM_GB:.0f} GB)",
                f"{ram:.1f} GB",
                "lipsa",
                detaliu="Modelul Whisper large-v3-turbo are nevoie de circa 4–6 GB doar pentru el.",
                sfat=(
                    f"Mai ai nevoie de {WHISPER_MIN_RAM_GB - ram:.1f} GB de memorie. "
                    "Închide programele care consumă mult sau folosește un calculator cu mai multă RAM."
                ),
            )
        )
    elif ram < WHISPER_RECOMANDAT_RAM_GB:
        c.append(
            Cerinta(
                "ram",
                "Memorie RAM",
                f"minimum {WHISPER_MIN_RAM_GB:.0f} GB (recomandat {WHISPER_RECOMANDAT_RAM_GB:.0f} GB)",
                f"{ram:.1f} GB",
                "atentionare",
                detaliu="Suficient pentru transcriere, dar închide alte programe mari în timpul folosirii.",
                sfat="Funcționează, însă este recomandat să închizi browserul sau alte programe grele.",
            )
        )
    else:
        c.append(
            Cerinta(
                "ram",
                "Memorie RAM",
                f"minimum {WHISPER_MIN_RAM_GB:.0f} GB (recomandat {WHISPER_RECOMANDAT_RAM_GB:.0f} GB)",
                f"{ram:.1f} GB",
                "ok",
            )
        )

    # --- 4. Spațiu pe disc ----------------------------------------------------
    necesar = raport.disc_necesar_gb
    detalii_spatiu = (
        f"model {DIMENSIUNI_GB['model']:.1f} GB + WordCraft {DIMENSIUNI_GB['wordcraft']:.1f} GB + "
        f"program și biblioteci {DIMENSIUNI_GB['program_gpu' if raport.are_gpu else 'program']:.1f} GB + "
        f"rezervă {DIMENSIUNI_GB['rezerva']:.1f} GB"
    )
    if raport.disc_liber_gb >= necesar:
        c.append(
            Cerinta(
                "disc",
                "Spațiu liber pe disc",
                f"minimum {necesar:.0f} GB pe discul programului",
                f"{raport.disc_liber_gb:.1f} GB liberi",
                "ok",
                detaliu=detalii_spatiu,
            )
        )
    else:
        lipsa = necesar - raport.disc_liber_gb
        c.append(
            Cerinta(
                "disc",
                "Spațiu liber pe disc",
                f"minimum {necesar:.0f} GB pe discul programului",
                f"{raport.disc_liber_gb:.1f} GB liberi",
                "lipsa",
                detaliu=detalii_spatiu,
                sfat=(
                    f"Ai nevoie de încă {lipsa:.1f} GB liberi pe disc. "
                    "Șterge fișiere de care nu ai nevoie, apoi apasă «Verifică din nou»."
                ),
            )
        )

    # --- 5. Placă video (opțională) ------------------------------------------
    if raport.are_gpu:
        c.append(
            Cerinta(
                "gpu",
                "Placă video (opțională)",
                f"NVIDIA cu minimum {WHISPER_MIN_VRAM_MB // 1024} GB memorie și driver {WHISPER_MIN_DRIVER}+",
                f"{raport.gpu_nume} · {vram} MB · driver {driver}",
                "ok",
                obligatorie=False,
                detaliu="Transcrierea va fi accelerată de placa video.",
            )
        )
    else:
        placi = _placi_video()
        gasit = ", ".join(placi[:2]) if placi else "nu am găsit o placă video NVIDIA compatibilă"
        motiv = ""
        if nume_gpu and vram < WHISPER_MIN_VRAM_MB:
            motiv = f"Placa are {vram} MB memorie, sub minimul de {WHISPER_MIN_VRAM_MB} MB."
        elif nume_gpu and driver < WHISPER_MIN_DRIVER:
            motiv = f"Driverul video este versiunea {driver}, sub minimul {WHISPER_MIN_DRIVER}."
        elif not nume_gpu:
            motiv = "Nu am găsit o placă video NVIDIA cu drivere instalate."
        c.append(
            Cerinta(
                "gpu",
                "Placă video (opțională)",
                f"NVIDIA cu minimum {WHISPER_MIN_VRAM_MB // 1024} GB memorie și driver {WHISPER_MIN_DRIVER}+",
                gasit,
                "optioanala",
                obligatorie=False,
                detaliu=motiv,
                sfat="Fără placă video, transcrierea rulează pe procesor: mai încet, dar funcționează.",
            )
        )

    # --- 6. Microfon (opțional, doar pentru dictare) -------------------------
    microfon = _are_microfon()
    c.append(
        Cerinta(
            "microfon",
            "Microfon (opțional, pentru dictare)",
            "orice microfon recunoscut de Windows",
            microfon,
            "ok" if microfon != "niciun microfon găsit" else "optioanala",
            obligatorie=False,
            detaliu="" if microfon != "niciun microfon găsit" else "Poți transcrie fișiere audio și fără microfon.",
        )
    )
    return raport


def _are_microfon() -> str:
    """Numele primului microfon, dacă există."""
    try:
        import sounddevice as sd  # doar dacă e deja instalat

        for dispozitiv in sd.query_devices():
            if dispozitiv.get("max_input_channels", 0) > 0:
                return str(dispozitiv.get("name", "microfon"))[:60]
    except Exception:
        pass
    return "se verifică la prima folosire"


def estimare_viteza(raport: Raport, minute_audio: float = 10.0) -> str:
    """Estimare prietenoasă a duratei transcrierii."""
    if raport.are_gpu:
        return (
            f"Cu placa video, {minute_audio:.0f} minute de audio se transcriu în "
            f"circa {max(1, round(minute_audio * 60 / 12 / 60)):d}–{max(2, round(minute_audio * 60 / 6 / 60)):d} minute."
        )
    factor_min, factor_max = 1.5, 4.0  # minute de calcul pentru un minut de audio
    return (
        f"Fără placă video, {minute_audio:.0f} minute de audio se transcriu în "
        f"circa {round(minute_audio * factor_min):d}–{round(minute_audio * factor_max):d} minute, "
        "în funcție de procesor."
    )


def text_pentru_consola(raport: Raport) -> str:
    """Afișare simplă în linia de comandă."""
    linii = ["", "Cerințe minime și ce are acest calculator:", ""]
    for cerinta in raport.cerinte:
        linii.append(f"  {cerinta.simbol} {cerinta.nume}: {cerinta.cerinta}")
        linii.append(f"      găsit: {cerinta.gasit}")
        if cerinta.detaliu:
            linii.append(f"      {cerinta.detaliu}")
        if cerinta.stare == "lipsa" and cerinta.sfat:
            linii.append(f"      → {cerinta.sfat}")
    linii.append("")
    linii.append(f"Rezultat: {raport.rezumat()}")
    return "\n".join(linii)
