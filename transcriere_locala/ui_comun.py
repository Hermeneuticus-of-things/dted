"""Elemente comune pentru ferestrele programului: temă, fonturi, mesaje."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

importi = ("Segoe UI", "Arial", "Tahoma")


def alege_font() -> str:
    """Alege un font disponibil, ca să arate bine pe orice Windows."""
    try:
        import tkinter.font as tkfont

        disponibile = set(tkfont.families())
        for nume in importi:
            if nume in disponibile:
                return nume
    except Exception:
        pass
    return "TkDefaultFont"


def pregateste_fereastra(fereastra: tk.Misc, titlu: str) -> str:
    """Setează titlul, scalarea și o dimensiune potrivită ecranului."""
    fereastra.title(titlu)
    font = alege_font()
    try:
        # Scalare mai mare pe ecrane cu rezoluție mare, fără a depăși limitele.
        scara = fereastra.winfo_fpixels("1i") / 96.0
        if scara > 1.1:
            fereastra.tk.call("tk", "scaling", min(2.0, scara))
    except Exception:
        pass

    latime_ecran = fereastra.winfo_screenwidth()
    inaltime_ecran = fereastra.winfo_screenheight()
    # Ferestrele mici (laptop vechi) primesc o fereastră mai mică, dar utilizabilă.
    latime = min(1020, max(720, int(latime_ecran * 0.78)))
    inaltime = min(760, max(560, int(inaltime_ecran * 0.80)))
    x = max(0, (latime_ecran - latime) // 2)
    y = max(0, (inaltime_ecran - inaltime) // 3)
    fereastra.geometry(f"{latime}x{inaltime}+{x}+{y}")
    fereastra.minsize(min(640, latime), min(480, inaltime))

    style = ttk.Style(fereastra)
    for tema in ("vista", "winnative", "clam", "default"):
        if tema in style.theme_names():
            try:
                style.theme_use(tema)
                break
            except tk.TclError:
                continue

    style.configure(".", font=(font, 10))
    style.configure("Titlu.TLabel", font=(font, 20, "bold"))
    style.configure("Subtitlu.TLabel", font=(font, 12))
    style.configure("Sectiune.TLabel", font=(font, 11, "bold"))
    style.configure("Mic.TLabel", font=(font, 9))
    style.configure("Pornire.TButton", font=(font, 14, "bold"), padding=(24, 16))
    style.configure("Mare.TButton", font=(font, 12, "bold"), padding=(18, 14))
    style.configure("Normal.TButton", font=(font, 10), padding=(12, 8))
    style.configure("Legatura.TButton", font=(font, 9), padding=(4, 2))
    style.configure("Ok.TLabel", font=(font, 11, "bold"), foreground="#1a7f37")
    style.configure("Rau.TLabel", font=(font, 11, "bold"), foreground="#b3261e")
    style.configure("Info.TLabel", font=(font, 10), foreground="#444444")
    style.configure("Progres.Horizontal.TProgressbar", thickness=22)
    return font


def centru(fereastra: tk.Misc) -> None:
    """Centrează o fereastră de dialog pe părintele ei."""
    fereastra.update_idletasks()
    parinte = fereastra.master
    if parinte is None:
        return
    try:
        x = parinte.winfo_rootx() + (parinte.winfo_width() - fereastra.winfo_width()) // 2
        y = parinte.winfo_rooty() + (parinte.winfo_height() - fereastra.winfo_height()) // 3
        fereastra.geometry(f"+{max(0, x)}+{max(0, y)}")
    except Exception:
        pass


def deschide_folder(cale) -> None:
    """Deschide un folder în Explorer, fără a depinde de programe externe."""
    import os
    from pathlib import Path

    folder = Path(cale)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        os.startfile(str(folder))  # type: ignore[attr-defined]
    except Exception:
        pass


def ruleaza_in_fir(functie, *argumente, **parametri):
    """Pornește o funcție în fundal, ca interfața să nu înghețe."""
    import threading

    fir = threading.Thread(target=functie, args=argumente, kwargs=parametri, daemon=True)
    fir.start()
    return fir
