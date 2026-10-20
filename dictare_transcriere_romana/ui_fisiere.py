"""Ecranul „Fișierele mele”: sunet, texte transcrise și documente finale.

Fereastra arată tot ce a făcut programul, pe trei file mari:

* **Audio** — înregistrările făcute cu microfonul și fișierele audio preluate;
* **Text transcris** — textele ținute separat, pentru corectat;
* **Documente finale** — documentele salvate (DOCX, ODT, PDF…).

Pentru fiecare fișier se vede numele, data („19.10.2026 10:35”) și durata (la
sunet) sau mărimea (la documente și la texte). Lângă fiecare fișier sunt
butoanele de care are nevoie un om obișnuit: deschide, transcrie, deschide în
programul de scris, arată în folder, redenumește și mută la Coșul de reciclare.

Ca peste tot în program, nu se folosesc dialogurile standard din Tk
(``messagebox``, ``filedialog``): întrebările, scrisul numelui nou și toate
mesajele sunt în ferestre proprii, în română.
"""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from pathlib import Path

from . import (
    biblioteca,
    config as config_modul,
    jurnal,
    libreoffice,
    programe_scris,
    sisteme,
    ui_comun,
)

#: Filele ferestrei: (felul din bibliotecă, numele filei, textul când e goală).
FILE: tuple[tuple[str, str, str], ...] = (
    (
        "audio",
        "Audio",
        "Încă nu ai nicio înregistrare. Apasă «Dictare vocală» ca să începi.",
    ),
    (
        "text",
        "Text transcris",
        "Încă nu ai niciun text transcris. Apasă «Dictare vocală» sau "
        "«Transcriere fișier audio» ca să începi.",
    ),
    (
        "document",
        "Documente finale",
        "Încă nu ai niciun document final. După ce ai un text transcris, apasă "
        "«Salvează ca DOCX» ca să începi.",
    ),
)

#: Câte fișiere se citesc dintr-o filă (cele mai noi primele).
MAXIM_FISIERE = 200


# --------------------------------------------------------------------------- texte


def _data_text(element) -> str:
    """Data și ora unui fișier, în forma „19.10.2026 10:35”."""
    moment = getattr(element, "data", None)
    if not isinstance(moment, dt.datetime):
        return "dată necunoscută"
    return moment.strftime("%d.%m.%Y %H:%M")


def _linie_detalii(element, fel: str) -> str:
    """A doua linie a rândului: data, apoi durata (la sunet) sau mărimea."""
    parti = [_data_text(element)]
    detalii = (getattr(element, "detalii", "") or "").strip()
    if fel == "audio":
        parti.append(f"durată: {detalii}" if detalii else "durata nu a putut fi citită")
    elif detalii:
        parti.append(f"mărime: {detalii}")
    return "  ·  ".join(parti)


# --------------------------------------------------------------------------- butonul unei file


class _ButonFila(ui_comun.Buton):
    """Butonul unei file: albastru când fila este deschisă, alb când nu."""

    def __init__(self, parinte: tk.Misc, text: str, comanda=None):
        """Creează butonul unei file, cu felul „secundar” la început."""
        super().__init__(parinte, text, comanda, fel="secundar", latime=250, inaltime=58)

    def este_aleasa(self, aleasa: bool) -> None:
        """Arată dacă fila acestui buton este cea deschisă acum."""
        self._fel = "principal" if aleasa else "secundar"
        fundal, culoare = self._culori_fel(self._fel)
        self.configure(background=fundal)
        self.eticheta.configure(background=fundal, foreground=culoare)


# --------------------------------------------------------------------------- dialog: nume nou


class _DialogNume(tk.Toplevel):
    """Dialog propriu pentru schimbarea numelui unui fișier (fără filedialog)."""

    def __init__(self, parinte: tk.Misc, nume_vechi: str):
        """Deschide dialogul cu numele de acum al fișierului, gata de scris."""
        super().__init__(parinte)
        self.rezultat: str | None = None
        C = ui_comun.CULORI
        ui_comun.seteaza_titlu(self, "Schimbă numele")
        self.configure(background=C.fundal)
        self.transient(parinte)
        self.resizable(True, True)

        cadru = tk.Frame(self, background=C.fundal)
        cadru.pack(fill="both", expand=True, padx=ui_comun.px(18), pady=ui_comun.px(16))
        ui_comun.eticheta(
            cadru, "Cum să se numească fișierul?", "subtitlu", fundal=C.fundal,
            latime_bucati=620,
        ).pack(anchor="w")
        ui_comun.eticheta(
            cadru,
            "Scrie noul nume. Terminația fișierului (de exemplu .docx) se păstrează.",
            "baza", fundal=C.fundal, latime_bucati=620,
        ).pack(anchor="w", pady=(ui_comun.px(6), ui_comun.px(10)))

        self.camp = tk.Entry(
            cadru,
            font=ui_comun.fonturi().baza,
            background=C.zona_text,
            foreground=C.text,
            highlightthickness=ui_comun.px(2),
            highlightbackground=C.chenar,
            highlightcolor=C.chenar_focus,
        )
        self.camp.pack(fill="x", ipady=ui_comun.px(6))
        self.camp.insert(0, nume_vechi)
        self.camp.select_range(0, "end")

        self.avertisment = tk.Label(
            cadru, text="", font=ui_comun.fonturi().mica, background=C.fundal,
            foreground=C.rosu_text, justify="left", anchor="w",
            wraplength=ui_comun.px(560),
        )
        self.avertisment.pack(anchor="w", pady=(ui_comun.px(6), 0))

        rand = tk.Frame(cadru, background=C.fundal)
        rand.pack(anchor="e", pady=(ui_comun.px(12), 0))
        self.buton_schimba = ui_comun.Buton(
            rand, "Schimbă numele", self._confirma, fel="principal",
            latime=ui_comun.BUTON_PRINCIPAL[0], inaltime=ui_comun.BUTON_PRINCIPAL[1],
        )
        self.buton_schimba.pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(rand, "Renunță", self._renunta, latime=190, inaltime=52).pack(side="left")

        self.bind("<Return>", lambda _e: self._confirma())
        self.bind("<Escape>", lambda _e: self._renunta())
        self.update_idletasks()
        ui_comun.centrat(
            self,
            max(ui_comun.px(680), self.winfo_reqwidth()),
            max(ui_comun.px(280), self.winfo_reqheight()),
        )
        self.grab_set()
        try:
            self.camp.focus_set()
        except tk.TclError:
            pass
        self.wait_window(self)

    def _confirma(self) -> None:
        """Ia numele scris și închide dialogul (sau arată ce lipsește)."""
        nume = self.camp.get().strip()
        if not nume:
            self.avertisment.configure(text="Scrie un nume, altfel nu am ce pune fișierului.")
            return
        self.rezultat = nume
        self._inchide()

    def _renunta(self) -> None:
        """Închide dialogul fără să schimbe numele."""
        self.rezultat = None
        self._inchide()

    def _inchide(self) -> None:
        """Ia grab-ul tastaturii și închide dialogul."""
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def _intreaba_nume(parinte: tk.Misc, nume_vechi: str) -> str | None:
    """Cere utilizatorului un nume nou de fișier (dialog propriu, în română)."""
    fereastra = _DialogNume(parinte, nume_vechi)
    return fereastra.rezultat


# --------------------------------------------------------------------------- fereastra


class FereastraFisiere(tk.Toplevel):
    """Fereastra „Fișierele mele”, cu trei file și butoanele fiecărui fișier."""

    def __init__(self, parinte: tk.Misc, la_deschidere=None):
        """Creează fereastra, desenează filele și citește lista de fișiere."""
        super().__init__(parinte)
        self.la_deschidere = la_deschidere
        self.fila = FILE[0][0]
        self.radacina = self._radacina_aleasa()
        self._butoane_file: dict[str, _ButonFila] = {}
        self._etichete_de_asezat: list[tk.Label] = []
        self.latime, self.inaltime = self._dimensiunea()

        ui_comun.seteaza_titlu(self, "Fișierele mele")
        self.configure(background=ui_comun.CULORI.fundal)
        self.transient(parinte)
        self.protocol("WM_DELETE_WINDOW", self._inchide)
        self.geometry(f"{self.latime}x{self.inaltime}")
        self.minsize(ui_comun.px(600), ui_comun.px(400))

        self._construieste()
        self._reincarca()

        self.bind("<Escape>", lambda _e: self._inchide())
        self.bind("<F1>", lambda _e: self._ajutor())
        self.bind("<MouseWheel>", self._roata, add="+")
        try:
            self.lift()
            self.focus_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ ajutoare

    def _dimensiunea(self) -> tuple[int, int]:
        """Dimensiunea ferestrei: cât încape pe ecran, fără să se taie nimic."""
        ecran_lat, ecran_inalt = ui_comun.maxim_ecran(0.98)
        latime = min(ui_comun.px(1060), max(ui_comun.px(620), ecran_lat - ui_comun.px(50)))
        inaltime = min(ui_comun.px(700), max(ui_comun.px(400), ecran_inalt - ui_comun.px(60)))
        return latime, inaltime

    def _radacina_aleasa(self) -> Path:
        """Folderul de bază al documentelor, așa cum este pus în setări."""
        try:
            setari = config_modul.incarca()
            return config_modul.director_iesiri(setari)
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut citi setările pentru folderul documentelor: {exc}")
            return biblioteca.radacina()

    def _cale_folder(self) -> Path:
        """Folderul filei deschise acum."""
        return biblioteca.folder(self.fila, self.radacina)

    def _latime_randuri(self) -> int:
        """Cât loc au textele din rânduri, ca să nu fie tăiate."""
        try:
            latime = self.canvas.winfo_width()
        except tk.TclError:
            latime = 0
        if latime <= 1:
            latime = self.latime
        return max(ui_comun.px(280), latime - ui_comun.px(90))

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        """Așază antetul, filele, lista derulabilă, linia de stare și butoanele."""
        C = ui_comun.CULORI

        antet = tk.Frame(self, background=C.fundal)
        antet.pack(fill="x", padx=ui_comun.px(14), pady=(ui_comun.px(12), 0))
        ui_comun.eticheta(antet, "Fișierele mele", "titlu", fundal=C.fundal).pack(side="left")
        ui_comun.buton_ajutor(antet, "fisiere", latime=170).pack(side="right")

        ui_comun.eticheta(
            self,
            "Toate fișierele făcute cu programul, pe trei file. Alege fila, apoi apasă "
            "butonul pentru ce vrei să faci cu fișierul.",
            "baza", fundal=C.fundal,
            latime_bucati=max(ui_comun.px(320), self.latime - ui_comun.px(60)),
        ).pack(anchor="w", padx=ui_comun.px(14), pady=(ui_comun.px(6), ui_comun.px(10)))

        rand_file = tk.Frame(self, background=C.fundal)
        rand_file.pack(fill="x", padx=ui_comun.px(14))
        for fel, titlu, _text_gol in FILE:
            buton = _ButonFila(rand_file, titlu, lambda f=fel: self._alege_fila(f))
            buton.pack(side="left", padx=(0, ui_comun.px(8)))
            self._butoane_file[fel] = buton
        ui_comun.Buton(
            rand_file, "Deschide folderul", self._deschide_folder, latime=240, inaltime=58
        ).pack(side="right")

        zona = tk.Frame(self, background=C.fundal)
        zona.pack(fill="both", expand=True, padx=ui_comun.px(14), pady=ui_comun.px(10))
        exterior = tk.Frame(
            zona, background=C.card, highlightthickness=ui_comun.px(2),
            highlightbackground=C.chenar, bd=0,
        )
        exterior.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(exterior, background=C.card, highlightthickness=0, bd=0)
        derulare = tk.Scrollbar(exterior, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=derulare.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        derulare.pack(side="right", fill="y")

        self.corp = tk.Frame(self.canvas, background=C.card)
        self._fereastra_corp = self.canvas.create_window((0, 0), window=self.corp, anchor="nw")
        self.corp.bind(
            "<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", self._la_redimensionare)

        self.linie_stare = ui_comun.LinieStare(self)
        self.linie_stare.pack(fill="x", padx=ui_comun.px(14), pady=(0, ui_comun.px(6)))

        jos = tk.Frame(self, background=C.fundal)
        jos.pack(fill="x", padx=ui_comun.px(14), pady=(0, ui_comun.px(12)))
        ui_comun.Buton(jos, "Închide", self._inchide, latime=190, inaltime=52).pack(side="right")
        self.eticheta_unde = ui_comun.eticheta(
            jos, "", "mica", fundal=C.fundal,
            latime_bucati=max(ui_comun.px(280), self.latime - ui_comun.px(240)),
        )
        self.eticheta_unde.pack(side="left")

    # ------------------------------------------------------------------ listă

    def _alege_fila(self, fel: str) -> None:
        """Deschide fila cerută și recitește lista de fișiere."""
        if fel == self.fila:
            return
        self.fila = fel
        try:
            self.canvas.yview_moveto(0.0)
        except tk.TclError:
            pass
        self._reincarca()

    def _reincarca(self) -> None:
        """Recitește fișierele filei deschise și redesenează lista."""
        C = ui_comun.CULORI
        for fel, buton in self._butoane_file.items():
            buton.este_aleasa(fel == self.fila)
        for copil in self.corp.winfo_children():
            copil.destroy()
        self._etichete_de_asezat = []
        try:
            elemente = biblioteca.listeaza(self.fila, self.radacina, maxim=MAXIM_FISIERE)
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut citi lista de fișiere: {exc}")
            elemente = []
        if not elemente:
            self._text_gol(self._textul_filei())
        else:
            for element in elemente:
                self._rand_fisier(element)
        try:
            self.eticheta_unde.configure(text=f"Unde se salvează: {self._cale_folder()}")
        except tk.TclError:
            pass
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.canvas.yview_moveto(0.0)
        except tk.TclError:
            pass
        self._aseaza_etichetele()

    def _textul_filei(self) -> str:
        """Textul afișat când fila deschisă nu are încă niciun fișier."""
        for fel, _titlu, text_gol in FILE:
            if fel == self.fila:
                return text_gol
        return "Încă nu ai niciun fișier aici. Apasă «Dictare vocală» ca să începi."

    def _text_gol(self, text: str) -> None:
        """Arată un îndemn prietenos în locul unei liste goale."""
        eticheta = ui_comun.eticheta(
            self.corp, text, "baza", fundal=ui_comun.CULORI.card,
            latime_bucati=self._latime_randuri(),
        )
        eticheta.pack(anchor="w", padx=ui_comun.px(14), pady=ui_comun.px(16))
        self._etichete_de_asezat.append(eticheta)

    def _rand_fisier(self, element) -> None:
        """Desenează un rând: numele fișierului, data, durata/mărimea, butoanele."""
        C = ui_comun.CULORI
        exterior, corp = ui_comun.card(self.corp, "")
        exterior.pack(fill="x", padx=ui_comun.px(8), pady=ui_comun.px(5))

        latime = self._latime_randuri()
        nume = ui_comun.eticheta(corp, element.nume, "buton", fundal=C.card, latime_bucati=latime)
        nume.pack(anchor="w")
        detalii = ui_comun.eticheta(
            corp, _linie_detalii(element, self.fila), "mica", fundal=C.card, latime_bucati=latime
        )
        detalii.pack(anchor="w", pady=(ui_comun.px(3), ui_comun.px(8)))
        self._etichete_de_asezat += [nume, detalii]

        sus = tk.Frame(corp, background=C.card)
        sus.pack(fill="x")
        ui_comun.Buton(
            sus, "Deschide", lambda el=element: self._deschide(el), latime=170, inaltime=48
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        if self.fila == "audio":
            ui_comun.Buton(
                sus, "Transcrie", lambda el=element: self._transcrie(el), latime=170, inaltime=48
            ).pack(side="left", padx=(0, ui_comun.px(8)))
        if self.fila == "document":
            ui_comun.Buton(
                sus, "Deschide în LibreOffice",
                lambda el=element: self._deschide_libreoffice(el), latime=300, inaltime=48,
            ).pack(side="left")

        jos = tk.Frame(corp, background=C.card)
        jos.pack(fill="x", pady=(ui_comun.px(8), 0))
        ui_comun.Buton(
            jos, "Arată în folder", lambda el=element: self._arata_in_folder(el),
            latime=200, inaltime=48,
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(
            jos, "Redenumește", lambda el=element: self._redenumeste(el), latime=190, inaltime=48
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(
            jos, "Mută la Coșul de reciclare", lambda el=element: self._la_gunoi(el),
            latime=300, inaltime=48,
        ).pack(side="left")

    # ------------------------------------------------------------------ așezare

    def _la_redimensionare(self, eveniment) -> None:
        """Potrivește lățimea rândurilor când se schimbă fereastra."""
        try:
            self.canvas.itemconfigure(self._fereastra_corp, width=eveniment.width)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            return
        self._aseaza_etichetele()

    def _aseaza_etichetele(self) -> None:
        """Rescrie lățimea la care se rupe rândul fiecărui text din listă."""
        latime = self._latime_randuri()
        for eticheta in self._etichete_de_asezat:
            try:
                eticheta.configure(wraplength=latime)
            except tk.TclError:
                pass

    def _roata(self, eveniment) -> None:
        """Derulează lista cu rotița mouse-ului, când arătătorul este peste ea."""
        if not self._peste_lista(eveniment):
            return
        pas = -1 if getattr(eveniment, "delta", 0) > 0 else 1
        try:
            self.canvas.yview_scroll(pas, "units")
        except tk.TclError:
            pass

    def _peste_lista(self, eveniment) -> bool:
        """Adevărat dacă arătătorul mouse-ului este deasupra listei de fișiere."""
        try:
            element = self.winfo_containing(eveniment.x_root, eveniment.y_root)
        except (tk.TclError, AttributeError):
            return False
        while element is not None:
            if element is self.canvas or element is self.corp:
                return True
            element = getattr(element, "master", None)
        return False

    # ------------------------------------------------------------------ acțiuni

    def _deschide(self, element) -> None:
        """Deschide fișierul: prin program sau cu programul potrivit din Windows."""
        if self.la_deschidere is not None:
            self._cere(element, "deschide")
            return
        if sisteme.deschide_fisier(element.cale):
            self.linie_stare.arata(
                "Deschis", f"am deschis „{element.nume}” cu programul potrivit.", "bine"
            )
            return
        ui_comun.anunta(
            self,
            "Fișierul nu s-a deschis",
            f"Nu am putut deschide „{element.nume}”.\n\n"
            "Probabil pentru că: fișierul a fost mutat ori șters între timp, sau programul "
            "care ar trebui să îl deschidă nu este instalat.\n\n"
            "Ce faci acum: apasă «Arată în folder» ca să vezi fișierul și deschide-l cu "
            "dublu-clic.",
        )

    def _transcrie(self, element) -> None:
        """Trimite un fișier audio la transcriere."""
        if self.la_deschidere is not None:
            self._cere(element, "transcrie")
            return
        ui_comun.anunta(
            self,
            "Transcrierea pornește din ecranul principal",
            "Închide această fereastră și apasă «Transcriere fișier audio» din ecranul "
            "principal; alegi acolo fișierul audio pe care vrei să îl transcrii.\n\n"
            "Fișierul este păstrat aici, deci îl poți transcrie oricând.",
        )

    def _cere(self, element, fel_actiune: str) -> None:
        """Cheamă legătura către programul principal și spune ce s-a întâmplat."""
        try:
            self.la_deschidere(element, fel_actiune)
        except Exception as exc:
            jurnal.eroare(
                f"Acțiunea „{fel_actiune}” pentru {element.cale} a eșuat: {type(exc).__name__}: {exc}"
            )
            ui_comun.anunta(
                self,
                "Nu am putut începe",
                f"Nu am putut începe lucrul cu „{element.nume}”.\n\n"
                "Probabil pentru că: fișierul este deteriorat sau este folosit de alt program.\n\n"
                "Ce faci acum: închide programele care folosesc fișierul, apoi încearcă din nou.",
                detalii=f"{type(exc).__name__}: {exc}",
            )
            return
        if fel_actiune == "transcrie":
            self.linie_stare.arata(
                "Pornit",
                f"am trimis „{element.nume}” la transcriere; urmărește progresul în "
                "fereastra principală.",
                "lucru",
            )
        else:
            self.linie_stare.arata("Deschis", f"am deschis „{element.nume}”.", "bine")

    def _deschide_libreoffice(self, element) -> None:
        """Deschide documentul în programul de scris, cu explicații dacă lipsește."""
        nume_program = libreoffice.nume_pentru_utilizator()
        try:
            stare = libreoffice.stare()
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut verifica LibreOffice: {exc}")
            stare = None
        if stare is None or not stare.gasit:
            self._fara_libreoffice(element, nume_program)
            return
        reusit, mesaj = libreoffice.deschide_in_writer(element.cale)
        if reusit:
            self.linie_stare.arata(
                "Deschis", f"am deschis „{element.nume}” în programul de scris.", "bine"
            )
            return
        ui_comun.anunta(
            self,
            "Documentul nu s-a deschis",
            f"„{element.nume}” nu a putut fi deschis în {nume_program}.\n\n"
            f"{mesaj}\n\n"
            "Ce faci acum: încearcă din nou sau apasă «Arată în folder» și deschide "
            "documentul cu dublu-clic.",
        )

    def _fara_libreoffice(self, element, nume_program: str) -> None:
        """Explică, pe înțeles, ce se poate face când LibreOffice nu este instalat."""
        alte = self._alte_programe()
        text = (
            f"Nu găsesc {nume_program} pe acest calculator, așa că nu pot deschide "
            f"documentul „{element.nume}” în el.\n\n"
            "Documentul este salvat și nu se pierde. Îl poți deschide cu un alt program de "
            "scris de pe calculator"
        )
        if alte:
            text += f" ({', '.join(program.nume for program in alte)})"
        text += " sau cu programul ales de Windows."
        rezultat = ui_comun.dialog(
            self,
            "LibreOffice nu este instalat",
            text,
            [("Deschide cu alt program", "principal"), ("Închide", "secundar")],
            implicit=0,
            anulare=1,
        )
        if rezultat == 0:
            self._cu_alt_program(element)

    def _alte_programe(self) -> list:
        """Programele de scris de pe calculator, în afară de cel implicit."""
        try:
            return list(programe_scris.alte_programe())
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut căuta alte programe de scris: {exc}")
            return []

    def _cu_alt_program(self, element) -> None:
        """Deschide documentul cu alt program de scris sau cu cel ales de Windows."""
        alte = self._alte_programe()
        if alte:
            program = alte[0]
            reusit, mesaj = programe_scris.deschide(element.cale, program)
            if reusit:
                self.linie_stare.arata(
                    "Deschis", f"am deschis „{element.nume}” în {program.nume}.", "bine"
                )
                return
            ui_comun.anunta(
                self,
                "Documentul nu s-a deschis",
                f"„{element.nume}” nu a putut fi deschis în {program.nume}.\n\n{mesaj}",
            )
            return
        if sisteme.deschide_fisier(element.cale):
            self.linie_stare.arata(
                "Deschis", f"am deschis „{element.nume}” cu programul ales de Windows.", "bine"
            )
            return
        ui_comun.anunta(
            self,
            "Documentul nu s-a deschis",
            f"Nu am găsit niciun program de scris care să deschidă „{element.nume}”.\n\n"
            "Probabil pentru că: pe calculator nu este instalat niciun program pentru acest "
            "tip de document.\n\n"
            "Ce faci acum: apasă «Arată în folder» ca să vezi fișierul, apoi deschide-l cu "
            "dublu-clic după ce instalezi un program de scris.",
        )

    def _arata_in_folder(self, element) -> None:
        """Deschide Explorerul exact pe folderul în care se află fișierul."""
        folder = Path(element.cale).parent
        if sisteme.deschide_folder(folder):
            self.linie_stare.arata(
                "Arătat", f"am deschis folderul fișierului „{element.nume}”.", "normal"
            )
            return
        ui_comun.anunta(
            self,
            "Folderul nu s-a deschis",
            f"Nu am putut deschide folderul fișierului „{element.nume}”.\n\n"
            "Probabil pentru că: folderul a fost mutat sau șters între timp.\n\n"
            "Ce faci acum: apasă «Deschide folderul» sus, ca să vezi unde se salvează "
            "fișierele acum.",
        )

    def _redenumeste(self, element) -> None:
        """Cere un nume nou și schimbă numele fișierului."""
        nume_nou = _intreaba_nume(self, element.nume)
        if not nume_nou:
            return
        cale_noua, mesaj = biblioteca.redenumeste(element.cale, nume_nou)
        if cale_noua is None:
            ui_comun.anunta(
                self,
                "Numele nu s-a putut schimba",
                mesaj or "Numele nu a putut fi schimbat. Încearcă din nou.",
            )
            return
        self.linie_stare.arata(
            "Redenumit", f"fișierul se numește acum „{cale_noua.name}”.", "bine"
        )
        self._reincarca()

    def _la_gunoi(self, element) -> None:
        """Trimite fișierul la Coșul de reciclare, după ce utilizatorul confirmă."""
        intrebare = (
            f"Fișierul „{element.nume}” ajunge în Coșul de reciclare.\n\n"
            "Nu se șterge definitiv: îl poți readuce oricând din Coșul de reciclare, dacă "
            "te răzgândești.\n\nVrei să îl mut acum?"
        )
        if not ui_comun.intreaba(
            self, "Muți fișierul la Coșul de reciclare?", intrebare, da="Da, mută-l", nu="Nu, lasă-l"
        ):
            self.linie_stare.arata("Neschimbat", "fișierul a rămas unde era.", "normal")
            return
        reusit, mesaj = biblioteca.la_gunoi(element.cale)
        if not reusit:
            ui_comun.anunta(
                self,
                "Fișierul nu a ajuns la Coșul de reciclare",
                mesaj or "Windows nu a putut muta fișierul. Încearcă din nou.",
            )
            return
        self.linie_stare.arata("Șters", "am mutat fișierul la Coșul de reciclare.", "atentie")
        self._reincarca()

    # ------------------------------------------------------------------ fereastră

    def _deschide_folder(self) -> None:
        """Deschide Explorerul pe folderul filei deschise acum."""
        folder = self._cale_folder()
        if sisteme.deschide_folder(folder):
            self.linie_stare.arata("Arătat", "am deschis folderul fișierelor.", "normal")
            return
        ui_comun.anunta(
            self,
            "Folderul nu s-a deschis",
            "Windows nu a putut deschide folderul acum.\n\n"
            "Probabil pentru că: folderul a fost mutat sau șters între timp.\n\n"
            "Ce faci acum: apasă «Închide» și încearcă din nou peste o clipă.",
        )

    def _ajutor(self) -> None:
        """Deschide ajutorul acestui ecran (butonul „? Ajutor” sau tasta F1)."""
        from . import ui_ajutor

        try:
            ui_ajutor.deschide(self, "fisiere")
        except Exception as exc:
            jurnal.eroare(f"Ajutorul nu s-a putut deschide: {exc}")
            ui_comun.anunta(self, "Ajutor", "Ajutorul nu s-a putut deschide acum. Încearcă din nou.")

    def _inchide(self) -> None:
        """Închide fereastra (Esc sau butonul „Închide”)."""
        try:
            self.destroy()
        except tk.TclError:
            pass


def deschide(parinte: tk.Misc, la_deschidere=None) -> None:
    """Deschide fereastra „Fișierele mele” și așteaptă să fie închisă.

    ``la_deschidere`` este chemat cu ``(element, fel_actiune)``, unde
    ``fel_actiune`` este „deschide” sau „transcrie”.
    """
    existente = [fereastra for fereastra in parinte.winfo_children() if isinstance(fereastra, FereastraFisiere)]
    if existente:
        # Fereastra se deschide o singură dată: dacă e deja pe ecran, o aduce în față
        # și tot așteaptă să fie închisă, ca la o deschidere obișnuită.
        existente[0].lift()
        existente[0].focus_set()
        existente[0].wait_window()
        return
    fereastra = FereastraFisiere(parinte, la_deschidere=la_deschidere)
    fereastra.wait_window()
