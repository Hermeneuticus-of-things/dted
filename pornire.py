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
# (salvată în %LOCALAPPDATA%\Dictare&Transcriere Română\program), aceasta are prioritate
# DOAR dacă versiunea din versiuni.json este strict mai nouă decât cea din pachetul de bază.
try:
    import json as _json
    import re as _re
    import shutil as _shutil

    def _tuplu_v(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in _re.findall(r"\d+", str(v or "")))

    _baza_inst = os.environ.get("DICTARE_DIR") or os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Dictare&Transcriere Română"
    )
    _prog_actualizat = Path(_baza_inst) / "program"
    _fis_vers = Path(_baza_inst) / "versiuni.json"
    if (_prog_actualizat / "dictare_transcriere_romana" / "__init__.py").is_file():
        _v_local = ""
        if _fis_vers.is_file():
            _date_v = _json.loads(_fis_vers.read_text(encoding="utf-8"))
            _v_local = str((_date_v.get("program") or {}).get("versiune", "")).strip()
        # Citim versiunea de bază din constante.py
        _const_baza = RADACINA / "dictare_transcriere_romana" / "constante.py"
        _v_baza = "0.0.0"
        if _const_baza.is_file():
            _m = _re.search(r'VERSIUNE\s*=\s*["\']([^"\']+)["\']', _const_baza.read_text(encoding="utf-8"))
            if _m:
                _v_baza = _m.group(1)
        if _v_local and _tuplu_v(_v_local) > _tuplu_v(_v_baza):
            if str(_prog_actualizat) not in sys.path:
                sys.path.insert(0, str(_prog_actualizat))
        elif _v_local and _tuplu_v(_v_local) <= _tuplu_v(_v_baza):
            # Instalatorul nou e la zi sau mai nou decât vechea actualizare descărcată: curățăm override-ul vechi.
            _shutil.rmtree(_prog_actualizat, ignore_errors=True)
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
