"""„Dictare&Transcriere Română” — transcriere locală, în limba română.

Programul rulează complet offline după instalare: modelul Whisper
large-v3-turbo este descărcat o singură dată, la instalare, iar apoi toată
transcrierea se face pe calculatorul utilizatorului.

Numele tehnic al pachetului este ``dictare_transcriere_romana`` (fără
diacritice și fără spații, așa cum cer uneltele Python), dar utilizatorul
vede mereu numele complet: **Dictare&Transcriere Română**.
"""

from __future__ import annotations

from .constante import NUME_APLICATIE, NUME_FOLDER, VERSIUNE

__all__ = ["NUME_APLICATIE", "NUME_FOLDER", "VERSIUNE"]

#: Numele complet, așa cum îl vede utilizatorul peste tot.
NUME = NUME_APLICATIE
