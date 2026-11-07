import hashlib, re
from pathlib import Path

fisiere = [
    "output-v0.6.13/Setup.DTED-0.6.13.exe",
    "program-0.6.13.zip",
    "portabil-DTED-0.6.13.zip",
    "dted-0.6.13-linux.tar.gz",
]
sume = {}
linii = []
for cale in fisiere:
    p = Path(cale)
    suma = hashlib.sha256(p.read_bytes()).hexdigest().upper()
    sume[p.name] = suma
    linii.append(f"{suma}  {p.name}")
    print(suma[:16], p.name, f"{p.stat().st_size:,} B")
Path("SHA256SUMS.txt").write_text("\n".join(linii) + "\n", encoding="ascii")

# bootstrap nou (dinamic, fără tag hardcodat) — doar confirmăm că folosește releases/latest + SHA256SUMS
sablon = Path("dted-bootstrap.ps1").read_text(encoding="utf-8")
assert "releases/latest" in sablon and "SHA256SUMS.txt" in sablon
assert f"Setup.DTED-0.6.13.exe" not in sablon  # fără nume hardcodat
print("bootstrap OK (dinamic, latest + SHA256SUMS)")
