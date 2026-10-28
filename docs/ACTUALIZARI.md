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
   asset-urile aceluiași tag și metadatele lor de la GitHub. Validatorul
   `scripts/validate_release_assets.py` cere kiturile pentru versiunea din tag,
   compară mărimile și amprentele GitHub cu `SHA256SUMS.txt`, descarcă și
   verifică arhivele de program și Linux, confirmă că `program.zip` este copia
   identică a arhivei versionate și respinge căi străine în arhive. Abia apoi
   workflow-ul publică manifestul pe `main`. Dacă oricare condiție pică,
   manifestul nu se schimbă și workflow-ul se oprește cu eroare. Repository-ul
   trebuie să permită workflow-urilor GitHub Actions permisiunea `contents: write`
   și push-ul pe `main`; dacă regulile de branch îl blochează, execuția eșuează
   vizibil și manifestul vechi rămâne activ.
6. Verifică rezultatul automat și URL-urile publice:
   - descarcă `.../releases/latest/download/program.zip`;
   - prima intrare ZIP trebuie să fie `dictare_transcriere_romana/...`, să
     existe `dictare_transcriere_romana/__init__.py`, iar SHA-256 și dimensiunea
     să coincidă cu `versiuni.json`;
   - verifică tag-ul/asset-urile returnate de `/releases/latest` și probează
     bootstrap-ul; confirmă după instalare și repornire versiunea din „Despre”.

Validatorul de asset-uri poate fi rulat local dacă ai un director cu fișierele
release-ului, un JSON cu metadatele asset-urilor returnate de GitHub și
`SHA256SUMS.txt`:

```powershell
python scripts\validate_release_assets.py v<versiune> <director-release> <asset-metadata.json>
```

## Istoric de compatibilitate

Release-ul `v0.6.9` a rămas nemodificat și nu are aliasul fix `program.zip`.
Începând cu `v0.6.10`, release-urile stabile publică `program.zip` alături de
arhiva versionată, iar actualizatorul folosește adresa stabilă din manifestul
public de pe `main`. `v0.6.11` a fixat și dependența PyAV și a inclus Tkinter
pentru asistentul de instalare de rezervă.

Pentru versiunea publică actuală, verifică întotdeauna tag-ul `latest` și
manifestul public, nu presupune că ultima intrare din această secțiune de istoric
este versiunea publicată.

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
