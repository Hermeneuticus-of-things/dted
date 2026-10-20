"""Ferestrele despre driverele care lipsesc (punctul 20).

Aceste ferestre vorbesc **doar** despre drivere și despre componentele Windows
de care are nevoie programul. Nu spun niciodată că ar trebui un calculator nou:
dacă driverul nu poate fi instalat automat, se explică exact de unde se ia.
"""

from __future__ import annotations

import threading
import tkinter as tk

from . import cai, drivere, jurnal
from .constante import NUME_APLICATIE
from .ui_comun import (
    BUTON_PRINCIPAL,
    CULORI,
    BaraProgres,
    Buton,
    ButonScurtatura,
    CoadaUI,
    centrat,
    eticheta,
    fonturi,
    px,
    spatiu,
)

TITLU_DRIVERE = f"{NUME_APLICATIE} – Lipsesc drivere"


class FereastraDrivere(tk.Toplevel):
    """„Dictare&Transcriere Română – Lipsesc drivere”."""

    def __init__(self, parinte: tk.Misc, stare: drivere.StareDrivere | None = None):
        super().__init__(parinte)
        self.title(TITLU_DRIVERE)
        self.configure(background=CULORI.fundal)
        self.transient(parinte)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.stare = stare or drivere.verifica()
        self.rezultat = "inchis"

        cadru = tk.Frame(self, background=CULORI.fundal)
        cadru.pack(fill="both", expand=True, padx=px(18), pady=px(16))
        latime = px(720)

        eticheta(cadru, "Lipsesc drivere", "titlu", fundal=CULORI.fundal).pack(anchor="w")
        eticheta(
            cadru,
            "Acestea nu împiedică salvarea documentelor. Se oprește doar partea care "
            "are nevoie de driverul respectiv.",
            "baza",
            fundal=CULORI.fundal,
            latime_bucati=latime,
        ).pack(anchor="w", pady=(px(6), px(10)))

        for lipsa in self.stare.lipsuri:
            bloc = tk.Frame(
                cadru,
                background=CULORI.card,
                highlightthickness=px(2),
                highlightbackground=CULORI.chenar,
            )
            bloc.pack(fill="x", pady=(0, px(10)))
            interior = tk.Frame(bloc, background=CULORI.card)
            interior.pack(fill="x", padx=px(12), pady=px(10))
            eticheta(
                interior,
                f"✖  Lipsește driverul pentru: {lipsa.dispozitiv}.",
                "subtitlu",
                fundal=CULORI.card,
                latime_bucati=latime - px(60),
            ).pack(anchor="w")
            eticheta(
                interior,
                f"Fără el nu merge: {lipsa.ce_nu_merge}.",
                "baza",
                fundal=CULORI.card,
                latime_bucati=latime - px(60),
            ).pack(anchor="w", pady=(px(4), 0))
            eticheta(
                interior,
                f"De unde îl iei: {lipsa.sursa}.",
                "baza",
                fundal=CULORI.card,
                latime_bucati=latime - px(60),
            ).pack(anchor="w", pady=(px(4), 0))

        if self.stare.producator or self.stare.model:
            eticheta(
                cadru,
                f"Calculatorul tău: {drivere.model_pentru_cautare()}. "
                "Pe site-ul oficial al producătorului, caută driverele pentru acest model.",
                "mica",
                fundal=CULORI.fundal,
                latime_bucati=latime,
            ).pack(anchor="w")

        rand = tk.Frame(cadru, background=CULORI.fundal)
        rand.pack(fill="x", pady=(px(14), 0))
        ButonScurtatura(
            rand,
            "Deschide Windows Update",
            lambda: self._deschide_update(),
            fel="principal",
            latime=280,
            inaltime=BUTON_PRINCIPAL[1],
        ).pack(side="left")
        ButonScurtatura(
            rand,
            "Copiază instrucțiunile",
            lambda: self._copiaza(),
            latime=250,
            inaltime=52,
        ).pack(side="left", padx=px(spatiu()))
        ButonScurtatura(rand, "Verifică din nou", self._verifica, latime=200, inaltime=52).pack(side="left")
        ButonScurtatura(
            rand,
            "? Ajutor",
            lambda: self._ajutor(),
            latime=160,
            inaltime=52,
        ).pack(side="left", padx=(px(spatiu()), 0))

        self.mesaj = eticheta(cadru, "", "baza", fundal=CULORI.fundal, latime_bucati=latime)
        self.mesaj.pack(anchor="w", pady=(px(10), 0))

        self.zona_detalii = tk.Text(
            cadru,
            height=5,
            width=80,
            font=fonturi().mica or ("Segoe UI", 11),
            background=CULORI.zona_text,
            foreground=CULORI.text,
            wrap="word",
        )
        self._detalii_aratate = False
        self.buton_detalii = Buton(
            cadru,
            "Detalii pentru cineva care se pricepe",
            self._comuta_detalii,
            latime=340,
            inaltime=44,
        )
        self.buton_detalii.pack(anchor="w", pady=(px(8), 0))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centrat(self, max(px(760), self.winfo_reqwidth()), max(px(540), self.winfo_reqheight()))
        self.grab_set()

    # ------------------------------------------------------------------ acțiuni

    def _comuta_detalii(self) -> None:
        self._detalii_aratate = not self._detalii_aratate
        if self._detalii_aratate:
            self.zona_detalii.insert("1.0", self.stare.detalii_tehnice or "(fără detalii)")
            self.zona_detalii.configure(state="disabled")
            self.zona_detalii.pack(fill="x", pady=(px(8), 0))
            self.buton_detalii.seteaza_text("Ascunde detaliile tehnice")
        else:
            self.zona_detalii.pack_forget()
            self.buton_detalii.seteaza_text("Detalii pentru cineva care se pricepe")

    def _deschide_update(self) -> None:
        drivere.deschide_windows_update()
        self.mesaj.configure(
            text=(
                "Am deschis Windows Update. Apasă „Verifică actualizările”, apoi "
                "„Actualizări opționale → Actualizări de drivere”."
            )
        )

    def _copiaza(self) -> None:
        text = drivere.instructiuni_de_copiat(self.stare)
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self.mesaj.configure(text="Instrucțiunile au fost copiate. Le poți lipi oriunde.")
        except Exception as exc:
            jurnal.atentionare(f"Copierea instrucțiunilor nu a reușit: {exc}")
            self.mesaj.configure(text="Nu am putut copia. Selectează textul și folosește Ctrl+C.")

    def _verifica(self) -> None:
        self.mesaj.configure(text="Verific din nou driverele…")
        self.update_idletasks()
        self.stare = drivere.verifica()
        if self.stare.totul_ok:
            self.mesaj.configure(
                text="Am verificat: toate driverele și componentele de care are nevoie programul sunt instalate."
            )
        else:
            self.mesaj.configure(
                text="Încă lipsesc drivere. Verifică din nou după ce instalezi actualizările."
            )
        self.rezultat = "verificat"

    def _ajutor(self) -> None:
        from . import ui_ajutor

        ui_ajutor.deschide(self, "drivere")


def fereastra_lipsesc_drivere(parinte: tk.Misc, stare: drivere.StareDrivere | None = None) -> drivere.StareDrivere:
    """Deschide fereastra „Lipsesc drivere” și întoarce starea de după verificări."""
    fereastra = FereastraDrivere(parinte, stare)
    try:
        fereastra.wait_window(fereastra)
    except Exception:
        pass
    return fereastra.stare


def intreaba_instalarea(parinte: tk.Misc, lipsa: drivere.Lipsa) -> bool:
    """Întreabă simplu dacă programul poate instala driverul lipsă.

    Se spune dinainte dacă Windows va cere drepturi de administrator, ca
    utilizatorul să nu fie luat prin surprindere de fereastra Windows.
    """
    from .ui_comun import dialog

    nume = lipsa.dispozitiv
    if lipsa.cheie == "componente":
        text = (
            "Lipsesc componentele Microsoft de care are nevoie programul de transcriere.\n\n"
            "Programul le poate instala singur, de pe site-ul oficial Microsoft, după ce "
            "verifică semnătura digitală.\n\n"
            "Windows va cere voie o singură dată, pentru instalare."
        )
    else:
        text = (
            f"Lipsește driverul pentru {nume}.\n\n"
            "Programul îl poate instala singur, din Windows Update (driverele oficiale ale "
            "Windows pentru acest dispozitiv).\n\n"
            "Windows va cere voie o singură dată, pentru instalare. Îți explicăm pe scurt: "
            "instalarea unui driver are nevoie de drepturi de administrator, altfel Windows "
            "nu dă voie să se schimbe ceva la dispozitive."
        )
    rezultat = dialog(
        parinte,
        "Lipsește un driver" if lipsa.cheie != "componente" else "Lipsesc componente Windows",
        text,
        [("Da, instalează", "principal"), ("Nu acum", "secundar")],
        implicit=0,
        anulare=1,
    )
    return rezultat == 0


class FereastraProgresDrivere(tk.Toplevel):
    """Fereastra mică de progres, cu mesaje în cuvinte simple."""

    def __init__(self, parinte: tk.Misc, titlu: str):
        super().__init__(parinte)
        self.title(f"{NUME_APLICATIE} – {titlu}")
        self.configure(background=CULORI.fundal)
        self.transient(parinte)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # nu închidem în timpul lucrului
        self.rezultat: tuple[bool, str, bool] = (False, "", False)
        self._coada = CoadaUI(self, 80)

        cadru = tk.Frame(self, background=CULORI.fundal)
        cadru.pack(fill="both", expand=True, padx=px(18), pady=px(16))
        eticheta(cadru, titlu, "subtitlu", fundal=CULORI.fundal).pack(anchor="w")
        self.text = eticheta(
            cadru,
            "Pregătesc instalarea…",
            "baza",
            fundal=CULORI.fundal,
            latime_bucati=px(560),
        )
        self.text.pack(anchor="w", pady=(px(8), px(10)))
        self.bara = BaraProgres(cadru, 560, 26)
        self.bara.pack(anchor="w")
        eticheta(
            cadru,
            "Nu închide fereastra. Dacă Windows cere voie pentru instalare, apasă „Da”.",
            "mica",
            fundal=CULORI.fundal,
            latime_bucati=px(560),
        ).pack(anchor="w", pady=(px(10), 0))

        self.update_idletasks()
        centrat(self, max(px(620), self.winfo_reqwidth()), max(px(260), self.winfo_reqheight()))
        self.grab_set()

    # ------------------------------------------------------------------ progres

    def raporteaza(self, mesaj: str, fractiune: float) -> None:
        self._coada.trimite(self._arata, mesaj, fractiune)

    def _arata(self, mesaj: str, fractiune: float) -> None:
        if not self.winfo_exists():
            return
        self.text.configure(text=mesaj)
        self.bara.seteaza(fractiune)

    def ruleaza(self, functie, *argumente) -> tuple[bool, str, bool]:
        """Rulează instalarea în alt fir și așteaptă rezultatul, fără să înghețe."""
        rezultat: dict = {}

        def lucru() -> None:
            try:
                rezultat["valoare"] = functie(*argumente, self.raporteaza)
            except Exception as exc:  # nicio eroare nu închide programul
                jurnal.eroare(f"Instalarea driverelor a eșuat: {type(exc).__name__}: {exc}")
                rezultat["valoare"] = (False, "Instalarea nu s-a terminat.", False)

        fir = threading.Thread(target=lucru, daemon=True, name="drivere")
        fir.start()
        while fir.is_alive():
            try:
                self.update()
            except tk.TclError:
                break
            fir.join(0.05)
        self._coada.opreste()
        self.rezultat = rezultat.get("valoare", (False, "Instalarea nu s-a terminat.", False))
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass
        return self.rezultat


def instaleaza_cu_progres(parinte: tk.Misc, lipsa: drivere.Lipsa) -> tuple[bool, str, bool]:
    """Instalează ce lipsește, arătând progresul în cuvinte simple."""
    if lipsa.cheie == "componente":
        fereastra = FereastraProgresDrivere(parinte, "Instalez componentele Microsoft")
        ok, mesaj, _ = fereastra.ruleaza(drivere.instaleaza_componente_windows)
        return ok, mesaj, False
    fereastra = FereastraProgresDrivere(parinte, "Instalez driverele din Windows Update")
    return fereastra.ruleaza(drivere.instaleaza_din_windows_update)


def rezolva_drivere(parinte: tk.Misc, stare: drivere.StareDrivere | None = None) -> drivere.StareDrivere:
    """Încearcă instalarea automată a driverelor, apoi arată ce a rămas.

    Se folosește la instalare și la fiecare pornire: întâi se încearcă ce se
    poate instala singur (din surse oficiale), apoi se explică ce nu s-a putut.
    """
    stare = stare or drivere.verifica()
    if stare.totul_ok:
        return stare
    for lipsa in list(stare.lipsuri):
        if not lipsa.poate_instala_automat:
            continue
        if not intreaba_instalarea(parinte, lipsa):
            continue
        ok, mesaj, repornire = instaleaza_cu_progres(parinte, lipsa)
        if ok:
            if repornire:
                _spune_repornire(parinte)
            else:
                _spune_reusit(parinte, lipsa)
            stare = drivere.verifica()
        else:
            jurnal.atentionare(f"Instalarea automată nu a reușit pentru {lipsa.dispozitiv}: {mesaj}")
            stare = drivere.verifica()
            if not stare.totul_ok:
                fereastra_lipsesc_drivere(parinte, stare)
            return stare
        if stare.totul_ok:
            return stare
    if not stare.totul_ok:
        fereastra_lipsesc_drivere(parinte, stare)
    return stare


def _spune_repornire(parinte: tk.Misc) -> None:
    from .ui_comun import anunta

    anunta(
        parinte,
        "Repornire necesară",
        "Ca driverul să meargă, repornește calculatorul.\n\n"
        "Programul își amintește unde ai rămas: după repornire, poți continua de aici.",
    )


def _spune_reusit(parinte: tk.Misc, lipsa: drivere.Lipsa) -> None:
    from .ui_comun import anunta

    text = "Am instalat componentele. Programul de transcriere poate porni."
    if lipsa.cheie in ("sunet", "dispozitiv"):
        text = (
            "Am instalat driverul. Microfonul ar trebui să meargă acum.\n\n"
            "Poți verifica imediat sunetul, din ecranul «Verifică sunetul»."
        )
    anunta(parinte, "Gata", text)


def deschide_optional() -> bool:
    """Deschide „Actualizări opționale”, acolo unde stau driverele."""
    return drivere.deschide_windows_update_optional()


def fisiere_jurnal() -> list[str]:
    """Jurnalele în care se poate citi ce s-a încercat (pentru cineva care se pricepe)."""
    return [str(cai.fisier_jurnal_instalare()), str(cai.fisier_jurnal_aplicatie())]
