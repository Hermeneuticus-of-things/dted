"""Partea de la finalul unei dictări sau transcrieri: bannerul și cele 4 butoane.

Cerința spune exact ce vede utilizatorul când textul este gata:

* bannerul „Gata! Verifică textul de mai jos și corectează ce nu e bine.”;
* patru butoane: „Deschide în LibreOffice pentru corectare” (principal),
  „Salvează ca DOCX”, „Salvează ca ODT”, „Alte formate…”.

Butoanele cheamă metodele ferestrei principale, ca să nu fie cod scris de două
ori: ``salveaza_document(fel)``, ``deschide_in_libreoffice()``, ``alte_formate()``.
"""

from __future__ import annotations

import tkinter as tk

from . import ui_comun

#: Textul bannerului de final, cuvânt cu cuvânt cum cere cerința.
TEXT_GATA = "Gata! Verifică textul de mai jos și corectează ce nu e bine."


class ZonaFinala(tk.Frame):
    """Bannerul de final plus cele patru butoane care apar când textul e gata."""

    def __init__(self, parinte: tk.Misc, aplicatie):
        super().__init__(parinte, background=ui_comun.CULORI.fundal)
        self.aplicatie = aplicatie
        self.banner = ui_comun.Banner(self, "bine")
        self.banner.arata(TEXT_GATA)
        self.banner.pack(fill="x", pady=(0, ui_comun.px(8)))

        rand_1 = tk.Frame(self, background=ui_comun.CULORI.fundal)
        rand_1.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        rand_2 = tk.Frame(self, background=ui_comun.CULORI.fundal)
        rand_2.pack(fill="x")

        self.buton_libreoffice = ui_comun.Buton(
            rand_1,
            "Deschide în LibreOffice pentru corectare",
            self._deschide_libreoffice,
            fel="principal",
            latime=460,
            inaltime=64,
        )
        self.buton_libreoffice.pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        self.buton_docx = ui_comun.Buton(
            rand_1, "Salvează ca DOCX", lambda: self._salveaza("docx"), latime=280, inaltime=64
        )
        self.buton_docx.pack(side="left")
        self.buton_odt = ui_comun.Buton(
            rand_2, "Salvează ca ODT", lambda: self._salveaza("odt"), latime=280, inaltime=64
        )
        self.buton_odt.pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        self.buton_alte = ui_comun.Buton(
            rand_2, "Alte formate…", self._alte_formate, latime=280, inaltime=64
        )
        self.buton_alte.pack(side="left")

    # ------------------------------------------------------------------ acțiuni

    def _salveaza(self, fel: str) -> None:
        self.aplicatie.salveaza_document(fel)

    def _deschide_libreoffice(self) -> None:
        self.aplicatie.deschide_in_libreoffice()

    def _alte_formate(self) -> None:
        self.aplicatie.alte_formate()

    # ------------------------------------------------------------------ arătare

    def arata(self) -> None:
        """Arată bannerul și butoanele (se cheamă când textul este gata)."""
        self.pack(fill="x", pady=(ui_comun.px(10), 0))
        improspateaza = getattr(self.aplicatie, "reimprospateaza_aspectul", None)
        if improspateaza is not None:
            improspateaza()

    def ascunde(self) -> None:
        self.pack_forget()
