"""Transcriere locală — program de dictare și transcriere 100% offline.

Pachetul este împărțit în module mici:

* ``constante``   — toate valorile fixe (linkuri, sume SHA-256, praguri minime)
* ``cai``         — unde se instalează programul (fără căi fixe)
* ``jurnal``      — jurnalul de aplicație și de instalare
* ``resurse``     — verificarea calculatorului înainte de instalare
* ``descarcare``  — descărcare cu progres și verificare SHA-256
* ``wordcraft``   — instalarea și lansarea WordCraft
* ``instalare``   — pașii de instalare (Python, biblioteci, model, WordCraft)
* ``documente``   — scrierea fișierelor DOCX și ODT fără dependențe externe
* ``motor``       — Whisper large-v3-turbo, rulat local
* ``microfon``    — înregistrare de la microfon
* ``ui_*``        — interfețele grafice în limba română
"""

__version__ = "1.0.0"
NUME = "Transcriere locală"
