"""Testează contractul de structură și URL stabil al kitului de update."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


RADACINA = Path(__file__).resolve().parents[1]


def test_build_kits_publica_alias_stabil_si_manifest_coerent():
    with tempfile.TemporaryDirectory() as director_tmp:
        tmp = Path(director_tmp)
        shutil.copy2(RADACINA / "_build_kits.py", tmp / "_build_kits.py")

        pachet = tmp / "dictare_transcriere_romana"
        pachet.mkdir()
        (pachet / "__init__.py").write_text("# pachet de test\n", encoding="utf-8")
        (pachet / "actualizare.py").write_text("# modul de test\n", encoding="utf-8")

        dist = tmp / "dist-v9.8.7" / "DTED"
        dist.mkdir(parents=True)
        (dist / "DTED.exe").write_bytes(b"kit de test")

        mediu = os.environ.copy()
        mediu["PYTHONIOENCODING"] = "utf-8"
        subprocess.run(
            [sys.executable, str(tmp / "_build_kits.py"), "9.8.7"],
            cwd=tmp,
            env=mediu,
            check=True,
            capture_output=True,
            text=True,
        )

        arhiva_versionata = tmp / "program-9.8.7.zip"
        arhiva_stabila = tmp / "program.zip"
        assert arhiva_versionata.read_bytes() == arhiva_stabila.read_bytes()

        with zipfile.ZipFile(arhiva_stabila) as arhiva:
            nume = arhiva.namelist()
        assert nume[0].startswith("dictare_transcriere_romana/")
        assert "dictare_transcriere_romana/__init__.py" in nume
        assert all(n.startswith("dictare_transcriere_romana/") for n in nume)

        program = json.loads((tmp / "versiuni.json").read_text(encoding="utf-8"))["program"]
        assert program["versiune"] == "9.8.7"
        assert program["url"] == (
            "https://github.com/Hermeneuticus-of-things/dted/"
            "releases/latest/download/program.zip"
        )
        assert program["sha256"] == hashlib.sha256(arhiva_stabila.read_bytes()).hexdigest()
        assert program["dimensiune"] == arhiva_stabila.stat().st_size
