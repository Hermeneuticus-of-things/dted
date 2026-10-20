"""Ferestrele despre componentele fizice ale calculatorului (punctul 19).

Aceste ferestre vorbesc **doar** despre memorie, procesor, spațiu pe disc și
sistem de operare. Despre drivere există ferestre separate (``ui_drivere``),
ca cele două situații să nu se amestece niciodată în același mesaj.

* „Ce calculator îți trebuie”: două coloane (Minim / Recomandat), ce are
  calculatorul de față și butoanele [Continuă instalarea], [Verifică din nou],
  [? Ajutor]. Se deschide înainte de orice descărcare, la instalare.
* „Acest calculator nu este potrivit”: apare doar când componentele fizice nu
  ajung, cu lista de arătat la magazin și butoanele [Copiază lista],
  [Salvează lista pe Desktop], [Închide].
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from . import ajutor, jurnal, resurse, sisteme
from .constante import DISC_RECOMANDAT_GB, NUME_APLICATIE
from .ui_comun import (
    BUTON_PRINCIPAL,
    CULORI,
    Buton,
    Banner,
    ButonScurtatura,
    centrat,
    eticheta,
    fonturi,
    px,
    spatiu,
)

#: Rezultatele posibile ale ferestrei „Ce calculator îți trebuie”.
CONTINUA = "continua"
VERIFICA_DIN_NOU = "verifica"
INCHEIAT = "inchis"


def _valoare_stare(rand: resurse.RandTabel) -> tuple[str, str]:
    """Culoarea și textul pentru coloana „Calculatorul tău”."""
    if rand.stare == "ok":
        return CULORI.verde_text, f"✔ {rand.cuvant}"
    if rand.stare == "atentionare":
        return CULORI.galben_text, f"! {rand.cuvant}"
    if rand.stare == "optioanala":
        return CULORI.text_secundar, f"– {rand.cuvant}"
    return CULORI.rosu_text, f"✖ {rand.cuvant}"


class FereastraCalculator(tk.Toplevel):
    """„Dictare&Transcriere Română – Ce calculator îți trebuie”."""

    def __init__(self, parinte: tk.Misc, raport: resurse.Raport | None = None):
        super().__init__(parinte)
        self.title(f"{NUME_APLICATIE} – Ce calculator îți trebuie")
        self.configure(background=CULORI.fundal)
        self.transient(parinte)
        self.protocol("WM_DELETE_WINDOW", lambda: self._termina(INCHEIAT))
        self.rezultat = INCHEIAT
        self.raport = raport or resurse.verifica()

        latime = min(resurse_maxim_latime(), px(980))
        cadru = tk.Frame(self, background=CULORI.fundal)
        cadru.pack(fill="both", expand=True, padx=px(16), pady=px(14))

        eticheta(cadru, "Ce calculator îți trebuie", "titlu", fundal=CULORI.fundal).pack(anchor="w")
        eticheta(
            cadru,
            "Așa arată calculatorul tău, citit automat acum. "
            "Nu se descarcă nimic până nu apeși „Continuă instalarea”.",
            "baza",
            fundal=CULORI.fundal,
            latime_bucati=latime - px(60),
        ).pack(anchor="w", pady=(px(6), px(10)))

        self.banner = Banner(cadru, "atentie")
        self.banner.pack(fill="x", pady=(0, px(10)))
        self._scrie_banner()

        tabel = tk.Frame(
            cadru,
            background=CULORI.card,
            highlightthickness=px(2),
            highlightbackground=CULORI.chenar,
        )
        tabel.pack(fill="both", expand=True)

        capete = ("Cerință", "Minim (merge, dar mai încet)", "Recomandat (merge bine)", "Calculatorul tău")
        latimi = (px(210), px(250), px(250), px(220))
        for coloana, text in enumerate(capete):
            tk.Label(
                tabel,
                text=text,
                font=fonturi().buton_secundar or ("Segoe UI", 12),
                background=CULORI.card,
                foreground=CULORI.text,
                justify="left",
                anchor="w",
                wraplength=latimi[coloana],
            ).grid(row=0, column=coloana, sticky="nw", padx=px(10), pady=(px(10), px(6)))

        for linie, rand in enumerate(resurse.tabel_minim_recomandat(self.raport), start=1):
            culoare, text_stare = _valoare_stare(rand)
            continut = [
                (rand.nume, CULORI.text, fonturi().buton_secundar or ("Segoe UI", 12)),
                (rand.minim, CULORI.text_secundar, fonturi().baza or ("Segoe UI", 12)),
                (rand.recomandat, CULORI.text_secundar, fonturi().baza or ("Segoe UI", 12)),
                (text_stare, culoare, fonturi().buton_secundar or ("Segoe UI", 12)),
            ]
            for coloana, (text, culoare_text, font) in enumerate(continut):
                tk.Label(
                    tabel,
                    text=text,
                    font=font,
                    background=CULORI.card,
                    foreground=culoare_text,
                    justify="left",
                    anchor="w",
                    wraplength=latimi[coloana],
                ).grid(row=linie, column=coloana, sticky="nw", padx=px(10), pady=px(6))
            if rand.explicatie:
                tk.Label(
                    tabel,
                    text=f"({rand.explicatie})",
                    font=fonturi().mica or ("Segoe UI", 11),
                    background=CULORI.card,
                    foreground=CULORI.text_secundar,
                    justify="left",
                    anchor="w",
                    wraplength=latime - px(80),
                ).grid(row=linie, column=0, columnspan=4, sticky="w", padx=px(10), pady=(0, px(6)))

        rand_butoane = tk.Frame(cadru, background=CULORI.fundal)
        rand_butoane.pack(fill="x", pady=(px(14), 0))

        self.buton_continua = ButonScurtatura(
            rand_butoane,
            "Continuă instalarea",
            lambda: self._termina(CONTINUA),
            fel="principal",
            latime=BUTON_PRINCIPAL[0] + 40,
            inaltime=BUTON_PRINCIPAL[1],
        )
        self.buton_continua.pack(side="left")
        ButonScurtatura(
            rand_butoane,
            "Verifică din nou",
            lambda: self._termina(VERIFICA_DIN_NOU),
            latime=210,
            inaltime=52,
            scurtatura="",
        ).pack(side="left", padx=px(spatiu()))
        ButonScurtatura(
            rand_butoane,
            "? Ajutor",
            lambda: self._ajutor(),
            latime=170,
            inaltime=52,
        ).pack(side="left")

        self.buton_continua.activeaza(self.raport.poate_instala)
        if not self.raport.poate_instala:
            eticheta(
                cadru,
                "Butonul „Continuă instalarea” se activează după ce cerințele minime sunt îndeplinite.",
                "mica",
                fundal=CULORI.fundal,
                latime_bucati=latime - px(80),
            ).pack(anchor="w", pady=(px(8), 0))

        self.bind("<Escape>", lambda _e: self._termina(INCHEIAT))
        self.bind("<Return>", lambda _e: self._enter())
        self.update_idletasks()
        centrat(self, max(px(760), self.winfo_reqwidth()), max(px(560), self.winfo_reqheight()))
        self.grab_set()
        try:
            (self.buton_continua if self.raport.poate_instala else self.buton_continua).focus_set()
        except Exception:
            pass
        self.wait_window(self)

    # ------------------------------------------------------------------ ajutoare

    def _enter(self) -> None:
        if self.raport.poate_instala:
            self._termina(CONTINUA)
        else:
            self._termina(VERIFICA_DIN_NOU)

    def _scrie_banner(self) -> None:
        if not self.raport.poate_instala:
            text = (
                "Acest calculator nu are componentele fizice minime. "
                "Apasă „Verifică din nou” după ce rezolvi ce scrie mai jos."
            )
            if self.raport.blocante and all(c.cheie == "disc" for c in self.raport.blocante):
                text = _mesaj_spatiu_disc(self.raport)
            self.banner.arata(text)
            return
        are_recomandate = all(
            rand.stare in ("ok", "optioanala") for rand in resurse.tabel_minim_recomandat(self.raport)
        )
        if are_recomandate:
            self.banner.arata(
                "Calculatorul tău îndeplinește toate cerințele. Poți porni instalarea."
            )
        else:
            self.banner.arata(_mesaj_mai_lent(self.raport))

    def _ajutor(self) -> None:
        from . import ui_ajutor

        ui_ajutor.deschide(self, "instalare")

    def _termina(self, rezultat: str) -> None:
        self.rezultat = rezultat
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


def resurse_maxim_latime() -> int:
    """Lățimea maximă folosită de fereastră, ca să încapă pe ecrane mici."""
    radacina = tk._default_root  # type: ignore[attr-defined]
    latime = radacina.winfo_screenwidth() if radacina else 1280
    return max(px(720), latime - px(120))


def _mesaj_spatiu_disc(raport: resurse.Raport) -> str:
    """Mesajul special pentru spațiul pe disc (singura lipsă fizică rezolvabilă pe loc)."""
    lipsa = max(0.0, raport.disc_necesar_gb - raport.disc_liber_gb)
    return (
        f"Ai nevoie de încă {lipsa:.1f} GB liberi pe disc. Șterge fișiere de care nu ai "
        "nevoie sau alege alt disc pentru instalare, apoi apasă «Verifică din nou»."
    )


def _mesaj_mai_lent(raport: resurse.Raport) -> str:
    """Avertismentul când minimul e îndeplinit, dar nu și recomandatul."""
    minute = _estimare_minute(raport, 10.0)
    return (
        "Programul va merge, dar transcrierea va fi mai lentă. De exemplu, 10 minute de "
        f"vorbire pot dura aproximativ {minute:.0f} minute (estimare)."
    )


def _estimare_minute(raport: resurse.Raport, minute_audio: float) -> float:
    """Cât ar putea dura transcrierea, în minute (estimare cinstită)."""
    if raport.are_gpu:
        return max(1.0, minute_audio * 0.25)
    nuclee = max(1, raport.nuclee)
    ram = raport.ram_gb or 8.0
    factor = 2.0
    if nuclee >= 8:
        factor = 1.2
    elif nuclee >= 4:
        factor = 1.8
    else:
        factor = 3.0
    if ram < 8:
        factor *= 1.6
    elif ram >= 16:
        factor *= 0.9
    return minute_audio * factor


class FereastraNepotrivit(tk.Toplevel):
    """„Acest calculator nu este potrivit” — doar componente fizice, fără drivere."""

    def __init__(self, parinte: tk.Misc, raport: resurse.Raport):
        super().__init__(parinte)
        self.title(f"{NUME_APLICATIE} – Acest calculator nu este potrivit")
        self.configure(background=CULORI.fundal)
        self.transient(parinte)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.raport = raport

        cadru = tk.Frame(self, background=CULORI.fundal)
        cadru.pack(fill="both", expand=True, padx=px(18), pady=px(16))
        latime = min(resurse_maxim_latime(), px(760))

        eticheta(
            cadru,
            "Acest calculator nu este potrivit pentru program.",
            "titlu",
            fundal=CULORI.fundal,
            latime_bucati=latime - px(60),
        ).pack(anchor="w")
        eticheta(
            cadru,
            f"De ce: {resurse.motiv_nepotrivit(self.raport)}.",
            "baza",
            fundal=CULORI.fundal,
            latime_bucati=latime - px(60),
        ).pack(anchor="w", pady=(px(8), px(12)))
        eticheta(
            cadru,
            "Ai nevoie de un calculator care să aibă:",
            "subtitlu",
            fundal=CULORI.fundal,
        ).pack(anchor="w")

        lista = resurse.lista_pentru_magazin()
        zona = tk.Text(
            cadru,
            height=9,
            width=60,
            font=fonturi().baza or ("Segoe UI", 12),
            background=CULORI.zona_text,
            foreground=CULORI.text,
            wrap="word",
            relief="solid",
            bd=1,
        )
        zona.insert("1.0", lista)
        zona.configure(state="disabled")
        zona.pack(fill="x", pady=(px(6), px(6)))

        eticheta(
            cadru,
            "Poți arăta această listă la magazin.",
            "baza",
            fundal=CULORI.fundal,
        ).pack(anchor="w")

        rand = tk.Frame(cadru, background=CULORI.fundal)
        rand.pack(anchor="e", pady=(px(14), 0))
        ButonScurtatura(rand, "Copiază lista", lambda: self._copiaza(lista), fel="principal",
                        latime=BUTON_PRINCIPAL[0], inaltime=BUTON_PRINCIPAL[1]).pack(side="left")
        self.buton_salveaza = ButonScurtatura(
            rand, "Salvează lista pe Desktop", lambda: self._salveaza(lista), latime=270, inaltime=52
        )
        self.buton_salveaza.pack(side="left", padx=px(spatiu()))
        ButonScurtatura(rand, "Închide", self.destroy, latime=170, inaltime=52).pack(side="left")

        self.mesaj = eticheta(cadru, "", "baza", fundal=CULORI.fundal, latime_bucati=latime - px(60))
        self.mesaj.pack(anchor="w", pady=(px(10), 0))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centrat(self, max(px(700), self.winfo_reqwidth()), max(px(560), self.winfo_reqheight()))
        self.grab_set()
        self.wait_window(self)

    def _copiaza(self, text: str) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self.mesaj.configure(text="Lista a fost copiată. O poți lipi oriunde, de exemplu într-un mesaj.")
        except Exception as exc:
            jurnal.atentionare(f"Copierea listei nu a reușit: {exc}")
            self.mesaj.configure(text="Nu am putut copia lista. Poți selecta textul de mai sus și îl copiezi cu Ctrl+C.")

    def _salveaza(self, text: str) -> None:
        tinta = sisteme.folder_desktop() / "Ce calculator îmi trebuie.txt"
        try:
            tinta.parent.mkdir(parents=True, exist_ok=True)
            tinta.write_text(text + "\n", encoding="utf-8")
            self.mesaj.configure(text=f"Am salvat lista pe Desktop: {tinta.name}")
            jurnal.info(f"Lista pentru magazin a fost salvată în {tinta}")
        except OSError as exc:
            jurnal.atentionare(f"Nu am putut salva lista pe Desktop: {exc}")
            self.mesaj.configure(text="Nu am putut salva lista pe Desktop. Poți folosi „Copiază lista”.")


def fereastra_calculator(parinte: tk.Misc, raport: resurse.Raport | None = None) -> tuple[str, resurse.Raport]:
    """Deschide fereastra „Ce calculator îți trebuie” și întoarce (alegerea, raportul)."""
    raport = raport or resurse.verifica()
    fereastra = FereastraCalculator(parinte, raport)
    return fereastra.rezultat, fereastra.raport


def fereastra_nepotrivit(parinte: tk.Misc, raport: resurse.Raport) -> None:
    """Deschide fereastra „Acest calculator nu este potrivit”."""
    FereastraNepotrivit(parinte, raport)


def verifica_si_explica(parinte: tk.Misc, raport: resurse.Raport | None = None) -> resurse.Raport:
    """Verifică resursele și, dacă e cazul, explică simplu ce lipsește.

    Întâi se arată ce se poate rezolva pe calculatorul de față (spațiu pe disc,
    actualizări de Windows, microfon); recomandarea unui calculator nou apare
    doar când problema chiar ține de componentele fizice.
    """
    raport = raport or resurse.verifica()
    if raport.poate_instala:
        return raport
    rezolvabile = resurse.probleme_rezolvabile(raport)
    if raport.blocante and all(c.cheie == "disc" for c in raport.blocante):
        from .ui_comun import anunta

        anunta(parinte, "Spațiu pe disc", _mesaj_spatiu_disc(raport))
        return raport
    if any(cheie == "windows_update" for _, cheie in rezolvabile):
        din_ui = _intreaba_windows_update(parinte, raport)
        if din_ui:
            return resurse.verifica()
    fereastra_nepotrivit(parinte, raport)
    return raport


def _intreaba_windows_update(parinte: tk.Misc, raport: resurse.Raport) -> bool:
    """Oferă instalarea actualizărilor de Windows înainte de a spune „calculator nou”."""
    from .ui_comun import dialog

    rezultat = dialog(
        parinte,
        "Se poate rezolva acum",
        (
            "Problema se poate rezolva pe acest calculator:\n\n"
            f"• {resurse.motiv_nepotrivit(raport)}\n\n"
            "Deschide Windows Update, instalează actualizările disponibile, apoi apasă "
            "«Verifică din nou». Programul nu instalează singur drivere și nu schimbă "
            "setări din Windows."
        ),
        [("Deschide Windows Update", "principal"), ("Verifică din nou", "secundar"), ("Închide", "secundar")],
        implicit=0,
        anulare=2,
    )
    if rezultat == 0:
        from . import drivere

        drivere.deschide_windows_update()
        return False
    if rezultat == 1:
        return True
    return False


def tabel_pentru_citeste_ma() -> str:
    """Tabelul cerințelor, așa cum apare în „Citește-mă.txt”."""
    from . import resurse as modul_resurse

    return modul_resurse.text_tabel_pentru_tiparire()


def text_despre_estimare(raport: resurse.Raport, minute_audio: float = 10.0) -> str:
    """Estimarea de timp afișată lângă avertismentul de calculator mai slab."""
    return _mesaj_mai_lent(raport)


def citeste_ma_pentru_test() -> str:
    """Textul din „Citește-mă.txt” (folosit la teste și la instalare)."""
    return ajutor.text_citeste_ma()


def disc_recomandat() -> float:
    return DISC_RECOMANDAT_GB
