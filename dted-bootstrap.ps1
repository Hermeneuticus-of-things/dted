# Instalare de la ultima versiune publicata pe GitHub.
# Folosire: irm https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/dted-bootstrap.ps1 | iex

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Repo = "Hermeneuticus-of-things/dted"
$ApiUrl = "https://api.github.com/repos/$Repo/releases/latest"
$Dest = Join-Path $env:TEMP "dted-install"
$Headers = @{
    Accept = "application/vnd.github+json"
    "User-Agent" = "DTED-Bootstrap/1.0"
}

Write-Host "D&TED — caut ultima versiune publicata..." -ForegroundColor Cyan
$Release = Invoke-RestMethod -Uri $ApiUrl -Headers $Headers
if ($Release.draft -or $Release.prerelease -or $Release.tag_name -notmatch '^v(\d+\.\d+\.\d+)$') {
    throw "GitHub nu a returnat un release stabil D&TED cu eticheta v<versiune>."
}

$Versiune = $Matches[1]
$PachetExe = "Setup.DTED-$Versiune.exe"
$Pachete = @($Release.assets | Where-Object {
    $_.name -eq $PachetExe -or $_.name -match (
        '^Setup\.DTED-' + [regex]::Escape($Versiune) + '-\d+\.bin$'
    )
})
$Exe = @($Pachete | Where-Object { $_.name -eq $PachetExe })
$Sume = @($Release.assets | Where-Object { $_.name -eq "SHA256SUMS.txt" })
if ($Exe.Count -ne 1 -or $Sume.Count -ne 1) {
    throw "Release-ul $($Release.tag_name) nu contine instalatorul si SHA256SUMS.txt asteptate."
}

$Pachete = @($Exe) + @($Pachete | Where-Object { $_.name -ne $PachetExe } | Sort-Object name)
if (-not (Test-Path $Dest)) {
    New-Item -ItemType Directory -Path $Dest | Out-Null
}

$FisierSume = Join-Path $Dest "SHA256SUMS.txt"
Invoke-WebRequest -Uri $Sume[0].browser_download_url -OutFile $FisierSume -UseBasicParsing
$LiniiSume = Get-Content -Path $FisierSume

foreach ($Pachet in $Pachete) {
    if ($Pachet.name -notmatch '^Setup\.DTED-[\d.]+(?:-\d+)?\.(?:exe|bin)$') {
        throw "Nume de asset neasteptat in release: $($Pachet.name)"
    }

    $NumeEscapat = [regex]::Escape($Pachet.name)
    $LiniiPotrivite = @($LiniiSume | Where-Object {
        $_ -match ('^\s*[0-9a-fA-F]{64}\s+\*?' + $NumeEscapat + '\s*$')
    })
    if ($LiniiPotrivite.Count -ne 1) {
        throw "SHA-256 lipsa sau duplicat pentru $($Pachet.name) in SHA256SUMS.txt."
    }
    $AmprentaAsteptata = [regex]::Match(
        $LiniiPotrivite[0], '^\s*([0-9a-fA-F]{64})'
    ).Groups[1].Value.ToUpperInvariant()

    $Cale = Join-Path $Dest $Pachet.name
    Write-Host "  se descarca $($Pachet.name)..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $Pachet.browser_download_url -OutFile $Cale -UseBasicParsing
    $AmprentaReala = (Get-FileHash -Path $Cale -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($AmprentaReala -ne $AmprentaAsteptata) {
        Remove-Item -LiteralPath $Cale -Force -ErrorAction SilentlyContinue
        throw "Verificarea SHA-256 a esuat pentru $($Pachet.name); instalarea a fost refuzata."
    }
    Write-Host "  SHA-256 verificat: $($Pachet.name)" -ForegroundColor Green
}

Write-Host "Pornesc D&TED $Versiune..." -ForegroundColor Cyan
Push-Location $Dest
try {
    Start-Process -FilePath (Join-Path $Dest $PachetExe) -Wait
}
finally {
    Pop-Location
}
