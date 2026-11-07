"""Criptarea din oficiu a textelor și dictărilor salvate de aplicație.

Promisiunea (cerința titularului): folderul în care stau textele e criptat chiar
fără parolă — din afara aplicației nu se poate citi nimic; textul iese lizibil
doar prin Export sau Salvează ca… (alese explicit de utilizator).

Cum funcționează:
* la prima rulare se generează o cheie aleatorie de 32 de octeți;
* cheia e pusă în seiful local, protejată de **DPAPI** (Windows o leagă de
  contul tău de utilizator — copiată pe alt calculator sau alt cont, nu se
  mai poate deschide);
* tot ce scrie aplicația în folderele ei (texte transcrise, dictări audio,
  salvarea automată, fișierele de recuperare) trece prin
  :func:`cripteaza_bytes` (AES-256-GCM, antet „DTED2");
* aplicația decriptează transparent la citire — utilizatorul nu simte nimic;
* Exports către alte foldere (alese de utilizator) rămân în clar, la cerere.

Nu se înlocuiește criptarea cu parolă (AES cu cheia din parolă) — cele două
straturi coexistă: din oficiu = cheie locală; cu parolă = cheie derivată.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
from pathlib import Path

from . import cai
from .criptare import CriptareInvalida, decripteaza_bytes, cripteaza_bytes

MAGIC = b"DTED2"  # antetul fișierelor criptate „din oficiu" (se deosebește de DTED1 = cu parolă)
NUME_CHEIE = "cheie-locala.bin"

_cheie_memo: dict[str, bytes] = {}
_dpapi_ok = True


# ------------------------------------------------------------------ DPAPI

class EroareDPAPI(RuntimeError):
    """DPAPI (Windows) nu a putut proteja/desproteja datele."""


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(date: bytes) -> DATA_BLOB:
    tampon = ctypes.create_string_buffer(date, len(date))
    return DATA_BLOB(len(date), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_ubyte)))


def _protejeaza_dpapi(date: bytes) -> bytes:
    """Leagă datele de contul de Windows al utilizatorului (CryptProtectData)."""
    global _dpapi_ok
    if not _dpapi_ok:
        raise EroareDPAPI("DPAPI nu este disponibil (doar Windows).")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),   # pDataIn
        wintypes.LPCWSTR,            # szDataDescr
        ctypes.POINTER(DATA_BLOB),   # pOptionalEntropy
        ctypes.c_void_p,             # pvReserved
        ctypes.c_void_p,             # pPromptStruct
        wintypes.DWORD,              # dwFlags
        ctypes.POINTER(DATA_BLOB),   # pDataOut
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    intrare = _blob(date)
    iesire = DATA_BLOB()
    ok = crypt32.CryptProtectData(
        ctypes.byref(intrare),
        "D&TED cheie locala",
        None,
        None,
        None,
        0,
        ctypes.byref(iesire),
    )
    if not ok or not iesire.pbData:
        raise EroareDPAPI(f"CryptProtectData a eșuat (erorile Windows {ctypes.get_last_error()}).")
    try:
        return ctypes.string_at(iesire.pbData, iesire.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(iesire.pbData)


def _desprotejeaza_dpapi(date: bytes) -> bytes:
    global _dpapi_ok
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),   # pDataIn
        ctypes.POINTER(wintypes.LPWSTR),  # ppszDataDescr
        ctypes.POINTER(DATA_BLOB),   # pOptionalEntropy
        ctypes.c_void_p,             # pvReserved
        ctypes.c_void_p,             # pPromptStruct
        wintypes.DWORD,              # dwFlags
        ctypes.POINTER(DATA_BLOB),   # pDataOut
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    intrare = _blob(date)
    iesire = DATA_BLOB()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(intrare),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(iesire),
    )
    if not ok or not iesire.pbData:
        _dpapi_ok = False
        raise EroareDPAPI("CryptUnprotectData a eșuat — datele nu sunt ale acestui cont.")
    try:
        return ctypes.string_at(iesire.pbData, iesire.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(iesire.pbData)


# ------------------------------------------------------------------ cheia locală

def cale_cheie_locala() -> Path:
    """Unde stă cheia locală protejată (în folderul de instalare, nu lângă textele criptate)."""
    return cai.director_instalare() / "seif" / NUME_CHEIE


def cheie_locala() -> bytes:
    """Cheia de 32 de octeți a instalației: o creează la prima folosire, o ține în memorie."""
    cale = cale_cheie_locala()
    memo = _cheie_memo.get(str(cale))
    if memo:
        return memo
    if cale.is_file():
        protejat = cale.read_bytes()
        cheie = _desprotejeaza_dpapi(protejat)
        if len(cheie) != 32:
            raise CriptareInvalida("Cheia locală are o lungime greșită.")
        _cheie_memo[str(cale)] = cheie
        return cheie
    import secrets

    cheie = secrets.token_bytes(32)
    cale.parent.mkdir(parents=True, exist_ok=True)
    cale.write_bytes(_protejeaza_dpapi(cheie))
    _cheie_memo[str(cale)] = cheie
    return cheie


def reseteaza_cheie_locala_memo() -> None:
    """Doar pentru teste: uită cheia ținută în memorie."""
    _cheie_memo.clear()


# ------------------------------------------------------------------ pachete

def cripteaza_automatic(text_curat: bytes) -> bytes:
    """Criptează cu cheia locală; antet „DTED2" + pachet AES-256-GCM."""
    return MAGIC + cripteaza_bytes(cheie_locala(), text_curat, aad=MAGIC)


def decripteaza_automatic(pachet: bytes) -> bytes:
    """Decriptează un fișier „din oficiu"; ridică CriptareInvalida dacă e stricat."""
    if not pachet.startswith(MAGIC):
        raise CriptareInvalida("Fișierul nu este criptat din oficiu (antet lipsă).")
    return decripteaza_bytes(cheie_locala(), pachet[len(MAGIC):], aad=MAGIC)


def este_criptat_oficiu(cale: Path) -> bool:
    """Adevărat dacă fișierul începe cu antetul „DTED2"."""
    try:
        with open(cale, "rb") as f:
            return f.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def scrie_criptat(cale: Path, text_curat: bytes) -> Path:
    """Scrie pe disc versiunea criptată din oficiu a conținutului."""
    cale.parent.mkdir(parents=True, exist_ok=True)
    temporar = cale.with_suffix(cale.suffix + ".tmp")
    temporar.write_bytes(cripteaza_automatic(text_curat))
    os.replace(temporar, cale)
    return cale


def citeste_criptat(cale: Path) -> bytes:
    """Citește și decriptează transparent un fișier „din oficiu"."""
    return decripteaza_automatic(Path(cale).read_bytes())


def este_criptat_oficiu(cale) -> bool:
    """Adevărat dacă fișierul începe cu antetul „DTED2"."""
    try:
        with open(cale, "rb") as f:
            return f.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def scrie_criptat(cale, text_curat: bytes):
    """Scrie pe disc versiunea criptată din oficiu a conținutului."""
    cale = Path(cale)
    cale.parent.mkdir(parents=True, exist_ok=True)
    temporar = cale.with_suffix(cale.suffix + ".tmp")
    temporar.write_bytes(cripteaza_automatic(text_curat))
    os.replace(temporar, cale)
    return cale


def citeste_criptat(cale) -> bytes:
    """Citește și decriptează transparent un fișier „din oficiu"."""
    return decripteaza_automatic(Path(cale).read_bytes())
