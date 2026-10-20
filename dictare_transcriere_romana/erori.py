"""Mesaje de eroare în trei părți, așa cum trebuie să vadă utilizatorul.

Fiecare eroare spune, în română simplă:

 1. **ce s-a întâmplat** (fără termeni tehnici);
 2. **de ce s-a întâmplat, probabil**;
 3. **ce trebuie făcut acum**, împreună cu butonul potrivit.

Textul tehnic al excepției nu ajunge niciodată în mesaj: el este scris în
jurnal și apare doar sub butonul mic „Detalii pentru cineva care se pricepe”.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import jurnal

#: Felurile de acțiuni pe care le poate oferi un mesaj de eroare.
INCERCARE_DIN_NOU = "incearca_din_nou"
SETARI_MICROFON = "setari_microfon"
SETARI_SUNET = "setari_sunet"
ALEGE_FISIER = "alege_fisier"
DESCHIDE_FOLDER = "deschide_folder"
RENUNTA = "renunta"
OPRIRE = "oprire"


@dataclass
class Actiune:
    """Un buton din fereastra de eroare."""

    eticheta: str
    fel: str = INCERCARE_DIN_NOU


@dataclass
class Eroare:
    """O problemă explicată în trei părți, pentru utilizator."""

    ce_s_a_intamplat: str
    de_ce: str = ""
    ce_faci_acum: str = ""
    actiuni: list[Actiune] = field(default_factory=list)
    detalii: str = ""

    def text_complet(self) -> str:
        """Mesajul din cele trei părți, așa cum apare pe ecran."""
        parti = [self.ce_s_a_intamplat]
        if self.de_ce:
            parti.append(f"Probabil pentru că: {self.de_ce}")
        if self.ce_faci_acum:
            parti.append(f"Ce faci acum: {self.ce_faci_acum}")
        return "\n\n".join(parti)


# --------------------------------------------------------------------------- erori obișnuite


def fara_microfon(detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat="Nu găsesc microfonul.",
        de_ce=(
            "microfonul nu este conectat, este oprit din Windows sau Windows nu dă "
            "voie programului să îl folosească."
        ),
        ce_faci_acum=(
            "Verifică dacă microfonul sau căștile sunt conectate, apasă «Caută din nou», "
            "apoi, dacă tot nu merge, deschide setările de sunet din Windows."
        ),
        actiuni=[
            Actiune("Caută din nou", INCERCARE_DIN_NOU),
            Actiune("Deschide setările Windows pentru microfon", SETARI_MICROFON),
            Actiune("Verifică sunetul", SETARI_SUNET),
        ],
        detalii=detalii,
    )


def fisier_neacceptat(nume: str, detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat=f"Fișierul „{nume}” nu poate fi folosit.",
        de_ce="nu pare a fi un fișier audio sau este deteriorat.",
        ce_faci_acum=(
            "Alege un fișier audio în formatul MP3, WAV, M4A, OGG sau FLAC, apoi "
            "încearcă din nou."
        ),
        actiuni=[Actiune("Alege alt fișier", ALEGE_FISIER), Actiune("Închide", RENUNTA)],
        detalii=detalii,
    )


def disc_plin(detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat="Nu mai am loc pe disc.",
        de_ce="discul pe care se salvează documentele s-a umplut.",
        ce_faci_acum=(
            "Șterge fișiere de care nu ai nevoie sau alege alt folder pentru documente "
            "(Setări → Folder pentru documente), apoi încearcă din nou."
        ),
        actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Deschide folderul", DESCHIDE_FOLDER)],
        detalii=detalii,
    )


def folder_nu_se_poate_scrie(cale: str, detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat=f"Nu pot scrie în folderul „{cale}”.",
        de_ce=(
            "folderul este protejat, este doar pentru citire sau contul de Windows nu "
            "are voie să scrie acolo."
        ),
        ce_faci_acum=(
            "Alege un alt folder pentru documente din „Setări”, de exemplu unul din "
            "Documente, apoi încearcă din nou."
        ),
        actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Deschide folderul", DESCHIDE_FOLDER)],
        detalii=detalii,
    )


def model_lipsa(detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat="Modelul de transcriere lipsește.",
        de_ce="instalarea nu s-a terminat sau modelul a fost șters de pe calculator.",
        ce_faci_acum=(
            "Pornește din nou programul D&TED cu internetul deschis (sau rulează din nou "
            "instalarea); modelul se descarcă din nou și se verifică."
        ),
        actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Închide", RENUNTA)],
        detalii=detalii,
    )


def fara_internet(detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat="Nu am internet.",
        de_ce="calculatorul nu este conectat la Wi-Fi sau la cablu, ori legătura s-a întrerupt.",
        ce_faci_acum=(
            "Conectează calculatorul la Wi-Fi sau la cablu, apoi apasă «Încearcă din nou». "
            "Ce s-a descărcat deja se păstrează."
        ),
        actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Închide", RENUNTA)],
        detalii=detalii,
    )


def suma_gresita(nume: str, asteptat: str, gasit: str, detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat=f"Fișierul descărcat „{nume}” nu este cel oficial, așa că instalarea s-a oprit.",
        de_ce=(
            "descărcarea s-a întrerupt și fișierul a rămas incomplet sau a fost "
            "modificat pe drum."
        ),
        ce_faci_acum=(
            "Apasă «Încearcă din nou»; fișierul se descarcă din nou de pe site-ul "
            "oficial și se verifică din nou."
        ),
        actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Închide", RENUNTA)],
        detalii=f"{detalii}\nsuma așteptată: {asteptat}\nsuma găsită: {gasit}".strip(),
    )


def libreoffice_lipsa(detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat="Nu găsesc LibreOffice pe acest calculator.",
        de_ce="LibreOffice nu este instalat sau instalarea nu s-a terminat.",
        ce_faci_acum=(
            "Poți salva documentul ca DOCX sau ODT și îl poți deschide cu orice "
            "program de scris. Ca să ai LibreOffice, rulează din nou instalarea."
        ),
        actiuni=[Actiune("Salvează ca DOCX", RENUNTA), Actiune("Închide", RENUNTA)],
        detalii=detalii,
    )


def libreoffice_nu_a_pornit(detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat="LibreOffice nu a pornit.",
        de_ce="programul era deja deschis și ocupat, ori instalarea lui nu este completă.",
        ce_faci_acum=(
            "Închide fereastra LibreOffice dacă este deschisă, apoi apasă «Deschide în "
            "LibreOffice» din nou."
        ),
        actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Deschide folderul", DESCHIDE_FOLDER)],
        detalii=detalii,
    )


def text_prea_scurt(detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat="Înregistrarea este prea scurtă.",
        de_ce="dictarea a fost oprită imediat după pornire.",
        ce_faci_acum="Apasă «Dictează», vorbește, apoi apasă «Oprește dictarea».",
        actiuni=[Actiune("Închide", RENUNTA)],
        detalii=detalii,
    )


def transcriere_esuata(ce_fac: str, detalii: str = "") -> Eroare:
    return Eroare(
        ce_s_a_intamplat="Transcrierea nu a putut fi făcută.",
        de_ce="fișierul audio nu poate fi citit sau calculatorul a rămas fără memorie.",
        ce_faci_acum=ce_fac
        or "Încearcă din nou; dacă problema apare din nou, folosește alt fișier audio.",
        actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Alege alt fișier", ALEGE_FISIER)],
        detalii=detalii,
    )


# --------------------------------------------------------------------------- din excepții


def din_exceptie(exc: BaseException, context: str = "") -> Eroare:
    """Transformă orice excepție într-o eroare în trei părți.

    Textul brut al excepției merge în jurnal, niciodată în fața utilizatorului.
    """
    detalii = f"{type(exc).__name__}: {exc}"
    if context:
        detalii = f"{context} · {detalii}"
    jurnal.eroare(detalii)

    from . import descarcare

    if isinstance(exc, descarcare.SumaGresita):
        return suma_gresita(exc.nume, exc.asteptat, exc.gasit, detalii)
    if isinstance(exc, descarcare.EroareDescarcare):
        if getattr(exc, "fara_internet", False):
            return fara_internet(detalii)
        return Eroare(
            ce_s_a_intamplat="Descărcarea nu s-a terminat.",
            de_ce="legătura la internet a fost întreruptă sau serverul nu a răspuns.",
            ce_faci_acum="Verifică internetul și apasă «Încearcă din nou».",
            actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Închide", RENUNTA)],
            detalii=detalii,
        )

    try:  # modulele programului, importate cu grijă (pot să nu fie instalate încă)
        from . import inregistrare, motor

        if isinstance(exc, inregistrare.EroareMicrofon):
            return fara_microfon(detalii)
        if isinstance(exc, motor.EroareMotor):
            if "model" in str(exc).lower() and "lipse" in str(exc).lower():
                return model_lipsa(detalii)
            return transcriere_esuata(str(getattr(exc, "ce_fac", "")), detalii)
    except Exception:
        pass

    try:
        from . import libreoffice

        if isinstance(exc, libreoffice.EroareLibreOffice):
            return Eroare(
                ce_s_a_intamplat="LibreOffice nu a putut fi instalat complet.",
                de_ce=str(exc) or "un pas al instalării nu s-a terminat.",
                ce_faci_acum=getattr(exc, "ce_fac", "") or "Apasă «Încearcă din nou».",
                actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Închide", RENUNTA)],
                detalii=detalii,
            )
    except Exception:
        pass

    try:
        from . import instalare

        if isinstance(exc, instalare.EroareInstalare):
            if getattr(exc, "fara_internet", False):
                return fara_internet(detalii)
            return Eroare(
                ce_s_a_intamplat=str(exc),
                de_ce="un pas al instalării nu s-a terminat.",
                ce_faci_acum=getattr(exc, "ce_fac", "") or "Apasă «Încearcă din nou».",
                actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Închide", RENUNTA)],
                detalii=detalii,
            )
        if isinstance(exc, instalare.InstalareOprita):
            return Eroare(
                ce_s_a_intamplat=str(exc),
                de_ce="ai apăsat «Oprește instalarea».",
                ce_faci_acum=(
                    "Poți relua instalarea oricând; ce s-a descărcat deja se păstrează."
                ),
                actiuni=[Actiune("Închide", RENUNTA)],
                detalii=detalii,
            )
    except Exception:
        pass

    if isinstance(exc, PermissionError):
        return Eroare(
            ce_s_a_intamplat="Nu am voie să scriu în folderul ales.",
            de_ce="folderul este protejat de Windows.",
            ce_faci_acum="Alege alt folder (Setări → Folder pentru documente) și încearcă din nou.",
            actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Deschide folderul", DESCHIDE_FOLDER)],
            detalii=detalii,
        )
    if isinstance(exc, OSError):
        text = str(exc).lower()
        if "no space" in text or "112" in text or "there is not enough space" in text:
            return disc_plin(detalii)
        return Eroare(
            ce_s_a_intamplat="Un fișier nu a putut fi scris sau citit.",
            de_ce="discul este plin, folderul este protejat sau fișierul este folosit de alt program.",
            ce_faci_acum=(
                "Închide programele care folosesc fișierul, verifică spațiul liber pe disc, "
                "apoi încearcă din nou."
            ),
            actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Deschide folderul", DESCHIDE_FOLDER)],
            detalii=detalii,
        )

    return Eroare(
        ce_s_a_intamplat="A apărut o problemă neașteptată, dar programul merge în continuare.",
        de_ce="un pas nu s-a terminat cum trebuie.",
        ce_faci_acum=(
            "Apasă «Încearcă din nou». Dacă problema apare din nou, deschide «Ajutor → "
            "Probleme frecvente» sau trimite jurnalul din folderul programului."
        ),
        actiuni=[Actiune("Încearcă din nou", INCERCARE_DIN_NOU), Actiune("Închide", RENUNTA)],
        detalii=detalii,
    )
