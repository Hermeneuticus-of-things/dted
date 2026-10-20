"""Verificarea calculatorului ÎNAINTE de instalare.

Fiecare cerință are un prag scris explicit, o valoare citită de la sistem și
un verdict. Rezultatul este folosit de ecranul de verificare pentru a arăta
bife verzi / X roșii și pentru a bloca instalarea când lipsește ceva
obligatoriu.

Nimic nu este presupus despre calculator: totul se citește de la Windows
(memorie, disc, procesor, placă video, microfon).
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
    DISC_RECOMANDAT_GB,
    WINDOWS_BUILD_MINIM,
    WHISPER_MIN_RAM_GB,
    WHISPER_MIN_VRAM_GB,
    WHISPER_MIN_VRAM_MB,
    WHISPER_RECOMANDAT_RAM_GB,
)

Stare = Literal["ok", "atentionare", "lipsa", "optioanala"]

FLAG_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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
        """Pictograma afișată lângă cerință (nu doar culoarea spune starea)."""
        return {"ok": "✔", "atentionare": "!", "lipsa": "✘", "optioanala": "–"}[self.stare]

    @property
    def cuvant(self) -> str:
        """Cuvântul care însoțește pictograma."""
        return {
            "ok": "Merge",
            "atentionare": "Atenție",
            "lipsa": "Lipsește",
            "optioanala": "Opțional",
        }[self.stare]


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
    are_microfon: bool = False
    microfon_stare: str = ""

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
        if hasattr(os, "sysconf"):
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
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
            creationflags=FLAG_NO_WINDOW,
        )
        return (rezultat.stdout or "") + (rezultat.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return ""


def _detecteaza_gpu_compatibil() -> tuple[str, int, int]:
    """Întoarce datele NVIDIA raportate de nvidia-smi; accelerarea folosește CUDA."""
    # Încearcă NVIDIA (CUDA)
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
    # Pentru alte plăci, WMI poate furniza doar numele; nu presupunem că Whisper le poate accelera.
    iesire = _executa(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-CimInstance Win32_VideoController -Filter 'AdapterCompatibility LIKE \"%AMD%\" OR AdapterCompatibility LIKE \"%Intel%\" OR AdapterCompatibility LIKE \"%NVIDIA%\"').Name",
        ],
        timeout=15,
    )
    for linie in iesire.splitlines():
        if linie.strip():
            return linie.strip(), 0, 0
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


def _stare_microfon() -> tuple[bool, str]:
    """(există microfon?, text pentru utilizator).

    Verificarea se face cu biblioteca de sunet, dacă este instalată. Înainte de
    instalare ea încă nu există: atunci spunem clar că microfonul se verifică
    la prima pornire, în loc să lăsăm impresia că nu există.
    """
    try:
        import sounddevice as sd  # type: ignore[import-not-found]
    except Exception:
        return False, "se verifică după instalare, la prima pornire"
    try:
        for dispozitiv in sd.query_devices():
            if int(dispozitiv.get("max_input_channels", 0) or 0) > 0:
                nume = str(dispozitiv.get("name", "")).strip()
                return True, nume[:70] or "microfon găsit"
    except Exception:
        return False, "nu am putut citi lista de dispozitive"
    return False, "niciun microfon găsit"


# --------------------------------------------------------------------------- raport


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

    nume_gpu, vram, driver = _detecteaza_gpu_compatibil()
    raport.gpu_nume, raport.gpu_vram_mb, raport.gpu_driver = nume_gpu, vram, driver
    raport.are_gpu = (
        bool(nume_gpu) and vram >= WHISPER_MIN_VRAM_MB
    )

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
                detaliu="Programul folosește componente Windows (microfon, instalare fără administrator).",
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
                    "Pe procesoarele ARM (Snapdragon) nu există versiunea Windows a "
                    "bibliotecii PyTorch de care depinde Whisper, deci transcrierea nu "
                    "poate rula local. LibreOffice, în schimb, are versiune pentru ARM "
                    "și ar funcționa pe acest calculator."
                ),
                sfat=(
                    "Folosește un calculator cu procesor Intel sau AMD pe 64 de biți. "
                    "Pe acest calculator poți instala LibreOffice separat, dar nu și "
                    "programul de transcriere."
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
                detaliu=(
                    "Pe un Windows pe 32 de biți nu pot rula nici Python pe 64 de biți, "
                    "nici PyTorch, nici modelul Whisper mare (are nevoie de peste 4 GB "
                    "de memorie pentru un singur program)."
                ),
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
    prag = f"minimum {WHISPER_MIN_RAM_GB:.0f} GB (recomandat {WHISPER_RECOMANDAT_RAM_GB:.0f} GB)"
    if ram <= 0:
        c.append(
            Cerinta(
                "ram",
                "Memorie RAM",
                prag,
                "nu am putut citi memoria",
                "atentionare",
                detaliu="Verificarea nu a putut citi memoria instalată; instalarea poate continua.",
                sfat=(
                    "Dacă programul merge greu, închide alte programe sau folosește un "
                    "calculator cu mai multă memorie."
                ),
            )
        )
    elif ram < WHISPER_MIN_RAM_GB:
        c.append(
            Cerinta(
                "ram",
                "Memorie RAM",
                prag,
                f"{ram:.1f} GB",
                "lipsa",
                detaliu="Modelul Whisper large-v3-turbo are nevoie de circa 4–6 GB doar pentru el.",
                sfat=(
                    f"Mai ai nevoie de {WHISPER_MIN_RAM_GB - ram:.1f} GB de memorie. "
                    "Închide programele care consumă mult sau folosește un calculator cu "
                    "mai multă RAM."
                ),
            )
        )
    elif ram < WHISPER_RECOMANDAT_RAM_GB:
        c.append(
            Cerinta(
                "ram",
                "Memorie RAM",
                prag,
                f"{ram:.1f} GB",
                "atentionare",
                detaliu="Suficient pentru transcriere, dar închide alte programe mari în timpul folosirii.",
                sfat="Funcționează, însă este recomandat să închizi browserul sau alte programe grele.",
            )
        )
    else:
        c.append(Cerinta("ram", "Memorie RAM", prag, f"{ram:.1f} GB", "ok"))

    # --- 4. Spațiu pe disc (include și LibreOffice) ---------------------------
    necesar = raport.disc_necesar_gb
    detalii_spatiu = (
        f"modelul de transcriere {DIMENSIUNI_GB['model']:.1f} GB + "
        f"LibreOffice {DIMENSIUNI_GB['libreoffice']:.1f} GB + "
        f"Python și biblioteci "
        f"{DIMENSIUNI_GB['program_gpu' if raport.are_gpu else 'program']:.1f} GB + "
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
    cerinta_gpu = (
        f"placă video NVIDIA cu minimum {WHISPER_MIN_VRAM_GB} GB VRAM (opțională)"
    )
    if raport.are_gpu:
        c.append(
            Cerinta(
                "gpu",
                "Placă video (opțională)",
                cerinta_gpu,
                f"{raport.gpu_nume} · {vram} MB",
                "ok",
                obligatorie=False,
                detaliu=(
                    "Placa NVIDIA îndeplinește cerințele pentru CUDA. Programul verifică "
                    "biblioteca video la instalare; dacă nu este disponibilă, transcrierea "
                    "continuă pe procesor."
                ),
            )
        )
    else:
        placi = _placi_video()
        gasit = ", ".join(placi[:2]) if placi else "nu am găsit o placă video compatibilă"
        motiv = ""
        if nume_gpu and vram < WHISPER_MIN_VRAM_MB:
            motiv = f"Placa are {vram} MB memorie, sub minimul de {WHISPER_MIN_VRAM_MB} MB."
        elif not nume_gpu:
            motiv = "Nu am găsit o placă NVIDIA compatibilă cu CUDA și cu drivere instalate."
        c.append(
            Cerinta(
                "gpu",
                "Placă video (opțională)",
                cerinta_gpu,
                gasit,
                "optioanala",
                obligatorie=False,
                detaliu=motiv,
                sfat="Fără placă video, transcrierea rulează pe procesor: mai încet, dar funcționează.",
            )
        )

    # --- 6. Microfon (opțional, doar pentru dictare) -------------------------
    raport.are_microfon, raport.microfon_stare = _stare_microfon()
    c.append(
        Cerinta(
            "microfon",
            "Microfon (opțional, pentru dictare)",
            "orice microfon recunoscut de Windows",
            raport.microfon_stare,
            "ok" if raport.are_microfon else "optioanala",
            obligatorie=False,
            detaliu="" if raport.are_microfon else "Poți transcrie fișiere audio și fără microfon.",
        )
    )

    # --- 7. LibreOffice (opțional; se instalează oricum la instalare) --------
    try:
        from . import libreoffice

        stare = libreoffice.stare()
    except Exception:
        stare = None
    if stare is not None and stare.gasit:
        are_ro = stare.are_meniu_romana and stare.are_dictionar_romana
        c.append(
            Cerinta(
                "libreoffice",
                "LibreOffice (programul de scris)",
                "versiunea actuală, cu meniurile și dicționarul în română",
                f"{stare.versiune or 'instalat'}"
                + ("" if are_ro else " · lipsește româna"),
                "ok" if are_ro else "atentionare",
                obligatorie=False,
                detaliu=(
                    "LibreOffice este deja instalat și este folosit așa cum e."
                    if are_ro
                    else "Există LibreOffice, dar îi lipsesc componentele în română; "
                    "le adaug la instalare."
                ),
            )
        )
    else:
        c.append(
            Cerinta(
                "libreoffice",
                "LibreOffice (programul de scris)",
                "versiunea actuală, cu meniurile și dicționarul în română",
                "nu este instalat încă",
                "optioanala",
                obligatorie=False,
                detaliu="Se descarcă și se instalează automat, în română, la instalare.",
            )
        )
    return raport


# --------------------------------------------------------------------------- tabel public


@dataclass
class RandTabel:
    """Un rând din fereastra „Ce calculator îți trebuie”."""

    nume: str
    minim: str
    recomandat: str
    gasit: str
    stare: Stare
    explicatie: str = ""        # termenii, pe înțelesul tuturor

    @property
    def simbol(self) -> str:
        return {"ok": "✔", "atentionare": "!", "lipsa": "✘", "optioanala": "–"}[self.stare]

    @property
    def cuvant(self) -> str:
        return {
            "ok": "E bine",
            "atentionare": "Merge, dar mai încet",
            "lipsa": "Nu ajunge",
            "optioanala": "Opțional",
        }[self.stare]


def tabel_minim_recomandat(raport: Raport | None = None) -> list[RandTabel]:
    """Tabelul cu „Minim” și „Recomandat”, plus ce are calculatorul de față.

    Valorile sunt luate din constante.py, ca să fie identice în fereastra de
    instalare, în „Citește-mă.txt” și în lista care se poate duce la magazin.
    """
    raport = raport or verifica()
    spatiu_min = DISC_MINIM_CU_GPU_GB if raport.are_gpu else DISC_MINIM_GB
    spatiu_min_text = f"{spatiu_min:.0f} GB liberi"
    if DISC_MINIM_GB != DISC_MINIM_CU_GPU_GB:
        spatiu_min_text += f" ({DISC_MINIM_GB:.0f} GB fără placă video)"

    stare_os = "ok" if raport.build_windows >= WINDOWS_BUILD_MINIM else "lipsa"
    stare_cpu = "ok" if raport.arhitectura not in ("ARM64", "x86") else "lipsa"
    if raport.ram_gb <= 0:
        stare_ram = "atentionare"
    elif raport.ram_gb < WHISPER_MIN_RAM_GB:
        stare_ram = "lipsa"
    elif raport.ram_gb < WHISPER_RECOMANDAT_RAM_GB:
        stare_ram = "atentionare"
    else:
        stare_ram = "ok"
    if raport.disc_liber_gb <= 0:
        stare_disc = "atentionare"
    elif raport.disc_liber_gb < spatiu_min:
        stare_disc = "lipsa"
    elif raport.disc_liber_gb < DISC_RECOMANDAT_GB:
        stare_disc = "atentionare"
    else:
        stare_disc = "ok"
    stare_gpu = "ok" if raport.are_gpu else "optioanala"

    return [
        RandTabel(
            nume="Sistemul de operare",
            minim="Windows 10 (versiunea 1809) sau Windows 11, pe 64 de biți",
            recomandat="Windows 11, actualizat",
            gasit=raport.versiune_windows,
            stare=stare_os,
            explicatie="Windows este programul de bază al calculatorului.",
        ),
        RandTabel(
            nume="Procesorul",
            minim="Intel sau AMD, pe 64 de biți",
            recomandat="procesor din ultimii ani, cu 8 nuclee sau mai multe",
            gasit=f"{raport.procesor} · {raport.nuclee} nuclee",
            stare=stare_cpu,
            explicatie="Procesorul face calculele când nu există placă video.",
        ),
        RandTabel(
            nume="Memoria (RAM)",
            minim=f"{WHISPER_MIN_RAM_GB:.0f} GB",
            recomandat=f"{WHISPER_RECOMANDAT_RAM_GB:.0f} GB sau mai mult",
            gasit=f"{raport.ram_gb:.1f} GB" if raport.ram_gb else "nu am putut citi",
            stare=stare_ram,
            explicatie="cât poate ține calculatorul deodată în minte",
        ),
        RandTabel(
            nume="Spațiul pe disc",
            minim=spatiu_min_text,
            recomandat=f"{DISC_RECOMANDAT_GB:.0f} GB liberi sau mai mult",
            gasit=f"{raport.disc_liber_gb:.1f} GB liberi",
            stare=stare_disc,
            explicatie="cât loc are pentru fișiere: model, programe și documente",
        ),
        RandTabel(
            nume="Placa video (opțională)",
            minim="nu este obligatorie",
            recomandat="placă video dedicată cu minim 6 GB VRAM și driver 525 sau mai nou",
            gasit=(
                f"{raport.gpu_nume} · {raport.gpu_vram_mb} MB · driver {raport.gpu_driver}"
                if raport.are_gpu
                else "nu există una compatibilă (se folosește procesorul)"
            ),
            stare=stare_gpu,
            explicatie="doar pentru viteză: fără ea, transcrierea merge mai încet",
        ),
    ]


def text_tabel_pentru_tiparire(raport: Raport | None = None) -> str:
    """Aceleași valori, în text simplu (pentru „Citește-mă.txt” și pentru listă)."""
    linii = [
        "Ce calculator îți trebuie",
        "=========================",
        "",
        "Cei doi termeni, pe înțeles:",
        "  • memoria (RAM) – cât poate ține calculatorul deodată în minte;",
        "  • spațiul pe disc – cât loc are pentru fișiere.",
        "",
    ]
    for rand in tabel_minim_recomandat(raport):
        linii.append(f"{rand.nume}")
        linii.append(f"  minim:      {rand.minim}")
        linii.append(f"  recomandat: {rand.recomandat}")
        if rand.explicatie:
            linii.append(f"  ({rand.explicatie})")
        linii.append("")
    linii.extend(
        [
            "Lista scurtă, de arătat la magazin:",
            "  • Windows 11, pe 64 de biți",
            "  • procesor pe 64 de biți (Intel sau AMD), din ultimii ani",
            f"  • cel puțin {WHISPER_RECOMANDAT_RAM_GB:.0f} GB memorie RAM",
            "  • disc SSD de cel puțin 256 GB, cu minim 20 GB liberi",
            "  • placă video: ajută la viteză, dar nu e obligatorie",
            "",
        ]
    )
    return "\n".join(linii)


def lista_pentru_magazin() -> str:
    """Lista pe care utilizatorul o poate duce la magazin (fără mărci sau modele)."""
    return "\n".join(
        [
            "Am nevoie de un calculator care să poată rula programul",
            "„Dictate & Transcription Express Digital (D&TED)” – dictare și transcriere în limba română:",
            "",
            "• Windows 11, pe 64 de biți",
            "• procesor pe 64 de biți (Intel sau AMD), din ultimii ani",
            f"• cel puțin {WHISPER_RECOMANDAT_RAM_GB:.0f} GB memorie RAM",
            "• disc SSD de cel puțin 256 GB, cu minim 20 GB liberi",
            "• placă video: ajută la viteză, dar nu e obligatorie",
            "",
            "Mulțumesc.",
        ]
    )


def motiv_nepotrivit(raport: Raport) -> str:
    """Motivul exact, în română simplă, pentru care calculatorul nu e potrivit."""
    motive: list[str] = []
    for cerinta in raport.blocante:
        if cerinta.cheie == "ram":
            motive.append(
                f"are {raport.ram_gb:.1f} GB memorie RAM, iar programul are nevoie de "
                f"cel puțin {WHISPER_MIN_RAM_GB:.0f} GB"
            )
        elif cerinta.cheie == "disc":
            lipsa = raport.disc_necesar_gb - raport.disc_liber_gb
            motive.append(
                f"are {raport.disc_liber_gb:.1f} GB liberi pe disc, iar programul are "
                f"nevoie de cel puțin {raport.disc_necesar_gb:.0f} GB (mai lipsesc "
                f"{lipsa:.1f} GB)"
            )
        elif cerinta.cheie == "cpu":
            if raport.arhitectura == "ARM64":
                motive.append(
                    "are un procesor ARM (Snapdragon), iar biblioteca de transcriere "
                    "(faster-whisper/CTranslate2) nu are versiune optimizată pentru Windows pe ARM"
                )
            else:
                motive.append("are Windows pe 32 de biți, iar programul are nevoie de 64 de biți")
        elif cerinta.cheie == "os":
            motive.append(
                f"are {raport.versiune_windows}, iar programul are nevoie de Windows 10 "
                "(versiunea 1809) sau Windows 11"
            )
        else:
            motive.append(f"{cerinta.nume.lower()}: {cerinta.gasit}")
    return "; ".join(motive) if motive else "calculatorul nu îndeplinește cerințele minime"


def probleme_rezolvabile(raport: Raport) -> list[tuple[str, str]]:
    """Problemele care se pot rezolva pe calculatorul actual, cu acțiunea potrivită.

    Întoarce perechi (ce se poate face, felul acțiunii). Se folosesc înaintea
    recomandării unui calculator nou: mai întâi spunem ce se poate repara acum.
    """
    rezolvari: list[tuple[str, str]] = []
    for cerinta in raport.blocante:
        if cerinta.cheie == "disc":
            rezolvari.append(
                (
                    "Șterge fișiere de care nu ai nevoie sau alege alt disc pentru "
                    "instalare, apoi apasă «Verifică din nou».",
                    "elibereaza_disc",
                )
            )
        elif cerinta.cheie == "os":
            rezolvari.append(
                (
                    "Deschide Windows Update și instalează actualizările; vei ajunge la "
                    "o versiune de Windows suportată.",
                    "windows_update",
                )
            )
    # Placa video și microfonul nu blochează instalarea, dar ajută explicat.
    if not raport.are_gpu:
        rezolvari.append(
            (
                "Poți instala oricum: transcrierea va merge pe procesor, mai încet. "
                "Un driver video nou de la Windows Update poate ajuta pe viitor.",
                "windows_update",
            )
        )
    if not raport.are_microfon:
        rezolvari.append(
            (
                "Pentru dictare ai nevoie de un microfon: conectează-l ori folosește "
                "căști cu microfon, apoi verifică din setările Windows.",
                "setari_microfon",
            )
        )
    return rezolvari


def estimare_viteza(raport: Raport, minute_audio: float = 10.0) -> str:
    """Estimare prietenoasă a duratei transcrierii."""
    if raport.are_gpu:
        return (
            f"Cu placa video, {minute_audio:.0f} minute de audio se transcriu în "
            f"circa {max(1, round(minute_audio * 60 / 12 / 60)):d}–"
            f"{max(2, round(minute_audio * 60 / 6 / 60)):d} minute."
        )
    factor_min, factor_max = 0.5, 2.0  # minute de calcul pentru un minut de audio
    return (
        f"Fără placă video, {minute_audio:.0f} minute de audio se transcriu în "
        f"circa {max(1, round(minute_audio * factor_min)):d}–"
        f"{max(2, round(minute_audio * factor_max)):d} minute, în funcție de procesor."
    )


def text_pentru_consola(raport: Raport) -> str:
    """Afișare simplă în linia de comandă."""
    linii = ["", "Cerințe minime și ce are acest calculator:", ""]
    for cerinta in raport.cerinte:
        linii.append(f"  {cerinta.simbol} {cerinta.cuvant}: {cerinta.nume}: {cerinta.cerinta}")
        linii.append(f"      găsit: {cerinta.gasit}")
        if cerinta.detaliu:
            linii.append(f"      {cerinta.detaliu}")
        if cerinta.stare == "lipsa" and cerinta.sfat:
            linii.append(f"      → {cerinta.sfat}")
    linii.append("")
    linii.append(f"Rezultat: {raport.rezumat()}")
    return "\n".join(linii)
