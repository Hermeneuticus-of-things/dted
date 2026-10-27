"""Blocarea căilor de ieșire + supravegherea (cerințele 5 / 9 / N-3 / N-4).

Două moduri de confidențialitate, alese în Setări și vizibile permanent în bara
de sus:

* **Mod 1 — „tot”** (implicit la dictare): blochează internetul pentru TOT
  calculatorul și, în plus, stocarea USB, Bluetooth-ul și Wi-Fi-ul → indicator
  **ROȘU** („totul e tăiat”).
* **Mod 2 — „program”**: blochează internetul DOAR pentru D&TED, printr-o regulă
  Windows Firewall pe executabilul programului → indicator **PORTOCALIU**.
* Fără blocare → indicator **VERDE** (internet pornit).

Oricare ar fi modul, blocarea o face un **proces separat de supraveghere**
(„gardian”): un PowerShell pornit cu drepturi de administrator care aplică
blocarea, așteaptă închiderea programului (chiar și după o cădere), apoi
readuce totul la loc. La pornire, programul anulează orice blocare veche rămasă.

Totul este **numit și marcat cu identificatori proprii** (grupul de firewall
``D&TED-Confidentialitate`` și fișierul-marcaj), ca să găsim și să anulăm doar
ce am făcut noi, fără să atingem alte reguli sau setări. USB-ul blochează doar
**depozitarea** (driverul ``USBSTOR``), nu tastatura, mouse-ul, touchpad-ul,
microfonul sau căștile. Operațiile sunt reversibile; nu se șterge nimic.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import cai

#: Grupul sub care stau TOATE regulile noastre de firewall (ușor de anulat).
NUME_GRUP = "D&TED-Confidentialitate"

#: Valorile celor două moduri (alese în config).
MOD_TOT = "tot"          # Mod 1: tot calculatorul + USB + Bluetooth + Wi-Fi
MOD_PROGRAM = "program"  # Mod 2: doar D&TED (regulă pe executabil)

NIVEL_VERDE = "verde"
NIVEL_PORTOCALIU = "portocaliu"
NIVEL_ROSU = "rosu"


def nivelul(mod_activ: str | None) -> str:
    """Culoarea indicatorului pentru un mod dat (0/N-3, §5.2)."""
    if mod_activ == MOD_TOT:
        return NIVEL_ROSU
    if mod_activ == MOD_PROGRAM:
        return NIVEL_PORTOCALIU
    return NIVEL_VERDE


def cale_marcaj() -> Path:
    """Fișierul-marcaj care spune că există o blocare activă (și modul ei)."""
    return cai.director_instalare() / "confidentialitate.txt"


def cale_executabil() -> str:
    """Executabilul programului (același și în dev, când e interpretorul)."""
    return str(Path(sys.executable))


# --------------------------------------------------------------------------- scripturi PowerShell


def _script_blocare_mod1() -> str:
    """Blochează internetul (tot PC) + stocarea USB + Bluetooth + Wi-Fi.

    Salvează în marcaj starea de dinainte (fiecare radio + Start-ul USBSTOR),
    ca la deblocare să readucem exact acea stare.
    """
    return r"""
$ErrorActionPreference = 'SilentlyContinue'
# Salvează starea de dinainte (radiouri + USBSTOR) în marcaj, ca s-o readucem exact.
[void][Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime]
$radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetAwaiter().GetResult()
$stari_orig = @()
foreach ($radio in $radios) {
  # RadioKind: 1 = Wi-Fi, 2 = banda larga mobila, 3 = Bluetooth.
  if ([int]$radio.Kind -in 1, 2, 3) {
    $stari_orig += ("{0}:{1}" -f [int]$radio.Kind, [int]$radio.State)
  }
}
$usb_start_orig = (Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\USBSTOR' -Name 'Start' -ErrorAction SilentlyContinue).Start
if ($null -eq $usb_start_orig) { $usb_start_orig = 3 }
Add-Content -Path '__MARCAJ__' -Value ("radiouri=" + ($stari_orig -join ',')) -Encoding Ascii -ErrorAction SilentlyContinue
Add-Content -Path '__MARCAJ__' -Value ("usbstor=" + $usb_start_orig) -Encoding Ascii -ErrorAction SilentlyContinue

Remove-NetFirewallRule -Group '__GRUP__'
New-NetFirewallRule -DisplayName 'D&TED - tot calculatorul offline' -Group '__GRUP__' -Direction Outbound -Action Block -Profile Any | Out-Null
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\USBSTOR' -Name 'Start' -Value 4 -ErrorAction SilentlyContinue
foreach ($radio in $radios) {
  if ([int]$radio.Kind -in 1, 2, 3) {
    $null = $radio.SetStateAsync([Windows.Devices.Radios.RadioState]::Off).GetAwaiter().GetResult()
  }
}
"""


def _script_blocare_mod2(exe: str) -> str:
    """Blochează internetul doar pentru executabilul programului (Mod 2)."""
    return r"""
$ErrorActionPreference = 'SilentlyContinue'
Remove-NetFirewallRule -Group '__GRUP__'
New-NetFirewallRule -DisplayName 'D&TED - doar acest program offline' -Group '__GRUP__' -Direction Outbound -Action Block -Program '__EXE__' -Profile Any | Out-Null
""".replace("__EXE__", str(exe).replace("'", "''"))


def _script_deblocare() -> str:
    """Anulează TOATE blocajele noastre, refăcând exact starea salvată.

    Citește din marcaj starea de dinainte (``radiouri=...`` și ``usbstor=...``,
    scrise de ``_script_blocare_mod1``) și readuce fiecare radio (Wi-Fi, mobil,
    Bluetooth) și USBSTOR la acea valoare — nu forțează pornirea. Dacă nu e
    nimic salvat, USBSTOR revine la 3 (manual, implicit Windows), iar radiourile
    rămân neschimbate.
    """
    return r"""
$ErrorActionPreference = 'SilentlyContinue'
# Citește starea de dinainte din marcaj, înainte să-l ștergem.
$saved_radios = @{}
$saved_usb = $null
if (Test-Path '__MARCAJ__') {
  foreach ($linie in (Get-Content -Path '__MARCAJ__')) {
    $i = $linie.IndexOf('=')
    if ($i -lt 0) { continue }
    $cheie = $linie.Substring(0, $i)
    $valoare = $linie.Substring($i + 1)
    if ($cheie -eq 'radiouri') {
      foreach ($parte in ($valoare -split ',')) {
        if ($parte -match '^([0-9]+):([0-9]+)$') {
          $saved_radios[$Matches[1]] = [int]$Matches[2]
        }
      }
    }
    elseif ($cheie -eq 'usbstor') {
      $saved_usb = $valoare
    }
  }
}

Remove-NetFirewallRule -Group '__GRUP__'

# USBSTOR: refă valoarea salvată; fără valoare → 3 (manual, implicit Windows).
if ([string]::IsNullOrEmpty($saved_usb)) { $saved_usb = '3' }
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\USBSTOR' -Name 'Start' -Value ([int]$saved_usb) -ErrorAction SilentlyContinue

# Radiouri: refă starea salvată (pornit/oprit), nu forța pornirea.
[void][Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime]
$radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetAwaiter().GetResult()
foreach ($radio in $radios) {
  $kind = ([int]$radio.Kind).ToString()
  if ($saved_radios.ContainsKey($kind)) {
    $null = $radio.SetStateAsync([Windows.Devices.Radios.RadioState]$saved_radios[$kind]).GetAwaiter().GetResult()
  }
}

Remove-Item -Path '__MARCAJ__' -Force -ErrorAction SilentlyContinue
"""


def scrie_marcaj(mod: str, pid_app: int, exe: str) -> bool:
    """Scrie marcajul blocării active (în folderul de date; nu cere admin)."""
    cale = cale_marcaj()
    try:
        cale.parent.mkdir(parents=True, exist_ok=True)
        cale.write_text(
            f"mod={mod}\npid={int(pid_app)}\nexe={exe}\n",
            encoding="utf-8",
        )
        return True
    except OSError:  # pragma: no cover
        return False


def script_gardian(mod: str, pid_app: int, exe: str, marcaj: Path) -> str:
    """Scriptul gardianului: blochează, așteaptă, apoi readuce totul la loc.

    ``mod`` este ``MOD_TOT`` sau ``MOD_PROGRAM``. Gardianul rulează ridicat
    (UAC o singură dată) și trăiește independent de program; când programul
    (``pid_app``) se închide sau cade, ``Wait-Process`` se întoarce și totul
    revine la loc — fără apel din partea programului.
    """
    blocare = _script_blocare_mod1() if mod == MOD_TOT else _script_blocare_mod2(exe)
    grup = NUME_GRUP
    deblocare = _script_deblocare().replace("__GRUP__", grup).replace(
        "__MARCAJ__", _sigur_ps(str(marcaj))
    )
    return (
        "$ErrorActionPreference = 'SilentlyContinue'\r\n"
        + blocare.replace("__GRUP__", grup)
        + f"Wait-Process -Id {int(pid_app)} -ErrorAction SilentlyContinue\r\n"
        + deblocare
    )


def script_anulare(marcaj: Path) -> str:
    """Script doar pentru anulare (la pornire), fără așteptare."""
    return _script_deblocare().replace("__GRUP__", NUME_GRUP).replace(
        "__MARCAJ__", _sigur_ps(str(marcaj))
    )


def _sigur_ps(text: str) -> str:
    """Text între ghilimele simple, sigur pentru PowerShell."""
    return "'" + str(text).replace("'", "''") + "'"


# --------------------------------------------------------------------------- marcaj (citit de program)


def citeste_marcaj() -> dict[str, str] | None:
    """Citește marcajul blocării active (dacă există); ``None`` dacă nu e nimic."""
    cale = cale_marcaj()
    try:
        text = cale.read_text(encoding="utf-8")
    except OSError:
        return None
    rezultat: dict[str, str] = {}
    for linie in text.splitlines():
        if "=" in linie:
            cheie, valoare = linie.split("=", 1)
            rezultat[cheie.strip()] = valoare.strip()
    return rezultat or None


# --------------------------------------------------------------------------- procese


def proces_viu(pid: int) -> bool:
    """Adevărat dacă procesul cu ``pid`` este încă în viață (Windows)."""
    try:
        import ctypes

        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
        if not handle:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) != 0  # 0 = semnalat (mort)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:  # pragma: no cover
        return False


# --------------------------------------------------------------------------- lansare


def _ruleaza_ridicat(salt: str) -> bool:
    """Pornește un PowerShell cu drepturi de administrator (UAC), din script-salt."""
    if not cai.este_windows():
        return False
    try:
        import ctypes

        rezultat = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "powershell.exe",
            f"-NoProfile -ExecutionPolicy Bypass -File {_sigur_ps(salt)}",
            None,
            1,  # SW_SHOWNORMAL
        )
        return int(rezultat) > 32
    except Exception:  # pragma: no cover
        return False


def _scrie_si_lanseaza(script: str) -> bool:
    """Scrie scriptul într-un fișier .ps1 temporar și-l pornește ridicat."""
    cale = cai.director_instalare() / "gardian.ps1"
    try:
        cale.parent.mkdir(parents=True, exist_ok=True)
        cale.write_text(script, encoding="utf-8-sig")
    except OSError:
        return False
    return _ruleaza_ridicat(str(cale))


def blocheaza(mod: str, pid_app: int | None = None) -> bool:
    """Pornește gardianul pentru modul ``mod`` (Mod 1 sau Mod 2).

    Întoarce ``True`` dacă gardianul a fost lansat (UAC acceptat). Efectele reale
    (firewall, USB, radio) le aplică gardianul ridicat, nu acest process.
    """
    if mod not in (MOD_TOT, MOD_PROGRAM):
        raise ValueError(f"Mod necunoscut: {mod!r}")
    pid = int(pid_app) if pid_app is not None else os.getpid()
    scrie_marcaj(mod, pid, cale_executabil())
    script = script_gardian(mod, pid, cale_executabil(), cale_marcaj())
    return _scrie_si_lanseaza(script)


def deblocheaza_acum() -> bool:
    """Anulează imediat orice blocare (butonul de oprire, §9.4)."""
    return _scrie_si_lanseaza(script_anulare(cale_marcaj()))


def anuleaza_blocuri_vechi() -> bool:
    """Anulează blocările rămase de la o rulare anterioară (la pornire, §5.5)."""
    if citeste_marcaj() is None:
        return True  # nu e nimic de anulat
    return _scrie_si_lanseaza(script_anulare(cale_marcaj()))


def starea_activa() -> str | None:
    """Modul blocat acum, citit din marcaj (``None`` = nimic activ).

    Un marcaj lăsat de un proces mort nu mai înseamnă blocare: o pornire
    întreruptă sau un test lasă fișierul în urmă, iar bara ar arăta „Program
    izolat” deși nimic nu e blocat. De aceea verificăm și PID-ul.
    """
    marcaj = citeste_marcaj()
    if not marcaj:
        return None
    try:
        pid = int(marcaj.get("pid", "0"))
    except ValueError:
        return None
    if not proces_viu(pid):
        return None
    return marcaj.get("mod")