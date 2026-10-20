"""Setările programului, păstrate într-un fișier JSON lângă instalare."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from . import cai


@dataclass
class Config:
    """Setările alese de utilizator (toate au valori sigure implicit)."""

    limba: str = "ro"
    dispozitiv: str = "auto"          # "auto", "cpu" sau "cuda"
    model_incarcat: bool = False      # ține modelul în memorie între transcrieri
    salveaza_automat: bool = True     # salvează documentul imediat după transcriere
    director_iesiri: str = ""         # gol = folderul implicit din Documente
    ultimul_folder_audio: str = ""
    wordcraft_executabil: str = ""
    versiune_instalare: str = ""


def incarca() -> Config:
    cale = cai.fisier_config()
    if not cale.exists():
        return Config()
    try:
        date: dict[str, Any] = json.loads(cale.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Config()
    permise = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in date.items() if k in permise})


def salveaza(config: Config) -> None:
    cale = cai.fisier_config()
    try:
        cale.parent.mkdir(parents=True, exist_ok=True)
        temporar = cale.with_suffix(".tmp")
        temporar.write_text(
            json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporar.replace(cale)
    except OSError:
        pass


def director_iesiri(config: Config) -> Path:
    """Folderul unde se salvează documentele."""
    if config.director_iesiri:
        return Path(config.director_iesiri)
    return cai.director_iesiri()


def instalare_completa() -> bool:
    """Adevărat dacă mediul Python și modelul există deja."""
    return cai.python_mediu().exists() and cai.fisier_model().exists()
