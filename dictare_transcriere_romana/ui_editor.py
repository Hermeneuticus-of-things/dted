"""Editorul simplu din program (punctul 12).

Editorul este locul în care textul apare imediat după dictare sau după
transcriere și în care poate fi corectat fără alt program. Este intenționat
simplu: text mare, fără formatare, doar uneltele de care are nevoie un om
obosit: anulează, refă, caută, copiază tot, mărește sau micșorează scrisul și
butoane pentru diacriticele românești (ă, â, î, ș, ț).

Textul se salvează automat și se păstrează o copie de siguranță, ca o
închidere bruscă a programului să nu piardă nimic.
"""

from __future__ import annotations

import datetime as dt
import re
import tkinter as tk
from pathlib import Path

from . import biblioteca, config as config_modul, jurnal, text_ro, ui_comun

#: Cât de mare poate fi scrisul din editor.
SCRIS_MIC = 14
SCRIS_MARE = 32

#: Literele românești care se pot insera cu un buton.
DIACRITICE = ("ă", "â", "î", "ș", "ț", "Ă", "Â", "Î", "Ș", "Ț")

#: Înlocuirile făcute la lipirea textului (litere vechi → litere corecte).
_INLOCUIRI_LIPIRE = (("ş", "ș"), ("Ş", "Ș"), ("ţ", "ț"), ("Ţ", "Ț"))


class Editor(tk.Frame):
    """Zona de text editabilă, cu uneltele ei, în română."""

    def __init__(self, parinte: tk.Misc, stare_obj, la_actiune=None, inaltime: int = 16):
        super().__init__(parinte, background=ui_comun.CULORI.card)
        self.stare = stare_obj
        self.la_actiune = la_actiune
        cfg = config_modul.incarca()
        self._scris = max(SCRIS_MIC, min(SCRIS_MARE, int(SCRIS_MIC * getattr(cfg, "marire_scris", 100) / 100)))
        self._wrap = "word" if getattr(cfg, "wrap_text", True) else "none"
        self._font = getattr(cfg, "font_text", "") or ui_comun.familia()
        spatiere = getattr(cfg, "spatiere_linii", "normal")
        self._spacing1 = 2 if spatiere == "normal" else (6 if spatiere == "mare" else 10)
        self._margini = getattr(cfg, "margini_text", 8)
        self._provizoriu_inceput: str | None = None
        self._cauta = ""
        self._rand_cautare: tk.Frame | None = None
        self._dictionar: set[str] | None = None
        self._linii = inaltime

        self._construieste()

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        C = ui_comun.CULORI
        f = ui_comun.fonturi()

        # Rândul de unelte (uneltele cerute de punctul 12, nimic în plus).
        unelte = tk.Frame(self, background=C.card)
        unelte.pack(fill="x", pady=(0, ui_comun.px(6)))
        self.buton_anuleaza = ui_comun.ButonScurtatura(
            unelte, "Anulează ultima modificare", self.anuleaza, latime=280, inaltime=44,
            scurtatura="Ctrl+Z",
        )
        self.buton_anuleaza.pack(side="left", padx=(0, ui_comun.px(6)))
        self.buton_refa = ui_comun.ButonScurtatura(
            unelte, "Refă", self.refa, latime=140, inaltime=44, scurtatura="Ctrl+Y"
        )
        self.buton_refa.pack(side="left", padx=(0, ui_comun.px(6)))
        self.buton_cauta = ui_comun.ButonScurtatura(
            unelte, "Caută în text", self.deschide_cautarea, latime=180, inaltime=44,
            scurtatura="Ctrl+F",
        )
        self.buton_cauta.pack(side="left", padx=(0, ui_comun.px(6)))
        self.buton_copiaza = ui_comun.Buton(
            unelte, "Copiază tot textul", self.copiaza_tot, latime=200, inaltime=44
        )
        self.buton_copiaza.pack(side="left", padx=(0, ui_comun.px(6)))
        self.buton_mare = ui_comun.Buton(
            unelte, "Mărește scrisul", lambda: self.schimba_scris(+2), latime=170, inaltime=44
        )
        self.buton_mare.pack(side="left", padx=(0, ui_comun.px(6)))
        self.buton_mic = ui_comun.Buton(
            unelte, "Micșorează scrisul", lambda: self.schimba_scris(-2), latime=180, inaltime=44
        )
        self.buton_mic.pack(side="left")

        # Rândul cu diacritice, lângă text, ușor de găsit când corectezi.
        diacritice = tk.Frame(self, background=C.card)
        diacritice.pack(fill="x", pady=(0, ui_comun.px(4)))
        ui_comun.eticheta(
            diacritice, "Litere românești:", "baza", fundal=C.card
        ).pack(side="left", padx=(0, ui_comun.px(6)))
        for litera in DIACRITICE:
            buton = ui_comun.Buton(
                diacritice, litera, lambda l=litera: self.insera(l),
                latime=44, inaltime=44,
            )
            buton.pack(side="left", padx=(0, ui_comun.px(4)))

        # Zona de text, cu derulare, cu colturi rotunjite.
        zona = tk.Canvas(self, background=C.fundal, highlightthickness=0, bd=0, height=ui_comun.px(max(200, self._linii * 20)))
        zona.pack(fill="both", expand=True)
        raza = ui_comun.px(12)

        def _redesenat(_e=None):
            try:
                w = zona.winfo_width()
                h = zona.winfo_height()
                if w <= 1 or h <= 1:
                    return
                zona.delete("text_bg")
                ui_comun._rotunjeste(zona, 2, 2, w - 2, h - 2, raza, fill=C.zona_text, outline=C.chenar, width=ui_comun.px(2))
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
            wrap=self._wrap,
            font=(self._font, self._scris),
            background=C.zona_text,
            foreground=C.text,
            insertbackground=C.text,
            selectbackground=C.principal,
            selectforeground=C.principal_text,
            highlightthickness=ui_comun.px(2),
            highlightbackground=C.chenar,
            highlightcolor=C.chenar_focus,
            bd=0,
            undo=True,
            height=self._linii,
            spacing1=ui_comun.px(self._spacing1),
            spacing3=ui_comun.px(4),
            padx=ui_comun.px(self._margini),
            pady=ui_comun.px(6),
        )
        derulare = tk.Scrollbar(interior, command=self.text.yview)
        self.text.configure(yscrollcommand=derulare.set)
        self.text.pack(side="left", fill="both", expand=True)
        derulare.pack(side="right", fill="y")

        # Textul încă nesigur se scrie cu gri, restul cu negru.
        self.text.tag_configure("provizoriu", foreground=C.text_dezactivat)
        self.text.tag_configure("gasit", background=C.galben_fundal)
        self.text.tag_configure(
            "posibil_gresit", underline=True, underlinefg=C.rosu_text
        )

        # Rândul de dedesubt: cât s-a salvat și câte cuvinte sunt.
        jos = tk.Frame(self, background=C.card)
        jos.pack(fill="x", pady=(ui_comun.px(4), 0))
        self.eticheta_salvare = tk.Label(
            jos,
            text="",
            font=ui_comun.fonturi().baza,
            background=C.card,
            foreground=C.text_secundar,
        )
        self.eticheta_salvare.pack(side="left")
        self.eticheta_cuvinte = tk.Label(
            jos,
            text="",
            font=ui_comun.fonturi().baza,
            background=C.card,
            foreground=C.text_secundar,
        )
        self.eticheta_cuvinte.pack(side="right")

        # Scurtăturile de tastatură cerute.
        self.text.bind("<Control-z>", lambda _e: (self.anuleaza(), "break")[1])
        self.text.bind("<Control-Z>", lambda _e: (self.anuleaza(), "break")[1])
        self.text.bind("<Control-y>", lambda _e: (self.refa(), "break")[1])
        self.text.bind("<Control-Y>", lambda _e: (self.refa(), "break")[1])
        self.text.bind("<Control-f>", lambda _e: (self.deschide_cautarea(), "break")[1])
        self.text.bind("<Control-F>", lambda _e: (self.deschide_cautarea(), "break")[1])
        self.text.bind("<Control-a>", self._selecteaza_tot)

        # Prevenire suprascriere/stricare text la Ctrl+T, Ctrl+D, Ctrl+O
        self.text.bind("<Control-t>", lambda _e: (getattr(self.aplicatie, "arata_ecran", lambda _n: None)("transcriere"), "break")[1])
        self.text.bind("<Control-T>", lambda _e: (getattr(self.aplicatie, "arata_ecran", lambda _n: None)("transcriere"), "break")[1])
        self.text.bind("<Control-d>", lambda _e: (getattr(self.aplicatie, "arata_ecran", lambda _n: None)("dictare"), "break")[1])
        self.text.bind("<Control-D>", lambda _e: (getattr(self.aplicatie, "arata_ecran", lambda _n: None)("dictare"), "break")[1])
        self.text.bind("<Control-o>", lambda _e: (getattr(self.aplicatie, "transcrie_fisier_ales", lambda: None)(), "break")[1])
        self.text.bind("<Control-O>", lambda _e: (getattr(self.aplicatie, "transcrie_fisier_ales", lambda: None)(), "break")[1])

        # Mărire / micșorare / resetare mărime scris
        self.text.bind("<Control-plus>", lambda _e: (getattr(self.aplicatie, "mareste_scrisul", lambda: None)(), "break")[1])
        self.text.bind("<Control-equal>", lambda _e: (getattr(self.aplicatie, "mareste_scrisul", lambda: None)(), "break")[1])
        self.text.bind("<Control-KP_Add>", lambda _e: (getattr(self.aplicatie, "mareste_scrisul", lambda: None)(), "break")[1])
        self.text.bind("<Control-minus>", lambda _e: (getattr(self.aplicatie, "micsoreaza_scrisul", lambda: None)(), "break")[1])
        self.text.bind("<Control-KP_Subtract>", lambda _e: (getattr(self.aplicatie, "micsoreaza_scrisul", lambda: None)(), "break")[1])
        self.text.bind("<Control-0>", lambda _e: (getattr(self.aplicatie, "reseteaza_scrisul", lambda: None)(), "break")[1])
        self.text.bind("<Control-KP_0>", lambda _e: (getattr(self.aplicatie, "reseteaza_scrisul", lambda: None)(), "break")[1])

        self.text.bind("<KeyRelease>", self._dupa_scriere, add="+")
        self.text.bind("<<Modified>>", self._modificat, add="+")
        self.text.bind("<<Paste>>", self._lipeste, add="+")

        self.actualizeaza_etichete()

    # ------------------------------------------------------------------ text

    def seteaza_text(self, text: str, deruleaza_sus: bool = True) -> None:
        """Pune textul de pe ecran în editor (înlocuiește ce era)."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text or "")
        self.text.tag_remove("provizoriu", "1.0", "end")
        self._provizoriu_inceput = None
        if deruleaza_sus:
            self.text.see("1.0")
            self.text.mark_set("insert", "1.0")
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.stare.text = text or ""
        self.stare.provizoriu = ""
        self.actualizeaza_etichete()

    def arata_provizoriu(self, text: str) -> None:
        """Arată o propoziție încă nesigură (peste textul deja hotărât)."""
        text = (text or "").strip()
        if not text:
            return
        if self._provizoriu_inceput is not None:
            self.text.tag_remove("provizoriu", self._provizoriu_inceput, "end")
            self.text.delete(self._provizoriu_inceput, "end")
            self._provizoriu_inceput = None
        gol = not self.text.get("1.0", "end").strip()
        if not gol:
            sfarsit = self.text.get("end-2c", "end-1c")
            if sfarsit and not sfarsit.isspace():
                self.text.insert("end", " ")
        inceput = self.text.index("insert")
        self.text.insert("end", text)
        self.text.tag_add("provizoriu", inceput, "end")
        self._provizoriu_inceput = self.text.index(f"{inceput} linestart")
        self.text.see("end")
        self.stare.provizoriu = text
        self.actualizeaza_etichete()

    def finalizeaza_provizoriu(self, salveaza: bool = True) -> None:
        """Textul nesigur devine text sigur (negru), fără să miște cursorul."""
        if self._provizoriu_inceput is not None:
            self.text.tag_remove("provizoriu", self._provizoriu_inceput, "end")
            self._provizoriu_inceput = None
        self.stare.provizoriu = ""
        self.sincronizeaza(salveaza=salveaza)

    def text_ecran(self) -> str:
        """Textul din editor, exact așa cum se vede."""
        return self.text.get("1.0", "end-1c")

    def sincronizeaza(self, salveaza: bool = True) -> str:
        """Potrivește starea programului cu ce se vede în editor."""
        continut = self.text_ecran()
        schimbat = continut != self.stare.text_complet()
        self.stare.text = continut
        self.stare.provizoriu = ""
        if schimbat:
            self.stare.marcheaza_modificat()
            if salveaza:
                self.salveaza_automat()
        self.actualizeaza_etichete()
        return continut

    # ------------------------------------------------------------------ unelte

    def anuleaza(self) -> None:
        try:
            self.text.edit_undo()
        except tk.TclError:
            pass
        self.sincronizeaza()

    def refa(self) -> None:
        try:
            self.text.edit_redo()
        except tk.TclError:
            pass
        self.sincronizeaza()

    def copiaza_tot(self) -> None:
        """Pune tot textul în memoria Windows, ca să poată fi lipit oriunde."""
        try:
            self.clipboard_clear()
            self.clipboard_append(self.text_ecran())
            self.update_idletasks()
        except tk.TclError:
            pass
        ui_comun.anunta(
            self,
            "Text copiat",
            "Tot textul din program a fost copiat. Îl poți lipi în alt program "
            "(Word, e-mail, mesaje) cu Ctrl+V.",
        )

    def insera(self, litera: str) -> None:
        """Inserează o literă românească la locul cursorului."""
        try:
            self.text.insert("insert", litera)
        except tk.TclError:
            return
        self.sincronizeaza()
        self.text.focus_set()

    def schimba_scris(self, cu_cat: int) -> None:
        """Mărește sau micșorează scrisul din editor."""
        self._scris = max(SCRIS_MIC, min(SCRIS_MARE, self._scris + cu_cat))
        self.text.configure(font=(ui_comun.familia(), self._scris))
        jurnal.info(f"Scrisul din editor: {self._scris} puncte")
        if self._scris <= SCRIS_MIC:
            ui_comun.anunta(self, "Scrisul nu se mai poate micșora", "Scrisul este deja cel mai mic.")
        if self._scris >= SCRIS_MARE:
            ui_comun.anunta(self, "Scrisul nu se mai poate mări", "Scrisul este deja cel mai mare.")

    # ------------------------------------------------------------------ căutare

    def deschide_cautarea(self) -> None:
        """Deschide rândul de căutare (Ctrl+F)."""
        if self._rand_cautare is not None:
            self._camp_cautare.focus_set()
            return
        C = ui_comun.CULORI
        self._rand_cautare = tk.Frame(self, background=C.card)
        self._rand_cautare.pack(fill="x", pady=(ui_comun.px(6), 0))
        ui_comun.eticheta(self._rand_cautare, "Caută:", "baza", fundal=C.card).pack(side="left")
        self._camp_cautare = tk.Entry(
            self._rand_cautare,
            font=ui_comun.fonturi().baza,
            background=C.zona_text,
            foreground=C.text,
            highlightthickness=ui_comun.px(2),
            highlightbackground=C.chenar,
        )
        self._camp_cautare.pack(side="left", fill="x", expand=True, padx=ui_comun.px(6))
        self._camp_cautare.bind("<Return>", lambda _e: self.cauta_urmatorul())
        ui_comun.Buton(
            self._rand_cautare, "Caută următorul", self.cauta_urmatorul, latime=190, inaltime=44
        ).pack(side="left", padx=(0, ui_comun.px(6)))
        ui_comun.Buton(
            self._rand_cautare, "Închide căutarea", self.inchide_cautarea, latime=180, inaltime=44
        ).pack(side="left")
        self._camp_cautare.focus_set()

    def inchide_cautarea(self) -> None:
        self.text.tag_remove("gasit", "1.0", "end")
        if self._rand_cautare is not None:
            self._rand_cautare.destroy()
            self._rand_cautare = None
        self.text.focus_set()

    def cauta_urmatorul(self) -> bool:
        """Caută textul scris de utilizator, de la cursor înainte."""
        if self._rand_cautare is None:
            return False
        cautat = self._camp_cautare.get()
        if not cautat:
            return False
        self.text.tag_remove("gasit", "1.0", "end")
        where = self.text.search(cautat, "insert", nocase=True, stopindex="end")
        if not where:
            # Dacă nu mai este nimic în jos, căutăm de la început.
            where = self.text.search(cautat, "1.0", nocase=True, stopindex="end")
            if where:
                ui_comun.anunta(
                    self,
                    "Am ajuns la început",
                    f"Textul „{cautat}” există mai sus. Am sărit la prima apariție.",
                )
        if not where:
            ui_comun.anunta(
                self,
                "Nu am găsit textul",
                f"Textul „{cautat}” nu apare în document. Verifică literele (poate fi o "
                "greșeală de scriere) și încearcă din nou.",
            )
            return False
        sfarsit = f"{where}+{len(cautat)}c"
        self.text.tag_add("gasit", where, sfarsit)
        self.text.mark_set("insert", sfarsit)
        self.text.see(where)
        return True

    # ------------------------------------------------------------------ scriere / lipire

    def _selecteaza_tot(self, _eveniment=None) -> str:
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "1.0")
        return "break"

    def _modificat(self, _eveniment=None) -> None:
        # Odată ce utilizatorul scrie, textul devine al lui: îl socotim sigur.
        self.text.edit_modified(False)

    def _dupa_scriere(self, _eveniment=None) -> None:
        self.sincronizeaza()

    def _lipeste(self, _eveniment=None) -> None:
        """Lipește textul, corectând literele vechi ş/ţ în ș/ț."""
        try:
            lipit = self.clipboard_get()
        except tk.TclError:
            return None
        curatat = text_ro.repara_diacritice(lipit)
        inainte = self.text_ecran()
        if self.text.tag_ranges("sel"):
            self.text.delete("sel.first", "sel.last")
        self.text.insert("insert", curatat)
        if curatat != lipit and inainte != self.text_ecran():
            jurnal.info("Textul lipit a fost corectat (ş/ţ → ș/ț).")
        self.sincronizeaza()
        return "break"

    # ------------------------------------------------------------------ verificare / salvare

    def actualizeaza_etichete(self) -> None:
        """Arată ora salvării automate și câte cuvinte are textul."""
        moment = self.stare.ultima_salvare
        if moment is None:
            text_salvare = "Se salvează automat (la fiecare acțiune)."
        else:
            text_salvare = f"Salvat automat la {biblioteca.ora_salvarii(moment)}"
        self.eticheta_salvare.configure(text=text_salvare)
        cuvinte = len([cuvant for cuvant in self.text_ecran().split() if cuvant])
        self.eticheta_cuvinte.configure(
            text=f"{cuvinte} cuvinte" if cuvinte else "text gol"
        )

    def salveaza_automat(self) -> bool:
        """Scrie copia de siguranță (se cheamă des și este ieftin)."""
        if not self.text_ecran().strip():
            self.actualizeaza_etichete()
            return False
        reusit = self.stare.salveaza_de_siguranta()
        self.actualizeaza_etichete()
        if self.la_actiune is not None:
            try:
                self.la_actiune()
            except Exception as exc:  # pragma: no cover - nu oprește programul
                jurnal.atentionare(f"Acțiunea după salvare a eșuat: {exc}")
        return reusit

    def pune_focus(self) -> None:
        try:
            self.text.focus_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ ortografie (opțional)

    def verifica_ortografia(self) -> int:
        """Marchează cuvintele care nu apar în dicționarul românesc local.

        Se face **doar** dacă dicționarul românesc există pe calculator (adus de
        LibreOffice). Nu trimite nimic pe internet și nu schimbă textul: doar
        subliniază cuvintele care par scrise greșit.
        """
        cuvintele = self._cuvinte_dictionar()
        self.text.tag_remove("posibil_gresit", "1.0", "end")
        if not cuvintele:
            return 0
        continut = self.text_ecran()
        cate = 0
        for potrivire in re.finditer(r"\b[A-Za-zĂÂÎȘȚĂÂÎȘȚăâîșț-]{3,}\b", continut):
            cuvant = potrivire.group(0).lower().strip("-")
            if not cuvant or cuvant in cuvintele:
                continue
            if any(parte in cuvintele for parte in cuvant.split("-")):
                continue
            if cuvant.endswith(("ul", "ului", "ele", "ilor")):
                radacina = re.sub(r"(ul|ului|ele|ilor)$", "", cuvant)
                if radacina in cuvintele:
                    continue
            cate += 1
            inceput = f"1.0+{potrivire.start()}c"
            sfarsit = f"1.0+{potrivire.end()}c"
            self.text.tag_add("posibil_gresit", inceput, sfarsit)
        return cate

    def _cuvinte_dictionar(self) -> set[str] | None:
        """Cuvintele din dicționarul românesc local, dacă există."""
        if self._dictionar is not None:
            return self._dictionar or None
        for cale in _fisiere_dictionar():
            try:
                cuvinte: set[str] = set()
                for linie in cale.read_text(encoding="utf-8", errors="replace").splitlines():
                    cuvant = linie.split("/", 1)[0].strip().lower()
                    if cuvant and not cuvant.isdigit():
                        cuvinte.add(cuvant)
                if cuvinte:
                    jurnal.info(f"Dicționar românesc citit din {cale} ({len(cuvinte)} cuvinte).")
                    self._dictionar = cuvinte
                    return cuvinte
            except OSError:
                continue
        self._dictionar = set()
        return None


def _fisiere_dictionar() -> list[Path]:
    """Fișierele de dicționar românesc de pe calculator (căutate la nevoie)."""
    from . import libreoffice

    gasite: list[Path] = []
    try:
        executabil = libreoffice.gaseste_libreoffice()
    except Exception:
        executabil = None
    if executabil:
        try:
            baza = Path(executabil).parent
            for parte in ("share/extensions/dict-ro", "share/dict/ooo", "share/dict"):
                for nume in ("ro_RO.dic", "ro.dic"):
                    candidat = baza / parte / nume
                    if candidat.exists():
                        gasite.append(candidat)
        except Exception:
            pass
    return gasite
