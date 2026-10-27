# ============================================================================
#  D&TED — Dictare și transcriere expresă digitală
#  Instalare dintr-o singură comandă, de la o etichetă de versiune fixă, cu
#  verificarea amprentei SHA-256.
#
#  Folosire (ferestre PowerShell):
#     irm https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/dted-bootstrap.ps1 | iex
#
#  Scriptul, pas cu pas:
#    1. descarcă instalatorul (împărțit în bucăți mai mici de 2 GB) de la eticheta
#       fixă v0.1.0;
#    2. verifică amprenta SHA-256 pentru FIECARE bucată (amprentele sunt scrise
#       mai jos, în acest script);
#    3. REFUZĂ instalarea dacă vreo amprentă nu se potrivește;
#    4. pornește instalatorul Inno (acesta își găsește singur bucățile .bin din
#       același dosar).
#
#  Scriptul nu modifică nimic pe calculator înainte ca toate amprentele să fi
#  fost verificate una câte una.
# ============================================================================

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # descărcare mai iute în PowerShell 5.1

# Etichetă de versiune FIXĂ (nu „ultima versiune" — fiecare publicare are eticheta ei).
$Tag  = "v0.6.3"
$Repo = "Hermeneuticus-of-things/dted"
$Base = "https://github.com/$Repo/releases/download/$Tag"
$Dest = Join-Path $env:TEMP "dted-install"

# ----------------------------------------------------------------------------
# Amprentele SHA-256 sunt închise AICI, în script (eticheta fixă v0.6.3).
# Rândul: "nume fișier" = "amprenta". Ordinea: întâi instalatorul .exe, apoi
# bucățile .bin în ordine (Setup DTED-1.bin, -2.bin, ...).
# AMPRENTELE SE CALCULEAZĂ pe fișierele construite și se schimbă la FIECARE
# versiune — niciodată nu se lasă amprentele versiunii precedente.
# ----------------------------------------------------------------------------
$Pachete = [ordered]@{
    "Setup.DTED-0.6.3.exe" = "D99DD6A1F4621128F09B188CFC066580A0D664A355CEAC05D64DCFE7D1CDD76D"
}

function Format-Amprenta { param([string]$s) ($s -replace '[^0-9a-fA-F]', '').ToUpper() }

Write-Host ""
Write-Host ("D&TED — instalare de la {0} (etichetă de versiune fixă)" -f $Tag) -ForegroundColor Cyan

if (-not (Test-Path $Dest)) { New-Item -ItemType Directory -Path $Dest | Out-Null }

# Alege instalatorul (.exe) din manifest.
$exeName = $Pachete.Keys | Where-Object { $_ -match '\.exe$' } | Select-Object -First 1
if (-not $exeName) { throw "Manifestul nu conține instalatorul (.exe)!" }

foreach ($num in $Pachete.Keys) {
    $asteptat = Format-Amprenta $Pachete[$num]
    if ($asteptat.Length -ne 64) { throw ("Amprentă greșită în manifest pentru '{0}'." -f $num) }

    $url = $Base + "/" + ([uri]::EscapeDataString($num))
    $out = Join-Path $Dest $num
    Write-Host ("  se descarcă  {0} ..." -f $num) -ForegroundColor Gray
    Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing

    $real = (Get-FileHash -Path $out -Algorithm SHA256).Hash.ToUpper()
    if ($real -ne $asteptat) {
        Remove-Item $out -Force -ErrorAction SilentlyContinue
        throw (("VERIFICAREA AMPRENTEI SHA-256 A EȘUAT pentru '{0}':`n" + `
               "  așteptat: {1}`n" + `
               "  primit:   {2}`n" + `
               "Instalarea a fost REFUZATĂ (fișier stricat ori alterat).") -f $num, $asteptat, $real)
    }
    Write-Host ("  în regulă  {0}  (amprenta SHA-256 se potrivește)" -f $num) -ForegroundColor Green
}

$exePath = Join-Path $Dest $exeName
Write-Host ""
Write-Host "Toate bucățile au fost verificate. Se pornește instalatorul..." -ForegroundColor Cyan
Push-Location $Dest
try { Start-Process -FilePath $exePath -Wait } finally { Pop-Location }
Write-Host "D&TED — instalarea a pornit." -ForegroundColor Green

