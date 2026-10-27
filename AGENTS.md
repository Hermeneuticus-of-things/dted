# Instrucțiuni pentru agent – proiectul D&TED

## Cum raportezi utilizatorului (utilizator)

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
   - `versiuni.json` (manifestul actualizărilor) → versiune, URL `program-<versiune>.zip`,
     SHA-256 real și dimensiunea reală a arhivei;
   - `dted-bootstrap.ps1` → `$Tag = "v<versiune>"` + amprentele SHA-256 ale fișierelor
     Setup.DTED-<versiune>.exe și .bin (AMPRENTE REALE, calculate pe fișierele construite —
     nu le lăsa niciodată de la versiunea precedentă; verifică întotdeauna perechea tag/sume).
3. **Actualizările trebuie să fie solide și vizibile**: manifestul de pe GitHub `main` e mereu la
   zi cu ultima versiune, butonul „Caută actualizări” din program trebuie să găsească noul
   număr, iar după aplicare versiunea nouă chiar rulează (vezi override-ul din `pornire.py`).
4. Înainte de push: **suita completă de teste verde** (`.venv/Scripts/python -m pytest -q teste`).
   După push: tag `v<versiune>` + release GitHub cu toate kiturile (Setup .exe + .bin,
   `program-<versiune>.zip`, arhiva Linux, `SHA256SUMS.txt`).
5. **Curățenie**: fără `.bak*`, `__pycache__`, build-uri vechi sau fișiere-artefact în repo.
   La UI/UX: **fără dubluri** — dacă o comandă are deja buton, nu o mai pune și în meniu.
