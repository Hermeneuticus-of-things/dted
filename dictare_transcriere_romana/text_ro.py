"""Nume românesc peste tot: diacritice, nume de fișiere, formatări.

Aici se află și corectarea automată a diacriticelor scrise greșit, cu sedilă
(ş, ţ) în loc de virgulă (ș, ț), așa cum apar ele din unele tastaturi, din
lipirea textului sau din convertoare vechi.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

# --------------------------------------------------------------------------- diacritice

#: Perechi (greșit → corect) pentru diacriticele românești.
#: Formele cu sedilă nu există în scrierea românească de azi; cele corecte
#: sunt literele cu virgulă (ș, ț și majusculele lor).
_TABEL_DIACRITICE = str.maketrans(
    {
        "\u015f": "\u0219",  # ş (s cu sedilă)      -> ș (s cu virgulă)
        "\u0163": "\u021b",  # ţ (t cu sedilă)      -> ț (t cu virgulă)
        "\u015e": "\u0218",  # Ş                    -> Ș
        "\u0162": "\u021a",  # Ţ                    -> Ț
    }
)

#: Variante „aproape corecte” care apar des în textul lipit din alte programe.
_INLOCUIRI = (
    ("\u015f", "\u0219"),
    ("\u0163", "\u021b"),
    ("\u015e", "\u0218"),
    ("\u0162", "\u021a"),
    ("\u0218\u0302", "\u0218"),  # Ș urmat de un accent rătăcit
    ("\u0103\u0302", "\u0103"),  # ă urmat de un accent rătăcit
)


def repara_diacritice(text: str) -> str:
    """Corectează diacriticele românești scrise greșit (ş/ţ → ș/ț).

    Funcția este sigură pentru orice text: nu modifică alte limbi,
    nu schimbă spațiile și nu atinge literele deja corecte.
    """
    if not text:
        return text
    for greu, corect in _INLOCUIRI:
        if greu in text:
            text = text.replace(greu, corect)
    return text


def diacritice_ok(text: str) -> bool:
    """Adevărat dacă textul nu mai conține litere românești cu sedilă."""
    return not any(greu in text for greu, _ in _INLOCUIRI)


def normalizeaza(text: str) -> str:
    """Formă NFC + diacritice corecte (se aplică înainte de afișare și salvare)."""
    return repara_diacritice(unicodedata.normalize("NFC", text or ""))


# --------------------------------------------------------------------------- texte


def curata_xml(text: str) -> str:
    """Elimină caracterele de control care nu sunt permise în XML."""
    return "".join(
        ch for ch in text if ch in "\t\n\r" or (ord(ch) >= 32 and ord(ch) != 0x7F)
    )


def paragrafe(text: str) -> list[str]:
    """Împarte textul în paragrafe, păstrând rândurile goale."""
    text = normalizeaza(text).replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text:
        return []
    return [linie.strip() for linie in text.split("\n")]


def numara_cuvinte(text: str) -> int:
    """Numărul de cuvinte, pentru mesajele din interfață."""
    return len([cuvânt for cuvânt in re.split(r"\s+", text.strip()) if cuvânt])


def scurteaza(text: str, maxim: int = 60) -> str:
    """Scurtează un text pentru afișare, fără a tăia literele diacritice."""
    text = text.strip()
    if len(text) <= maxim:
        return text
    taiat = text[:maxim]
    if " " in taiat:
        taiat = taiat.rsplit(" ", 1)[0]
    return taiat.rstrip(" ,;:.") + "…"


def titlu_din_text(text: str, maxim: int = 70) -> str:
    """Prima propoziție, folosită ca titlu al documentului."""
    prima = ""
    for linie in normalizeaza(text).splitlines():
        linie = linie.strip()
        if linie:
            prima = linie
            break
    if not prima:
        return ""
    potrivire = re.match(r"(.+?[.!?])(\s|$)", prima)
    titlu = potrivire.group(1) if potrivire else prima
    return scurteaza(titlu, maxim)


# --------------------------------------------------------------------------- nume fișiere


def nume_sigur(text: str, maxim: int = 80) -> str:
    """Transformă un text într-un nume de fișier valid pe Windows."""
    curatat = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", normalizeaza(text)).strip(" .")
    curatat = re.sub(r"\s+", " ", curatat)
    if not curatat:
        curatat = "Transcriere"
    return curatat[:maxim].strip(" .") or "Transcriere"


def marca_timp(moment: datetime | None = None) -> str:
    """Data și ora într-o formă potrivită pentru nume de fișiere."""
    return (moment or datetime.now()).strftime("%Y-%m-%d %H-%M")


def nume_document(prefix: str, extensie: str = ".docx", moment: datetime | None = None) -> str:
    """Numele complet al unui document nou.

    Exemplu: „Dictare&Transcriere Română – 2026-10-19 10-35.docx”.
    """
    from .constante import NUME_FOLDER

    baza = nume_sigur(prefix) if prefix else NUME_FOLDER
    if not baza.lower().startswith(NUME_FOLDER.lower()):
        baza = f"{NUME_FOLDER} – {baza}"
    if not extensie.startswith("."):
        extensie = "." + extensie
    return f"{baza} – {marca_timp(moment)}{extensie}"


def nume_recuperare(moment: datetime | None = None) -> str:
    """Numele fișierului de recuperare automată."""
    return f"recuperare {marca_timp(moment)}.txt"


# --------------------------------------------------------------------------- timpi


def durata_text(secunde: float) -> str:
    """Durată în cuvinte simple: „1 minut 23 secunde”."""
    secunde = max(0.0, float(secunde))
    total = int(round(secunde))
    ore, rest = divmod(total, 3600)
    minute, sec = divmod(rest, 60)
    parti: list[str] = []
    if ore:
        parti.append(f"{ore} {'oră' if ore == 1 else 'ore'}")
    if minute:
        parti.append(f"{minute} {'minut' if minute == 1 else 'minute'}")
    if sec or not parti:
        parti.append(f"{sec} {'secundă' if sec == 1 else 'secunde'}")
    return " ".join(parti)


def durata_pentru_transcriere(secunde: float, are_gpu: bool) -> str:
    """Estimare a duratei transcrierii, în cuvinte simple."""
    minute_audio = max(0.1, secunde / 60.0)
    if are_gpu:
        minim = max(0.2, minute_audio * 0.1)
        maxim = max(0.4, minute_audio * 0.25)
    else:
        # Pe procesor, transcrierea durează de obicei de la jumătate din
        # durata audio până la de două ori durata audio, în funcție de procesor.
        minim = minute_audio * 0.5
        maxim = minute_audio * 2.0
    return (
        f"aproximativ {durata_text(minim * 60)}"
        if abs(maxim - minim) < 0.5
        else f"între {durata_text(minim * 60)} și {durata_text(maxim * 60)}"
    )


def timp_subtitrare(secunde: float, separator: str = ",") -> str:
    """Timp în formatul subtitrărilor: 00:01:23,456 (SRT) sau 00:01:23.456 (VTT)."""
    secunde = max(0.0, float(secunde))
    ore, rest = divmod(int(secunde), 3600)
    minute, sec = divmod(rest, 60)
    milli = int(round((secunde - int(secunde)) * 1000))
    if milli == 1000:
        milli, sec = 0, sec + 1
    return f"{ore:02d}:{minute:02d}:{sec:02d}{separator}{milli:03d}"
