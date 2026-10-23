<!-- D&TED · Dictare și transcriere locală în limba română -->

<p align="center">
  <img src="dictare_transcriere_romana/iconita_dictare.png" alt="Microfonul D&TED" width="112">
</p>

<h1 align="center">D&TED</h1>

<p align="center"><strong>Dictare și transcriere în limba română, direct pe calculatorul tău.</strong></p>
<p align="center">Vorbești la microfon sau alegi un fișier audio. Revizuiești textul, îl editezi și îl salvezi.</p>

<p align="center">
  <a href="https://github.com/Hermeneuticus-of-things/dted/releases/tag/v0.1.1">Descarcă kitul offline · v0.1.1</a>
  &nbsp;·&nbsp;
  <a href="#instalare-windows">Instalare</a>
  &nbsp;·&nbsp;
  <a href="#rulare-din-codul-sursă">Cod sursă</a>
</p>

<p align="center"><sub>Windows 10/11 · 64 de biți · Whisper large-v3-turbo · procesare locală</sub></p>

---

## De la voce la document

| 1 · Vorbești sau alegi audio | 2 · Transcriere locală | 3 · Revizuiești | 4 · Exporți |
| --- | --- | --- | --- |
| Microfon sau fișier audio | Whisper large-v3-turbo, pe CPU sau GPU NVIDIA compatibil | Editor integrat și salvare automată | DOCX, ODT, TXT, RTF, HTML, SRT sau VTT |

## Ce poți face

- **Dictezi în timp real**; textul apare pe ecran pe măsură ce vorbești.
- **Transcrii fișiere audio** MP3, WAV, M4A, OGG și FLAC.
- **Editezi și salvezi** textul în editorul integrat. Poți deschide documentul în LibreOffice Writer sau într-un alt program de scris găsit pe calculator.
- **Exporți în mai multe formate:** DOCX, ODT, TXT, RTF, HTML, SRT și VTT. Exportul PDF este disponibil din interfață și necesită LibreOffice.
- **Protejezi o înregistrare și textul ei** cu AES-256-GCM, parolă și cheie de recuperare. Parola nu este salvată.
- **Verifici calculatorul** pentru memorie, spațiu pe disc, drivere, placă video și codecuri, cu explicații în română.

## Date și confidențialitate

Recunoașterea vocală se face local cu Whisper prin faster-whisper și CTranslate2. Audio-ul și textul transcris nu sunt încărcate într-un serviciu cloud. Kitul publicat include componentele pentru rularea offline; descărcarea kitului și verificarea manuală a actualizărilor folosesc internetul.

În Setări poți vedea starea internetului, Wi-Fi-ului, Bluetooth-ului și a stocării externe. Există două moduri opționale de blocare:

- **„program”** blochează accesul la internet pentru D&TED prin Windows Firewall.
- **„tot”** blochează internetul pentru calculator, precum și stocarea USB, Bluetooth-ul și Wi-Fi-ul. Necesită drepturi de administrator și afectează întregul calculator.

## Cerințe

| | Minim | Recomandat |
| --- | --- | --- |
| Windows | Windows 10, versiunea 1809, 64 de biți | Windows 11, 64 de biți |
| Memorie | 8 GB RAM | 16 GB RAM |
| Spațiu liber | 8 GB (10 GB cu placă NVIDIA) | 20 GB |
| Placă video | Nu este necesară | NVIDIA cu cel puțin 6 GB VRAM |
| Microfon | Necesar pentru dictare | — |

Procesoarele ARM, de exemplu Snapdragon, nu sunt suportate pentru transcriere. Modurile de blocare a internetului cer drepturi de administrator.

## Instalare Windows

Descarcă [kitul offline D&TED v0.1.1](https://github.com/Hermeneuticus-of-things/dted/releases/tag/v0.1.1). Release-ul conține `Setup.DTED.exe`, `Setup.DTED-1.bin`, `Setup.DTED-2.bin` și `SHA256SUMS.txt`.

1. Descarcă cele trei fișiere ale kitului și SHA256SUMS.txt; păstrează-le în același folder.
2. Verifică amprentele SHA-256 cu lista din release.
3. Pornește `Setup.DTED.exe` numai după ce verificările sunt reușite.

<details>
<summary>Comenzi PowerShell pentru verificarea kitului</summary>

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\Downloads\DTED-kit" | Out-Null
Set-Location "$HOME\Downloads\DTED-kit"

$fisiere = @("Setup.DTED.exe", "Setup.DTED-1.bin", "Setup.DTED-2.bin")
foreach ($nume in $fisiere) {
    $rand = Get-Content .\SHA256SUMS.txt | Where-Object { $_ -match "\s+$([regex]::Escape($nume))$" }
    if (-not $rand) { throw "Nu există amprentă publicată pentru $nume" }
    $asteptat = ($rand -split '\s+')[0].ToUpper()
    $real = (Get-FileHash ".\$nume" -Algorithm SHA256).Hash.ToUpper()
    if ($real -ne $asteptat) { throw "Amprentă greșită pentru $nume" }
    "OK      $nume"
}

# Pornește instalarea numai dacă toate cele trei verificări au afișat OK
.\Setup.DTED.exe
```

</details>

<details>
<summary>Instalare asistată prin scriptul bootstrap</summary>

Scriptul `dted-bootstrap.ps1` este în codul sursă al tag-ului `v0.1.1`, dar nu este un fișier separat în release. Descarcă-l pe disc și verifică amprenta înainte de rulare; nu îl porni direct din internet cu `irm ... | iex`.

Amprenta de mai jos este pentru fișierul raw GitHub cu sfârșituri de linie LF. Copia cu CRLF are altă amprentă.

```powershell
Set-Location "$HOME\Downloads"
$url = "https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/v0.1.1/dted-bootstrap.ps1"
Invoke-WebRequest $url -OutFile .\dted-bootstrap.ps1

$asteptat = "CFA33F16AAA0E759E6D15C886C9B350B306CC004C38A42C6AE9D49E8B04A8203"
$real = (Get-FileHash .\dted-bootstrap.ps1 -Algorithm SHA256).Hash.ToUpper()
if ($real -ne $asteptat) { throw "Amprenta scriptului nu se potrivește" }

powershell -ExecutionPolicy Bypass -File .\dted-bootstrap.ps1
```

</details>

## Rulare din codul sursă

Ai nevoie de [Git](https://git-scm.com/download/win) și de [Python 3.12 pe 64 de biți](https://www.python.org/downloads/windows/).

<details>
<summary>Instalare, pregătirea modelului și transcriere din terminal</summary>

```powershell
git clone https://github.com/Hermeneuticus-of-things/dted.git
Set-Location .\dted

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Verifică acest calculator și pornește interfața
.\.venv\Scripts\python.exe pornire.py --verifica
.\.venv\Scripts\python.exe pornire.py
```

La prima pregătire din sursă, programul descarcă modelul Whisper (aproximativ 1,6 GB) de la Hugging Face, la o revizie fixă cu verificare SHA-256. Dacă ai placă NVIDIA, se descarcă și bibliotecile CUDA. E necesară o conexiune la internet pentru acest pas; îl poți porni separat:

```powershell
.\.venv\Scripts\python.exe pornire.py --pregateste
```

Exemplu fără interfață grafică:

```powershell
.\.venv\Scripts\python.exe pornire.py --transcrie .\inregistrare.mp3 --format docx
```

Formatele din terminal sunt DOCX, ODT, TXT, RTF, HTML, SRT și VTT. PDF se exportă din interfață. Pentru lista completă de opțiuni:

```powershell
.\.venv\Scripts\python.exe pornire.py --help
```

</details>

## Linux

Există o [variantă Linux documentată](LINUX.md), dar rularea aplicației pe un sistem Linux real nu a fost testată. Funcțiile specifice Windows — inclusiv criptarea și blocarea prin Windows Firewall — nu sunt portate. Calea CUDA nu a fost verificată pe o placă NVIDIA reală.

<details>
<summary>Teste și dezvoltare</summary>

Instalează `pytest` în mediul virtual și rulează testele:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q .\teste
```

Pentru verificările grafice PySide6, rulează separat `teste\_smoke_uiqt.py` și `teste\_smoke_principal.py`. `teste\_proba_transcriere.py` folosește modelul real și cere pregătirea lui cu `pornire.py --pregateste`. Unele teste din `test_baza.py`, `test_verificare.py` și `test_descarcare.py` verifică versiunea anterioară din `transcriere_locala/`; ele nu înlocuiesc probele funcțiilor actuale.

</details>

---

**Licență:** repository-ul nu are încă un fișier de licență.<br>
**Descărcări:** [toate versiunile publicate](https://github.com/Hermeneuticus-of-things/dted/releases) · [codul sursă](https://github.com/Hermeneuticus-of-things/dted)
