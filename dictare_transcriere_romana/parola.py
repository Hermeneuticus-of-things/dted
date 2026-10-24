"""Parola, cheia maestră și cheia de recuperare (cerința 11 / N-6).

Fișierele se criptează cu o **cheie maestră** de 32 de octeți (``vault_key``),
generată o singură dată. Ca să nu depindem de ea direct (și ca utilizatorul să
o deschidă cu parola lui), cheia maestră se **învelește** (se criptează) de
două ori, cu AES-256-GCM din ``criptare.py``:

1. cu **cheia derivată din parolă** (``scrypt`` — Argon2id/scrypt sunt admise);
2. cu **cheia de recuperare** (aleatoare, arătată o singură dată).

Pe disc se salvează doar cele două „învelișuri” + sarea scrypt. **Parola nu se
salvează nicăieri** (0.11.3). La schimbarea parolei, se re-învelește doar
cheia maestră cu noua parolă — fișierele rămân neatinsa (0.11.3).

Cheia de recuperare deschide fișierele chiar și fără parolă (0.11.6-d). E
afișată **o singură dată** la setarea parolei: dacă se pierde și parola, și
cheia de recuperare, fișierele se pierd definitiv (0.11.4).
"""

from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass, field
from hashlib import scrypt
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    from . import criptare
else:
    # Criptarea (AES-256-GCM) folosește Windows CNG (bcrypt.dll) și nu există pe
    # Linux. Un stub minimal, ca „parola.py" să fie importabil și să dea o eroare
    # clară la folosire, în loc să pice la import cu un WinDLL inexistent.
    class _CriptareIndisponibila:
        class CriptareInvalida(Exception):
            """Echivalent fără implementare al ``criptare.CriptareInvalida``."""

        @staticmethod
        def cripteaza_bytes(*args: Any, **kwargs: Any) -> bytes:
            raise NotImplementedError(
                "Criptarea fișierelor este specifică Windows (CNG / bcrypt.dll) "
                "și nu este disponibilă pe Linux."
            )

        @staticmethod
        def decripteaza_bytes(*args: Any, **kwargs: Any) -> bytes:
            raise NotImplementedError(
                "Criptarea fișierelor este specifică Windows (CNG / bcrypt.dll) "
                "și nu este disponibilă pe Linux."
            )

    criptare = _CriptareIndisponibila  # type: ignore[assignment]

# Parametri scrypt (puternici, rapidi ~100 ms): N=2^15, r=8, p=1.
SCRYPT_N = 32768
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
#: Memoria maximă pentru scrypt (128*N*r octeți + rezervă).
SCRYPT_MAXMEM = 64 * 1024 * 1024


class ParolaGresita(Exception):
    """Parola nu se potrivește (sau datele seifului sunt stricate)."""


def genereaza_salt() -> bytes:
    return os.urandom(16)


def genereaza_cheie_recuperare() -> bytes:
    """Cheia de recuperare brută (32 octeți); se arată utilizatorului ca base64."""
    return os.urandom(32)


def codifica_recuperare(cheie: bytes) -> str:
    return base64.b64encode(cheie).decode("ascii")


def decodifica_recuperare(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def deriveaza_din_parola(parola: str, salt: bytes, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P) -> bytes:
    """Derivă o cheie de 32 octeți din parolă prin scrypt."""
    return scrypt(
        parola.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=SCRYPT_MAXMEM,
        dklen=SCRYPT_DKLEN,
    )


@dataclass
class Seif:
    """Datele persistente ale seifului — ce se salvează pe disc (JSON)."""

    format: str = "dted-vault-1"
    salt: bytes = field(default_factory=genereaza_salt)
    n: int = SCRYPT_N
    r: int = SCRYPT_R
    p: int = SCRYPT_P
    invelita_parola: bytes = b""
    invelita_recuperare: bytes = b""

    def la_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "salt": base64.b64encode(self.salt).decode("ascii"),
            "n": self.n,
            "r": self.r,
            "p": self.p,
            "invelita_parola": base64.b64encode(self.invelita_parola).decode("ascii"),
            "invelita_recuperare": base64.b64encode(self.invelita_recuperare).decode("ascii"),
        }

    @staticmethod
    def din_dict(date: dict[str, Any]) -> "Seif":
        return Seif(
            format=str(date.get("format", "dted-vault-1")),
            salt=base64.b64decode(date.get("salt", "")),
            n=int(date.get("n", SCRYPT_N)),
            r=int(date.get("r", SCRYPT_R)),
            p=int(date.get("p", SCRYPT_P)),
            invelita_parola=base64.b64decode(date.get("invelita_parola", "")),
            invelita_recuperare=base64.b64decode(date.get("invelita_recuperare", "")),
        )


_AAD_PAROLA = b"dted-vault-parola"
_AAD_RECUPERARE = b"dted-vault-recuperare"


def _inveleste_in(cheie: bytes, cheie_maestra: bytes, aad: bytes) -> bytes:
    return criptare.cripteaza_bytes(cheie, cheie_maestra, aad)


def _desveleste_din(cheie: bytes, invelis: bytes, aad: bytes) -> bytes:
    return criptare.decripteaza_bytes(cheie, invelis, aad)


def defineste(parola: str) -> tuple[Seif, str, bytes]:
    """Creează un seif nou pentru ``parola``.

    Întoarce (``Seif`` de salvat, cheia de recuperare ca base64, cheia maestră).
    Cheia de recuperare **trebuie arătată o singură dată** și nu se mai salvează.
    """
    cheie_maestra = os.urandom(32)
    cheie_recuperare = genereaza_cheie_recuperare()
    salt = genereaza_salt()
    cheie_parola = deriveaza_din_parola(parola, salt)
    seif = Seif(
        salt=salt,
        invelita_parola=_inveleste_in(cheie_parola, cheie_maestra, _AAD_PAROLA),
        invelita_recuperare=_inveleste_in(cheie_recuperare, cheie_maestra, _AAD_RECUPERARE),
    )
    return seif, codifica_recuperare(cheie_recuperare), cheie_maestra


def deschide_cu_parola(seif: Seif, parola: str) -> bytes:
    """Întoarce cheia maestră, după verificarea parolei. Ridică ``ParolaGresita``."""
    cheie_parola = deriveaza_din_parola(parola, seif.salt, seif.n, seif.r, seif.p)
    try:
        return _desveleste_din(cheie_parola, seif.invelita_parola, _AAD_PAROLA)
    except criptare.CriptareInvalida as exc:
        raise ParolaGresita("Parola nu este corectă.") from exc


def deschide_cu_recuperare(seif: Seif, cheie_recuperare_b64: str) -> bytes:
    """Întoarce cheia maestră folosind cheia de recuperare (fără parolă)."""
    try:
        cheie_recuperare = decodifica_recuperare(cheie_recuperare_b64)
    except Exception as exc:  # pragma: no cover - base64 greșit
        raise ParolaGresita("Cheia de recuperare nu are formatul corect.") from exc
    if len(cheie_recuperare) != 32:
        raise ParolaGresita("Cheia de recuperare nu are formatul corect.")
    try:
        return _desveleste_din(cheie_recuperare, seif.invelita_recuperare, _AAD_RECUPERARE)
    except criptare.CriptareInvalida as exc:
        raise ParolaGresita("Cheia de recuperare nu se potrivește.") from exc


def schimba_parola(seif: Seif, parola_veche: str, parola_noua: str) -> Seif:
    """Verifică parola veche și re-învelește doar cheia maestră (fișierele NU se ating)."""
    cheie_maestra = deschide_cu_parola(seif, parola_veche)  # verifică vechea parolă
    cheie_noua = deriveaza_din_parola(parola_noua, seif.salt, seif.n, seif.r, seif.p)
    return Seif(
        format=seif.format,
        salt=seif.salt,
        n=seif.n,
        r=seif.r,
        p=seif.p,
        invelita_parola=_inveleste_in(cheie_noua, cheie_maestra, _AAD_PAROLA),
        invelita_recuperare=seif.invelita_recuperare,
    )


def pauza_greseli(nr_greseli: int) -> float:
    """Pauza crescătoare (secunde) pentru parole greșite repetate (0.11.5).

    Începe de la 2 s și se dublează până la maximum 256 s (~4 minute). Nu șterge date.
    """
    if nr_greseli <= 0:
        return 0.0
    return float(min(2 ** min(nr_greseli, 8), 300))


# ------------------------------------------------------------------ fișierul seifului


def fisier_seif() -> Path:
    """Unde stă seiful pe disc, în folderul de instalare (``seif.json``)."""
    from . import cai

    return cai.director_instalare() / "seif.json"


def salveaza_seif(seif: Seif) -> bool:
    """Scrie seiful pe disc (JSON). Întoarce ``False`` dacă scrierea eșuează."""
    try:
        fisier = fisier_seif()
        fisier.parent.mkdir(parents=True, exist_ok=True)
        fisier.write_text(json.dumps(seif.la_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def incarca_seif() -> Seif | None:
    """Citește seiful de pe disc; ``None`` dacă lipsește sau e deteriorat."""
    try:
        date = json.loads(fisier_seif().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(date, dict):
        return None
    return Seif.din_dict(date)


def sterge_seif() -> bool:
    """Șterge seiful (când utilizatorul scoate parola). Nu șterge documente."""
    try:
        fisier_seif().unlink(missing_ok=True)
        return True
    except OSError:
        return False


def seif_definit() -> bool:
    """``True`` dacă există o parolă pusă (seiful e pe disc)."""
    return fisier_seif().exists()