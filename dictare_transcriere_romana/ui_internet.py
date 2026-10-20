"""Avertizarea roșie de securitate (cerința 22): internet, Wi-Fi, Bluetooth, stick.

Dictarea și transcrierea se fac numai pe calculator: sunetul, textul și
documentele nu pleacă nicăieri. Ca omul să fie liniștit și atent, programul se
uită la cele patru căi prin care ceva ar putea ieși din calculator și, dacă
vreuna este deschisă, arată o fereastră mare și roșie, în cuvinte de om
obișnuit, cu un buton mare pentru fiecare cale.

Aici se află trei lucruri:

* ``IndicatorCai`` — semnul mic, mereu vizibil, cu patru pictograme (verde =
  închis, roșu = deschis) și vorbele „Totul e închis – lucrezi în siguranță.”;
* ``FereastraAvertisment`` — fereastra roșie, cu toate căile deschise una sub
  alta, fiecare cu butonul ei;
* ``explica`` — ajutorul pas cu pas (cu desene) pentru fiecare cale.

Fereastra nu blochează lucrul: dictarea merge mai departe, textul nu se pierde,
iar rândurile devin verzi singure după ce omul închide calea.
"""

from __future__ import annotations

import datetime as dt
import time
import tkinter as tk

from . import jurnal, securitate, sisteme, ui_comun

#: Cât timp nu mai arătăm fereastra roșie de la sine (10 minute).
PAUZA_DUPA_AVERTISMENT = 600.0

#: Titlul mare al ferestrei.
TEXT_AVERTISMENT = "Ai lăsat ceva deschis"

#: Explicația de sus, aceeași pentru toate căile.
TEXT_INTRODUCERE = (
    "Dictarea și transcrierea se fac numai pe acest calculator. Programul NU trimite nimic "
    "nicăieri: nici pe internet, nici prin Bluetooth, nici pe stick. Dar acum ai ceva "
    "deschis, iar dacă lucrezi cu lucruri personale sau secrete, e mai bine să închizi."
)

#: Vorbele arătate de indicator când totul este închis.
TEXT_LINISTIT = "Totul e închis – lucrezi în siguranță."


# --------------------------------------------------------------------------- desene


def deseneaza_semn(zona: tk.Canvas, cheie: str, culoare: str, marime: int = 26, fundal: str = "") -> None:
    """Desenează semnul unei căi (glob, valuri, Bluetooth, stick), fără fișiere."""
    zona.delete("all")
    lat = zona.winfo_reqwidth() or marime
    centru = lat // 2
    jos = marime - 3
    gros = max(2, marime // 9)
    if cheie == "internet":
        raza = marime // 2 - 4
        zona.create_oval(centru - raza, 3, centru + raza, 3 + 2 * raza, outline=culoare, width=gros)
        zona.create_oval(
            centru - raza // 2, 3, centru + raza // 2, 3 + 2 * raza, outline=culoare, width=max(1, gros - 1)
        )
        zona.create_line(centru - raza, 3 + raza, centru + raza, 3 + raza, fill=culoare, width=max(1, gros - 1))
    elif cheie == "wifi":
        for index, raza in enumerate((marime // 6, marime // 3, marime // 2 - 1)):
            zona.create_arc(
                centru - raza,
                jos - 2 * raza,
                centru + raza,
                jos + raza,
                start=30,
                extent=120,
                style="arc",
                outline=culoare,
                width=gros,
            )
        zona.create_oval(centru - gros, jos - 2 * gros, centru + gros, jos, fill=culoare, outline=culoare)
    elif cheie == "bluetooth":
        jumatate = marime // 2 - 3
        zona.create_line(centru - jumatate // 2, 4, centru + jumatate // 2, jos - 4, fill=culoare, width=gros)
        zona.create_line(
            centru + jumatate // 2, 4, centru - jumatate // 2, jos - 4, fill=culoare, width=gros
        )
        zona.create_line(centru, 3, centru, marime - 3, fill=culoare, width=gros)
        zona.create_line(centru, marime // 2, centru + jumatate, marime // 2 - jumatate, fill=culoare, width=gros)
    else:  # stick USB
        latime = marime - 8
        zona.create_rectangle(4, marime // 2 - 4, 4 + latime, marime // 2 + 4, outline=culoare, width=gros)
        zona.create_rectangle(
            4 + latime - 4, marime // 2 - 2, 4 + latime + 3, marime // 2 + 2, fill=culoare, outline=culoare
        )


# --------------------------------------------------------------------------- indicatorul


class IndicatorCai(tk.Frame):
    """Semnul mic, mereu vizibil: patru pictograme, verzi sau roșii, plus vorbele potrivite."""

    def __init__(self, parinte: tk.Misc, config, pentru_dictare: bool = False):
        super().__init__(
            parinte,
            background=ui_comun.CULORI.card,
            highlightthickness=ui_comun.px(2),
            highlightbackground=ui_comun.CULORI.chenar,
            bd=0,
            takefocus=True,
        )
        self.config = config
        self.pentru_dictare = pentru_dictare
        self.stare: securitate.StareCai = securitate.StareCai()
        self._semne: dict[str, tuple[tk.Canvas, tk.Label]] = {}

        rand = tk.Frame(self, background=ui_comun.CULORI.card)
        rand.pack(padx=ui_comun.px(8), pady=ui_comun.px(4))
        for cheie in ("internet", "wifi", "bluetooth", "stick"):
            coloana = tk.Frame(rand, background=ui_comun.CULORI.card)
            coloana.pack(side="left", padx=ui_comun.px(4))
            zona = tk.Canvas(
                coloana,
                width=ui_comun.px(26),
                height=ui_comun.px(26),
                background=ui_comun.CULORI.card,
                highlightthickness=0,
                bd=0,
            )
            zona.pack()
            eticheta = ui_comun.eticheta(
                coloana,
                _nume_scurt(cheie),
                "mica",
                fundal=ui_comun.CULORI.card,
                latime_bucati=90,
                ancora="center",
            )
            eticheta.configure(justify="center")
            eticheta.pack()
            self._semne[cheie] = (zona, eticheta)
        self.eticheta_stare = ui_comun.eticheta(
            self, "Se verifică…", "mica", fundal=ui_comun.CULORI.card, latime_bucati=260, ancora="center"
        )
        self.eticheta_stare.configure(justify="center")
        self.eticheta_stare.pack(padx=ui_comun.px(6), pady=(0, ui_comun.px(4)))

        for element in (self, *self.winfo_children(), *rand.winfo_children()):
            element.bind("<Button-1>", lambda _e: self.deschide_explicatia())
            element.bind("<Return>", lambda _e: self.deschide_explicatia())
        self.actualizeaza()

    def actualizeaza(self) -> securitate.StareCai:
        """Citește acum starea celor patru căi și arată semnele potrivite."""
        try:
            self.stare = securitate.stare(pentru_dictare=self.pentru_dictare)
        except Exception as exc:
            jurnal.atentionare(f"Starea căilor de securitate nu a putut fi citită: {exc}")
            return self.stare
        for cheie, (zona, eticheta) in self._semne.items():
            cale = self.stare.despre(cheie)
            deschisa = bool(cale and cale.deschisa)
            exista = bool(cale is None or cale.exista)
            if not exista:
                culoare = ui_comun.CULORI.succes
            elif deschisa:
                culoare = ui_comun.CULORI.pericol
            else:
                culoare = ui_comun.CULORI.succes
            deseneaza_semn(zona, cheie, culoare, ui_comun.px(26), ui_comun.CULORI.card)
            eticheta.configure(
                text=_nume_scurt(cheie) + ("\n(deschis)" if deschisa else ""),
                foreground=culoare if deschisa else ui_comun.CULORI.text_secundar,
            )
        if self.stare.toate_inchise:
            self.eticheta_stare.configure(text=TEXT_LINISTIT, foreground=ui_comun.CULORI.succes)
        else:
            self.eticheta_stare.configure(text=self.stare.pe_scurt(), foreground=ui_comun.CULORI.pericol)
        return self.stare

    def deschide_explicatia(self) -> None:
        """Un clic pe indicator deschide fereastra cu explicații."""
        deschide_fereastra(self, self.config, self.pentru_dictare)


def _nume_scurt(cheie: str) -> str:
    return {
        "internet": "Internet",
        "wifi": "Wi-Fi",
        "bluetooth": "Bluetooth",
        "stick": "Stick",
    }.get(cheie, cheie)


def indicator(parinte: tk.Misc, config, pentru_dictare: bool = False) -> IndicatorCai:
    """Semnul mic, gata de așezat în colțul de sus al ecranului."""
    return IndicatorCai(parinte, config, pentru_dictare)


#: Numele vechi, păstrat pentru ecranele care îl folosesc deja.
IndicatorInternet = IndicatorCai


# --------------------------------------------------------------------------- fereastra roșie


class FereastraAvertisment(tk.Toplevel):
    """Fereastra mare și roșie, cu toate căile deschise, una sub alta."""

    def __init__(self, parinte: tk.Misc, config, pentru_dictare: bool = False):
        super().__init__(parinte)
        self.config = config
        self.pentru_dictare = pentru_dictare
        self._randuri: dict[str, tuple[tk.Frame, tk.Label, ui_comun.Buton, tk.Canvas]] = {}
        self._id_ceas: str | None = None
        self._ultima_stare = ""

        ui_comun.seteaza_titlu(self, TEXT_AVERTISMENT)
        self.configure(background=ui_comun.CULORI.pericol_fundal)
        self.minsize(ui_comun.px(760), ui_comun.px(420))

        sus = tk.Frame(self, background=ui_comun.CULORI.pericol_fundal)
        sus.pack(fill="x", padx=ui_comun.px(18), pady=(ui_comun.px(14), 0))
        semn = tk.Canvas(
            sus,
            width=ui_comun.px(56),
            height=ui_comun.px(56),
            background=ui_comun.CULORI.pericol_fundal,
            highlightthickness=0,
        )
        semn.pack(side="left")
        semn.create_oval(
            ui_comun.px(4), ui_comun.px(4), ui_comun.px(52), ui_comun.px(52),
            outline=ui_comun.CULORI.pericol, width=ui_comun.px(4),
        )
        semn.create_line(
            ui_comun.px(28), ui_comun.px(14), ui_comun.px(28), ui_comun.px(34),
            fill=ui_comun.CULORI.pericol, width=ui_comun.px(6),
        )
        semn.create_oval(
            ui_comun.px(25), ui_comun.px(38), ui_comun.px(31), ui_comun.px(44),
            fill=ui_comun.CULORI.pericol, outline=ui_comun.CULORI.pericol,
        )
        titlu = ui_comun.eticheta(
            sus, TEXT_AVERTISMENT, "titlu", fundal=ui_comun.CULORI.pericol_fundal, latime_bucati=640
        )
        titlu.configure(foreground=ui_comun.CULORI.pericol_text)
        titlu.pack(side="left", padx=ui_comun.px(10))

        introducere = ui_comun.eticheta(
            self,
            TEXT_INTRODUCERE,
            "baza",
            fundal=ui_comun.CULORI.pericol_fundal,
            latime_bucati=700,
        )
        introducere.configure(foreground=ui_comun.CULORI.text)
        introducere.pack(anchor="w", padx=ui_comun.px(18), pady=(ui_comun.px(8), ui_comun.px(10)))

        self.zona_cai = ui_comun.ZonaDerulare(self, latime_minima=700)
        self.zona_cai.pack(fill="both", expand=True, padx=ui_comun.px(18))

        jos = tk.Frame(self, background=ui_comun.CULORI.pericol_fundal)
        jos.pack(fill="x", padx=ui_comun.px(18), pady=ui_comun.px(14))
        self.buton_avion = ui_comun.Buton(
            jos,
            "Închide totul deodată (Modul avion)",
            self._mod_avion,
            latime=420,
            inaltime=64,
        )
        self.buton_avion.pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        self.buton_continuă = ui_comun.Buton(
            jos, "Am înțeles, continuă", self.distruge, fel="succes", latime=280, inaltime=64
        )
        self.buton_continuă.pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(jos, "Nu mai afișa azi", self._ascunde_azi, latime=240, inaltime=64).pack(side="left")

        self._construieste_randurile()
        self._aseaza()
        self.bind("<Escape>", lambda _e: self.distruge())
        self.reimprospateaza()
        self._id_ceas = self.after(2000, self._ceas)

    # ------------------------------------------------------------------ rândurile

    def _construieste_randurile(self) -> None:
        for copil in list(self.zona_cai.interior.winfo_children()):
            copil.destroy()
        self._randuri.clear()
        for cheie in ("internet", "wifi", "bluetooth", "stick"):
            rand = tk.Frame(
                self.zona_cai.interior,
                background=ui_comun.CULORI.card,
                highlightthickness=ui_comun.px(2),
                highlightbackground=ui_comun.CULORI.chenar,
            )
            rand.pack(fill="x", pady=(0, ui_comun.px(8)))
            semn = tk.Canvas(
                rand,
                width=ui_comun.px(44),
                height=ui_comun.px(44),
                background=ui_comun.CULORI.card,
                highlightthickness=0,
            )
            semn.pack(side="left", padx=ui_comun.px(10), pady=ui_comun.px(8))
            coloana = tk.Frame(rand, background=ui_comun.CULORI.card)
            coloana.pack(side="left", fill="both", expand=True, pady=ui_comun.px(8))
            titlu = ui_comun.eticheta(
                coloana, "", "subtitlu", fundal=ui_comun.CULORI.card, latime_bucati=420
            )
            titlu.pack(anchor="w")
            text = ui_comun.eticheta(
                coloana, "", "baza", fundal=ui_comun.CULORI.card, latime_bucati=420
            )
            text.pack(anchor="w")
            buton = ui_comun.Buton(
                rand, "…", lambda c=cheie: self._apasa(c), fel="principal", latime=300, inaltime=64
            )
            buton.pack(side="right", padx=ui_comun.px(10))
            self._randuri[cheie] = (rand, titlu, buton, semn)
            # Se ține textul de sub titlu legat de rând, ca să fie și el pus la loc.
            rand._eticheta_text = text  # type: ignore[attr-defined]

    def _aseaza(self) -> None:
        """Așază fereastra sus, pe mijloc, ca să nu acopere textul care se dictează."""
        self.update_idletasks()
        ecran_lat, ecran_inalt = ui_comun.maxim_ecran(0.98)
        latime = min(ui_comun.px(900), max(ui_comun.px(760), ecran_lat - ui_comun.px(40)))
        inaltime = min(ui_comun.px(700), max(ui_comun.px(420), ecran_inalt - ui_comun.px(120)))
        x = max(0, (ecran_lat - latime) // 2 + self.winfo_rootx() - self.winfo_rootx())
        y = ui_comun.px(8)
        self.geometry(f"{latime}x{inaltime}+{x}+{y}")

    # ------------------------------------------------------------------ starea

    def reimprospateaza(self) -> None:
        """Recitește starea și arată fiecare cale: roșu dacă e deschisă, verde dacă e închisă."""
        try:
            stare = securitate.stare(pentru_dictare=self.pentru_dictare)
        except Exception as exc:
            jurnal.atentionare(f"Starea căilor nu a putut fi citită: {exc}")
            return
        self._ultima_stare = stare.pe_scurt()
        for cheie, (rand, titlu, buton, semn) in self._randuri.items():
            cale = stare.despre(cheie)
            text = getattr(rand, "_eticheta_text", None)
            if cale is None:
                continue
            deschisa = cale.deschisa and cale.exista
            if not cale.exista:
                rand.configure(background=ui_comun.CULORI.verde_fundal)
                titlu.configure(
                    text=f"{_nume_scurt(cheie)}: nu există pe acest calculator",
                    background=ui_comun.CULORI.verde_fundal,
                    foreground=ui_comun.CULORI.succes,
                )
                if text is not None:
                    text.configure(
                        text="Aici e totul în regulă.", background=ui_comun.CULORI.verde_fundal
                    )
                buton.configure(state="normal")
                buton.activeaza(False)
                buton.seteaza_text("Nu e nevoie de nimic")
                deseneaza_semn(semn, cheie, ui_comun.CULORI.succes, ui_comun.px(44))
                semn.configure(background=ui_comun.CULORI.verde_fundal)
            elif not cale.masurata:
                rand.configure(background=ui_comun.CULORI.card)
                titlu.configure(
                    text=f"{_nume_scurt(cheie)}: se verifică…",
                    background=ui_comun.CULORI.card,
                    foreground=ui_comun.CULORI.text_secundar,
                )
                if text is not None:
                    text.configure(text="", background=ui_comun.CULORI.card)
                buton.activeaza(False)
                buton.seteaza_text("Se verifică…")
                deseneaza_semn(semn, cheie, ui_comun.CULORI.text_secundar, ui_comun.px(44))
                semn.configure(background=ui_comun.CULORI.card)
            elif deschisa:
                rand.configure(background=ui_comun.CULORI.rosu_fundal)
                titlu.configure(
                    text=cale.titlu,
                    background=ui_comun.CULORI.rosu_fundal,
                    foreground=ui_comun.CULORI.rosu_text,
                )
                if text is not None:
                    text.configure(text=cale.text, background=ui_comun.CULORI.rosu_fundal)
                buton.activeaza(True)
                buton.seteaza_fel("principal")
                buton.seteaza_text(cale.buton)
                deseneaza_semn(semn, cheie, ui_comun.CULORI.pericol, ui_comun.px(44), ui_comun.CULORI.rosu_fundal)
                semn.configure(background=ui_comun.CULORI.rosu_fundal)
            else:
                rand.configure(background=ui_comun.CULORI.verde_fundal)
                titlu.configure(
                    text=f"{_nume_scurt(cheie)}: gata, e închis.",
                    background=ui_comun.CULORI.verde_fundal,
                    foreground=ui_comun.CULORI.succes,
                )
                if text is not None:
                    text.configure(
                        text="Aici e totul în regulă.", background=ui_comun.CULORI.verde_fundal
                    )
                buton.activeaza(False)
                buton.seteaza_text("Închis")
                deseneaza_semn(semn, cheie, ui_comun.CULORI.succes, ui_comun.px(44), ui_comun.CULORI.verde_fundal)
                semn.configure(background=ui_comun.CULORI.verde_fundal)
        if stare.toate_inchise:
            self.buton_avion.activeaza(False)
            self.buton_avion.seteaza_text("Totul e închis")
        else:
            self.buton_avion.activeaza(True)

    def _ceas(self) -> None:
        """Din două în două secunde se uită dacă omul a închis ceva."""
        self._id_ceas = None
        if not self.winfo_exists():
            return
        try:
            self.reimprospateaza()
        except tk.TclError:
            return
        self._id_ceas = self.after(2000, self._ceas)

    # ------------------------------------------------------------------ butoane

    def _apasa(self, cheie: str) -> None:
        """Butonul mare al unei căi: deschide setarea Windows sau scoate stickul."""
        if cheie == "stick":
            self._scoate_stickurile()
            return
        if cheie == "internet":
            explica(self, self.config, cheie="internet")
            return
        if securitate.deschide_setarea(cheie):
            self._anunta_deschidere(cheie)
            return
        explica(self, self.config, cheie=cheie)

    def _anunta_deschidere(self, cheie: str) -> None:
        uicm = ui_comun.dialog(
            self,
            f"Cum oprești {securitate.NUME_CAI.get(cheie, cheie)}",
            (
                f"Am deschis setările Windows pentru {securitate.NUME_CAI.get(cheie, cheie)}. "
                "Apasă pe butonul de pornit/oprit din pagina care s-a deschis, apoi întoarce-te "
                "aici: rândul devine verde singur, în două secunde."
            ),
            [("Am oprit, verifică acum", "principal"), ("Mai târziu", "secundar")],
            implicit=0,
            anulare=1,
        )
        if uicm == 0:
            self.reimprospateaza()

    def _scoate_stickurile(self) -> None:
        stare = securitate.stare(pentru_dictare=self.pentru_dictare)
        cale = stare.despre("stick")
        if cale is None or not cale.stickuri:
            self.reimprospateaza()
            return
        nume = ", ".join(stick.descriere() for stick in cale.stickuri)
        răspuns = ui_comun.dialog(
            self,
            "Scoaterea stickului în siguranță",
            (
                f"Scot în siguranță {nume}. Închide programele care folosesc fișiere de pe stick "
                "(de exemplu, o fereastră deschisă pe stick), apoi apasă „Scoate-l acum”."
            ),
            [("Scoate-l acum", "principal"), ("Nu acum", "secundar")],
            implicit=0,
            anulare=1,
        )
        if răspuns != 0:
            return
        mesaje = []
        for stick in cale.stickuri:
            reusit, mesaj = securitate.scoate_in_siguranta(stick.litera)
            mesaje.append(mesaj)
        ui_comun.anunta(self, "Stickul", "\n".join(dict.fromkeys(mesaje)))
        self.reimprospateaza()

    def _mod_avion(self) -> None:
        """Închide totul deodată: internet, Wi-Fi și Bluetooth (Modul avion)."""
        răspuns = ui_comun.dialog(
            self,
            "Închid totul deodată",
            (
                "Se deschide pagina „Mod avion” din Windows. Dacă îl pornești, se închid internetul, "
                "Wi-Fi-ul și Bluetooth-ul deodată. Programul nu schimbă nimic singur: alegi tu în "
                "pagina care se deschide."
            ),
            [("Deschide pagina", "principal"), ("Nu acum", "secundar")],
            implicit=0,
            anulare=1,
        )
        if răspuns == 0 and securitate.deschide_modul_avion():
            self.reimprospateaza()

    def _ascunde_azi(self) -> None:
        ascunde_azi(self.config)
        anunta_ascundere(self)
        self.distruge()

    def distruge(self) -> None:
        """Închide fereastra (lucrul merge mai departe)."""
        if self._id_ceas is not None:
            try:
                self.after_cancel(self._id_ceas)
            except tk.TclError:
                pass
            self._id_ceas = None
        try:
            self.destroy()
        except tk.TclError:
            pass


def anunta_ascundere(parinte: tk.Misc) -> None:
    """Spune simplu că fereastra nu mai apare până mâine (indicatorul rămâne)."""
    ui_comun.dialog(
        parinte,
        "Nu mai arăt fereastra azi",
        (
            "Bine. Nu mai arăt fereastra roșie până mâine. Semnul mic din colț rămâne acolo și "
            "se face roșu dacă ceva se deschide, ca să știi mereu cum stai."
        ),
        [("Am înțeles", "principal")],
    )


# --------------------------------------------------------------------------- arătarea


def _fereastra_deschisa(parinte: tk.Misc) -> FereastraAvertisment | None:
    """Fereastra roșie, dacă este deschisă deja."""
    try:
        for copil in parinte.winfo_toplevel().winfo_children():
            if isinstance(copil, FereastraAvertisment) and copil.winfo_exists():
                return copil
    except tk.TclError:
        return None
    return None


def _cai_de_arătat(config, stare: securitate.StareCai) -> list[securitate.Cale]:
    """Căile deschise pentru care omul vrea să fie avertizat."""
    de_arătat = []
    for cale in stare.deschise:
        camp = securitate.CAMP_SETARE.get(cale.cheie, "")
        if camp and not getattr(config, camp, True):
            continue
        de_arătat.append(cale)
    return de_arătat


def este_ascuns_azi(config) -> bool:
    """Adevărat dacă omul a ales „Nu mai afișa azi”."""
    azi = dt.date.today().isoformat()
    return (getattr(config, "fara_avertisment_azi", "") or "") == azi


def ascunde_azi(config) -> None:
    """Ține minte că omul nu mai vrea fereastra până mâine."""
    from . import config as config_modul

    config.fara_avertisment_azi = dt.date.today().isoformat()
    config_modul.salveaza(config)
    jurnal.info("Fereastra de avertizare nu va mai apărea până mâine.")


def deschide_fereastra(
    parinte: tk.Misc, config, pentru_dictare: bool = False, fortat: bool = True
) -> FereastraAvertisment | None:
    """Deschide fereastra roșie cu toate căile deschise (un clic pe indicator)."""
    existenta = _fereastra_deschisa(parinte)
    if existenta is not None:
        existenta.reimprospateaza()
        try:
            existenta.lift()
            existenta.focus_set()
        except tk.TclError:
            pass
        return existenta
    fereastra = FereastraAvertisment(parinte, config, pentru_dictare=pentru_dictare)
    return fereastra


_ULTIMA_ARATARE: dict[str, float] = {}
_ULTIMELE_CAI: dict[str, tuple[str, ...]] = {}


def avertizeaza(
    parinte: tk.Misc,
    config,
    pentru_dictare: bool = False,
    fortat: bool = False,
    la_continuare=None,
) -> FereastraAvertisment | None:
    """Arată fereastra roșie dacă vreo cale este deschisă.

    Se cheamă la pornire, la începutul dictării, la începutul transcrierii, la
    prima scriere în editor și apoi din când în când cât timp se lucrează. Dacă
    omul a închis-o de curând și nimic nou nu s-a deschis, nu o mai arată;
    dacă apare o cale nouă (de exemplu, se bagă un stick), o arată din nou.
    """
    try:
        stare = securitate.stare(pentru_dictare=pentru_dictare)
    except Exception as exc:
        jurnal.atentionare(f"Verificarea căilor de securitate a eșuat: {exc}")
        return None
    de_arătat = _cai_de_arătat(config, stare)
    if not de_arătat:
        return None
    if este_ascuns_azi(config) and not fortat:
        return None
    cheie_fereastra = parinte.winfo_toplevel().winfo_id() if hasattr(parinte, "winfo_toplevel") else 0
    cheie = f"{cheie_fereastra}-{pentru_dictare}"
    cai_acum = tuple(sorted(cale.cheie for cale in de_arătat))
    acum = time.monotonic()
    ultima = _ULTIMA_ARATARE.get(cheie, 0.0)
    cai_vechi = _ULTIMELE_CAI.get(cheie, ())
    if not fortat and cai_acum == cai_vechi and acum - ultima < PAUZA_DUPA_AVERTISMENT:
        return None
    _ULTIMA_ARATARE[cheie] = acum
    _ULTIMELE_CAI[cheie] = cai_acum
    fereastra = deschide_fereastra(parinte, config, pentru_dictare=pentru_dictare)
    if fereastra is not None and la_continuare is not None:
        vechiul = fereastra.buton_continuă._comanda  # noqa: SLF001 - butonul „Am înțeles, continuă”

        def combina():
            try:
                vechiul()
            finally:
                la_continuare()

        fereastra.buton_continuă._comanda = combina  # noqa: SLF001
    return fereastra


# --------------------------------------------------------------------------- explicații


def explica(parinte: tk.Misc, config=None, cheie: str = "internet", pentru_dictare: bool = False) -> None:
    """Ajutorul simplu: ce este calea respectivă și cum o închizi, pas cu pas."""
    C = ui_comun.CULORI
    fereastra = tk.Toplevel(parinte)
    ui_comun.seteaza_titlu(fereastra, "Cum închizi ce e deschis")
    fereastra.configure(background=C.fundal)
    fereastra.transient(parinte.winfo_toplevel())
    fereastra.minsize(ui_comun.px(760), ui_comun.px(560))

    corp = tk.Frame(fereastra, background=C.fundal)
    corp.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(14))
    ui_comun.eticheta(corp, "Cum închizi ce e deschis", "titlu").pack(anchor="w")
    ui_comun.eticheta(
        corp,
        "Alege calea care te interesează. Programul nu oprește nimic singur: îți arată pe ce să "
        "apeși, iar tu hotărăști. Tot ce este scris aici se face pe calculatorul tău.",
        "baza",
        latime_bucati=880,
    ).pack(anchor="w", pady=(0, ui_comun.px(10)))

    zona = ui_comun.ZonaDerulare(corp, latime_minima=860)
    zona.pack(fill="both", expand=True)
    interior = zona.interior

    _sectiune_internet(interior)
    _sectiune_wifi(interior)
    _sectiune_bluetooth(interior)
    _sectiune_stick(interior)

    rand = tk.Frame(corp, background=C.fundal)
    rand.pack(fill="x", pady=(ui_comun.px(12), 0))
    ui_comun.Buton(
        rand,
        "Pornește Modul avion (închide internet, Wi-Fi și Bluetooth)",
        lambda: securitate.deschide_modul_avion(),
        fel="principal",
        latime=520,
        inaltime=64,
    ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
    ui_comun.Buton(rand, "Închide explicația", fereastra.destroy, latime=260, inaltime=64).pack(side="left")
    fereastra.bind("<Escape>", lambda _e: fereastra.destroy())
    ui_comun.centrat(fereastra, latime=940, inaltime=760)


def _card_cale(interior: tk.Misc, cheie: str, titlu: str, expl: str, pasi: tuple[str, ...], setare: str = "") -> None:
    C = ui_comun.CULORI
    exterior = tk.Frame(interior, background=C.card, highlightthickness=ui_comun.px(2), highlightbackground=C.chenar)
    exterior.pack(fill="x", pady=(0, ui_comun.px(10)))
    sus = tk.Frame(exterior, background=C.card)
    sus.pack(fill="x", padx=ui_comun.px(12), pady=(ui_comun.px(10), 0))
    semn = tk.Canvas(
        sus, width=ui_comun.px(40), height=ui_comun.px(40), background=C.card, highlightthickness=0
    )
    semn.pack(side="left", padx=(0, ui_comun.px(10)))
    deseneaza_semn(semn, cheie, C.principal, ui_comun.px(40), C.card)
    ui_comun.eticheta(sus, titlu, "subtitlu", fundal=C.card, latime_bucati=700).pack(side="left")
    ui_comun.eticheta(exterior, expl, "baza", fundal=C.card, latime_bucati=780).pack(
        anchor="w", padx=ui_comun.px(12), pady=(ui_comun.px(4), 0)
    )
    for pas in pasi:
        ui_comun.eticheta(exterior, "• " + pas, "baza", fundal=C.card, latime_bucati=780).pack(
            anchor="w", padx=ui_comun.px(12)
        )
    if setare:
        ui_comun.Buton(
            exterior,
            f"Deschide setarea Windows ({titlu.split('–')[0].strip()})",
            lambda: securitate.deschide_setarea(cheie),
            latime=420,
            inaltime=64,
        ).pack(anchor="w", padx=ui_comun.px(12), pady=ui_comun.px(10))


def _sectiune_internet(interior: tk.Misc) -> None:
    _card_cale(
        interior,
        "internet",
        "Internetul – legătura prin care calculatorul intră în rețea",
        "Sunt patru căi ca să închizi internetul. Alege-o pe cea mai simplă pentru tine:",
        (
            "Wi-Fi: apasă pe lângă ceas (jos, în dreapta) pe semnul rețelei, apoi pe „Wi-Fi oprit”.",
            "Cablu: dacă ai un cablu de la router în calculator, scoate-l din calculator.",
            "Mod avion: în aceeași listă de lângă ceas, apasă „Mod avion” — se oprește tot deodată.",
            "Telefonul: dacă ții telefonul legat la calculator (Bluetooth sau cablu USB) și îi dai "
            "internet, oprește partajarea din telefon ori scoate cablul.",
        ),
        setare="internet",
    )


def _sectiune_wifi(interior: tk.Misc) -> None:
    _card_cale(
        interior,
        "wifi",
        "Wi-Fi-ul – legătura fără fir",
        "Wi-Fi-ul poate fi pornit chiar dacă nu ești conectat la nimic. Cum îl închizi:",
        (
            "Apasă pe lângă ceas (jos, în dreapta) pe semnul rețelei.",
            "Apasă pe butonul „Wi-Fi” (se face gri) sau pe „Wi-Fi oprit”.",
            "Pe laptop mai este și o tastă cu semnul antenei, care oprește Wi-Fi-ul de tot.",
        ),
        setare="wifi",
    )


def _sectiune_bluetooth(interior: tk.Misc) -> None:
    _card_cale(
        interior,
        "bluetooth",
        "Bluetooth-ul – legătura fără fir cu aparate din apropiere",
        "Bluetooth-ul lasă calculatorul să vorbească cu telefoane, căști sau boxe mici. Cum îl închizi:",
        (
            "Apasă pe lângă ceas (jos, în dreapta) pe semnul rețelei, apoi pe semnul Bluetooth.",
            "Se face gri, adică este oprit.",
            "Dacă folosești căști Bluetooth pentru dictare, lasă-l pornit: este normal.",
        ),
        setare="bluetooth",
    )


def _sectiune_stick(interior: tk.Misc) -> None:
    C = ui_comun.CULORI
    exterior = tk.Frame(interior, background=C.card, highlightthickness=ui_comun.px(2), highlightbackground=C.chenar)
    exterior.pack(fill="x", pady=(0, ui_comun.px(10)))
    sus = tk.Frame(exterior, background=C.card)
    sus.pack(fill="x", padx=ui_comun.px(12), pady=(ui_comun.px(10), 0))
    semn = tk.Canvas(sus, width=ui_comun.px(40), height=ui_comun.px(40), background=C.card, highlightthickness=0)
    semn.pack(side="left", padx=(0, ui_comun.px(10)))
    deseneaza_semn(semn, "stick", C.principal, ui_comun.px(40), C.card)
    ui_comun.eticheta(sus, "Stickul sau cardul de memorie", "subtitlu", fundal=C.card, latime_bucati=700).pack(
        side="left"
    )
    ui_comun.eticheta(
        exterior,
        "Pe stick se pot copia fișiere ușor. Cum îl scoți:",
        "baza",
        fundal=C.card,
        latime_bucati=780,
    ).pack(anchor="w", padx=ui_comun.px(12), pady=(ui_comun.px(4), 0))
    for pas in (
        "Închide ferestrele în care vezi fișiere de pe stick.",
        "Apasă butonul „Scoate stickul în siguranță” din fereastra roșie.",
        "Când îți scrie „Acum poți scoate stickul din calculator.”, trage-l afară.",
    ):
        ui_comun.eticheta(exterior, "• " + pas, "baza", fundal=C.card, latime_bucati=780).pack(
            anchor="w", padx=ui_comun.px(12)
        )
    stare = securitate.stare()
    cale = stare.despre("stick")
    nume = ", ".join(stick.descriere() for stick in (cale.stickuri if cale else ())) or "niciunul acum"
    ui_comun.eticheta(exterior, f"Acum în calculator: {nume}", "mica", fundal=C.card, latime_bucati=780).pack(
        anchor="w", padx=ui_comun.px(12), pady=(ui_comun.px(6), 0)
    )
    if cale is not None and cale.stickuri:
        ui_comun.Buton(
            exterior,
            "Scoate stickul în siguranță",
            lambda: _scoate_din_explicatie(exterior, cale),
            fel="principal",
            latime=340,
            inaltime=64,
        ).pack(anchor="w", padx=ui_comun.px(12), pady=ui_comun.px(10))


def _scoate_din_explicatie(parinte: tk.Misc, cale) -> None:
    mesaje = []
    for stick in cale.stickuri:
        _reusit, mesaj = securitate.scoate_in_siguranta(stick.litera)
        mesaje.append(mesaj)
    ui_comun.anunta(parinte, "Stickul", "\n".join(dict.fromkeys(mesaje)))
