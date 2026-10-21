"""Fundația interfeței: scaling, fonturi, culori, butoane, dialoguri în română.

Aici sunt lucrurile folosite de toate ferestrele programului:

* **DPI**: ``pregateste_dpi()`` se apelează înainte de ``tk.Tk()``, apoi toate
  dimensiunile se scalează (butoanele principale au minimum 64×220 px la 100%,
  cele secundare minimum 44×44 px, distanța dintre ele minimum 12 px).
* **Culori**: perechile folosite sunt verificate cu formula de contrast WCAG;
  textul are minimum 4,5:1, textul mare și chenarele minimum 3:1. Starea nu se
  arată niciodată doar prin culoare: are și pictogramă și cuvânt.
* **Dialoguri proprii**: nu se folosește ``messagebox`` sau ``filedialog``,
  pentru ca toate butoanele să fie în română, iar erorile să aibă trei părți.
"""

from __future__ import annotations

import ctypes
import os
import queue
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import font as tkfont

from . import jurnal
from .constante import NUME_APLICATIE, FORMATE_AUDIO

# --------------------------------------------------------------------------- DPI

#: Factorul de scalare stabilit după pornirea ferestrei (1.0 = 100%).
_SCALA = 1.0


def pregateste_dpi() -> None:
    """Spune Windows că programul știe de ecranele cu scaling (100% → 200%).

    Se apelează **înainte** de ``tk.Tk()``; dacă nu reușește (Windows vechi),
    programul merge în continuare, doar puțin mai mic.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2, bun pentru ecrane cu DPI diferit
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        jurnal.info("Scalare ecran: pe monitor (per-monitor DPI aware).")
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            jurnal.info("Scalare ecran: mod simplu.")
        except Exception as exc:  # pragma: no cover - depinde de Windows
            jurnal.atentionare(f"Scalarea ecranului nu a putut fi anunțată: {exc}")


def seteaza_scala(radacina: tk.Misc) -> float:
    """Citește scalarea reală a ecranului (1.0, 1.5, 2.0 …)."""
    global _SCALA
    try:
        puncte = float(radacina.winfo_fpixels("1i"))
        _SCALA = max(1.0, min(4.0, puncte / 96.0))
    except Exception:
        _SCALA = 1.0
    return _SCALA


def scala() -> float:
    """Factorul de scalare curent."""
    return _SCALA


def px(valoare: float) -> int:
    """Transformă o dimensiune gândită la 100% în pixeli reali."""
    return max(1, int(round(valoare * _SCALA)))


# --------------------------------------------------------------------------- culori


class Culori:
    """Culorile programului (fiecare pereche importantă are contrast suficient)."""

    fundal = "#EEF2F6"
    card = "#FFFFFF"
    chenar = "#5A6B7C"          # chenarul cardurilor: 3:1 pe fundal deschis
    chenar_focus = "#0B3D77"    # inelul de focus, gros și închis la culoare
    text = "#14181C"            # text principal (peste 15:1 pe alb)
    text_secundar = "#39424B"   # text secundar (peste 9:1 pe alb)
    text_dezactivat = "#5C6672"  # text pe zone dezactivate, tot lizibil
    principal = "#0B4A8F"       # acțiunea principală (alb pe albastru: 7:1)
    principal_apasat = "#083569"
    principal_text = "#FFFFFF"
    pericol = "#9E1B1B"         # oprirea dictării / avertismente (alb pe roșu: 7:1)
    pericol_apasat = "#7A1414"
    pericol_text = "#FFFFFF"
    pericol_fundal = "#FBE3E3"  # fundal deschis pentru avertismente roșii
    succes = "#14602C"          # „Am înțeles, continuă” (alb pe verde: 7:1)
    succes_apasat = "#0F4A22"
    succes_text = "#FFFFFF"
    secundar = "#FFFFFF"
    secundar_text = "#12314F"
    bara_goala = "#D7DEE6"
    bara_plina = "#0B4A8F"
    verde_fundal = "#DDF3E2"
    verde_text = "#0B3D1C"
    galben_fundal = "#FDF1D2"
    galben_text = "#4A3200"
    rosu_fundal = "#FBE3E3"
    rosu_text = "#5C1111"
    zona_text = "#FFFFFF"
    dezactivat_fundal = "#E2E7EC"
    dezactivat_text = "#4B5560"


CULORI = Culori()


def _canal(valoare: float) -> float:
    valoare = valoare / 255.0
    return valoare / 12.92 if valoare <= 0.03928 else ((valoare + 0.055) / 1.055) ** 2.4


def _luminanta(culoare: str) -> float:
    """Luminanța relativă a unei culori de forma „#RRGGBB”."""
    text = culoare.lstrip("#")
    r, g, b = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _canal(r) + 0.7152 * _canal(g) + 0.0722 * _canal(b)


def raport_contrast(culoare_1: str, culoare_2: str) -> float:
    """Raportul de contrast dintre două culori (1 = identice, 21 = alb/negru)."""
    luminoase = sorted((_luminanta(culoare_1), _luminanta(culoare_2)), reverse=True)
    return (luminoase[0] + 0.05) / (luminoase[1] + 0.05)


#: Perechile (fundal, text) folosite în program, pentru verificarea automată.
PERECHI_CONTRAST = [
    (CULORI.card, CULORI.text, 4.5),
    (CULORI.card, CULORI.text_secundar, 4.5),
    (CULORI.principal, CULORI.principal_text, 4.5),
    (CULORI.fundal, CULORI.text, 4.5),
    (CULORI.verde_fundal, CULORI.verde_text, 4.5),
    (CULORI.galben_fundal, CULORI.galben_text, 4.5),
    (CULORI.rosu_fundal, CULORI.rosu_text, 4.5),
    (CULORI.dezactivat_fundal, CULORI.dezactivat_text, 4.5),
    (CULORI.card, CULORI.chenar, 3.0),
    (CULORI.card, CULORI.chenar_focus, 3.0),
    (CULORI.dezactivat_fundal, CULORI.principal, 3.0),
    (CULORI.pericol, CULORI.pericol_text, 4.5),
    (CULORI.succes, CULORI.succes_text, 4.5),
]


def verifica_contrast() -> list[str]:
    """Întoarce lista perechilor care NU trec pragul (goală = totul e în regulă)."""
    probleme: list[str] = []
    for fundal, text, prag in PERECHI_CONTRAST:
        raport = raport_contrast(fundal, text)
        if raport < prag:
            probleme.append(
                f"{text} pe {fundal}: contrast {raport:.2f}, sub pragul {prag:.1f}"
            )
    return probleme


# --------------------------------------------------------------------------- mod luminos / întunecat

#: Culorile modului luminos (fundal alb, scris închis la culoare).
_TEMA_LUMINOASA = {
    "fundal": "#EEF2F6",
    "card": "#FFFFFF",
    "chenar": "#5A6B7C",
    "chenar_focus": "#0B3D77",
    "text": "#14181C",
    "text_secundar": "#39424B",
    "text_dezactivat": "#5C6672",
    "principal": "#0B4A8F",
    "principal_apasat": "#083569",
    "principal_text": "#FFFFFF",
    "pericol": "#9E1B1B",
    "pericol_apasat": "#7A1414",
    "pericol_text": "#FFFFFF",
    "succes": "#14602C",
    "succes_apasat": "#0F4A22",
    "succes_text": "#FFFFFF",
    "secundar": "#FFFFFF",
    "secundar_text": "#12314F",
    "bara_goala": "#D7DEE6",
    "bara_plina": "#0B4A8F",
    "verde_fundal": "#DDF3E2",
    "verde_text": "#0B3D1C",
    "galben_fundal": "#FDF1D2",
    "galben_text": "#4A3200",
    "rosu_fundal": "#FBE3E3",
    "rosu_text": "#5C1111",
    "pericol_fundal": "#FBE3E3",
    "zona_text": "#FFFFFF",
    "dezactivat_fundal": "#E2E7EC",
    "dezactivat_text": "#4B5560",
}

#: Culorile modului întunecat (fundal închis, scris deschis la culoare).
#: Toate perechile (fundal, text) trec pragul de contrast al WCAG AA.
_TEMA_INTUNECATA = {
    "fundal": "#15181C",
    "card": "#1E2329",
    "chenar": "#8C99A6",
    "chenar_focus": "#8FC1FF",
    "text": "#F2F5F8",
    "text_secundar": "#D3DAE2",
    "text_dezactivat": "#A9B3BE",
    "principal": "#2F6FC1",
    "principal_apasat": "#26599C",
    "principal_text": "#FFFFFF",
    "pericol": "#B3261E",
    "pericol_apasat": "#8E1D17",
    "pericol_text": "#FFFFFF",
    "pericol_fundal": "#3D1414",
    "succes": "#1E7A3C",
    "succes_apasat": "#16602F",
    "succes_text": "#FFFFFF",
    "secundar": "#2A3037",
    "secundar_text": "#E3E9EF",
    "bara_goala": "#3A424B",
    "bara_plina": "#4C8DD6",
    "verde_fundal": "#123A1E",
    "verde_text": "#B9EFC8",
    "galben_fundal": "#3B3005",
    "galben_text": "#F5E3A3",
    "rosu_fundal": "#3D1414",
    "rosu_text": "#FFC7C7",
    "zona_text": "#1B2026",
    "dezactivat_fundal": "#2A3037",
    "dezactivat_text": "#C2CBD4",
}

#: Modul cerut de utilizator și modul care este aplicat acum.
MODURI = ("windows", "luminos", "intunecat")
_mod_cerut = "windows"
_mod_aplicat = "luminos"


def _reface_perechi() -> None:
    """Perechile de contrast se recalculă pentru culorile de acum."""
    PERECHI_CONTRAST.clear()
    PERECHI_CONTRAST.extend(
        [
            (CULORI.card, CULORI.text, 4.5),
            (CULORI.card, CULORI.text_secundar, 4.5),
            (CULORI.principal, CULORI.principal_text, 4.5),
            (CULORI.fundal, CULORI.text, 4.5),
            (CULORI.verde_fundal, CULORI.verde_text, 4.5),
            (CULORI.galben_fundal, CULORI.galben_text, 4.5),
            (CULORI.rosu_fundal, CULORI.rosu_text, 4.5),
            (CULORI.dezactivat_fundal, CULORI.dezactivat_text, 4.5),
            (CULORI.card, CULORI.chenar, 3.0),
            (CULORI.card, CULORI.chenar_focus, 3.0),
            (CULORI.dezactivat_fundal, CULORI.principal, 3.0),
            (CULORI.pericol, CULORI.pericol_text, 4.5),
            (CULORI.succes, CULORI.succes_text, 4.5),
        ]
    )


def citeste_tema_windows() -> str:
    """Citește din Windows dacă e pe luminos sau pe întunecat („luminos” la necunoscut).

    Se citește **doar** o valoare din registru (fără să se scrie nimic) și, dacă
    nu poate fi citită, programul rămâne pe luminos.
    """
    try:
        import winreg  # type: ignore[import-not-found]
    except Exception:
        return "luminos"
    cale = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cale) as cheie:
            valoare, _tip = winreg.QueryValueEx(cheie, "AppsUseLightTheme")
        return "luminos" if int(valoare) else "intunecat"
    except Exception:
        return "luminos"


def mod_efectiv(mod: str = "") -> str:
    """Ce mod se vede acum: „luminos” sau „întunecat”."""
    ales = (mod or _mod_cerut or "windows").lower()
    if ales == "intunecat":
        return "intunecat"
    if ales == "luminos":
        return "luminos"
    return citeste_tema_windows()


def aplica_tema(mod: str = "windows") -> str:
    """Pune culorile modului cerut și întoarce modul care s-a aplicat.

    Se poate chema oricând: ecranele se refac după aceea (vezi
    ``ui_principal.Aplicatie.reimprospateaza_aspectul``).
    """
    global _mod_cerut, _mod_aplicat
    _mod_cerut = (mod or "windows").lower()
    dorit = mod_efectiv(_mod_cerut)
    culori = _TEMA_INTUNECATA if dorit == "intunecat" else _TEMA_LUMINOASA
    for nume, valoare in culori.items():
        setattr(CULORI, nume, valoare)
    _reface_perechi()
    _mod_aplicat = dorit
    return dorit


def mod_aplicat() -> str:
    """Modul care este pe ecran acum („luminos” sau „întunecat”)."""
    return _mod_aplicat


def si_cu_marirea_scrisului(procent: int) -> bool:
    """Spune dacă mărirea scrisului a fost așezată (se folosește la Setări)."""
    return _marime_scris_ceruta == int(procent or 100)


#: Mărirea scrisului cerută de utilizator (100, 125, 150 sau 200 la sută).
_marime_scris_ceruta = 100


def seteaza_marirea_scrisului(procent: int) -> int:
    """Ține minte mărirea scrisului (se aplică la refacerea ecranelor)."""
    global _marime_scris_ceruta
    try:
        valoare = int(procent or 100)
    except (TypeError, ValueError):
        valoare = 100
    _marime_scris_ceruta = max(80, min(200, valoare))
    return _marime_scris_ceruta


def schimba_marimea_scrisului(delta: int = 0, exact: int | None = None, radacina: tk.Misc | None = None) -> int:
    """Modifică mărirea scrisului (+/- delta sau valoare exactă) și actualizează dinamic fonturile."""
    global _marime_scris_ceruta, _FONTURI
    if exact is not None:
        _marime_scris_ceruta = max(80, min(200, int(exact)))
    else:
        _marime_scris_ceruta = max(80, min(200, _marime_scris_ceruta + delta))

    mare = _marime_scris_ceruta / 100.0
    if _FONTURI is not None:
        try:
            if _FONTURI.baza:
                _FONTURI.baza.configure(size=max(10, round(12 * mare)))
            if _FONTURI.mica:
                _FONTURI.mica.configure(size=max(9, round(11 * mare)))
            if _FONTURI.buton:
                _FONTURI.buton.configure(size=max(11, round(14 * mare)))
            if _FONTURI.buton_secundar:
                _FONTURI.buton_secundar.configure(size=max(10, round(12 * mare)))
            if _FONTURI.titlu:
                _FONTURI.titlu.configure(size=max(14, round(18 * mare)))
            if _FONTURI.subtitlu:
                _FONTURI.subtitlu.configure(size=max(12, round(15 * mare)))
            if _FONTURI.imens:
                _FONTURI.imens.configure(size=max(16, round(22 * mare)))
        except Exception:
            pass
    elif radacina is not None:
        pregateste_fonturi(radacina)
    return _marime_scris_ceruta


# --------------------------------------------------------------------------- fonturi


@dataclass
class Fonturi:
    """Fonturile programului, după scalare (minimum 12 pt / 14 pt / 18 pt)."""

    familie: str = "Segoe UI"
    baza: tkfont.Font | None = None
    mica: tkfont.Font | None = None
    buton: tkfont.Font | None = None
    buton_secundar: tkfont.Font | None = None
    titlu: tkfont.Font | None = None
    subtitlu: tkfont.Font | None = None
    imens: tkfont.Font | None = None


_FONTURI: Fonturi | None = None


def _familie_potrivita(radacina: tk.Misc) -> str:
    try:
        existente = set(tkfont.families(radacina))
    except Exception:
        return "Segoe UI"
    for nume in ("Segoe UI", "Tahoma", "Verdana", "Arial"):
        if nume in existente:
            return nume
    return "TkDefaultFont"


def pregateste_fonturi(radacina: tk.Misc) -> Fonturi:
    """Creează fonturile programului, odată ce fereastra există."""
    global _FONTURI
    familie = _familie_potrivita(radacina)
    mare = _marime_scris_ceruta / 100.0
    _FONTURI = Fonturi(
        familie=familie,
        baza=tkfont.Font(radacina, family=familie, size=max(12, round(12 * mare))),
        mica=tkfont.Font(radacina, family=familie, size=max(11, round(11 * mare))),
        buton=tkfont.Font(radacina, family=familie, size=max(14, round(14 * mare)), weight="bold"),
        buton_secundar=tkfont.Font(radacina, family=familie, size=max(12, round(12 * mare))),
        titlu=tkfont.Font(radacina, family=familie, size=max(18, round(18 * mare)), weight="bold"),
        subtitlu=tkfont.Font(radacina, family=familie, size=max(15, round(15 * mare)), weight="bold"),
        imens=tkfont.Font(radacina, family=familie, size=max(22, round(22 * mare)), weight="bold"),
    )
    return _FONTURI


def fonturi() -> Fonturi:
    """Fonturile pregătite (sau valori de siguranță, înainte de fereastră)."""
    if _FONTURI is None:  # pragma: no cover - se întâmplă doar în teste
        return Fonturi()
    return _FONTURI


def familia() -> str:
    return fonturi().familie


# --------------------------------------------------------------------------- scară globală

#: Spațiul minim dintre butoane, la 100%.
SPATIU = 12
#: Dimensiunile minime cerute pentru butoane, la 100%.
BUTON_PRINCIPAL = (220, 64)
BUTON_SECUNDAR = (44, 44)


def spatiu() -> int:
    return px(SPATIU)


# --------------------------------------------------------------------------- coada interfeței


class CoadaUI:
    """Trimite actualizări din firele de lucru în interfață, prin coadă + ``after``.

    Interfața nu este atinsă niciodată direct din alt fir: lucrătorii pun
    funcții în coadă, iar fereastra le execută în ritmul ei, la fiecare 60 ms.
    """

    def __init__(self, fereastra: tk.Misc, interval: int = 60):
        self.fereastra = fereastra
        self.coada: queue.Queue = queue.Queue()
        self.interval = interval
        self._oprit = threading.Event()
        self._id = None
        self._porneste()

    def _porneste(self) -> None:
        if not self._oprit.is_set():
            self._id = self.fereastra.after(self.interval, self._goleste)

    def _goleste(self) -> None:
        while True:
            try:
                functie, argumente, numite = self.coada.get_nowait()
            except queue.Empty:
                break
            try:
                functie(*argumente, **numite)
            except tk.TclError:
                return
            except Exception as exc:  # nicio eroare din interfață nu închide programul
                jurnal.eroare(f"Eroare în interfață: {type(exc).__name__}: {exc}")
        self._porneste()

    def trimite(self, functie, *argumente, **numite) -> None:
        """Cere ca funcția să fie rulată în firul interfeței."""
        self.coada.put((functie, argumente, numite))

    def opreste(self) -> None:
        self._oprit.set()
        if self._id is not None:
            try:
                self.fereastra.after_cancel(self._id)
            except Exception:
                pass
            self._id = None


# --------------------------------------------------------------------------- ferestre


def seteaza_titlu(fereastra: tk.Misc, parte: str = "") -> None:
    """Pune titlul „Dictare&Transcriere Română – …” pe o fereastră."""
    text = NUME_APLICATIE if not parte else f"{NUME_APLICATIE} – {parte}"
    try:
        fereastra.title(text)
        fereastra.wm_title(text)
    except Exception:
        pass


def centrat(fereastra: tk.Misc, latime: int | None = None, inaltime: int | None = None) -> None:
    """Așază fereastra în mijlocul ecranului (sau al părintelui)."""
    fereastra.update_idletasks()
    l = latime or fereastra.winfo_reqwidth()
    i = inaltime or fereastra.winfo_reqheight()
    try:
        parinte = fereastra.master
        if parinte is not None and parinte.winfo_exists() and parinte.winfo_width() > 1:
            x = parinte.winfo_rootx() + max(0, (parinte.winfo_width() - l) // 2)
            y = parinte.winfo_rooty() + max(0, (parinte.winfo_height() - i) // 3)
        else:
            x = max(0, (fereastra.winfo_screenwidth() - l) // 2)
            y = max(0, (fereastra.winfo_screenheight() - i) // 3)
    except Exception:
        x = y = 60
    fereastra.geometry(f"{l}x{i}+{x}+{y}")


def maxim_ecran(procent: float = 0.9) -> tuple[int, int]:
    """Dimensiunea maximă a unei ferestre, ca procent din ecran."""
    radacina = tk._default_root  # type: ignore[attr-defined]
    latime = radacina.winfo_screenwidth() if radacina else 1280
    inaltime = radacina.winfo_screenheight() if radacina else 800
    return int(latime * procent), int(inaltime * procent)


# --------------------------------------------------------------------------- derulare


class ZonaDerulare(tk.Frame):
    """Zonă cu derulare verticală: nimic nu se taie pe ecrane mici (1024×600).

    Conținutul se pune în ``zona.interior``. Roata mouse-ului derulează doar
    când arătătorul este deasupra zonei.
    """

    def __init__(self, parinte: tk.Misc, latime_minima: int = 0):
        super().__init__(parinte, background=CULORI.fundal)
        self._latime_minima = latime_minima
        self.canvas = tk.Canvas(self, background=CULORI.fundal, highlightthickness=0, bd=0)
        self.bara = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._bara_din_canvas)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bara.pack(side="right", fill="y")
        self.interior = tk.Frame(self.canvas, background=CULORI.fundal)
        self._fereastra = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.interior.bind("<Configure>", self._continut_schimbat)
        self.canvas.bind("<Configure>", self._latime_schimbata)
        for element in (self.canvas, self.interior):
            element.bind("<MouseWheel>", self._roata, add="+")
            element.bind("<Button-4>", self._roata, add="+")
            element.bind("<Button-5>", self._roata, add="+")

    # ------------------------------------------------------------------ ajutoare

    def _bara_din_canvas(self, inceput: str, sfarsit: str) -> None:
        primul, ultimul = float(inceput), float(sfarsit)
        if primul <= 0.0 and ultimul >= 1.0:
            self.bara.pack_forget()
        elif not self.bara.winfo_ismapped():
            self.bara.pack(side="right", fill="y")
        self.bara.set(inceput, sfarsit)

    def _continut_schimbat(self, _eveniment=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _latime_schimbata(self, eveniment) -> None:
        latime = max(int(eveniment.width), px(self._latime_minima))
        self.canvas.itemconfigure(self._fereastra, width=latime)

    def deruleaza_sus(self) -> None:
        try:
            self.canvas.yview_moveto(0.0)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ roata

    def _roata(self, eveniment) -> str | None:
        element = self.winfo_containing(eveniment.x_root, eveniment.y_root)
        if element is None or not self._este_in_zona(element):
            return None
        pas = -1 if getattr(eveniment, "delta", 0) > 0 or getattr(eveniment, "num", 0) == 4 else 1
        self.canvas.yview_scroll(pas, "units")
        return "break"

    def _este_in_zona(self, element: tk.Misc) -> bool:
        try:
            x, y = self.winfo_rootx(), self.winfo_rooty()
            latime, inaltime = self.winfo_width(), self.winfo_height()
            alto_x, alto_y = element.winfo_rootx(), element.winfo_rooty()
        except tk.TclError:
            return False
        return x <= alto_x < x + latime and y <= alto_y < y + inaltime


# --------------------------------------------------------------------------- butoane



def _rotunjeste(canvas, x1, y1, x2, y2, r, fill="", outline="", width=1, tags=()):
    """Deseneaza un dreptunghi cu colturi rotunjite pe un Canvas."""
    r = max(0, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
    items = []
    if r == 0:
        items.append(canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width, tags=tags))
        return items
    # Corp principal
    items.append(canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="", width=0, tags=tags))
    items.append(canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="", width=0, tags=tags))
    # Colțuri (arcuri pieslice)
    items.append(canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, fill=fill, outline="", style="pieslice", tags=tags))
    items.append(canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, fill=fill, outline="", style="pieslice", tags=tags))
    items.append(canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, fill=fill, outline="", style="pieslice", tags=tags))
    items.append(canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, fill=fill, outline="", style="pieslice", tags=tags))
    # Contur (optional)
    if outline and width > 0:
        items.append(canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=tags))
        items.append(canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=tags))
        items.append(canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=tags))
        items.append(canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=tags))
        items.append(canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, fill="", outline=outline, width=width, style="arc", tags=tags))
        items.append(canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, fill="", outline=outline, width=width, style="arc", tags=tags))
        items.append(canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, fill="", outline=outline, width=width, style="arc", tags=tags))
        items.append(canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, fill="", outline=outline, width=width, style="arc", tags=tags))

    return items


def _interpoleaza_culoare(c1, c2, t):
    """Interpoleaza liniar intre doua culori hex."""
    c1 = c1.lstrip("#")
    c2 = c2.lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"



class Buton(tk.Canvas):
    """Buton propriu, cu colturi rotunjite si inel de focus vizibil.

    Construit pe Canvas, ca sa poata avea colturi rotunjite (cerinta de
    aspect). Pastreaza aceeasi interfata ca versiunea anterioara, ca sa nu
    se strice codul care il foloseste.
    """

    def __init__(
        self,
        parinte: tk.Misc,
        text: str,
        comanda=None,
        fel: str = "secundar",
        latime: int | None = None,
        inaltime: int | None = None,
        scurtatura: str = "",
        ancora: str = "center",
        imagine: str | None = None,
    ):
        latime = latime or (BUTON_PRINCIPAL[0] if fel in ("principal", "pericol", "succes") else BUTON_SECUNDAR[0])
        inaltime = inaltime or (BUTON_PRINCIPAL[1] if fel in ("principal", "pericol", "succes") else 48)
        if not scurtatura:
            text_aratat = text
        else:
            text_aratat = f"{text}\n({scurtatura})" if "\n" not in text else text
        px_l = px(latime)
        px_i = px(inaltime)
        super().__init__(
            parinte,
            width=px_l,
            height=px_i,
            highlightthickness=0,
            bd=0,
            background=CULORI.fundal,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._comanda = comanda
        self._fel = fel
        self._activ = True
        self._inaltime = inaltime
        self._latime = latime
        self._text_original = text
        self._text_aratat = text_aratat
        self._ancora = ancora
        self._stare = "normal"  # normal, hover, pressed, focus
        self._culoare_curenta = None
        self._anima_dupa = None
        self._raza = px(10)
        self._elemente = []
        self._puls = False
        self._puls_val = 0.0
        self._puls_dupa = None

        culori_fel = self._culori_fel(fel)
        self.eticheta = tk.Label(
            self,
            text=text_aratat,
            font=fonturi().buton if fel in ("principal", "pericol", "succes") else fonturi().buton_secundar,
            background=culori_fel[0],
            foreground=culori_fel[1],
            justify="center" if ancora == "center" else "left",
            anchor=ancora,
            wraplength=px(latime - 16) if latime < 420 else px(360),
        )
        if imagine:
            try:
                self.eticheta.configure(image=imagine, compound="left")
            except Exception:
                pass

        self._label_window = self.create_window(px_l // 2, px_i // 2, window=self.eticheta, anchor="center")

        self._deseneaza()

        for element in (self, self.eticheta):
            element.bind("<Button-1>", self._apasa, add="+")
            element.bind("<Enter>", self._intra, add="+")
            element.bind("<Leave>", self._iese, add="+")
            element.bind("<FocusIn>", self._focus, add="+")
            element.bind("<FocusOut>", self._fara_focus, add="+")
            element.bind("<Return>", self._din_tastatura, add="+")
            element.bind("<space>", self._din_tastatura, add="+")
            element.bind("<ButtonRelease-1>", self._ridica, add="+")

    def _deseneaza(self):
        for item in self._elemente:
            self.delete(item)
        self._elemente = []

        w = px(self._latime)
        h = px(self._inaltime)
        r = self._raza

        if not self._activ:
            fundal, text = self._culori_dezactivat()
        else:
            fundal, text = self._culori_fel(self._fel)

        if self._stare == "pressed":
            fundal = self._culoare_apasata(self._fel)
        elif self._stare == "hover":
            fundal = self._culoare_hover(self._fel)
        elif self._puls:
            import math
            t = (math.sin(self._puls_val) + 1) / 2
            fundal = _interpoleaza_culoare(fundal, self._culoare_hover(self._fel), t * 0.3)

        items = _rotunjeste(self, 2, 2, w - 2, h - 2, r, fill=fundal)
        self._elemente.extend(items)

        if self._stare == "focus":
            ring_items = _rotunjeste(self, 0, 0, w, h, r + 2, fill="", outline=CULORI.chenar_focus, width=px(3))
            self._elemente.extend(ring_items)

        self.eticheta.configure(background=fundal, foreground=text)

        if self._puls:
            self._puls_val += 0.15
            self._puls_dupa = self.after(30, self._deseneaza)

    def _culoare_hover(self, fel):
        perechi = {
            "principal": "#1A5F9E",
            "pericol": "#B32525",
            "succes": "#1E7A3A",
        }
        return perechi.get(fel, "#E8ECF2")

    def pulseaza(self, activ=True):
        """Pornește/oprește animația de puls (pentru dictare)."""
        self._puls = activ
        if activ:
            self._puls_val = 0.0
            self._deseneaza()
        else:
            if self._puls_dupa:
                self.after_cancel(self._puls_dupa)
                self._puls_dupa = None
            self._deseneaza()

    def _apasa(self, _eveniment=None):
        if not self._activ:
            return
        self._stare = "pressed"
        self._deseneaza()
        try:
            self.focus_set()
        except Exception:
            pass

    def _ridica(self, _eveniment=None):
        if not self._activ:
            return
        self._stare = "hover" if self._mouse_peste() else "normal"
        self._deseneaza()
        if self._comanda:
            self._comanda()

    def _mouse_peste(self):
        try:
            x = self.winfo_pointerx() - self.winfo_rootx()
            y = self.winfo_pointery() - self.winfo_rooty()
            return 0 <= x <= px(self._latime) and 0 <= y <= px(self._inaltime)
        except Exception:
            return False

    def _din_tastatura(self, _eveniment=None):
        if self._activ and self._comanda:
            self._stare = "pressed"
            self._deseneaza()
            self.after(100, self._restaureaza_dupa_tastatura)
            self._comanda()
        return "break"

    def _restaureaza_dupa_tastatura(self):
        self._stare = "normal"
        self._deseneaza()

    def _intra(self, _eveniment=None):
        if self._activ:
            self._stare = "hover"
            self._deseneaza()

    def _iese(self, _eveniment=None):
        if self._activ:
            self._stare = "normal"
            self._deseneaza()

    def _focus(self, _eveniment=None):
        if self._activ:
            self._stare = "focus"
            self._deseneaza()

    def _fara_focus(self, _eveniment=None):
        if self._activ:
            self._stare = "normal"
            self._deseneaza()

    def activeaza(self, activ: bool):
        self._activ = bool(activ)
        if not self._activ:
            self.configure(cursor="")
        else:
            self.configure(cursor="hand2")
        self.configure(takefocus=self._activ)
        self._deseneaza()

    def este_activ(self) -> bool:
        return self._activ

    def seteaza_text(self, text: str):
        self._text_original = text
        self.eticheta.configure(text=text)

    def seteaza_fel(self, fel: str):
        self._fel = fel
        self.eticheta.configure(
            font=fonturi().buton if fel in ("principal", "pericol", "succes") else fonturi().buton_secundar,
        )
        self._deseneaza()

    # ------------------------------------------------------------------ culori

    @staticmethod
    def _culori_fel(fel: str) -> tuple[str, str]:
        perechi = {
            "principal": (CULORI.principal, CULORI.principal_text),
            "pericol": (CULORI.pericol, CULORI.pericol_text),
            "succes": (CULORI.succes, CULORI.succes_text),
        }
        return perechi.get(fel, (CULORI.secundar, CULORI.secundar_text))

    @staticmethod
    def _culoare_apasata(fel: str) -> str:
        perechi = {
            "principal": CULORI.principal_apasat,
            "pericol": CULORI.pericol_apasat,
            "succes": CULORI.succes_apasat,
        }
        return perechi.get(fel, CULORI.secundar)

    def _culori_dezactivat(self) -> tuple[str, str]:
        return CULORI.dezactivat_fundal, CULORI.dezactivat_text


class ButonScurtatura(Buton):
    """Buton care scrie scurtătura și pe el (cerință de accesibilitate)."""


# --------------------------------------------------------------------------- etichete


def eticheta(
    parinte: tk.Misc,
    text: str,
    fel: str = "baza",
    latime_bucati: int | None = None,
    fundal: str | None = None,
    ancora: str = "w",
) -> tk.Label:
    """Creează o etichetă cu textul care se rupe pe rânduri, fără să se taie."""
    f = fonturi()
    tip = {
        "baza": f.baza or ("Segoe UI", 12),
        "mica": f.mica or ("Segoe UI", 11),
        "titlu": f.titlu or ("Segoe UI", 18, "bold"),
        "subtitlu": f.subtitlu or ("Segoe UI", 15, "bold"),
        "imens": f.imens or ("Segoe UI", 22, "bold"),
        "buton": f.buton or ("Segoe UI", 14, "bold"),
    }.get(fel, f.baza or ("Segoe UI", 12))
    culoare = {
        "titlu": CULORI.text,
        "subtitlu": CULORI.text,
        "imens": CULORI.text,
    }.get(fel, CULORI.text)
    eticheta_noua = tk.Label(
        parinte,
        text=text,
        font=tip,
        background=fundal or CULORI.card,
        foreground=culoare,
        justify="left",
        anchor=ancora,
    )
    if latime_bucati:
        eticheta_noua.configure(wraplength=px(latime_bucati))
    return eticheta_noua


def card(parinte: tk.Misc, titlu: str = "") -> tuple[tk.Frame, tk.Frame]:
    """Un card alb cu chenar vizibil si colturi rotunjite; intoarce (cardul, locul unde pui continut)."""
    exterior = tk.Canvas(
        parinte,
        background=CULORI.fundal,
        highlightthickness=0,
        bd=0,
    )
    exterior.pack_propagate(False)
    raza = px(12)

    def _redesenat(_eveniment=None):
        try:
            w = exterior.winfo_width()
            h = exterior.winfo_height()
            if w <= 1 or h <= 1:
                return
            exterior.delete("card")
            _rotunjeste(exterior, 2, 2, w - 2, h - 2, raza, fill=CULORI.card, outline=CULORI.chenar, width=px(2), tags="card")
        except Exception:
            pass

    interior = tk.Frame(exterior, background=CULORI.card)

    def _resize(_eveniment=None):
        try:
            w = exterior.winfo_width()
            h = exterior.winfo_height()
            if w <= 1 or h <= 1:
                return
            exterior.coords(interior_window, px(14), px(12))
            exterior.itemconfigure(interior_window, width=max(1, w - px(28)), height=max(1, h - px(24)))
            _redesenat()
        except Exception:
            pass

    interior_window = exterior.create_window(px(14), px(12), window=interior, anchor="nw")
    exterior.bind("<Configure>", _resize)

    if titlu:
        eticheta(interior, titlu, "subtitlu").pack(anchor="w")

    exterior.configure(height=px(120))

    return exterior, interior

# --------------------------------------------------------------------------- bare și stare


class BaraProgres(tk.Canvas):
    """Bară de progres simplă, desenată manual (se vede bine la orice scaling)."""

    def __init__(self, parinte: tk.Misc, latime: int = 520, inaltime: int = 26):
        super().__init__(
            parinte,
            width=px(latime),
            height=px(inaltime),
            background=CULORI.bara_goala,
            highlightthickness=px(1),
            highlightbackground=CULORI.chenar,
            bd=0,
        )
        self._latime = latime
        self._inaltime = inaltime
        self._valoare = 0.0
        self._bucata = None

    def seteaza(self, fractiune: float) -> None:
        """Setează progresul (0..1) și redesenează bara."""
        self._valoare = max(0.0, min(1.0, float(fractiune)))
        self.update_idletasks()
        if self._bucata is not None:
            self.delete(self._bucata)
        latime_totala = self.winfo_width()
        if latime_totala <= 1:  # încă nemăsurată: folosim lățimea cerută
            latime_totala = px(self._latime)
        umplut = int(latime_totala * self._valoare)
        if umplut > 0:
            self._bucata = self.create_rectangle(
                0, 0, umplut, px(self._inaltime), fill=CULORI.bara_plina, width=0
            )

    def valoare(self) -> float:
        return self._valoare


class LinieStare(tk.Frame):
    """Linia de stare: pictogramă + cuvânt + propoziție scurtă (niciodată jurnal)."""

    def __init__(self, parinte: tk.Misc):
        super().__init__(parinte, background=CULORI.fundal)
        self.pictograma = tk.Label(
            self,
            text="●",
            font=fonturi().subtitlu or ("Segoe UI", 15, "bold"),
            background=CULORI.fundal,
            foreground=CULORI.text,
        )
        self.pictograma.pack(side="left")
        self.cuvant = tk.Label(
            self,
            text="Gata",
            font=fonturi().buton or ("Segoe UI", 14, "bold"),
            background=CULORI.fundal,
            foreground=CULORI.text,
        )
        self.cuvant.pack(side="left", padx=(px(6), px(10)))
        self.text = tk.Label(
            self,
            text="",
            font=fonturi().baza or ("Segoe UI", 12),
            background=CULORI.fundal,
            foreground=CULORI.text,
            justify="left",
            anchor="w",
            wraplength=px(760),
        )
        self.text.pack(side="left", fill="x", expand=True)

    def arata(self, cuvant: str, text: str, fel: str = "normal", pictograma: str = "") -> None:
        """Schimbă starea afișată (cuvântul și pictograma spun starea, nu doar culoarea)."""
        perechi = {
            "normal": ("●", CULORI.text),
            "bine": ("✔", CULORI.verde_text),
            "atentie": ("!", CULORI.galben_text),
            "problema": ("✘", CULORI.rosu_text),
            "lucru": ("⏳", CULORI.text),
        }
        semn, culoare = perechi.get(fel, perechi["normal"])
        self.pictograma.configure(text=pictograma or semn, foreground=culoare)
        self.cuvant.configure(text=cuvant, foreground=culoare)
        self.text.configure(text=text, foreground=culoare)


class Banner(tk.Frame):
    """Banner colorat cu pictogramă și cuvânt (starea nu se arată doar prin culoare)."""

    def __init__(self, parinte: tk.Misc, fel: str = "bine"):
        perechi = {
            "bine": (CULORI.verde_fundal, CULORI.verde_text, "✔"),
            "atentie": (CULORI.galben_fundal, CULORI.galben_text, "!"),
            "problema": (CULORI.rosu_fundal, CULORI.rosu_text, "✘"),
        }
        fundal, culoare_text, semn = perechi.get(fel, perechi["bine"])
        super().__init__(
            parinte,
            background=fundal,
            highlightthickness=px(1),
            highlightbackground=culoare_text,
            bd=0,
        )
        self.eticheta = tk.Label(
            self,
            text=f"{semn}  ",
            font=fonturi().subtitlu or ("Segoe UI", 15, "bold"),
            background=fundal,
            foreground=culoare_text,
        )
        self.eticheta.pack(side="left", padx=(px(10), 0))
        self.text = tk.Label(
            self,
            text="",
            font=fonturi().buton or ("Segoe UI", 14, "bold"),
            background=fundal,
            foreground=culoare_text,
            justify="left",
            anchor="w",
            wraplength=px(700),
        )
        self.text.pack(side="left", fill="x", expand=True, padx=px(10), pady=px(8))

    def arata(self, text: str) -> None:
        self.text.configure(text=text)


# --------------------------------------------------------------------------- dialoguri


class _Dialog(tk.Toplevel):
    """Fereastră proprie de dialog, cu butoane în română și focus clar."""

    def __init__(
        self,
        parinte: tk.Misc,
        titlu: str,
        text: str,
        butoane: list[tuple[str, str]],
        implicit: int = 0,
        anulare: int | None = None,
        detalii: str = "",
        latime: int = 620,
        pictograma: str = "",
    ):
        super().__init__(parinte)
        seteaza_titlu(self, titlu)
        self.configure(background=CULORI.fundal)
        self.resizable(True, True)
        self.transient(parinte)
        self.protocol("WM_DELETE_WINDOW", lambda: self._inchide(self._anulare))
        self.rezultat: int | None = None
        self._anulare = anulare if anulare is not None else len(butoane) - 1

        cadru = tk.Frame(self, background=CULORI.fundal)
        cadru.pack(fill="both", expand=True, padx=px(18), pady=px(16))

        if pictograma:
            tk.Label(
                cadru,
                text=pictograma,
                font=fonturi().imens or ("Segoe UI", 22, "bold"),
                background=CULORI.fundal,
                foreground=CULORI.principal,
            ).pack(anchor="w")

        self.corp = tk.Message(
            cadru,
            text=text,
            width=px(latime - 40),
            font=fonturi().baza or ("Segoe UI", 12),
            background=CULORI.fundal,
            foreground=CULORI.text,
            justify="left",
            anchor="w",
        )
        self.corp.pack(anchor="w", fill="x")

        self._detalii_text = detalii
        self._detalii_aratate = False
        self.buton_detalii: Buton | None = None
        if detalii:
            self.buton_detalii = Buton(
                cadru,
                "Detalii pentru cineva care se pricepe",
                self._comuta_detalii,
                fel="secundar",
                latime=320,
                inaltime=44,
            )
            self.buton_detalii.pack(anchor="w", pady=(px(10), 0))
            self.zona_detalii = tk.Text(
                cadru,
                height=6,
                width=70,
                font=fonturi().mica or ("Segoe UI", 11),
                background=CULORI.zona_text,
                foreground=CULORI.text,
                wrap="word",
            )
            self.zona_detalii.insert("1.0", detalii)
            self.zona_detalii.configure(state="disabled")

        rand = tk.Frame(cadru, background=CULORI.fundal)
        rand.pack(anchor="e", pady=(px(16), 0))
        self.butoane: list[Buton] = []
        for index, (eticheta_buton, fel) in enumerate(butoane):
            buton = Buton(
                rand,
                eticheta_buton,
                lambda i=index: self._inchide(i),
                fel=fel,
                latime=BUTON_PRINCIPAL[0] if fel == "principal" else 190,
                inaltime=BUTON_PRINCIPAL[1] if fel == "principal" else 52,
            )
            buton.pack(side="left", padx=px(SPATIU / 2))
            self.butoane.append(buton)

        self.bind("<Escape>", lambda _e: self._inchide(self._anulare))
        self.bind("<Return>", lambda _e: self._inchide(implicit))
        self.update_idletasks()
        centrat(self, self.winfo_reqwidth(), self.winfo_reqheight())
        self.grab_set()
        try:
            self.butoane[implicit].focus_set()
        except Exception:
            pass
        self.wait_window(self)

    def _comuta_detalii(self) -> None:
        self._detalii_aratate = not self._detalii_aratate
        if self._detalii_aratate:
            self.zona_detalii.pack(anchor="w", fill="x", pady=(px(8), 0))
            self.buton_detalii.seteaza_text("Ascunde detaliile tehnice")
        else:
            self.zona_detalii.pack_forget()
            self.buton_detalii.seteaza_text("Detalii pentru cineva care se pricepe")
        self.update_idletasks()

    def _inchide(self, index: int | None) -> None:
        self.rezultat = index
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


def dialog(
    parinte: tk.Misc,
    titlu: str,
    text: str,
    butoane: list[tuple[str, str]],
    implicit: int = 0,
    anulare: int | None = None,
    detalii: str = "",
    pictograma: str = "",
    latime: int = 620,
) -> int | None:
    """Dialog propriu, cu butoane în română. Întoarce numărul butonului apăsat."""
    fereastra = _Dialog(
        parinte,
        titlu,
        text,
        butoane,
        implicit=implicit,
        anulare=anulare,
        detalii=detalii,
        pictograma=pictograma,
        latime=latime,
    )
    return fereastra.rezultat


def intreaba(parinte: tk.Misc, titlu: str, text: str, da: str = "Da", nu: str = "Nu") -> bool:
    """Întrebare simplă, cu „Da”/„Nu”, în română."""
    rezultat = dialog(
        parinte,
        titlu,
        text,
        [(da, "principal"), (nu, "secundar")],
        implicit=0,
        anulare=1,
    )
    return rezultat == 0


def anunta(parinte: tk.Misc, titlu: str, text: str, detalii: str = "") -> None:
    """Mesaj simplu, cu un singur buton „Am înțeles”."""
    dialog(parinte, titlu, text, [("Am înțeles", "principal")], detalii=detalii)


def dialog_eroare(parinte: tk.Misc, eroare, la_actiune=None) -> None:
    """Arată o eroare în trei părți, cu buton de acțiune și detalii închise.

    Textul tehnic nu apare niciodată în mesaj: el stă doar sub butonul
    „Detalii pentru cineva care se pricepe”, care este închis implicit.
    """
    actiuni = list(getattr(eroare, "actiuni", []) or [])
    if not actiuni:
        actiuni = []
    butoane: list[tuple[str, str]] = []
    for index, actiune in enumerate(actiuni):
        butoane.append((actiune.eticheta, "principal" if index == 0 else "secundar"))
    butoane.append(("Închide", "secundar"))
    rezultat = dialog(
        parinte,
        "A apărut o problemă",
        eroare.text_complet(),
        butoane,
        implicit=0,
        anulare=len(butoane) - 1,
        detalii=getattr(eroare, "detalii", ""),
        pictograma="!",
        latime=660,
    )
    if rezultat is None or rezultat >= len(actiuni) or la_actiune is None:
        return
    try:
        la_actiune(actiuni[rezultat].fel)
    except Exception as exc:
        jurnal.eroare(f"Acțiunea din dialogul de eroare a eșuat: {exc}")


# --------------------------------------------------------------------------- alegerea fișierului


class _AlegeFisier(tk.Toplevel):
    """Dialog propriu de alegere a unui fișier audio, în română."""

    def __init__(
        self,
        parinte: tk.Misc,
        titlu: str = "Alege fișierul audio",
    extensii: tuple[str, ...] = FORMATE_AUDIO,
        folder: Path | None = None,
    ):
        super().__init__(parinte)
        seteaza_titlu(self, titlu)
        self.configure(background=CULORI.fundal)
        self.transient(parinte)
        self.rezultat: Path | None = None
        self.extensii = tuple(extensii)
        self.folder = Path(folder) if folder else cai_documente()

        cadru = tk.Frame(self, background=CULORI.fundal)
        cadru.pack(fill="both", expand=True, padx=px(14), pady=px(12))

        eticheta(cadru, "Unde te uiți:", "subtitlu").pack(anchor="w")

        rand_scurtaturi = tk.Frame(cadru, background=CULORI.fundal)
        rand_scurtaturi.pack(anchor="w", pady=(px(6), px(8)))
        for nume, cale in self._scurtaturi():
            Buton(
                rand_scurtaturi,
                nume,
                lambda c=cale: self._mergi(c),
                latime=150,
                inaltime=44,
            ).pack(side="left", padx=(0, px(SPATIU)))
        buton_mai_sus = Buton(rand_scurtaturi, "Un nivel mai sus", self._mai_sus, latime=180, inaltime=44)
        buton_mai_sus.pack(side="left")

        rand_cale = tk.Frame(cadru, background=CULORI.fundal)
        rand_cale.pack(fill="x")
        self.camp_cale = tk.Entry(
            rand_cale,
            font=fonturi().baza or ("Segoe UI", 12),
            background=CULORI.zona_text,
            foreground=CULORI.text,
            relief="solid",
            bd=1,
        )
        self.camp_cale.pack(side="left", fill="x", expand=True, ipady=px(6))
        Buton(rand_cale, "Deschide", self._deschide_scris, latime=130, inaltime=44).pack(
            side="left", padx=(px(SPATIU), 0)
        )

        eticheta(cadru, "Fi?iere audio/video (mp3, wav, m4a, ogg, flac, opus, webm, mp4, aac, wma)", "mica").pack(
            anchor="w", pady=(px(10), px(4))
        )
        cadru_lista = tk.Frame(cadru, background=CULORI.card, highlightthickness=px(1), highlightbackground=CULORI.chenar)
        cadru_lista.pack(fill="both", expand=True)
        bara = tk.Scrollbar(cadru_lista)
        bara.pack(side="right", fill="y")
        self.lista = tk.Listbox(
            cadru_lista,
            font=fonturi().baza or ("Segoe UI", 12),
            background=CULORI.zona_text,
            foreground=CULORI.text,
            yscrollcommand=bara.set,
            activestyle="none",
            exportselection=False,
            height=12,
        )
        self.lista.pack(side="left", fill="both", expand=True)
        bara.configure(command=self.lista.yview)
        self.lista.bind("<Double-Button-1>", lambda _e: self._alege_selectat())

        rand_butoane = tk.Frame(cadru, background=CULORI.fundal)
        rand_butoane.pack(anchor="e", pady=(px(12), 0))
        self.buton_alege = Buton(
            rand_butoane, "Alege", self._alege_selectat, fel="principal", latime=BUTON_PRINCIPAL[0], inaltime=BUTON_PRINCIPAL[1]
        )
        self.buton_alege.pack(side="left", padx=(0, px(SPATIU)))
        Buton(rand_butoane, "Renunță", self._renunta, latime=190, inaltime=52).pack(side="left")

        self.bind("<Escape>", lambda _e: self._renunta())
        self.bind("<Return>", lambda _e: self._alege_selectat())
        self._mergi(self.folder)
        self.update_idletasks()
        centrat(self, max(760, px(760)), max(560, px(620)))
        self.grab_set()
        try:
            self.buton_alege.focus_set()
        except Exception:
            pass
        self.wait_window(self)

    # ------------------------------------------------------------------ ajutoare

    def _scurtaturi(self) -> list[tuple[str, Path]]:
        """Scurtăturile de sus. Folderele se cer de la Windows, nu se presupun."""
        from . import cai

        lista = [
            ("Documente", cai.director_documente()),
            ("Unde salvez", cai.director_iesiri()),
            ("Desktop", cai.folder_desktop_windows()),
            ("Descărcări", cai.folder_cunoscut("{374DE290-123F-4565-9164-39C4925E467B}")),
            ("Muzică", cai.folder_cunoscut("{4BD8D571-6D19-48D3-BE97-422220080E43}")),
            ("Videoclipuri", cai.folder_cunoscut("{18989B1D-99B5-455B-841C-AB7C74E4DDFC}")),
        ]
        rezultat: list[tuple[str, Path]] = []
        for nume, cale in lista:
            if cale and Path(cale).exists():
                rezultat.append((nume, Path(cale)))
        return rezultat

    def _mergi(self, cale: Path) -> None:
        if not cale.exists():
            return
        self.folder = cale
        self.camp_cale.delete(0, "end")
        self.camp_cale.insert(0, str(cale))
        self.lista.delete(0, "end")
        try:
            elemente = sorted(
                cale.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError:
            return
        for element in elemente:
            if element.is_dir():
                self.lista.insert("end", f"[folder] {element.name}")
            elif element.suffix.lower() in self.extensii:
                self.lista.insert("end", element.name)

    def _mai_sus(self) -> None:
        parinte = self.folder.parent
        if parinte != self.folder:
            self._mergi(parinte)

    def _cale_selectata(self) -> Path | None:
        selectie = self.lista.curselection()
        if not selectie:
            return None
        nume = self.lista.get(selectie[0])
        if nume.startswith("[folder] "):
            return self.folder / nume[len("[folder] ") :]
        return self.folder / nume

    def _deschide_scris(self) -> None:
        cale = Path(self.camp_cale.get().strip())
        if cale.is_dir():
            self._mergi(cale)
        elif cale.is_file():
            self._termina(cale)

    def _alege_selectat(self) -> None:
        cale = self._cale_selectata()
        if cale is None:
            return
        if cale.is_dir():
            self._mergi(cale)
            return
        self._termina(cale)

    def _termina(self, cale: Path) -> None:
        self.rezultat = cale
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _renunta(self) -> None:
        self.rezultat = None
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


def cai_documente() -> Path:
    """Folderul „Documente” al utilizatorului (cerut de la Windows)."""
    from . import cai

    return cai.director_documente()


def alege_fisier_audio(
    parinte: tk.Misc,
    folder: Path | None = None,
    titlu: str = "Alege fișierul audio",
) -> Path | None:
    """Alege un fișier audio cu dialogul propriu, în română."""
    fereastra = _AlegeFisier(parinte, titlu=titlu, folder=folder)
    return fereastra.rezultat


class _AlegeFolder(tk.Toplevel):
    """Dialog propriu de alegere a unui folder, în română (fără ``filedialog``)."""

    def __init__(self, parinte: tk.Misc, titlu: str = "Alege folderul", initial: Path | None = None):
        super().__init__(parinte)
        seteaza_titlu(self, titlu)
        self.configure(background=CULORI.fundal)
        self.transient(parinte)
        self.rezultat: Path | None = None
        self.folder = Path(initial) if initial else cai_documente()

        cadru = tk.Frame(self, background=CULORI.fundal)
        cadru.pack(fill="both", expand=True, padx=px(16), pady=px(14))
        eticheta(cadru, "Unde pui fișierele programului?", "subtitlu").pack(anchor="w")
        eticheta(
            cadru,
            "Se aleg foldere de pe acest calculator. Fișierele rămân la tine; nimic nu pleacă pe internet.",
            "baza",
            latime_bucati=700,
        ).pack(anchor="w", pady=(px(4), px(8)))

        rand_scurtaturi = tk.Frame(cadru, background=CULORI.fundal)
        rand_scurtaturi.pack(anchor="w", pady=(0, px(8)))
        for nume, cale in self._scurtaturi():
            Buton(rand_scurtaturi, nume, lambda c=cale: self._mergi(c), latime=170, inaltime=48).pack(
                side="left", padx=(0, px(SPATIU))
            )
        Buton(rand_scurtaturi, "Un nivel mai sus", self._mai_sus, latime=200, inaltime=48).pack(side="left")

        rand_cale = tk.Frame(cadru, background=CULORI.fundal)
        rand_cale.pack(fill="x")
        self.camp_cale = tk.Entry(
            rand_cale,
            font=fonturi().baza or ("Segoe UI", 12),
            background=CULORI.zona_text,
            foreground=CULORI.text,
            relief="solid",
            bd=1,
        )
        self.camp_cale.pack(side="left", fill="x", expand=True, ipady=px(6))
        Buton(rand_cale, "Deschide", self._deschide_scris, latime=140, inaltime=48).pack(
            side="left", padx=(px(SPATIU), 0)
        )

        eticheta(cadru, "Foldere din interior:", "mica").pack(anchor="w", pady=(px(10), px(4)))
        cadru_lista = tk.Frame(
            cadru, background=CULORI.card, highlightthickness=px(1), highlightbackground=CULORI.chenar
        )
        cadru_lista.pack(fill="both", expand=True)
        bara = tk.Scrollbar(cadru_lista)
        bara.pack(side="right", fill="y")
        self.lista = tk.Listbox(
            cadru_lista,
            font=fonturi().baza or ("Segoe UI", 12),
            background=CULORI.zona_text,
            foreground=CULORI.text,
            yscrollcommand=bara.set,
            activestyle="none",
            exportselection=False,
            height=12,
        )
        self.lista.pack(side="left", fill="both", expand=True)
        bara.configure(command=self.lista.yview)
        self.lista.bind("<Double-Button-1>", lambda _e: self._intra_selectat())

        rand_butoane = tk.Frame(cadru, background=CULORI.fundal)
        rand_butoane.pack(anchor="e", pady=(px(12), 0))
        self.buton_alege = Buton(
            rand_butoane,
            "Alege acest folder",
            self._alege_folderul_curent,
            fel="principal",
            latime=BUTON_PRINCIPAL[0],
            inaltime=BUTON_PRINCIPAL[1],
        )
        self.buton_alege.pack(side="left", padx=(0, px(SPATIU)))
        Buton(rand_butoane, "Renunță", self._renunta, latime=200, inaltime=56).pack(side="left")

        self.bind("<Escape>", lambda _e: self._renunta())
        self.bind("<Return>", lambda _e: self._alege_folderul_curent())
        self._mergi(self.folder)
        self.update_idletasks()
        centrat(self, max(780, px(780)), max(600, px(640)))
        self.grab_set()
        self.wait_window(self)

    def _scurtaturi(self) -> list[tuple[str, Path]]:
        from . import cai

        lista = [
            ("Documente", cai.director_documente()),
            ("Desktop", cai.folder_desktop_windows()),
            ("Descărcări", cai.folder_cunoscut("{374DE290-123F-4565-9164-39C4925E467B}")),
        ]
        return [(nume, Path(cale)) for nume, cale in lista if cale and Path(cale).exists()]

    def _mergi(self, cale: Path) -> None:
        cale = Path(cale)
        if not cale.is_dir():
            return
        self.folder = cale
        self.camp_cale.delete(0, "end")
        self.camp_cale.insert(0, str(cale))
        self.lista.delete(0, "end")
        try:
            for element in sorted(cale.iterdir(), key=lambda p: p.name.lower()):
                if element.is_dir():
                    self.lista.insert("end", element.name)
        except OSError as exc:
            jurnal.atentionare(f"Folderul {cale} nu a putut fi citit: {exc}")

    def _mai_sus(self) -> None:
        parinte = self.folder.parent
        if parinte != self.folder:
            self._mergi(parinte)

    def _deschide_scris(self) -> None:
        self._mergi(Path(self.camp_cale.get().strip()))

    def _intra_selectat(self) -> None:
        selectie = self.lista.curselection()
        if selectie:
            self._mergi(self.folder / self.lista.get(selectie[0]))

    def _alege_folderul_curent(self) -> None:
        self.rezultat = self.folder
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _renunta(self) -> None:
        self.rezultat = None
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


def alege_folder(
    parinte: tk.Misc, titlu: str = "Alege folderul", initial: Path | None = None
) -> Path | None:
    """Alege un folder cu dialogul propriu, în română."""
    return _AlegeFolder(parinte, titlu=titlu, initial=initial).rezultat


# --------------------------------------------------------------------------- ajutor


def buton_ajutor(parinte: tk.Misc, cheie: str = "principal", latime: int = 150) -> Buton:
    """Butonul „? Ajutor”, prezent pe fiecare ecran."""

    def deschide() -> None:
        from . import ui_ajutor

        try:
            ui_ajutor.deschide(parinte, cheie)
        except Exception as exc:
            jurnal.eroare(f"Ajutorul nu s-a putut deschide: {exc}")
            anunta(parinte, "Ajutor", "Ajutorul nu s-a putut deschide acum. Încearcă din nou.")

    return Buton(parinte, "? Ajutor", deschide, latime=latime, inaltime=48, scurtatura="F1")


def seteaza_scurtatura(radacina: tk.Misc, secventa: str, functie) -> None:
    """Leagă o scurtătură de tastatură (Ctrl+O, F1 etc.)."""
    try:
        radacina.bind_all(secventa, lambda _e: (functie(), "break")[1])
    except Exception:
        pass


def pictograma_check() -> str:
    return "✔"
