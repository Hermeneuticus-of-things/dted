"""Nivelul microfonului din Windows + gradații în decibeli.

Două părți:

1. **Volumul microfonului** (setat de utilizator sau de program) se citește și
   se schimbă prin Windows Core Audio (COM ``IAudioEndpointVolume``) — fără
   biblioteci externe, doar ``ctypes``.
2. **Decibelli** pentru vumetru: ``0 dB`` înseamnă plină scara, adică nivelul
   la care sunetul se **distorsionează** (taiere). Sunetul bun de dictare e
   între -30 și -6 dB. Sub -45 dB e prea încet, peste -3 dB e pe cale să
   taie. Urechea aude logarithmic, de aceea bara e gradată în dB, nu liniar.
"""

from __future__ import annotations

import ctypes
import math
import sys
from ctypes import POINTER, c_float, c_void_p, wintypes

if sys.platform == "win32":
    from ctypes import WINFUNCTYPE
else:  # pe alte sisteme modulul doar nu face nimic (funcțiile întorc None/False)
    WINFUNCTYPE = None

#: Pragurile în dB pentru vumetru (0 dB = distorsiune).
DB_MINIM = -60.0
DB_DISTORSIUNE = 0.0
#: Zona bună de dictare.
DB_BUN_JOS = -30.0
DB_BUN_SUS = -6.0
#: Peste acest nivel sunetul e pe cale să se taie (roșu).
DB_ATENTIE = -3.0
#: Sub acest nivel e prea încet pentru transcriere bună (galben jos).
DB_PREA_INCET = -42.0


# --------------------------------------------------------------------------- dB


def amplitudine_in_db(amplitudine: float) -> float:
    """Transformă o amplitudine (0..1) în dB față de plină scală.

    1.0 → 0 dB (distorsiune), 0.5 → -6 dB, 0.1 → -20 dB, 0.0 → -inf (limitat).
    """
    if amplitudine <= 0.0:
        return DB_MINIM
    return max(DB_MINIM, 20.0 * math.log10(min(1.0, float(amplitudine))))


def db_in_fractie(db: float) -> float:
    """Poziția pe bara vumetrului (0..1) pentru o valoare în dB."""
    fractie = (db - DB_MINIM) / (DB_DISTORSIUNE - DB_MINIM)
    return min(1.0, max(0.0, fractie))


def zona_db(db: float) -> str:
    """„verde” (bun), „galben” (prea încet / aproape tare) sau „roșu” (taie)."""
    if db >= DB_ATENTIE:
        return "roșu"
    if DB_BUN_JOS <= db <= DB_BUN_SUS:
        return "verde"
    return "galben"


def text_db(db: float) -> str:
    """Text scurt pentru vumetru: „-12,4 dB” sau „0 dB — distorsiune!”."""
    if db >= -0.05:
        return "0 dB — distorsiune!"
    return f"{db:.1f} dB".replace(".", ",")


# ------------------------------------------------------------- decizia automată


def decizie_volum(varf_db: float) -> str:
    """Ce să facă programul cu volumul microfonului, după vârful auzit.

    ``"coboara"`` (e pe cale să se taie), ``"urca"`` (abia se aude) sau
    ``""`` (e bine așa).
    """
    if varf_db >= DB_ATENTIE:
        return "coboara"
    if varf_db < DB_PREA_INCET:
        return "urca"
    return ""


# --------------------------------------------------------------------------- COM


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


def _guid(text: str) -> _GUID:
    """„{BCDE0395-E52F-467C-8E3D-C4579291692E}” → structură GUID."""
    curat = text.strip("{}").replace("-", "")
    octeti = bytes.fromhex(curat[16:32])
    guid = _GUID()
    guid.Data1 = int(curat[0:8], 16)
    guid.Data2 = int(curat[8:12], 16)
    guid.Data3 = int(curat[12:16], 16)
    guid.Data4[:] = (ctypes.c_ubyte * 8).from_buffer_copy(octeti)
    return guid


_CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
_IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
_IID_IAudioEndpointVolume = "{5CDF2C82-841E-4546-9722-0CF74078229A}"

_ENDPOINT_CAPTURE = 1  # microfon
_CONSOLE = 0

# Indecșii metodelor în vtable, după cele 3 ale IUnknown.
_METODA_GET_DEFAULT = 4   # IMMDeviceEnumerator::GetDefaultAudioEndpoint
_METODA_ACTIVATE = 3      # IMMDevice::Activate
_METODA_SET_SCALAR = 7    # IAudioEndpointVolume::SetMasterVolumeLevelScalar
_METODA_GET_SCALAR = 9    # IAudioEndpointVolume::GetMasterVolumeLevelScalar


def _endpoint_volume():
    """Obiectul IAudioEndpointVolume al microfonului implicit (sau None)."""
    if sys.platform != "win32":
        return None
    try:
        ole32 = ctypes.WinDLL("ole32")
        try:
            ole32.CoInitializeEx(None, 0)  # STA; dacă e deja inițializat, ignorăm
        except OSError:
            pass
        enumerare = c_void_p()
        rezultat = ole32.CoCreateInstance(
            ctypes.byref(_guid(_CLSID_MMDeviceEnumerator)),
            None,
            1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(_guid(_IID_IMMDeviceEnumerator)),
            ctypes.byref(enumerare),
        )
        if rezultat != 0 or not enumerare.value:
            return None
        vtable_enum = (ctypes.c_void_p * 12).from_address(
            ctypes.cast(enumerare, ctypes.POINTER(c_void_p)).contents.value
        )
        get_default = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, c_void_p, wintypes.UINT, wintypes.UINT, ctypes.POINTER(c_void_p)
        )(vtable_enum[_METODA_GET_DEFAULT])
        dispozitiv = c_void_p()
        if get_default(enumerare, _ENDPOINT_CAPTURE, _CONSOLE, ctypes.byref(dispozitiv)) != 0:
            return None
        vtable_dispozitiv = (ctypes.c_void_p * 6).from_address(
            ctypes.cast(dispozitiv, ctypes.POINTER(c_void_p)).contents.value
        )
        activate = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, c_void_p, ctypes.POINTER(_GUID), wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(c_void_p)
        )(vtable_dispozitiv[_METODA_ACTIVATE])
        volum = c_void_p()
        if activate(
            dispozitiv,
            ctypes.byref(_guid(_IID_IAudioEndpointVolume)),
            1,  # CLSCTX_INPROC_SERVER
            None,
            ctypes.byref(volum),
        ) != 0:
            return None
        return volum
    except Exception:
        return None


def nivel_microfon() -> float | None:
    """Volumul microfonului implicit (0,0 – 1,0) sau ``None`` dacă nu se poate."""
    volum = _endpoint_volume()
    if volum is None:
        return None
    try:
        vtable = (ctypes.c_void_p * 16).from_address(
            ctypes.cast(volum, ctypes.POINTER(c_void_p)).contents.value
        )
        get_scalar = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, c_void_p, ctypes.POINTER(c_float)
        )(vtable[_METODA_GET_SCALAR])
        valoare = c_float()
        if get_scalar(volum, ctypes.byref(valoare)) != 0:
            return None
        return float(valoare.value)
    except Exception:
        return None


def seteaza_nivel_microfon(valoare: float) -> bool:
    """Pune volumul microfonului (0,0 – 1,0). Întoarce ``True`` dacă a reușit."""
    valoare = min(1.0, max(0.0, float(valoare)))
    volum = _endpoint_volume()
    if volum is None:
        return False
    try:
        vtable = (ctypes.c_void_p * 16).from_address(
            ctypes.cast(volum, ctypes.POINTER(c_void_p)).contents.value
        )
        set_scalar = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, c_void_p, c_float, ctypes.c_void_p
        )(vtable[_METODA_SET_SCALAR])
        return set_scalar(volum, c_float(valoare), None) == 0
    except Exception:
        return False


PAS_REGLAJ = 0.10       # cât de mult se schimbă volumul dintr-o dată (10%)
MINIM = 0.20            # nu coborâm sub 20% (altfel nu se mai aude deloc)
MAXIM = 0.95            # nu urcăm peste 95% (altfel taie sigur)


def aplica_decizia(decizie: str) -> float | None:
    """Schimbă volumul microfonului după decizie; întoarce noul nivel (sau None)."""
    if sys.platform != "win32" or not decizie:
        return None
    curent = nivel_microfon()
    if curent is None:
        return None
    if decizie == "coboara":
        nou = max(MINIM, curent - PAS_REGLAJ)
    elif decizie == "urca":
        nou = min(MAXIM, curent + PAS_REGLAJ)
    else:
        return None
    if abs(nou - curent) < 0.01:
        return None
    if seteaza_nivel_microfon(nou):
        return nou
    return None
