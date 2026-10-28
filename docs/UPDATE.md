# Lanțul de actualizare (update) — reguli obligatorii

Acest document spune **cum funcționează update-ul**, **unde se pune fiecare fișier** și
**ce trebuie să facă oricine publică o versiune nouă** (om sau AI). Citit și de alte
AI-uri care lucrează la repo: regulile identice sunt în [`AGENTS.md`](../AGENTS.md).

## 1. Lanțul, de la utilizator la fișier

```
Utilizator apasă „Caută actualizări” în program
        │  (ADRESĂ FIXĂ, nu se schimbă niciodată)
        ▼
https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/versiuni.json
        │  (manifestul de pe branch „main” — mereu ultima versiune publicată)
        ▼
{ "versiune": "0.6.x", "url": ".../releases/download/v0.6.x/program-0.6.x.zip",
  "sha256": "…", "dimensiune": … }
        │  (descarcă DOAR arhiva mică, verifică SHA-256)
        ▼
actualizare.aplica(): VALIDEAZĂ structura arhivei („dictare_transcriere_romana/__init__.py”),
        taie componenta veche (după backup), instalează cea nouă, scrie versiunea aplicată
        ▼
pornire.py: la repornire, dacă versiunea din „program/” > versiunea de bază,
        încarcă pachetul actualizat (importlib) → versiunea nouă chiar rulează
```

**Divergent → convergent:** de unde ar veni pachetul (orice release, orice nume), totul
converge în același loc: manifestul fix de pe `main`. Programul nu „ghicește” niciodată
o adresă — o citește din `versiuni.json`, iar adresa manifestului e constantă în
`constante.py` (`URL_MANIFEST_ACTUALIZARI`).

## 2. Unde se pune ce (la fiecare versiune)

| Fișier | Unde | Rol |
|---|---|---|
| `Setup.DTED-<v>.exe` (+ `.bin` dacă > 2 GB) | Release `v<v>` „Assets” | instalare completă offline |
| `portabil-DTED-<v>.zip` | Release `v<v>` | fără instalare (fără CUDA; programul îl descarcă de la buton) |
| `program-<v>.zip` | Release `v<v>` | **actualizarea din program** — conține EXCLUSIV `dictare_transcriere_romana/…` |
| `dted-<v>-linux.tar.gz` | Release `v<v>` | Linux |
| `SHA256SUMS.txt` | Release `v<v>` | sumele tuturor fișierelor de mai sus |
| `versiuni.json` | **root, branch `main`** | manifestul live: versiune + URL + SHA-256 + dimensiune |
| `dted-bootstrap.ps1` | root, branch `main` | `$Tag = "v<v>"` + amprenta SHA-256 reală a Setup-ului |

## 3. Reguli nerindicibile (bug-ul 0.6.7/0.6.8 nu se repetă)

1. **`program-<v>.zip` = doar pachetul, la rădăcină.** Prima intrare din arhivă trebuie
   să fie `dictare_transcriere_romana/…`. Se construiește DOAR cu
   `python _build_kits.py <versiune>` — scriptul forțează `arcname` relativ și
   **se auto-verifică** (eșuează dacă apar căi străine de pe mașina de build).
2. **`versiuni.json` de pe `main` e manifestul live.** După publicare, updatezi și
   împingi manifestul înainte de a anunța versiunea — altfel „Caută actualizări”
   nu găsește nimic.
3. **Cross-check obligatoriu înainte de publicare:**
   `python _cross_check.py <versiune>` — 7 verificări încrucișate (versiune în
   constante/setup/manifest/zip/bootstrap, SHA-256-uri, existența kiturilor).
   Orice ✘ = nu se publică.
4. **Proba reală:** după publicare, verifici de pe GitHub (nu local): manifestul de pe
   `main`, structura zip-ului descărcat din release și faptul că SHA-256 coincide.
5. **Componenta veche e sacră până la validare:** `actualizare.aplica` validează
   pachetul („__init__.py” prezent) ÎNAINTE să șteargă ceva; un pachet stricat lasă
   instalarea intactă și NU marchează versiunea ca aplicată.
6. **Proba de capăt:** aplicația instalată → update → repornire → „Despre” arată
   versiunea nouă (nu e hardcodată — citește `VERSIUNE_COMPLETA`), F1 → „Ce e nou”
   arată schimbările noi.

## 4. Comenzi rapide (copy-paste)

```bash
# 1. versiune nouă peste tot (constante, setup.iss, README) — vezi AGENTS.md
# 2. build kit
.venv/Scripts/pyinstaller.exe dictare.spec --noconfirm --distpath dist-v<X> --workpath build-v<X>
"C:\Users\Ionut\AppData\Local\Programs\Inno Setup 6\ISCC.exe" instalator\setup.iss
.venv/Scripts/python _build_kits.py <X>          # portabil + zip + linux + manifest (auto-verificat)

# 3. sume + bootstrap (amprente REALE)
#    (vezi AGENTS.md punctul 2 — SHA256SUMS.txt + dted-bootstrap.ps1)

# 4. cross-check — OBLIGATORIU
.venv/Scripts/python _cross_check.py <X>

# 5. push, tag v<X>, release cu toate kiturile, apoi verificare pe GitHub
```
