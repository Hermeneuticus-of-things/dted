# Distribuție D&TED — trei variante (planificare)

**Status:** planificare / documentație only (2026-10-26). Fără schimbări de cod de aplicație în această notă.  
**Roadmap:** [issue #15](https://github.com/Hermeneuticus-of-things/dted/issues/15).

Modelele relevante pentru mărime:

| Asset | Dimensiune orientativă | Rol |
|-------|------------------------|-----|
| Whisper **eek** (`whisper-turbo-ro-en-ct2`) | ~787–820 MB | ASR implicit (offline) |
| **OpenLLM-Ro** instruct GGUF Q4_K_M | ~5 GB | Memorie / rezumat la dictări lungi (opțional) |
| Installer Windows (exe + runtime) | sute MB–~1+ GB | Depinde de bundling (PyInstaller etc.) |

**Total offline complet:** ≈ **6+ GB** (installer + eek + OpenLLM-Ro + alte asset-uri). Pentru zip-uri mari: split pe volume (ex. `.zip.001`) sau manager de download cu resume (aria2, GitHub multi-asset).

Modelele utilizatorului (fără admin) → `%LOCALAPPDATA%` (ex. `%LOCALAPPDATA%\DTED\models\`, `%LOCALAPPDATA%\Dictare&Transcriere Română\model\`), nu Program Files.

---

## 1) FULL OFFLINE PACKAGE

**Pentru:** utilizatori fără internet la instalare sau la prima rulare.

**Conținut:**
- Installerul complet Windows (sau portabil).
- **Toate** modelele pre-descărcate: eek + OpenLLM-Ro Q4_K_M (+ orice alt asset obligatoriu).
- Checksum-uri (SHA-256) și un `README-INSTALARE-OFFLINE.md` scurt în română.

**Formă de livrare:**
- Un zip / set de zip-uri pe GitHub Releases sau pe un mirror (TransferRapid etc.).
- Dacă >2 GB pe un singur asset: **split** (instrucțiuni de reasamblare) sau **mai multe asset-uri** pe același release (`DTED-offline-part1`, `part2`, …) + script `reaseambla.ps1`.

**Build (plan):**
1. Build installer ca la varianta Standard (fără a forța download la runtime pentru eek/OpenLLM).
2. Descarcă eek + OpenLLM-Ro în staging `dist/offline/models/`.
3. Empachetează `DTED-Setup-….exe` + `models/` + checksums → `DTED-offline-full-VERSION.zip` (sau parts).
4. Publică pe release + notează în CHANGELOG că e varianta offline.

**Rulare:** instalare din zip; app pornește fără rețea; „Memorie la dictări lungi” găsește GGUF local.

---

## 2) STANDARD INSTALLER

**Pentru:** majoritatea utilizatorilor cu internet.

**Conținut:**
- Installer cu **eek bundled** (mic relativ la OpenLLM; ASR merge imediat offline).
- **OpenLLM-Ro NU** e în installer: se descarcă **on demand** când utilizatorul activează modul de memorie lungă (toggle Basic „Memorie la dictări lungi” / echivalent).
- Destinație download: `%LOCALAPPDATA%\…\models\openllm-ro\` (fără admin); verificare SHA-256; retry/resume.

**Build (plan):**
1. Build curent + include doar eek în bundle / first-run cache.
2. URL manifest (GitHub Release asset sau JSON) pentru OpenLLM-Ro Q4_K_M.
3. UI: progres download, anulare, mesaj dacă offline.
4. Fallback: fără GGUF → stub / coadă verbatim (comportament deja planificat în summarizer).

---

## 3) BOOTSTRAP FROM GITHUB

**Pentru:** instalare minimală „un singur fișier mic” care trage restul de pe Releases.

**Conținut:**
- Bootstrapper mic (ps1/exe) care:
  1. Citește ultimul release `Hermeneuticus-of-things/dted` (API GitHub sau pagină Releases).
  2. Descarcă installerul Standard (sau portable).
  3. Opțional: descarcă eek dacă nu e în installer; descarcă OpenLLM-Ro doar dacă utilizatorul bifează „memorie lungă” / full.
  4. Verifică SHA-256 din `SHA256SUMS` de pe release.
- Necesită internet la bootstrap; după instalare, Standard se aplică.

**Build (plan):**
1. Script `bootstrap/dted-bootstrap.ps1` (există deja variante istorice în workspace — aliniază la Releases actuale).
2. Publică bootstrapperul ca asset ușor pe fiecare release + documentează în README.
3. Rate limits GitHub: preferă URL-uri `releases/download/…` directe, nu API autentificat pentru utilizatori finali.

---

## Alegere rapidă

| Situație | Variantă |
|----------|----------|
| Fără net / laborator închis | **1 Full offline** |
| Acasă / birou cu net | **2 Standard** (recomandat) |
| Link scurt „descarcă de pe GitHub” | **3 Bootstrap** |

---

## Note transversale

- **Compatibilitate Pneuma Sofer:** același canal de versiuni / manifest poate alimenta și update-ul D&TED din Pneuma (vezi `docs/CROSS_PROJECT_PNEUMA.md`; update-check în Scriptorium e ON HOLD).
- **Licențe:** verifică termenii modelului OpenLLM-Ro / GGUF redistribuit în pachetul offline înainte de publicare.
- **CI:** job opțional „pack-offline” doar pe tag, nu pe fiecare PR (cost timp/spațiu).

*Documentație / planning only — 2026-10-26.*
