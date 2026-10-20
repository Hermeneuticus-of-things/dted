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
* **NU s-a testat rularea efectivă pe Linux.** Pe mașina de dezvoltare nu există un
  mediu Linux funcțional: WSL este **dezactivat** (`Wsl/ERROR_SERVICE_DISABLED`) și
  Docker lipsește. **Nu le-am activat/instalat** (ar fi cerut confirmare explicită).
  Prin urmare:
  - comportamentul la rulare pe Linux este **netestat**;
  - calea CUDA este **netestată pe placă reală**;
  - analiza de mai sus (importuri/pornire) este **statică**, din citirea codului, nu
    dintr-o rulare Linux.

## Cum se instalează / rulează (Linux)

```bash
./install.sh          # mediu Python + lansator + intrare în meniu + modelul
~/.local/bin/dted     # lansatorul creat de install.sh
```

> Instrucțiunile de mai sus au fost verificate static (citit `install.sh`), nu
> rulate efectiv pe Linux.

## Verificare rapidă a backend-ului (din sursă)

```bash
python -m linux.suport_linux
```

afișează platforma și ce backend (CUDA sau CPU) ar fi ales acum, folosind
aceeași logică de detectare ca motorul de transcriere.