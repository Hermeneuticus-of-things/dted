"""Fereastra de ajutor, pe fiecare ecran (cerință de accesibilitate).

Aceeași fereastră se deschide din butonul „? Ajutor” sau cu tasta F1, de pe
orice ecran, și explică mereu patru lucruri: ce vezi, ce faci acum, ce urmează
și răspunsurile la problemele frecvente. Se poate citi și „Citește-mă.txt” ori
reporni turul de la prima pornire.
"""

from __future__ import annotations

import tkinter as tk

from . import ajutor, cai, sisteme, ui_comun


class FereastraAjutor(tk.Toplevel):
    """Ajutorul, cu explicațiile ecranului cerut și întrebările frecvente."""

    def __init__(self, parinte: tk.Misc, cheie: str = "principal"):
        super().__init__(parinte)
        self.ghid = ajutor.ghid(cheie)
        ui_comun.seteaza_titlu(self, f"Ajutor — {self.ghid.titlu}")
        self.configure(background=ui_comun.CULORI.fundal)
        self.transient(parinte)
        self.resizable(True, True)
        self.minsize(ui_comun.px(720), ui_comun.px(520))

        self._construieste()
        ui_comun.centrat(self, latime=860, inaltime=640)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.bind("<Escape>", lambda _e: self._inchide())

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        C = ui_comun.CULORI
        f = ui_comun.fonturi()

        antet = tk.Frame(self, background=C.fundal)
        antet.pack(fill="x", padx=ui_comun.px(14), pady=(ui_comun.px(12), ui_comun.px(6)))
        ui_comun.eticheta(antet, self.ghid.titlu, "titlu", fundal=C.fundal).pack(side="left")
        ui_comun.Buton(
            antet, "Închide ajutorul", self._inchide, latime=180, inaltime=44, scurtatura="Esc"
        ).pack(side="right")

        zona_exterior = tk.Frame(self, background=C.card, highlightthickness=ui_comun.px(2),
                                 highlightbackground=C.chenar, bd=0)
        zona_exterior.pack(fill="both", expand=True, padx=ui_comun.px(14))

        canvas = tk.Canvas(zona_exterior, background=C.card, highlightthickness=0, bd=0)
        derulare = tk.Scrollbar(zona_exterior, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=derulare.set)
        canvas.pack(side="left", fill="both", expand=True)
        derulare.pack(side="right", fill="y")

        corp = tk.Frame(canvas, background=C.card)
        fereastra = canvas.create_window((0, 0), window=corp, anchor="nw")
        corp.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind(
            "<Configure>", lambda eveniment: canvas.itemconfigure(fereastra, width=eveniment.width)
        )

        self._sectiune(corp, "Ce vezi pe acest ecran", self.ghid.ce_vezi)
        self._sectiune(corp, "Ce faci acum", self.ghid.ce_faci)
        self._sectiune(corp, "Ce urmează", self.ghid.urmeaza)

        if self.ghid.probleme:
            ui_comun.eticheta(
                corp, "Probleme frecvente pe acest ecran", "subtitlu", fundal=C.card
            ).pack(anchor="w", padx=ui_comun.px(16), pady=(ui_comun.px(14), ui_comun.px(4)))
            for intrebare, raspuns in self.ghid.probleme:
                self._intrebare(corp, intrebare, raspuns)

        ui_comun.eticheta(corp, "Întrebări frecvente", "subtitlu", fundal=C.card).pack(
            anchor="w", padx=ui_comun.px(16), pady=(ui_comun.px(16), ui_comun.px(4))
        )
        for intrebare, raspuns in ajutor.INTREBARI:
            self._intrebare(corp, intrebare, raspuns)

        jos = tk.Frame(self, background=C.fundal)
        jos.pack(fill="x", padx=ui_comun.px(14), pady=ui_comun.px(12))
        ui_comun.Buton(
            jos, "Vezi din nou turul de la început", self._tur, latime=340, inaltime=48
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(
            jos, "Deschide „Citește-mă.txt”", self._citeste_ma, latime=280, inaltime=48
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(
            jos, "Deschide ghidul de folosire", self._ghid_scris, latime=300, inaltime=48
        ).pack(side="left")

    def _sectiune(self, parinte: tk.Misc, titlu: str, linii: list[str]) -> None:
        C = ui_comun.CULORI
        ui_comun.eticheta(parinte, titlu, "subtitlu", fundal=C.card).pack(
            anchor="w", padx=ui_comun.px(16), pady=(ui_comun.px(14), ui_comun.px(4))
        )
        if not linii:
            ui_comun.eticheta(parinte, "—", "baza", fundal=C.card, latime_bucati=760).pack(
                anchor="w", padx=ui_comun.px(26)
            )
            return
        for linie in linii:
            ui_comun.eticheta(
                parinte, f"•  {linie}", "baza", fundal=C.card, latime_bucati=700
            ).pack(anchor="w", padx=ui_comun.px(26), pady=ui_comun.px(2))

    def _intrebare(self, parinte: tk.Misc, intrebare: str, raspuns: str) -> None:
        C = ui_comun.CULORI
        ui_comun.eticheta(parinte, f"•  {intrebare}", "buton", fundal=C.card, latime_bucati=760).pack(
            anchor="w", padx=ui_comun.px(26), pady=(ui_comun.px(8), 0)
        )
        ui_comun.eticheta(parinte, raspuns, "baza", fundal=C.card, latime_bucati=700).pack(
            anchor="w", padx=ui_comun.px(44), pady=(0, ui_comun.px(2))
        )

    # ------------------------------------------------------------------ butoane

    def _tur(self) -> None:
        from . import ui_tur

        self._inchide()

        def _dupa() -> None:
            ui_tur.porneste(self.master, la_final=None, fortat=True)

        try:
            self.after(200, _dupa)
        except tk.TclError:
            pass

    def _citeste_ma(self) -> None:
        cale = cai.fisier_citeste_ma()
        if not cale.exists():
            scris = ajutor.scrie_citeste_ma(cale)
            if scris is None:
                ui_comun.anunta(
                    self,
                    "Nu am putut scrie fișierul",
                    "„Citește-mă.txt” nu a putut fi scris lângă program. "
                    "Poți citi aceleași explicații aici, în fereastra de ajutor.",
                )
                return
        if not sisteme.deschide_fisier(cale):
            ui_comun.anunta(
                self,
                "Fișierul nu s-a deschis",
                f"Deschide-l singur, cu dublu-clic, din acest loc:\n\n{cale}",
            )

    def _ghid_scris(self) -> None:
        cale = cai.director_instalare() / "Ghid de folosire.txt"
        if not cale.exists():
            scris = ajutor.scrie_ghid_ajutor(cale)
            if scris is None:
                ui_comun.anunta(
                    self,
                    "Nu am putut scrie ghidul",
                    "Ghidul nu a putut fi scris lângă program.",
                )
                return
        if not sisteme.deschide_fisier(cale):
            ui_comun.anunta(
                self,
                "Fișierul nu s-a deschis",
                f"Deschide-l singur, cu dublu-clic, din acest loc:\n\n{cale}",
            )

    def _inchide(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def deschide(parinte: tk.Misc, cheie: str = "principal") -> None:
    """Deschide ajutorul ecranului cerut (folosit de butonul „? Ajutor” și de F1)."""
    existent = [fereastra for fereastra in parinte.winfo_children() if isinstance(fereastra, FereastraAjutor)]
    if existent:
        existent[0].lift()
        existent[0].focus_set()
        return
    fereastra = FereastraAjutor(parinte, cheie)
    fereastra.wait_window()
