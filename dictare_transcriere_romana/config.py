"""Setările programului, păstrate într-un fișier JSON lângă instalare.

Toate setările au valori sigure implicit, iar fișierul se scrie în așa fel
încât o scriere întreruptă să nu strice setările existente.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from . import cai


@dataclass
class Config:
    """Setările alese de utilizator (toate au valori sigure implicit)."""

    limba: str = "ro"                     # limba vorbită; implicit română
    termeni: str = ""                     # nume și termeni ai utilizatorului, separați prin virgulă
    dispozitiv: str = "auto"              # „auto”, „cpu” sau „cuda”
    model_incarcat: bool = True           # ține modelul în memorie între transcrieri
    salveaza_automat: bool = True         # salvează documentul imediat după transcriere
    salvare_automata_secunde: int = 20    # cât de des se salvează textul de siguranță
    director_iesiri: str = ""             # gol = folderul implicit din Documente
    ultimul_folder_audio: str = ""
    ultimul_format: str = "docx"          # formatul folosit ultima dată
    program_scris_preferat: str = ""      # gol = LibreOffice (implicit)
    program_scris_nume: str = ""          # numele, pentru afișare
    microfon_preferat: str = ""           # numele dispozitivului de intrare
    difuzor_preferat: str = ""            # numele dispozitivului de ieșire
    mod_afisare: str = "windows"          # „windows”, „luminos” sau „intunecat”
    marire_scris: int = 100               # mărimea scrisului: 100, 125, 150 sau 200
    font_text: str = ""                   # fontul textului (gol = implicit)
    wrap_text: bool = True                # randurile lungi trec pe randul urmator
    spatiere_linii: str = "normal"        # "normal", "mare", "foarte_mare"
    latime_max_rand: str = "tot"          # "tot" sau "ingust"
    margini_text: int = 8                 # marginile din jurul textului (px)
    marime_butoane: int = 100             # marimea butoanelor si meniurilor
    versiune_instalare: str = ""
    tur_vazut: bool = False               # turul de la prima pornire
    sunet_testat: bool = False            # proba de sunet a fost făcută
    avertizeaza_internet: bool = True     # avertizarea roșie „Internetul este deschis”
    avertizeaza_wifi: bool = True         # avertizarea pentru Wi-Fi pornit
    avertizeaza_bluetooth: bool = True    # avertizarea pentru Bluetooth pornit
    avertizeaza_stick: bool = True        # avertizarea pentru stick băgat în calculator
    fara_avertisment_azi: str = ""        # ziua în care utilizatorul a ales „Nu mai afișa azi”
    oprire_la_iesire: bool = False        # a fost oprită o operațiune lungă înainte de închidere
    geometrie_fereastra: str = ""          # "WxH+X+Y" pentru restaurare la pornire
    cuda_stare: str = ""                  # bibliotecile plăcii video: "", "ok", "esuat", "refuzat"
    cuda_stare_data: str = ""             # când s-a hotărât starea de mai sus (AAAA-LL-ZZ HH:MM)
    cuda_stare_detaliu: str = ""          # motivul, dacă descărcarea a eșuat
    cripteaza_documente: bool = False     # salvează documentele criptat (AES-256, cu parolă)
    blocare_dictare: str = "nimic"        # la dictare: „nimic”, „program” (doar D&TED) sau „tot”
    model_preferat: str = "auto"          # „auto” (românescul, dacă există) sau numele folderului
    auto_volum: bool = True                # aduce singur nivelul microfonului ca să nu distorsioneze
    scurteaza_pauze: bool = False         # dictare: taie tăcerile mai lungi de 2 secunde (52)
    pregateste_audio: bool = False        # dictare: aduce volumul la un nivel potrivit (51)
    scurtaturi_globale: bool = False      # scurtăturile globale (Ctrl+Alt+D) — OPRITE implicit (53)
    asistent_microfon_vazut: bool = False # asistentul de microfon de la prima dictare (52)
    activare_vocala: bool = False         # pornește singură dictarea când auzi vocea (Express Dictate)
    prag_activare_db: int = -35           # pragul activării vocale, în dB
    scurtaturi: dict[str, str] = field(default_factory=lambda: dict(SCURTATURI_IMPLICIT))


#: Tastele rapide pe care utilizatorul și le poate schimba din Setări → „Taste rapide”.
#: Cheile sunt nume stabile (nu se schimbă), valorile sunt secvențe QKeySequence.
SCURTATURI_IMPLICIT: dict[str, str] = {
    "dictare": "F5",                # pornește/oprește dictarea (⏺ roșu)
    "asculta": "F9",                # ascultă de la semn / pauză
    "stop_asculta": "Shift+Esc",    # oprește ascultarea
    "inapoi_5": "F7",               # derulează înapoi 5 s
    "inainte_5": "F8",              # derulează înainte 5 s
    "viteza_normala": "F10",
    "viteza_lenta": "F11",
    "viteza_rapida": "F12",
    "de_la_capat": "F6",            # șterge fraza neterminată, o iei de la capăt
    "idee_noua": "Shift+F6",        # șterge fraza + paragraf nou cu tab
    "semn": "Ctrl+B",               # semnul [mm:ss] la cursor
}


def scurtaturi(config: "Config | None" = None) -> dict[str, str]:
    """Tastele rapide alese, cu valorile implicite pentru cele neschiebrate."""
    baza = dict(SCURTATURI_IMPLICIT)
    if config is None:
        try:
            config = incarca()
        except Exception:
            config = None
    alese = getattr(config, "scurtaturi", None) or {}
    for cheie, valoare in alese.items():
        if isinstance(valoare, str) and valoare.strip():
            baza[str(cheie)] = valoare.strip()
    return baza


def incarca() -> Config:
    """Citește setările; dacă fișierul lipsește sau e stricat, folosește valorile sigure."""
    cale = cai.fisier_config()
    if not cale.exists():
        return Config()
    try:
        date: dict[str, Any] = json.loads(cale.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Config()
    permise = {camp.name for camp in fields(Config)}
    return Config(**{cheie: valoare for cheie, valoare in date.items() if cheie in permise})


def salveaza(config: Config) -> bool:
    """Scrie setările, fără a lăsa fișiere pe jumătate scrise."""
    cale = cai.fisier_config()
    try:
        cale.parent.mkdir(parents=True, exist_ok=True)
        temporar = cale.with_suffix(".tmp")
        temporar.write_text(
            json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporar.replace(cale)
        return True
    except OSError:
        return False


def director_iesiri(config: Config) -> Path:
    """Folderul în care se salvează documentele."""
    if config.director_iesiri:
        return Path(config.director_iesiri)
    return cai.director_iesiri()


def instalare_completa() -> bool:
    """Adevărat dacă mediul Python și modelul există deja."""
    return cai.python_mediu().exists() and cai.fisier_model().exists()
