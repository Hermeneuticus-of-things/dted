"""Construiește kiturile per-versiune: portabil, program-zip, Linux, manifest.

Folosire: python _build_kits.py <versiune>   (după ce dist-v<versiune>\\DTED există)

REGULI DE PACKAGING (bug-ul de la 0.6.7/0.6.8):
- program-zip-ul conține DOAR „dictare_transcriere_romana/...” la rădăcină —
  arcname se calculează mereu relativ la folderul pachetului (niciodată căi
  absolute de pe mașina de build, cum a ieșit o dată: „OpenCode/...” în zip);
- la final, zip-ul se VERIFICĂ: prima intrare trebuie să înceapă cu numele
  pachetului, altfel scriptul eșuează (nu se publică nimic stricat).
"""
import hashlib
import json
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

RADACINA = Path(__file__).resolve().parent
if len(sys.argv) != 2:
    raise SystemExit("Folosire: python _build_kits.py <versiune>")
VERSIUNE = sys.argv[1]
DIST = RADACINA / f"dist-v{VERSIUNE}" / "DTED"
PACHET = RADACINA / "dictare_transcriere_romana"
NUME_PACHET = "dictare_transcriere_romana"

if not DIST.is_dir():
    raise SystemExit(f"Lipsește folderul de build: {DIST}")
if not (PACHET / "__init__.py").is_file():
    raise SystemExit(f"Lipsește pachetul aplicației: {PACHET / '__init__.py'}")

# 1) portabil: tot kitul, fără bibliotecile CUDA (programul le descarcă singur)
with zipfile.ZipFile(RADACINA / f"portabil-DTED-{VERSIUNE}.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for fisier in sorted(DIST.rglob("*")):
        if not fisier.is_file():
            continue
        rel = fisier.relative_to(DIST)
        if rel.parts[:2] == ("_internal", "nvidia"):
            continue
        z.write(fisier, "DTED/" + rel.as_posix())
print("PORTABIL-OK", flush=True)

# 2) program-zip (actualizare din program): sursele pachetului, curat, RELATIV
with zipfile.ZipFile(RADACINA / f"program-{VERSIUNE}.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for fisier in sorted(PACHET.rglob("*")):
        if not fisier.is_file() or "__pycache__" in fisier.parts or ".bak" in fisier.name:
            continue
        if fisier.suffix.lower() not in {".py", ".ico", ".png"}:
            continue
        z.write(
            fisier,
            (Path(NUME_PACHET) / fisier.relative_to(PACHET)).as_posix(),
        )
# VERIFICARE de structură (bug 0.6.7/0.6.8): toate intrările de pachet pornesc cu numele pachetului
with zipfile.ZipFile(RADACINA / f"program-{VERSIUNE}.zip") as z:
    nume = z.namelist()
    stricate = [n for n in nume if not n.startswith(NUME_PACHET + "/")]
    if stricate:
        raise SystemExit(f"EROARE packaging: intrări în afara pachetului: {stricate[:5]}")
    if f"{NUME_PACHET}/__init__.py" not in nume:
        raise SystemExit("EROARE packaging: lipsește __init__.py la rădăcină")
print("ZIP-UPDATE-OK (structura verificata)", flush=True)

# Numele versionat rămâne pentru arhiva istorică; aplicația folosește mereu
# aceeași cale din release-ul marcat „latest”.
shutil.copyfile(RADACINA / f"program-{VERSIUNE}.zip", RADACINA / "program.zip")

# 3) arhiva Linux: surse + scripturi + documentație (arcname relativ la RADACINA)
with tarfile.open(RADACINA / f"dted-{VERSIUNE}-linux.tar.gz", "w:gz") as t:
    for nume in (NUME_PACHET, "linux", "docs"):
        p = RADACINA / nume
        if p.exists():
            for f in sorted(p.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts and ".bak" not in f.name:
                    t.add(f, arcname=f.relative_to(RADACINA).as_posix(), recursive=False)
    for nume in (
        "install.sh", "requirements.txt", "LINUX.md", "README.md",
        "download_model.py", "pornire.py", "versiuni.json", "AGENTS.md",
    ):
        p = RADACINA / nume
        if p.exists():
            t.add(p, arcname=p.relative_to(RADACINA).as_posix())
print("LINUX-OK", flush=True)

# 4) manifestul actualizărilor (versiuni.json)
dim = (RADACINA / "program.zip").stat().st_size
sha = hashlib.sha256((RADACINA / "program.zip").read_bytes()).hexdigest()
(RADACINA / "versiuni.json").write_text(
    json.dumps({
        "program": {
            "versiune": VERSIUNE,
            "url": "https://github.com/Hermeneuticus-of-things/dted/releases/latest/download/program.zip",
            "sha256": sha,
            "dimensiune": dim,
        },
        "model": {"versiune": "whisper-turbo-ro-en-ct2"},
    }, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print("MANIFEST-OK", dim, sha[:12], flush=True)
