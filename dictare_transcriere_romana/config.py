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
    # Aspect Fluent (migrarea Qt): culoarea de accent a Windows și pastila de înregistrare.
    accent_sistem: bool = True            # butoanele principale iau culoarea de accent din Windows
    pastila_inregistrare: bool = True     # pastila plutitoare „Înregistrez” când fereastra e ascunsă
    # Setări „Expert” (pliate implicit). Valorile implicite = comportamentul de dinainte.
    expert_fereastra_sec: float = 4.0     # câte secunde de sunet se transcriu o dată la dictare
    expert_suprapunere_sec: float = 0.0   # suprapunerea ferestrelor (doar motorul audio nativ)
    expert_ring_buffer_ms: int = 2000     # mărimea bufferului circular (doar motorul audio nativ)
    expert_buget_text_anterior: int = 0   # câte caractere din textul anterior intră în prompt (0 = deloc)
    expert_text_anterior: bool = False    # condition_on_previous_text (faster-whisper)
    expert_beam_size: int = 5             # beam search (faster-whisper: 5 implicit)
    expert_compute_type: str = "auto"     # auto / int8 / int8_float16 / float16 / float32
    expert_vad_prag: float = 0.5          # pragul detectorului de vorbire (Silero, 0.5 implicit)
    expert_timp_tacere_sec: int = 0       # oprește dictarea după atâtea secunde de liniște (0 = niciodată)
    # Dictarea lungă (dictare_lunga.py): Silero VAD → ferestre 30 s / 7,5 s suprapunere → commit LCP.
    # OPRITĂ implicit: dictarea clasică (bucăți de expert_fereastra_sec) rămâne neschimbată.
    # Pornire și din mediu: DTED_DICTARE_LUNGA=1 (are prioritate față de setare).
    dictare_lunga: bool = False
    dictare_lunga_vad: str = "auto"       # auto / ggml / onnx / energie (auto: ggml → onnx → energie)
    dictare_lunga_pauza_idee_sec: float = 2.0   # pauza după care începe o idee nouă (paragraf nou)
    dictare_lunga_fereastra_sec: float = 30.0   # fereastra maximă trimisă la ASR (5–30 s)
    dictare_lunga_suprapunere_sec: float = 7.5  # suprapunerea ferestrelor (0–15 s)
    # Serverul MCP local (mcp_server/): OPRIT implicit, doar 127.0.0.1; lista goală = nimeni nu are acces.
    mcp_enabled: bool = False
    mcp_port: int = 0                     # 0 = doar stdio (fără port TCP); altfel portul pe 127.0.0.1
    mcp_allowed_agents: list[str] = field(default_factory=list)
    mcp_comenzi_vocale_enabled: bool = False  # unealta „comenzi_vocale” (separat, oprită implicit)
    # Transcriere în cloud (cloud/): OPRITĂ implicit; cheile NU stau aici (keyring / fișier criptat).
    cloud_enabled: bool = False
    cloud_provider: str = "openai"        # „openai” sau „deepseek”
    cloud_endpoint: str = ""              # gol = adresa implicită a furnizorului
    # Memoria dictărilor lungi (rezumatorul C++ OpenLLM-Ro, ~8,5 GB RAM): OPRITĂ implicit,
    # ca Portabil/Offline și PC-urile slabe să nu o pornească singure (B1, 2026-10-27).
    # ``hardware.aplica_profil_rezumat`` o pornește o dată pe PC-uri capabile (Standard/Bootstrap).
    rezumat_activ: bool = False           # oprit implicit; profilul hardware îl pornește pe PC-uri capabile
    rezumat_la_fragmente: int = 4         # un rezumat la fiecare N fragmente confirmate…
    rezumat_la_caractere: int = 1500      # …sau când s-au strâns peste atâtea caractere noi
    rezumat_prag_suprapunere: float = 0.90  # sub prag ⇒ coada textului (nu poate coborî sub 0.90)
    rezumat_buget_tokeni: int = 160       # cât din prompt ia memoria (Whisper: max 224 cu tot cu termenii)
    rezumat_gguf: str = ""                # gol = caută singur OpenLLM-Ro (vezi memorie_dictare.gaseste_gguf)
    rezumat_profil_aplicat: bool = False  # True după ce profilul hardware a decis rezumat_activ o dată
    rezumat_profil_nivel: str = ""        # nivelul A–E salvat la aplicarea profilului


#: Limitele setărilor „Expert” (minim, maxim). Valorile din afară sunt aduse în interval,
#: ca un fișier de setări editat de mână să nu poată strica dictarea.
LIMITE_EXPERT: dict[str, tuple[float, float]] = {
    "expert_fereastra_sec": (1.0, 30.0),
    "expert_suprapunere_sec": (0.0, 5.0),
    "expert_ring_buffer_ms": (200, 30_000),
    "expert_buget_text_anterior": (0, 800),
    "expert_beam_size": (1, 10),
    "expert_vad_prag": (0.1, 0.9),
    "expert_timp_tacere_sec": (0, 600),
    "prag_activare_db": (-70, -5),
}
#: Limitele memoriei dictărilor lungi (pragul 0.90 e poarta anti-halucinație: doar în sus).
LIMITE_REZUMAT: dict[str, tuple[float, float]] = {
    "rezumat_la_fragmente": (1, 100),
    "rezumat_la_caractere": (100, 50_000),
    "rezumat_prag_suprapunere": (0.90, 1.0),
    "rezumat_buget_tokeni": (32, 224),
}

#: Felurile de calcul acceptate de CTranslate2 (``auto`` = alegerea programului).
FELURI_CALCUL = ("auto", "int8", "int8_float16", "float16", "float32")


def valori_expert_implicite() -> dict[str, Any]:
    """Valorile implicite ale setărilor Expert (pentru „Revino la valorile implicite”)."""
    implicit = Config()
    chei = [camp.name for camp in fields(Config) if camp.name.startswith("expert_")]
    chei.append("prag_activare_db")
    return {cheie: getattr(implicit, cheie) for cheie in chei}


def limiteaza_expert(config: Config) -> Config:
    """Aduce setările Expert în intervalele permise (pe loc) și întoarce config-ul."""
    implicit = Config()
    for cheie, (minim, maxim) in LIMITE_EXPERT.items():
        valoare_implicita = getattr(implicit, cheie)
        tip = type(valoare_implicita)
        try:
            valoare = tip(getattr(config, cheie))
        except (TypeError, ValueError):
            valoare = valoare_implicita
        setattr(config, cheie, tip(max(minim, min(maxim, valoare))))
    if config.expert_suprapunere_sec >= config.expert_fereastra_sec:
        config.expert_suprapunere_sec = 0.0
    if config.expert_compute_type not in FELURI_CALCUL:
        config.expert_compute_type = "auto"
    config.expert_text_anterior = bool(config.expert_text_anterior)
    return config


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
    try:
        config = Config(**{cheie: valoare for cheie, valoare in date.items() if cheie in permise})
    except (TypeError, AttributeError):
        return Config()
    return normalizeaza_rezumat(normalizeaza_integrari(limiteaza_expert(config)))


def normalizeaza_rezumat(config: Config) -> Config:
    """Memoria dictărilor lungi: tipuri corecte și valori în interval; orice ciudățenie = oprit."""
    implicit = Config()
    config.rezumat_activ = config.rezumat_activ is True
    config.rezumat_profil_aplicat = config.rezumat_profil_aplicat is True
    for cheie, (minim, maxim) in LIMITE_REZUMAT.items():
        tip = type(getattr(implicit, cheie))
        try:
            valoare = tip(getattr(config, cheie))
        except (TypeError, ValueError):
            valoare = getattr(implicit, cheie)
        if valoare != valoare:  # NaN
            valoare = getattr(implicit, cheie)
        setattr(config, cheie, tip(max(minim, min(maxim, valoare))))
    if not isinstance(config.rezumat_gguf, str):
        config.rezumat_gguf = ""
    config.rezumat_gguf = config.rezumat_gguf.strip()
    return config


#: Furnizorii de transcriere în cloud acceptați (vezi ``cloud/``).
FURNIZORI_CLOUD = ("openai", "deepseek")


def adresa_cloud_permisa(url: str) -> bool:
    """HTTPS oriunde; HTTP simplu doar spre acest calculator (un server local)."""
    from urllib.parse import urlsplit  # noqa: PLC0415

    parti = urlsplit(url)
    if parti.scheme == "https" and parti.hostname:
        return True
    return parti.scheme == "http" and parti.hostname in ("127.0.0.1", "localhost", "::1")


def normalizeaza_integrari(config: Config) -> Config:
    """MCP și cloud: tipuri corecte; orice valoare ciudată înseamnă „oprit” / implicit."""
    config.mcp_enabled = config.mcp_enabled is True
    config.mcp_comenzi_vocale_enabled = config.mcp_comenzi_vocale_enabled is True
    config.cloud_enabled = config.cloud_enabled is True
    try:
        config.mcp_port = int(config.mcp_port)
    except (TypeError, ValueError):
        config.mcp_port = 0
    if not 0 <= config.mcp_port <= 65535:
        config.mcp_port = 0
    agenti = config.mcp_allowed_agents if isinstance(config.mcp_allowed_agents, list) else []
    config.mcp_allowed_agents = [a.strip() for a in agenti if isinstance(a, str) and a.strip()]
    if config.cloud_provider not in FURNIZORI_CLOUD:
        config.cloud_provider = "openai"
    if not isinstance(config.cloud_endpoint, str) or (
        config.cloud_endpoint and not adresa_cloud_permisa(config.cloud_endpoint)
    ):
        config.cloud_endpoint = ""  # doar HTTPS (sau http pe acest calculator)
    return config


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
