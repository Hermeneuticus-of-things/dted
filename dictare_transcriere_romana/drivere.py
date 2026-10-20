"""Driverele și componentele Windows de care are nevoie programul (punctul 20).

Se ocupă **doar** de drivere și de componentele Windows, niciodată de
componentele fizice (memorie, procesor, disc, sistem de operare — acelea sunt
tratate separat, în `resurse.py`).

Ce se verifică, citind de la Windows, fără căi fixe și fără nume fixe:

* driverul de sunet (dispozitive care există, dar au driver lipsă sau cu eroare);
* driverul plăcii video, **doar** dacă există o placă ce ar putea grăbi
  transcrierea (placa video este opțională: fără driver, merge procesorul);
* componentele Windows (Microsoft Visual C++ Redistributable) de care au
  nevoie Python și bibliotecile;
* alte dispozitive de sunet conectate, dar nerecunoscute.

Instalarea se face numai din surse oficiale: Windows Update (pentru drivere) și
site-ul oficial Microsoft (pentru componentele Windows), cu verificarea
semnăturii digitale acolo unde se descarcă un fișier.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import cai, jurnal, sisteme

FLAG_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Fișierele care arată că pachetul Microsoft Visual C++ Redistributable există.
FISIERE_VC = ("vcruntime140.dll", "msvcp140.dll", "vcruntime140_1.dll")

#: Linkurile oficiale Microsoft pentru pachetul Visual C++ Redistributable,
#: pe arhitecturi. Se alege cel potrivit calculatorului, nu se presupune x64.
URL_VC = {
    "x64": "https://aka.ms/vs/17/release/vc_redist.x64.exe",
    "x86": "https://aka.ms/vs/17/release/vc_redist.x86.exe",
    "arm64": "https://aka.ms/vs/17/release/vc_redist.arm64.exe",
}

#: Cheile din registru în care Windows ține minte pachetul instalat, pe arhitecturi.
CHEI_VC = {
    "x64": r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
    "x86": r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x86",
    "arm64": r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\arm64",
}

#: CUDA în PyTorch pentru Windows este folosit aici doar pe plăcile NVIDIA.
VEN_ACCELERARE = ("VEN_10DE",)

#: Cuvinte din numele plăcii care arată că poate grăbi transcrierea.
NUME_ACCELERARE = ("nvidia", "geforce", "quadro", "rtx", "tesla")

#: Cuvinte din numele plăcii care arată că driverul ei lipsește.
NUME_FARA_DRIVER = ("basic display", "afișare de bază", "adaptor de afișare standard")

#: Codul oficial Microsoft din care se descarcă pachetul, pe arhitecturi.
URL_VC_X64 = URL_VC["x64"]
URL_VC_X86 = URL_VC["x86"]
URL_VC_ARM64 = URL_VC["arm64"]

Progres = Callable[[str, float], None]


@dataclass
@dataclass
class Lipsa:
    """Un driver sau o componentă care lipsește."""

    cheie: str                    # „sunet”, „video”, „componente” sau „dispozitiv”
    dispozitiv: str               # numele pe înțeles
    ce_nu_merge: str              # ce anume nu funcționează fără el
    sursa: str = ""               # de unde se ia, exact
    poate_instala_automat: bool = False
    detalii: str = ""


@dataclass
class StareDrivere:
    """Ce s-a găsit la verificare."""

    lipsuri: list[Lipsa] = field(default_factory=list)
    sunet_ok: bool = True
    video_ok: bool = True
    componente_ok: bool = True
    producator: str = ""
    model: str = ""
    dispozitive_sunet: int = 0
    detalii_tehnice: str = ""

    @property
    def totul_ok(self) -> bool:
        return not self.lipsuri

    @property
    def blocheaza_dictarea(self) -> bool:
        return any(lipsa.cheie in ("sunet", "dispozitiv") for lipsa in self.lipsuri)

    def rezumat(self) -> str:
        if self.totul_ok:
            return "Driverele și componentele Windows sunt în regulă."
        return f"{len(self.lipsuri)} lucruri lipsesc pentru sunet, video sau componentele Windows."


# --------------------------------------------------------------------------- citiri Windows


def _powershell(cod: str, timeout: int = 45) -> str:
    """Rulează PowerShell fără fereastră și întoarce ieșirea (gol la eroare)."""
    if not cai.este_windows():
        return ""
    try:
        rezultat = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                cod,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=FLAG_NO_WINDOW,
            encoding="utf-8",
            errors="replace",
        )
        return (rezultat.stdout or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        jurnal.atentionare(f"Citirea din Windows nu a reușit: {exc}")
        return ""


def _citeste_sistemul() -> dict:
    """Citește, într-o singură rulare, ce trebuie știut despre drivere.

    Se cer și ID-urile hardware (``InstanceId``, ``PNPDeviceID``), ca o placă
    video fără driver să poată fi recunoscută după producătorul real, nu doar
    după numele pe care îl arată Windows.
    """
    cod = (
        "$date = @{};"
        "try { $date.pnp = @(Get-PnpDevice -PresentOnly -ErrorAction Stop | "
        "Select-Object FriendlyName,Class,Status,InstanceId) } catch { $date.pnp = @() };"
        "try { $date.video = @(Get-CimInstance Win32_VideoController -ErrorAction Stop | "
        "Select-Object Name,DriverVersion,DriverDate,Status,ConfigManagerErrorCode,PNPDeviceID) } "
        "catch { $date.video = @() };"
        "try { $s = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop; "
        "$date.sistem = @{ producator = $s.Manufacturer; model = $s.Model } } "
        "catch { $date.sistem = @{ producator = ''; model = '' } };"
        "$date | ConvertTo-Json -Depth 5 -Compress"
    )
    text = _powershell(cod)
    if not text:
        return {}
    try:
        date = json.loads(text)
    except json.JSONDecodeError:
        jurnal.atentionare("Răspunsul Windows nu a putut fi citit (JSON neașteptat).")
        return {}
    return date if isinstance(date, dict) else {}


def _ca_lista(ceva) -> list:
    if ceva is None:
        return []
    if isinstance(ceva, list):
        return ceva
    return [ceva]


def _folder_sistem() -> Path | None:
    """Folderul System32, cerut de la Windows (fără cale presupusă)."""
    if not cai.este_windows():
        return None
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer)):
            cale = Path(buffer.value)
            if cale.is_absolute():
                return cale
    except Exception:
        pass
    return None


def arhitectura_componente() -> str:
    """Arhitectura pachetului Visual C++ potrivit calculatorului de față."""
    arhitectura = cai.arhitectura().lower()
    if arhitectura in ("arm64",):
        return "arm64"
    if arhitectura in ("x86", "i386", "32"):
        return "x86"
    return "x64"


def componentele_windows_lipsesc() -> tuple[bool, str]:
    """Verifică dacă pachetul Visual C++ Redistributable este instalat.

    Se citește atât din fișierele din System32, cât și din registru, iar cheia
    și fișierul de instalare se aleg după arhitectura calculatorului (x64, x86
    sau arm64), nu se presupune una singură.
    """
    sistem32 = _folder_sistem()
    lipsa: list[str] = []
    if sistem32 is not None:
        lipsa = [nume for nume in FISIERE_VC if not (sistem32 / nume).exists()]
    cheie = CHEI_VC.get(arhitectura_componente(), CHEI_VC["x64"])
    inregistrat = False
    try:
        import winreg  # type: ignore[import-not-found]

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cheie) as cheia:
            valoare, _ = winreg.QueryValueEx(cheia, "Installed")
            inregistrat = bool(int(valoare))
    except Exception:
        inregistrat = False
    detalii = ""
    if lipsa:
        detalii = "Fișiere lipsă: " + ", ".join(lipsa)
    if inregistrat and not lipsa:
        return True, ""
    if not lipsa and not inregistrat:
        # Fișierele sunt acolo; probabil aduse de alt program. Îl lăsăm să meargă.
        return True, ""
    return False, detalii or "Pachetul Microsoft Visual C++ nu a fost găsit."


def producator_si_model() -> tuple[str, str]:
    """Producătorul și modelul calculatorului, citite de la Windows (fără căi fixe)."""
    date = _citeste_sistemul()
    sistem = date.get("sistem") or {}
    producator = str(sistem.get("producator") or "").strip()
    model = str(sistem.get("model") or "").strip()
    return producator, model


def _pare_dispozitiv_de_sunet(clasa: str, nume: str) -> bool:
    text = f"{clasa} {nume}".lower()
    return any(
        cuvant in text
        for cuvant in ("media", "audio", "sound", "sunet", "microfon", "microphone", "speaker", "difuzor", "headset", "căști")
    )


def _placa_poate_accelera(nume: str, id_hardware: str = "") -> bool:
    """Adevărat doar pentru plăcile care pot grăbi transcrierea.

    Se citesc și numele, și ID-ul hardware dat de Windows (de exemplu
    ``PCI\\VEN_10DE&DEV_...``), pentru că o placă fără driver apare adesea doar
    ca „Microsoft Basic Display Adapter”, fără numele producătorului.
    """
    id_mare = (id_hardware or "").upper()
    if any(cod in id_mare for cod in VEN_ACCELERARE):
        return True
    text = (nume or "").lower()
    return any(cuvant in text for cuvant in NUME_ACCELERARE)


def _fara_driver_video(nume: str, versiune: str, cod_problema: int) -> bool:
    """Adevărat dacă placa video nu are driver (sau are un driver cu eroare)."""
    text = (nume or "").lower()
    if any(cuvant in text for cuvant in NUME_FARA_DRIVER):
        return True
    if cod_problema not in (0,):
        return True
    return not (versiune or "").strip()


def dispozitive_cu_probleme(limita: int = 40) -> list[dict]:
    """Dispozitivele pe care Windows le raportează cu probleme.

    Întoarce liste cu ``nume``, ``clasa``, ``stare`` și ``id_hardware``, citite
    de la Windows. Se folosesc la potrivirea driverelor din Windows Update cu
    dispozitivul căruia îi lipsesc (nu se instalează drivere „la grămadă”).
    """
    date = _citeste_sistemul()
    rezultat: list[dict] = []
    for dispozitiv in _ca_lista(date.get("pnp")):
        if not isinstance(dispozitiv, dict):
            continue
        stare_text = str(dispozitiv.get("Status") or "").strip()
        if stare_text.lower() in ("ok", ""):
            continue
        rezultat.append(
            {
                "nume": str(dispozitiv.get("FriendlyName") or "").strip() or "dispozitiv fără nume",
                "clasa": str(dispozitiv.get("Class") or "").strip(),
                "stare": stare_text,
                "id_hardware": str(dispozitiv.get("InstanceId") or "").strip(),
            }
        )
        if len(rezultat) >= limita:
            break
    return rezultat


def _semnificativ(id_hardware: str) -> str:
    """Partea din ID-ul hardware care identifică dispozitivul (VEN_&DEV_)."""
    text = (id_hardware or "").upper()
    if "VEN_" not in text:
        return ""
    bucata = text[text.index("VEN_") :]
    if "&DEV_" in bucata:
        bucata = bucata[: bucata.index("&DEV_") + len("&DEV_") + 4]
    return bucata[:40]


def verifica() -> StareDrivere:
    """Verifică toate driverele și componentele de care depinde programul.

    Driverele video se raportează **doar** pentru plăcile care pot grăbi
    transcrierea (recunoscute după ID-ul hardware, nu doar după nume). O placă
    Intel sau AMD fără driver nu blochează nimic, deci nu se raportează.
    """
    stare = StareDrivere()
    date = _citeste_sistemul()

    pnp = _ca_lista(date.get("pnp"))
    video = _ca_lista(date.get("video"))
    sistem = date.get("sistem") or {}
    stare.producator = str(sistem.get("producator") or "").strip()
    stare.model = str(sistem.get("model") or "").strip()

    linii_detalii: list[str] = []
    dispozitive_sunet = 0
    for dispozitiv in pnp:
        if not isinstance(dispozitiv, dict):
            continue
        nume = str(dispozitiv.get("FriendlyName") or "").strip() or "dispozitiv fără nume"
        clasa = str(dispozitiv.get("Class") or "").strip()
        status = str(dispozitiv.get("Status") or "").strip()
        id_hardware = str(dispozitiv.get("InstanceId") or "").strip()
        if status.lower() in ("ok", ""):
            continue
        linii_detalii.append(f"{nume} · clasa {clasa} · stare {status} · {id_hardware}")
        if _pare_dispozitiv_de_sunet(clasa, nume):
            dispozitive_sunet += 1
            stare.sunet_ok = False
            stare.lipsuri.append(
                Lipsa(
                    cheie="sunet",
                    dispozitiv=nume,
                    ce_nu_merge="microfonul și difuzoarele",
                    sursa="Windows Update (driverele puse la dispoziție de Windows)",
                    poate_instala_automat=True,
                    detalii=f"clasa {clasa}, stare {status}, id {id_hardware}",
                )
            )

    for placa in video:
        if not isinstance(placa, dict):
            continue
        nume = str(placa.get("Name") or "").strip()
        cod = placa.get("ConfigManagerErrorCode")
        versiune = str(placa.get("DriverVersion") or "").strip()
        id_video = str(placa.get("PNPDeviceID") or "").strip()
        try:
            cod_int = int(cod) if cod is not None else 0
        except (TypeError, ValueError):
            cod_int = 0
        poate_accelera = _placa_poate_accelera(nume, id_video)
        lipseste_driverul = _fara_driver_video(nume, versiune, cod_int)
        linii_detalii.append(
            f"video: {nume} · driver {versiune or '—'} · cod {cod_int} · {id_video}"
        )
        if not poate_accelera:
            # Plăcile care nu pot grăbi transcrierea nu se raportează (punctul 20).
            continue
        if lipseste_driverul:
            stare.video_ok = False
            stare.lipsuri.append(
                Lipsa(
                    cheie="video",
                    dispozitiv=nume,
                    ce_nu_merge="accelerarea transcrierii pe placă video (fără driver, merge procesorul)",
                    sursa=(
                        "Windows Update sau site-ul oficial al producătorului plăcii video"
                    ),
                    poate_instala_automat=True,
                    detalii=f"cod problemă {cod_int}, versiune driver „{versiune}”, id {id_video}",
                )
            )

    are_componente, detalii_componente = componentele_windows_lipsesc()
    if not are_componente:
        stare.componente_ok = False
        stare.lipsuri.append(
            Lipsa(
                cheie="componente",
                dispozitiv="componentele Microsoft Visual C++ (de care au nevoie Python și Whisper)",
                ce_nu_merge="pornirea programului de transcriere",
                sursa="site-ul oficial Microsoft (pachetul Visual C++ Redistributable)",
                poate_instala_automat=True,
                detalii=detalii_componente,
            )
        )

    stare.dispozitive_sunet = dispozitive_sunet
    stare.detalii_tehnice = "\n".join(linii_detalii)
    jurnal.info(f"Verificare drivere: {stare.rezumat()}")
    for lipsa in stare.lipsuri:
        jurnal.info(f"  lipsește: {lipsa.dispozitiv} ({lipsa.detalii})")
    return stare


def rezumat_pentru_utilizator(stare: StareDrivere) -> str:
    """Textul simplu din fereastra „Lipsesc drivere”."""
    if stare.totul_ok:
        return "Toate driverele și componentele de care are nevoie programul sunt instalate."
    parti = []
    for lipsa in stare.lipsuri:
        parti.append(
            f"Lipsește driverul pentru: {lipsa.dispozitiv}.\n"
            f"Fără el nu merge: {lipsa.ce_nu_merge}.\n"
            f"De unde îl iei: {lipsa.sursa}."
        )
    return "\n\n".join(parti)


def instructiuni_de_copiat(stare: StareDrivere) -> str:
    """Instrucțiunile pe care utilizatorul le poate copia și lipi altundeva."""
    linii = [
        "Cum se rezolvă driverele care lipsesc pentru programul",
        "„Dictate & Transcription Express Digital (D&TED)” – dictare și transcriere în limba română:",
        "",
    ]
    for lipsa in stare.lipsuri:
        linii.append(f"• {lipsa.dispozitiv}")
        linii.append(f"  - fără el nu merge: {lipsa.ce_nu_merge}")
        linii.append(f"  - de unde se ia: {lipsa.sursa}")
    linii.extend(
        [
            "",
            "Pașii obișnuiți:",
            "1. Deschide „Setări Windows → Windows Update” și apasă „Verifică actualizările”.",
            "2. Deschide și „Actualizări opționale → Actualizări de drivere”.",
            "3. Instalează ce apare acolo, apoi repornește calculatorul dacă ți se cere.",
        ]
    )
    if stare.producator and stare.model:
        linii.append(
            f"4. Dacă Windows nu are driverul: caută pe site-ul oficial al producătorului "
            f"({stare.producator}) driverele pentru modelul „{stare.model}”."
        )
    linii.append("")
    linii.append("Nu descărca drivere de pe alte site-uri și nu folosi programe de tip „driver booster”.")
    return "\n".join(linii)


# --------------------------------------------------------------------------- instalare automată


def _fragmente_potrivire() -> list[str]:
    """ID-urile hardware ale dispozitivelor cu probleme, pentru potrivirea driverelor.

    Windows Update trimite, pentru fiecare driver, ID-ul hardware pentru care
    este făcut. Se instalează **doar** driverele care se potrivesc cu un
    dispozitiv care are probleme (nu toate driverele disponibile).
    """
    fragmente: list[str] = []
    for dispozitiv in dispozitive_cu_probleme():
        bucata = _semnificativ(dispozitiv.get("id_hardware", ""))
        if bucata and bucata not in fragmente:
            fragmente.append(bucata)
    return fragmente


def _script_windows_update(cale_rezultat: Path, cale_filtru: Path, doar_cauta: bool) -> str:
    """Scriptul care caută (și, la nevoie, instalează) driverele potrivite.

    Potrivirea se face după ID-ul hardware al dispozitivelor cu probleme, iar
    lista filtrelor este scrisă de program într-un fișier separat. Se folosește
    exclusiv Windows Update (serverul Microsoft).
    """
    cale = str(cale_rezultat).replace("'", "''")
    filtru = str(cale_filtru).replace("'", "''")
    cauta = "$true" if doar_cauta else "$false"
    return (
        "$ErrorActionPreference = 'Continue';"
        "$fisier = '" + cale + "';"
        "$filtru = '" + filtru + "';"
        "$doarCauta = " + cauta + ";"
        "function Scrie([string]$text) { Write-Output $text; "
        "Add-Content -LiteralPath $fisier -Value $text -Encoding UTF8 }"
        "try {"
        "  $sesiune = New-Object -ComObject Microsoft.Update.Session;"
        "  $cautator = $sesiune.CreateUpdateSearcher();"
        "  $cautator.ServerSelection = 3;"  # 3 = Windows Update (serverul Microsoft)
        "  Scrie 'Caut driverele care lipsesc în Windows Update…';"
        "  $rezultat = $cautator.Search(\"IsInstalled=0 and Type='Driver'\");"
        "  $fragmente = @(Get-Content -LiteralPath $filtru -Encoding UTF8 | "
        "Where-Object { $_.Trim() -ne '' });"
        "  $potrivite = New-Object System.Collections.ArrayList;"
        "  foreach ($u in $rezultat.Updates) {"
        "    $id = '';"
        "    try { $id = [string]$u.DriverHardwareID } catch { $id = '' };"
        "    $potrivit = $false;"
        "    foreach ($f in $fragmente) {"
        "      if ($id -and $f -and $id.ToUpper().Contains($f.ToUpper())) { $potrivit = $true }"
        "    };"
        "    if ($potrivit) { [void]$potrivite.Add($u); Scrie ('  • ' + $u.Title) }"
        "  };"
        "  if ($potrivite.Count -eq 0) { Scrie 'NICIO_ACTUALIZARE'; exit 0 }"
        "  Scrie ('POTRIVITE=' + $potrivite.Count);"
        "  Scrie 'DOAR_CAUTARE';"
        "  if ($doarCauta) { exit 0 }"
        "  $pachet = New-Object -ComObject Microsoft.Update.UpdateColl;"
        "  foreach ($u in $potrivite) {"
        "    if (-not $u.EulaAccepted) { $u.AcceptEula() };"
        "    [void]$pachet.Add($u)"
        "  };"
        "  $descarcator = $sesiune.CreateUpdateDownloader();"
        "  $descarcator.Updates = $pachet;"
        "  Scrie 'Descarc driverele…';"
        "  [void]$descarcator.Download();"
        "  $instalator = $sesiune.CreateUpdateInstaller();"
        "  $instalator.Updates = $pachet;"
        "  Scrie 'Instalez driverele…';"
        "  $instalare = $instalator.Install();"
        "  Scrie ('REZULTAT=' + $instalare.ResultCode);"  # 2 = reușit
        "  Scrie ('REPORNIRE=' + $instalare.RebootRequired);"
        "} catch {"
        "  Scrie ('EROARE=' + $_.Exception.Message)"
        "}"
    )


def _scrie_filtru(cale_filtru: Path, fragmente: list[str]) -> bool:
    """Scrie lista de ID-uri hardware pentru care se instalează drivere."""
    try:
        cale_filtru.write_text("\n".join(fragmente) + "\n", encoding="utf-8")
        return True
    except OSError as exc:
        jurnal.eroare(f"Nu am putut scrie lista de drivere potrivite: {exc}")
        return False


def drivere_din_windows_update() -> tuple[list[str], str]:
    """Caută în Windows Update driverele potrivite dispozitivelor cu probleme.

    Întoarce (lista de nume, mesaj). **Nu instalează nimic**: lista se arată
    utilizatorului, iar instalarea se face doar după ce acesta este de acord.
    """
    if not cai.este_windows():
        return [], "Instalarea driverelor se face doar pe Windows."
    fragmente = _fragmente_potrivire()
    if not fragmente:
        return [], "Nu am găsit dispozitive cu probleme pentru care Windows să aibă drivere."
    folder = cai.director_jurnale()
    folder.mkdir(parents=True, exist_ok=True)
    rezultat_cale = folder / "drivere_cautare.txt"
    filtru_cale = folder / "drivere_filtru.txt"
    script_cale = folder / "cauta_drivers.ps1"
    rezultat_cale.unlink(missing_ok=True)
    if not _scrie_filtru(filtru_cale, fragmente):
        return [], "Nu am putut pregăti căutarea driverelor."
    try:
        script_cale.write_text(
            _script_windows_update(rezultat_cale, filtru_cale, True), encoding="utf-8-sig"
        )
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_cale),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=FLAG_NO_WINDOW,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        jurnal.atentionare(f"Căutarea driverelor nu a reușit: {exc}")
        return [], "Nu am putut întreba Windows Update ce drivere sunt disponibile."
    if not rezultat_cale.exists():
        return [], "Windows Update nu a răspuns."
    try:
        linii = rezultat_cale.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [], "Răspunsul Windows Update nu a putut fi citit."
    titluri = [linie.strip()[2:].strip() for linie in linii if linie.strip().startswith("•")]
    if any("NICIO_ACTUALIZARE" in linie for linie in linii):
        return [], "Windows Update nu are niciun driver pentru dispozitivele cu probleme."
    for linie in linii:
        jurnal.info(f"drivere disponibile: {linie}")
    return titluri, ("Am găsit drivere potrivite în Windows Update." if titluri else "Windows Update nu a răspuns cu drivere.")


def progress_mesaj(linie: str) -> bool:
    """Adevărat dacă linia din jurnal merită arătată utilizatorului."""
    text = linie.strip()
    if not text:
        return False
    return not text.startswith(
        ("REZULTAT=", "REPORNIRE=", "COD=", "POTRIVITE=", "DOAR_CAUTARE", "NICIO_ACTUALIZARE")
    )


def instaleaza_din_windows_update(progres: Progres | None = None) -> tuple[bool, str, bool]:
    """Instalează driverele potrivite din Windows Update.

    Se instalează **doar** driverele care se potrivesc cu dispozitivele care au
    probleme (după ID-ul hardware), niciodată toate driverele disponibile.
    Întoarce (a reușit?, mesaj, trebuie repornire?). Instalarea se face cu
    drepturi de administrator, după ce utilizatorul își dă acordul.
    """
    if not cai.este_windows():
        return False, "Instalarea driverelor se face doar pe Windows.", False
    fragmente = _fragmente_potrivire()
    if not fragmente:
        return False, "Nu am găsit dispozitive cu probleme pentru care să se instaleze drivere.", False
    folder = cai.director_jurnale()
    folder.mkdir(parents=True, exist_ok=True)
    rezultat_cale = folder / "drivere_rezultat.txt"
    filtru_cale = folder / "drivere_filtru.txt"
    script_cale = folder / "instaleaza_drivers.ps1"
    rezultat_cale.unlink(missing_ok=True)
    if not _scrie_filtru(filtru_cale, fragmente):
        return False, "Nu am putut pregăti instalarea driverelor.", False
    try:
        script_cale.write_text(
            _script_windows_update(rezultat_cale, filtru_cale, False), encoding="utf-8-sig"
        )
    except OSError as exc:
        jurnal.eroare(f"Nu am putut scrie scriptul de drivere: {exc}")
        return False, "Nu am putut pregăti instalarea driverelor.", False

    jurnal.instalare("Cer instalarea driverelor din Windows Update (doar pentru dispozitivele cu probleme).")
    if progres:
        progres("Pregătesc instalarea driverelor din Windows Update…", 0.05)
    if not _ruleaza_elevat(script_cale):
        jurnal.atentionare("Rularea cu drepturi de administrator nu a fost acceptată.")
        return False, "Instalarea driverelor are nevoie de acordul tău (fereastra Windows).", False

    antet = "Windows Update poate dura câteva minute. "
    text = _asteapta_fisier(rezultat_cale, 1800, progres, antet)
    if not text:
        return False, "Windows Update nu a răspuns la timp.", False
    if "NICIO_ACTUALIZARE" in text:
        return False, "Windows Update nu are niciun driver nou pentru acest calculator.", False
    if "EROARE=" in text:
        return False, "Instalarea driverelor nu a reușit.", False
    repornire = "REPORNIRE=True" in text
    reusit = "REZULTAT=2" in text or "REZULTAT=3" in text
    if progres:
        progres("Instalarea driverelor s-a terminat.", 1.0)
    return reusit, ("Driverele au fost instalate." if reusit else "Windows a raportat o problemă la instalarea driverelor."), repornire


def _script_componente(cale_fisier: Path, cale_rezultat: Path) -> str:
    """Scriptul care instalează pachetul Visual C++ Redistributable.

    Instalarea se face cu drepturi de administrator și scrie rezultatul
    (codul de ieșire) într-un fișier, ca programul să știe exact când s-a
    terminat, în loc să aștepte un timp fix.
    """
    cale = str(cale_fisier).replace("'", "''")
    rezultat = str(cale_rezultat).replace("'", "''")
    return (
        "$fisier = '" + rezultat + "';"
        "function Scrie([string]$text) { Add-Content -LiteralPath $fisier -Value $text -Encoding UTF8 }"
        "$ErrorActionPreference = 'Stop';"
        "try {"
        f"  $proces = Start-Process -FilePath '{cale}' -ArgumentList '/install','/quiet','/norestart' "
        "-Wait -PassThru;"
        "  Scrie ('COD=' + $proces.ExitCode)"
        f"}} catch {{ Scrie ('EROARE=' + $_.Exception.Message) }}"
    )


def _ruleaza_elevat(script: Path) -> bool:
    """Rulează un script PowerShell cu drepturi de administrator (cere voie în Windows)."""
    try:
        import ctypes

        # -ExecutionPolicy Bypass doar pentru acest script, scris de noi, local.
        argumente = (
            f'-NoProfile -ExecutionPolicy Bypass -File "{script}"'
        )
        rezultat = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "powershell.exe", argumente, None, 1
        )
        return int(rezultat) > 32
    except Exception as exc:
        jurnal.atentionare(f"Nu am putut porni scriptul cu drepturi de administrator: {exc}")
        return False


def _asteapta_fisier(cale: Path, secunde: int, progres: Progres | None = None, mesaj: str = "") -> str:
    """Așteaptă ca un alt program să termine și să scrie rezultatul."""
    inceput = time.time()
    ultima_linie = 0
    while time.time() - inceput < secunde:
        if progres and mesaj:
            trecut = int(time.time() - inceput)
            progres(f"{mesaj} ({trecut // 5 * 5} secunde)", min(0.9, trecut / max(1, secunde)))
        if cale.exists():
            try:
                linii = cale.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                linii = []
            if linii and len(linii) > ultima_linie:
                for linie in linii[ultima_linie:]:
                    jurnal.info(f"drivere: {linie}")
                    if progress_mesaj(linie) and progres:
                        progres(linie, min(0.95, 0.2 + 0.7 * min(1.0, len(linii) / 10)))
                ultima_linie = len(linii)
            continut = "\n".join(linii)
            if "REZULTAT=" in continut or "COD=" in continut or "EROARE=" in continut or "NICIO_ACTUALIZARE" in continut:
                return continut
        time.sleep(1.0)
    return ""


def _semnatura_ok(cale: Path) -> bool:
    """Verifică dacă un fișier descărcat este semnat de Microsoft."""
    cod = (
        f"$s = Get-AuthenticodeSignature -FilePath '{str(cale).replace(chr(39), chr(39) * 2)}';"
        "Write-Output ($s.Status.ToString() + '|' + $s.SignerCertificate.Subject)"
    )
    text = _powershell(cod, timeout=30)
    if not text or "|" not in text:
        return False
    stare, _, semnatar = text.partition("|")
    ok_stare = stare.strip().lower() == "valid"
    ok_semnatar = "microsoft" in semnatar.lower()
    if not (ok_stare and ok_semnatar):
        jurnal.atentionare(f"Semnătura fișierului {cale.name}: {stare} / {semnatar.strip()}")
    return ok_stare and ok_semnatar


def instaleaza_componente_windows(progres: Progres | None = None) -> tuple[bool, str]:
    """Instalează pachetul Microsoft Visual C++ Redistributable, din sursa oficială.

    Fișierul se descarcă de pe linkul oficial Microsoft, se verifică semnătura
    digitală (Microsoft) și abia apoi se rulează. Fără semnătură validă, nu se
    instalează nimic.
    """
    from .descarcare import EroareDescarcare, descarca
    from .internet import are_internet

    if not are_internet():
        return False, "Pentru această componentă este nevoie de internet."

    arhitectura = arhitectura_componente()
    url = URL_VC.get(arhitectura, URL_VC["x64"])
    tinta = cai.director_descarcari() / Path(url).name
    if progres:
        progres("Descarc componentele Microsoft de care are nevoie programul…", 0.1)
    try:
        descarca(url, tinta, None, None)
    except EroareDescarcare as exc:
        return False, f"Descărcarea componentelor Microsoft nu a reușit: {exc}"

    if not _semnatura_ok(tinta):
        jurnal.eroare(f"Semnătura fișierului {tinta.name} nu este validă; nu îl instalez.")
        return False, "Fișierul descărcat nu are semnătura Microsoft, așa că nu a fost instalat."

    jurnal.instalare(f"Instalez componentele Microsoft din {tinta.name} (pentru {arhitectura}).")
    if progres:
        progres("Instalez componentele Microsoft…", 0.5)
    folder = cai.director_jurnale()
    folder.mkdir(parents=True, exist_ok=True)
    rezultat_cale = folder / "componente_rezultat.txt"
    rezultat_cale.unlink(missing_ok=True)
    script_cale = folder / "instaleaza_componente.ps1"
    try:
        script_cale.write_text(
            _script_componente(tinta, rezultat_cale), encoding="utf-8-sig"
        )
    except OSError as exc:
        return False, f"Nu am putut pregăti instalarea: {exc}"
    if not _ruleaza_elevat(script_cale):
        return False, "Instalarea are nevoie de acordul tău (fereastra Windows)."
    if progres:
        progres("Aștept terminarea instalării…", 0.7)
    text = _asteapta_fisier(rezultat_cale, 1800, progres, "Instalez componentele Microsoft. ")
    if not text:
        return False, "Instalarea componentelor Microsoft nu s-a terminat la timp."
    if "EROARE=" in text:
        jurnal.atentionare(f"Instalarea componentelor a raportat: {text.strip()}")
        return False, "Instalarea componentelor Microsoft nu a reușit."
    cod = ""
    for linie in text.splitlines():
        if linie.strip().startswith("COD="):
            cod = linie.strip().split("=", 1)[1]
    # 0 = instalat; 1638 = există deja o versiune mai nouă; 3010 = cere repornire.
    if cod in ("0", "1638", "3010"):
        if componentele_windows_lipsesc()[0]:
            if progres:
                progres("Componentele Microsoft au fost instalate.", 1.0)
            return True, "Componentele Microsoft au fost instalate."
        if cod == "3010":
            return True, "Componentele Microsoft s-au instalat. Repornește calculatorul ca să fie folosite."
        return False, "Componentele Microsoft s-au instalat, dar fișierele lor nu se văd încă. Încearcă din nou după repornire."
    return False, f"Instalarea componentelor Microsoft a raportat codul {cod or 'necunoscut'}."


def deschide_windows_update() -> bool:
    """Deschide pagina Windows Update din setările Windows."""
    return sisteme.deschide_setare("ms-settings:windowsupdate")


def deschide_windows_update_optional() -> bool:
    """Deschide „Actualizări opționale”, acolo unde stau driverele."""
    return sisteme.deschide_setare("ms-settings:windowsupdate-optionalupdates")


def model_pentru_cautare() -> str:
    """Textul prietenos cu producătorul și modelul, pentru căutarea driverelor."""
    producator, model = producator_si_model()
    if producator and model:
        return f"{producator} · {model}"
    if model:
        return model
    return "calculatorul acesta"
