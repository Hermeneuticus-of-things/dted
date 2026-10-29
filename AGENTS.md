# Instrucțiuni pentru agent – proiectul D&TED

## Cum raportezi utilizatorului

Lucrează în liniște. Scrie utilizatorului DOAR când:
1. o sarcină sau o subsarcină (etapă, cerință) s-a terminat;
2. apare o eroare sau o stare neașteptată (test picat, fișier lipsă, limită de model, rezultat diferit de cel așteptat);
3. ai nevoie de o decizie sau de un răspuns de la utilizator (blocaj).

Nu povesti pașii mărunți: nu anunța fiecare fișier citit, fiecare căutare sau fiecare comandă rulată. Mesajele sunt scurte, în limba română, și spun: ce s-a terminat sau ce s-a întâmplat, fișier:rând unde e cazul, rezultatul testelor și ce urmează sau ce decizie se cere.

## Reguli de versiune și publicare (obligatorii — aplică-le automat, la fiecare rulare)

Orice agent care lucrează la acest repo le urmează fără să ceară permisiunea:

1. **Fiecare build publicat = versiune NOUĂ.** Numerele cresc mereu cu 1 pe ultimul segment:
   0.6.2 → 0.6.3 → 0.6.4 … Niciun număr nu se refolosește și nu se sare peste.
2. La fiecare versiune actualizezi, împreună, **toate** locurile unde stă numărul:
   - `dictare_transcriere_romana/constante.py` → `VERSIUNE`;
   - `instalator/setup.iss` → `MyAppVersion`, `MyDistDir`, `OutputDir`, `OutputBaseFilename`;
   - `README.md` → secțiunea de instalare (nume fișiere, linkuri release) + o intrare nouă în
     „Ce e nou în v<versiune>” — scurt, lizibil, cu ce s-a schimbat;
   - `versiuni.json` (manifestul actualizărilor) → versiune, URL fix
     `https://github.com/Hermeneuticus-of-things/dted/releases/latest/download/program.zip`,
     SHA-256 real și dimensiunea reală a arhivei;
   - `dted-bootstrap.ps1` rămâne fără tag și sume hardcodate: găsește release-ul
     GitHub `latest` și verifică instalatorul/bucățile cu `SHA256SUMS.txt` din același release.
3. **Actualizările trebuie să fie solide și vizibile**: manifestul de pe GitHub `main` e mereu la
   zi cu ultima versiune, butonul „Caută actualizări” din program trebuie să găsească noul
   număr, iar după aplicare versiunea nouă chiar rulează (vezi override-ul din `pornire.py`).
4. Înainte de push: **suita completă de teste verde** (`.venv/Scripts/python -m pytest -q teste`).
   După push: tag `v<versiune>` + release GitHub cu toate kiturile (Setup .exe + .bin,
   `program-<versiune>.zip`, copia identică `program.zip`, arhiva Linux, `SHA256SUMS.txt`).
5. **Curățenie**: fără `.bak*`, `__pycache__`, build-uri vechi sau fișiere-artefact în repo.
   La UI/UX: **fără dubluri** — dacă o comandă are deja buton, nu o mai pune și în meniu.

## Reguli de update/packaging (obligatorii — bug-ul 0.6.7/0.6.8 nu se repetă)

1. **`program-<versiune>.zip` și `program.zip`** conțin EXCLUSIV „dictare_transcriere_romana/…” la rădăcină și sunt identice.
   Construire: `python _build_kits.py <versiune>` (calculează arcname relativ și VERIFICĂ
   structura — eșuează singur dacă apar căi străine). NU construi zip-uri „de mână”.
2. Aplicația folosește exclusiv URL-ul stabil `releases/latest/download/program.zip`;
   fiecare release stabil nou trebuie să aibă acel asset, identic cu arhiva versionată.
3. **`versiuni.json` din repo (branch main) e manifestul live** — păstrează URL-ul fix
   și se actualizează numai după publicarea/verificarea asset-ului `program.zip`.
   SHA-256 și dimensiunea trebuie să corespundă exact arhivei descărcate de la URL-ul stabil.
4. `actualizare.aplica` validează pachetul extras („dictare_transcriere_romana/__init__.py”
   trebuie să existe; structurile stricate se curăță automat). Nu marca versiunea ca aplicată
   dacă validarea pică.
5. Update-ul e „bun” DOAR după probă reală: aplicația instalată, după update și repornire,
   afișează versiunea nouă la „Despre” și noul changelog la F1 → „Ce e nou”.
6. Procedura completă și verificările de release sunt în `docs/ACTUALIZARI.md`.

## Reguli pentru README și documentație

1. README-ul este pentru utilizatorul care ajunge prima dată în repo: explică, în
   această ordine, **ce este**, **pentru cine**, **ce face**, **cum funcționează**,
   **cum lucrezi cu el**, **funcțiile**, **cum colaborează utilizatorul cu aplicația**,
   **ce s-a livrat și ce urmează**, apoi **instalarea, întrebările, problemele și
   detaliile tehnice**.
2. Noutățile din release se scriu pe înțelesul utilizatorului. Detaliile despre
   PyInstaller, dependențe și depanare rămân în documentația tehnică, nu în
   „Ce e nou”. Nu fixa în README numărul testelor; acesta se schimbă.
3. La o schimbare amplă de README, folosește skill-ul `beautify-github-readme`
   când este disponibil; păstrează capturi și materiale reale, text alternativ
   descriptiv și verifică toate legăturile locale.
4. README-ul și roadmap-ul se actualizează cu informații confirmate. Nu marca
   automat un obiectiv drept livrat doar pentru că apare într-un commit; verifică
   funcția și release-ul efectiv.
5. În CI rulează `python scripts/check_release_contract.py`, care verifică
   alinierea versiunii sursă, instalatorului, README-ului, manifestului și
   endpoint-urilor stabile.
6. La publicarea release-ului, workflow-ul rulează
   `scripts/validate_release_assets.py` înainte să modifice manifestul: verifică
   lista kiturilor, dimensiunile și SHA-256-urile GitHub, egalitatea ZIP-urilor
   pentru update și căile din arhiva Linux. Nu ocoli această validare.

## Contribuții și administrarea repo-ului

- Modificările se trimit prin pull request către `main`; după validarea release-ului,
  workflow-ul deschide un PR pentru manifestul live și rulează CI pe ramura acelui PR.
- `main` cere PR și status checks Windows/Linux verzi; nu permite push direct,
  force-push sau ștergerea branch-ului. Nu adăuga bypass pentru GitHub Actions.
- Înainte de merge: verifică testele Windows/Linux și contractul de release.
- Nu alege sau inventa o licență. În prezent repo-ul nu are un fișier `LICENSE`;
  licența trebuie decisă explicit de titularul drepturilor.
