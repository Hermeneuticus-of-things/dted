"""Ecranul „Setări”: toate alegerile programului, pe rânduri ușor de citit.

Fiecare rând are un titlu, o propoziție de explicație și butoanele lui:

1. **Unde se salvează documentele** — folderul de salvare, cu „Schimbă folderul”
   și „Revino la locul implicit”;
2. **Limba vorbită** — limba în care vorbești (implicit română);
3. **Microfonul folosit** — „Automat” sau un microfon anume;
4. **Difuzorul folosit** — „Automat” sau o ieșire de sunet anume;
5. **Cum transcrie** — automat, doar procesorul sau doar placa video;
6. **Salvare automată** — textul de siguranță și documentul final;
7. **Programul de scris** — LibreOffice (implicit) sau alt program găsit.

Ca peste tot în program, nu se folosesc dialogurile standard din Tk
(``messagebox``, ``filedialog``): alegerea folderului și alegerile din liste se
fac în ferestre proprii, în română.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from dataclasses import asdict
from pathlib import Path

from . import (
    biblioteca,
    cai,
    constante,
    config as config_modul,
    dispozitive,
    erori,
    jurnal,
    libreoffice,
    programe_scris,
    sisteme,
    ui_comun,
)

#: Opțiunile de transcriere: (codul din setări, textul de pe buton, explicația).
OPTIUNI_TRANSCRIERE: tuple[tuple[str, str, str], ...] = (
    ("auto", "Automat (recomandat)", "Programul alege singur ce merge mai bine pe calculatorul tău."),
    ("cpu", "Doar procesorul (fără placă video)", "Mai încet, dar merge pe orice calculator."),
    ("cuda", "Doar placa video", "Cel mai rapid, dacă placa video are driver instalat."),
)

#: Din câte în câte secunde se salvează singur textul de siguranță.
SECUNDE_SALVARE_AUTOMATA = 30

#: Textul pentru alegerea automată a unui dispozitiv de sunet.
AUTOMAT = "Automat (cel ales de Windows)"


# --------------------------------------------------------------------------- dialog: folder


class _DialogFolder(tk.Toplevel):
    """Dialog propriu de alegere a folderului (fără ``filedialog``)."""

    def __init__(self, parinte: tk.Misc, cale_initiala: Path):
        """Deschide dialogul pe folderul cerut, cu locul de scris gata de folosit."""
        super().__init__(parinte)
        self.rezultat: Path | None = None
        C = ui_comun.CULORI
        ui_comun.seteaza_titlu(self, "Alege folderul")
        self.configure(background=C.fundal)
        self.transient(parinte)
        self.resizable(True, True)

        cadru = tk.Frame(self, background=C.fundal)
        cadru.pack(fill="both", expand=True, padx=ui_comun.px(18), pady=ui_comun.px(16))

        ui_comun.eticheta(
            cadru, "Unde să se salveze documentele?", "subtitlu", fundal=C.fundal,
            latime_bucati=680,
        ).pack(anchor="w")
        ui_comun.eticheta(
            cadru,
            "Poți scrie locul, ori poți folosi scurtăturile de mai jos și apoi «Alege acest folder».",
            "baza", fundal=C.fundal, latime_bucati=680,
        ).pack(anchor="w", pady=(ui_comun.px(6), ui_comun.px(10)))

        rand_scurtaturi = tk.Frame(cadru, background=C.fundal)
        rand_scurtaturi.pack(fill="x", pady=(0, ui_comun.px(10)))
        for nume, cale in self._scurtaturi():
            ui_comun.Buton(
                rand_scurtaturi, nume, lambda c=cale: self._pune(c), latime=170, inaltime=48
            ).pack(side="left", padx=(0, ui_comun.px(8)))

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
        self.camp.insert(0, str(cale_initiala))

        self.avertisment = tk.Label(
            cadru, text="", font=ui_comun.fonturi().mica, background=C.fundal,
            foreground=C.rosu_text, justify="left", anchor="w", wraplength=ui_comun.px(620),
        )
        self.avertisment.pack(anchor="w", pady=(ui_comun.px(6), 0))

        rand = tk.Frame(cadru, background=C.fundal)
        rand.pack(anchor="e", pady=(ui_comun.px(12), 0))
        self.buton_alege = ui_comun.Buton(
            rand, "Alege acest folder", self._confirma, fel="principal",
            latime=280, inaltime=ui_comun.BUTON_PRINCIPAL[1],
        )
        self.buton_alege.pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(rand, "Renunță", self._renunta, latime=190, inaltime=52).pack(side="left")

        self.bind("<Return>", lambda _e: self._confirma())
        self.bind("<Escape>", lambda _e: self._renunta())
        self.update_idletasks()
        ui_comun.centrat(
            self,
            max(ui_comun.px(760), self.winfo_reqwidth()),
            max(ui_comun.px(300), self.winfo_reqheight()),
        )
        self.grab_set()
        try:
            self.camp.focus_set()
            self.camp.icursor("end")
        except tk.TclError:
            pass
        self.wait_window(self)

    def _scurtaturi(self) -> list[tuple[str, Path]]:
        """Scurtăturile de sus: folderele cerute de la Windows, nu presupuse."""
        candidati = [
            ("Documente", cai.director_documente()),
            ("Desktop", cai.folder_desktop_windows()),
            ("Descărcări", cai.folder_cunoscut("{374DE290-123F-4565-9164-39C4925E467B}")),
        ]
        return [(nume, Path(cale)) for nume, cale in candidati if cale]

    def _pune(self, cale: Path) -> None:
        """Pune o scurtătură în căsuța de scris."""
        self.camp.delete(0, "end")
        self.camp.insert(0, str(cale))
        self.avertisment.configure(text="")

    def _confirma(self) -> None:
        """Ia folderul scris și închide dialogul (sau arată ce nu este în regulă)."""
        text = self.camp.get().strip().strip('"')
        if not text:
            self.avertisment.configure(text="Scrie unde vrei să se salveze documentele.")
            return
        cale = Path(text)
        if cale.is_file():
            self.avertisment.configure(
                text="Aici este un fișier, nu un folder. Alege un folder."
            )
            return
        self.rezultat = cale
        self._inchide()

    def _renunta(self) -> None:
        """Închide dialogul fără să schimbe folderul."""
        self.rezultat = None
        self._inchide()

    def _inchide(self) -> None:
        """Ia grab-ul tastaturii și închide dialogul."""
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def alege_folder(parinte: tk.Misc, cale_initiala: Path) -> Path | None:
    """Cere un folder cu dialogul propriu al programului (în română)."""
    fereastra = _DialogFolder(parinte, Path(cale_initiala))
    return fereastra.rezultat


# --------------------------------------------------------------------------- dialog: alegere


class _DialogAlegere(tk.Toplevel):
    """Dialog propriu de alegere dintr-o listă (limbă, dispozitiv, program)."""

    def __init__(
        self,
        parinte: tk.Misc,
        titlu: str,
        text: str,
        optiuni: list[tuple[str, str]],
        ales: str = "",
    ):
        """Deschide dialogul cu lista de alegeri dată, bifând-o pe cea de acum."""
        super().__init__(parinte)
        self.rezultat: str | None = None
        C = ui_comun.CULORI
        ui_comun.seteaza_titlu(self, titlu)
        self.configure(background=C.fundal)
        self.transient(parinte)
        self.resizable(True, True)

        cadru = tk.Frame(self, background=C.fundal)
        cadru.pack(fill="both", expand=True, padx=ui_comun.px(18), pady=ui_comun.px(16))
        ui_comun.eticheta(
            cadru, titlu, "subtitlu", fundal=C.fundal, latime_bucati=700
        ).pack(anchor="w")
        ui_comun.eticheta(
            cadru, text, "baza", fundal=C.fundal, latime_bucati=700
        ).pack(anchor="w", pady=(ui_comun.px(6), ui_comun.px(10)))

        zona = tk.Frame(
            cadru, background=C.card, highlightthickness=ui_comun.px(2),
            highlightbackground=C.chenar, bd=0,
        )
        zona.pack(fill="both", expand=True)
        bara = tk.Scrollbar(zona, orient="vertical")
        bara.pack(side="right", fill="y")
        self.lista = tk.Listbox(
            zona,
            font=ui_comun.fonturi().baza,
            background=C.zona_text,
            foreground=C.text,
            selectbackground=C.principal,
            selectforeground=C.principal_text,
            yscrollcommand=bara.set,
            activestyle="none",
            exportselection=False,
            height=min(14, max(3, len(optiuni))),
            highlightthickness=0,
            bd=0,
        )
        self.lista.pack(side="left", fill="both", expand=True)
        bara.configure(command=self.lista.yview)
        for index, (eticheta, _cheie) in enumerate(optiuni):
            self.lista.insert("end", eticheta)
            if ales and _cheie == ales:
                self.lista.selection_set(index)
                self.lista.see(index)
        self._chei = [cheie for _eticheta, cheie in optiuni]
        self.lista.bind("<Double-Button-1>", lambda _e: self._confirma())

        rand = tk.Frame(cadru, background=C.fundal)
        rand.pack(anchor="e", pady=(ui_comun.px(12), 0))
        self.buton_alege = ui_comun.Buton(
            rand, "Alege", self._confirma, fel="principal",
            latime=200, inaltime=ui_comun.BUTON_PRINCIPAL[1],
        )
        self.buton_alege.pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(rand, "Renunță", self._renunta, latime=190, inaltime=52).pack(side="left")

        self.bind("<Return>", lambda _e: self._confirma())
        self.bind("<Escape>", lambda _e: self._renunta())
        self.update_idletasks()
        ui_comun.centrat(
            self,
            max(ui_comun.px(780), self.winfo_reqwidth()),
            max(ui_comun.px(420), min(ui_comun.px(620), self.winfo_reqheight())),
        )
        self.grab_set()
        try:
            self.buton_alege.focus_set()
        except tk.TclError:
            pass
        self.wait_window(self)

    def _confirma(self) -> None:
        """Ia alegerea făcută în listă și închide dialogul."""
        selectie = self.lista.curselection()
        if not selectie:
            return
        index = int(selectie[0])
        if index < len(self._chei):
            self.rezultat = self._chei[index]
            self._inchide()

    def _renunta(self) -> None:
        """Închide dialogul fără să aleagă nimic."""
        self.rezultat = None
        self._inchide()

    def _inchide(self) -> None:
        """Ia grab-ul tastaturii și închide dialogul."""
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def _alege_din_lista(
    parinte: tk.Misc, titlu: str, text: str, optiuni: list[tuple[str, str]], ales: str = ""
) -> str | None:
    """Cere o alegere dintr-o listă, cu fereastra proprie a programului."""
    if not optiuni:
        return None
    fereastra = _DialogAlegere(parinte, titlu, text, optiuni, ales)
    return fereastra.rezultat


# --------------------------------------------------------------------------- fereastra


class FereastraSetari(tk.Toplevel):
    """Fereastra „Setări”, cu toate alegerile programului pe rânduri."""

    def __init__(self, parinte: tk.Misc, config_obj, la_salvare=None):
        """Creează fereastra cu rândurile de setări, pe valorile primite."""
        super().__init__(parinte)
        self.config = config_obj if config_obj is not None else config_modul.Config()
        self.la_salvare = la_salvare
        self._stare_inceput = self._copie()
        self._etichete_de_asezat: list[tk.Label] = []
        self.latime, self.inaltime = self._dimensiunea()

        ui_comun.seteaza_titlu(self, "Setări")
        self.configure(background=ui_comun.CULORI.fundal)
        self.transient(parinte)
        self.protocol("WM_DELETE_WINDOW", self._inchide)
        self.geometry(f"{self.latime}x{self.inaltime}")
        self.minsize(ui_comun.px(600), ui_comun.px(400))

        self._construieste()
        self._arata_toate()

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
        latime = min(ui_comun.px(1040), max(ui_comun.px(620), ecran_lat - ui_comun.px(50)))
        inaltime = min(ui_comun.px(720), max(ui_comun.px(400), ecran_inalt - ui_comun.px(60)))
        return latime, inaltime

    def _copie(self) -> dict:
        """O copie a setărilor, ca să se vadă dacă s-a schimbat ceva."""
        try:
            return asdict(self.config)
        except Exception:
            return {}

    def _latime_text(self) -> int:
        """Cât loc au textele de pe rânduri, ca să nu fie tăiate."""
        try:
            latime = self.canvas.winfo_width()
        except tk.TclError:
            latime = 0
        if latime <= 1:
            latime = self.latime
        return max(ui_comun.px(280), latime - ui_comun.px(90))

    def _folder_curent(self) -> Path:
        """Folderul în care se salvează documentele acum."""
        try:
            return config_modul.director_iesiri(self.config)
        except Exception:
            return cai.director_iesiri()

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        """Așază antetul, rândurile derulabile, linia de stare și butoanele."""
        C = ui_comun.CULORI
        antet = tk.Frame(self, background=C.fundal)
        antet.pack(fill="x", padx=ui_comun.px(14), pady=(ui_comun.px(12), 0))
        ui_comun.eticheta(antet, "Setări", "titlu", fundal=C.fundal).pack(side="left")

        ui_comun.eticheta(
            self,
            "Schimbă doar ce ai nevoie; fiecare rând spune pe scurt la ce folosește. "
            "La sfârșit apasă «Salvează setările».",
            "baza", fundal=C.fundal,
            latime_bucati=max(ui_comun.px(320), self.latime - ui_comun.px(60)),
        ).pack(anchor="w", padx=ui_comun.px(14), pady=(ui_comun.px(6), ui_comun.px(10)))

        zona = tk.Frame(self, background=C.fundal)
        zona.pack(fill="both", expand=True, padx=ui_comun.px(14))
        self.canvas = tk.Canvas(zona, background=C.fundal, highlightthickness=0, bd=0)
        derulare = tk.Scrollbar(zona, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=derulare.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        derulare.pack(side="right", fill="y")

        self.corp = tk.Frame(self.canvas, background=C.fundal)
        self._fereastra_corp = self.canvas.create_window((0, 0), window=self.corp, anchor="nw")
        self.corp.bind(
            "<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", self._la_redimensionare)

        self._rand_folder()
        self._rand_limba()
        self._rand_microfon()
        self._rand_difuzor()
        self._rand_transcriere()
        self._rand_salvare()
        self._rand_program()
        self._rand_afisare()
        self._rand_aspect()

        self.linie_stare = ui_comun.LinieStare(self)
        self.linie_stare.pack(fill="x", padx=ui_comun.px(14), pady=(ui_comun.px(8), ui_comun.px(6)))

        jos = tk.Frame(self, background=C.fundal)
        jos.pack(fill="x", padx=ui_comun.px(14), pady=(0, ui_comun.px(12)))
        ui_comun.Buton(
            jos, "Salvează setările", self._salveaza, fel="principal",
            latime=300, inaltime=ui_comun.BUTON_PRINCIPAL[1],
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(jos, "Închide", self._inchide, latime=190, inaltime=52).pack(side="left")
        ui_comun.buton_ajutor(jos, "setari", latime=170).pack(side="right")

    def _card(self, titlu: str, explicatie: str) -> tk.Frame:
        """Un rând de setare: titlu, explicație și locul unde se pun comenzile."""
        C = ui_comun.CULORI
        exterior, interior = ui_comun.card(self.corp, titlu)
        exterior.pack(fill="x", pady=ui_comun.px(6))
        eticheta = ui_comun.eticheta(
            interior, explicatie, "baza", fundal=C.card, latime_bucati=self._latime_text()
        )
        eticheta.pack(anchor="w", pady=(ui_comun.px(2), ui_comun.px(8)))
        self._etichete_de_asezat.append(eticheta)
        return interior

    def _valoare(self, parinte: tk.Misc, culoare_fundal: str) -> tk.Label:
        """Eticheta care arată valoarea aleasă acum pe un rând."""
        eticheta = ui_comun.eticheta(
            parinte, "", "buton", fundal=culoare_fundal, latime_bucati=self._latime_text()
        )
        eticheta.pack(anchor="w", pady=(0, ui_comun.px(8)))
        self._etichete_de_asezat.append(eticheta)
        return eticheta

    # ------------------------------------------------------------------ rânduri

    def _rand_folder(self) -> None:
        """Rândul 1: unde se salvează documentele."""
        C = ui_comun.CULORI
        corp = self._card(
            "Unde se salvează documentele",
            "Aici ajung documentele noi pe care le salvezi. Locul se poate schimba oricând.",
        )
        self.eticheta_folder = self._valoare(corp, C.card)
        rand = tk.Frame(corp, background=C.card)
        rand.pack(fill="x")
        ui_comun.Buton(
            rand, "Schimbă folderul", self._schimba_folder, latime=250, inaltime=48
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(
            rand, "Revino la locul implicit", self._folder_implicit, latime=290, inaltime=48
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(
            rand, "Deschide folderul", self._deschide_folder, latime=220, inaltime=48
        ).pack(side="left")

    def _rand_limba(self) -> None:
        """Rândul 2: limba în care vorbești."""
        C = ui_comun.CULORI
        corp = self._card(
            "Limba vorbită",
            "În ce limbă vorbești, ca programul să scrie corect. Limba de la început este româna.",
        )
        self.eticheta_limba = self._valoare(corp, C.card)
        ui_comun.Buton(
            corp, "Alege limba", self._schimba_limba, latime=220, inaltime=48
        ).pack(anchor="w")

    def _rand_microfon(self) -> None:
        """Rândul 3: microfonul folosit la dictare."""
        C = ui_comun.CULORI
        corp = self._card(
            "Microfonul folosit",
            "Microfonul de la dictare. Alegerea „Automat” însemnă că îl alege Windows, "
            "de obicei cel mai bun de acum.",
        )
        self.eticheta_microfon = self._valoare(corp, C.card)
        ui_comun.Buton(
            corp, "Alege microfonul", self._schimba_microfon, latime=250, inaltime=48
        ).pack(anchor="w")

    def _rand_difuzor(self) -> None:
        """Rândul 4: ieșirea de sunet folosită."""
        C = ui_comun.CULORI
        corp = self._card(
            "Difuzorul folosit",
            "Unde se aude sunetul de probă și ce s-a înregistrat. „Automat” însemnă că îl "
            "alege Windows.",
        )
        self.eticheta_difuzor = self._valoare(corp, C.card)
        ui_comun.Buton(
            corp, "Alege difuzorul", self._schimba_difuzor, latime=250, inaltime=48
        ).pack(anchor="w")

    def _rand_transcriere(self) -> None:
        """Rândul 5: felul de a transcrie (procesor sau placă video)."""
        C = ui_comun.CULORI
        corp = self._card(
            "Cum transcrie",
            "Ce folosește programul la transcriere. „Automat” merge bine pe aproape orice "
            "calculator.",
        )
        valoare = self.config.dispozitiv if self.config.dispozitiv in ("auto", "cpu", "cuda") else "auto"
        self.var_dispozitiv = tk.StringVar(master=self, value=valoare)
        for cod, text, explicatie in OPTIUNI_TRANSCRIERE:
            rand = tk.Frame(corp, background=C.card)
            rand.pack(fill="x", pady=ui_comun.px(2))
            tk.Radiobutton(
                rand,
                text=text,
                variable=self.var_dispozitiv,
                value=cod,
                font=ui_comun.fonturi().buton_secundar,
                background=C.card,
                foreground=C.text,
                activebackground=C.card,
                activeforeground=C.text,
                selectcolor=C.zona_text,
                anchor="w",
                justify="left",
                highlightthickness=0,
                bd=0,
            ).pack(anchor="w")
            eticheta = ui_comun.eticheta(
                rand, explicatie, "mica", fundal=C.card,
                latime_bucati=max(ui_comun.px(240), self._latime_text() - ui_comun.px(40)),
            )
            eticheta.pack(anchor="w", padx=ui_comun.px(26))
            self._etichete_de_asezat.append(eticheta)

    def _rand_salvare(self) -> None:
        """Rândul 6: salvarea automată a textului și a documentului final."""
        corp = self._card(
            "Salvare automată",
            "Cât de des se păstrează textul ca să nu se piardă nimic, și dacă documentul "
            "final se salvează singur după transcriere.",
        )
        # Câmpul cu secundele ține minte din câte în câte secunde se salvează textul
        # de siguranță: o valoare mai mare decât zero însemnă „da”, zero însemnă „nu”.
        try:
            salveaza_singur = int(self.config.salvare_automata_secunde) > 0
        except (TypeError, ValueError):
            salveaza_singur = True
        self.var_salvare_auto = self._rand_da_nu(
            corp,
            f"Salvează singur textul, din {SECUNDE_SALVARE_AUTOMATA} în "
            f"{SECUNDE_SALVARE_AUTOMATA} de secunde",
            salveaza_singur,
        )
        self.var_document_singur = self._rand_da_nu(
            corp,
            "Salvează documentul final singur, imediat după transcriere",
            bool(self.config.salveaza_automat),
        )

    def _rand_da_nu(self, parinte: tk.Misc, text: str, valoare: bool) -> tk.IntVar:
        """Un rând cu „Da” și „Nu” pentru o întrebare simplă."""
        C = ui_comun.CULORI
        rand = tk.Frame(parinte, background=C.card)
        rand.pack(fill="x", pady=(0, ui_comun.px(10)))
        eticheta = ui_comun.eticheta(
            rand, text, "baza", fundal=C.card, latime_bucati=self._latime_text()
        )
        eticheta.pack(anchor="w")
        self._etichete_de_asezat.append(eticheta)
        variabila = tk.IntVar(master=self, value=1 if valoare else 0)
        alegeri = tk.Frame(rand, background=C.card)
        alegeri.pack(anchor="w", padx=ui_comun.px(24), pady=(ui_comun.px(4), 0))
        for text_alegere, cod in (("Da", 1), ("Nu", 0)):
            tk.Radiobutton(
                alegeri,
                text=text_alegere,
                variable=variabila,
                value=cod,
                font=ui_comun.fonturi().buton_secundar,
                background=C.card,
                foreground=C.text,
                activebackground=C.card,
                activeforeground=C.text,
                selectcolor=C.zona_text,
                highlightthickness=0,
                bd=0,
            ).pack(side="left", padx=(0, ui_comun.px(24)))
        return variabila

    def _rand_program(self) -> None:
        """Rândul 7: programul de scris folosit pentru documentele finale."""
        C = ui_comun.CULORI
        corp = self._card(
            "Programul de scris",
            "În ce program se deschid documentele finale. Programul de la început este "
            "LibreOffice Writer.",
        )
        self.eticheta_program = self._valoare(corp, C.card)
        rand = tk.Frame(corp, background=C.card)
        rand.pack(fill="x")
        ui_comun.Buton(
            rand, "Alege alt program", self._schimba_program, latime=260, inaltime=48
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(
            rand, "Revino la LibreOffice", self._program_implicit, latime=290, inaltime=48
        ).pack(side="left")

    # ------------------------------------------------------------------ arătarea valorilor

    def _arata_toate(self) -> None:
        """Scrie pe ecran toate valorile alese acum."""
        self._arata_folder()
        self._arata_limba()
        self._arata_microfon()
        self._arata_difuzor()
        self._arata_program()

    def _arata_folder(self) -> None:
        """Scrie unde se salvează documentele acum."""
        cale = self._folder_curent()
        text = f"Se salvează în: {cale}"
        if not (self.config.director_iesiri or "").strip():
            text += "\n(locul de la început: folderul „Documente”)"
        self.eticheta_folder.configure(text=text)

    def _arata_limba(self) -> None:
        """Scrie limba aleasă acum."""
        nume = {cod: eticheta for eticheta, cod in constante.LIMBI}
        aleasa = nume.get(self.config.limba, self.config.limba or "Română")
        self.eticheta_limba.configure(text=f"Acum: {aleasa}")

    def _arata_microfon(self) -> None:
        """Scrie microfonul ales acum (sau că se alege singur)."""
        cheie = (self.config.microfon_preferat or "").strip()
        if not cheie:
            self.eticheta_microfon.configure(text=f"Acum: {AUTOMAT}")
            return
        gasit = self._dispozitiv_dupa_cheie(cheie, este_intrare=True)
        if gasit is not None:
            self.eticheta_microfon.configure(text=f"Acum: {gasit.descriere()}")
            return
        self.eticheta_microfon.configure(
            text="Acum: microfonul ales mai înainte nu se vede pe calculator.\n"
            "Se folosește cel ales de Windows."
        )

    def _arata_difuzor(self) -> None:
        """Scrie difuzorul ales acum (sau că se alege singur)."""
        cheie = (self.config.difuzor_preferat or "").strip()
        if not cheie:
            self.eticheta_difuzor.configure(text=f"Acum: {AUTOMAT}")
            return
        gasit = self._dispozitiv_dupa_cheie(cheie, este_intrare=False)
        if gasit is not None:
            self.eticheta_difuzor.configure(text=f"Acum: {gasit.descriere()}")
            return
        self.eticheta_difuzor.configure(
            text="Acum: difuzorul ales mai înainte nu se vede pe calculator.\n"
            "Se folosește cel ales de Windows."
        )

    def _arata_program(self) -> None:
        """Scrie ce program de scris este folosit acum."""
        cheie = (self.config.program_scris_preferat or "").strip()
        if cheie:
            program = None
            try:
                program = programe_scris.dupa_cheie(cheie)
            except Exception as exc:
                jurnal.atentionare(f"Nu am putut verifica programul de scris ales: {exc}")
            if program is not None:
                self.eticheta_program.configure(
                    text=f"Programul ales: {program.nume} (ales de tine)"
                )
                return
            nume = self.config.program_scris_nume or "Programul ales mai înainte"
            self.eticheta_program.configure(
                text=f"Programul ales: {nume} nu mai este pe calculator.\nSe folosește programul de la început."
            )
            return
        text = libreoffice.nume_pentru_utilizator()
        try:
            stare = libreoffice.stare()
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut verifica LibreOffice: {exc}")
            stare = None
        if stare is None:
            self.eticheta_program.configure(text=f"Programul ales: {text}")
            return
        if not stare.gasit:
            self.eticheta_program.configure(
                text=f"Programul ales: {text}\n(nu este instalat încă)"
            )
            return
        versiune = f", versiunea {stare.versiune}" if stare.versiune else ""
        self.eticheta_program.configure(text=f"Programul ales: {text} (instalat{versiune})")

    # ------------------------------------------------------------------ schimbări

    def _schimba_folder(self) -> None:
        """Cere alt folder pentru documente și verifică scrierea în el."""
        cale = alege_folder(self, self._folder_curent())
        if cale is None:
            return
        se_poate_scrie, mesaj = biblioteca.verificare_folder(cale)
        if not se_poate_scrie:
            self._mesaj_folder_protejat(cale, mesaj)
            return
        self.config.director_iesiri = str(cale)
        self._arata_folder()
        self.linie_stare.arata(
            "Schimbat",
            f"documentele noi se salvează în {cale}. Apasă «Salvează setările» ca să "
            "rămână așa.",
            "bine",
        )

    def _mesaj_folder_protejat(self, cale: Path, mesaj: str) -> None:
        """Mesaj în trei părți: acolo nu se poate scrie, alege alt loc."""
        self.linie_stare.arata("Neschimbat", "folderul a rămas cel de dinainte.", "atentie")
        ui_comun.dialog_eroare(
            self,
            erori.folder_nu_se_poate_scrie(str(cale), detalii=mesaj),
            la_actiune=self._dupa_eroare_folder,
        )

    def _dupa_eroare_folder(self, fel: str) -> None:
        """Butoanele din mesajul de eroare al folderului."""
        if fel == erori.INCERCARE_DIN_NOU:
            self._schimba_folder()
        elif fel == erori.DESCHIDE_FOLDER:
            self._deschide_folder()

    def _folder_implicit(self) -> None:
        """Readuce folderul de salvare la locul de la început („Documente”)."""
        self.config.director_iesiri = ""
        self._arata_folder()
        self.linie_stare.arata(
            "Schimbat", "documentele se salvează iar în folderul „Documente”.", "bine"
        )

    def _deschide_folder(self) -> None:
        """Deschide Explorerul pe folderul de salvare de acum."""
        if sisteme.deschide_folder(self._folder_curent()):
            self.linie_stare.arata("Arătat", "am deschis folderul documentelor.", "normal")
            return
        ui_comun.anunta(
            self,
            "Folderul nu s-a deschis",
            "Windows nu a putut deschide folderul acum.\n\n"
            "Probabil pentru că: folderul a fost mutat sau șters între timp.\n\n"
            "Ce faci acum: apasă «Schimbă folderul» și alege alt loc, sau încearcă din nou "
            "peste o clipă.",
        )

    def _schimba_limba(self) -> None:
        """Alege limba vorbită din lista de limbi a programului."""
        optiuni = [(eticheta, cod) for eticheta, cod in constante.LIMBI]
        cod = _alege_din_lista(
            self,
            "Limba vorbită",
            "Alege limba în care vorbești, ca programul să scrie corect.",
            optiuni,
            self.config.limba,
        )
        if cod is None:
            return
        self.config.limba = cod
        self._arata_limba()
        nume = {cod_limba: eticheta for eticheta, cod_limba in constante.LIMBI}
        self.linie_stare.arata(
            "Schimbat", f"limba aleasă este {nume.get(cod, cod)}.", "bine"
        )

    def _optiuni_microfoane(self) -> list[tuple[str, str]]:
        """Lista pentru alegerea microfonului: „Automat”, apoi microfoanele găsite."""
        optiuni: list[tuple[str, str]] = [(AUTOMAT, "")]
        for dispozitiv in self._dispozitive(este_intrare=True):
            optiuni.append((dispozitiv.descriere(), dispozitiv.cheie))
        return optiuni

    def _optiuni_difuzoare(self) -> list[tuple[str, str]]:
        """Lista pentru alegerea difuzorului: „Automat”, apoi ieșirile găsite."""
        optiuni: list[tuple[str, str]] = [(AUTOMAT, "")]
        for dispozitiv in self._dispozitive(este_intrare=False):
            optiuni.append((dispozitiv.descriere(), dispozitiv.cheie))
        return optiuni

    def _dispozitive(self, este_intrare: bool) -> list:
        """Dispozitivele de sunet de pe calculator, citite de la Windows."""
        try:
            return list(dispozitive.microfoane() if este_intrare else dispozitive.iesiri())
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut citi dispozitivele de sunet: {exc}")
            return []

    def _dispozitiv_dupa_cheie(self, cheie: str, este_intrare: bool):
        """Găsește dispozitivul ținut minte în setări, dacă mai este conectat."""
        try:
            return dispozitive.alege_dupa_cheie(
                cheie, self._dispozitive(este_intrare), este_intrare=este_intrare
            )
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut verifica dispozitivul ales: {exc}")
            return None

    def _schimba_microfon(self) -> None:
        """Alege microfonul folosit la dictare."""
        optiuni = self._optiuni_microfoane()
        if len(optiuni) <= 1:
            self._fara_dispozitive("microfoane", "microfonul")
            return
        cheie = _alege_din_lista(
            self,
            "Microfonul folosit",
            "Alege microfonul la care vorbești.",
            optiuni,
            self.config.microfon_preferat or "",
        )
        if cheie is None:
            return
        self.config.microfon_preferat = cheie
        self._arata_microfon()
        self.linie_stare.arata(
            "Schimbat",
            "microfonul ales se folosește de acum. Apasă «Salvează setările» ca să rămână așa.",
            "bine",
        )

    def _schimba_difuzor(self) -> None:
        """Alege ieșirea de sunet folosită."""
        optiuni = self._optiuni_difuzoare()
        if len(optiuni) <= 1:
            self._fara_dispozitive("difuzoare", "difuzorul")
            return
        cheie = _alege_din_lista(
            self,
            "Difuzorul folosit",
            "Alege unde vrei să se audă sunetul.",
            optiuni,
            self.config.difuzor_preferat or "",
        )
        if cheie is None:
            return
        self.config.difuzor_preferat = cheie
        self._arata_difuzor()
        self.linie_stare.arata(
            "Schimbat",
            "difuzorul ales se folosește de acum. Apasă «Salvează setările» ca să rămână așa.",
            "bine",
        )

    def _fara_dispozitive(self, ce_lipseste: str, cum_se_numește: str) -> None:
        """Explică, în trei părți, ce se face când nu se vede niciun dispozitiv."""
        ui_comun.anunta(
            self,
            f"Nu am găsit {ce_lipseste}",
            f"Pe acest calculator nu se vede acum niciun {cum_se_numește}.\n\n"
            "Probabil pentru că: dispozitivul nu este conectat sau lipsește driverul lui de sunet.\n\n"
            f"Ce faci acum: conectează {cum_se_numește} și apasă din nou butonul de alegere; "
            "verificarea sunetului se poate face din ecranul de început.",
        )

    def _schimba_program(self) -> None:
        """Caută programele de scris de pe calculator și lasă utilizatorul să aleagă."""
        try:
            programe = list(programe_scris.gaseste_programe())
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut căuta programele de scris: {exc}")
            programe = []
        if not programe:
            ui_comun.anunta(
                self,
                "Nu am găsit programe de scris",
                "Pe acest calculator nu am găsit niciun program de scris.\n\n"
                "Probabil pentru că: nu este instalat niciunul, sau este instalat într-un loc "
                "pe care Windows nu îl știe.\n\n"
                "Ce faci acum: documentele se salvează oricum (ca DOCX, ODT sau PDF) și se pot "
                "deschide cu dublu-clic.",
            )
            return
        optiuni = [(program.descriere(), program.cheie) for program in programe]
        cheie = _alege_din_lista(
            self,
            "Programul de scris",
            "Alege programul în care să se deschidă documentele finale.",
            optiuni,
            self.config.program_scris_preferat or "",
        )
        if not cheie:
            return
        program = programe_scris.dupa_cheie(cheie)
        if program is None:
            return
        if getattr(program, "implicit", False):
            self._program_implicit()
            return
        self.config.program_scris_preferat = program.cheie
        self.config.program_scris_nume = program.nume
        self._arata_program()
        self.linie_stare.arata(
            "Schimbat",
            f"documentele se deschid în {program.nume}. Apasă «Salvează setările» ca să "
            "rămână așa.",
            "bine",
        )

    def _program_implicit(self) -> None:
        """Readuce programul de scris la LibreOffice (alegerea de la început)."""
        self.config.program_scris_preferat = ""
        self.config.program_scris_nume = ""
        self._arata_program()
        self.linie_stare.arata(
            "Schimbat", "documentele se deschid iar în LibreOffice Writer.", "bine"
        )

    # ------------------------------------------------------------------ salvare

    def _rand_afisare(self) -> None:
        """Setari pentru afisarea textului (punctul 28)."""
        interior = self._card(
            "Afișarea textului",
            "Cum se vede textul în editor: mărimea scrisului, fontul, "
            "rândurile lungi, spațierea și marginile.",
        )
        C = ui_comun.CULORI

        # Marimea scrisului
        rand = tk.Frame(interior, background=C.card)
        rand.pack(fill="x", pady=(0, ui_comun.px(8)))
        ui_comun.eticheta(rand, "Mărimea scrisului:", "baza", fundal=C.card).pack(side="left")
        self.var_marime_scris = tk.IntVar(value=getattr(self.config, "marire_scris", 100))
        scala = tk.Scale(
            rand, from_=80, to=200, orient="horizontal", variable=self.var_marime_scris,
            length=ui_comun.px(220), background=C.card, highlightthickness=0,
        )
        scala.pack(side="left", padx=(ui_comun.px(8), ui_comun.px(8)))
        ui_comun.eticheta(rand, "%", "baza", fundal=C.card).pack(side="left")
        ui_comun.Buton(rand, "A-", lambda: self._schimba_marime(-10), latime=90, inaltime=40).pack(side="left", padx=(ui_comun.px(8), 0))
        ui_comun.Buton(rand, "A+", lambda: self._schimba_marime(+10), latime=90, inaltime=40).pack(side="left", padx=(ui_comun.px(4), 0))

        # Wrap
        self.var_wrap = tk.BooleanVar(value=getattr(self.config, "wrap_text", True))
        ttk.Checkbutton(interior, text="Rândurile lungi trec pe rândul următor", variable=self.var_wrap).pack(anchor="w", pady=(0, ui_comun.px(6)))

        # Font
        rand2 = tk.Frame(interior, background=C.card)
        rand2.pack(fill="x", pady=(0, ui_comun.px(6)))
        ui_comun.eticheta(rand2, "Tipul de scris:", "baza", fundal=C.card).pack(side="left")
        self.var_font = tk.StringVar(value=getattr(self.config, "font_text", "") or "Implicit")
        self.combo_font = ttk.Combobox(rand2, values=["Implicit", "Segoe UI", "Arial", "Tahoma", "Calibri"], state="readonly", width=18, textvariable=self.var_font)
        self.combo_font.pack(side="left", padx=(ui_comun.px(8), 0))

        # Spatiere
        rand3 = tk.Frame(interior, background=C.card)
        rand3.pack(fill="x", pady=(0, ui_comun.px(6)))
        ui_comun.eticheta(rand3, "Distanța dintre rânduri:", "baza", fundal=C.card).pack(side="left")
        self.var_spatiere = tk.StringVar(value=getattr(self.config, "spatiere_linii", "normal"))
        self.combo_spatiere = ttk.Combobox(rand3, values=["normal", "mare", "foarte_mare"], state="readonly", width=16, textvariable=self.var_spatiere)
        self.combo_spatiere.pack(side="left", padx=(ui_comun.px(8), 0))

        # Latime max
        rand4 = tk.Frame(interior, background=C.card)
        rand4.pack(fill="x", pady=(0, ui_comun.px(6)))
        ui_comun.eticheta(rand4, "Lățimea maximă a rândului:", "baza", fundal=C.card).pack(side="left")
        self.var_latime = tk.StringVar(value=getattr(self.config, "latime_max_rand", "tot"))
        self.combo_latime = ttk.Combobox(rand4, values=["tot", "ingust"], state="readonly", width=12, textvariable=self.var_latime)
        self.combo_latime.pack(side="left", padx=(ui_comun.px(8), 0))

        # Margini
        rand5 = tk.Frame(interior, background=C.card)
        rand5.pack(fill="x", pady=(0, ui_comun.px(6)))
        ui_comun.eticheta(rand5, "Marginile textului (px):", "baza", fundal=C.card).pack(side="left")
        self.var_margini = tk.IntVar(value=getattr(self.config, "margini_text", 8))
        tk.Spinbox(rand5, from_=0, to=40, textvariable=self.var_margini, width=6).pack(side="left", padx=(ui_comun.px(8), 0))

        # Preview
        self.eticheta_preview = ui_comun.eticheta(
            interior, "Știința și înțelepciunea țăranului român.", "baza", fundal=C.card, latime_bucati=600,
        )
        self.eticheta_preview.pack(anchor="w", pady=(ui_comun.px(8), ui_comun.px(6)))

        ui_comun.Buton(interior, "Revino la setările inițiale", self._reset_afisare, latime=260, inaltime=44).pack(anchor="w", pady=(0, ui_comun.px(4)))

    def _schimba_marime(self, delta: int) -> None:
        try:
            val = int(self.var_marime_scris.get()) + delta
        except (tk.TclError, ValueError):
            val = 100
        val = max(80, min(200, val))
        self.var_marime_scris.set(val)

    def _reset_afisare(self) -> None:
        self.var_marime_scris.set(100)
        self.var_wrap.set(True)
        self.var_font.set("Implicit")
        self.var_spatiere.set("normal")
        self.var_latime.set("tot")
        self.var_margini.set(8)


    def _rand_aspect(self) -> None:
        interior = self._card(
            "Aspect",
            "Modul de afișare: luminos, întunecat sau ca Windows.",
        )
        C = ui_comun.CULORI
        rand = tk.Frame(interior, background=C.card)
        rand.pack(fill="x", pady=(0, ui_comun.px(6)))
        ui_comun.eticheta(rand, "Mod de afișare:", "baza", fundal=C.card).pack(side="left")
        self.var_mod = tk.StringVar(value=getattr(self.config, "mod_afisare", "windows"))
        self.combo_mod = ttk.Combobox(
            rand, values=["windows", "luminos", "intunecat"], state="readonly", width=16, textvariable=self.var_mod
        )
        self.combo_mod.pack(side="left", padx=(ui_comun.px(8), 0))
        self.combo_mod.bind("<<ComboboxSelected>>", lambda _e: self._aplica_mod())

    def _aplica_mod(self) -> None:
        try:
            self.config.mod_afisare = self.var_mod.get()
            ui_comun.aplica_tema(self.config.mod_afisare)
        except Exception as exc:
            jurnal.atentionare(f"Modul de afișare nu a putut fi aplicat: {exc}")

    def _aduna(self) -> None:
        """Pune în setări tot ce a ales utilizatorul pe rânduri."""
        try:
            self.config.dispozitiv = self.var_dispozitiv.get()
        except (tk.TclError, AttributeError):
            pass
        try:
            # Rândul „din 30 în 30 de secunde” ține în câmpul cu secundele dacă textul de
            # siguranță se salvează singur: zero însemnă „nu”, o valoare mai mare decât
            # zero însemnă „da”. Când se pornește și câmpul era gol, se pune 30 de secunde.
            if self.var_salvare_auto.get():
                try:
                    cat = int(self.config.salvare_automata_secunde)
                except (TypeError, ValueError):
                    cat = 0
                if cat <= 0:
                    self.config.salvare_automata_secunde = SECUNDE_SALVARE_AUTOMATA
            else:
                self.config.salvare_automata_secunde = 0
        except (tk.TclError, AttributeError):
            pass
        try:
            self.config.salveaza_automat = bool(self.var_document_singur.get())
        except (tk.TclError, AttributeError):
            pass
        try:
            self.config.mod_afisare = self.var_mod.get()
        except (tk.TclError, AttributeError):
            pass
        try:
            self.config.marire_scris = int(self.var_marime_scris.get())
        except (tk.TclError, ValueError, AttributeError):
            pass
        try:
            self.config.wrap_text = bool(self.var_wrap.get())
        except (tk.TclError, AttributeError):
            pass
        try:
            font = self.var_font.get()
            self.config.font_text = "" if font == "Implicit" else font
        except (tk.TclError, AttributeError):
            pass
        try:
            self.config.spatiere_linii = self.var_spatiere.get()
        except (tk.TclError, AttributeError):
            pass
        try:
            self.config.latime_max_rand = self.var_latime.get()
        except (tk.TclError, AttributeError):
            pass
        try:
            self.config.margini_text = int(self.var_margini.get())
        except (tk.TclError, ValueError, AttributeError):
            pass

    def _schimbari(self) -> bool:
        """Adevărat dacă s-a schimbat ceva de la deschiderea ferestrei."""
        try:
            self._aduna()
            return self._copie() != self._stare_inceput
        except Exception:
            return False

    def _salveaza(self) -> None:
        """Scrie setările pe disc și spune dacă a mers."""
        self._aduna()
        if not config_modul.salveaza(self.config):
            self.linie_stare.arata(
                "Nepăstrat", "setările nu au putut fi scrise pe disc.", "problema"
            )
            ui_comun.dialog_eroare(
                self,
                erori.Eroare(
                    ce_s_a_intamplat="Setările nu au putut fi păstrate.",
                    de_ce="folderul programului este protejat sau discul este plin.",
                    ce_faci_acum=(
                        "Încearcă din nou. Dacă tot nu merge, închide programul, pornește-l "
                        "din nou și schimbă doar o setare o dată."
                    ),
                    actiuni=[erori.Actiune("Încearcă din nou", erori.INCERCARE_DIN_NOU)],
                ),
                la_actiune=self._dupa_eroare_salvare,
            )
            return
        self._stare_inceput = self._copie()
        self.linie_stare.arata("Salvat", "setările s-au păstrat și se folosesc de acum.", "bine")
        if self.la_salvare is not None:
            try:
                self.la_salvare(self.config)
            except Exception as exc:
                jurnal.atentionare(f"Ce urma după salvarea setărilor a eșuat: {exc}")

    def _dupa_eroare_salvare(self, fel: str) -> None:
        """Butonul „Încearcă din nou” din mesajul de eroare al salvării."""
        if fel == erori.INCERCARE_DIN_NOU:
            self._salveaza()

    # ------------------------------------------------------------------ așezare și închidere

    def _la_redimensionare(self, eveniment) -> None:
        """Potrivește lățimea rândurilor când se schimbă fereastra."""
        try:
            self.canvas.itemconfigure(self._fereastra_corp, width=eveniment.width)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            return
        self._aseaza_etichetele()

    def _aseaza_etichetele(self) -> None:
        """Rescrie lățimea la care se rupe rândul fiecărui text de pe rânduri."""
        latime = self._latime_text()
        for eticheta in self._etichete_de_asezat:
            try:
                eticheta.configure(wraplength=latime)
            except tk.TclError:
                pass

    def _peste_lista(self, eveniment) -> bool:
        """Adevărat dacă arătătorul mouse-ului este deasupra rândurilor."""
        try:
            element = self.winfo_containing(eveniment.x_root, eveniment.y_root)
        except (tk.TclError, AttributeError):
            return False
        while element is not None:
            if element is self.canvas or element is self.corp:
                return True
            element = getattr(element, "master", None)
        return False

    def _roata(self, eveniment) -> None:
        """Derulează rândurile cu rotița mouse-ului, când arătătorul este peste ele."""
        if not self._peste_lista(eveniment):
            return
        pas = -1 if getattr(eveniment, "delta", 0) > 0 else 1
        try:
            self.canvas.yview_scroll(pas, "units")
        except tk.TclError:
            pass

    def _ajutor(self) -> None:
        """Deschide ajutorul acestui ecran (butonul „? Ajutor” sau tasta F1)."""
        from . import ui_ajutor

        try:
            ui_ajutor.deschide(self, "setari")
        except Exception as exc:
            jurnal.eroare(f"Ajutorul nu s-a putut deschide: {exc}")
            ui_comun.anunta(self, "Ajutor", "Ajutorul nu s-a putut deschide acum. Încearcă din nou.")

    def _inchide(self) -> None:
        """Închide fereastra, după ce întreabă dacă setările se păstrează."""
        if self._schimbari():
            rezultat = ui_comun.dialog(
                self,
                "Setări schimbate",
                "Ai schimbat niște setări. Vrei să le păstrez înainte de a închide?",
                [
                    ("Păstrează setările", "principal"),
                    ("Nu le păstra", "secundar"),
                    ("Înapoi", "secundar"),
                ],
                implicit=0,
                anulare=2,
            )
            if rezultat is None or rezultat == 2:
                return
            if rezultat == 0:
                self._salveaza()
                if self._schimbari():
                    # Setările nu au putut fi scrise: rămânem în fereastră.
                    return
        try:
            self.destroy()
        except tk.TclError:
            pass


def deschide(parinte: tk.Misc, config_obj, la_salvare=None) -> None:
    """Deschide fereastra „Setări” și așteaptă să fie închisă.

    La „Salvează setările” se cheamă ``la_salvare(config)``, dacă a fost dat.
    """
    existente = [fereastra for fereastra in parinte.winfo_children() if isinstance(fereastra, FereastraSetari)]
    if existente:
        # Fereastra se deschide o singură dată: dacă e deja pe ecran, o aduce în față
        # și tot așteaptă să fie închisă, ca la o deschidere obișnuită.
        existente[0].lift()
        existente[0].focus_set()
        existente[0].wait_window()
        return
    fereastra = FereastraSetari(parinte, config_obj, la_salvare=la_salvare)
    fereastra.wait_window()
