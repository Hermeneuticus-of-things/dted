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
marcate ca nefuncționale în `linux/suport_linux.py`. Fișierele Windows nu au fost
atinse.

## Ce s-a testat efectiv

* **Verificare de sintaxă** (`py_compile`) — a trecut.
* **Teste unitare cross-platform** (fără dependență de hardware sau de Windows),
  rulată pe Windows — raportul exact e în mesajul commit-ului / la sfârșitul
  acestei lucrări.
* **NU s-a testat rularea efectivă pe Linux.** Pe mașina de dezvoltare nu există
  un mediu Linux (WSL este dezactivat, Docker lipsește). Prin urmare:
  - comportamentul la rulare pe Linux este **netestat**;
  - calea CUDA este **netestată pe placă reală**.

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