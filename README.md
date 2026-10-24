<!-- D&TED · Dictare și transcriere locală în limba română -->

<p align="center">
  <img src="dictare_transcriere_romana/iconita_dictare.png" alt="Microfonul D&TED" width="112">
</p>

<h1 align="center">D&amp;TED</h1>

<p align="center"><strong>Dictare și transcriere în limba română, direct pe calculatorul tău.</strong></p>
<p align="center">Vorbești la microfon sau alegi un fișier audio. Revizuiești textul, îl editezi și îl salvezi.</p>

<p align="center">
  <a href="https://github.com/Hermeneuticus-of-things/dted/releases"><img src="https://img.shields.io/github/v/release/Hermeneuticus-of-things/dted?include_prereleases&label=versiune&color=2563eb" alt="Versiune"></a>
  &nbsp;
  <a href="https://github.com/Hermeneuticus-of-things/dted/actions"><img src="https://img.shields.io/github/actions/workflow/status/Hermeneuticus-of-things/dted/ci.yml?label=teste&logo=github" alt="Teste"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078d4?logo=windows11" alt="Platformă">
  &nbsp;
  <img src="https://img.shields.io/badge/procesare-100%25%20local%C4%83-16a34a" alt="Procesare locală">
</p>

<p align="center">
  <a href="https://github.com/Hermeneuticus-of-things/dted/releases/tag/v0.1.2">⬇ Descarcă kitul offline · v0.1.2-beta</a>
  &nbsp;·&nbsp;
  <a href="#instalare-windows">Instalare</a>
  &nbsp;·&nbsp;
  <a href="#-ai-găsit-o-problemă">Raportează o problemă</a>
  &nbsp;·&nbsp;
  <a href="#-ce-urmează">Ce urmează</a>
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

### Noi în v0.1.2-beta

- 🎚 **Vumetru cu gradații în dB** — 0 dB înseamnă distorsiune; zona verde (-30…-6 dB) e cea bună pentru dictare, iar programul **aduce singur volumul microfonului** ca să nu se taie sunetul.
- ✅ **Setări cu bife simple** — fiecare opțiune e o singură casuță de bifat.
- 📚 **Dicționar de corecturi învățate** — corectezi un cuvânt o dată, programul îl repară singur de acum încolo (cu import/export).

<p align="center">
  <img src="docs/img/vumetru-db.png" alt="Vumetrul cu gradații dB" width="360"><br>
  <img src="docs/img/setari-sunet.png" alt="Setări → Sunet: bife + reglaj automat al microfonului" width="640">
</p>

## Date și confidențialitate

Recunoașterea vocală se face local cu Whisper prin faster-whisper și CTranslate2. Audio-ul și textul transcris nu sunt încărcate într-un serviciu cloud. Kitul publicat include componentele pentru rularea offline; descărcarea kitului și verificarea manuală a actualizărilor folosesc internetul.

În Setări poți vedea starea internetului, Wi-Fi-ului, Bluetooth-ului și a stocării externe. Există două moduri opționale de blocare:

- **„program”** blochează accesul la internet pentru D&TED prin Windows Firewall.
- **„tot”** blochează internetul pentru calculator, precum și stocarea USB, Bluetooth-ul și Wi-Fi-ul. Necesită drepturi de administrator și afectează întregul calculator.

## 🐞 Ai găsit o problemă?

Nimic de configurat, niciun cont de făcut. Programul își face singur raportul.

**Când apare o eroare**, jos în fereastră apare discret: „⚠ A apărut o problemă — trimite raportul?”. Un clic și fereastra de raport se deschide **cu detaliile tehnice deja completate** din jurnalul programului: mesajul, locul și ora erorii. Tu scrii doar, cu cuvintele tale, ce făceai în momentul acela și apeși **„Trimite pe GitHub”** — raportul ajunge direct la proiect.

Poți deschide fereastra oricând și din meniul **Ajutor → 🐞 Raportează o problemă**.

Ce trimite — și ce nu trimite — raportul:

| ✔ Se trimite | ✘ NU se trimite |
|---|---|
| Descrierea ta, cu cuvintele tale | Textul dicat sau transcris (din carte) |
| Ultimele erori din jurnal (mesaj, loc, oră) | Căile complete de pe disc (sunt scurtate: `%UTILIZATOR%`) |
| Versiunea programului și a Windows-ului | Setările, parolele, cheile, numele de utilizator |

<p align="center">
  <img src="docs/img/raport.png" alt="Fereastra „Raportează o problemă” — detaliile tehnice deja completate" width="640">
</p>

Fereastra arată **exact** ce se trimite — nimic altceva nu pleacă din calculatorul tău. Dacă preferi, ai butonul „Copiază raportul” și îl trimiți cum vrei tu (poate și ca e-mail).

---

## 🚀 Ce urmează

- 🔊 **Redarea sunetului în editor, sincronizată cu semnele [mm:ss]** — asculți exact bucata din jurul unui marcaj și o corectezi „ascultând” (cerințele 32–35).
- 📦 **Instalatorul online mic (V2)** — varianta care descarcă de pe internet doar dintr-o listă fixă de versiuni, cu sume verificate (N-7).
- 🧠 **Modelul [eek/whisper-turbo-ro-en](https://huggingface.co/eek/whisper-turbo-ro-en)** — cel mai bun raportat pe română vorbită; îl aducem ca opțiune imediat ce autorul aprobă accesul.
- 🎛 **Tur de finisaj UX**: scalare pe ecrane mici, ordinea tastării Tab/Narrator, mesajele de eroare unificate.

---

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

### Dintr-o singură comandă (cel mai simplu)

Deschide **PowerShell** (Start → tastează „powershell” → Enter), copiază rândul de mai jos, lipește cu Enter și așteaptă:

```powershell
irm https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/dted-bootstrap.ps1 | iex
```

Scriptul descarcă kitul de la versiunea fixă **v0.2.0-beta**, verifică **amprenta SHA-256 a fiecărei bucăți** (refuză instalarea dacă vreo sumă nu se potrivește — nimic nu se instalează înainte ca toate verificările să treacă) și pornește instalatorul. Nu cere drepturi de administrator.

### Sau descarcă manual kitul

Descarcă [kitul offline D&TED v0.1.1](https://github.com/Hermeneuticus-of-things/dted/releases/tag/v0.1.1). Release-ul conține `Setup.DTED.exe`, `Setup.DTED-1.bin`, `Setup.DTED-2.bin` și `SHA256SUMS.txt`.

**De ce mai multe fișiere?** Programul complet are ~4,3 GB (include modelul de transcriere, ca să meargă fără internet), iar GitHub nu acceptă fișiere mai mari de 2 GB la un download. De aceea instalatorul e tăiat în bucăți: `Setup.DTED.exe` e doar „vrăjitorul" de instalare (mesajele și butoanele), iar cele două fișiere `.bin` conțin efectiv programul. Nu porni niciodată un `.bin` — e doar un pachet citit de `Setup.DTED.exe`.

**Cum instalezi, pas cu pas:**

1. Descarcă **toate cele patru fișiere** din pagină: `Setup.DTED.exe`, `Setup.DTED-1.bin`, `Setup.DTED-2.bin` și `SHA256SUMS.txt`. (Apasă pe fiecare fișier în parte, nu pe butonul „Source code".)
2. Pune-le **pe toate în același folder** (de exemplu `Descărcări\DTED`). Dacă lipsește un `.bin`, instalatorul se oprește cu un mesaj de eroare — nimic nu se strică: completează fișierul lipsă și pornește din nou.
3. (Recomandat, dar opțional) Verifică descărcarea cu `SHA256SUMS.txt` — vezi comenzile de mai jos. Confirmă că fișierele nu s-au stricat pe drum.
4. Dă **dublu clic pe `Setup.DTED.exe`** și urmează pașii: alegere limbă → Următor → Instalează. Nu cere internet: totul e deja în pachet.
5. La final, pornește D&TED din scurtătura „D&TED – Dictare și transcriere" din meniul Start. Prima pornire verifică modelul (durează puțin).

**Cum dezinstalezi:** meniul Start → „D&TED – Dezinstalare", sau Setări → Aplicații → D&TED.

<details>
<summary>Comenzi PowerShell pentru verificarea kitului (pasul 3)</summary>

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
