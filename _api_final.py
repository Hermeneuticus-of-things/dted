"""Finalizează v0.6.13 prin API: commit pe main + PR + tag la zi (fără git push)."""
import base64
import json
import subprocess
import urllib.request
from pathlib import Path

REPO = "Hermeneuticus-of-things/dted"
RADACINA = Path(".").resolve()

FISIERE = [
    "instalator/setup.iss",
    "teste/test_release_contract.py",
    "SHA256SUMS.txt",
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
    metoda_efectivă = metoda if date is not None else "GET"
    cer = urllib.request.Request(url, data=date, headers=ANTETE, method=metoda_efectivă)
    if date is not None:
        cer.add_header("Content-Type", "application/json")
    return json.loads(urllib.request.urlopen(cer, timeout=120).read().decode())


main_sha = api(f"https://api.github.com/repos/{REPO}/commits/main")["sha"]
print("main:", main_sha[:10], flush=True)

# branch-ul de update: ref nou din main
try:
    api(f"https://api.github.com/repos/{REPO}/git/refs",
        {"ref": "refs/heads/v0.6.13-final", "sha": main_sha})
    print("branch v0.6.13-final creat", flush=True)
except Exception as exc:
    print("branch există:", exc, flush=True)
    api(f"https://api.github.com/repos/{REPO}/git/refs/heads/v0.6.13-final",
        {"sha": main_sha, "force": True}, metoda="PATCH")

# blob-uri + tree peste main
intrari = []
for cale in FISIERE:
    conținut = (RADACINA / cale).read_bytes()
    blob = api(f"https://api.github.com/repos/{REPO}/git/blobs",
               {"content": base64.b64encode(conținut).decode(), "encoding": "base64"})
    intrari.append({"path": cale, "mode": "100644", "type": "blob", "sha": blob["sha"]})
main_commit = api(f"https://api.github.com/repos/{REPO}/git/commits/{main_sha}")
tree = api(f"https://api.github.com/repos/{REPO}/git/trees",
           {"base_tree": main_commit["tree"]["sha"], "tree": intrari})
commit = api(f"https://api.github.com/repos/{REPO}/git/commits", {
    "message": "v0.6.13: setup.iss + contract de release + SHA256SUMS la 0.6.13",
    "tree": tree["sha"],
    "parents": [main_sha],
})
print("commit:", commit["sha"][:10], flush=True)

# PR din branch-ul de update
corp = json.dumps({
    "title": "v0.6.13 — setup.iss + contract + SHA256SUMS la 0.6.13",
    "head": "v0.6.13-final",
    "base": "main",
    "body": "Alinierea ultimelor fișiere la 0.6.13 pentru coerența contractului de release.",
}).encode()
cer = urllib.request.Request(f"https://api.github.com/repos/{REPO}/pulls",
    data=corp, headers={**ANTETE, "Content-Type": "application/json"}, method="POST")
try:
    rasp = json.loads(urllib.request.urlopen(cer, timeout=90).read().decode())
    print("PR:", rasp["html_url"], "#", rasp["number"], flush=True)
except Exception as exc:
    print("PR există sau eroare:", exc, flush=True)
