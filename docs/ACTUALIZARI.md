# Publicarea actualizărilor D&TED

Acest document definește căile unice pe care le folosesc aplicația instalată și
bootstrap-ul. Nu se introduc URL-uri cu numere de versiune în codul aplicației.

## Căile stabile

| Rol | URL fix |
|---|---|
| Manifest citit de program la „Caută actualizări” | `https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/versiuni.json` |
| Arhiva programului din cel mai nou release GitHub | `https://github.com/Hermeneuticus-of-things/dted/releases/latest/download/program.zip` |
| Scriptul de instalare/bootstrap | `https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/dted-bootstrap.ps1` |
| Release-ul cel mai nou pentru bootstrap | `https://api.github.com/repos/Hermeneuticus-of-things/dted/releases/latest` |

Aplicația rămâne fixă: ea citește întotdeauna manifestul `main/versiuni.json`.
Manifestul spune versiunea, SHA-256 și dimensiunea; URL-ul arhivei rămâne
întotdeauna `releases/latest/download/program.zip`. Release-ul păstrează și
arhiva versionată `program-<versiune>.zip` pentru istoric, dar `program.zip`
trebuie să fie o copie identică a aceleiași arhive și să existe ca asset al
fiecărui release stabil.

Bootstrap-ul nu are versiune sau amprente înghețate în cod. La fiecare rulare
cere `/releases/latest`, identifică instalatorul și eventualele bucăți `.bin`
din tag-ul returnat, ia `SHA256SUMS.txt` din același release, verifică fiecare
fișier și abia apoi pornește instalarea. Astfel, un release nou nu cere editarea
bootstrap-ului.

## Publicarea unei versiuni noi

1. Incrementează versiunea conform regulilor din `AGENTS.md`; actualizează
   sursele și configurarea instalatorului. Rulează suita completă de teste.
2. Construiește kiturile: `python _build_kits.py <versiune>`. Scriptul produce
   `program-<versiune>.zip`, copia fixă `program.zip` și manifestul cu URL-ul
   `releases/latest/download/program.zip`. Nu arhiva manual și nu redenumi doar
   URL-ul fără să publici asset-ul corespunzător.
3. Construiește instalatorul versionat și pregătește arhiva Linux/portabilă.
   Creează `SHA256SUMS.txt` cu amprentele reale ale tuturor asset-urilor ce vor
   fi încărcate, inclusiv ambele arhive de program. Pentru `program.zip` și
   `program-<versiune>.zip`, amprentele și dimensiunile trebuie să coincidă.
4. Publică un release stabil cu tag-ul `v<versiune>` și asset-urile:
   `Setup.DTED-<versiune>.exe` (și toate `.bin`, dacă există),
   `program-<versiune>.zip`, `program.zip`, arhiva portabilă, arhiva Linux și
   `SHA256SUMS.txt`. Nu marca release-ul ca pre-release; GitHub trebuie să-l
   recunoască drept „latest”.
5. Publicarea release-ului stabil declanșează automat
   `.github/workflows/release-update-manifest.yml`. Workflow-ul descarcă
   `program.zip`, arhiva versionată și `SHA256SUMS.txt` din același tag,
   verifică egalitatea arhivelor, checksum-urile și structura ZIP, apoi
   publică manifestul corect pe `main`. Dacă oricare condiție pică, manifestul
   nu se schimbă și workflow-ul se oprește cu eroare. Repository-ul trebuie să
   permită workflow-urilor GitHub Actions permisiunea `contents: write` și
   push-ul pe `main`; dacă regulile de branch îl blochează, execuția eșuează
   vizibil și manifestul vechi rămâne activ.
6. Verifică rezultatul automat și URL-urile publice:
   - descarcă `.../releases/latest/download/program.zip`;
   - prima intrare ZIP trebuie să fie `dictare_transcriere_romana/...`, să
     existe `dictare_transcriere_romana/__init__.py`, iar SHA-256 și dimensiunea
     să coincidă cu `versiuni.json`;
   - verifică tag-ul/asset-urile returnate de `/releases/latest` și probează
     bootstrap-ul; confirmă după instalare și repornire versiunea din „Despre”.

## Migrarea de la v0.6.9

Release-ul existent `v0.6.9` rămâne nemodificat: nu are asset-ul fix
`program.zip`, iar codul său de update are un defect de aplicare. Manifestul
public rămâne pe URL-ul versionat existent până la publicarea unei versiuni noi.
`v0.6.10` a reparat aplicarea update-urilor și a activat aliasul stabil.
`v0.6.11` fixează și dependența PyAV la versiunea compatibilă cu motorul de
transcriere și include Tkinter pentru ruta de instalare de rezervă; nu modifica
asset-urile deja publicate pentru `v0.6.10`.

Bootstrap-ul este deja dinamic și nu depinde de tag-ul sau amprentele scrise
manual în script.

## Divergențe de evitat

- Codul aplicației, README-ul și manifestul trebuie să indice manifestul stabil
  `main/versiuni.json`; versiunea nu se codifică în program.
- `versiuni.json` indică versiunea curentă și o singură cale stabilă pentru
  arhivă; checksum-ul este calculat pentru conținutul exact de la acea cale.
- Arhiva versionată este istorică; aplicația nu trebuie să folosească URL-ul ei.
- Bootstrap-ul alege tag-ul cel mai nou din GitHub, dar descarcă instalatorul și
  checksum-urile din același tag, niciodată din două release-uri diferite.
- Linkurile de instalare din README trebuie să ducă la Releases/latest sau la
  un URL stabil; nu păstra linkuri către o versiune veche.
