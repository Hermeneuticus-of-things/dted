# D&TED – Dictate & Transcription Express Digital

**Dictare și transcriere în limba română**

D&TED este un program pentru Windows care transformă vocea în text, în limba română.
Poți dicta direct la microfon sau poți da programului un fișier audio, iar el scrie textul.
Totul se face **pe calculatorul tău**: după instalare, programul nu are nevoie de internet
și nu trimite nimic nicăieri.

> **Stare: v0.1.0 – cod sursă, în dezvoltare.**
> Această versiune conține doar codul sursă. Kitul offline, instalatorul online și scriptul
> de pornire PowerShell **nu sunt publicate încă** (vezi mai jos).

## Ce face

- **Dictare** de la microfon, cu textul afișat pe ecran pe măsură ce vorbești.
- **Transcriere de fișiere audio** (MP3, WAV, M4A, OGG, FLAC).
- **Recunoaștere locală a vorbirii** cu modelul Whisper `large-v3-turbo` (prin faster-whisper / CTranslate2).
  Dacă există o placă video NVIDIA potrivită, este folosită automat; altfel merge pe procesor.
- **Salvare în mai multe formate:** DOCX, ODT, TXT, RTF, HTML, subtitrări SRT și VTT; PDF prin LibreOffice.
- **Editor de text** integrat și deschidere a documentelor în LibreOffice Writer (sau în alt program de scris găsit pe calculator).
- **Moduri de confidențialitate**, alese în Setări și afișate permanent în bara de sus:
  - **„tot”** – oprește internetul pentru tot calculatorul, plus stocarea USB, Bluetooth-ul și Wi-Fi-ul (indicator roșu);
  - **„program”** – blochează internetul doar pentru D&TED, printr-o regulă Windows Firewall (indicator portocaliu);
  - fără blocare – indicator verde.
- **Supraveghere** a căilor prin care ar putea ieși date: internet, Wi-Fi, Bluetooth, stick/card/disc extern.
- **Criptare** a fișierelor salvate (sunet + text) cu AES-256-GCM (Windows CNG), cu parolă
  și cheie de recuperare. Parola nu se salvează nicăieri.
- **Nimic nu se pierde:** textul se salvează automat, iar programul întreabă înainte să înlocuiască textul de pe ecran.
- **Verificarea calculatorului** (memorie, disc, drivere, placă video, codecuri) și mesaje în română simplă.
- **Actualizări opționale**, doar la apăsarea butonului „Caută actualizări”, cu verificare SHA-256.

## Cerințe de sistem

| | Minim | Recomandat |
|---|---|---|
| Sistem | Windows 10 versiunea 1809, 64 de biți | Windows 11, 64 de biți |
| Memorie (RAM) | 8 GB | 16 GB |
| Spațiu pe disc | 8 GB (10 GB cu placă NVIDIA) | 20 GB |
| Placă video | opțională | NVIDIA cu cel puțin 6 GB memorie video |
| Microfon | necesar pentru dictare | – |

Procesoarele ARM (de exemplu Snapdragon) nu sunt suportate pentru transcriere.
Pentru modurile de blocare a internetului, programul cere drepturi de administrator.

## Instalare

Există (sau vor exista) trei variante. Toate fișierele vor fi publicate pe pagina
[Releases](https://github.com/Hermeneuticus-of-things/dted/releases), împreună cu un fișier
`SHA256SUMS.txt` care conține amprenta SHA-256 a fiecărui fișier.

**Verifică întotdeauna amprenta SHA-256 înainte să rulezi ceva descărcat de pe internet.**

### Varianta 1 – Kit offline complet (4–5 GB)

> **În pregătire – comenzile vor funcționa după publicarea fișierului în Releases.**

Kitul conține tot: programul, modelul de transcriere și bibliotecile pentru placa video.
După descărcare nu mai este nevoie de internet, nici la instalare, nici la prima pornire.
Pentru că GitHub acceptă fișiere de cel mult 2 GB, kitul va fi împărțit în
`DTED-Setup-v0.1.0.exe` și mai multe fișiere `DTED-Setup-v0.1.0-*.bin`, care trebuie să stea în același folder.

Pașii, în Windows PowerShell:

```powershell
# 1. Fă un folder pentru kit și intră în el
New-Item -ItemType Directory -Force -Path "$HOME\Downloads\DTED-kit" | Out-Null
Set-Location "$HOME\Downloads\DTED-kit"

# 2. Descarcă lista de amprente și fișierele kitului
$baza = "https://github.com/Hermeneuticus-of-things/dted/releases/download/v0.1.0"
Invoke-WebRequest "$baza/SHA256SUMS.txt" -OutFile .\SHA256SUMS.txt
Invoke-WebRequest "$baza/DTED-Setup-v0.1.0.exe" -OutFile .\DTED-Setup-v0.1.0.exe
# descarcă la fel fiecare fișier DTED-Setup-v0.1.0-*.bin trecut în SHA256SUMS.txt

# 3. Verifică amprenta fiecărui fișier (trebuie să scrie OK la toate)
Get-Content .\SHA256SUMS.txt | ForEach-Object {
    $suma, $nume = $_ -split '\s+\*?', 2
    if (Test-Path $nume) {
        $real = (Get-FileHash ".\$nume" -Algorithm SHA256).Hash
        if ($real -eq $suma.ToUpper()) { "OK      $nume" } else { "GREȘIT  $nume" }
    }
}

# 4. Pornește instalarea (doar dacă toate sunt OK)
.\DTED-Setup-v0.1.0.exe
```

Poți verifica și un singur fișier:

```powershell
Get-FileHash .\DTED-Setup-v0.1.0.exe -Algorithm SHA256
```

și compari valoarea cu cea publicată în release.

### Varianta 2 – Instalator online mic, cu listă fixă de versiuni

> **În pregătire – comenzile vor funcționa după publicarea fișierului în Releases.**

Un instalator mic, care descarcă în timpul instalării doar componentele dintr-o listă fixă
de versiuni, fiecare verificată cu SHA-256. Ai nevoie de internet în timpul instalării.

```powershell
Set-Location "$HOME\Downloads"
$baza = "https://github.com/Hermeneuticus-of-things/dted/releases/download/v0.1.0"
Invoke-WebRequest "$baza/DTED-Setup-online-v0.1.0.exe" -OutFile .\DTED-Setup-online-v0.1.0.exe

# Verifică amprenta și compar-o cu valoarea publicată în release (SHA256SUMS.txt)
Get-FileHash .\DTED-Setup-online-v0.1.0.exe -Algorithm SHA256

# Rulează instalatorul doar dacă amprenta se potrivește
.\DTED-Setup-online-v0.1.0.exe
```

### Varianta 3 – Script PowerShell de pornire (bootstrap), de la un tag fix

> **În pregătire – comenzile vor funcționa după publicarea fișierului în Releases.**

Un script PowerShell descărcat de la tag-ul fix `v0.1.0`, care aduce și instalează programul.
Scriptul se descarcă **întâi pe disc**, i se verifică amprenta, și abia apoi se rulează.
Nu rula scriptul direct din internet (de exemplu cu `irm ... | iex`), fără verificare.

```powershell
Set-Location "$HOME\Downloads"
$url = "https://github.com/Hermeneuticus-of-things/dted/releases/download/v0.1.0/dted-bootstrap.ps1"
Invoke-WebRequest $url -OutFile .\dted-bootstrap.ps1

# Verifică amprenta și compar-o cu valoarea publicată în release (SHA256SUMS.txt)
Get-FileHash .\dted-bootstrap.ps1 -Algorithm SHA256

# Rulează scriptul doar dacă amprenta se potrivește
powershell -ExecutionPolicy Bypass -File .\dted-bootstrap.ps1
```

## Rulare din codul sursă (funcționează acum)

Ai nevoie de [Git](https://git-scm.com/download/win) și de
[Python 3.12 pe 64 de biți](https://www.python.org/downloads/windows/)
(bifează „Add python.exe to PATH” la instalare).

```powershell
# 1. Descarcă codul
git clone https://github.com/Hermeneuticus-of-things/dted.git
Set-Location .\dted

# 2. Fă un mediu Python separat
py -3.12 -m venv .venv

# 3. Instalează bibliotecile (versiuni fixe)
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 4. Verifică ce are calculatorul (fără ferestre)
.\.venv\Scripts\python.exe pornire.py --verifica

# 5. Pornește programul
.\.venv\Scripts\python.exe pornire.py
```

La prima pornire din sursă, programul descarcă modelul de transcriere (aproximativ 1,6 GB)
de pe Hugging Face, la o revizie fixă, cu verificare SHA-256, iar dacă ai placă NVIDIA,
și bibliotecile CUDA. Pentru asta e nevoie de internet o singură dată. Poți face pasul acesta
și separat:

```powershell
.\.venv\Scripts\python.exe pornire.py --pregateste
```

Alte opțiuni utile:

```powershell
# Transcrie un fișier fără interfață (formate: docx, odt, txt, srt, vtt)
.\.venv\Scripts\python.exe pornire.py --transcrie .\inregistrare.mp3 --format docx

# Lista completă de opțiuni
.\.venv\Scripts\python.exe pornire.py --help
```

## Structura proiectului

- `dictare_transcriere_romana/` – programul (interfața PySide6 este în `ui_qt/`)
- `pornire.py` – punctul de pornire
- `teste/` – teste automate
- `instalator/` – scriptul Inno Setup (`setup.iss`) pentru instalatorul Windows
- `dictare.spec` – configurarea PyInstaller pentru programul construit
- `transcriere_locala/` – versiunea anterioară a programului, păstrată pentru teste

## Descărcări

Toate versiunile publicate sunt pe pagina
[Releases](https://github.com/Hermeneuticus-of-things/dted/releases).
