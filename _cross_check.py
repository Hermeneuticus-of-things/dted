"""Cross-check OBLIGATORIU înainte de publicare: python _cross_check.py <versiune>

Verifică, încrucișat, tot lanțul update-ului. ORICE eșec = nu se publică:
 1. versiunea din constante.py = versiunea cerută
 2. instalator/setup.iss = aceeași versiune + dist/output pe versiunea respectivă
 3. versiuni.json (manifestul) = versiunea cerută + URL-ul release-ului potrivit
 4. program-<v>.zip există, e zip valid, structura = „dictare_transcriere_romana/...”,
    SHA-256 = cel din manifest, dimensiunea = cea din manifest
 5. __init__.py din zip are constanta VERSIUNE = versiunea cerută (citit din conținut)
 6. Setup.DTED-<v>.exe există, iar SHA256SUMS.txt conține toate sumele
 7. dted-bootstrap.ps1: $Tag = v<versiune> + amprenta exe-ului din SHA256SUMS
"""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

RADACINA = Path(__file__).resolve().parent
V = sys.argv[1] if len(sys.argv) > 1 else ""
esecuri = []


def ok(text):
    print("  ✔", text)


def verifica(condiție, text):
    if condiție:
        ok(text)
    else:
        esecuri.append(text)
        print("  ✘ EȘEC:", text)


print(f"== CROSS-CHECK v{V} ==")

# 1) constante.py
t = (RADACINA / "dictare_transcriere_romana/constante.py").read_text(encoding="utf-8")
verifica(f'VERSIUNE = "{V}"' in t, f"constante.py: VERSIUNE = {V}")

# 2) setup.iss
t = (RADACINA / "instalator/setup.iss").read_text(encoding="utf-8")
verifica(f'#define MyAppVersion "{V}"' in t, f"setup.iss: MyAppVersion = {V}")
verifica(f"dist-v{V}" in t and f"output-v{V}" in t, "setup.iss: dist/output pe versiunea potrivită")

# 3) manifestul
manifest = json.loads((RADACINA / "versiuni.json").read_text(encoding="utf-8"))
verifica(manifest["program"]["versiune"] == V, f"versiuni.json: versiune = {V}")
verifica(
    manifest["program"]["url"].endswith(f"/v{V}/program-{V}.zip"),
    "versiuni.json: URL-ul arată la release-ul potrivit",
)

# 4) program-zip: există, valid, structură + hash + dimensiune
zip_path = RADACINA / f"program-{V}.zip"
verifica(zip_path.is_file(), f"program-{V}.zip există")
if zip_path.is_file():
    try:
        with zipfile.ZipFile(zip_path) as z:
            nume = z.namelist()
            străine = [n for n in nume if not n.startswith("dictare_transcriere_romana/") and n != "_test_audio_ro.mp3"]
            verifica(not străine, f"zip: doar „dictare_transcriere_romana/...” (străine: {străine[:3]})")
            verifica("dictare_transcriere_romana/__init__.py" in nume, "zip: __init__.py la rădăcină")
            sursă_init = z.read("dictare_transcriere_romana/constante.py").decode("utf-8")
            verifica(f'VERSIUNE = "{V}"' in sursă_init, "zip: constante.py din zip are versiunea nouă")
    except zipfile.BadZipFile:
        verifica(False, "zip: fișier corupt (nu e zip valid)")
    suma = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    verifica(suma == manifest["program"]["sha256"], "zip: SHA-256 = cel din manifest")
    verifica(zip_path.stat().st_size == manifest["program"]["dimensiune"], "zip: dimensiunea = cea din manifest")

# 5+6) instalatorul și SHA256SUMS
setup_exe = RADACINA / f"output-v{V}" / f"Setup.DTED-{V}.exe"
verifica(setup_exe.is_file(), f"Setup.DTED-{V}.exe există")
sums = (RADACINA / "SHA256SUMS.txt").read_text(encoding="ascii") if (RADACINA / "SHA256SUMS.txt").is_file() else ""
for nume in (f"Setup.DTED-{V}.exe", f"program-{V}.zip", f"portabil-DTED-{V}.zip", f"dted-{V}-linux.tar.gz"):
    verifica(nume in sums, f"SHA256SUMS.txt conține {nume}")
for nume in (f"portabil-DTED-{V}.zip", f"dted-{V}-linux.tar.gz"):
    verifica((RADACINA / nume).is_file(), f"{nume} există")

# 7) bootstrap
t = (RADACINA / "dted-bootstrap.ps1").read_text(encoding="utf-8")
verifica(f'$Tag  = "v{V}"' in t or f'$Tag = "v{V}"' in t, f"bootstrap: $Tag = v{V}")
m = re.search(rf'"Setup\.DTED-{re.escape(V)}\.exe"\s*=\s*"([0-9A-Fa-f]{{64}})"', t)
verifica(bool(m), "bootstrap: are amprenta exe-ului")
if m and setup_exe.is_file():
    suma_exe = hashlib.sha256(setup_exe.read_bytes()).hexdigest().upper()
    verifica(m.group(1).upper() == suma_exe, "bootstrap: amprenta = SHA-256 real al exe-ului")

print()
if esecuri:
    print(f"== {len(esecuri)} EȘECURI — NU SE PUBLICĂ ==")
    raise SystemExit(1)
print("== CROSS-CHECK COMPLET: totul e coerent, se poate publica ==")
