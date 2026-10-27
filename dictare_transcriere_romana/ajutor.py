"""Ajutorul din program: explicații pe ecrane, întrebări frecvente, tur, ghiduri.

Tot textul este scris pentru cineva care nu a mai folosit un astfel de program:
fără termeni tehnici, propoziții scurte, pași numerotați. Explicațiile se
folosesc offline, din chiar programul instalat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import cai, jurnal
from .constante import (
    MESAJ_FARA_INTERNET,
    NUME_APLICATIE,
    NUME_CITESTE_MA,
    NUME_SCURTATURA,
    TITLU_FEREASTRA,
    NUME_GHD_AJUTOR,
    VERSIUNE,
)

# --------------------------------------------------------------------------- ecrane


@dataclass
class Ghid:
    """Explicația unui ecran, așa cum apare în fereastra de ajutor."""

    titlu: str
    ce_vezi: list[str] = field(default_factory=list)
    ce_faci: list[str] = field(default_factory=list)
    urmeaza: list[str] = field(default_factory=list)
    probleme: list[tuple[str, str]] = field(default_factory=list)


ECRANE: dict[str, Ghid] = {
    "noutati": Ghid(
        titlu="Ce e nou în v0.6.3",
        ce_vezi=[
            "Textul dictat apare pe ecran cuvânt cu cuvânt, pe măsură ce vorbești; partea gri se confirmă în câteva secunde.",
            "În bara de jos, lângă butonul roșu de dictare: „⏸ Pauză microfon”, „⏎ P alineat” și „⇥ I alineat”.",
            "Modelul de transcriere se încarcă singur în fundal, imediat după pornirea programului.",
        ],
        ce_faci=[
            "Dictezi non-stop: apasă butonul roșu (F5) și vorbește — programul scrie în timp ce vorbești, nu te mai așteaptă.",
            "Vorbești cu cineva lângă tine? Apasă „⏸ Pauză microfon”: programul nu mai aude nimic; la reluare, dictarea continuă de unde a rămas.",
            "Ai rostit o frază greșit? Apasă „⏎ P alineat” (F6): fraza neterminată se șterge, inclusiv cuvintele de pe ecran, și începi un paragraf nou de la margine.",
            "Începi o idee nouă? Apasă „⇥ I alineat” (Shift+F6): șterge fraza curentă și deschide un paragraf nou, cu alineat (tab), ca în cărțile tipărite.",
            "Tastele ți se par incomode? Setări → „Taste rapide”: îți alegi singur tastele; butonul „Pune tot la fel ca la început” le aduce pe cele din fabrică.",
        ],
        urmeaza=[
            "Actualizările din program („📦 Actualizări”) acum chiar intră în vigoare în aplicația instalată, după repornire.",
            "Instalatorul are o pagină nouă, „Ce știe să facă D&TED”, pe care o poți citi cât se instalează.",
        ],
        probleme=[
            (
                "Prima dictare tot târzie puțin.",
                "Așteaptă mesajul „modelul de transcriere e încărcat” din bara de jos: apare la câteva secunde după pornire. După el, dictarea pornește instant.",
            ),
        ],
    ),
    "comenzi": Ghid(
        titlu="Comenzi vocale",
        ce_vezi=[
            "Programul recunoaște singur comenzile rostite clar, cu o pauză scurtă înainte și după:",
            "• Structură: „paragraf nou”, „rând nou” (sau „linie nouă”), „P alineat”/„I alineat” pe butoane.",
            "• Punctuație: „punct”, „virgulă”, „punct și virgulă”, „două puncte”, „semn de întrebare”, „semnul exclamării”.",
            "• Ghilimele și paranteze: „deschide ghilimele” / „închide ghilimele”, „deschide paranteză” / „închide paranteză”.",
            "• Linii și simboluri: „cratimă”, „linie de dialog”, „linie de pauză”, „procent”, „slash”, „ampersand” (sau „și comercial”).",
            "• Pauzele lungi structurează singure textul: peste 4 secunde de liniște → rând nou; peste 8 secunde → paragraf nou.",
        ],
        ce_faci=[
            "Rostește comanda clar, cu o pauză scurtă înainte și după, ca programul să o deosebească de text.",
            "Vorbește natural între comenzi: „Am ajuns acasă punct mâine merg la târg paragraf nou”.",
            "Variantele cu și fără diacritice merg la fel: „semn de întrebare” sau „semn de intrebare”.",
            "Pentru text structurat corect, folosește regulile de alineat: fiecare idee nouă începe cu un alineat",
            "(„P alineat” de la margine, pentru stilul de pe web; „I alineat” cu tab, pentru cărți) — nu le amesteca.",
        ],
        urmeaza=[
            "Comenzile de selecție, formatare (bold/italic), navigare și controlul dictării pe voce",
            "(„oprește dictarea”, „pauză”) sunt în plan pentru o versiune următoare.",
            "În alte programe (Word, Google Docs, Windows, telefon) lista de comenzi diferă;",
            "punctuația de bază de mai sus e cea mai portabilă.",
        ],
        probleme=[
            (
                "Comanda nu a fost recunoscută.",
                "Rostește-o cu pauză scurtă înainte și după; încearcă varianta fără diacritice („doua puncte”).",
            ),
            (
                "Apar spații greșite lângă semne.",
                "Programul curăță singur spațiul dinaintea punctuației și după paranteza deschisă; dacă mai vezi ceva, apasă înapoi o dată.",
            ),
        ],
    ),    "principal": Ghid(
        titlu="Ecranul de început",
        ce_vezi=[
            "Sus scrie „Dictate & Transcription Express Digital (D&TED)” și, mai mic, "
            "„Dictare și transcriere în limba română”, apoi „Programul funcționează fără internet.” "
            "și „Limba vorbită: Română”.",
            "Trei carduri mari: „🎤 Dictare vocală”, „🎧 Transcriere fișier audio” și "
            "„📄 Deschide fișier existent”.",
            "Dedesubt, „Ultimele documente” (cel mult cinci) și butoanele mici "
            "„Fișierele mele”, „Verifică sunetul”, „Setări”.",
            "Sus, în dreapta, butonul „? Ajutor”, care este pe fiecare ecran (sau tasta F1).",
        ],
        ce_faci=[
            "Dacă vrei să vorbești: apasă „🎤 Dictare vocală” (Ctrl+D).",
            "Dacă ai o înregistrare: apasă „🎧 Transcriere fișier audio” (Ctrl+O).",
            "Dacă ai un document făcut mai demult: apasă „📄 Deschide fișier existent” (Ctrl+T).",
            "Ca să vezi unde au ajuns documentele: apasă „Fișierele mele”.",
        ],
        urmeaza=[
            "După fiecare dictare sau transcriere, textul se vede imediat în editorul din program, "
            "unde poate fi corectat.",
            "Din editor, un singur buton deschide documentul în LibreOffice, iar altul îl salvează "
            "ca DOCX sau ODT.",
        ],
        probleme=[
            ("Un card mare nu se apasă.", "Butoanele gri arată de ce nu pot fi folosite; citește scrisul de pe ele."),
            ("Nu știu unde am ajuns.", "Apasă „← Înapoi la început”, scris sus pe fiecare ecran."),
            ("Vreau explicații pas cu pas.", "Apasă „? Ajutor”; acolo scrie ce vezi, ce faci acum și ce urmează."),
        ],
    ),
    "dictare": Ghid(
        titlu="Dictare vocală",
        ce_vezi=[
            "Jos, în bara de transport: butonul roșu „⏺ Dictează (F5)”, „▶ Ascultă”, „⏹ Stop”, „⏸ Pauză microfon”, „⏎ P alineat” și „⇥ I alineat” — scurtăturile stau scrise pe butoane.",
            "Vumetrul se mișcă când vorbești; textul apare în editor cuvânt cu cuvânt, pe măsură ce rostești.",
            "Partea gri a textului e provizorie (se confirmă în câteva secunde); partea neagră e sigură.",
        ],
        ce_faci=[
            "Apasă butonul roșu (sau F5) și vorbește non-stop — nu te opri să aștepți: programul scrie în timp ce vorbești.",
            "Vorbești cu altcineva? Apasă „⏸ Pauză microfon”; apasă-l din nou ca să continui dictarea.",
            "Fraza nu a ieșit? „⏎ P alineat” (F6) o șterge pe cea neterminată și deschide un paragraf nou, de la margine.",
            "Idee nouă? „⇥ I alineat” (Shift+F6) șterge fraza curentă și deschide un paragraf nou, cu alineat (tab), ca în cărțile tipărite.",
            "„⏱ Semn” (Ctrl+B) pune [mm:ss] la cursor; „▶ Ascultă” (F9) redă bucata de la semn ca să o corectezi.",
            "Apasă din nou butonul roșu când ai terminat; textul și înregistrarea se salvează singure.",
        ],
        urmeaza=[
            "Corectezi în editor (cuvintele corectate se învață), apoi salvezi ca DOCX/ODT sau deschizi în LibreOffice.",
            "Tastele se schimbă din Setări → „Taste rapide” și merg imediat; scurtătura curentă stă scrisă pe fiecare buton.",
        ],
        probleme=[
            (
                "Scrie „Nu te aud”.",
                "Vorbește mai aproape de microfon sau verifică „Verifică sunetul” din ecranul de început.",
            ),
            (
                "Scrie cu întârziere.",
                "Așteaptă mesajul „modelul e încărcat” din bara de jos (apare la pornire); pe calculatoare fără placă video e puțin mai încet, dar merge.",
            ),
            (
                "Textul este gri.",
                "Gri înseamnă „încă se confirmă”: devine negru singur, în câteva secunde.",
            ),
        ],
    ),
    "transcriere": Ghid(
        titlu="Transcriere fișier audio",
        ce_vezi=[
            "Patru pași numerotați: 1 Alege fișierul, 2 Transcrie, 3 Așteaptă, 4 Gata.",
            "Pasul care urmează este scris îngroșat; pașii terminați au bifă verde.",
            "După alegerea fișierului: numele lui, durata și cât va dura transcrierea (estimare).",
        ],
        ce_faci=[
            "Pasul 1: trage fișierul în zona de sus sau apasă „Alege fișierul” (merge și F2).",
            "Pasul 2: apasă „Transcrie”, apoi așteaptă; poți citi textul pe măsură ce apare.",
            "Dacă vrei să te oprești, apasă „Anulează”: textul scris până atunci se păstrează.",
            "Pasul 4: salvează ca DOCX sau ODT și deschide documentul în LibreOffice.",
        ],
        urmeaza=[
            "Fișierul audio se păstrează în folderul „Audio”, cu numele lui.",
            "Textul se vede în editor chiar înainte de a salva documentul final.",
        ],
        probleme=[
            ("Butonul „Transcrie” este gri.", "Mai întâi trebuie ales un fișier audio (pasul 1)."),
            (
                "Transcrierea durează mai mult decât scria.",
                "Estimarea este aproximativă, mai ales când nu există placă video. Poți lăsa programul să lucreze.",
            ),
            (
                "Fișierul nu este acceptat.",
                "Sunt acceptate MP3, WAV, M4A, OGG, FLAC și alte formate obișnuite. Verifică extensia fișierului.",
            ),
        ],
    ),
    "editor": Ghid(
        titlu="Editorul din program",
        ce_vezi=[
            "Zona mare cu text, cu litere de cel puțin 14 puncte.",
            "Sus: „Anulează ultima modificare (Ctrl+Z)”, „Refă (Ctrl+Y)”, „Caută în text (Ctrl+F)”, "
            "„Copiază tot textul”, „Mărește scrisul”, „Micșorează scrisul”.",
            "Rândul cu litere românești: ă â î ș ț, pentru corectare rapidă.",
            "Jos: „Salvat automat la HH:MM” și numărul de cuvinte.",
        ],
        ce_faci=[
            "Scrie direct în text, ca într-un caiet.",
            "Pune cursorul unde lipsește o literă cu diacritică și apasă butonul potrivit (sau scrie litera de la tastatură).",
            "Apasă Ctrl+F ca să cauți un cuvânt, Ctrl+Z dacă ai greșit.",
        ],
        urmeaza=[
            "Textul se salvează automat la fiecare 30 de secunde și după fiecare acțiune, "
            "într-o copie de siguranță.",
            "Când ești gata, salvează ca DOCX sau ODT și deschide în LibreOffice pentru formatare.",
        ],
        probleme=[
            (
                "Formatarea s-a pierdut.",
                "Editorul este simplu, intenționat: nu păstrează îngroșarea sau culorile. "
                "Pentru formatare, deschide documentul în LibreOffice.",
            ),
            (
                "Am lipit text cu litere vechi (ş, ţ).",
                "Programul corectează automat ş și ţ în ș și ț atunci când lipești text.",
            ),
            ("Cuvintele au o linie roșie dedesubt.", "Sunt cuvinte care nu apar în dicționarul românesc de pe calculator; poți să le lași așa."),
        ],
    ),
    "fisiere": Ghid(
        titlu="Fișierele mele",
        ce_vezi=[
            "Trei file mari: „Audio”, „Text transcris” și „Documente finale”.",
            "Lista fișierelor, cu nume, data și durata (la sunet) sau mărimea (la documente).",
            "Lângă fiecare fișier, butoanele pentru ce vrei să faci cu el.",
        ],
        ce_faci=[
            "Apasă „Deschide” ca să vezi textul în editorul programului (sau documentul, dacă e DOCX/ODT).",
            "Apasă „Transcrie” ca să transcrii din nou un fișier audio.",
            "Apasă „Deschide în LibreOffice” pentru documentele finale.",
            "„Arată în folder” deschide Explorerul exact pe acel fișier; „Redenumește” schimbă numele.",
            "„Mută la Coșul de reciclare” trimite fișierul la Coșul de reciclare (nu-l șterge definitiv).",
        ],
        urmeaza=[
            "Folderele sunt în „Documente\\Dictare&Transcriere Română” (sau acolo unde ai ales în „Setări”).",
            "Poți deschide folderul și cu butonul „Deschide folderul”.",
        ],
        probleme=[
            ("Lista este goală.", "Apasă „Dictare vocală” sau „Transcriere fișier audio” ca să începi."),
            ("Am șters ceva din greșeală.", "Fișierele se mută la Coșul de reciclare și pot fi readuse de acolo."),
            ("Vreau alt folder.", "Deschide „Setări” și schimbă folderul; „Revino la locul implicit” readuce locul de la început."),
        ],
    ),
    "setari": Ghid(
        titlu="Setări",
        ce_vezi=[
            "Unde se salvează documentele, cu butonul „Schimbă folderul”.",
            "Limba vorbită, microfonul și difuzorul alese, felul de a transcrie (procesor sau placă video).",
            "Cât de des se salvează automat și dacă documentele se salvează singure după transcriere.",
            "Programul de scris preferat, folosit la „Deschide în…”.",
            "Secțiunea „Parolă și criptare”: parola documentelor și criptarea lor la salvare.",
            "Secțiunea „Confidențialitate”: blocarea căilor de ieșire în timpul dictării.",
        ],
        ce_faci=[
            "Schimbă doar ce ai nevoie; fiecare rând are explicație simplă.",
            "Apasă „Revino la locul implicit” sau „Revino la LibreOffice” dacă vrei înapoi setările din start.",
            "La „Parolă și criptare”, apasă „Pune o parolă”: parola implicită a programului este „Dictare” "
            "(deja scrisă în căsuță — poți rămâne la ea sau să scrii alta).",
            "Bifează „Criptează documentele salvate” ca documentele să fie încuiate cu parola (AES-256).",
            "Apasă „Salvează setările” când ai terminat.",
        ],
        urmeaza=[
            "Setările se păstrează și după închiderea programului.",
            "Dacă schimbi folderul, fișierele vechi rămân unde erau; cele noi se pun în folderul nou.",
            "Documentele criptate se deschid doar cu parola (implicit „Dictare”) sau cu cheia de recuperare primită la punerea parolei.",
        ],
        probleme=[
            ("Am pus un folder greșit.", "Apasă „Revino la locul implicit” și documentele se pun iar în „Documente”."),
            ("Nu găsesc setarea.", "Apasă „? Ajutor”; toate setările sunt explicate pe scurt, cu cuvintele din program."),
            ("Care este parola implicită?", "Parola implicită a programului este „Dictare”. O poți schimba oricând din „Parolă și criptare” → „Schimbă parola”."),
            ("Am uitat parola.", "Folosește cheia de recuperare arătată la punerea parolei (dacă ai salvat-o). Fără parolă sau cheie, documentele criptate nu se mai pot deschide."),
        ],
    ),

    "sunet": Ghid(
        titlu="Verifică sunetul",
        ce_vezi=[
            "Trei rânduri: Microfon, Difuzor și Căști.",
            "Pe fiecare rând: numele dispozitivului, starea („Merge”, „Lipsește”, „Netestat încă”) și un buton de test.",
        ],
        ce_faci=[
            "Apasă „Testează microfonul”, vorbește normal 5 secunde, apoi ascultă ce s-a înregistrat.",
            "Apasă „Testează difuzorul” ca să auzi un sunet scurt prin difuzoare.",
            "Pentru căști, apasă „Testează căștile”: se aude întâi în urechea stângă, apoi în cea dreaptă.",
            "La final răspunde la întrebarea „Te-ai auzit clar?”.",
        ],
        urmeaza=[
            "Dacă totul se aude bine, poți începe să dictezi din ecranul principal.",
            "Dacă lipsește microfonul, doar dictarea este oprită; transcrierea fișierelor merge oricând.",
        ],
        probleme=[
            (
                "Nu se aude nimic la test.",
                "Verifică volumul din Windows (pictograma cu difuzor) și dacă dispozitivul e pornit.",
            ),
            (
                "„Nu te aud.” apare în timpul dictării.",
                "Vorbește mai aproape de microfon sau alege alt microfon din „Setări”.",
            ),
            (
                "Am conectat căștile acum.",
                "Dispozitivele se caută singure la fiecare 3 secunde; apasă „Caută din nou”.",
            ),
        ],
    ),
    "internet": Ghid(
        titlu="Internetul și informațiile tale",
        ce_vezi=[
            "Un indicator colorat sus: roșu „● Internet pornit” sau verde „● Internet oprit – lucrezi în siguranță”.",
            "Când începi să dictezi sau să scrii cu internetul pornit, o fereastră roșie care îți explică situația.",
            "În fereastră, pașii simpli pentru a opri internetul (Wi-Fi, Mod avion sau cablu).",
        ],
        ce_faci=[
            "Citește mesajul: programul nu trimite nimic pe internet, nici sunetul, nici textul, nici documentele.",
            "Apasă „Am înțeles, continuă” ca să lucrezi mai departe (dictarea nu se oprește oricum).",
            "Dacă lucrezi cu informații importante, apasă „Cum opresc internetul?”. Sunt patru căi: oprești Wi-Fi, scoți cablul de rețea, pornești „Mod avion” sau oprești partajarea din telefon (Bluetooth ori cablu USB).",
            "În ajutorul care se deschide ai un buton care pornește „Mod avion” direct, fără să cauți prin setări.",
            "Apasă „Nu mai afișa azi” dacă nu vrei să mai vezi fereastra până mâine; indicatorul rămâne vizibil.",
        ],
        urmeaza=[
            "Indicatorul se actualizează singur la fiecare 10 secunde, deci afli imediat dacă internetul se pornește sau se oprește.",
            "Poți opri avertizarea din „Setări” („Avertizează-mă când internetul e pornit”), dar indicatorul rămâne.",
        ],
        probleme=[
            (
                "De ce îmi spune că internetul este pornit, dacă nu folosesc internetul?",
                "Indicatorul citește doar starea rețelei de la Windows: dacă ești conectat la o rețea (Wi-Fi, cablu sau telefon), scrie „Internet pornit”. Programul nu folosește însă internetul decât dacă ceri tu o descărcare.",
            ),
            (
                "Programul trimite cumva datele mele?",
                "Nu. Dictarea și transcrierea se fac pe calculatorul tău, iar funcția care citește starea rețelei nu trimite niciun fel de date: doar întreabă Windows dacă există legătură.",
            ),
            (
                "Internetul s-a oprit în timpul dictării.",
                "Nu se întrerupe nimic: dictarea merge la fel, iar indicatorul devine verde.",
            ),
        ],
    ),
    "drivere": Ghid(
        titlu="Lipsesc drivere",
        ce_vezi=[
            "Lista dispozitivelor care nu merg din lipsă de drivere (sunetul, placa video).",
            "Pentru fiecare, se spune pe scurt ce nu merge din cauza lui.",
            "Butonul de reparare, care poate instala driverul din Windows Update (numai după acordul tău).",
        ],
        ce_faci=[
            "Citește lista: fiecare rând spune ce dispozitiv are problema.",
            "Apasă „Da, instalează” dacă ești de acord; se instalează **doar** driverele pentru "
            "dispozitivele cu probleme, potrivite după codul lor de hardware.",
            "Dacă nu vrei acum, apasă „Nu acum”; poți relua oricând din „Verifică sunetul” sau din instalare.",
        ],
        urmeaza=[
            "După instalare, programul verifică din nou și spune dacă totul merge.",
            "Uneori Windows cere repornirea calculatorului; atunci îți spune clar.",
        ],
        probleme=[
            (
                "Nu am internet.",
                "Driverele se iau de la Microsoft, deci este nevoie de internet. Conectează-te și încearcă din nou.",
            ),
            (
                "Nu vreau să instalez drivere.",
                "Poți folosi programul fără ele: transcrierea merge pe procesor. Doar microfonul are nevoie de driver de sunet.",
            ),
            (
                "Placa video nu are driver.",
                "Fără driver, transcrierea merge pe procesor, mai încet. Se raportează doar plăcile care ar putea grăbi transcrierea.",
            ),
        ],
    ),
    "instalare": Ghid(
        titlu="Instalare",
        ce_vezi=[
            "Lista cerințelor calculatorului, cu bifă verde, semn de atenție sau X roșu.",
            "Cât spațiu liber este pe disc și cât este necesar.",
            "Butonul mare „Confirm, pornește instalarea”.",
        ],
        ce_faci=[
            "Citește lista; dacă ceva lipsește, rezolvă mai întâi (de exemplu eliberează spațiu pe disc).",
            "Apasă „Verifică din nou” după ce ai rezolvat, apoi „Confirm, pornește instalarea”.",
            "Așteaptă; progresul este scris în cuvinte, de exemplu „Descarc modelul de transcriere: 1,2 din 1,6 GB”.",
            "Dacă vrei să te oprești, apasă „Oprește instalarea”; ce s-a descărcat se păstrează.",
        ],
        urmeaza=[
            "La final se creează scurtătura de pe Desktop și cea din meniul Start.",
            "LibreOffice se instalează în română, cu dicționarul românesc, apoi se verifică.",
        ],
        probleme=[
            (
                "„Nu am internet.”",
                "Conectează calculatorul la Wi-Fi sau la cablu, apoi apasă „Încearcă din nou”. Descărcările continuă de unde au rămas.",
            ),
            (
                "Instalarea durează mult.",
                "Modelul are aproximativ 1,6 GB și se descarcă o singură dată. Poți lăsa instalarea să meargă.",
            ),
            (
                "Am închis fereastra din greșeală.",
                "Deschide din nou instalarea: continuă de unde a rămas, fără să descarce a doua oară.",
            ),
        ],
    ),
    "progres": Ghid(
        titlu="Ce se întâmplă acum (bara de progres)",
        ce_vezi=[
            "O bară care se umple și procentul, de exemplu „37%”.",
            "Pasul curent, în cuvinte simple, de exemplu „Pasul 2 din 5: descarc modelul de recunoaștere a vocii”.",
            "Cât mai durează, în minute, socotit după viteza calculatorului tău.",
            "Un semn mic care se mișcă mereu: înseamnă că programul lucrează, nu s-a blocat.",
            "Butonul mare roșu „■ Oprește”, drept lângă bară.",
        ],
        ce_faci=[
            "Nu trebuie să faci nimic: poți lăsa fereastra deschisă și îți vezi de treabă.",
            "Dacă vrei să te oprești, apasă „■ Oprește”, apoi „Da, oprește”: ce s-a scris până acum se păstrează.",
            "Dacă scrie „Calculez cât mai durează…”, programul încă măsoară viteza calculatorului; după puțin timp apare numărul de minute.",
        ],
        urmeaza=[
            "Când se termină, scrie „Gata! A durat …” și apar butoanele de salvare.",
            "Dacă oprești, poți continua mai târziu de unde ai rămas: programul își amintește.",
        ],
        probleme=[
            (
                "„Calculatorul tău lucrează mai încet acum.”",
                "Programul merge în continuare. Închide alte programe deschise și lasă calculatorul la priză; apoi așteaptă.",
            ),
            (
                "„Pare că s-a blocat.”",
                "Poți să mai aștepți sau să apeși „Oprește”. Ce s-a făcut până acum nu se pierde.",
            ),
            (
                "Am apăsat din greșeală „Oprește”.",
                "Textul scris până atunci este păstrat. Apasă „Continuă de unde am rămas” și merge mai departe.",
            ),
        ],
    ),
    "verificare": Ghid(
        titlu="Verificarea calculatorului",
        ce_vezi=[
            "O listă de rânduri, fiecare cu un semn: ✔ verde „E bine”, ! „Atenție” sau ✘ roșu „Lipsește”.",
            "Rândurile verifică sunetul (microfon, difuzoare, căști), părțile de transcriere, "
            "ce trebuie ca să se poată asculta fișierele audio, LibreOffice și legăturile de internet, "
            "Wi-Fi, Bluetooth și stick.",
            "Lângă fiecare rând care are o problemă este un buton de reparare.",
        ],
        ce_faci=[
            "Citește rândurile cu ✘ sau cu ! și apasă butonul de lângă ele (de exemplu „Verifică sunetul”).",
            "Apasă „Verifică din nou” după ce ai rezolvat ceva: lista se împrospătează.",
            "Închei cu „← Înapoi la început” și lucrezi liniștit.",
        ],
        urmeaza=[
            "Verificarea se face singură și la fiecare pornire a programului.",
            "Dacă lipsește un driver, se deschide fereastra „Lipsesc drivere”, care spune de unde se ia.",
        ],
        probleme=[
            (
                "Un rând are ✘ roșu.",
                "Scrie sub rând ce lipsește și ce poate face programul singur. Apasă butonul de lângă rând.",
            ),
            (
                "„Nu găsesc niciun microfon.”",
                "Conectează un microfon sau căști cu microfon, apoi apasă „Verifică sunetul” și „Caută din nou”. "
                "Poți folosi programul și fără microfon, cu un fișier audio înregistrat.",
            ),
            (
                "Nu știu ce înseamnă un rând.",
                "Apasă „? Ajutor” (sau F1): fiecare rând are explicația lui, în cuvinte simple.",
            ),
        ],
    ),
}

#: Întrebările frecvente, valabile pe orice ecran.
INTREBARI: list[tuple[str, str]] = [
    (
        "Nu merge microfonul",
        "1) Verifică dacă microfonul este conectat (la un laptop, microfonul intern este gata de folosit). "
        "2) Deschide „Verifică sunetul” din ecranul de început și apasă „Testează microfonul”: "
        "dacă bara se mișcă atunci când vorbești, microfonul merge. "
        "3) Dacă bara nu se mișcă, apasă „Verifică sunetul”, apoi „Deschide setările Windows pentru microfon” "
        "și îngăduie programelor să folosească microfonul. "
        "4) Apasă „Schimbă microfonul” în ecranul de dictare și alege alt microfon din listă. "
        "5) Dacă în listă nu apare niciun microfon, lipsește driverul de sunet: deschide instalarea "
        "și folosește „Rezolvă driverele”, sau întreabă pe cineva care se pricepe.",
    ),
    (
        "Nu se deschide în LibreOffice",
        "1) Verifică dacă documentul a fost salvat (apare „Salvat la ora…” lângă butonul de salvare). "
        "2) Închide fereastra LibreOffice dacă era deschisă, apoi apasă din nou „Deschide în LibreOffice”. "
        "3) Apasă „Deschide folderul” și deschide documentul cu dublu-clic din folderul „Documente finale”. "
        "4) Dacă LibreOffice nu este instalat deloc, programul îți scrie asta și îți propune „Instalează LibreOffice” "
        "(este nevoie de internet). Poți corecta textul în editorul din program și îl poți salva ca DOCX sau ODT.",
    ),
    (
        "Unde sunt fișierele mele?",
        "În folderul „Documente\\Dictare&Transcriere Română”, în trei subfoldere: „Audio” (înregistrările), "
        "„Text transcris” (textul simplu) și „Documente finale” (DOCX, ODT și celelalte formate). "
        "Cel mai repede ajungi acolo din ecranul de început: „Fișierele mele”, apoi „Deschide folderul”. "
        "Numerele sunt legate: „Dictare 2026-10-19 10-35.wav”, „…txt” și „…docx” sunt același lucru. "
        "Poți schimba folderul din „Setări”, iar „Revino la locul implicit” îl readuce în „Documente”.",
    ),
    (
        "Lipsesc driverele",
        "Programul verifică driverele de care are nevoie: driverul de sunet (pentru microfon și difuzoare) "
        "și, doar dacă placa video poate grăbi transcrierea, driverul plăcii video. "
        "Dacă lipsește ceva, apare fereastra „Lipsesc drivere”, cu lista dispozitivelor și cu butonul de reparare. "
        "Instalarea se face numai după ce îți dă acordul, doar pentru dispozitivele cu probleme, "
        "și numai din sursele oficiale Microsoft (Windows Update sau site-ul Microsoft). "
        "Fără driver de sunet, dictarea nu poate merge; fără driver de placă video, transcrierea merge mai încet, "
        "pe procesor, dar programul funcționează.",
    ),
    (
        "Cum opresc internetul cât lucrez?",
        "Sunt patru căi, alege-o pe cea mai simplă pentru tine:\n"
        "1. Wi-Fi: apasă pe pictograma rețelei de lângă ceas (colțul din dreapta jos), apoi alege „Wi-Fi oprit”.\n"
        "2. Cablu: dacă ai cablu de la router în calculator, scoate-l.\n"
        "3. Mod avion: în aceeași listă, apasă „Mod avion” — se oprește tot internetul deodată (și Wi-Fi, și Bluetooth).\n"
        "4. Telefonul: dacă îți ții telefonul legat la calculator prin Bluetooth sau prin cablu USB și îi dai "
        "internet, oprește partajarea din telefon sau scoate cablul USB. Telefonul poate aduce internet fără să știi.\n"
        "Programul merge la fel și fără internet: doar descărcările au nevoie de el.",
    ),
    (
        "Programul are nevoie de internet?",
        f"{MESAJ_FARA_INTERNET} Internetul este folosit doar la instalare, ca să se "
        "descărcare modelul, Python și LibreOffice. După aceea, programul merge "
        "complet offline, iar datele nu pleacă nicăieri de pe calculator.",
    ),
    (
        "Nu se deschide în LibreOffice. Ce fac?",
        "1) Verifică dacă documentul a fost salvat (apare „Salvat la ora…” lângă butonul de salvare). "
        "2) Închide fereastra LibreOffice dacă era deschisă și apasă din nou „Deschide în LibreOffice”. "
        "3) Dacă nici atunci nu merge, apasă „Deschide folderul” și deschide documentul cu dublu-clic. "
        "4) Dacă nu ai LibreOffice, salvează ca DOCX sau ODT și deschide documentul cu „Deschide cu alt program…”. "
        "5) Poți rula din nou instalarea: doar LibreOffice se adaugă, restul rămâne cum este.",
    ),
    (
        "Cum salvez în alt format, de exemplu PDF?",
        "Apasă „Alte formate…” și alege formatul dorit (TXT, RTF, HTML, SRT, VTT, PDF). "
        "PDF-ul se face cu LibreOffice, așa că are nevoie ca LibreOffice să fie instalat.",
    ),
    (
        "Unde ajung documentele salvate?",
        "În folderul „Documente\\Dictare&Transcriere Română”, cu data și ora în nume "
        "(„… – AAAA-LL-ZZ HH-MM”). Butonul „Deschide folderul” "
        "deschide exact acel folder. Poți schimba folderul din „Setări”.",
    ),
    (
        "Textul are diacritice greșite (ş în loc de ș).",
        "Programul corectează automat ş și ţ în ș și ț, în textul transcris și în "
        "documentele salvate. Dacă observi altceva, corectează în zona de text înainte de salvare.",
    ),
    (
        "Dictez, dar nu apare text.",
        "Verifică patru lucruri: microfonul este conectat; Windows dă voie programului să îl "
        "folosească („Setări Windows pentru microfon”); scrie „Te aud” în timpul dictării; "
        "ai vorbit după apăsarea butonului „Dictează”.",
    ),
    (
        "Transcrierea merge încet.",
        "Fără placă video, transcrierea rulează pe procesor: este normal să dureze de la câteva "
        "secunde la câteva minute pentru fiecare minut de audio. Închide programele mari în timpul transcrierii.",
    ),
    (
        "Am închis programul și am pierdut textul.",
        "Nu se pierde: textul este păstrat automat la fiecare 30 de secunde. La pornirea "
        "următoare apare întrebarea „Am găsit un text nesalvat de data trecută. Îl recuperez?”.",
    ),
    (
        "Vreau să folosesc Microsoft Word, nu LibreOffice.",
        "Deschide „Setări → Programul de scris preferat” și alege Word. Butonul „Deschide în "
        "LibreOffice” deschide documentul în programul ales; poți reveni oricând cu „Revino la LibreOffice”.",
    ),
    (
        "Pot scrie în altă limbă?",
        "Da, din „Setări” poți alege limba vorbită. Româna este limba programului și "
        "valoarea implicită pentru transcriere. „Automat” nu este ales niciodată din start.",
    ),
    (
        "Cum dezinstalez programul?",
        f"Din „Setări Windows → Aplicații → Programe instalate”, alege „{TITLU_FEREASTRA}” "
        "și apasă „Dezinstalează”. Documentele transcrise rămân în folderul „Documente”.",
    ),
    (
        "Unde văd ce a mers greșit?",
        "În folderul programului, fișierele „jurnal_instalare.txt” și „jurnal.txt” conțin "
        "toate informațiile tehnice. Le poți trimite cuiva care se pricepe.",
    ),
]

#: Pașii turului de la prima pornire (maximum 4).
PASI_TUR: list[tuple[str, str, str]] = [
    (
        "principal",
        "Bun venit! Aici este tot ce ai nevoie",
        "Ai trei butoane mari: „🎤 Dictare vocală” (vorbești și textul apare singur), "
        "„🎧 Transcriere fișier audio” (alegi o înregistrare) și „📄 Deschide fișier existent” "
        "(deschizi un document făcut mai demult).",
    ),
    (
        "principal",
        "Unde se salvează documentele",
        f"Tot ce salvezi ajunge în „{cai.director_documente()}” → „Dictare&Transcriere Română”, "
        "în trei subfoldere: „Audio”, „Text transcris” și „Documente finale”. "
        "Le vezi oricând cu „Fișierele mele”.",
    ),
    (
        "sunet",
        "Verificăm sunetul (durează un minut)",
        "Aici se testează microfonul, difuzorul și căștile. Apasă butonul de lângă fiecare rând. "
        "Dacă microfonul nu merge, programul îți spune exact ce să faci.",
    ),
    (
        "ajutor",
        "Dacă te încurci, apasă „? Ajutor”",
        "Butonul „? Ajutor” este sus, în dreapta, pe fiecare ecran (sau tasta F1). "
        "Acolo scrie ce vezi, ce faci acum, ce urmează și răspunsuri la problemele obișnuite.",
    ),
]


def ghid(cheie: str) -> Ghid:
    """Explicația ecranului cerut (sau cea principală, dacă nu există)."""
    return ECRANE.get(cheie, ECRANE["principal"])


# --------------------------------------------------------------------------- ghiduri scrise


def _linie_titlu(text: str, semn: str = "=") -> str:
    return f"{text}\n{semn * len(text)}\n"


def text_citeste_ma() -> str:
    """Conținutul fișierului „Citește-mă.txt”, scris simplu, pentru tipărire.

    Începe cu tabelul cerințelor („ce calculator îți trebuie”), ca oricine să
    poată vedea de la prima privire dacă programul are ce îi trebuie.
    """
    from . import resurse

    parti: list[str] = [
        _linie_titlu(f"{TITLU_FEREASTRA} — citește-mă"),
        f"Versiunea {VERSIUNE}.\n",
        _linie_titlu("Ce calculator îți trebuie", "-"),
        resurse.text_tabel_pentru_tiparire(),
        "\n",
        _linie_titlu("Cum se instalează", "-"),
        "1. Dublu-clic pe programul de instalare „Setup DTED.exe” (sau, în varianta veche,",
        "   pe „instaleaza.bat” din arhiva primită).",
        "   (Dacă Windows cere voie, apasă „Da”.)",
        "2. Pe ecran apare lista cu cerințele calculatorului. Citește-o și apasă",
        "   „Confirm, pornește instalarea”.",
        "3. Se descarcă automat, în ordine: programul Python (fără instalare, nu schimbă Windows),",
        "   bibliotecile de transcriere, modelul de transcriere (aproximativ 1,6 GB) și",
        "   LibreOffice, în română, cu dicționar românesc.",
        "4. La final apar scurtăturile: pe Desktop și în meniul Start.",
        "\nAre nevoie de internet doar la instalare. După aceea programul merge fără internet.",
        "\nDacă instalarea se întrerupe (lipsă de curent, închizi fereastra, se ia internetul),",
        "deschide-o din nou: continuă de unde a rămas, fără să descarce din nou ce este gata.",
        "\n",
        _linie_titlu("Cum se folosește", "-"),
        f"1. Deschide „{NUME_SCURTATURA}” de pe Desktop.",
        "2. Alege un fișier audio (MP3, WAV, M4A, OGG, FLAC) sau apasă „Dictează” și vorbește.",
        "3. Apasă „Transcrie” și așteaptă textul.",
        "4. Corectează dacă vrei, apoi apasă „Salvează ca DOCX” sau „Salvează ca ODT”.",
        "5. „Deschide în LibreOffice” deschide documentul în programul de scris.",
        "\n",
        _linie_titlu("Ce trebuie să aibă calculatorul", "-"),
        "• Windows 10 (versiunea 1809) sau Windows 11, pe 64 de biți;",
        "• minim 8 GB memorie RAM (recomandat 16 GB);",
        "• minim 7 GB liberi pe disc (9 GB dacă are placă video dedicată);",
        "• placă video dedicată cu minim 6 GB memorie și driver 525 sau mai nou (opțional);",
        "• microfon, pentru dictare (opțional: transcrierea fișierelor merge și fără microfon).",
        "\n",
        _linie_titlu("Comenzi vocale", "-"),
        "Rostește comanda clar, cu o pauză scurtă înainte și după, ca programul",
        "să o deosebească de textul dictat:",
        "• structură: „paragraf nou”, „rând nou” (sau „linie nouă”);",
        "• punctuație: „punct”, „virgulă”, „punct și virgulă”, „două puncte”,",
        "  „semn de întrebare”, „semnul exclamării” (merg și fără diacritice);",
        "• ghilimele: „deschide ghilimele”, „închide ghilimele”;",
        "• paranteze: „deschide paranteză”, „închide paranteză”;",
        "• linii și simboluri: „cratimă”, „linie de dialog”, „linie de pauză”,",
        "  „procent”, „slash”, „ampersand” (sau „și comercial”);",
        "• pauzele lungi structurează singure textul: peste 4 secunde de liniște",
        "  → rând nou; peste 8 secunde → paragraf nou;",
        "• pentru paragrafe, butoanele „P alineat” (de la margine, stil web) și",
        "  „I alineat” (cu tab, stil de carte) — fiecare idee nouă începe cu alineat.",
        "\n",
        _linie_titlu("Probleme frecvente", "-"),
    ]
    for intrebare, raspuns in INTREBARI:
        parti.append(f"Î: {intrebare}")
        parti.append(f"R: {raspuns}\n")
    parti.extend(
        [
            _linie_titlu("Unde sunt documentele", "-"),
            str(cai.director_iesiri()),
            "\nJurnale (pentru cineva care se pricepe):",
            str(cai.fisier_jurnal_instalare()),
            str(cai.fisier_jurnal_aplicatie()),
            "\n",
        ]
    )
    return "\n".join(parti)


def scrie_citeste_ma(cale: Path | None = None) -> Path | None:
    """Scrie „Citește-mă.txt” lângă program și, dacă se poate, o copie pe Desktop."""
    tinta = Path(cale) if cale else cai.fisier_citeste_ma()
    text = text_citeste_ma()
    scris: Path | None = None
    try:
        tinta.parent.mkdir(parents=True, exist_ok=True)
        tinta.write_text(text, encoding="utf-8")
        scris = tinta
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut scrie {tinta}: {exc}")
    return scris


def text_ghid_ajutor() -> str:
    """Ghidul de folosire, cu explicația fiecărui ecran."""
    parti: list[str] = [
        _linie_titlu(f"{TITLU_FEREASTRA} — Ghid de folosire"),
        "Toate explicațiile se pot citi și din program, cu butonul „? Ajutor”.",
        "",
    ]
    for cheie in (
        "noutati",
        "comenzi",
        "principal",
        "dictare",
        "transcriere",
        "editor",
        "fisiere",
        "setari",
        "sunet",
        "drivere",
        "instalare",
    ):
        date = ghid(cheie)
        parti.append(_linie_titlu(date.titlu, "-"))
        parti.append("Ce vezi:")
        parti.extend(f"  • {linie}" for linie in date.ce_vezi)
        parti.append("\nCe faci acum:")
        parti.extend(f"  • {linie}" for linie in date.ce_faci)
        parti.append("\nCe urmează:")
        parti.extend(f"  • {linie}" for linie in date.urmeaza)
        if date.probleme:
            parti.append("\nProbleme frecvente:")
            for intrebare, raspuns in date.probleme:
                parti.append(f"  • {intrebare}\n    {raspuns}")
        parti.append("")
    parti.append(_linie_titlu("Întrebări frecvente", "-"))
    for intrebare, raspuns in INTREBARI:
        parti.append(f"Î: {intrebare}")
        parti.append(f"R: {raspuns}\n")
    return "\n".join(parti)


def scrie_ghid_ajutor(cale: Path | None = None) -> Path | None:
    """Scrie „Ghid de folosire.txt” lângă program."""
    tinta = Path(cale) if cale else cai.director_instalare() / NUME_GHD_AJUTOR
    try:
        tinta.parent.mkdir(parents=True, exist_ok=True)
        tinta.write_text(text_ghid_ajutor(), encoding="utf-8")
        return tinta
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut scrie {tinta}: {exc}")
        return None


def nume_citeste_ma() -> str:
    return NUME_CITESTE_MA
