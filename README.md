<!-- D&TED · Dictare și transcriere locală în limba română -->

<div align="center">

<img src="docs/img/interfata-v064.png" alt="D&TED: editorul cu textul dictat, iar jos bara de dictare — Dictează (F5), Pauză microfon, P alineat, I alineat, vumetru dB" width="880">

# 🎙️ D&ED · Dictare & Transcriere Express Digital

### Vorbești românește. Programul scrie. Totul pe calculatorul tău.

[![Versiune](https://img.shields.io/github/v/release/Hermeneuticus-of-things/dted?include_prereleases&label=versiune&color=2563eb)](https://github.com/Hermeneuticus-of-things/dted/releases)
[![Teste](https://img.shields.io/github/actions/workflow/status/Hermeneuticus-of-things/dted/ci.yml?label=teste&logo=github)](https://github.com/Hermeneuticus-of-things/dted/actions)
![WER română 5,8%](https://img.shields.io/badge/WER%20rom%C3%A2n%C4%83-5%2C8%25-16a34a)
![Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-0078d4?logo=windows11)
![100% local](https://img.shields.io/badge/procesare-100%25%20local%C4%83-16a34a)

[⬇️ Descarcă](#9-️-instalare--descărcare) · [✨ Funcțiile](#6-funcțiile-pe-rând) · [❓ Întrebări](#-întrebări-frecvente) · [🐞 Raportează](#-găsești-o-problemă-raportează-dintrun-clic) · [⚙️ Detalii tehnice](#️-detalii-tehnice)

</div>

---

## 1. Ce este

**D&TED e un program de dictare pentru limba română**, făcut pentru text lung de carte.
Vorbești în microfon — textul apare pe ecran **cuvânt cu cuvânt, pe măsură ce vorbești** —
îl corectezi ascultând înregistrarea, apoi îl salvezi ca document (DOCX, ODT, PDF…).

Transcrie și **fișiere audio** gata înregistrate (MP3, WAV, M4A, OGG, FLAC, Opus),
tot în română, tot local.

Totul rulează **pe calculatorul tău**: fără internet, fără cont, fără cloud, fără abonamente.

## 2. Pentru cine

- **Pentru cine scrie cărți** — volume, memorii, manuscrise: dictezi capitole întregi non-stop.
- **Pentru lucrări lungi** — licențe, dizertații, articole, rapoarte.
- **Pentru cei care nu pot sau nu vor să bată la tastatură** ore în șir.
- **Pentru text sensibil** — jurnale, corespondență, materiale juridice: nimic nu pleacă de pe calculator.
- **Pentru calculatoare obișnuite** — merge pe procesor, iar cu placă video NVIDIA e de ~20× mai rapid.

## 3. Ce face

| | |
|---|---|
| 🎤 **Dictezi live** | textul curge în editor cuvânt cu cuvânt, fără să aștepte după tine |
| ⏸ **Pauză microfon** | vorbești cu cineva lângă tine — programul nu aude nimic până la reluare |
| ⏎ **P alineat** | ștergi fraza neterminată și începi un paragraf nou, de la margine (F6) |
| ⇥ **I alineat** | ștergi fraza și începi paragraf nou **cu alineat** (tab), ca în cărțile tipărite (Shift+F6) |
| ⏱ **Semne [mm:ss]** | marchezi locurile importante; „Ascultă” (F9) redă exact bucata respectivă |
| 🎚 **Microfon automat** | vumetru în dB + reglaj automat: nu mai taie, nu mai e prea încet |
| 🧠 **Învață de la tine** | corectezi un cuvânt o dată — îl scrie corect de atunci |
| 📂 **Transcriere fișiere** | tragi mai multe audio deodată; cele transcrise se sar singure |
| 💾 **Export complet** | DOCX, ODT, TXT, RTF, HTML, SRT, VTT, PDF |
| 🔐 **Criptare** | documentele salvate pot fi criptate AES-256, cu parola ta |
| 🛡 **Confidențialitate** | 100% local; la cerere taie internetul programului sau al tot calculatorului |
| 📦 **Actualizări** | un buton în program; descarcă, verifică SHA-256, păstrează versiunea veche |

<div align="center">
<img src="docs/img/transport-redare-v064.png" alt="Modul de redare: bara de jos arată doar butoanele audio — Ascultă, Stop, derulare, poziție, volum" width="860">
</div>

## 4. Cum face

- **Motor**: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) peste [CTranslate2](https://github.com/OpenNMT/CTranslate2), cu modelul
  **[eek whisper-turbo-ro-en](https://huggingface.co/eek/whisper-turbo-ro-en)** optimizat pentru română — **implicit**.
- **Măsurat pe text de carte** (mostre reale, WER = cuvinte greșite):

| Model | Carte (30 s) | Total | Viteză (30 s audio) | Mărime |
|---|---|---|---|---|
| **eek whisper-turbo-ro** — implicit ✔ | **5,4%** | **5,8%** | 1,3 s | 800 MB |
| Whisper large-v3-turbo (standard) | 12,2% | 10,9% | 1,6 s | 1,6 GB |
| Fine-tunat RO (TransferRapid) | 47,3% ⚠️ | 37,0% | 0,7 s | 1,6 GB |

<sub>⚠️ fine-tunatul taie textul lung — bun doar pentru clipuri scurte. Se alege din Setări → „Cum transcrie”, unde fiecare model poate fi <b>descărcat cu un buton</b> (cu SHA-256 verificat).</sub>

- **Live adevărat**: microfonul și modelul lucrează pe **fire separate** — captura nu se oprește cât timp
  modelul scrie; o bucată de 2 s se transcrie în ~0,25 s pe placă video (GPU, float16) sau pe procesor
  (CPU, float32 — aceeași calitate, doar mai încet). Programul își alege singur dispozitivul.
- **Alineate ca în cărți**: fiecare idee nouă începe cu alineat — cu tab (stil tipărit) sau de la
  margine (stil web). Le alegi tu; programul nu le amestecă niciodată.

## 5. Cum lucrezi

1. Pornești programul — modelul se încarcă singur în fundal („modelul e încărcat” apare în bara de jos).
2. Apesi **⏺ Dictează (F5)** și vorbești non-stop. Nu te opri să aștepți: textul curge.
3. Te-ai încurcat? **⏎ P alineat (F6)** sau **⇥ I alineat (Shift+F6)** — fraza ștearsă, paragraf nou.
   Vorbește cineva lângă tine? **⏸ Pauză microfon**.
4. Marchezi locurile importante cu **⏱ Semn (Ctrl+B)** → apar `[mm:ss]` în text.
5. După dictare, bara trece pe modul audio: **▶ Ascultă (F9)** de la semnul de lângă cursor, corectezi
   direct în editor — și programul învață corecturile tale.
6. Salvezi (Ctrl+S) în formatul pe care îl vrei, cu parolă dacă vrei. Gata.

**Tastele principale** (se schimbă din Setări → „Taste rapide”, iar scurtătura stă scrisă pe fiecare buton):
F5 dictează · F9 ascultă · F7/F8 derulare · F10–F12 viteze · F6 P alineat · Shift+F6 I alineat · Ctrl+B semn.

## 6. Funcțiile, pe rând

- **Dictare pentru text de carte** — o singură fereastră, text legat de sunet, fără pagini separate.
- **Listă „Dictările mele”** — Dată, Oră, Durată, Prioritate, Nume, primele cuvinte; clic dreapta:
  Deschide / Redenumește (F2) / Șterge la Coșul de reciclare.
- **Activare vocală (opțional)** — programul pornește singur dictarea când începi să vorbești.
- **Fereastră mică, mereu deasupra** — pornești/oprești dictarea din orice alt program.
- **Curățenie automată** — bâlbâielile („nu, nu, nu”) se strâng singure; dublările firești rămân.
- **Comenzi vocale** — „punct”, „virgulă”, „punct și virgulă”, „două puncte”, „semn de întrebare”,
  „semnul exclamării”, „deschide/închide ghilimele”, „deschide/închide paranteză”, „cratimă”,
  „linie de dialog”, „linie de pauză”, „procent”, „slash”, „ampersand”, „paragraf nou”, „rând nou”.
- **Pauzele structurează singure textul** — peste 4 secunde de liniște → rând nou; peste 8 secunde → paragraf nou.
- **Căutare în editor** (Ctrl+F), zoom text (Ctrl + / − / 0), teme: Luminos / Întunecat / Ca Windows.
- **Verificare calculator** — CPU, RAM, disc, placă video + VRAM, driver, microfoane și boxe.
- **Mod serviciu** — `DTED.exe --serviciu`, pentru folosirea din alte programe.

## 7. Cum lucrați împreună

- **Programul și tu**: el scrie, tu curăți. Corecturile tale intră în dicționar și se aplică de la
  următoarea transcriere; „Nume și termeni” din Setări îi predau numele proprii (autor, personaje).
- **Cu documentele tale**: deschizi DOCX/ODT existente, continui dictarea, salvezi înapoi.
- **Cu stick-ul**: instalarea offline (varianta A de mai jos) se pune pe stick și instalează pe orice
  calculator, fără internet; portabilul chiar rulează de pe stick.
- **Cu confidențialitatea**: indicatorul din bara de jos arată mereu starea (🟢 internet pornit /
  🟠 doar programul izolat / 🔴 totul tăiat). La dictare se poate bloca automat.
- **Cu noi**: la orice eroare apare discret „⚠ Trimite raportul?” — fereastra vine completată din
  jurnal, fără text din carte și fără căi personale, și se trimite direct pe GitHub.

## 8. Ce urmează

### 🆕 Ce e nou în v0.6.5

- **Comenzi vocale extinse** — pe lângă „punct”, „virgulă”, „paragraf nou”, „rând nou”:
  „punct și virgulă”, „două puncte”, „semn de întrebare”, „semnul exclamării”,
  „deschide/închide ghilimele”, „deschide/închide paranteză”, „cratimă”, „linie de dialog”,
  „linie de pauză”, „procent”, „slash”, „ampersand”. Spațiile din jurul semnelor se curăță singure.
- **Pauzele lungi structurează singure textul** — peste 4 secunde de liniște → rând nou;
  peste 8 secunde → paragraf nou.
- **Lista completă de comenzi** e în Ajutor (F1 → „Comenzi vocale”), în „Citește-mă” și în ghidul scris.

Rămas după v0.6.5 (dictarea pentru cărți e completă):

Rămas după v0.6.5 (dictarea pentru cărți e completă):

- [ ] Modelul „pentru toți utilizatorii” — instalare partajată (admin o singură dată)
- [ ] Editare audio — marcarea și ștergerea unor porțiuni din înregistrare
- [ ] Limbi suplimentare — engleza prima; româna rămâne implicită
- [ ] Coloana Prioritate reală în lista dictărilor
- [ ] Alte modele noi pentru română, pe măsură ce apar

## 9. ⬇️ Instalare / descărcare

**Folosești Windows?** Ai nevoie de UNUL din cele trei rânduri:

| Vrei… | Apasă aici | Apoi… |
|---|---|---|
| **Cel mai simplu: instalează** | **[⬇️ DESCARCĂ SETUP.DTED-0.6.5.EXE](https://github.com/Hermeneuticus-of-things/dted/releases/download/v0.6.5/Setup.DTED-0.6.5.exe)** | ~1,84 GB; dublu clic → Next → Instalează |
| **Fără instalare, de pe stick** | **[⬇️ DESCARCĂ PORTABIL-DTED-0.6.5.ZIP](https://github.com/Hermeneuticus-of-things/dted/releases/download/v0.6.5/portabil-DTED-0.6.5.zip)** | click dreapta → Dezarhivează → `DTED.exe` |
| **Totul automat, o comandă** | PowerShell: `irm https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/dted-bootstrap.ps1 \| iex` | descarcă + verifică SHA-256 + instalează |

**Ai deja D&TED?** → butonul **📦 Actualizări** din program → „Caută actualizări (internet)”:
descarcă doar arhiva mică [`program-0.6.5.zip`](https://github.com/Hermeneuticus-of-things/dted/releases/download/v0.6.5/program-0.6.5.zip)
(~1,25 MB), verifică amprenta, păstrează versiunea veche; după repornire rulează chiar versiunea nouă.

**Linux (x86_64)?** → **[⬇️ DESCARCĂ DTED PENTRU LINUX](https://github.com/Hermeneuticus-of-things/dted/releases/download/v0.6.5/dted-0.6.5-linux.tar.gz)**,
apoi `tar -xzf dted-0.6.5-linux.tar.gz` și `./install.sh`.

**Kitul offline (exe) include tot** — modelul + CUDA; instalare 100% fără internet, fără administrator.
Wizard-ul îți arată pagina „Ce știe să facă D&TED” și verificarea calculatorului (CPU, RAM, disc, placă video + VRAM).
Aceleași fișiere, cu sume în [SHA256SUMS.txt](https://github.com/Hermeneuticus-of-things/dted/releases/download/v0.6.5/SHA256SUMS.txt),
sunt pe [pagina release v0.6.5](https://github.com/Hermeneuticus-of-things/dted/releases/tag/v0.6.5).

**Cerințe:** Windows 10/11 pe 64 de biți · 8 GB RAM recomandate · ~4 GB pe disc. Nucleul merge și pe Linux.

### ❓ Întrebări frecvente

**Primele cuvinte apar greșit la început?** Așteaptă mesajul „modelul e încărcat” din bara de jos — după el, dictarea pornește instant.

**Scrie cu întârziere pe calculator fără placă video?** Merge pe procesor, cu aceeași calitate — doar mai încet. Cu placă NVIDIA, butonul din Setări aduce CUDA (~1,2 GB).

**Unde ajung documentele?** În Documente → „Dictare&Transcriere Română”; folderul se schimbă din Setări.

**Cine vede textul meu?** Nimeni. Transcrierea e 100% locală; actualizările și rapoartele sunt singurele cu internet, doar când apeși tu.

### 🐞 Găsești o problemă? Raportează dintr-un clic

La orice eroare apare discret „⚠ Trimite raportul?” — fereastra vine **deja completată** cu detaliile
tehnice din jurnal; tu adaugi doar ce făceai. Se trimite direct pe
[GitHub Issues](https://github.com/Hermeneuticus-of-things/dted/issues) — **fără text din carte,
fără căi personale** (toate căile de disc sunt anonimizate automat).

<div align="center">
<img src="docs/img/raport.png" alt="Fereastra „Raportează o problemă” — pre-completată din jurnal" width="560">
</div>

### ⚙️ Detalii tehnice

- Cod sursă + teste:

  ```bash
  git clone https://github.com/Hermeneuticus-of-things/dted.git
  cd dted
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt pytest
  .venv\Scripts\python -m pytest -q teste      # 128 teste
  .venv\Scripts\python pornire.py               # pornește aplicația
  ```

- **128 de teste automate**, CI pe Windows și Linux la fiecare commit.
- Modelele și măsurătorile complete: [`docs/MODELE_ROMANA.md`](docs/MODELE_ROMANA.md).
- Nucleul pe Linux: [`LINUX.md`](LINUX.md).
- Confidențialitate: transcriere locală; izolare de rețea pe proces (Mod 2, fără UAC) sau completă
  (Mod 1, gardian reversibil); rapoarte anonimizate.

<div align="center">

**[⬇ Toate versiunile](https://github.com/Hermeneuticus-of-things/dted/releases)** · **[🐞 Problema? Raportează din program](https://github.com/Hermeneuticus-of-things/dted/issues)**

Cu 🎙 și 🤍 pentru limba română

<sub>D&amp;ED v0.6.5-beta · Whisper large-v3-turbo (eek, optimizat RO) · CTranslate2 · PySide6 · Inno Setup</sub>

</div>
