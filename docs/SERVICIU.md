# Modul serviciu: D&TED folosit de alte programe

`DTED.exe --serviciu`, sau din codul sursă `python -m dictare_transcriere_romana --serviciu`, pornește D&TED fără ferestre. Programul primește comenzi pe intrarea standard și trimite textul pe ieșirea standard, câte un obiect JSON pe linie, în UTF-8. Primul care îl folosește este Scribner, pentru dictare și transcriere direct în editorul de carte. Specificația completă a integrării: https://github.com/Hermeneuticus-of-things/Scriptorium/blob/main/docs/DTED.md

Pe scurt:

- la pornire trimite `{"ev":"gata","protocol":1}`;
- comenzile sunt `stare`, `transcrie` (fișier), `dictare_start` și `dictare_stop` (microfon, text pe bucăți de ~4 s), `anuleaza` și `iesire`;
- evenimentele sunt `stare`, `faza`, `progres`, `rezultat`, `dictare_pornita`, `nivel`, `fragment`, `dictare_oprita`, `anulat` și `eroare` (cu `mesaj` și `ce_fac`, în română);
- nimic nu pleacă pe internet; modelul și sunetul rămân pe calculator;
- merge și cu fereastra D&TED deschisă: serviciul nu ține cont de blocarea „o singură instanță”;
- în `DTED.exe` (fără consolă) canalele se deschid direct din handle-urile Windows.

Codul e în `dictare_transcriere_romana/serviciu.py`, iar testele, cu motor și microfon falși, în `teste/test_serviciu.py`.

## De făcut

- [x] modul serviciu + teste
- [ ] proba pe Windows cu `DTED.exe` construit (`dictare.spec`): canale prin handle-uri, model real, microfon real
- [ ] opțional: `--serviciu --port` (HTTP local), pentru programe care nu pot porni procese
