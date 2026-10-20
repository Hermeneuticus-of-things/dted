"""Turul de la prima pornire: patru pași scurți, cu „Înainte” și „Sari peste”."""

from __future__ import annotations

import tkinter as tk

from . import ajutor, ui_comun


class FereastraTur(tk.Toplevel):
    """Turul de început (cel mult patru pași, fiecare cu o singură idee)."""

    def __init__(self, parinte: tk.Misc, la_final=None):
        super().__init__(parinte)
        self.la_final = la_final
        self.pas = 0
        self.pasi = ajutor.PASI_TUR
        ui_comun.seteaza_titlu(self, "Bine ai venit")
        self.configure(background=ui_comun.CULORI.fundal)
        self.transient(parinte)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._sari)

        C = ui_comun.CULORI
        card, corp = ui_comun.card(self, "")
        card.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(16))

        self.eticheta_pas = ui_comun.eticheta(corp, "", "subtitlu", fundal=C.card)
        self.eticheta_pas.pack(anchor="w")
        self.eticheta_titlu = ui_comun.eticheta(corp, "", "titlu", fundal=C.card, latime_bucati=560)
        self.eticheta_titlu.pack(anchor="w", pady=(ui_comun.px(6), ui_comun.px(4)))
        self.eticheta_text = ui_comun.eticheta(corp, "", "baza", fundal=C.card, latime_bucati=560)
        self.eticheta_text.pack(anchor="w")

        butoane = tk.Frame(corp, background=C.card)
        butoane.pack(fill="x", pady=(ui_comun.px(14), 0))
        self.buton_inalte = ui_comun.Buton(
            butoane, "Înainte", self._inalte, fel="principal", latime=260, inaltime=64
        )
        self.buton_inalte.pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(butoane, "Sari peste", self._sari, latime=180, inaltime=48).pack(side="left")

        self.bind("<Return>", lambda _e: self._inalte())
        self.bind("<Escape>", lambda _e: self._sari())
        self._arata_pas()
        ui_comun.centrat(self, latime=660, inaltime=420)

    # ------------------------------------------------------------------ pași

    def _arata_pas(self) -> None:
        cheie, titlu, text = self.pasi[self.pas]
        self.eticheta_pas.configure(text=f"Pasul {self.pas + 1} din {len(self.pasi)}")
        self.eticheta_titlu.configure(text=titlu)
        self.eticheta_text.configure(text=text)
        self.buton_inalte.seteaza_text(
            "Am înțeles" if self.pas == len(self.pasi) - 1 else "Înainte"
        )

    def _inalte(self) -> None:
        self.pas += 1
        if self.pas >= len(self.pasi):
            self._termina()
            return
        self._arata_pas()

    def _sari(self) -> None:
        self._termina()

    def _termina(self) -> None:
        cheie = self.pasi[min(self.pas, len(self.pasi) - 1)][0]
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self.la_final is not None:
            try:
                self.la_final(cheie)
            except Exception:
                pass


def porneste(parinte: tk.Misc, la_final=None, fortat: bool = False) -> None:
    """Deschide turul (o singură dată la prima pornire, sau la cerere)."""
    fereastra = FereastraTur(parinte, la_final)
    fereastra.wait_window()
