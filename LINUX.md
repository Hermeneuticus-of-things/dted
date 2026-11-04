# D&TED — varianta de Linux

Această pagină descrie starea **variantei de Linux** a programului
*Dictate & Transcription Express Digital* (D&TED). Scrie **doar ce s-a testat
efectiv** și marchează explicit tot ce rămâne netestat.

## Ce este disponibil

Programul de bază este scris în Python și folosește biblioteci cross-platform
(vezi `requirements.txt`): motorul de transcriere este
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) peste
[CTranslate2](https://github.com/OpenNMT/CTranslate2), înregistrarea audio
folosește `sounddevice`, iar interfața grafică `PySide6`. Instalarea pe Linux se
face cu scriptul existent `install.sh` (mediu Python propriu + lansator +
intrare în meniu + descărcarea modelului).

## Backend-uri: CUDA și CPU (auto-detect + trecere automată pe CPU)

La pornire, programul alege singur dispozitivul de transcriere:

1. Dacă există o placă NVIDIA cu driver CUDA detectabil prin CTranslate2
   (`ctranslate2.get_cuda_device_count() > 0`), se folosește **CUDA**
   (`compute_type="float16"`).
2. Dacă placa lipsește, sau încărcarea/folosirea CUDA dă eroare, programul
   trece **singur pe CPU** (`compute_type="float32"`), fără intervenție manuală.

Logica este implementată în `dictare_transcriere_romana/motor.py`
(`_alege_dispozitiv` + fallback-ul din `MotorWhisper.incarca`) și este expusă,
ca funcție de sine stătătoare, și în `linux/suport_linux.py`
(`alege_dispozitiv`).

> **Calea CUDA nu a fost testată pe o placă reală.** Detectarea se bazează pe
> CTranslate2 și a fost verificată doar logic (vezi „Ce s-a testat efectiv”);
> rularea efectivă pe GPU NVIDIA nu a fost verificată în momentul acestui commit.

## Ce NU este portat (specific Windows, nefuncțional pe Linux)

| Funcție | Fișier(e) | Motiv |
|---|---|---|
| Criptarea fișierelor (AES-256-GCM prin Windows CNG / `bcrypt.dll`) | `dictare_transcriere_romana/criptare.py` | `ctypes.WinDLL("bcrypt")` nu există pe Linux |
| Blocarea internetului prin Windows Firewall | `dictare_transcriere_romana/blocare.py`, `internet.py` | reguli PowerShell (`New-NetFirewallRule`) |
| Blocarea Bluetooth / USB (stocare) | `dictare_transcriere_romana/blocare.py` | comenzi PowerShell Windows |
| Verificarea driverelor Windows | `dictare_transcriere_romana/drivere.py` | API-uri Windows |
| Instalatorul Inno Setup | `instalator/setup.iss` | Inno Setup este doar Windows |

Aceste părți **nu au fost portate** și **nu au fost modificate**; pe Linux sunt
marcate ca nefuncționale în `linux/suport_linux.py`. Modulele strict Windows
(`criptare.py`, `blocare.py`, `drivere.py`, `instalator/setup.iss`) au rămas
neatinse. Singura excepție este `parola.py`, care a primit o **gardă de platformă**
la importul `criptare` (fără schimbare de comportament pe Windows) — vezi mai jos.

### Lanțul de importuri și pornirea interfeței (analiză statică din cod, **nu** rulat pe Linux)

S-a **analizat din cod** (nu prin rulare pe Linux) lanțul prin care `criptare.py`
(care încarcă `bcrypt.dll` la import, `ctypes.WinDLL`, r.39) ar putea bloca pornirea pe Linux:

* `ui_qt/principal.py` importă `securitate` la nivel de modul (r.56).
* `securitate.py` importă `internet`, `jurnal`, `sisteme` — **nu** `parola`/`criptare`.
* `parola.py` importă `criptare` (`from . import criptare`, r.28), dar **nimeni** nu
  importă `parola` la nivel de modul — doar leneș, când se folosește criptarea/parola.

Singurul `ctypes.WinDLL` la **nivel de modul** este în `criptare.py` (r.39); restul
cuplărilor Windows (`ui_drag`, `ui_comun`, `sisteme`, `blocare`, …) sunt în funcții sau
deja păzite cu `sys.platform`. **După această analiză statică**, fereastra principală
**ar porni** pe Linux (nepuțut confirmat — nu s-a rulat pe Linux real); doar folosirea
criptării ar pica.

Ca măsură de siguranță, `parola.py` importă acum `criptare` doar pe Windows; pe Linux
folosește un stub ale cărui funcții (`cripteaza_bytes`, `decripteaza_bytes`) ridică
`NotImplementedError` cu un mesaj clar. Astfel importul `parola` nu mai pune problema
nicăieri. Comportamentul pe Windows este neschimbat (verificat cu `teste/test_parola.py`,
toate cele 6 teste trec).

## Ce s-a testat efectiv

* **Verificare de sintaxă** (`py_compile`) — a trecut.
* **Teste unitare cross-platform** (fără dependență de hardware sau de Windows),
  rulată pe Windows — raportul exact e în mesajul commit-ului / la sfârșitul
  acestei lucrări.

### Rulare reală pe Linux — CONFIRMATĂ (04.11.2026)

Prima rulare efectivă pe un calculator Linux real (Omarchy / Arch, Python 3.11.17,
NVIDIA RTX PRO 4000, 16 GB VRAM). Metodă **divergent → convergent**:

**Faza divergentă** — baleiere completă a codului: **91 de apeluri Windows**
(`ctypes.windll`/`WinDLL`, `winreg`, `os.startfile`, PowerShell) în 30 de fișiere,
clasate în: păzite corect cu `este_windows()`/`sys.platform`; irelevante pe Linux
(instalator Inno, firewall, criptare CNG — documentate ca neportate); și
**negărdite în fluxul normal de pe Linux**.

**Faza convergentă** — bug-uri reale găsite, root-cause și reparare:

| # | Bug (root-cause) | Fișier | Reparare |
|---|---|---|---|
| 1 | Verificarea cerințelor respingea Linux-ul („Lipsește Windows 10/11") | `resurse.py` | cerința „os" raportează „Linux pe 64 de biți — ✔" pe platforma Linux |
| 2 | „Driverele și componentele Windows sunt în regulă" + `verifica()` rula PowerShell pe Linux | `drivere.py` | pe Linux verificarea sunetului merge prin ALSA/PipeWire (`sounddevice`); mesaj neutru („sistemului") |
| 3 | „Deschide folderul/fișierul" pică tăcut: `os.startfile` nu există pe Linux | `sisteme.py` | `_deschide_cu_sistemul()`: `xdg-open` prin `Popen`, fără așteptare (ca `startfile`) |
| 4 | „Șterge (Ctrl+Delete)" nu făcea nimic: `muta_la_gunoi` întorcea `False` pe non-Windows | `sisteme.py` | Coșul XDG Trash (`~/.local/share/Trash/files` + `.trashinfo`), recuperabil; fallback `shutil.move` între discuri |
| 5 | `proces_viu` considera orice proces „mort" pe Linux (`ctypes.windll` → `AttributeError` prins tăcut) | `blocare.py` | ramură Linux cu `os.kill(pid, 0)` (EPERM = viu, ESRCH = mort) |
| 6 | Instanța unică (cerința 44) inactivă pe Linux — mutex-ul Windows oprit de `except Exception` | `__main__.py` | blocare `flock` pe `dted-single-instance.lock` (`XDG_RUNTIME_DIR`/tmp), semantica mutex-ului |

Verificate suplimentar și **sane** (păzite deja): hotkey global, tema (fallback
„luminos"), DPI, `parola` (stub), `ui_drag` (neimportat — cod doar Windows),
`nivele`, `serviciu`.

**Rezultate măsurate pe calculatorul real:**
* Suita de teste: **98 passed, 4 skipped** (înainte de reparare: `test_marcaj` picat).
* Backend: `python -m linux.suport_linux` → „CUDA, placă NVIDIA detectată" — calea
  CUDA **confirmată pe placă reală** (RTX PRO 4000, float16; modelul
  `large-v3-turbo-ct2` încărcat pe GPU).
* Transcriere reală: 18 s de audio în limba română transcrise în ~1 s pe GPU.
* Microfon și redare: testate live (înregistrare + redare OK; microfonul sistemului
  era la 17% volum — crescut la 100%).
* Fereastra principală: pornire + captură (`DTED_CAPTURA`) — aranjament corect.
* „Deschide folder"/„Deschide fișier": testate live pe Linux (`xdg-open`) → OK.

**Rămas neportat, prin design** (ridică eroare clară, nu pice): criptarea AES
(CNG), firewall-ul, blocarea Bluetooth/USB, driverele Windows, instalatorul Inno.

**Avertisment rămas (nu blochează programul instalat):** verificarea cerințelor
raportează spațiu liber sub minim (7,9 GB < 10 GB) și LibreOffice fără componentele
românești (meniuri + dicționar).

## Cum se instalează / rulează (Linux)

Cea mai scurtă cale — o singură linie, care găsește release-ul „latest”,
verifică SHA-256 și instalează tot:

```bash
curl -fsSL https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/dted-bootstrap.sh | bash
```

Sau manual, din arhiva `dted-<versiune>-linux.tar.gz`:

```bash
./install.sh          # mediu Python + lansator + intrare în meniu + modelul
~/.local/bin/dted     # lansatorul creat de install.sh
```

`install.sh` (de la 0.6.12): se auto-corectează dacă arhiva conține linii
Windows (CRLF — defectul kitului 0.6.11), instalează la cerere biblioteca
PortAudio (necesară dictării de la microfon; pe Debian/Ubuntu `libportaudio2`,
Fedora `portaudio`, Arch `portaudio`) și pune dependențele la versiunile
testate, cu trecere automată pe versiuni compatibile dacă Pythonul local
nu are roți pentru ele.

> Notă istorică: până la repararea din PR #29, aceste instrucțiuni fuseseră
> verificate doar static (citit `install.sh`). Instalarea completă a fost
> rulată efectiv pe Arch Linux (x86_64, Python 3.11) cu scenariul kitului
> CRLF-stricat — instalare completă, exit 0.

## Verificare rapidă a backend-ului (din sursă)

```bash
python -m linux.suport_linux
```

afișează platforma și ce backend (CUDA sau CPU) ar fi ales acum, folosind
aceeași logică de detectare ca motorul de transcriere.