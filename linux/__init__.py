"""Suportul pentru varianta de Linux a programului D&TED.

Conține două piese:

* alegerea backend-ului de transcriere (CUDA sau CPU) — ``suport_linux.alege_dispozitiv``;
* marcarea explicită a părților specifice Windows ca nefuncționale pe Linux.

Documentația completă, onestă, stă în ``LINUX.md`` (rădăcina repo-ului).
"""

from .suport_linux import (
    PĂRȚI_WINDOWS_NEPORTATE,
    FunctieWindowsNeportata,
    alege_dispozitiv,
    este_linux,
    marcatori,
)

__all__ = [
    "PĂRȚI_WINDOWS_NEPORTATE",
    "FunctieWindowsNeportata",
    "alege_dispozitiv",
    "este_linux",
    "marcatori",
]