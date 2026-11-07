"""Creează commit-ul v0.6.13 prin API GitHub (blob-uri -> tree -> commit -> ref)."""
import base64
import json
import subprocess
import urllib.request
from pathlib import Path

REPO = "Hermeneuticus-of-things/dted"
RADACINA = Path(".").resolve()

FISIERE = [
    "README.md",
    "dictare_transcriere_romana/constante.py",
    "dictare_transcriere_romana/ui_qt/comun.py",
    "dictare_transcriere_romana/ui_qt/focus_motor.py",
    "dictare_transcriere_romana/ui_qt/principal.py",
    "dictare_transcriere_romana/ui_qt/ui_mini.py",
    "dictare_transcriere_romana/ui_qt/ui_raport.py",
    "dictare_transcriere_romana/ui_qt/ui_setari.py",
    "instalator/setup.iss",
    "teste/test_focus_motor.py",
    "teste/test_release_contract.py",
]


def token():
    r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True, timeout=30)
    for linie in r.stdout.splitlines():
        if linie.startswith("password="):
            return linie.split("=", 1)[1].strip()


TOKEN = token()
ANTETE = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "User-Agent": "DTED-API/1.0"}


def api(url, corp=None, metoda="GET"):
    date = json.dumps(corp).encode() if corp is not None else None
    metoda_efectivă = metoda if date is not None and metoda != "GET" else ("GET" if date is None else "POST")
    cer = urllib.request.Request(url, data=date, headers=ANTETE, method=metoda_efectivă)
    if date is not None:
        cer.add_header("Content-Type", "application/json")
    return json.loads(urllib.request.urlopen(cer, timeout=120).read().decode())


main_sha = api(f"https://api.github.com/repos/{REPO}/commits/main")["sha"]
print("main:", main_sha[:10], flush=True)

# blob-uri
intrari = []
for cale in FISIERE:
    conținut = (RADACINA / cale).read_bytes()
    blob = api(f"https://api.github.com/repos/{REPO}/git/blobs",
               {"content": base64.b64encode(conținut).decode(), "encoding": "base64"})
    intrari.append({"path": cale, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    print("blob:", cale, flush=True)

# tree: bază = tree-ul main-ului, cu intrările schimbate peste
main_commit = api(f"https://api.github.com/repos/{REPO}/git/commits/{main_sha}")
tree_bază = main_commit["tree"]["sha"]
tree = api(f"https://api.github.com/repos/{REPO}/git/trees",
           {"base_tree": tree_bază, "tree": intrari})
print("tree:", tree["sha"][:10], flush=True)

commit = api(f"https://api.github.com/repos/{REPO}/git/commits", {
    "message": ("v0.6.13: Ionuț ADL complet — motorul de focus formal (focus_motor.py: registru, "
                "stivă, rutare comenzi divergent->convergent, onFocus/onBlur exact); etichete SR "
                "complete pe toate controalele (comun.completeaza_accesibilitate); focus ring 2px; "
                "transport fără focus-steal; Setări dialog modal în stivă; 150 teste"),
    "tree": tree["sha"],
    "parents": [main_sha],
})
print("commit:", commit["sha"][:10], flush=True)

try:
    ref = api(f"https://api.github.com/repos/{REPO}/git/refs",
              {"ref": "refs/heads/v0.6.13-adl-motor", "sha": commit["sha"]})
    print("ref creat:", ref["ref"], flush=True)
except Exception as exc:
    # branch-ul poate exista deja: actualizează-l
    print("update ref:", exc, flush=True)
    api(f"https://api.github.com/repos/{REPO}/git/refs/heads/v0.6.13-adl-motor",
        {"sha": commit["sha"], "force": True}, metoda="PATCH")
    print("ref actualizat", flush=True)


# PR-ul
import subprocess

TOKEN2 = token()
ANTETE2 = {"Authorization": f"token {TOKEN2}", "Accept": "application/vnd.github+json", "User-Agent": "DTED-API/1.0"}
corp = json.dumps({
    "title": "v0.6.13 — Ionuț ADL complet: motor de focus formal + etichete SR pe toate controalele",
    "head": "v0.6.13-adl-motor",
    "base": "main",
    "body": (
        "- `focus_motor.py` (nou): registru de suprafețe cu id-uri ADL, stivă per fereastră, "
        "push/switch/scoate cu onFocus/onBlur exact, rutarea comenzilor divergent→convergent "
        "(suprafața activă → părinte → rădăcină).
"
        "- Aplicația e în motorul de focus: editorul activ la pornire, ecranele comută suprafața, "
        "Setările e dialog modal în stivă.
"
        "- Etichete SR complete: `comun.completeaza_accesibilitate` dă nume accesibile tuturor "
        "controalelor (button/checkbox/slider/field), apelat pe fereastra principală, Setări, Mini, Raport.
"
        "- Focus ring 2 px în QSS (ambele teme); transport fără focus-steal.
"
        "- 150 teste locale verzi, inclusiv 4 noi pentru motor și accesibilitate."
    ),
}).encode()
cer2 = urllib.request.Request("https://api.github.com/repos/Hermeneuticus-of-things/dted/pulls",
    data=corp, headers={**ANTETE2, "Content-Type": "application/json"}, method="POST")
try:
    rasp = json.loads(urllib.request.urlopen(cer2, timeout=90).read().decode())
    print("PR:", rasp["html_url"], "#", rasp["number"], flush=True)
except Exception as exc:
    print("PR există sau eroare:", exc, flush=True)
print("API-PUSH-COMPLET", flush=True)
