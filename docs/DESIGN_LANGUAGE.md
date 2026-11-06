# Design language: Ionuț ADL — yes

Proiectul D&TED folosește **Ionuț Application Design Language** (skill:
`~/.agents/skills/ionut-application-design-language/SKILL.md`). Adoptat de
titular la 2026-11-06 (instrucțiune explicită: „trecu aplicația D&TED și
actualizează Ionut Application Design Language deep la toată aplicația").

## Ce înseamnă concret în D&TED

- **Funcția de bază** = editorul de text (cea mai mare suprafață, activă la
  pornire). Bara de transport și meniurile sunt *surrounding controls*:
  secundare vizual, mereu accesibile, iau focus doar când lucrezi în ele.
- **Focus pe niveluri** app → fereastră → suprafață → obiect. Ecranul de
  Setări e propria suprafață (deschis → primul câmp; închis → cursorul
  revine în editor). Bara de transport NU ia focus la clic pe butoane.
- **Fără dubluri de comenzi** (regulă deja aplicată): dacă o comandă are
  buton, nu apare și în meniu.
- **Scale**: controale 32–48 px (butonul roșu de dictare), tip UI 10–14 pt,
  spacing pe 4/8/12, raze 4–8 px. Fără butoane decorative.
- **Dispariție vs. disponibil**: bara de transport e contextuală (dictare /
  audio), dar fiecare comandă are mereu o cale (buton sau scurtătură scrisă
  pe buton).
- **Feedback la cauză**: mesajele de stare apar în bara de jos, fără a fura
  focusul; operațiile lungi au progres + anulare.
- **AA în ambele teme** (Luminos/Întunecat), contrast ≥ 4,5:1 verificat cu
  `teste/_contrast.py`; focus ring vizibil pe controale.
- **Vector peste tot**: iconițe și hero SVG; nimic raster pentru UI.

## Reguli la orice modificare de interfață

1. Nu elimina comenzi; reorganizează-le.
2. Un singur buton primar per suprafață.
3. Focus ≠ selecție: selecția din editor se păstrează când intri în Setări.
4. Orice caz nou de suprafață se semnalează (§2.13), nu se improvizează.
5. Checklist-ul complet e în SKILL.md (§17) — rulat înainte de livrare UI.
