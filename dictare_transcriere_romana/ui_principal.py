"""Fereastra principală a programului: ecranul curat de început și celelalte ecrane.

Aici este „creierul” interfeței. Fereastra asta:

* ține **starea** lucrului (textul, sunetul, documentul) și setările;
* arată ecranul de început, cu trei carduri mari („Dictează”, „Transcrie un fișier
  audio”, „Scrie sau corectează textul”), cu „Ultimele documente” și cu butoanele
  mici („Fișierele mele”, „Verifică sunetul”, „Verifică calculatorul”, „Setări”);
* ține **editorul integrat** jos, în aceeași fereastră, și îl arată doar pe ecranele
  de dictare, transcriere și scriere (cerința 12);
* trece de la un ecran la altul (``arata_ecran``) și deschide ajutorul (``?`` / F1);
* salvează documentele (DOCX, ODT și alte formate), le deschide în LibreOffice
  (sau în alt program de scris ales) și **observă** când documentul a fost salvat
  din nou în LibreOffice, ca să ia modificările făcute acolo;
* la pornire: verifică părțile de care are nevoie, întreabă dacă se reia lucrul
  neterminat de data trecută și dacă se recuperează textul nesalvat;
* ține minte modul de afișare (luminos / întunecat / ca Windows, cerința 27) și
  mărimea scrisului, refăcând ecranele când se schimbă.

Toată munca grea (încărcarea modelului, transcrierea, descărcările) rulează în
alte fire de lucru; fereastra răspunde mereu la clicuri (cerința 25).
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path

from . import (
    biblioteca,
    cai,
    codecuri,
    config as config_modul,
    constante,
    dispozitive,
    documente,
    drivere,
    erori,
    inregistrare,
    instalare,
    jurnal,
    libreoffice,
    motor,
    operatiuni,
    programe_scris,
    resurse,
    securitate,
    sisteme,
    stare as stare_modul,
    text_ro,
    ui_ajutor,
    ui_calculator,
    ui_comun,
    ui_dictare,
    ui_drivere,
    ui_editor,
    ui_fisiere,
    ui_internet,
    ui_progres,
    ui_setari,
    ui_sunet,
    ui_transcriere,
    ui_tur,
)

#: Numele ferestrei, peste tot la fel (cerința 1).
NUME = constante.NUME_APLICATIE

#: Ecranele care arată și editorul integrat, jos.
ECRANE_CU_EDITOR = ("dictare", "transcriere", "editor")

#: Formatele din „Alte formate…” (cerința 5).
ALTE_FORMATE: list[tuple[str, str]] = [
    ("txt", "Text simplu (.txt) — se deschide în orice program"),
    ("rtf", "Document RTF (.rtf) — merge în multe programe de scris"),
    ("html", "Pagină web (.html) — pentru site-uri sau e-mail"),
    ("srt", "Subtitrări (.srt) — pentru filme, cu timpi"),
    ("vtt", "Subtitrări (.vtt) — pentru filme, cu timpi"),
    ("pdf", "PDF (.pdf) — se citește pe orice calculator, nu se modifică ușor"),
]

#: La cât timp se verifică, în fundal, dacă documentul a fost salvat în LibreOffice.
SECUNDE_VERIFICARE_DOCUMENT = 4.0
#: Cât timp se urmărește documentul deschis în LibreOffice (10 minute).
SECUNDE_URMARIRE_DOCUMENT = 600.0


# --------------------------------------------------------------------------- rândurile verificării


class RandVerificare(tk.Frame):
    """Un rând din ecranul „Verifică calculatorul”: semn, text, explicație, buton.

    Semnul spune starea cu **pictogramă și cuvânt**, niciodată doar cu culoare
    (cerințele 19, 20 și 27).
    """

    FELURI = {
        "ok": ("✔", "E bine", "verde_fundal", "verde_text"),
        "atentie": ("!", "Atenție", "galben_fundal", "galben_text"),
        "lipsa": ("✘", "Lipsește", "rosu_fundal", "rosu_text"),
        "necunoscut": ("?", "Se verifică…", "galben_fundal", "galben_text"),
    }

    def __init__(self, parinte: tk.Misc, titlu: str, la_buton=None, text_buton: str = ""):
        super().__init__(parinte, background=ui_comun.CULORI.card)
        C = ui_comun.CULORI
        self._la_buton = la_buton
        rand = tk.Frame(self, background=C.card)
        rand.pack(fill="x", padx=ui_comun.px(10), pady=ui_comun.px(6))
        self.pictograma = tk.Label(
            rand,
            text="?",
            font=ui_comun.fonturi().titlu,
            background=C.card,
            foreground=C.text,
            width=3,
        )
        self.pictograma.pack(side="left", anchor="n")
        coloana = tk.Frame(rand, background=C.card)
        coloana.pack(side="left", fill="x", expand=True)
        self.titlu = ui_comun.eticheta(coloana, titlu, "subtitlu", fundal=C.card, latime_bucati=680)
        self.titlu.pack(anchor="w")
        self.stare_text = ui_comun.eticheta(coloana, "Se verifică…", "baza", fundal=C.card, latime_bucati=680)
        self.stare_text.pack(anchor="w")
        self.explicatie = ui_comun.eticheta(coloana, "", "mica", fundal=C.card, latime_bucati=680)
        self.explicatie.pack(anchor="w")
        self.buton = None
        if la_buton is not None:
            self.buton = ui_comun.Buton(
                rand, text_buton or "Rezolvă", la_buton, latime=280, inaltime=56
            )
            self.buton.pack(side="left", padx=(ui_comun.px(8), 0))

    def arata(self, fel: str, text: str, explicatie: str = "", text_buton: str = "") -> None:
        """Arată starea rândului: „ok”, „atentie”, „lipsa” sau „necunoscut”."""
        simbol, cuvant, fundal_fel, text_fel = self.FELURI.get(fel, self.FELURI["necunoscut"])
        C = ui_comun.CULORI
        culoare = getattr(C, text_fel)
        self.configure(background=getattr(C, fundal_fel))
        for copil in self.winfo_children():
            copil.configure(background=getattr(C, fundal_fel))
            for nepot in copil.winfo_children():
                try:
                    nepot.configure(background=getattr(C, fundal_fel))
                except tk.TclError:
                    pass
        self.pictograma.configure(text=simbol, foreground=culoare)
        self.stare_text.configure(text=f"{simbol} {cuvant}. {text}".strip(), foreground=culoare)
        self.explicatie.configure(text=explicatie, foreground=culoare)
        if self.buton is not None and text_buton:
            self.buton.seteaza_text(text_buton)


class PaginaVerificare(tk.Frame):
    """Ecranul „Verifică calculatorul”: bife verzi, X-uri roșii și butoane de reparare.

    Verificările sunt citite de pe calculatorul pe care rulează programul
    (cerința 21): sunetul, părțile de transcriere, ce trebuie pentru fișierele
    audio, LibreOffice, driverele și cele patru căi de la punctul 22.
    """

    def __init__(self, parinte: tk.Misc, aplicatie):
        super().__init__(parinte, background=ui_comun.CULORI.fundal)
        self.aplicatie = aplicatie
        self.config = aplicatie.config
        self._raport: resurse.Raport | None = None
        self._drivere: drivere.StareDrivere | None = None
        self._se_verifica = False
        self._construieste()

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        C = ui_comun.CULORI
        zona = ui_comun.ZonaDerulare(self, latime_minima=940)
        zona.pack(fill="both", expand=True)
        corp = tk.Frame(zona.interior, background=C.fundal)
        corp.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(12))

        rand_titlu = tk.Frame(corp, background=C.fundal)
        rand_titlu.pack(fill="x")
        ui_comun.eticheta(rand_titlu, "Verifică calculatorul", "titlu").pack(side="left")
        self.indicator = ui_internet.indicator(rand_titlu, self.config)
        self.indicator.pack(side="right")

        ui_comun.eticheta(
            corp,
            "Programul citește singur ce are calculatorul tău: sunetul, părțile de transcriere, "
            "programul de scris și legăturile prin care informația ar putea ieși din calculator. "
            "Ce are ✔ verde este bine; ce are ✘ roșu are un buton de reparare lângă.",
            "baza",
            latime_bucati=940,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        card, corp_card = ui_comun.card(corp, "Ce am găsit pe acest calculator")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        self.randuri: dict[str, RandVerificare] = {}
        randuri_text = [
            ("calculator", "Calculatorul (memorie, procesor, disc, sistem)", self._repara_calculator, "Vezi ce îmi trebuie"),
            ("sunet", "Sunetul (microfon, difuzoare, căști)", self._repara_sunet, "Verifică sunetul"),
            ("transcriere", "Părțile de transcriere (modelul de recunoaștere a vocii)", self._repara_transcriere, "Rezolvă"),
            ("codecuri", "Ce trebuie ca să se poată asculta fișierele audio", self._repara_codecuri, "Pregătește"),
            ("libreoffice", "LibreOffice, cu dicționarul românesc", self._repara_libreoffice, "Rezolvă"),
            ("drivere", "Driverele și componentele Windows", self._repara_drivere, "Vezi ce lipsește"),
            ("cai", "Legăturile care ar putea duce informația afară (internet, Wi-Fi, Bluetooth, stick)", self._arata_cai, "Arată-mi"),
        ]
        for cheie, titlu, comanda, text_buton in randuri_text:
            rand = RandVerificare(corp_card, titlu, comanda, text_buton)
            rand.pack(fill="x", pady=(0, ui_comun.px(6)))
            self.randuri[cheie] = rand

        rand_butoane = tk.Frame(corp, background=C.fundal)
        rand_butoane.pack(fill="x", pady=(ui_comun.px(12), 0))
        self.buton_reverifica = ui_comun.Buton(
            rand_butoane,
            "Verifică din nou",
            self.verifica,
            fel="principal",
            latime=300,
            inaltime=64,
        )
        self.buton_reverifica.pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(
            rand_butoane,
            "← Înapoi la început",
            lambda: self.aplicatie.arata_ecran("principal"),
            latime=280,
            inaltime=64,
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(
            rand_butoane, "Ajutor pentru acest ecran", self._ajutor, scurtatura="F1", latime=320, inaltime=64
        ).pack(side="left")

        self.zona_progres = tk.Frame(corp, background=C.fundal)
        self.zona_progres.pack(fill="x")

    def _ajutor(self) -> None:
        self.aplicatie.arata_ajutor("verificare")

    # ------------------------------------------------------------------ verificarea

    def verifica(self) -> None:
        """Citește starea reală a calculatorului (în fundal, fereastra nu îngheață)."""
        if self._se_verifica:
            return
        self._se_verifica = True
        for rand in self.randuri.values():
            rand.arata("necunoscut", "Se verifică…")
        self.buton_reverifica.seteaza_text("Se verifică…")
        self.buton_reverifica.activeaza(False)
        self.aplicatie.bara_stare.arata("Verific", "Citesc ce are calculatorul tău…", "lucru")
        threading.Thread(target=self._verifica_in_fundal, name="verificare", daemon=True).start()

    def _verifica_in_fundal(self) -> None:
        rezultate: dict[str, tuple[str, str, str]] = {}
        try:
            self._raport = resurse.verifica(config_modul.director_iesiri(self.config))
        except Exception as exc:
            jurnal.atentionare(f"Verificarea calculatorului a eșuat: {exc}")
        rezultate["calculator"] = self._stare_calculator()
        rezultate["sunet"] = self._stare_sunet()
        rezultate["transcriere"] = self._stare_transcriere()
        rezultate["codecuri"] = self._stare_codecuri()
        rezultate["libreoffice"] = self._stare_libreoffice()
        rezultate["drivere"] = self._stare_drivere()
        self.aplicatie.trimite(self._dupa_verificare, rezultate)

    def _stare_calculator(self) -> tuple[str, str, str]:
        raport = self._raport
        if raport is None:
            return "atentie", "Nu am putut citi informațiile calculatorului.", ""
        if not raport.poate_instala:
            motive = "; ".join(f"{c.nume}: {c.sfat or c.cerinta}" for c in raport.blocante)
            return (
                "lipsa",
                "Calculatorul nu îndeplinește cerințele obligatorii.",
                f"Ce lipsește: {motive} Poți arăta lista la magazin sau elibera spațiu pe disc. Nu este o problemă de drivere.",
            )
        if not raport.are_gpu:
            return (
                "atentie",
                "Calculatorul poate rula programul, dar fără accelerare video.",
                "Fără placă video, transcrierea merge pe procesor: mai încet, dar sigur. Poți continua liniștit.",
            )
        if not instalare._are_cuda(cai.python_mediu()):
            return (
                "atentie",
                "Placa video este potrivită, dar transcrierea folosește procesorul.",
                "Accelerarea CUDA nu este instalată. Rulează din nou instalarea pentru a o pregăti; "
                "programul funcționează și până atunci, doar mai încet.",
            )
        return (
            "ok",
            "Calculatorul are tot ce trebuie.",
            f"Memorie: {raport.ram_gb:.1f} GB · loc liber pe disc: {raport.disc_liber_gb:.1f} GB · "
            f"placă video: {raport.gpu_nume or 'fără'}.",
        )

    def _stare_sunet(self) -> tuple[str, str, str]:
        try:
            microfoane = dispozitive.microfoane()
            iesiri = dispozitive.iesiri()
        except Exception as exc:
            jurnal.atentionare(f"Citirea dispozitivelor de sunet a eșuat: {exc}")
            return "atentie", "Nu am putut citi lista dispozitivelor de sunet.", str(exc)
        if not microfoane and not iesiri:
            return (
                "lipsa",
                "Nu găsesc niciun microfon și niciun difuzor.",
                "Conectează un microfon sau căști cu microfon și apasă „Verifică sunetul”, "
                "apoi „Caută din nou”. Poți folosi programul și fără microfon, cu un fișier audio.",
            )
        if not microfoane:
            return (
                "lipsa",
                f"Nu găsesc niciun microfon (difuzoare și căști găsite: {len(iesiri)}).",
                "Fără microfon nu poți dicta, dar poți transcrie fișiere audio. Conectează un microfon "
                "sau căști cu microfon, apoi apasă „Verifică sunetul”.",
            )
        return (
            "ok",
            f"Am găsit {len(microfoane)} microfon{'e' if len(microfoane) > 1 else ''} și "
            f"{len(iesiri)} dispozitiv{'e' if len(iesiri) > 1 else ''} de ascultare.",
            "Apasă „Verifică sunetul” ca să le încerci pe rând: microfon, difuzoare, căști.",
        )

    def _stare_transcriere(self) -> tuple[str, str, str]:
        if not motor.biblioteci_disponibile():
            return (
                "lipsa",
                "Părțile de transcriere nu sunt instalate încă.",
                "Rulează instalarea programului (scurtătura „Instalare Dictare&Transcriere Română”). "
                "Se descarcă o singură dată, apoi programul merge fără internet.",
            )
        if not cai.fisier_model().exists():
            return (
                "lipsa",
                "Lipsește modelul de recunoaștere a vocii.",
                "Rulează instalarea: modelul se descarcă o singură dată (aproximativ 1,6 GB).",
            )
        return (
            "ok",
            "Transcrierea este pregătită (modelul local este pe calculator).",
            "Totul se face pe calculatorul tău: nimic nu pleacă pe internet.",
        )

    def _stare_codecuri(self) -> tuple[str, str, str]:
        try:
            stare = codecuri.verifica()
        except Exception as exc:
            jurnal.atentionare(f"Verificarea părților audio a eșuat: {exc}")
            return "atentie", "Nu am putut verifica părțile audio.", str(exc)
        if stare.ok:
            return "ok", "Fișierele audio se pot deschide (MP3, WAV, M4A, OGG, FLAC).", stare.pentru_utilizator()
        return (
            "atentie",
            "Pentru unele fișiere audio mai trebuie descărcat ceva.",
            stare.pentru_utilizator()
            + " Apasă „Pregătește”: se descarcă o singură dată, de pe sursa oficială.",
        )

    def _stare_libreoffice(self) -> tuple[str, str, str]:
        try:
            stare = libreoffice.stare()
        except Exception as exc:
            jurnal.atentionare(f"Verificarea LibreOffice a eșuat: {exc}")
            return "atentie", "Nu am putut verifica LibreOffice.", str(exc)
        if stare.gasit and stare.are_meniu_romana and stare.are_dictionar_romana:
            return "ok", f"LibreOffice {stare.versiune} este instalat, în română.", stare.pentru_utilizator()
        if stare.gasit:
            return "atentie", "LibreOffice este instalat, dar lipsește ceva pentru română.", stare.pentru_utilizator()
        return (
            "atentie",
            "LibreOffice nu este instalat.",
            "Poți salva documentele ca DOCX sau ODT și le poți deschide cu alt program de scris. "
            "Dacă vrei și LibreOffice, apasă butonul de alături (are nevoie de internet o singură dată).",
        )

    def _stare_drivere(self) -> tuple[str, str, str]:
        try:
            self._drivere = drivere.verifica()
        except Exception as exc:
            jurnal.atentionare(f"Verificarea driverelor a eșuat: {exc}")
            return "atentie", "Nu am putut verifica driverele.", str(exc)
        stare = self._drivere
        if stare.totul_ok:
            return "ok", "Driverele și componentele Windows sunt în regulă.", stare.rezumat()
        lipsa = "; ".join(f"{l.dispozitiv} ({l.ce_nu_merge})" for l in stare.lipsuri[:4])
        return (
            "lipsa" if stare.blocheaza_dictarea else "atentie",
            f"{len(stare.lipsuri)} lucruri lipsesc.",
            f"Ce lipsește: {lipsa}. Nu este o problemă de componente fizice: apasă butonul ca să vezi "
            "de unde se ia fiecare.",
        )

    def _dupa_verificare(self, rezultate: dict) -> None:
        self._se_verifica = False
        self.buton_reverifica.seteaza_text("Verifică din nou")
        self.buton_reverifica.activeaza(True)
        for cheie, rand in self.randuri.items():
            if cheie in rezultate:
                fel, text, explicatie = rezultate[cheie]
                rand.arata(fel, text, explicatie)
        # Indicatorul celor patru căi (punctul 22) se citește separat, ca să nu încurce restul.
        rand_cai = self.randuri["cai"]
        if self.indicator is not None:
            stare_cai = self.indicator.actualizeaza()
            deschise = [cale.titlu or securitate.NUME_CAI.get(cale.cheie, cale.cheie) for cale in stare_cai.deschise]
            if deschise:
                rand_cai.arata(
                    "atentie",
                    "Sunt deschise: " + ", ".join(deschise) + ".",
                    "Programul nostru nu trimite nimic, dar alte programe ar putea. Apasă „Arată-mi” "
                    "ca să vezi ce poți închide. Nimic nu se închide singur.",
                )
            else:
                rand_cai.arata("ok", "Totul e închis – lucrezi în siguranță.", stare_cai.pe_scurt())
        self.aplicatie.bara_stare.arata("Verificat", "Gata! Am citit ce are calculatorul tău.", "bine")

    # ------------------------------------------------------------------ butoane de reparare

    def _repara_calculator(self) -> None:
        from . import ui_calculator

        rezultat, _raport = ui_calculator.fereastra_calculator(self, self._raport)
        if rezultat == "iesire":
            return
        self.verifica()

    def _repara_sunet(self) -> None:
        ui_sunet.fereastra_verificare(self, la_terminare=self.verifica)

    def _repara_transcriere(self) -> None:
        self.aplicatie.ruleaza_instalarea(
            "Rulez instalarea ca să aduc părțile de transcriere (modelul de recunoaștere a vocii)."
        )
        self.after(2000, self.verifica)

    def _repara_codecuri(self) -> None:
        self.aplicatie.pregateste_codecurile(fortat=True)

    def _repara_libreoffice(self) -> None:
        self.aplicatie.instaleaza_libreoffice()

    def _repara_drivere(self) -> None:
        ui_drivere.fereastra_lipsesc_drivere(self, self._drivere)
        self.after(500, self.verifica)

    def _arata_cai(self) -> None:
        ui_internet.explica(self, self.config)

    def opreste_tot(self) -> None:
        """Ecranul nu ține niciun fir de lucru în urmă."""
        return

    def reimprospateaza(self) -> None:
        """Reîmprospătează ecranul de verificare: re-verifică resursele."""
        self.verifica()


# --------------------------------------------------------------------------- fereastra


class Aplicatie(tk.Tk):
    """Fereastra principală. Tot ce fac ecranele trece prin metodele de aici."""

    def __init__(self, optiuni=None):
        super().__init__()
        self.optiuni = optiuni
        ui_comun.seteaza_scala(self)
        self.configurare = config_modul.incarca()
        ui_comun.seteaza_marirea_scrisului(getattr(self.configurare, "marire_scris", 100))
        ui_comun.aplica_tema(getattr(self.configurare, "mod_afisare", "windows"))
        ui_comun.pregateste_fonturi(self)
        ui_comun.seteaza_titlu(self)
        _seteaza_pictograma(self)

        # Restaureaza geometria ferestrei de la pornirea anterioara, daca e valabila.
        geometrie = getattr(self.configurare, "geometrie_fereastra", "")
        if geometrie:
            try:
                self.geometry(geometrie)
            except Exception:
                pass

        self.stare = stare_modul.Stare(config=self.configurare)
        self.coada = ui_comun.CoadaUI(self)
        self._motor: motor.MotorWhisper | None = None
        self._pagini: dict[str, tk.Frame] = {}
        self._pagina_aleasa = ""
        self._indicator: ui_internet.IndicatorCai | None = None
        self._eticheta_limba: tk.Label | None = None
        self._eticheta_mesaj: tk.Label | None = None
        self._ultimele_randuri: list[tk.Frame] = []
        self._primul_click_editor = False
        self._mod_anterior = ui_comun.mod_aplicat()
        self._cale_document_urmarit: Path | None = None
        self._amprenta_document: tuple[float, int] = (0.0, 0)
        self._inceput_urmarire = 0.0
        self._cod_hotplug: str | None = None
        self._instalare_in_curs = False
        self._se_inchide = False

        self._construieste()
        self.protocol("WM_DELETE_WINDOW", self.cerere_inchidere)
        ui_comun.seteaza_scurtatura(self, "<F1>", lambda: self.arata_ajutor(self._pagina_aleasa or "principal"))
        ui_comun.seteaza_scurtatura(self, "<Control-d>", lambda: self.arata_ecran("dictare"))
        ui_comun.seteaza_scurtatura(self, "<Control-D>", lambda: self.arata_ecran("dictare"))
        ui_comun.seteaza_scurtatura(self, "<Control-o>", self.transcrie_fisier_ales)
        ui_comun.seteaza_scurtatura(self, "<Control-O>", self.transcrie_fisier_ales)
        ui_comun.seteaza_scurtatura(self, "<Control-t>", lambda: self.arata_ecran("transcriere"))
        ui_comun.seteaza_scurtatura(self, "<Control-T>", lambda: self.arata_ecran("transcriere"))
        ui_comun.seteaza_scurtatura(self, "<Control-s>", lambda: self.salveaza_document("docx"))
        ui_comun.seteaza_scurtatura(self, "<Control-S>", lambda: self.salveaza_document("docx"))
        ui_comun.seteaza_scurtatura(self, "<Control-plus>", self.mareste_scrisul)
        ui_comun.seteaza_scurtatura(self, "<Control-equal>", self.mareste_scrisul)
        ui_comun.seteaza_scurtatura(self, "<Control-KP_Add>", self.mareste_scrisul)
        ui_comun.seteaza_scurtatura(self, "<Control-minus>", self.micsoreaza_scrisul)
        ui_comun.seteaza_scurtatura(self, "<Control-KP_Subtract>", self.micsoreaza_scrisul)
        ui_comun.seteaza_scurtatura(self, "<Control-0>", self.reseteaza_scrisul)
        ui_comun.seteaza_scurtatura(self, "<Control-KP_0>", self.reseteaza_scrisul)
        self.bind("<Map>", self._la_afisare, add="+")
        self.after(400, self._la_pornire)

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        C = ui_comun.CULORI
        self.configure(background=C.fundal)
        latime_ecran, inaltime_ecran = ui_comun.maxim_ecran(0.95)
        lat_min = min(ui_comun.px(800), int(latime_ecran * 0.85))
        inalt_min = min(ui_comun.px(480), int(inaltime_ecran * 0.85))
        self.minsize(lat_min, inalt_min)
        if latime_ecran >= ui_comun.px(1280) and inaltime_ecran >= ui_comun.px(760):
            try:
                self.state("zoomed")
            except tk.TclError:
                ui_comun.centrat(self, latime=min(ui_comun.px(1100), latime_ecran), inaltime=min(ui_comun.px(720), inaltime_ecran))
        else:
            ui_comun.centrat(self, latime=min(ui_comun.px(980), latime_ecran), inaltime=min(ui_comun.px(620), inaltime_ecran))

        self._construieste_antetul()
        self._construieste_editorul()
        self._construieste_liniile_de_jos()
        self.arata_ecran("principal")
        self._reimprospateaza_ultimele()
        self._seteaza_mesajul_de_sus()

    def _construieste_antetul(self) -> None:
        """Antetul: numele programului, mesajul liniștitor, limba, ajutorul, indicatorul."""
        C = ui_comun.CULORI
        self._antet = tk.Frame(self, background=C.card, highlightthickness=ui_comun.px(1), highlightbackground=C.chenar)
        self._antet.pack(fill="x")
        interior = tk.Frame(self._antet, background=C.card)
        interior.pack(fill="x", padx=ui_comun.px(14), pady=ui_comun.px(10))

        stanga = tk.Frame(interior, background=C.card)
        stanga.pack(side="left", fill="x", expand=True)
        ui_comun.eticheta(stanga, NUME, "titlu", fundal=C.card, latime_bucati=560).pack(anchor="w")
        self._eticheta_mesaj = ui_comun.eticheta(
            stanga, constante.MESAJ_FARA_INTERNET, "baza", fundal=C.card, latime_bucati=560
        )
        self._eticheta_mesaj.pack(anchor="w")
        self._eticheta_limba = ui_comun.eticheta(stanga, self._text_limba(), "baza", fundal=C.card, latime_bucati=560)
        self._eticheta_limba.pack(anchor="w")

        dreapta = tk.Frame(interior, background=C.card)
        dreapta.pack(side="right", anchor="n")
        ui_comun.Buton(
            dreapta,
            "? Ajutor",
            lambda: self.arata_ajutor(self._pagina_aleasa or "principal"),
            scurtatura="F1",
            latime=200,
            inaltime=56,
        ).pack(anchor="e")
        self._indicator = ui_internet.indicator(dreapta, self.configurare)
        self._indicator.pack(anchor="e", pady=(ui_comun.px(8), 0))

    def _construieste_editorul(self) -> None:
        """Editorul integrat, ținut de fereastra principală (cerințele 12 și 8)."""
        self._zona_editor = tk.Frame(self, background=ui_comun.CULORI.fundal)
        self.editor = ui_editor.Editor(self._zona_editor, self.stare, la_actiune=self._dupa_scriere, inaltime=13)
        self.editor.pack(fill="both", expand=True)

    def _construieste_liniile_de_jos(self) -> None:
        C = ui_comun.CULORI
        self._jos = tk.Frame(self, background=C.fundal)
        self._jos.pack(side="bottom", fill="x")
        self._zona_editor.pack(side="bottom", fill="x", padx=ui_comun.px(10), pady=(0, ui_comun.px(6)))
        self._zona_editor.pack_forget()
        self._zona_pagini = tk.Frame(self, background=C.fundal)
        self._zona_pagini.pack(fill="both", expand=True)
        rand = tk.Frame(self._jos, background=C.fundal)
        rand.pack(fill="x", padx=ui_comun.px(14), pady=(0, ui_comun.px(4)))
        self.bara_stare = ui_comun.LinieStare(rand)
        self.bara_stare.pack(side="left", fill="x", expand=True)
        self._buton_folder = ui_comun.Buton(
            rand, "Deschide folderul documentelor", self._deschide_folderul, latime=280, inaltime=48
        )
        self._buton_folder.pack(side="right")

    # ------------------------------------------------------------------ ecrane

    def _ia_pagina(self, nume: str) -> tk.Frame:
        if nume in self._pagini:
            return self._pagini[nume]
        if nume == "principal":
            pagina: tk.Frame = PaginaPrincipala(self._zona_pagini, self)
        elif nume == "dictare":
            pagina = ui_dictare.PaginaDictare(self._zona_pagini, self)
        elif nume == "transcriere":
            pagina = ui_transcriere.PaginaTranscriere(self._zona_pagini, self)
        elif nume == "editor":
            pagina = PaginaEditor(self._zona_pagini, self)
        elif nume == "verificare":
            pagina = PaginaVerificare(self._zona_pagini, self)
        else:
            pagina = PaginaPrincipala(self._zona_pagini, self)
        self._pagini[nume] = pagina
        return pagina

    def arata_ecran(self, nume: str) -> None:
        """Trece la ecranul cerut, arătând editorul doar unde are rost."""
        nume = nume or "principal"
        if getattr(self, "_pagina_aleasa", None) == "dictare" and nume != "dictare":
            pagina_dictare = self._pagini.get("dictare")
            if pagina_dictare is not None and getattr(pagina_dictare, "_pornita", False):
                raspuns = ui_comun.dialog(
                    self,
                    "Dictarea este în curs",
                    "Dictarea este în curs. Oprești dictarea?",
                    [
                        ("Oprește dictarea", "pericol"),
                        ("Rămâi la dictare", "secundar"),
                    ],
                    implicit=1,
                    anulare=1,
                )
                if raspuns != 0:
                    return
                if hasattr(pagina_dictare, "opreste_dictarea"):
                    pagina_dictare.opreste_dictarea()
                elif hasattr(pagina_dictare, "_opreste"):
                    pagina_dictare._opreste()

        pagina = self._ia_pagina(nume)
        for alta in self._pagini.values():
            if alta is not pagina and alta.winfo_ismapped():
                alta.pack_forget()
        pagina.pack(fill="both", expand=True)
        self._pagina_aleasa = nume
        if nume in ECRANE_CU_EDITOR:
            if not self._zona_editor.winfo_ismapped():
                self._zona_pagini.pack_forget()
                self._zona_editor.pack(side="bottom", fill="x", padx=ui_comun.px(10), pady=(0, ui_comun.px(6)))
                self._zona_pagini.pack(fill="both", expand=True)
        elif self._zona_editor.winfo_ismapped():
            self._zona_editor.pack_forget()
        if nume == "principal":
            if hasattr(pagina, "sincronizeaza_din_stare"):
                pagina.sincronizeaza_din_stare()
            self._reimprospateaza_ultimele()
        if nume == "verificare" and not pagina.winfo_ismapped():
            pagina.verifica()
        if nume == "editor":
            self.editor.pune_focus()
        jurnal.info(f"Ecran deschis: {nume}.")

    def pagina(self, nume: str):
        """Pagina construită (sau se construiește acum) — folosită de alte module."""
        return self._ia_pagina(nume)

    # ------------------------------------------------------------------ ce se cere des de pagini

    def arata_ajutor(self, cheie: str = "principal") -> None:
        ui_ajutor.deschide(self, cheie)

    def mareste_scrisul(self) -> None:
        val = ui_comun.schimba_marimea_scrisului(delta=10, radacina=self)
        self.configurare.marire_scris = val
        self.bara_stare.arata("Scris", f"Mărime text: {val}%", "lucru")

    def micsoreaza_scrisul(self) -> None:
        val = ui_comun.schimba_marimea_scrisului(delta=-10, radacina=self)
        self.configurare.marire_scris = val
        self.bara_stare.arata("Scris", f"Mărime text: {val}%", "lucru")

    def reseteaza_scrisul(self) -> None:
        val = ui_comun.schimba_marimea_scrisului(exact=100, radacina=self)
        self.configurare.marire_scris = val
        self.bara_stare.arata("Scris", "Mărime text resetată la 100%", "lucru")

    def avertizeaza_internet(self, pentru_dictare: bool = False, fortat: bool = False) -> None:
        """Avertizarea roșie de securitate, cu cele patru căi (cerința 22)."""
        ui_internet.avertizeaza(self, self.configurare, pentru_dictare=bool(pentru_dictare), fortat=fortat)
        if self._indicator is not None:
            self._indicator.actualizeaza()

    def salveaza_document(self, fel: str = "docx", radacina: Path | None = None) -> Path | None:
        """Salvează textul de pe ecran ca document, apoi spune unde a ajuns."""
        cale = stare_modul.salveaza_document(self, self.stare, fel, radacina)
        if cale is None:
            return None
        self.configurare.ultimul_format = fel
        config_modul.salveaza(self.configurare)
        self.editor.actualizeaza_etichete()
        self._reimprospateaza_ultimele()
        ce_nume = cale.name
        raspuns = ui_comun.dialog(
            self,
            "Document salvat",
            f"Am salvat documentul „{ce_nume}” în folderul programului.\n\n"
            f"Aici este: {cale.parent}\n\n"
            "Ce vrei să faci acum?",
            [
                ("Deschide documentul", "principal"),
                ("Deschide folderul", "secundar"),
                ("Am înțeles", "secundar"),
            ],
            implicit=0,
            anulare=2,
        )
        if raspuns == 0:
            self.deschide_documentul(cale)
        elif raspuns == 1:
            self._deschide_folderul()
        self.bara_stare.arata("Salvat", f"Documentul este salvat: {ce_nume}", "bine")
        return cale

    def deschide_in_libreoffice(self, cale: Path | None = None) -> None:
        """Butonul principal: salvează DOCX și deschide documentul în programul de scris."""
        if cale is None:
            cale = self._salveaza_pentru_deschidere()
            if cale is None:
                return
        self.deschide_documentul(cale)

    def deschide_documentul(self, cale: Path, program_nume: str = "") -> None:
        """Deschide documentul în programul de scris ales (LibreOffice implicit)."""
        preferat = getattr(self.configurare, "program_scris_preferat", "")
        if preferat and preferat != "libreoffice" and not program_nume:
            program = programe_scris.dupa_cheie(preferat)
            if program is not None:
                reusit, mesaj = programe_scris.deschide(cale, program)
                if not reusit:
                    jurnal.atentionare(f"Documentul nu s-a putut deschide în „{program.nume}”: {mesaj}")
                    ui_comun.anunta(
                        self,
                        f"Nu am putut deschide documentul în „{program.nume}”",
                        "Îl deschid în LibreOffice.",
                        detalii=mesaj,
                    )
                    self._deschide_cu_libreoffice(cale)
                else:
                    self.bara_stare.arata("Deschis", f"Documentul este deschis în „{program.nume}”.", "bine")
                    self._porneste_urmarirea(cale)
                return
        self._deschide_cu_libreoffice(cale)

    def _deschide_cu_libreoffice(self, cale: Path) -> None:
        reusit, mesaj = libreoffice.deschide_in_writer(cale)
        if reusit:
            self.bara_stare.arata(
                "Deschis",
                f"Documentul este deschis în {libreoffice.nume_pentru_utilizator()}. "
                "Corectează-l acolo; programul își dă seama singur când îl salvezi.",
                "bine",
            )
            self._porneste_urmarirea(cale)
            return
        stare = libreoffice.stare()
        if not stare.gasit:
            raspuns = ui_comun.dialog(
                self,
                "LibreOffice nu este instalat",
                "Poți citi și corecta textul în editorul din program, iar documentul l-ai salvat deja.\n\n"
                "Vrei să instalez LibreOffice acum, în română, cu dicționarul românesc? "
                "(Este nevoie de internet o singură dată.)",
                [
                    ("Da, instalează LibreOffice", "principal"),
                    ("Nu acum", "secundar"),
                    ("Deschide cu alt program…", "secundar"),
                ],
                implicit=0,
                anulare=1,
            )
            if raspuns == 0:
                self.instaleaza_libreoffice(dupa_instalare=cale)
            elif raspuns == 2:
                self.alte_programe(cale)
            return
        ui_comun.dialog_eroare(
            self,
            erori.libreoffice_nu_a_pornit(mesaj),
            la_actiune=lambda fel: self._dupa_eroare_libreoffice(fel, cale),
        )

    def _dupa_eroare_libreoffice(self, fel: str, cale: Path) -> None:
        if fel == erori.INCERCARE_DIN_NOU:
            self._deschide_cu_libreoffice(cale)
        elif fel == erori.DESCHIDE_FOLDER:
            self._deschide_folderul(cale.parent)

    def alte_formate(self) -> None:
        """Fereastra „Alte formate…”: TXT, RTF, HTML, SRT, VTT, PDF și alte programe."""
        text = self.editor.text_ecran().strip()
        if not text:
            ui_comun.anunta(
                self,
                "Nu este nimic de salvat",
                "Textul este gol. Dictează sau transcrie ceva, apoi salvează.",
            )
            return
        alte = programe_scris.alte_programe()
        variante = [f"{nume}" for _cheie, nume in ALTE_FORMATE]
        variante.append("Deschide cu alt program de scris…")
        variante.append("Verifică textul cu LibreOffice (corectură)")
        raspuns = self._alege_din_lista(
            "Alte formate",
            "Alege în ce fel salvezi documentul. PDF-ul și corectura au nevoie de LibreOffice.",
            variante,
        )
        if raspuns is None:
            return
        if raspuns < len(ALTE_FORMATE):
            cheie = ALTE_FORMATE[raspuns][0]
            if cheie == "pdf":
                self._salveaza_pdf()
            else:
                self.salveaza_document(cheie)
            return
        if raspuns == len(ALTE_FORMATE):
            self._salveaza_ca_si_apoi_deschide()
            return
        if raspuns == len(ALTE_FORMATE) + 1:
            if not alte:
                ui_comun.anunta(
                    self,
                    "Nu am găsit alt program de scris",
                    "Pe acest calculator, singurul program de scris cu care pot deschide documentul "
                    "este LibreOffice. Butonul „Deschide în LibreOffice” face asta.",
                )
                return
            self.alte_programe()
            return
        self._corectura_cu_libreoffice()

    def alte_programe(self, cale: Path | None = None) -> None:
        """Lista cu celelalte programe de scris găsite pe calculator (cerința 18)."""
        programe = programe_scris.alte_programe()
        if not programe:
            ui_comun.anunta(
                self,
                "Nu am găsit alt program de scris",
                "Butonul „Deschide în LibreOffice” deschide documentul în LibreOffice, "
                "care este programul de scris al programului.",
            )
            return
        if cale is None:
            cale = self._salveaza_pentru_deschidere()
            if cale is None:
                return
        variante = [program.descriere() for program in programe]
        variante.append("Revino la LibreOffice")
        raspuns = self._alege_din_lista(
            "Deschide cu alt program",
            f"În care program deschizi „{cale.name}”?",
            variante,
        )
        if raspuns is None:
            return
        if raspuns == len(programe):
            self.configurare.program_scris_preferat = ""
            self.configurare.program_scris_nume = ""
            config_modul.salveaza(self.configurare)
            ui_comun.anunta(self, "Am revenit la LibreOffice", "De acum documentele se deschid în LibreOffice.")
            self._deschide_cu_libreoffice(cale)
            return
        program = programe[raspuns]
        reusit, mesaj = programe_scris.deschide(cale, program)
        if not reusit:
            ui_comun.anunta(
                self,
                f"Nu am putut deschide documentul în „{program.nume}”",
                "Îl deschid în LibreOffice.",
                detalii=mesaj,
            )
            self._deschide_cu_libreoffice(cale)
            return
        self.configurare.program_scris_preferat = program.cheie
        self.configurare.program_scris_nume = program.nume
        config_modul.salveaza(self.configurare)
        self.bara_stare.arata("Deschis", f"Documentul este deschis în „{program.nume}”.", "bine")
        self._porneste_urmarirea(cale)

    def _alege_din_lista(self, titlu: str, text: str, variante: list[str]) -> int | None:
        """Fereastra de alegere dintr-o listă, în română (fără ferestrele Windows)."""
        fereastra = tk.Toplevel(self)
        ui_comun.seteaza_titlu(fereastra, titlu)
        fereastra.configure(background=ui_comun.CULORI.fundal)
        fereastra.transient(self)
        rezultat: dict[str, int | None] = {"ales": None}
        cadru = tk.Frame(fereastra, background=ui_comun.CULORI.fundal)
        cadru.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(14))
        ui_comun.eticheta(cadru, titlu, "titlu").pack(anchor="w")
        ui_comun.eticheta(cadru, text, "baza", latime_bucati=620).pack(anchor="w", pady=(0, ui_comun.px(10)))
        zona = ui_comun.ZonaDerulare(cadru)
        zona.pack(fill="both", expand=True)

        def alege(index: int) -> None:
            rezultat["ales"] = index
            fereastra.destroy()

        for index, varianta in enumerate(variante):
            ui_comun.Buton(
                zona.interior,
                varianta,
                lambda i=index: alege(i),
                latime=620,
                inaltime=60,
                ancora="w",
            ).pack(anchor="w", pady=(0, ui_comun.px(6)))
        ui_comun.Buton(cadru, "Renunță", fereastra.destroy, latime=220, inaltime=56).pack(anchor="w", pady=(ui_comun.px(10), 0))
        fereastra.bind("<Escape>", lambda _e: fereastra.destroy())
        fereastra.update_idletasks()
        ui_comun.centrat(fereastra, latime=720, inaltime=560)
        fereastra.grab_set()
        self.wait_window(fereastra)
        return rezultat["ales"]

    def _salveaza_pdf(self) -> None:
        """PDF: se scrie întâi ODT, apoi se transformă cu LibreOffice (cerința 5)."""
        stare = libreoffice.stare()
        if not stare.gasit:
            ui_comun.anunta(
                self,
                "PDF-ul are nevoie de LibreOffice",
                "Salvează documentul ca DOCX sau ODT: se deschide în orice program de scris. "
                "Dacă vrei PDF, instalează LibreOffice (butonul „Da, instalează LibreOffice”).",
            )
            return
        cale = self._salveaza_pentru_deschidere("odt")
        if cale is None:
            return
        self.bara_stare.arata("PDF", "Fac documentul PDF. Durează puțin…", "lucru")
        self.update_idletasks()
        rezultat, mesaj = libreoffice.converteste(cale, "pdf")
        if rezultat is None:
            ui_comun.anunta(self, "Nu am putut face PDF-ul", "Încearcă din nou sau salvează ca DOCX.", detalii=mesaj)
            return
        self.bara_stare.arata("PDF gata", f"PDF-ul este salvat: {rezultat.name}", "bine")
        self._reimprospateaza_ultimele()
        raspuns = ui_comun.dialog(
            self,
            "PDF gata",
            f"Am făcut PDF-ul „{rezultat.name}” în folderul programului.\n\nCe vrei să faci acum?",
            [("Deschide PDF-ul", "principal"), ("Deschide folderul", "secundar"), ("Am înțeles", "secundar")],
            implicit=0,
            anulare=2,
        )
        if raspuns == 0:
            sisteme.deschide_fisier(rezultat)
        elif raspuns == 1:
            self._deschide_folderul(rezultat.parent)

    def _salveaza_ca_si_apoi_deschide(self) -> None:
        """„Deschide cu alt program…” direct din lista de formate."""
        cale = self._salveaza_pentru_deschidere()
        if cale is None:
            return
        self.alte_programe(cale)

    def _corectura_cu_libreoffice(self) -> None:
        """Trimite textul la LibreOffice pentru corectură (dicționarul românesc)."""
        if not libreoffice.stare().gasit:
            ui_comun.anunta(
                self,
                "Corectura are nevoie de LibreOffice",
                "Programul corectează singur diacriticele (ş → ș, ţ → ț). Pentru corectură "
                "ortografică completă este nevoie de LibreOffice.",
            )
            return
        ui_comun.anunta(
            self,
            "Corectura se face în LibreOffice",
            "Am salvat documentul și îl deschid în LibreOffice: acolo cuvintele greșite apar "
            "subliniate cu roșu, iar sugestiile sunt în meniul de click dreapta.",
        )
        self.deschide_in_libreoffice()

    def _salveaza_pentru_deschidere(self, fel: str = "docx") -> Path | None:
        """Salvează o copie în formatul cerut, gata de deschis în programul de scris."""
        text = self.stare.text_complet()
        if not text.strip():
            ui_comun.anunta(
                self,
                "Nu este nimic de trimis",
                "Textul este gol. Dictează sau transcrie ceva, apoi deschide documentul.",
            )
            return None
        marca = self.stare.marca_pentru_salvare()
        cale = self.stare.document_cale
        if cale is not None and cale.exists() and cale.suffix.lower() == f".{fel}":
            try:
                # documentul există deja: îl scriem din nou, cu textul de acum
                documente.salveaza(
                    text,
                    cale,
                    titlu=marca,
                    subtitlu="Transcriere făcută cu programul „Dictare&Transcriere Română”.",
                    segmente=self.stare.segmente,
                    secunde=self.stare.durata_audio,
                )
                return cale
            except Exception as exc:
                jurnal.atentionare(f"Rescrierea documentului a eșuat: {exc}")
        return self.salveaza_document(fel)

    # ------------------------------------------------------------------ urmărirea documentului

    def _porneste_urmarirea(self, cale: Path) -> None:
        """Ține minte documentul deschis, ca să vadă când este salvat din nou."""
        try:
            info = cale.stat()
        except OSError:
            return
        self._cale_document_urmarit = cale
        self._amprenta_document = (info.st_mtime, info.st_size)
        self._inceput_urmarire = time.monotonic()
        self.after(int(SECUNDE_VERIFICARE_DOCUMENT * 1000), self._verifica_documentul)

    def _verifica_documentul(self) -> None:
        cale = self._cale_document_urmarit
        if cale is None or self._se_inchide:
            return
        if time.monotonic() - self._inceput_urmarire > SECUNDE_URMARIRE_DOCUMENT:
            self._cale_document_urmarit = None
            return
        try:
            info = cale.stat()
        except OSError:
            self._cale_document_urmarit = None
            return
        amprenta = (info.st_mtime, info.st_size)
        if amprenta != self._amprenta_document:
            self._amprenta_document = amprenta
            self._ia_modificarile_din_document(cale)
        if self._cale_document_urmarit is not None:
            self.after(int(SECUNDE_VERIFICARE_DOCUMENT * 1000), self._verifica_documentul)

    def _ia_modificarile_din_document(self, cale: Path) -> None:
        """„Am văzut că ai salvat documentul: iau modificările în editor?” (cerința 23.9)."""
        if self._pagina_aleasa in ("dictare", "transcriere"):
            # nu întrerupem lucrul în curs; verificăm mai târziu
            self.after(4000, lambda: self._ia_modificarile_din_document(cale))
            return
        try:
            text = documente.citeste_text(cale)
        except Exception as exc:
            jurnal.atentionare(f"Documentul nu a putut fi citit înapoi: {exc}")
            return
        if not text.strip():
            return
        raspuns = ui_comun.dialog(
            self,
            "Am văzut modificările tale",
            f"Documentul „{cale.name}” a fost salvat din nou în programul de scris.\n\n"
            "Iau textul așa cum l-ai corectat acolo, aici în editor?",
            [
                ("Da, iau modificările", "principal"),
                ("Nu, lasă cum era", "secundar"),
                ("Deschide documentul", "secundar"),
            ],
            implicit=0,
            anulare=1,
        )
        if raspuns == 0:
            self.stare.fixeaza_text(text, "editor")
            self.editor.seteaza_text(text)
            self.editor.salveaza_automat()
            self.arata_ecran("editor")
            self.bara_stare.arata(
                "Modificări luate", "Textul din document este acum și în editorul programului.", "bine"
            )
        elif raspuns == 2:
            self.deschide_documentul(cale)

    # ------------------------------------------------------------------ pornirea

    def _la_pornire(self) -> None:
        """Ce se face la fiecare pornire: verificări, recuperare, tur (cerințele 14, 20, 24, 26)."""
        self.editor.actualizeaza_etichete()
        self.bara_stare.arata("Gata", "Programul este pornit. Alege ce vrei să faci.", "normal")
        if not self._instalarea_este_completa():
            self.bara_stare.arata(
                "Repară instalarea",
                "Fără instalare completă, transcrierea nu poate porni. Deschide instalarea pentru a repara.",
                "atentie",
            )
            return
        self._verifica_codecurile_la_pornire()
        self.after(300, self._intreaba_de_text_recuperat)
        self.after(600, self._intreaba_de_lucrul_neterminat)
        self.after(1200, self._verifica_driverele_la_pornire)
        if not self.configurare.tur_vazut:
            self.after(1500, lambda: ui_tur.porneste(self, la_final=self._dupa_tur))

    def _instalarea_este_completa(self) -> bool:
        try:
            lipsa = instalare.verifica_instalare()
        except Exception as exc:
            jurnal.atentionare(f"Verificarea instalării a eșuat: {exc}")
            return True
        return not lipsa

    def _verifica_codecurile_la_pornire(self) -> None:
        """Cerința 24: la fiecare pornire se verifică ce trebuie pentru fișierele audio."""
        def in_fundal() -> None:
            try:
                are_nevoie = codecuri.are_nevoie()
            except Exception as exc:
                jurnal.atentionare(f"Verificarea părților audio a eșuat: {exc}")
                return
            if are_nevoie:
                self.trimite(self._codecuri_lipsa)

        threading.Thread(target=in_fundal, name="codecuri-pornire", daemon=True).start()

    def _codecuri_lipsa(self) -> None:
        self.bara_stare.arata(
            "Pregătesc",
            "Programul pregătește ce îi trebuie ca să poată asculta fișierele tale audio.",
            "lucru",
        )
        self.pregateste_codecurile()

    def pregateste_codecurile(self, fortat: bool = False) -> None:
        """Aduce ce trebuie pentru fișierele audio, cu progres și buton de oprire (24)."""
        pagina = self._ia_pagina("verificare")
        if isinstance(pagina, PaginaVerificare):
            self.arata_ecran("verificare")
        rezultat = {"oprit": False}

        def opreste() -> None:
            rezultat["oprit"] = True
            jurnal.info("Utilizatorul a oprit pregătirea părților audio.")

        self._instalare_in_curs = True
        try:
            parinte = self._pagina_aleasa_ferestra()
            zona = ui_comun.ZonaDerulare(parinte, latime_minima=820)
            zona.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(12))
            corp = tk.Frame(zona.interior, background=ui_comun.CULORI.fundal)
            corp.pack(fill="both", expand=True)
            ui_comun.eticheta(corp, "Pregătesc ce trebuie pentru fișierele audio", "titlu").pack(anchor="w")
            ui_comun.eticheta(
                corp,
                codecuri.MESAJ_PREGATIRE,
                "baza",
                latime_bucati=820,
            ).pack(anchor="w", pady=(0, ui_comun.px(10)))
            from . import ui_progres

            progres = ui_comun.ZonaProgres if False else None  # loc ținut pentru lizibilitate
            progres = ui_comun.ZonaProgres if False else None  # loc ținut pentru lizibilitate
            from . import ui_progres

            zona_progres = ui_progres.ZonaProgres(corp, "Descarc ce trebuie de pe sursa oficială", la_oprire=opreste)
            zona_progres.pack(fill="x")
            zona_progres.incepe("Verific ce am deja pe calculator", 1, 3)
            self.update_idletasks()

            def raporteaza(mesaj: str, fractiune: float) -> None:
                try:
                    zona_progres.seteaza(fractiune, mesaj)
                except tk.TclError:
                    pass

            stare_initiala = codecuri.verifica()
            if stare_initiala.ok and not fortat:
                zona_progres.gata("Totul este la locul lui: fișierele audio se pot deschide.")
                self.after(1500, lambda: self.arata_ecran("verificare"))
                return
            try:
                cale = codecuri.asigura(raporteaza)
            except codecuri.EroareCodecuri as exc:
                if getattr(exc, "fara_internet", False):
                    zona_progres.reseteaza()
                    raspuns = ui_comun.dialog(
                        self,
                        "Am nevoie de internet o singură dată",
                        exc.mesaj,
                        [("Încearcă din nou", "principal"), ("Trimite-mi pașii într-un fișier", "secundar"), ("Închide", "secundar")],
                        implicit=0,
                        anulare=2,
                    )
                    if raspuns == 0:
                        self.pregateste_codecurile(fortat=True)
                    elif raspuns == 1:
                        cale_fisier = codecuri.scrie_pasii_in_citeste_ma()
                        self._arata_fisierul_scris(cale_fisier)
                    self.avertizeaza_internet(fortat=True)
                    return
                zona_progres.reseteaza()
                ui_comun.dialog_eroare(
                    self,
                    erori.din_exceptie(exc, "pregătirea părților audio"),
                    la_actiune=lambda fel: self._dupa_eroare_codecuri(fel),
                )
                return
            if rezultat["oprit"]:
                zona_progres.reseteaza()
                self.bara_stare.arata("Oprit", "Ai oprit pregătirea. Se reia data viitoare când porniți programul.", "atentie")
                return
            zona_progres.gata("Gata! Fișierele audio se pot deschide acum.")
            if cale is not None:
                jurnal.info(f"Părțile audio sunt gata: {cale}")
            self.after(2000, lambda: self.arata_ecran("verificare"))
        finally:
            self._instalare_in_curs = False

    def _dupa_eroare_codecuri(self, fel: str) -> None:
        if fel == erori.INCERCARE_DIN_NOU:
            self.pregateste_codecurile(fortat=True)
        elif fel == erori.DESCHIDE_FOLDER:
            self._deschide_folderul()

    def _arata_fisierul_scris(self, cale) -> None:
        if cale is None:
            return
        ui_comun.anunta(
            self,
            "Am scris pașii într-un fișier",
            f"Pașii sunt în „{Path(cale).name}”, lângă program. Îl poți deschide cu orice program "
            "de text sau îl poți da cuiva care se pricepe.",
        )
        sisteme.deschide_fisier(Path(cale))

    def _pagina_aleasa_ferestra(self) -> tk.Misc:
        """Un părinte curat pentru ferestrele trecătoare."""
        return self

    def _intreaba_de_text_recuperat(self) -> None:
        """„Am găsit un text nesalvat de data trecută. Îl recuperez?” (cerința 14)."""
        try:
            gasit = biblioteca.citeste_recuperare()
        except Exception as exc:
            jurnal.atentionare(f"Textul de siguranță nu a putut fi citit: {exc}")
            return
        if not gasit:
            return
        text, marca, detalii = gasit
        if not text.strip():
            return
        raspuns = ui_comun.dialog(
            self,
            "Am găsit un text nesalvat de data trecută",
            f"Textul are {len(text.split())} cuvinte și este din {detalii or 'o lucrare mai veche'}.\n\n"
            "Îl recuperez? (Îl poți salva apoi ca document.)",
            [("Da, recuperează-l", "principal"), ("Nu, șterge-l", "secundar")],
            implicit=0,
            anulare=0,
        )
        if raspuns == 0:
            self.stare.fixeaza_text(text, "editor")
            if marca:
                self.stare.marca = marca
            self.editor.seteaza_text(text)
            self.arata_ecran("editor")
            self.bara_stare.arata(
                "Recuperat", "Textul nesalvat de data trecută este acum în editor.", "bine"
            )
        else:
            biblioteca.sterge_recuperare()
        self._reimprospateaza_ultimele()

    def _intreaba_de_lucrul_neterminat(self) -> None:
        """„Data trecută nu am terminat. Vrei să continui de unde ai rămas?” (cerința 26)."""
        if not operatiuni.are_text_salvat():
            return
        lucru = operatiuni.citeste()
        if lucru is None:
            return
        if lucru.fel not in ("transcriere", "dictare"):
            return
        raspuns = ui_comun.dialog(
            self,
            "Data trecută nu am terminat",
            lucru.propozitie() + "\n\nVrei să continui de unde ai rămas?",
            [
                ("Continuă de unde ai rămas", "principal"),
                ("Salvează ce am", "secundar"),
                ("Renunță", "secundar"),
            ],
            implicit=0,
            anulare=2,
        )
        if raspuns == 0:
            if lucru.fel == "transcriere":
                pagina = self._ia_pagina("transcriere")
                self.arata_ecran("transcriere")
                continua = getattr(pagina, "continua_din_operatiune", None)
                if continua is not None:
                    continua(lucru)
            else:
                pagina = self._ia_pagina("dictare")
                self.arata_ecran("dictare")
                continua = getattr(pagina, "continua_din_operatiune", None)
                if continua is not None:
                    continua(lucru)
            return
        if raspuns == 1:
            self._salveaza_textul_de_siguranta()
            return
        operatiuni.sterge()
        biblioteca.sterge_recuperare()

    def _salveaza_textul_de_siguranta(self) -> None:
        gasit = biblioteca.citeste_recuperare()
        if not gasit:
            return
        text, marca, _detalii = gasit
        self.stare.fixeaza_text(text, "editor")
        if marca:
            self.stare.marca = marca
        self.salveaza_document(self.configurare.ultimul_format or "docx")
        operatiuni.sterge()

    def _verifica_driverele_la_pornire(self) -> None:
        """Driverele se verifică la fiecare pornire (cerința 20), fără să încurce."""
        def in_fundal() -> None:
            try:
                stare = drivere.verifica()
            except Exception as exc:
                jurnal.atentionare(f"Verificarea driverelor a eșuat: {exc}")
                return
            if stare.totul_ok:
                return
            self.trimite(self._drivere_lipsa, stare)

        threading.Thread(target=in_fundal, name="drivere-pornire", daemon=True).start()

    def _drivere_lipsa(self, stare) -> None:
        rand = getattr(self._pagina_aleasa_obj(), "randuri", None)
        if isinstance(rand, dict) and "drivere" in rand:
            rand["drivere"].arata(
                "lipsa" if stare.blocheaza_dictarea else "atentie",
                stare.rezumat(),
                "Apasă „Vezi ce lipsește”.",
            )
        ui_drivere.fereastra_lipsesc_drivere(self, stare)

    def _pagina_aleasa_obj(self):
        return self._pagini.get(self._pagina_aleasa)

    def _dupa_tur(self) -> None:
        self.configurare.tur_vazut = True
        config_modul.salveaza(self.configurare)
        self.arata_ecran("principal")

    # ------------------------------------------------------------------ instalare / LibreOffice

    def ruleaza_instalarea(self, motiv: str = "") -> None:
        """Deschide fereastra de instalare (se poate opri oricând — cerința 26)."""
        from . import ui_instalare

        self._instalare_in_curs = True
        ui_instalare.deschide(self, motiv=motiv, la_final=self._dupa_instalare)

    def _dupa_instalare(self, reusit: bool) -> None:
        self._instalare_in_curs = False
        self.editor.actualizeaza_etichete()
        if reusit:
            self.bara_stare.arata("Instalat", "Instalarea s-a terminat. Programul este gata de folosit.", "bine")
            pagina = self._pagini.get("verificare")
            if isinstance(pagina, PaginaVerificare):
                pagina.verifica()
        else:
            self.bara_stare.arata(
                "Instalarea nu s-a terminat",
                "O poți relua oricând: ce s-a descărcat se păstrează.",
                "atentie",
            )

    def instaleaza_libreoffice(self, dupa_instalare: Path | None = None) -> None:
        """Instalează LibreOffice în română, cu progres și oprire (cerințele 17 și 26)."""
        from . import ui_instalare

        ui_instalare.instaleaza_libreoffice(self, dupa_instalare=dupa_instalare)

    # ------------------------------------------------------------------ editorul

    def _dupa_scriere(self) -> None:
        """La prima scriere în editor se verifică și legăturile (cerința 22)."""
        if self._primul_click_editor:
            return
        self._primul_click_editor = True
        self.avertizeaza_internet(pentru_dictare=False)

    def _seteaza_mesajul_de_sus(self) -> None:
        if self._eticheta_limba is not None:
            self._eticheta_limba.configure(text=self._text_limba())

    def _text_limba(self) -> str:
        limba = getattr(self.configurare, "limba", "ro") or "ro"
        nume = limba
        for eticheta, cod in constante.LIMBI:
            if cod == limba:
                nume = eticheta
                break
        if limba == "ro":
            return "Limba vorbită: Română"
        return f"Limba vorbită: {nume} (interfața rămâne în română)"

    def _reimprospateaza_ultimele(self) -> None:
        for rand in self._ultimele_randuri:
            rand.destroy()
        self._ultimele_randuri = []
        pagina = self._pagini.get("principal")
        if not isinstance(pagina, PaginaPrincipala):
            return
        pagina.reimprospateaza()

    # ------------------------------------------------------------------ aspectul (cerința 27)

    def _la_afisare(self, _eveniment=None) -> None:
        self.reimprospateaza_aspectul()

    def reimprospateaza_aspectul(self) -> None:
        """Aplică modul de afișare și reface ecranele dacă modul s-a schimbat."""
        dorit = ui_comun.aplica_tema(getattr(self.configurare, "mod_afisare", "windows"))
        if dorit == self._mod_anterior:
            return
        self._mod_anterior = dorit
        self._reconstruieste()

    def schimba_aspectul(self) -> None:
        """Forțează refacerea ecranelor (se cheamă din „Setări”)."""
        self._mod_anterior = ui_comun.aplica_tema(getattr(self.configurare, "mod_afisare", "windows"))
        self._reconstruieste()

    def _reconstruieste(self) -> None:
        """Reface toată fereastra cu culorile și scrisul de acum."""
        pagina_aleasa = self._pagina_aleasa or "principal"
        for pagina in self._pagini.values():
            pagina.destroy()
        self._pagini = {}
        ui_comun.pregateste_fonturi(self)
        self._zona_editor.destroy()
        self._antet.destroy()
        self._jos.destroy()
        self._construieste_antetul()
        self._construieste_editorul()
        self._construieste_liniile_de_jos()
        text = self.stare.text_complet()
        self.arata_ecran(pagina_aleasa)
        if text:
            self.editor.seteaza_text(text)
        self._reimprospateaza_ultimele()

    # ------------------------------------------------------------------ ieșirea

    def cerere_inchidere(self) -> None:
        """Întrebarea de la închidere: textul nu se pierde niciodată (cerințele 14 și 26)."""
        if self._instalare_in_curs:
            raspuns = ui_comun.dialog(
                self,
                "Se lucrează",
                "O instalare sau o descărcare este în curs. Dacă închizi acum, se oprește.\n\n"
                "Ce s-a descărcat se păstrează și se reia data viitoare.",
                [("Oprește și închide", "principal"), ("Lasă-l să meargă", "secundar")],
                implicit=1,
                anulare=1,
            )
            if raspuns != 0:
                return
        pagina = self._pagini.get(self._pagina_aleasa)
        if pagina is not None and hasattr(pagina, "este_ocupata") and pagina.este_ocupata():
            raspuns = ui_comun.dialog(
                self,
                "Se lucrează",
                "Lucrul este în curs. Dacă închizi acum, se oprește, iar textul scris până acum "
                "se păstrează.\n\nPoți continua data viitoare de unde ai rămas.",
                [("Oprește și închide", "principal"), ("Lasă-l să meargă", "secundar")],
                implicit=1,
                anulare=1,
            )
            if raspuns != 0:
                return
            pagina.opreste_tot()
        if not stare_modul.pregateste_iesire(self, self.stare):
            return
        # Salveaza geometria ferestrei pentru data viitoare.
        try:
            self.configurare.geometrie_fereastra = self.geometry()
            config_modul.salveaza(self.configurare)
        except Exception:
            pass
        self._se_inchide = True
        self.inchide()

    def inchide(self) -> None:
        """Oprește tot ce lucrează în fundal, apoi închide fereastra."""
        self.stare.salveaza_de_siguranta("închiderea programului")
        for pagina in self._pagini.values():
            opreste = getattr(pagina, "opreste_tot", None)
            if opreste is not None:
                try:
                    opreste()
                except Exception:
                    pass
        try:
            if self._motor is not None:
                self._motor.elibereaza()
        except Exception:
            pass
        try:
            codecuri.curata_temporare()
        except Exception:
            pass
        try:
            self.coada.opreste()
        except Exception:
            pass
        try:
            inregistrare.opreste_redarea()
        except Exception:
            pass
        jurnal.info("Programul s-a închis.")
        self.destroy()

    # ------------------------------------------------------------------ ajutoare

    @property
    def motor(self) -> motor.MotorWhisper:
        """Motorul de transcriere, încărcat o singură dată, când este nevoie de el."""
        if self._motor is None:
            self._motor = motor.MotorWhisper(getattr(self.configurare, "dispozitiv", "auto"))
        return self._motor

    @property
    def config(self):
        """Numele scurt folosit de ecrane pentru setări."""
        return self.configurare

    def trimite(self, functie, *argumente, **numite) -> None:
        """Trimite o lucrare în firul interfeței (niciodată Tk din alt fir)."""
        self.coada.trimite(functie, *argumente, **numite)

    def transcrie_fisier_ales(self) -> None:
        """Ctrl+O sau cardul de transcriere: se alege fișierul, apoi se trece la ecran."""
        self.arata_ecran("transcriere")
        pagina = self._pagini.get("transcriere")
        if pagina is not None and hasattr(pagina, "_alege_fisier"):
            pagina._alege_fisier()

    def deschide_fisierele(self) -> None:
        ui_fisiere.deschide(self, self._la_deschidere_fisier)

    def _la_deschidere_fisier(self, element, fel_actiune: str) -> None:
        if fel_actiune == "transcrie":
            pagina = self._ia_pagina("transcriere")
            self.arata_ecran("transcriere")
            ia = getattr(pagina, "_ia_fisierul", None)
            if ia is not None:
                ia(element.cale)
            return
        self._deschide_in_editor(element.cale)

    def _deschide_in_editor(self, cale: Path) -> None:
        """Deschide un document salvat, înapoi în editorul programului."""
        try:
            text = documente.citeste_text(cale)
        except Exception as exc:
            jurnal.eroare(f"Documentul „{cale.name}” nu a putut fi citit: {exc}")
            ui_comun.dialog_eroare(self, erori.din_exceptie(exc, f"citirea documentului „{cale.name}”"))
            return
        if not text.strip():
            ui_comun.anunta(
                self,
                "Documentul este gol",
                "În acest document nu am găsit text. Alege altul din „Fișierele mele”.",
            )
            return
        if self.stare.are_text() and self.stare.text_complet().strip() != text.strip():
            if not stare_modul.pregateste_schimbarea(
                self, self.stare, f"Deschizi documentul „{cale.name}”, iar textul de pe ecran se înlocuiește."
            ):
                return
        self.stare.fixeaza_text(text, "editor")
        self.stare.marca = biblioteca.marca_din_nume(cale)
        self.stare.document_cale = cale
        self.stare.marcheaza_salvat()
        self.editor.seteaza_text(text)
        self.arata_ecran("editor")
        self.bara_stare.arata("Deschis", f"Documentul „{cale.name}” este în editor.", "bine")

    def deschide_setarile(self) -> None:
        ui_setari.deschide(self, self.configurare, self._dupa_setari)

    def _dupa_setari(self, configurare=None) -> None:
        if configurare is not None:
            self.configurare = configurare
        config_modul.salveaza(self.configurare)
        ui_comun.seteaza_marirea_scrisului(getattr(self.configurare, "marire_scris", 100))
        self.schimba_aspectul()
        self._seteaza_mesajul_de_sus()
        if self._indicator is not None:
            self._indicator.actualizeaza()

    def verifica_sunetul(self) -> None:
        ui_sunet.fereastra_verificare(self, la_terminare=self._dupa_sunet)

    def _dupa_sunet(self) -> None:
        self.configurare.sunet_testat = True
        config_modul.salveaza(self.configurare)
        pagina = self._pagini.get("verificare")
        if isinstance(pagina, PaginaVerificare):
            pagina.verifica()

    def _deschide_folderul(self, cale: Path | None = None) -> None:
        if cale is None:
            cale = biblioteca.radacina(self.configurare)
        try:
            biblioteca.asigura(cale)
        except Exception:
            pass
        if not sisteme.deschide_folder(cale):
            ui_comun.anunta(
                self,
                "Nu am putut deschide folderul",
                f"Deschide-l manual din Windows: {cale}",
            )

    def deschide_ecranul_de_verificare(self) -> None:
        self.arata_ecran("verificare")


# --------------------------------------------------------------------------- ecranul de început


class PaginaPrincipala(tk.Frame):
    """Ecranul curat de început: trei carduri mari, ultimele documente, butoane mici."""

    def __init__(self, parinte: tk.Misc, aplicatie: Aplicatie):
        super().__init__(parinte, background=ui_comun.CULORI.fundal)
        self.aplicatie = aplicatie
        self.config = aplicatie.config
        self._randuri: list[tk.Frame] = []
        self._construieste()

    def _construieste(self) -> None:
        C = ui_comun.CULORI
        zona = ui_comun.ZonaDerulare(self, latime_minima=900)
        zona.pack(fill="both", expand=True)
        corp = tk.Frame(zona.interior, background=C.fundal)
        corp.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(12))
        self.corp = corp

        # Textul principal, sus, pe toata latimea, cu colturi rotunjite.
        zona = tk.Canvas(corp, background=C.fundal, highlightthickness=0, bd=0)
        zona.pack(fill="both", expand=True)
        raza = ui_comun.px(12)

        def _redesenat(_e=None):
            try:
                w = zona.winfo_width()
                h = zona.winfo_height()
                if w <= 1 or h <= 1:
                    return
                zona.delete("text_bg")
                ui_comun._rotunjeste(zona, 2, 2, w - 2, h - 2, raza, fill=C.zona_text, outline=C.chenar, width=ui_comun.px(2), tags="text_bg")
            except Exception:
                pass

        interior = tk.Frame(zona, background=C.zona_text)
        interior_window = zona.create_window(ui_comun.px(12), ui_comun.px(12), window=interior, anchor="nw")

        def _resize(_e=None):
            try:
                w = zona.winfo_width()
                h = zona.winfo_height()
                if w <= 1 or h <= 1:
                    return
                zona.coords(interior_window, ui_comun.px(12), ui_comun.px(12))
                zona.itemconfigure(interior_window, width=max(1, w - ui_comun.px(24)), height=max(1, h - ui_comun.px(24)))
                _redesenat()
            except Exception:
                pass

        zona.bind("<Configure>", _resize)

        self.text = tk.Text(
            interior,
            wrap="word" if getattr(self.config, "wrap_text", True) else "none",
            font=(getattr(self.config, "font_text", "") or ui_comun.familia(),
                  max(12, int(14 * getattr(self.config, "marire_scris", 100) / 100))),
            background=C.zona_text,
            foreground=C.text,
            insertbackground=C.text,
            highlightthickness=0,
            bd=0,
            undo=True,
            padx=ui_comun.px(getattr(self.config, "margini_text", 8)),
            pady=ui_comun.px(getattr(self.config, "margini_text", 8)),
        )
        derulare = tk.Scrollbar(interior, command=self.text.yview)
        self.text.configure(yscrollcommand=derulare.set)
        self.text.pack(side="left", fill="both", expand=True)
        derulare.pack(side="right", fill="y")

        try:
            initial = self.aplicatie.stare.text_complet()
            if initial:
                self.text.insert("1.0", initial)
        except Exception:
            pass
        self.text.bind("<KeyRelease>", lambda _e: self._sincronizeaza_text())
        self.text.bind("<Control-z>", lambda _e: (self.text.edit_undo(), self._sincronizeaza_text(), "break")[2])
        self.text.bind("<Control-Z>", lambda _e: (self.text.edit_undo(), self._sincronizeaza_text(), "break")[2])
        self.text.bind("<Control-y>", lambda _e: (self.text.edit_redo(), self._sincronizeaza_text(), "break")[2])
        self.text.bind("<Control-Y>", lambda _e: (self.text.edit_redo(), self._sincronizeaza_text(), "break")[2])
        self.text.bind("<Control-t>", lambda _e: (self.aplicatie.arata_ecran("transcriere"), "break")[1])
        self.text.bind("<Control-T>", lambda _e: (self.aplicatie.arata_ecran("transcriere"), "break")[1])
        self.text.bind("<Control-d>", lambda _e: (self._porneste_dictarea(), "break")[1])
        self.text.bind("<Control-D>", lambda _e: (self._porneste_dictarea(), "break")[1])
        self.text.bind("<Control-o>", lambda _e: (self.aplicatie.transcrie_fisier_ales(), "break")[1])
        self.text.bind("<Control-O>", lambda _e: (self.aplicatie.transcrie_fisier_ales(), "break")[1])
        self.text.bind("<Control-s>", lambda _e: (self.aplicatie.salveaza_document("docx"), "break")[1])
        self.text.bind("<Control-S>", lambda _e: (self.aplicatie.salveaza_document("docx"), "break")[1])
        self.text.bind("<Control-plus>", lambda _e: (self.aplicatie.mareste_scrisul(), "break")[1])
        self.text.bind("<Control-equal>", lambda _e: (self.aplicatie.mareste_scrisul(), "break")[1])
        self.text.bind("<Control-KP_Add>", lambda _e: (self.aplicatie.mareste_scrisul(), "break")[1])
        self.text.bind("<Control-minus>", lambda _e: (self.aplicatie.micsoreaza_scrisul(), "break")[1])
        self.text.bind("<Control-KP_Subtract>", lambda _e: (self.aplicatie.micsoreaza_scrisul(), "break")[1])
        self.text.bind("<Control-0>", lambda _e: (self.aplicatie.reseteaza_scrisul(), "break")[1])
        self.text.bind("<Control-KP_0>", lambda _e: (self.aplicatie.reseteaza_scrisul(), "break")[1])

        # Linie de stare deasupra barei de jos.
        self.linie_stare = tk.Label(
            self, text="Gata de dictare", font=ui_comun.fonturi().baza,
            background=C.fundal, foreground=C.text_secundar, anchor="w",
        )
        self.linie_stare.pack(fill="x", padx=ui_comun.px(16), pady=(0, ui_comun.px(4)))

        # Bara de jos cu butoanele esențiale.
        jos = tk.Frame(self, background=C.fundal)
        jos.pack(fill="x", padx=ui_comun.px(16), pady=ui_comun.px(12))
        self.btn_dicteaza = ui_comun.Buton(
            jos, "Dictează", self._porneste_dictarea, fel="principal", latime=200, inaltime=56
        )
        self.btn_dicteaza.pack(side="left", padx=(0, ui_comun.px(8)))
        self.btn_opreste = ui_comun.Buton(
            jos, "Oprește", self._opreste_dictarea, latime=160, inaltime=56
        )
        self.btn_opreste.pack(side="left", padx=(0, ui_comun.px(8)))
        self.btn_salveaza = ui_comun.Buton(
            jos, "Salvează", lambda: self.aplicatie.salveaza_document("docx"), fel="principal", latime=180, inaltime=56
        )
        self.btn_salveaza.pack(side="left", padx=(0, ui_comun.px(8)))
        self.btn_libreoffice = ui_comun.Buton(
            jos, "Deschide în LibreOffice", self._deschide_in_libreoffice, latime=250, inaltime=56
        )
        self.btn_libreoffice.pack(side="left", padx=(0, ui_comun.px(8)))
        self.btn_libreoffice.activeaza(self.aplicatie.stare.are_text())
        self.btn_salveaza.activeaza(self.aplicatie.stare.are_text())

        self.btn_meniu = ui_comun.Buton(
            jos, "Meniu", self._deschide_meniu, latime=140, inaltime=56
        )
        self.btn_meniu.pack(side="right", padx=(ui_comun.px(8), 0))
        self.btn_setari = ui_comun.Buton(
            jos, "Setări", self.aplicatie.deschide_setarile, latime=140, inaltime=56
        )
        self.btn_setari.pack(side="right")

        # Indicator securitate în colțul de sus.
        try:
            self._indicator = ui_internet.indicator(jos, self.config)
        except Exception:
            self._indicator = None

        self._porneste_ceasul()

    def _porneste_dictarea(self) -> None:
        self.aplicatie.arata_ecran("dictare")
        pagina = self.aplicatie._pagini.get("dictare")
        if pagina is not None:
            if hasattr(pagina, "porneste_dictarea"):
                pagina.porneste_dictarea()
            elif hasattr(pagina, "_porneste"):
                pagina._porneste()

    def _opreste_dictarea(self) -> None:
        pagina = self.aplicatie._pagini.get("dictare")
        if pagina is not None and hasattr(pagina, "opreste_dictarea"):
            pagina.opreste_dictarea()
        elif getattr(self.aplicatie, "_motor", None):
            self.aplicatie.motor.anuleaza()

    def _deschide_in_libreoffice(self) -> None:
        self._sincronizeaza_text()
        cale = getattr(self.aplicatie.stare, "document_cale", None)
        self.aplicatie.deschide_in_libreoffice(cale)

    def _sincronizeaza_text(self) -> None:
        try:
            text_nou = self.text.get("1.0", "end-1c")
            self.aplicatie.stare.fixeaza_text(text_nou, "editor")
            if hasattr(self.aplicatie, "editor") and self.aplicatie.editor is not None:
                if self.aplicatie.editor.text_complet() != text_nou:
                    self.aplicatie.editor.seteaza_text(text_nou)
        except Exception:
            pass

    def sincronizeaza_din_stare(self) -> None:
        try:
            text_nou = self.aplicatie.stare.text_complet()
            if hasattr(self, "text"):
                text_existent = self.text.get("1.0", "end-1c")
                if text_existent != text_nou:
                    self.text.delete("1.0", "end")
                    if text_nou:
                        self.text.insert("1.0", text_nou)
        except Exception:
            pass

    def _deschide_meniu(self) -> None:
        meniu = tk.Toplevel(self)
        meniu.title("Meniu")
        meniu.transient(self)
        C = ui_comun.CULORI
        meniu.configure(background=C.fundal)
        for text, comanda in (
            ("Transcrie un fișier audio", self.aplicatie.transcrie_fisier_ales),
            ("Fișierele mele", self.aplicatie.deschide_fisierele),
            ("Verifică sunetul", self.aplicatie.verifica_sunetul),
            ("Verifică calculatorul", self.aplicatie.deschide_ecranul_de_verificare),
            ("Setări", self.aplicatie.deschide_setarile),
            ("Ajutor", lambda: self.aplicatie.arata_ajutor("principal")),
        ):
            ui_comun.Buton(meniu, text, comanda, latime=320, inaltime=52).pack(padx=ui_comun.px(12), pady=ui_comun.px(6))
        ui_comun.Buton(meniu, "Închide", meniu.destroy, latime=320, inaltime=44).pack(padx=ui_comun.px(12), pady=ui_comun.px(6))

    def reimprospateaza(self) -> None:
        """Reîmprospătează ecranul principal: sincronizează cardurile și aspectul."""
        self.sincronizeaza_din_stare()
        are_text = self.aplicatie.stare.are_text()
        if hasattr(self, "btn_libreoffice"):
            self.btn_libreoffice.activeaza(are_text)
        if hasattr(self, "btn_salveaza"):
            self.btn_salveaza.activeaza(are_text)

    def _porneste_ceasul(self) -> None:
        self.after(10_000, self._tic)

    def _tic(self) -> None:
        try:
            if self.aplicatie._indicator is not None:
                self.aplicatie._indicator.actualizeaza()
        except tk.TclError:
            return
        except Exception as exc:
            jurnal.atentionare(f"Verificarea legăturilor a eșuat: {exc}")
        self.after(10_000, self._tic)

    def opreste_tot(self) -> None:
        return


class PaginaEditor(tk.Frame):
    """Ecranul „Scrie sau corectează textul”: editorul, plus sfaturi și salvare."""

    def __init__(self, parinte: tk.Misc, aplicatie: Aplicatie):
        super().__init__(parinte, background=ui_comun.CULORI.fundal)
        self.aplicatie = aplicatie
        self.config = aplicatie.config
        self._construieste()

    def _construieste(self) -> None:
        C = ui_comun.CULORI
        zona = ui_comun.ZonaDerulare(self, latime_minima=880)
        zona.pack(fill="both", expand=True)
        corp = tk.Frame(zona.interior, background=C.fundal)
        corp.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(10))

        rand_titlu = tk.Frame(corp, background=C.fundal)
        rand_titlu.pack(fill="x")
        ui_comun.eticheta(rand_titlu, "Scrie sau corectează textul", "titlu").pack(side="left")
        self.indicator = ui_internet.indicator(rand_titlu, self.config)
        self.indicator.pack(side="right")

        ui_comun.eticheta(
            corp,
            "Textul se scrie în caseta de mai jos. Se salvează singur, mereu, ca să nu se piardă nimic. "
            "Când e gata, apasă „Salvează ca DOCX” sau „Deschide în LibreOffice pentru corectare”.",
            "baza",
            latime_bucati=880,
        ).pack(anchor="w", pady=(0, ui_comun.px(8)))

        card, corp_card = ui_comun.card(corp, "Salvează și trimite mai departe")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        rand_1 = tk.Frame(corp_card, background=C.card)
        rand_1.pack(fill="x", pady=(0, ui_comun.px(6)))
        rand_2 = tk.Frame(corp_card, background=C.card)
        rand_2.pack(fill="x")
        ui_comun.Buton(
            rand_1,
            "Deschide în LibreOffice pentru corectare",
            self.aplicatie.deschide_in_libreoffice,
            fel="principal",
            latime=460,
            inaltime=64,
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(
            rand_1, "Salvează ca DOCX", lambda: self.aplicatie.salveaza_document("docx"), latime=260, inaltime=64
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(
            rand_1, "Salvează ca ODT", lambda: self.aplicatie.salveaza_document("odt"), latime=260, inaltime=64
        ).pack(side="left")
        ui_comun.Buton(rand_2, "Alte formate…", self.aplicatie.alte_formate, latime=260, inaltime=60).pack(side="left")
        if programe_scris.alte_programe():
            ui_comun.Buton(rand_2, "Deschide cu alt program…", lambda: self.aplicatie.alte_programe(), latime=320, inaltime=60).pack(
                side="left", padx=(ui_comun.px(ui_comun.SPATIU), 0)
            )

        rand_final = tk.Frame(corp, background=C.fundal)
        rand_final.pack(fill="x", pady=(ui_comun.px(10), 0))
        ui_comun.Buton(
            rand_final,
            "← Înapoi la început",
            lambda: self.aplicatie.arata_ecran("principal"),
            latime=280,
            inaltime=56,
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(
            rand_final,
            "Deschide folderul documentelor",
            lambda: self.aplicatie._deschide_folderul(),
            latime=320,
            inaltime=56,
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(
            rand_final, "Ajutor pentru acest ecran", lambda: self.aplicatie.arata_ajutor("editor"), scurtatura="F1", latime=320, inaltime=56
        ).pack(side="left")

    def opreste_tot(self) -> None:
        return


# --------------------------------------------------------------------------- pictograma


def _seteaza_pictograma(fereastra: tk.Tk) -> None:
    """Setează pictograma ferestrei din fișierul .ico al aplicației."""
    try:
        ico_sursa = Path(__file__).with_name("iconita_dictare.ico")
        if ico_sursa.exists():
            fereastra.iconbitmap(str(ico_sursa))
        else:
            # Încercă și calea de instalare (unde pictograma este copiată)
            from . import cai
            ico_instalat = cai.director_instalare() / "pictograma.ico"
            if ico_instalat.exists():
                fereastra.iconbitmap(str(ico_instalat))
    except Exception:
        pass


# --------------------------------------------------------------------------- pornire


def ruleaza(optiuni=None) -> int:
    """Pornește programul: fereastra principală, apoi curățenie la închidere."""
    ui_comun.pregateste_dpi()
    cai.pregateste_directoare()
    biblioteca.asigura()
    aplicatie = Aplicatie(optiuni)
    try:
        aplicatie.mainloop()
    except KeyboardInterrupt:  # pragma: no cover - doar la Ctrl+C în consolă
        jurnal.atentionare("Programul a fost oprit din tastatură.")
    finally:
        try:
            if aplicatie.winfo_exists():
                aplicatie.inchide()
        except Exception:
            pass
    return 0
