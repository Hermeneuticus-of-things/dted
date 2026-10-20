"""Criptare simetrică AES-256-GCM folosind Windows CNG (``bcrypt.dll``).

Dictarea și transcrierea sunt ale utilizatorului: fișierele din folderul
implicit (sunet + text) se criptează la salvare, ca să nu poată fi citite din
Explorer sau din alte programe (cerința 10 / N-5). Aici este doar motorul de
criptare/decriptare; parolele, cheia de criptare și recuperarea stau în
``parola.py``.

Nu adăugăm nicio dependență: modulul vorbește direct cu **Windows
Cryptography: Next Generation** (CNG) prin ``ctypes``. AES-GCM este
*autentificat*: fiecărui mesaj i se face hash cu un **nonce** aleator de 12
octeți și i se adaugă un **tag** de autentificare de 16 octeți. Orice modificare
a datelor (chiar un singur bit) face decriptarea să eșueze cu ``CriptareInvalida``.

Formatul pachetului criptat (băți), produs de ``cripteaza_bytes``::

    nonce (12) | text criptat (N) | tag (16)

Toate funcțiile lucrează cu o **cheie brută de 32 de octeți**. De unde vine
cheia (parolă Argon2id/scrypt, cheie de recuperare) nu este treaba acestui modul.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

# --------------------------------------------------------------------------- eroare


class CriptareInvalida(Exception):
    """Pachetul nu a putut fi decriptat (parolă greșită sau date stricate)."""


# --------------------------------------------------------------------------- CNG (bcrypt.dll)

_bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)

BCRYPT_AES_ALGORITHM = "AES"
BCRYPT_CHAINING_MODE = "ChainingMode"
BCRYPT_CHAIN_MODE_GCM = "ChainingModeGCM"
BCRYPT_OBJECT_LENGTH = "ObjectLength"

STATUS_SUCCESS = 0
STATUS_AUTH_TAG_MISMATCH = 0xC000A002


class BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO(ctypes.Structure):
    """Structura cerută de BCrypt pentru modul GCM (lucru pe 32 și 64 de biți)."""

    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwInfoVersion", wintypes.DWORD),
        ("pbNonce", ctypes.POINTER(ctypes.c_ubyte)),
        ("cbNonce", wintypes.DWORD),
        ("pbAuthData", ctypes.POINTER(ctypes.c_ubyte)),
        ("cbAuthData", wintypes.DWORD),
        ("pbTag", ctypes.POINTER(ctypes.c_ubyte)),
        ("cbTag", wintypes.DWORD),
        ("pbMacContext", ctypes.POINTER(ctypes.c_ubyte)),
        ("cbMacContext", wintypes.DWORD),
        ("cbAAD", wintypes.DWORD),
        ("cbData", ctypes.c_ulonglong),
        ("dwFlags", wintypes.DWORD),
    ]


# --------------------------------------------------------------------------- semnături funcții


def _semneaza() -> None:
    _bcrypt.BCryptOpenAlgorithmProvider.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        wintypes.DWORD,
    ]
    _bcrypt.BCryptOpenAlgorithmProvider.restype = ctypes.c_long

    _bcrypt.BCryptCloseAlgorithmProvider.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    _bcrypt.BCryptCloseAlgorithmProvider.restype = ctypes.c_long

    _bcrypt.BCryptSetProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    _bcrypt.BCryptSetProperty.restype = ctypes.c_long

    _bcrypt.BCryptGetProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
    ]
    _bcrypt.BCryptGetProperty.restype = ctypes.c_long

    _bcrypt.BCryptGenerateSymmetricKey.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    _bcrypt.BCryptGenerateSymmetricKey.restype = ctypes.c_long

    _bcrypt.BCryptDestroyKey.argtypes = [ctypes.c_void_p]
    _bcrypt.BCryptDestroyKey.restype = ctypes.c_long

    _bcrypt.BCryptEncrypt.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
    ]
    _bcrypt.BCryptEncrypt.restype = ctypes.c_long

    _bcrypt.BCryptDecrypt.argtypes = _bcrypt.BCryptEncrypt.argtypes
    _bcrypt.BCryptDecrypt.restype = ctypes.c_long


_semnat = False


def _deschide_algoritm() -> ctypes.c_void_p:
    """Deschide providerul AES în mod GCM; întoarce mânerul algoritmului."""
    global _semnat
    if not _semnat:
        _semneaza()
        _semnat = True
    alg = ctypes.c_void_p()
    status = _bcrypt.BCryptOpenAlgorithmProvider(
        ctypes.byref(alg), BCRYPT_AES_ALGORITHM, None, 0
    )
    if status != STATUS_SUCCESS or not alg.value:
        raise OSError(f"Nu am putut deschide AES (CNG), cod 0x{status & 0xFFFFFFFF:08X}")
    try:
        mod = ctypes.c_wchar_p(BCRYPT_CHAIN_MODE_GCM)
        bufer_mod = ctypes.cast(mod, ctypes.POINTER(ctypes.c_ubyte))
        lungime = (len(BCRYPT_CHAIN_MODE_GCM) + 1) * ctypes.sizeof(ctypes.c_wchar)
        status = _bcrypt.BCryptSetProperty(
            alg, BCRYPT_CHAINING_MODE, bufer_mod, lungime, 0
        )
        if status != STATUS_SUCCESS:
            raise OSError(f"Nu am putut seta modul GCM, cod 0x{status & 0xFFFFFFFF:08X}")
    except Exception:
        _bcrypt.BCryptCloseAlgorithmProvider(alg, 0)
        raise
    return alg


def _cheie_simetrica(alg: ctypes.c_void_p, cheie: bytes):
    """Creează o cheie AES-256 dintr-o cheie brută de 32 de octeți."""
    lungime_obiect = wintypes.DWORD()
    rezultat = wintypes.DWORD()
    status = _bcrypt.BCryptGetProperty(
        alg,
        BCRYPT_OBJECT_LENGTH,
        ctypes.cast(ctypes.byref(lungime_obiect), ctypes.POINTER(ctypes.c_ubyte)),
        ctypes.sizeof(wintypes.DWORD),
        ctypes.byref(rezultat),
        0,
    )
    if status != STATUS_SUCCESS or lungime_obiect.value == 0:
        raise OSError(f"Nu am putut citi lungimea obiectului-cheie, cod 0x{status & 0xFFFFFFFF:08X}")
    obiect_cheie = (ctypes.c_ubyte * lungime_obiect.value)()
    hkey = ctypes.c_void_p()
    secret = (ctypes.c_ubyte * len(cheie)).from_buffer_copy(cheie)
    status = _bcrypt.BCryptGenerateSymmetricKey(
        alg,
        ctypes.byref(hkey),
        obiect_cheie,
        lungime_obiect.value,
        secret,
        len(cheie),
        0,
    )
    if status != STATUS_SUCCESS or not hkey.value:
        raise OSError(f"Nu am putut crea cheia, cod 0x{status & 0xFFFFFFFF:08X}")
    return hkey


def _gcm(
    hkey: ctypes.c_void_p,
    date: bytes,
    nonce: bytes,
    tag: bytes | None,
    aad: bytes,
    cripteaza: bool,
) -> tuple[bytes, bytes]:
    """O singură operație GCM: criptare sau decriptare. Întoarce (iesire, tag)."""
    if len(nonce) != 12:
        raise ValueError("Nonce-ul GCM trebuie să aibă 12 octeți.")

    info = BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO()
    info.cbSize = ctypes.sizeof(BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO)
    info.dwInfoVersion = 1

    bufer_nonce = (ctypes.c_ubyte * 12).from_buffer_copy(nonce)
    info.pbNonce = ctypes.cast(bufer_nonce, ctypes.POINTER(ctypes.c_ubyte))
    info.cbNonce = 12

    bufer_aad = (ctypes.c_ubyte * len(aad)).from_buffer_copy(aad) if aad else None
    if bufer_aad is not None:
        info.pbAuthData = ctypes.cast(bufer_aad, ctypes.POINTER(ctypes.c_ubyte))
        info.cbAuthData = len(aad)

    bufer_tag = (ctypes.c_ubyte * 16)()
    if tag is not None:
        if len(tag) != 16:
            raise ValueError("Tag-ul GCM trebuie să aibă 16 octeți.")
        ctypes.memmove(bufer_tag, tag, 16)
    info.pbTag = ctypes.cast(bufer_tag, ctypes.POINTER(ctypes.c_ubyte))
    info.cbTag = 16

    intrare = (ctypes.c_ubyte * len(date)).from_buffer_copy(date) if date else (ctypes.c_ubyte * 0)()
    iesire = (ctypes.c_ubyte * len(date))()
    rezultat = wintypes.DWORD()
    functie = _bcrypt.BCryptEncrypt if cripteaza else _bcrypt.BCryptDecrypt

    status = functie(
        hkey,
        ctypes.cast(intrare, ctypes.POINTER(ctypes.c_ubyte)) if date else None,
        len(date),
        ctypes.cast(ctypes.byref(info), ctypes.c_void_p),
        None,
        0,
        ctypes.cast(iesire, ctypes.POINTER(ctypes.c_ubyte)),
        len(date),
        ctypes.byref(rezultat),
        0,
    )
    if (status & 0xFFFFFFFF) == STATUS_AUTH_TAG_MISMATCH:
        raise CriptareInvalida("Datele au fost modificate sau parola este greșită.")
    if status != STATUS_SUCCESS:
        raise OSError(
            f"Operația GCM a eșuat (cod 0x{status & 0xFFFFFFFF:08X})."
        )
    return bytes(iesire[: rezultat.value]), bytes(bufer_tag)


# --------------------------------------------------------------------------- API public


def cripteaza_bytes(cheie: bytes, text_curat: bytes, aad: bytes = b"") -> bytes:
    """Criptează ``text_curat``; întoarce ``nonce | text criptat | tag``."""
    if len(cheie) != 32:
        raise ValueError("Cheia de criptare trebuie să aibă 32 de octeți.")
    nonce = os.urandom(12)
    alg = _deschide_algoritm()
    try:
        hkey = _cheie_simetrica(alg, cheie)
        try:
            text_criptat, tag = _gcm(hkey, text_curat, nonce, None, aad, True)
        finally:
            _bcrypt.BCryptDestroyKey(hkey)
    finally:
        _bcrypt.BCryptCloseAlgorithmProvider(alg, 0)
    return nonce + text_criptat + tag


def decripteaza_bytes(cheie: bytes, pachet: bytes, aad: bytes = b"") -> bytes:
    """Decriptează un pachet produs de ``cripteaza_bytes``.

    Ridică ``CriptareInvalida`` dacă parola/cheia e greșită sau datele au fost
    modificate ori stricate.
    """
    if len(cheie) != 32:
        raise ValueError("Cheia de criptare trebuie să aibă 32 de octeți.")
    if len(pachet) < 12 + 16:
        raise CriptareInvalida("Pachetul criptat este prea scurt sau nu are formatul așteptat.")
    nonce = pachet[:12]
    tag = pachet[-16:]
    text_criptat = pachet[12:-16]
    alg = _deschide_algoritm()
    try:
        hkey = _cheie_simetrica(alg, cheie)
        try:
            text_curat, _ = _gcm(hkey, text_criptat, nonce, tag, aad, False)
        finally:
            _bcrypt.BCryptDestroyKey(hkey)
    finally:
        _bcrypt.BCryptCloseAlgorithmProvider(alg, 0)
    return text_curat


# --------------------------------------------------------------------------- fișiere

MAGIC = b"DTED1"  # 5 octeți la începutul oricărui fișier criptat


def cripteaza_fisier(cheie: bytes, sursa: Path, destinatie: Path, aad: bytes = b"") -> None:
    """Criptează fișierul ``sursa`` în ``destinatie`` (scrie magic + pachet)."""
    date = sursa.read_bytes()
    pachet = cripteaza_bytes(cheie, date, aad)
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    temporar = destinatie.with_name(destinatie.name + ".tmp")
    temporar.write_bytes(MAGIC + pachet)
    os.replace(temporar, destinatie)


def decripteaza_fisier(cheie: bytes, sursa: Path, destinatie: Path, aad: bytes = b"") -> None:
    """Decriptează un fișier scris de ``cripteaza_fisier``."""
    continut = sursa.read_bytes()
    if not continut.startswith(MAGIC):
        raise CriptareInvalida("Fișierul nu este criptat (lipsește antetul).")
    date = decripteaza_bytes(cheie, continut[len(MAGIC):], aad)
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    temporar = destinatie.with_name(destinatie.name + ".tmp")
    temporar.write_bytes(date)
    os.replace(temporar, destinatie)


def este_criptat(sursa: Path) -> bool:
    """Spune dacă un fișier poartă antetul nostru de criptare."""
    try:
        with sursa.open("rb") as fisier:
            return fisier.read(len(MAGIC)) == MAGIC
    except OSError:
        return False