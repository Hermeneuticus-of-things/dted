$urls = @(
    'https://download.documentfoundation.org/libreoffice/stable/26.8.1/win/x86_64/LibreOffice_26.8.1_Win_x86-64.msi',
    'https://download.documentfoundation.org/libreoffice/stable/26.8.1/win/x86_64/LibreOffice_26.8.1_Win_x86-64_helppack_ro.msi',
    'https://extensions.openoffice.org/en/download/4091'
)
$dest = $PSScriptRoot
New-Item -ItemType Directory -Force -Path $dest | Out-Null
foreach ($url in $urls) {
    $filename = [System.IO.Path]::GetFileName($url)
    if ($filename -eq '') { $filename = 'dict-ro.oxt' }
    $out = Join-Path $dest $filename
    Write-Host "Downloading $url -> $out"
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
        Write-Host "  OK: $((Get-Item $out).Length) bytes"
    } catch {
        Write-Host "  FAILED: $($_.Exception.Message)"
    }
}