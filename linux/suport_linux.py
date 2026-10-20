"""Suport pentru varianta de Linux a programului D&TED.

Două responsabilități:

1. **Alegerea backend-ului de transcriere** (CUDA sau CPU) ca funcție de sine
   stătătoare — aceeași logică din ``dictare_transcriere_romana/motor.py``
   (metoda ``_alege_dispozitiv``), expusă separat pentru claritate și testare.

2. **Marcarea explicită a părților specifice Windows** ca **nefuncționale pe
   Linux** (criptare CNG/``bcrypt.dll``, firewall Windows, Bluetooth, drivere,
   instalator Inno). Aceste părți nu au fost portate.

Onest despre testare: acest modul a fost verificat doar prin compilare și prin
apelarea funcțiilor pe platforma Windows (``platform.system() == "Windows"``).
Rularea efectivă pe Linux nu a fost testată.
"""

from __future__ import annotations

import os
import platform
import sys
from typing import Callable, Mapping


# --------------------------------------------------------------------------
# 1. Backend de transcriere: CUDA sau CPU (auto-detect + fallback implicit)
# --------------------------------------------------------------------------

def alege_dispozitiv(fortat_cpu: bool = False) -> tuple[str, str]:
    """Alege „cuda" sau „cpu" pentru transcriere.

    Întoarce ``(dispozitiv, motiv)``. Logică identică cu ``motor.py``:

    * dacă s-a cerut explicit CPU, se folosește CPU;
    * dacă CTranslate2 vede cel puțin un dispozitiv CUDA, se folosește CUDA;
    * la orice eroare, se cade pe CPU.

    Fallback-ul „CUDA dă eroare → CPU" este garantat aici de faptul că orice
    excepție este prinsă și întoarce ``"cpu"``. Fallback-ul complet la
    încărcarea modelului (dacă *încărcarea* pe CUDA eșuează) rămâne în
    ``motor.py``, în metoda ``MotorWhisper.incarca``.
    """
    if fortat_cpu or os.environ.get("DTED_FORTEAZA_CPU") == "1":
        return "cpu", "procesorul a fost cerut explicit (CPU forțat)"
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "placă NVIDIA detectată prin CTranslate2"
        return "cpu", "nu s-a găsit o placă NVIDIA cu driver CUDA"
    except Exception as exc:  # noqa: BLE001 - orice eroare înseamnă CPU
        return "cpu", f"CTranslate2 nu poate verifica placa ({exc})"


def este_linux() -> bool:
    """Adevărat când rulează pe Linux. Folosit pentru a marca funcțiile Windows."""
    return platform.system() == "Linux"


# --------------------------------------------------------------------------
# 2. Părțile specifice Windows — marcate ca nefuncționale pe Linux
# --------------------------------------------------------------------------

#: Funcțiile Windows care NU au fost portate pe Linux (și nu vor fi).
PĂRȚI_WINDOWS_NEPORTATE: Mapping[str, str] = {
    "criptare": "criptarea fișierelor (AES-256-GCM prin Windows CNG / bcrypt.dll)",
    "firewall": "blocarea internetului prin Windows Firewall (blocare.py / internet.py)",
    "bluetooth": "blocarea/folosirea Bluetooth-ului (blocare.py)",
    "usb": "blocarea stocării USB (blocare.py)",
    "drivere": "verificarea driverelor Windows (drivere.py)",
    "inno": "instalatorul Inno Setup (instalator/setup.iss)",
}


class FunctieWindowsNeportata:
    """Un apel care explică clar că funcția este doar Windows.

    Se instanțiază per funcție; la apel ridică ``NotImplementedError`` cu un
    mesaj lizibil, în loc să pice cu o eroare obscură de legare Windows.
    """

    def __init__(self, funcție: str) -> None:
        self.funcție = funcție
        self.descriere = PĂRȚI_WINDOWS_NEPORTATE.get(
            funcție, f"funcția Windows „{funcție}”"
        )

    def __call__(self, *args, **kwargs):  # noqa: D102
        raise NotImplementedError(
            f"{self.descriere} este specific Windows și nu este disponibil pe Linux."
        )

    def __repr__(self) -> str:  # noqa: D105
        return f"<funcție Windows neportată: {self.funcție}>"


def marcatori() -> dict[str, Callable[..., None]]:
    """Întoarce un stub apelabil pentru fiecare funcție Windows neportată.

    Utile în codul de pe Linux care, de dragul compatibilității, trebuie să aibă
    un simbol importabil, dar care să spună clar „nu există aici".
    """
    return {nume: FunctieWindowsNeportata(nume) for nume in PĂRȚI_WINDOWS_NEPORTATE}


def _afiseaza_alege_dispozitiv() -> int:
    """Comandă de verificare: ce backend s-ar folosi acum."""
    dispozitiv, motiv = alege_dispozitiv()
    print(f"platformă: {platform.system()}")
    print(f"backend ales: {dispozitiv.upper()}  ({motiv})")
    print("Linux real: " + ("da" if este_linux() else "nu (Windows/altceva)"))
    return 0


if __name__ == "__main__":  # pragma: no cover - doar pentru verificare manuală
    sys.exit(_afiseaza_alege_dispozitiv())