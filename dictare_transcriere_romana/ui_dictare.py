"""Ecranul de dictare vocală: vorbești, iar textul apare singur în editor.

Ce face ecranul, pas cu pas (cerințele 5, 6, 12 și 22):

* arată microfonul ales și lasă utilizatorul să îl schimbe;
* are un singur buton mare, rotund: „● Pornește dictarea” / „■ Oprește dictarea”;
* „Pauză” / „Continuă”, un cronometru mare și o bară mare de nivel;
* textul apare **singur în editorul de jos**, pe măsură ce vorbești: propoziția
  încă nesigură se scrie cu gri, apoi devine neagră;
* după 3 secunde de liniște scrie „Nu te aud. Vorbește mai aproape de microfon.”;
* salvează automat (la 30 de secunde și la oprire) în „Text transcris”;
* când textul e gata, arată bannerul „Gata! …” și cele patru butoane;
* arată indicatorul de internet (roșu/verde), fără să întrerupă dictarea.

Sunetul se împarte în bucăți de 8 secunde cu o mică suprapunere de o secundă,
ca să nu se taie cuvintele la mijloc; bucățile se transcriu pe rând, într-un fir
de lucru, ca fereastra să nu înghețe niciodată.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from queue import Queue

import numpy as np

from . import (
    biblioteca,
    dispozitive,
    erori,
    inregistrare,
    jurnal,
    motor,
    stare as stare_modul,
    ui_comun,
    ui_final,
    ui_internet,
)

#: Cât sunet se strânge înainte de a fi trimis la transcriere.
SECUNDE_BUCATA = 8.0
#: Cât sunet se păstrează la începutul bucății următoare (ca să nu taie cuvinte).
SECUNDE_SUPRAPUNERE = 1.0
#: Câte secunde de liniște înseamnă „nu te aud”.
SECUNDE_TACERE = 3.0
SECUNDE_PAUZA_TACERE = 300.0  # 5 minute de tacere -> pauza automata (cerinta 50)
#: Sub acest nivel, sunetul este socotit liniște.
NIVEL_MINIM = 0.015
#: La cât timp se scrie copia de siguranță în timpul dictării.
SECUNDE_SALVARE_AUTOMATA = 30.0
#: La cât timp se verifică starea internetului (cerința 22).
SECUNDE_VERIFICARE_INTERNET = 10.0
#: La cât timp se verifică dacă microfonul a fost scos sau pus la loc.
SECUNDE_VERIFICARE_DISPOZITIVE = 3.0
#: Cât sunet trebuie să aibă ultima bucată ca să merite transcrisă.
ESANTIOANE_MINIME = 4_800  # 0,3 secunde la 16 kHz


def _curata_cuvant(cuvant: str) -> str:
    return cuvant.lower().strip(".,!?;:„”\"()[]")


def fara_suprapunere(anterior: str, nou: str) -> str:
    """Taie din textul nou cuvintele care repetă sfârșitul textului anterior.

    Bucățile de sunet se suprapun puțin, ca să nu se taie cuvintele; la
    transcriere, aceeași propoziție poate apărea de două ori. Aici se scoate
    repetiția, cât mai lungă, de la începutul textului nou.
    """
    if not anterior or not nou:
        return nou
    vechi = anterior.split()
    noua = nou.split()
    cel_mult = min(len(vechi), len(noua), 10)
    for cate in range(cel_mult, 0, -1):
        if [_curata_cuvant(c) for c in vechi[-cate:]] == [_curata_cuvant(c) for c in noua[:cate]]:
            return " ".join(noua[cate:]).strip()
    return nou


# --------------------------------------------------------------------------- alegerea microfonului


class _AlegeMicrofon(tk.Toplevel):
    """Fereastra în care utilizatorul își alege microfonul dintr-o listă simplă."""

    def __init__(self, parinte: tk.Misc, preferat: str = ""):
        super().__init__(parinte)
        ui_comun.seteaza_titlu(self, "Alege microfonul")
        self.configure(background=ui_comun.CULORI.fundal)
        self.transient(parinte)
        self.rezultat = None
        self._dispozitive: list[dispozitive.Dispozitiv] = []
        self._butoane: list[ui_comun.Buton] = []

        cadru = tk.Frame(self, background=ui_comun.CULORI.fundal)
        cadru.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(14))
        ui_comun.eticheta(cadru, "Alege microfonul cu care vorbești", "titlu").pack(anchor="w")
        ui_comun.eticheta(
            cadru,
            "Apasă pe microfonul dorit. Alegerea se ține minte pentru data viitoare.",
            "baza",
            latime_bucati=560,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        self.zona_lista = ui_comun.ZonaDerulare(cadru)
        self.zona_lista.pack(fill="both", expand=True)
        self._umple(preferat)

        rand = tk.Frame(cadru, background=ui_comun.CULORI.fundal)
        rand.pack(fill="x", pady=(ui_comun.px(12), 0))
        ui_comun.Buton(
            rand, "Caută microfoanele din nou", lambda: self._umple(""), latime=320, inaltime=56
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(rand, "Renunță", self.destroy, latime=200, inaltime=56).pack(side="left")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<KeyPress-F9>", lambda _e: self._porneste_daca_posibil())
        self.bind("<KeyRelease-F9>", lambda _e: self._opreste_daca_push_to_talk())
        self.update_idletasks()
        ui_comun.centrat(self, latime=760, inaltime=560)
        self.grab_set()
        self.wait_window(self)

    def _umple(self, preferat: str) -> None:
        for copil in list(self.zona_lista.interior.winfo_children()):
            copil.destroy()
        self._butoane = []
        try:
            self._dispozitive = dispozitive.microfoane()
        except Exception as exc:
            self._dispozitive = []
            jurnal.atentionare(f"Lista microfoanelor nu a putut fi citită: {exc}")
        if not self._dispozitive:
            ui_comun.eticheta(
                self.zona_lista.interior,
                "Nu găsesc niciun microfon. Verifică dacă este conectat, apoi apasă "
                "„Caută microfoanele din nou”.",
                "baza",
                latime_bucati=680,
            ).pack(anchor="w", pady=ui_comun.px(4))
            return
        for dispozitiv in self._dispozitive:
            text = dispozitiv.descriere() or dispozitiv.nume
            if dispozitiv.cheie == preferat:
                text += "  (folosit acum)"
            buton = ui_comun.Buton(
                self.zona_lista.interior,
                text,
                lambda d=dispozitiv: self._alege(d),
                fel="principal" if dispozitiv.cheie == preferat else "secundar",
                latime=660,
                inaltime=64,
                ancora="w",
            )
            buton.pack(anchor="w", pady=(0, ui_comun.px(6)))
            self._butoane.append(buton)

    def _alege(self, dispozitiv) -> None:
        self.rezultat = dispozitiv
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


# --------------------------------------------------------------------------- pagina


class PaginaDictare(tk.Frame):
    """Ecranul „Dictare vocală”.

    Fereastra principală îi dă, prin ``aplicatie``: ``stare``, ``config``,
    ``editor``, ``coada``, ``motor``, ``bara_stare``, ``avertizeaza_internet()``,
    ``arata_ecran(nume)``, ``salveaza_document(fel)``, ``deschide_in_libreoffice()``,
    ``alte_formate()``.
    """

    def __init__(self, parinte: tk.Misc, aplicatie):
        super().__init__(parinte, background=ui_comun.CULORI.fundal)
        self.aplicatie = aplicatie
        self.stare = aplicatie.stare
        self.config = aplicatie.config
        self.editor = aplicatie.editor

        self._microfon: inregistrare.Microfon | None = None
        self._dispozitiv = None
        self._fir_sunet: threading.Thread | None = None
        self._fir_text: threading.Thread | None = None
        self._oprit = threading.Event()
        self._pauza = threading.Event()
        self._de_transcris: Queue | None = None
        self._blocare = threading.Lock()
        self._total: list = []
        self._coada_sunet: list = []
        self._nr_coada = 0
        self._prag_bucata = int(SECUNDE_BUCATA * inregistrare.RATA_WHISPER)
        self._prag_suprapunere = int(SECUNDE_SUPRAPUNERE * inregistrare.RATA_WHISPER)
        self._index_bucata = 0
        self._ultimul_text_brut = ""
        self._inceput = 0.0
        self._secunde = 0.0
        self._nivel = 0.0
        self._tacere = 0.0
        self._push_to_talk = False  # cerinta 49: tine apasat pentru a dicta
        self._pornita = False
        self._se_termina = False
        self._erori_la_transcriere = 0
        self._ticuri = 0
        self._ultima_salvare = 0.0
        self._internet_anterior = False
        self._indicator: ui_internet.IndicatorInternet | None = None
        self._motor_local: motor.MotorWhisper | None = None
        self._construieste()

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        C = ui_comun.CULORI
        zona = ui_comun.ZonaDerulare(self, latime_minima=900)
        zona.pack(fill="both", expand=True)
        corp = tk.Frame(zona.interior, background=C.fundal)
        corp.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(12))

        # Titlul ecranului, cu indicatorul de internet în dreapta sus.
        rand_titlu = tk.Frame(corp, background=C.fundal)
        rand_titlu.pack(fill="x")
        ui_comun.eticheta(rand_titlu, "Dictare vocală", "titlu").pack(side="left")
        self._indicator = ui_internet.indicator(rand_titlu, self.config)
        self._indicator.pack(side="right")

        ui_comun.eticheta(
            corp,
            "Apasă butonul mare, vorbește normal, iar textul apare singur mai jos, în editor. "
            "Apasă din nou pe buton ca să te oprești.",
            "baza",
            latime_bucati=900,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        # Cardul microfonului.
        card_mic, corp_mic = ui_comun.card(corp, "Microfonul folosit")
        card_mic.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        rand_mic = tk.Frame(corp_mic, background=C.card)
        rand_mic.pack(fill="x")
        self.eticheta_microfon = ui_comun.eticheta(rand_mic, self._text_microfon(), "baza", latime_bucati=560)
        self.eticheta_microfon.pack(side="left", fill="x", expand=True)
        ui_comun.Buton(
            rand_mic, "Schimbă microfonul", self._schimba_microfonul, latime=280, inaltime=56
        ).pack(side="left", padx=(ui_comun.px(ui_comun.SPATIU), 0))
        ui_comun.Buton(
            rand_mic, "Verifică sunetul", self._verifica_sunetul, latime=240, inaltime=56
        ).pack(side="left", padx=(ui_comun.px(ui_comun.SPATIU), 0))

        # Cardul butonului mare, cu cronometru și bara de nivel.
        card_vorba, corp_vorba = ui_comun.card(corp, "Vorbește acum")
        card_vorba.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        rand_butoane = tk.Frame(corp_vorba, background=C.card)
        rand_butoane.pack(fill="x")
        self.buton_mare = ui_comun.Buton(
            rand_butoane,
            "● Pornește dictarea",
            self._apasa_buton_mare,
            fel="principal",
            latime=440,
            inaltime=110,
        )
        self.buton_mare.pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        coloana = tk.Frame(rand_butoane, background=C.card)
        coloana.pack(side="left", fill="x", expand=True)
        self.buton_pauza = ui_comun.Buton(
            coloana, "Pauză", self._pauza_continua, latime=240, inaltime=64
        )
        self.buton_pauza.pack(anchor="w")
        self.buton_pauza.activeaza(False)
        ui_comun.eticheta(
            coloana,
            "Pauză: se oprește scrisul, dar textul rămas se păstrează. Apasă „Continuă” ca să reiei.",
            "mica",
            fundal=C.card,
            latime_bucati=420,
        ).pack(anchor="w", pady=(ui_comun.px(6), 0))

        rand_stare = tk.Frame(corp_vorba, background=C.card)
        rand_stare.pack(fill="x", pady=(ui_comun.px(10), ui_comun.px(4)))
        self.eticheta_timp = ui_comun.eticheta(rand_stare, "00:00", "imens", fundal=C.card)
        self.eticheta_timp.pack(side="left", padx=(0, ui_comun.px(16)))
        self.eticheta_te_aud = ui_comun.eticheta(rand_stare, "● Te aud", "buton", fundal=C.card)
        self.eticheta_te_aud.pack(side="left")

        self.bara_nivel = tk.Canvas(
            corp_vorba,
            width=ui_comun.px(880),
            height=ui_comun.px(40),
            background=C.bara_goala,
            highlightthickness=ui_comun.px(2),
            highlightbackground=C.chenar,
            bd=0,
        )
        self.bara_nivel.pack(fill="x")
        # Cerinta 59: copie de siguranta ZIP.
        rand_backup = tk.Frame(corp_vorba, background=C.card)
        rand_backup.pack(fill="x", pady=(ui_comun.px(8), 0))
        ui_comun.Buton(rand_backup, "Copie de siguranta (ZIP)", self._copiaza_siguranta, latime=260, inaltime=44).pack(side="left")
        self._bucata_nivel = None

        # Bannerul „Nu te aud” și bannerul pentru microfon scos.
        self.banner_tacere = ui_comun.Banner(corp, "atentie")
        self.banner_dispozitiv = ui_comun.Banner(corp, "atentie")

        # „Cum se folosește”, pe scurt.
        card_ajutor, corp_ajutor = ui_comun.card(corp, "Cum se folosește, pe scurt")
        card_ajutor.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        for rand in (
            "1. Apasă butonul mare „● Pornește dictarea” și vorbește normal, aproape de microfon.",
            "2. Textul apare singur în editor, mai jos. Propoziția scrisă cu gri încă se verifică.",
            "3. Apasă „■ Oprește dictarea” când ai terminat. Apasă iar ca să continui în același text.",
        ):
            ui_comun.eticheta(corp_ajutor, rand, "baza", fundal=C.card, latime_bucati=880).pack(anchor="w")

        # Editorul (adus aici de fereastra principală) și partea de final.
        self.zona_editor = tk.Frame(corp, background=C.fundal)
        self.zona_editor.pack(fill="both", expand=True)
        self.zona_finala = ui_final.ZonaFinala(corp, self.aplicatie)

        rand_final = tk.Frame(corp, background=C.fundal)
        rand_final.pack(fill="x", pady=(ui_comun.px(12), 0))
        ui_comun.Buton(
            rand_final,
            "← Înapoi la început",
            lambda: self.aplicatie.arata_ecran("principal"),
            latime=280,
            inaltime=56,
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(rand_final, "Ajutor pentru acest ecran", self._ajutor, scurtatura="F1", latime=320, inaltime=56).pack(
            side="left"
        )

        self._porneste_ceasurile()

    # ------------------------------------------------------------------ texte ajutătoare

    def _text_microfon(self) -> str:
        if self._dispozitiv is None:
            return "Microfon: se alege automat când pornești dictarea."
        return f"Microfon: {self._dispozitiv.descriere() or self._dispozitiv.nume}"

    def _ajutor(self) -> None:
        self.aplicatie.arata_ajutor("dictare")

    # ------------------------------------------------------------------ ceasuri

    def _porneste_ceasurile(self) -> None:
        self.after(250, self._tic)
        self.after(1000, self._ceas_internet)

    def _tic(self) -> None:
        """Actualizează cronometrul, bara de nivel și starea microfonului."""
        try:
            self._deseneaza_nivel()
            if self._pornita and not self._pauza.is_set() and not self._se_termina:
                self._secunde = time.monotonic() - self._inceput
                self.eticheta_timp.configure(text=_text_timp(self._secunde))
                self._urmareste_tacerea()
                if self._secunde - self._ultima_salvare >= SECUNDE_SALVARE_AUTOMATA:
                    self._salveaza_automat()
            if self._pornita:
                self._ticuri += 1
                if self._ticuri % int(SECUNDE_VERIFICARE_DISPOZITIVE / 0.25) == 0:
                    self._verifica_dispozitive()
        except tk.TclError:
            return
        self.after(250, self._tic)

    def _deseneaza_nivel(self) -> None:
        nivel = self._nivel
        if self._microfon is not None and self._microfon.activ:
            nivel = self._microfon.nivel
        self._nivel = nivel
        if self._bucata_nivel is not None:
            self.bara_nivel.delete(self._bucata_nivel)
        latime = self.bara_nivel.winfo_width()
        if latime <= 1:
            latime = ui_comun.px(880)
        umplut = int(latime * max(0.0, min(1.0, nivel)))
        culoare = ui_comun.CULORI.bara_plina
        if nivel < NIVEL_MINIM:
            culoare = ui_comun.CULORI.bara_goala
        self._bucata_nivel = self.bara_nivel.create_rectangle(
            0, 0, umplut, ui_comun.px(40), fill=culoare, width=0
        )

    def _urmareste_tacerea(self) -> None:
        nivel = self._nivel
        if nivel < NIVEL_MINIM:
            self._tacere += 0.25
        else:
            self._tacere = 0.0
        if self._tacere >= SECUNDE_TACERE:
            self.eticheta_te_aud.configure(text="● Nu te aud")
            self.banner_tacere.arata("Nu te aud. Vorbește mai aproape de microfon.")
            if not self.banner_tacere.winfo_ismapped():
                self.banner_tacere.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        elif self._tacere == 0.0:
            self.eticheta_te_aud.configure(text="● Te aud")
            if self.banner_tacere.winfo_ismapped():
                self.banner_tacere.pack_forget()

        # Cerinta 50: pauza automata dupa 5 minute de tacere.
        if self._tacere >= SECUNDE_PAUZA_TACERE and not self._pauza.is_set():
            self._pauza_continua()
            self.aplicatie.bara_stare.arata("Pauza automata", "5 minute de liniste - dictarea a fost pusa pe pauza.", "atentie")
    def _ceas_internet(self) -> None:
        """Verifică internetul la fiecare 10 secunde (cerința 22)."""
        try:
            if self._indicator is not None:
                self._indicator.actualizeaza()
                cale_internet = self._indicator.stare.despre("internet")
                conectat = bool(cale_internet and cale_internet.deschisa)
                if conectat and not self._internet_anterior:
                    # Internetul s-a pornit în timpul lucrului: spunem o dată.
                    ui_internet.avertizeaza(self, self.config)
                self._internet_anterior = conectat
        finally:
            self.after(int(SECUNDE_VERIFICARE_INTERNET * 1000), self._ceas_internet)

    # ------------------------------------------------------------------ microfon

    def _schimba_microfonul(self) -> None:
        if self._pornita:
            ui_comun.anunta(
                self,
                "Oprește dictarea mai întâi",
                "Ca să schimbi microfonul, apasă mai întâi „■ Oprește dictarea”, apoi schimbă-l.",
            )
            return
        alegere = _AlegeMicrofon(self, getattr(self.config, "microfon_preferat", ""))
        if alegere.rezultat is None:
            return
        self._dispozitiv = alegere.rezultat
        self._salveaza_preferinta(self._dispozitiv)
        self.eticheta_microfon.configure(text=self._text_microfon())
        ui_comun.anunta(
            self,
            "Microfon ales",
            f"De acum vorbești la „{self._dispozitiv.nume}”. Alegerea se ține minte.",
        )

    def _salveaza_preferinta(self, dispozitiv) -> None:
        try:
            self.config.microfon_preferat = dispozitiv.cheie
            from . import config as config_modul

            config_modul.salveaza(self.config)
        except Exception as exc:
            jurnal.atentionare(f"Preferința de microfon nu a putut fi salvată: {exc}")

    def _verifica_sunetul(self) -> None:
        """Deschide fereastra de probă a sunetului (microfon, boxe, căști)."""
        from . import ui_sunet

        ui_sunet.fereastra_verificare(self, la_terminare=self._dupa_verificare_sunet)

    def _dupa_verificare_sunet(self) -> None:
        if self._dispozitiv is None:
            self._dispozitiv = dispozitive.alege_microfon(getattr(self.config, "microfon_preferat", ""))
            self.eticheta_microfon.configure(text=self._text_microfon())
        self.aplicatie.reimprospateaza_aspectul()

    def _alege_microfonul_automat(self):
        try:
            return dispozitive.alege_microfon(getattr(self.config, "microfon_preferat", ""))
        except Exception as exc:
            jurnal.atentionare(f"Alegerea microfonului a eșuat: {exc}")
            return None

    def _verifica_dispozitive(self) -> None:
        """Microfonul a fost scos sau pus la loc în timpul folosirii."""
        if self._dispozitiv is None:
            return
        try:
            chei = {dispozitiv.cheie for dispozitiv in dispozitive.microfoane()}
        except Exception:
            return
        prezent = self._dispozitiv.cheie in chei
        if not prezent and self._pornita and not self._se_termina:
            self.banner_dispozitiv.arata(
                "Microfonul nu mai răspunde (pare scos). Îl aștept să revină: poți continua, "
                "apoi apasă „Schimbă microfonul” dacă nu reapare."
            )
            if not self.banner_dispozitiv.winfo_ismapped():
                self.banner_dispozitiv.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
            jurnal.atentionare("Microfonul ales nu mai este conectat.")
        elif prezent and self.banner_dispozitiv.winfo_ismapped():
            self.banner_dispozitiv.pack_forget()

    # ------------------------------------------------------------------ pornire / oprire

    def porneste_dictarea(self) -> None:
        """Pornește dictarea dacă nu este deja pornită."""
        if not self._pornita and not self._se_termina:
            self._porneste()

    def opreste_dictarea(self) -> None:
        """Oprește dictarea dacă este activă."""
        if self._pornita:
            self._opreste()

    def _apasa_buton_mare(self) -> None:
        if self._pornita and not self._se_termina:
            self._opreste()
        else:
            self._porneste()

    def _porneste_daca_posibil(self) -> None:
        if self._pornita or self._se_termina:
            return
        self._push_to_talk = True
        self._porneste()

    def _opreste_daca_push_to_talk(self) -> None:
        if self._push_to_talk and self._pornita and not self._se_termina:
            self._push_to_talk = False
            self._opreste()


    def _porneste(self) -> None:
        try:
            self.buton_mare.pulseaza(True)
            self.buton_mare.seteaza_text("? Te ascult\u2026")
        except Exception:
            pass
        # 1. Internetul: se verifică înainte de a începe lucrul (cerința 22).
        self.aplicatie.avertizeaza_internet()
        if self._indicator is not None:
            self._indicator.actualizeaza()
            cale_internet = self._indicator.stare.despre("internet")
            self._internet_anterior = bool(cale_internet and cale_internet.deschisa)

        # Cerinta 42: avertisment spatiu pe disc înainte de înregistrare.
        try:
            from . import resurse, constante
            liber = resurse.spatiu_liber_gb("~")
            if liber < constante.DISC_MINIM_GB:
                raspuns = ui_comun.dialog(
                    self,
                    "Spatiu pe disc",
                    f"Mai ai doar {liber:.1f} GB liberi. Pentru dictare si salvare sunt recomandate cel putin {constante.DISC_MINIM_GB:.0f} GB.\n\nContinui?",
                    [("Continua", "principal"), ("Anuleaza", "secundar")],
                    implicit=1,
                    anulare=1,
                )
                if raspuns != 0:
                    return
        except Exception:
            pass

        # 2. Se poate lucra? (părțile de transcriere trebuie să fie instalate)
        if not motor.biblioteci_disponibile():
            ui_comun.dialog_eroare(
                self,
                erori.Eroare(
                    ce_s_a_intamplat="Părțile de transcriere nu sunt instalate încă.",
                    de_ce="instalarea programului nu s-a terminat până la capăt.",
                    ce_faci_acum=(
                        "Rulează din nou instalarea programului (scurtătura „Instalare "
                        "Dictare&Transcriere Română”), apoi încearcă din nou."
                    ),
                    actiuni=[erori.Actiune("Am înțeles", erori.RENUNTA)],
                ),
            )
            return

        # 3. Textul de pe ecran: se adaugă la el sau se începe unul nou?
        if self.editor.text_ecran().strip():
            raspuns = ui_comun.dialog(
                self,
                "Ai deja text pe ecran",
                "Textul dictat acum se adaugă la textul care există deja?",
                [
                    ("Adaugă la sfârșitul textului", "principal"),
                    ("Începe un text nou", "secundar"),
                    ("Înapoi", "secundar"),
                ],
                implicit=0,
                anulare=2,
            )
            if raspuns is None or raspuns == 2:
                return
            if raspuns == 1:
                if not stare_modul.pregateste_schimbarea(
                    self, self.stare, "Începi o dictare nouă, iar textul de pe ecran se înlocuiește."
                ):
                    return
                self.editor.seteaza_text("")
                self.zona_finala.ascunde()

        # 4. Microfonul.
        if self._dispozitiv is None:
            self._dispozitiv = self._alege_microfonul_automat()
        if self._dispozitiv is None:
            ui_comun.dialog_eroare(
                self,
                erori.fara_microfon("Niciun microfon nu a fost găsit în Windows."),
                la_actiune=lambda fel: self._dupa_eroare(fel),
            )
            return

        try:
            self._microfon = inregistrare.Microfon(self._dispozitiv, inregistrare.RATA_WHISPER)
            self._microfon.porneste()
        except Exception as exc:
            self._microfon = None
            jurnal.eroare(f"Microfonul nu a pornit: {exc}")
            ui_comun.dialog_eroare(
                self,
                erori.din_exceptie(exc, "pornirea microfonului"),
                la_actiune=lambda fel: self._dupa_eroare(fel),
            )
            return

        if not self.stare.marca:
            self.stare.marca = biblioteca.marca_acum()
        self.stare.sursa = "dictare"

        self._oprit.clear()
        self._pauza.clear()
        self._total = []
        self._coada_sunet = []
        self._nr_coada = 0
        self._index_bucata = 0
        self._ultimul_text_brut = ""
        self._tacere = 0.0
        self._secunde = 0.0
        self._ultima_salvare = 0.0
        self._se_termina = False
        self._pornita = True
        self._inceput = time.monotonic()
        self._de_transcris = Queue()
        self._fir_sunet = threading.Thread(target=self._bucla_sunet, name="dictare-sunet", daemon=True)
        self._fir_text = threading.Thread(target=self._bucla_text, name="dictare-text", daemon=True)
        self._fir_sunet.start()
        self._fir_text.start()

        self.buton_mare.seteaza_text("■ Oprește dictarea")
        self.buton_mare.seteaza_fel("pericol")
        self.buton_pauza.activeaza(True)
        self.eticheta_te_aud.configure(text="● Te aud")
        self.zona_finala.ascunde()
        self.aplicatie.bara_stare.arata(
            "Te ascult…", "Vorbește normal. Textul apare singur în editor, mai jos.", "lucru"
        )

    def _dupa_eroare(self, fel: str) -> None:
        if fel in (erori.INCERCARE_DIN_NOU,):
            self._dispozitiv = None
            self._porneste()
        elif fel == erori.SETARI_MICROFON:
            from . import sisteme

            if not sisteme.deschide_setare("ms-settings:privacy-microphone"):
                ui_comun.anunta(
                    self,
                    "Nu am putut deschide setările",
                    "Deschide „Setări Windows” (Start, apoi rotița) → Confidențialitate → Microfon "
                    "și verifică dacă programelor li se dă voie să folosească microfonul.",
                )
        elif fel == erori.SETARI_SUNET:
            self._verifica_sunetul()

    def _pauza_continua(self) -> None:
        if not self._pornita or self._se_termina:
            return
        if self._pauza.is_set():
            self._pauza.clear()
            self.buton_pauza.seteaza_text("Pauză")
            self._inceput = time.monotonic() - self._secunde
            self.aplicatie.bara_stare.arata("Te ascult…", "Am reînceput. Vorbește normal.", "lucru")
        else:
            self._pauza.set()
            self.buton_pauza.seteaza_text("Continuă")
            self.aplicatie.bara_stare.arata(
                "Pauză", "Dictarea este pusă pe pauză. Textul scris până acum se păstrează.", "atentie"
            )
            self._salveaza_automat()

    def _opreste(self) -> None:
        if not self._pornita or self._se_termina:
            return
        self._se_termina = True
        self._pornita = False
        try:
            self.buton_mare.pulseaza(False)
        except Exception:
            pass
        self.buton_mare.seteaza_text("Termin ultimele cuvinte…")
        self.buton_mare.activeaza(False)
        self.buton_pauza.activeaza(False)
        self.aplicatie.bara_stare.arata(
            "Termin", "Mai scriu ultimele cuvinte, apoi arăt textul gata.", "lucru"
        )
        threading.Thread(target=self._inchide_dictarea, name="dictare-oprire", daemon=True).start()

    # ------------------------------------------------------------------ firele de lucru

    def _bucla_sunet(self) -> None:
        while not self._oprit.is_set():
            if self._pauza.is_set():
                # Cât timp e pauză, sunetul se aruncă: nu se înregistrează zgomot.
                try:
                    self._microfon.preia()
                except Exception:
                    pass
                time.sleep(0.2)
                continue
            try:
                bucata = self._microfon.preia()
            except Exception as exc:
                self._trimite(self._eroare_microfon, exc)
                self._oprit.set()
                return
            if bucata.size:
                self._adauga_sunet(bucata)
            time.sleep(0.25)

    def _adauga_sunet(self, bucata) -> None:
        with self._blocare:
            self._total.append(bucata)
            self._coada_sunet.append(bucata)
            self._nr_coada += int(bucata.size)
            while self._nr_coada >= self._prag_bucata:
                unit = np.concatenate(self._coada_sunet)
                prima = unit[: self._prag_bucata]
                rest = unit[self._prag_bucata - self._prag_suprapunere :]
                self._coada_sunet = [rest]
                self._nr_coada = int(rest.size)
                self._trimite_la_transcriere(prima)

    def _trimite_la_transcriere(self, bucata, fortat: bool = False) -> None:
        if not fortat and self._se_termina:
            return
        if bucata is None or len(bucata) < ESANTIOANE_MINIME:
            return
        self._index_bucata += 1
        offset = max(0.0, (self._index_bucata - 1) * (SECUNDE_BUCATA - SECUNDE_SUPRAPUNERE))
        if self._de_transcris is not None:
            self._de_transcris.put((self._index_bucata, bucata, offset))

    def _motor_de_folosit(self) -> motor.MotorWhisper:
        existent = getattr(self.aplicatie, "motor", None)
        if existent is not None:
            return existent
        if self._motor_local is None:
            self._motor_local = motor.MotorWhisper(getattr(self.config, "dispozitiv", "auto"))
        return self._motor_local

    def _bucla_text(self) -> None:
        """Transcrie bucățile de sunet, pe rând, fără să blocheze fereastra."""
        while True:
            element = self._de_transcris.get()
            if element is None:
                break
            index, bucata, offset = element
            try:
                rezultat = self._motor_de_folosit().transcrie(
                    bucata, limba=getattr(self.config, "limba", "ro")
                )
            except motor.Anulat:
                break
            except Exception as exc:
                self._trimite(self._eroare_transcriere, exc)
                break
            brut = (rezultat.text or "").strip()
            text = fara_suprapunere(self._ultimul_text_brut, brut)
            self._ultimul_text_brut = brut
            segmente = [
                motor.Segment(offset + segment.start, offset + segment.end, segment.text, [motor.Cuvant(offset + c.start, offset + c.end, c.text) for c in (getattr(segment, 'cuvinte', None) or [])])
                for segment in (rezultat.segmente or [])
            ]
            self._trimite(self._text_nou, text, segmente)

    def _inchide_dictarea(self) -> None:
        """Oprește microfonul, termină transcrierea și scrie fișierul audio."""
        self._oprit.set()
        if self._fir_sunet is not None:
            self._fir_sunet.join(timeout=5.0)
        ramas = None
        if self._microfon is not None:
            try:
                ramas = self._microfon.opreste()
            except Exception as exc:
                jurnal.atentionare(f"Oprirea microfonului a dat eroare: {exc}")
        if ramas is not None and len(ramas.pcm):
            with self._blocare:
                self._total.append(ramas.pcm)
            self._trimite_la_transcriere(ramas.pcm, fortat=True)
        if self._de_transcris is not None:
            self._de_transcris.put(None)
        if self._fir_text is not None:
            self._fir_text.join(timeout=900.0)

        cale_audio = None
        durata = 0.0
        if self._total:
            try:
                pcm = np.concatenate(self._total)
                inregistrare_totala = inregistrare.Inregistrare(pcm, inregistrare.RATA_WHISPER)
                durata = inregistrare_totala.secunde
                cale = biblioteca.nume_unic(
                    biblioteca.folder("audio"),
                    biblioteca.nume_legat(self.stare.marca or biblioteca.marca_acum(), ".wav"),
                )
                inregistrare_totala.scrie_wav(cale)
                cale_audio = cale
                jurnal.info(f"Dictarea a fost salvată în {cale} ({durata:.1f} secunde).")
            except Exception as exc:
                jurnal.atentionare(f"Sunetul dictării nu a putut fi salvat: {exc}")
        self._trimite(self._dupa_oprire, durata, cale_audio)

    # ------------------------------------------------------------------ înapoi în interfață

    def _trimite(self, functie, *argumente) -> None:
        coada = getattr(self.aplicatie, "coada", None)
        if coada is not None:
            coada.trimite(functie, *argumente)
        else:  # fără coadă (la teste), se rulează direct
            functie(*argumente)

    def _text_nou(self, text: str, segmente: list) -> None:
        if segmente:
            self.stare.segmente.extend(segmente)
        if not text:
            return
        self.editor.finalizeaza_provizoriu(salveaza=False)
        self.editor.arata_provizoriu(text)

    def _eroare_transcriere(self, exc: Exception) -> None:
        self._erori_la_transcriere += 1
        jurnal.eroare(f"Transcrierea unei bucăți de dictare a eșuat: {exc}")
        if self._erori_la_transcriere <= 1:
            ui_comun.dialog_eroare(self, erori.din_exceptie(exc, "dictare în timp real"))

    def _eroare_microfon(self, exc: Exception) -> None:
        jurnal.eroare(f"Microfonul s-a oprit în timpul dictării: {exc}")
        self._pornita = False
        self._se_termina = True
        self.buton_mare.seteaza_text("● Pornește dictarea")
        self.buton_mare.seteaza_fel("principal")
        self.buton_mare.activeaza(True)
        self.buton_pauza.activeaza(False)
        try:
            self._salveaza_automat(forțat=True)
        except Exception:
            pass
        ui_comun.dialog_eroare(self, erori.din_exceptie(exc, "citirea de la microfon"))

    def _dupa_oprire(self, durata: float, cale_audio) -> None:
        self.editor.finalizeaza_provizoriu(salveaza=False)
        self.stare.provizoriu = ""
        self.editor.sincronizeaza(salveaza=False)
        self.stare.durata_audio = durata
        self.stare.audio_cale = cale_audio
        self.stare.sursa = "dictare"
        self.stare.marcheaza_modificat()

        self.buton_mare.seteaza_text("● Pornește dictarea")
        self.buton_mare.seteaza_fel("principal")
        self.buton_mare.activeaza(True)
        self.buton_pauza.seteaza_text("Pauză")
        self.buton_pauza.activeaza(False)
        self.eticheta_te_aud.configure(text="● Te aud")
        if self.banner_tacere.winfo_ismapped():
            self.banner_tacere.pack_forget()
        self.eticheta_timp.configure(text=_text_timp(self._secunde))
        self._deseneaza_nivel()

        text = self.editor.text_ecran().strip()
        if not text:
            self.aplicatie.bara_stare.arata(
                "Text gol",
                "Nu am auzit nimic. Verifică microfonul („Verifică sunetul”), apoi încearcă din nou.",
                "atentie",
            )
            return
        self._salveaza_automat(forțat=True)
        self.zona_finala.arata()
        self.aplicatie.bara_stare.arata(
            "Gata",
            "Textul este scris mai jos. Verifică-l, corectează ce nu e bine și salvează-l.",
            "bine",
        )
        self.aplicatie.reimprospateaza_aspectul()

    def _copiaza_siguranta(self) -> None:
        text = self.editor.text_ecran()
        if not text.strip():
            ui_comun.anunta(self, "Nimic de salvat", "Nu exista text pe ecran pentru copia de siguranta.")
            return
        marca = self.stare.marca or biblioteca.marca_acum()
        cale_text = biblioteca.scrie_text(text, marca)
        if cale_text is None:
            ui_comun.anunta(self, "Eroare", "Textul nu a putut fi salvat pentru copia de siguranta.")
            return
        cale_zip, mesaj = biblioteca.copiaza_siguranta_zip(cale_text)
        if cale_zip is None:
            ui_comun.anunta(self, "Copie de siguranta", mesaj)
            return
        self.linie_stare.arata("Copie de siguranta", "arhiva creata: " + cale_zip.name, "bine")


    def _salveaza_automat(self, forțat: bool = False) -> None:
        self._ultima_salvare = time.monotonic()
        text = self.editor.text_ecran()
        if not text.strip():
            return
        marca = self.stare.marca or biblioteca.marca_acum()
        self.stare.marca = marca
        biblioteca.scrie_text_legat(text, marca)
        self.editor.salveaza_automat()
        if forțat:
            jurnal.info(f"Dictarea a fost salvată în „Text transcris” ca {marca}.txt")

    # ------------------------------------------------------------------ curățenie

    def opreste_tot(self) -> None:
        """Se cheamă când se închide programul: nu rămâne niciun fir de lucru."""
        self._oprit.set()
        if self._microfon is not None:
            try:
                self._microfon.anuleaza()
            except Exception:
                pass
            self._microfon = None


def _text_timp(secunde: float) -> str:
    """Afișează durata ca „02:35”."""
    total = int(max(0.0, secunde))
    return f"{total // 60:02d}:{total % 60:02d}"
