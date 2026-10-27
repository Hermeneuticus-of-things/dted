"""Lansator prietenos: deschide programul sau instalarea, fără consolă.

Este folosit de ``instaleaza.bat`` și de ``porneste.bat``, dar poate fi
rulat și direct: ``python pornire.py``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# Permite rularea din folderul sursă, fără instalare de pachet.
RADACINA = Path(__file__).resolve().parent
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

# Dacă utilizatorul a aplicat o actualizare a componentei „program” din GitHub
# (salvată în %LOCALAPPDATA%\Dictare&Transcriere Română\program), aceasta are prioritate.
try:
    _baza_inst = os.environ.get("DICTARE_DIR") or os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Dictare&Transcriere Română"
    )
    _prog_actualizat = Path(_baza_inst) / "program"
    if (_prog_actualizat / "dictare_transcriere_romana" / "__init__.py").is_file():
        if str(_prog_actualizat) not in sys.path:
            sys.path.insert(0, str(_prog_actualizat))
except Exception:
    pass

# Pregătește consola pe UTF-8 pentru diacritice corecte în jurnal/err.txt
if os.name == "nt":
    # În programul construit (fără consolă) „chcp” ar deschide o fereastră neagră.
    if not getattr(sys, "frozen", False) and sys.stdout is not None:
        try:
            os.system("chcp 65001 > nul")
        except Exception:
            pass
    for fir in (sys.stdout, sys.stderr):
        try:
            fir.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def main() -> int:
    from dictare_transcriere_romana.__main__ import main as intrare

    return intrare(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
