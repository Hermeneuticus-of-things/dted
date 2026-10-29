# Contribuții la D&TED

Mulțumim pentru interes. Modificările obișnuite se propun prin pull request către
`main`; nu publica direct o versiune nouă fără să urmezi procedura de release.

## Pregătirea mediului

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest
```

## Înainte de pull request

Rulează verificarea documentației și suita de teste:

```powershell
.\.venv\Scripts\python.exe scripts\check_release_contract.py
.\.venv\Scripts\python.exe -m pytest -q teste
```

Actualizează README-ul când se schimbă experiența utilizatorului. Scrie noutățile
în termeni simpli, fără numere fixe pentru teste și fără detalii interne de build.
Verifică linkurile și imaginile locale. Roadmap-ul arată separat ce este deja
livrat și ce rămâne planificat.

## Publicarea unui release

Un release stabil necesită un tag `v<major>.<minor>.<patch>`, kiturile versionate,
aliasul `program.zip` și sumele SHA-256. După validare, workflow-ul deschide un PR
pentru manifestul live; manifestul devine activ numai după ce PR-ul trece CI și
este integrat în `main`. Nu crea manual arhiva de update. Urmează integral
[`docs/ACTUALIZARI.md`](docs/ACTUALIZARI.md); acesta descrie și verificarea
descărcării publice după publicare.

PyAV este ignorat de Dependabot deoarece versiunea lui trebuie să rămână
compatibilă cu motorul de transcriere și cu kitul Windows; schimbarea se face
numai împreună cu actualizarea verificărilor de compatibilitate.

## Raportarea problemelor

Folosește formularul Bug sau funcția de raportare din aplicație. Nu publica
documente dictate, înregistrări audio, parole sau alte date personale.
