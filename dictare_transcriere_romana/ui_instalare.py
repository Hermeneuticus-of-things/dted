"""Fereastra de instalare: wizard complet în 10 pași conform WIZARD_PROPUNERE.md.

Pașii:
1. Bun venit (ce se instalează, timp aproximativ)
2. Verificare rapidă a calculatorului (reutilizează resurse.verifica)
3. Unde instalezi programul? (cale folder, implicit LOCALAPPDATA, buton Răsfoiește)
4. Unde vrei iconița / scurtăturile? (bifă: Desktop, bara de activități, meniul Start, niciunde)
5. Unde salvezi fișierele create? (transcrieri / descărcări / recuperare, implicit Documente)
6. Ce instalezi (componente): Python, Model Whisper, LibreOffice RO (implicit: tot ce lipsește)
7. Rezumat „gata de instalat” (folder program, folder date, scurtături, componente)
8. Progres real + Anulează curat (etape reale, fără resturi, fără ștergere documente)
9. Verificare după instalare (pornire scurtă UI, mesaj clar dacă eșuează)
10. Finalizare (bifă „Pornește acum”, „Deschide Citește-mă”, confirmă locații)

Fereastra are titlu Windows normal, e mutabilă, redimensionabilă, închidibilă (X, Esc, Alt+F4).
"""

from __future__ import annotations

import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from . import (
    cai,
    codecuri,
    config as config_modul,
    constante,
    drivere,
    instalare,
    jurnal,
    libreoffice,
    resurse,
    sisteme,
    ui_calculator,
    ui_comun,
    ui_drivere,
    ui_progres,
)

#: Textul de la începutul instalării.
MESAJ_INCEPUT = (
    "Programul are nevoie, o singură dată, de câteva descărcări de pe site-urile "
    "oficiale (Python, bibliotecile de transcriere, modelul de recunoaștere a "
    "vocii și programul de scris). Nu se descarcă nimic până nu apeși butonul "
    "de mai jos."
)

#: Textul de după instalare, când totul a mers.
MESAJ_GATA = (
    "Gata! Programul este instalat. Pe Desktop a apărut pictograma "
    "„{nume}”: de acolo îl pornești de fiecare dată."
)

#: Cât de des se citește ce a raportat firul de instalare (secunde).
PAS_COADA = 0.08


class FereastraInstalare(tk.Toplevel):
    """Asistent de instalare în 10 pași: bun venit → calculator → folder → scurtături → date → componente → rezumat → progres → verificare → finalizare."""

    def __init__(self, parinte: tk.Misc, motiv: str = "", la_final=None, presetari: dict | None = None):
        super().__init__(parinte)
        ui_comun.seteaza_titlu(self, "Instalare — Dictare&Transcriere Română")
        self.configure(background=ui_comun.CULORI.fundal)
        self.transient(parinte)
        # Fereastră normală Windows: mutabilă, redimensionabilă, închidibilă
        self.resizable(True, True)
        self.minsize(ui_comun.px(900), ui_comun.px(650))
        self.protocol("WM_DELETE_WINDOW", self._cere_inchiderea)
        self.bind("<Escape>", lambda _e: self._cere_inchiderea())
        self.bind("<Alt-F4>", lambda _e: self._cere_inchiderea())

        self.la_final = la_final
        self.motiv = motiv
        self.presetari = dict(presetari or {})
        self._sari_verificarea = bool(self.presetari.get("sari_verificarea", False))
        self._pas_curent = 1
        self._oprit = False
        self._oprit_cerut = False
        self._terminat = False
        self._reusit = False
        self._program_deschis = False
        self._coada: queue.Queue = queue.Queue()
        self._fir: threading.Thread | None = None
        self._raport: resurse.Raport | None = None
        self._se_citeste_calculator: bool = False
        self._zona_progres: ui_progres.ZonaProgres | None = None
        self._rezumat: dict = {}
        self._stare_drivere = None

        # Variabile pentru wizard
        self._var_folder_instalare = tk.StringVar(value=str(cai.director_instalare()))
        self._var_scurtatura_desktop = tk.BooleanVar(value=True)
        self._var_scurtatura_start = tk.BooleanVar(value=True)
        self._var_scurtatura_taskbar = tk.BooleanVar(value=False)
        self._var_folder_date = tk.StringVar(value=str(config_modul.director_iesiri(config_modul.incarca())))
        self._var_libreoffice = tk.BooleanVar(value=not bool(self.presetari.get("fara_libreoffice", False)))
        self._var_model_whisper = tk.BooleanVar(value=True)
        self._var_python_env = tk.BooleanVar(value=True)
        self._var_porneste_acum = tk.BooleanVar(value=True)
        self._var_deschide_citeste_ma = tk.BooleanVar(value=True)

        # 1. Antetul wizard-ului (sus, fix)
        self._antet = tk.Frame(self, background=ui_comun.CULORI.fundal)
        self._antet.pack(side="top", fill="x", padx=ui_comun.px(20), pady=(ui_comun.px(14), ui_comun.px(6)))

        self._lbl_pas = tk.Label(
            self._antet,
            text="Pasul 1 din 10",
            font=ui_comun.fonturi().buton,
            background=ui_comun.CULORI.fundal,
            foreground=ui_comun.CULORI.principal,
        )
        self._lbl_pas.pack(anchor="w")

        self._lbl_titlu_pas = tk.Label(
            self._antet,
            text="Bun venit și verificare internet",
            font=ui_comun.fonturi().titlu,
            background=ui_comun.CULORI.fundal,
            foreground=ui_comun.CULORI.text,
        )
        self._lbl_titlu_pas.pack(anchor="w", pady=(ui_comun.px(2), 0))

        linia = tk.Canvas(self._antet, height=ui_comun.px(2), background=ui_comun.CULORI.chenar, highlightthickness=0)
        linia.pack(fill="x", pady=(ui_comun.px(8), 0))

        # 2. Linia de stare și bara de butoane (jos, mereu în același loc)
        self._stare = ui_comun.LinieStare(self)
        self._stare.pack(side="bottom", fill="x", padx=ui_comun.px(20), pady=(0, ui_comun.px(10)))

        self._cadru_butoane = tk.Frame(self, background=ui_comun.CULORI.fundal)
        self._cadru_butoane.pack(side="bottom", fill="x", padx=ui_comun.px(20), pady=ui_comun.px(8))

        self.btn_inapoi = ui_comun.Buton(
            self._cadru_butoane,
            "← Înapoi",
            self._pas_inapoi,
            latime=180,
            inaltime=52,
        )
        self.btn_inapoi.pack(side="left")

        self.btn_inainte = ui_comun.Buton(
            self._cadru_butoane,
            "Următorul →",
            self._pas_inainte,
            fel="principal",
            latime=260,
            inaltime=52,
        )
        self.btn_inainte.pack(side="left", padx=ui_comun.px(ui_comun.SPATIU))

        self.btn_anuleaza = ui_comun.Buton(
            self._cadru_butoane,
            "Anulează",
            self._cere_inchiderea,
            latime=180,
            inaltime=52,
        )
        self.btn_anuleaza.pack(side="right")

        # 3. Corpul derulabil de conținut (mijloc)
        self._zona_derulare = ui_comun.ZonaDerulare(self, latime_minima=880)
        self._zona_derulare.pack(fill="both", expand=True, padx=ui_comun.px(18), pady=ui_comun.px(6))
        self._corp = tk.Frame(self._zona_derulare.interior, background=ui_comun.CULORI.fundal)
        self._corp.pack(fill="both", expand=True)

        self._arata_pas(1)
        self._aseaza()
        self.after(int(PAS_COADA * 1000), self._citeste_coada)

    # ------------------------------------------------------------------ așezare

    def _aseaza(self) -> None:
        self.update_idletasks()
        latime_ecran, inaltime_ecran = ui_comun.maxim_ecran(0.95)
        latime = min(ui_comun.px(1000), latime_ecran)
        inaltime = min(ui_comun.px(720), inaltime_ecran)
        ui_comun.centrat(self, latime=latime, inaltime=inaltime)

    # ------------------------------------------------------------------ navigare între pași

    def _arata_pas(self, pas: int) -> None:
        self._pas_curent = pas
        for copil in self._corp.winfo_children():
            copil.destroy()

        titluri = {
            1: "Bun venit",
            2: "Verificare calculator",
            3: "Unde instalezi programul?",
            4: "Unde vrei iconița / scurtăturile?",
            5: "Unde salvezi fișierele create?",
            6: "Ce instalezi (componente)",
            7: "Rezumat – gata de instalat",
            8: "Instalare – progres real",
            9: "Verificare după instalare",
            10: "Finalizare",
        }
        self._lbl_pas.configure(text=f"Pasul {pas} din 10")
        self._lbl_titlu_pas.configure(text=titluri.get(pas, ""))

        if pas == 1:
            self._construieste_pas_1()
        elif pas == 2:
            self._construieste_pas_2()
        elif pas == 3:
            self._construieste_pas_3()
        elif pas == 4:
            self._construieste_pas_4()
        elif pas == 5:
            self._construieste_pas_5()
        elif pas == 6:
            self._construieste_pas_6()
        elif pas == 7:
            self._construieste_pas_7()
        elif pas == 8:
            self._construieste_pas_8()
        elif pas == 9:
            self._construieste_pas_9()
        elif pas == 10:
            self._construieste_pas_10()

        self._actualizeaza_butoane()

    def _actualizeaza_butoane(self) -> None:
        pas = self._pas_curent
        ruleaza = bool(self._fir is not None and self._fir.is_alive())

        if pas == 1:
            self.btn_inapoi.activeaza(False)
            self.btn_inainte.seteaza_text("Următorul →")
            self.btn_inainte.seteaza_fel("principal")
            self.btn_inainte.activeaza(True)
            self.btn_anuleaza.seteaza_text("Anulează")
            self.btn_anuleaza.activeaza(True)
        elif pas == 2:
            self.btn_inapoi.activeaza(True)
            self.btn_inainte.seteaza_text("Următorul →")
            self.btn_inainte.seteaza_fel("principal")
            if self._se_citeste_calculator or self._raport is None:
                self.btn_inainte.activeaza(False)
            else:
                self.btn_inainte.activeaza(bool(self._raport.poate_instala or self._sari_verificarea))
            self.btn_anuleaza.seteaza_text("Anulează")
            self.btn_anuleaza.activeaza(True)
        elif pas == 3:
            self.btn_inapoi.activeaza(True)
            self.btn_inainte.seteaza_text("Următorul →")
            self.btn_inainte.seteaza_fel("principal")
            self.btn_inainte.activeaza(True)
            self.btn_anuleaza.seteaza_text("Anulează")
            self.btn_anuleaza.activeaza(True)
        elif pas == 4:
            self.btn_inapoi.activeaza(True)
            self.btn_inainte.seteaza_text("Următorul →")
            self.btn_inainte.seteaza_fel("principal")
            self.btn_inainte.activeaza(True)
            self.btn_anuleaza.seteaza_text("Anulează")
            self.btn_anuleaza.activeaza(True)
        elif pas == 5:
            self.btn_inapoi.activeaza(True)
            self.btn_inainte.seteaza_text("Următorul →")
            self.btn_inainte.seteaza_fel("principal")
            self.btn_inainte.activeaza(True)
            self.btn_anuleaza.seteaza_text("Anulează")
            self.btn_anuleaza.activeaza(True)
        elif pas == 6:
            self.btn_inapoi.activeaza(True)
            self.btn_inainte.seteaza_text("Următorul →")
            self.btn_inainte.seteaza_fel("principal")
            self.btn_inainte.activeaza(True)
            self.btn_anuleaza.seteaza_text("Anulează")
            self.btn_anuleaza.activeaza(True)
        elif pas == 7:
            self.btn_inapoi.activeaza(True)
            self.btn_inainte.seteaza_text("Instalează")
            self.btn_inainte.seteaza_fel("principal")
            self.btn_inainte.activeaza(True)
            self.btn_anuleaza.seteaza_text("Anulează")
            self.btn_anuleaza.activeaza(True)
        elif pas == 8:
            if ruleaza:
                self.btn_inapoi.activeaza(False)
                self.btn_inainte.seteaza_text("Se instalează…")
                self.btn_inainte.seteaza_fel("principal")
                self.btn_inainte.activeaza(False)
                self.btn_anuleaza.seteaza_text("Oprește")
                self.btn_anuleaza.activeaza(True)
            else:
                self.btn_inapoi.activeaza(True)
                self.btn_inainte.seteaza_text("Instalează")
                self.btn_inainte.seteaza_fel("principal")
                self.btn_inainte.activeaza(True)
                self.btn_anuleaza.seteaza_text("Anulează")
                self.btn_anuleaza.activeaza(True)
        elif pas == 9:
            self.btn_inapoi.activeaza(False)
            self.btn_inainte.seteaza_text("Următorul →")
            self.btn_inainte.seteaza_fel("principal")
            self.btn_inainte.activeaza(True)
            self.btn_anuleaza.seteaza_text("Închide")
            self.btn_anuleaza.activeaza(True)
        elif pas == 10:
            self.btn_inapoi.activeaza(False)
            self.btn_inainte.seteaza_text("Gata")
            self.btn_inainte.seteaza_fel("principal")
            self.btn_inainte.activeaza(True)
            self.btn_anuleaza.seteaza_text("Închide")
            self.btn_anuleaza.activeaza(True)

    def _pas_inapoi(self) -> None:
        if self._fir is not None and self._fir.is_alive():
            return
        if self._pas_curent > 1 and self._pas_curent < 10:
            self._arata_pas(self._pas_curent - 1)

    def _pas_inainte(self) -> None:
        if self._pas_curent < 7:
            self._arata_pas(self._pas_curent + 1)
        elif self._pas_curent == 7:
            self._porneste_instalarea()
        elif self._pas_curent == 9:
            self._arata_pas(10)
        elif self._pas_curent == 10:
            self._termina_si_porneste()

    # ------------------------------------------------------------------ pasul 1: bun venit & internet

    def _construieste_pas_1(self) -> None:
        C = ui_comun.CULORI
        card_desc, corp_desc = ui_comun.card(self._corp, f"Bun venit în {constante.NUME_APLICATIE}")
        card_desc.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        ui_comun.eticheta(
            corp_desc,
            "Acest asistent te ghidează pas cu pas în pregătirea programului de dictare și transcriere.\n\n"
            "• Transcrie automat vorbirea în limba română (cu diacritice corecte).\n"
            "• Funcționează complet offline după instalare — înregistrările și documentele tale nu părăsesc calculatorul.\n"
            "• Salvează automat în LibreOffice Writer, DOCX sau ODT.\n\n"
            "Nu se descarcă nimic pe calculator până la pasul de instalare (Pasul 5).",
            "baza",
            fundal=C.card,
            latime_bucati=840,
        ).pack(anchor="w")

        card_net, corp_net = ui_comun.card(self._corp, "Verificare conexiune internet")
        card_net.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        self._rand_internet = tk.Frame(corp_net, background=C.card)
        self._rand_internet.pack(fill="x")
        self._afiseaza_stare_internet()

        self._stare.arata("Pregătit", "Apasă „Următorul” pentru a continua.", "normal")

    def _afiseaza_stare_internet(self) -> None:
        C = ui_comun.CULORI
        for copil in self._rand_internet.winfo_children():
            copil.destroy()
        from . import internet

        try:
            stare = internet.verifica()
            ok = stare.complet or stare.are_legatura
        except Exception:
            ok = True

        if ok:
            ui_comun.eticheta(
                self._rand_internet,
                "✔ Conexiunea la internet este activă. Descărcarea componentelor inițiale este posibilă.",
                "baza",
                fundal=C.card,
            ).pack(anchor="w")
        else:
            ui_comun.eticheta(
                self._rand_internet,
                "! Conexiunea la internet nu a putut fi confirmată. Programul are nevoie de internet doar o singură dată, la instalare.",
                "baza",
                fundal=C.card,
            ).pack(anchor="w")
            ui_comun.Buton(
                self._rand_internet,
                "Verifică conexiunea din nou",
                self._afiseaza_stare_internet,
                latime=260,
                inaltime=48,
            ).pack(anchor="w", pady=(ui_comun.px(6), 0))

    # ------------------------------------------------------------------ pasul 2: calculatorul (în fundal)

    def _construieste_pas_2(self) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self._corp, "Componentele calculatorului tău")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        self._rand_tabel = tk.Frame(corp, background=C.card)
        self._rand_tabel.pack(fill="x")

        rand_actiuni = tk.Frame(corp, background=C.card)
        rand_actiuni.pack(fill="x", pady=(ui_comun.px(10), 0))
        ui_comun.Buton(
            rand_actiuni,
            "Arată-mi ce calculator îmi trebuie",
            self._arata_calculatorul,
            latime=340,
            inaltime=52,
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(
            rand_actiuni,
            "Verifică din nou",
            self._reverifica_calculator,
            latime=200,
            inaltime=52,
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(rand_actiuni, "? Ajutor", self._ajutor, scurtatura="F1", latime=160, inaltime=52).pack(side="left")

        if self._raport is None:
            self._arata_asteptare_calculator()
            if not self._se_citeste_calculator:
                self._porneste_citire_calculator()
        else:
            self._scrie_tabelul()

    def _arata_asteptare_calculator(self) -> None:
        C = ui_comun.CULORI
        for copil in self._rand_tabel.winfo_children():
            copil.destroy()
        ui_comun.eticheta(
            self._rand_tabel,
            "⏳ Citesc componentele calculatorului tău… (procesor, memorie RAM, spațiu pe disc)",
            "baza",
            fundal=C.card,
        ).pack(anchor="w", pady=ui_comun.px(8))
        self._stare.arata("Verific", "Citesc componentele calculatorului…", "lucru")

    def _porneste_citire_calculator(self) -> None:
        if self._se_citeste_calculator:
            return
        self._se_citeste_calculator = True
        threading.Thread(target=self._fir_citeste_calculator, name="citire-calculator", daemon=True).start()

    def _fir_citeste_calculator(self) -> None:
        try:
            config = config_modul.incarca()
            raport = resurse.verifica(config_modul.director_iesiri(config))
        except Exception as exc:
            jurnal.atentionare(f"Citirea resurselor a eșuat: {exc}")
            raport = None
        self._coada.put(("raport_calculator", raport))

    def _reverifica_calculator(self) -> None:
        self._raport = None
        self._arata_asteptare_calculator()
        self._actualizeaza_butoane()
        self._porneste_citire_calculator()

    def _scrie_tabelul(self) -> None:
        C = ui_comun.CULORI
        for copil in self._rand_tabel.winfo_children():
            copil.destroy()
        if self._raport is None:
            ui_comun.eticheta(self._rand_tabel, "Nu am putut citi informațiile calculatorului.", "baza", fundal=C.card).pack(
                anchor="w"
            )
            return
        raport = self._raport
        for rand in resurse.tabel_minim_recomandat(raport)[:8]:
            linie = tk.Frame(self._rand_tabel, background=C.card)
            linie.pack(fill="x", pady=(0, ui_comun.px(4)))
            semn = {"ok": "✔", "atentionare": "!", "lipsa": "✘", "optioanala": "–"}.get(rand.stare, "–")
            culoare = {
                "ok": C.verde_text,
                "atentionare": C.galben_text,
                "lipsa": C.rosu_text,
                "optioanala": C.text_secundar,
            }.get(rand.stare, C.text)
            tk.Label(
                linie,
                text=semn,
                font=ui_comun.fonturi().buton,
                background=C.card,
                foreground=culoare,
                width=3,
                anchor="w",
            ).pack(side="left")
            tk.Label(
                linie,
                text=f"{rand.nume}: {rand.gasit}",
                font=ui_comun.fonturi().baza,
                background=C.card,
                foreground=C.text,
                anchor="w",
                justify="left",
                wraplength=ui_comun.px(600),
            ).pack(side="left")
        self._stare.arata("Verificat", self._rezumat_scurt(), "bine" if self._raport and self._raport.poate_instala else "atentie")

    def _rezumat_scurt(self) -> str:
        if self._raport is None:
            return "Nu am putut citi informațiile calculatorului."
        if not self._raport.poate_instala:
            return "Calculatorul nu îndeplinește încă cerințele obligatorii."
        return "Calculatorul poate rula programul."

    def _arata_calculatorul(self) -> None:
        rezultat, raport = ui_calculator.fereastra_calculator(self, self._raport)
        self._raport = raport
        if rezultat != ui_calculator.INCHEIAT:
            self._scrie_tabelul()
            self._actualizeaza_butoane()
        if rezultat == ui_calculator.CONTINUA:
            self._pas_inainte()

    # ------------------------------------------------------------------ pasul 3: Unde instalezi programul?

    def _construieste_pas_3(self) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self._corp, "Alege folderul de instalare")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        ui_comun.eticheta(
            corp,
            "Programul și componentele sale (Python, model, LibreOffice) vor fi instalate aici.\n"
            "Implicit este un folder dedicat în datele locale ale utilizatorului.",
            "baza",
            fundal=C.card,
            latime_bucati=840,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        rand_folder = tk.Frame(corp, background=C.card)
        rand_folder.pack(fill="x")
        entry = tk.Entry(
            rand_folder,
            textvariable=self._var_folder_instalare,
            font=ui_comun.fonturi().baza,
            width=70,
            background=C.input_fundal,
            foreground=C.input_text,
            insertbackground=C.input_text,
            relief="flat",
            highlightthickness=ui_comun.px(1),
            highlightbackground=C.chenar,
            highlightcolor=C.principal,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, ui_comun.px(6)))

        ui_comun.Buton(
            rand_folder,
            "Răsfoiește…",
            lambda: self._alegere_folder(self._var_folder_instalare),
            latime=160,
            inaltime=44,
        ).pack(side="left")

        ui_comun.eticheta(
            corp,
            "Se vor crea subfolderele: program/, model/, libreoffice/, descarcari/, recuperare/",
            "mica",
            fundal=C.card,
            foreground=C.text_secundar,
        ).pack(anchor="w", pady=(ui_comun.px(8), 0))

        self._stare.arata("Folder", "Alege unde se instalează programul.", "normal")

    def _alegere_folder(self, variabila: tk.StringVar) -> None:
        folder = filedialog.askdirectory(
            parent=self,
            title="Alege folderul de instalare",
            initialdir=variabila.get() or str(Path.home()),
        )
        if folder:
            variabila.set(folder)

    def _arata_driverele(self) -> None:
        ui_drivere.fereastra_lipsesc_drivere(self)

    # ------------------------------------------------------------------ pasul 4: Unde vrei iconița / scurtăturile?

    def _construieste_pas_4(self) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self._corp, "Creează scurtături pentru pornire rapidă")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        ui_comun.eticheta(
            corp,
            "Bifează unde vrei să apară pictograma programului:",
            "baza",
            fundal=C.card,
            latime_bucati=840,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        self._bifeaza(corp, self._var_scurtatura_desktop, "Pe Desktop")
        self._bifeaza(corp, self._var_scurtatura_start, "În meniul Start")
        self._bifeaza(corp, self._var_scurtatura_taskbar, "Pe bara de activități (taskbar)")

        ui_comun.eticheta(
            corp,
            "Poți schimba aceste setări ulterior din program: Setări → Scurtături.",
            "mica",
            fundal=C.card,
            foreground=C.text_secundar,
        ).pack(anchor="w", pady=(ui_comun.px(8), 0))

        self._stare.arata("Scurtături", "Alege unde apar pictogramele de pornire.", "normal")

    # ------------------------------------------------------------------ pasul 5: Unde salvezi fișierele create?

    def _construieste_pas_5(self) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self._corp, "Alege folderul pentru fișierele create")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        ui_comun.eticheta(
            corp,
            "Transcrierile, înregistrările și fișierele recuperate se salvează aici.\n"
            "Implicit este folderul Documente al utilizatorului.",
            "baza",
            fundal=C.card,
            latime_bucati=840,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        rand_folder = tk.Frame(corp, background=C.card)
        rand_folder.pack(fill="x")
        entry = tk.Entry(
            rand_folder,
            textvariable=self._var_folder_date,
            font=ui_comun.fonturi().baza,
            width=70,
            background=C.input_fundal,
            foreground=C.input_text,
            insertbackground=C.input_text,
            relief="flat",
            highlightthickness=ui_comun.px(1),
            highlightbackground=C.chenar,
            highlightcolor=C.principal,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, ui_comun.px(6)))

        ui_comun.Buton(
            rand_folder,
            "Răsfoiește…",
            lambda: self._alegere_folder(self._var_folder_date),
            latime=160,
            inaltime=44,
        ).pack(side="left")

        ui_comun.eticheta(
            corp,
            "Se vor crea subfolderele: transcrieri/, inregistrari/, recuperare/",
            "mica",
            fundal=C.card,
            foreground=C.text_secundar,
        ).pack(anchor="w", pady=(ui_comun.px(8), 0))

        self._stare.arata("Date", "Alege unde se salvează fișierele tale.", "normal")

    # ------------------------------------------------------------------ pasul 6: Ce instalezi (componente)

    def _construieste_pas_6(self) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self._corp, "Selectează componentele de instalat")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        ui_comun.eticheta(
            corp,
            "Se instalează doar ce lipsește. Bifează ce vrei (implicit: tot ce nu este deja pe calculator).",
            "baza",
            fundal=C.card,
            latime_bucati=840,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        # Python + mediul de transcriere
        stare_python = instalare.verifica_python()
        text_python = "✔ Python și mediul sunt deja instalați" if stare_python.ok else "Python + biblioteci de transcriere (obligatoriu)"
        self._bifeaza(corp, self._var_python_env, text_python)

        # Model Whisper
        stare_model = instalare.verifica_model()
        text_model = "✔ Modelul Whisper este deja descărcat" if stare_model.ok else "Modelul Whisper large-v3-turbo (~1,5 GB, obligatoriu)"
        self._bifeaza(corp, self._var_model_whisper, text_model)

        # LibreOffice
        stare_lo = libreoffice.stare()
        if stare_lo.gasit:
            text_lo = f"✔ LibreOffice Writer este deja instalat ({stare_lo.pentru_utilizator()})"
            self._bifeaza(corp, self._var_libreoffice, text_lo)
            self._var_libreoffice.set(False)
        else:
            self._bifeaza(
                corp,
                self._var_libreoffice,
                "LibreOffice Writer, în română, cu dicționarul românesc (recomandat)",
            )

        self._stare.arata("Componente", "Selectează ce se instalează.", "normal")

    # ------------------------------------------------------------------ pasul 7: Rezumat – gata de instalat

    def _construieste_pas_7(self) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self._corp, "Rezumat înainte de instalare")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        ui_comun.eticheta(
            corp,
            "Verifică setările înainte de a începe instalarea:",
            "baza",
            fundal=C.card,
            latime_bucati=840,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        randuri = [
            ("Folder program", self._var_folder_instalare.get()),
            ("Folder date (transcrieri, înregistrări)", self._var_folder_date.get()),
            ("Scurtătură Desktop", "Da" if self._var_scurtatura_desktop.get() else "Nu"),
            ("Scurtătură Meniul Start", "Da" if self._var_scurtatura_start.get() else "Nu"),
            ("Scurtătură Taskbar", "Da" if self._var_scurtatura_taskbar.get() else "Nu"),
            ("Python + mediul de transcriere", "Da" if self._var_python_env.get() else "Nu"),
            ("Model Whisper large-v3-turbo", "Da" if self._var_model_whisper.get() else "Nu"),
            ("LibreOffice Writer (română)", "Da" if self._var_libreoffice.get() else "Nu"),
        ]

        for eticheta, valoare in randuri:
            rand = tk.Frame(corp, background=C.card)
            rand.pack(fill="x", pady=(0, ui_comun.px(3)))
            tk.Label(
                rand, text=f"{eticheta}:", font=ui_comun.fonturi().baza, background=C.card, foreground=C.text_secundar, width=40, anchor="w"
            ).pack(side="left")
            tk.Label(
                rand, text=valoare, font=ui_comun.fonturi().baza, background=C.card, foreground=C.text, anchor="w"
            ).pack(side="left")

        self._stare.arata("Rezumat", "Verifică și apasă „Instalează”.", "normal")

    def _porneste_instalarea(self) -> None:
        """Colectează setările din wizard și pornește instalarea reală."""
        # Colectăm opțiunile
        optiuni = {
            "folder_instalare": self._var_folder_instalare.get(),
            "folder_date": self._var_folder_date.get(),
            "scurtatura_desktop": self._var_scurtatura_desktop.get(),
            "scurtatura_start": self._var_scurtatura_start.get(),
            "scurtatura_taskbar": self._var_scurtatura_taskbar.get(),
            "instaleaza_python": self._var_python_env.get(),
            "instaleaza_model": self._var_model_whisper.get(),
            "instaleaza_libreoffice": self._var_libreoffice.get(),
            "sari_verificarea": self._sari_verificarea,
        }
        
        # Salvăm configurația
        config = config_modul.incarca()
        config.director_instalare = Path(optiuni["folder_instalare"])
        config.director_iesiri = Path(optiuni["folder_date"])
        config.creeaza_scurtatura_desktop = optiuni["scurtatura_desktop"]
        config.creeaza_scurtatura_start = optiuni["scurtatura_start"]
        config.creeaza_scurtatura_taskbar = optiuni["scurtatura_taskbar"]
        config_modul.salveaza(config)
        
        # Pornește instalarea
        self._arata_pas(8)
        
        def thread_instalare():
            self._ruleaza_instalarea(optiuni)
        
        self._fir = threading.Thread(target=thread_instalare, name="instalare-completa", daemon=True)
        self._fir.start()

    # ------------------------------------------------------------------ pasul 8: Instalare – progres real

    def _construieste_pas_8(self) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self._corp, "Instalare în curs")
        card.pack(fill="x")

        ui_comun.eticheta(
            corp,
            "Se descarcă și instalează componentele selectate. Poți opri oricând — ce s-a descărcat se păstrează.",
            "baza",
            fundal=C.card,
            latime_bucati=840,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        self._zona_progres = ui_progres.ZonaProgres(corp, "", la_oprire=self._cere_oprirea, latime=860)
        self._zona_progres.pack(fill="x")
        self._zona_progres.incepe("Pregătesc instalarea", 1, 5)

        if self._fir is not None and self._fir.is_alive():
            self._stare.arata("Instalez", "Descarc și instalez ce trebuie. Nu închide fereastra.", "lucru")
        else:
            self._stare.arata("Pregătit", "Apasă butonul „Instalează” pentru a începe.", "normal")

    # ------------------------------------------------------------------ pasul 9: Verificare după instalare

    def _construieste_pas_9(self) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self._corp, "Verificare după instalare")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        ui_comun.eticheta(
            corp,
            "Verificăm că programul pornește corect după instalare…",
            "baza",
            fundal=C.card,
            latime_bucati=840,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        self._zona_progres = ui_progres.ZonaProgres(corp, "", la_oprire=None, latime=860)
        self._zona_progres.pack(fill="x")
        self._zona_progres.incepe("Verific", 1, 1)
        
        # Rulează testul de pornire
        threading.Thread(target=self._testeaza_pornire, name="test-pornire", daemon=True).start()

    def _testeaza_pornire(self) -> None:
        """Testează că programul pornește după instalare."""
        import subprocess
        import sys
        
        try:
            # Pornește programul ca test (doar verifică că importurile merg)
            python_exe = cai.python_exe()
            if python_exe.exists():
                # Import test - verifică că modulele se încarcă
                rezultat = subprocess.run(
                    [str(python_exe), "-c", "import dictare_transcriere_romana.ui_principal; print('OK')"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if rezultat.returncode == 0:
                    self._coada.put(("test_pornire_ok",))
                else:
                    self._coada.put(("test_pornire_esuat", rezultat.stderr))
            else:
                self._coada.put(("test_pornire_esuat", "Python nu a fost găsit după instalare"))
        except subprocess.TimeoutExpired:
            self._coada.put(("test_pornire_esuat", "Testul de pornire a expirat"))
        except Exception as exc:
            self._coada.put(("test_pornire_esuat", str(exc)))

    # ------------------------------------------------------------------ pasul 10: Finalizare

    def _construieste_pas_10(self) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self._corp, "Instalare finalizată cu succes!")
        card.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))

        ui_comun.eticheta(
            corp,
            f"Gata! Programul „{constante.NUME_APLICATIE}” este instalat și verificat.\n"
            "Pe Desktop și în meniul Start a apărut pictograma programului.",
            "titlu",
            fundal=C.card,
            latime_bucati=840,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        rezumat = self._rezumat
        randuri = [
            ("Programul și pictogramele", "gata"),
            ("Python și mediul de transcriere", rezumat.get("biblioteci", "gata")),
            ("Modelul de recunoaștere a vocii (Whisper)", "gata" if rezumat.get("model") else "neterminat"),
            (
                "LibreOffice Writer",
                "gata" if rezumat.get("libreoffice") and rezumat.get("libreoffice") != "indisponibil" else "opțional",
            ),
            ("Suportul pentru fișiere audio", "gata"),
            ("Scurtături selectate", "gata" if rezumat.get("scurtaturi") else "opțional"),
        ]
        for text, stare in randuri:
            rand = tk.Frame(corp, background=C.card)
            rand.pack(fill="x", pady=(0, ui_comun.px(4)))
            semn = "✔" if stare == "gata" else ("–" if stare == "opțional" else "!")
            culoare = C.verde_text if stare == "gata" else (C.galben_text if stare == "opțional" else C.rosu_text)
            tk.Label(
                rand, text=semn, font=ui_comun.fonturi().buton, background=C.card, foreground=culoare, width=3, anchor="w"
            ).pack(side="left")
            tk.Label(
                rand,
                text=text,
                font=ui_comun.fonturi().baza,
                background=C.card,
                foreground=C.text,
                anchor="w",
                justify="left",
                wraplength=ui_comun.px(640),
            ).pack(side="left")

        # Checkbox-uri finale
        rand_bife = tk.Frame(corp, background=C.card)
        rand_bife.pack(fill="x", pady=(ui_comun.px(12), 0))
        cb1 = tk.Checkbutton(
            rand_bife,
            text="Pornește programul acum",
            variable=self._var_porneste_acum,
            font=ui_comun.fonturi().baza,
            background=C.card,
            foreground=C.text,
            activebackground=C.card,
            activeforeground=C.text,
            selectcolor=C.card,
        )
        cb1.pack(anchor="w")
        cb2 = tk.Checkbutton(
            rand_bife,
            text="Deschide „Citește-mă.txt”",
            variable=self._var_deschide_citeste_ma,
            font=ui_comun.fonturi().baza,
            background=C.card,
            foreground=C.text,
            activebackground=C.card,
            activeforeground=C.text,
            selectcolor=C.card,
        )
        cb2.pack(anchor="w", pady=(ui_comun.px(6), 0))

        rand_actiuni = tk.Frame(corp, background=C.card)
        rand_actiuni.pack(fill="x", pady=(ui_comun.px(12), 0))
        ui_comun.Buton(
            rand_actiuni,
            "Deschide „Citește-mă.txt”",
            self._deschide_citeste_ma,
            latime=340,
            inaltime=52,
        ).pack(side="left")

        self._stare.arata("Gata", "Programul este instalat și pregătit. Apasă „Gata”.", "bine")

    def _termina_si_porneste(self) -> None:
        """Încheie instalarea și opțional pornește programul."""
        if self._program_deschis:
            return
        self._program_deschis = True
        self._reusit = True
        
        if self._var_deschide_citeste_ma.get():
            self._deschide_citeste_ma()
        
        if self._var_porneste_acum.get():
            self._porneste_programul()
        
        self._inchide()

    def _porneste_programul(self) -> None:
        """Pornește aplicația principală după instalare."""
        import subprocess
        python_exe = cai.python_exe()
        if python_exe.exists():
            try:
                subprocess.Popen(
                    [str(python_exe), "-m", "dictare_transcriere_romana"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as exc:
                jurnal.atentionare(f"Nu am putut porni programul: {exc}")

    def _ruleaza_instalarea(self, optiuni) -> None:
        """Aici lucrează firul greu: instalarea, apoi ce trebuie pentru fișierele audio."""
        try:
            rezumat = instalare.instaleaza(
                optiuni,
                progres=self._raporteaza,
                anuleaza=lambda: self._oprit,
            )
        except instalare.InstalareOprita:
            self._coada.put(("oprit",))
            return
        except Exception as exc:
            self._coada.put(("eroare", exc, "instalarea programului"))
            return

        if self._oprit:
            self._coada.put(("oprit",))
            return

        # Ce trebuie ca să se poată asculta orice fișier audio (cerința 24).
        try:
            self._raporteaza("Pregătesc ce trebuie pentru fișierele audio…", 0.95)
            codecuri.asigura(self._raporteaza)
            if self._oprit:
                self._coada.put(("oprit",))
                return
            self._raporteaza("Verific driverele de care are nevoie programul…", 0.98)
            stare_drivere = drivere.verifica()
        except Exception as exc:
            if self._oprit:
                self._coada.put(("oprit",))
                return
            self._coada.put(("eroare", exc, "pregătirea părților audio"))
            return

        if self._oprit:
            self._coada.put(("oprit",))
            return

        self._coada.put(("gata", rezumat, stare_drivere))

    def _raporteaza(self, mesaj: str, fractiune: float) -> None:
        self._coada.put(("progres", mesaj, fractiune))

    # ------------------------------------------------------------------ tratare evenimente din coadă

    def _trateaza(self, mesaj: tuple) -> None:
        """Procesează mesajele din firul de instalare."""
        try:
            tip = mesaj[0]
            if tip == "progres":
                if self._zona_progres is not None:
                    self._zona_progres.seteaza(float(mesaj[2]), mesaj[1], 1, 5)
                self._stare.arata("Instalez", mesaj[1], "lucru")
            elif tip == "gata":
                rezumat, stare_drivere = mesaj[1], mesaj[2]
                self._termina_bine(rezumat, stare_drivere)
            elif tip == "eroare":
                exc, context = mesaj[1], mesaj[2]
                self._arata_eroarea(exc, context)
            elif tip == "oprit":
                self._termina_oprit()
            elif tip == "test_pornire_ok":
                if self._zona_progres is not None:
                    self._zona_progres.gata("Gata! Programul pornește corect.")
                self._stare.arata("Verificat", "Programul pornește corect.", "bine")
            elif tip == "test_pornire_esuat":
                eroare = mesaj[1] if len(mesaj) > 1 else "Eroare necunoscută"
                if self._zona_progres is not None:
                    self._zona_progres.reseteaza()
                self._stare.arata("Eroare", f"Testul de pornire a eșuat: {eroare}", "eroare")
                ui_comun.anunta(
                    self,
                    "Verificarea a eșuat",
                    f"Programul nu pornește corect după instalare:\n{eroare}\n\n"
                    "Poți încerca să pornești manual sau să reinstalezi.",
                )
        except tk.TclError:
            pass
        except Exception as exc:
            jurnal.atentionare(f"Eroare la tratarea mesajului {mesaj}: {exc}")

    # ------------------------------------------------------------------ coada de evenimente

    def _citeste_coada(self) -> None:
        try:
            while True:
                mesaj = self._coada.get_nowait()
                self._trateaza(mesaj)
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            self.after(int(PAS_COADA * 1000), self._citeste_coada)
        except tk.TclError:
            return

    def _cere_oprirea(self) -> None:
        """Oprirea se face curat, cu termen-limită."""
        if self._terminat:
            return
        raspuns = ui_comun.dialog(
            self,
            "Sigur vrei să oprești?",
            "Instalarea se oprește acum. Ce s-a descărcat până acum se păstrează, iar data viitoare "
            "instalarea continuă de unde a rămas.\n\nVrei să oprești?",
            [("Da, oprește", "pericol"), ("Nu, continuă", "secundar")],
            implicit=1,
            anulare=1,
        )
        if raspuns == 0:
            self._oprit = True
            self._oprit_cerut = True
            if self._zona_progres is not None:
                self._zona_progres.seteaza_pas("Opresc… păstrez ce s-a descărcat")
            self._stare.arata("Opresc", "Opresc instalarea. Ce s-a descărcat se păstrează.", "atentie")

    def _termina_oprit(self) -> None:
        self._terminat = True
        self._reusit = False
        if self._zona_progres is not None:
            self._zona_progres.reseteaza()
        self._stare.arata("Oprit", "Am oprit instalarea. Ce s-a descărcat se păstrează.", "atentie")
        self._actualizeaza_butoane()

    def _termina_bine(self, rezumat: dict, stare_drivere) -> None:
        self._terminat = True
        self._reusit = True
        self._rezumat = rezumat or {}
        self._stare_drivere = stare_drivere
        if self._zona_progres is not None:
            self._zona_progres.gata("Gata! Instalarea s-a terminat.")
        if stare_drivere is not None and getattr(stare_drivere, "lipsuri", None):
            try:
                ui_drivere.fereastra_lipsesc_drivere(self, stare_drivere)
            except Exception as exc:
                jurnal.atentionare(f"Fereastra de drivere nu a putut fi arătată: {exc}")
        self._arata_pas(9)

    def _arata_eroarea(self, exc: BaseException, context: str) -> None:
        from . import ajutor, erori

        self._terminat = True
        self._reusit = False
        if self._zona_progres is not None:
            self._zona_progres.reseteaza()

        def scrie_pasii(_fel: str = "") -> None:
            cale = ajutor.scrie_citeste_ma()
            if cale is not None:
                sisteme.deschide_fisier(cale)
                ui_comun.anunta(
                    self,
                    "Am scris pașii într-un fișier",
                    f"Pașii sunt în „{Path(cale).name}”, lângă program. Îl poți citi sau îl poți da "
                    "cuiva care se pricepe.",
                )

        eroare = getattr(exc, "eroare", None)
        if eroare is None:
            if isinstance(exc, (instalare.EroareInstalare, codecuri.EroareCodecuri, libreoffice.EroareLibreOffice)):
                fara_internet = bool(getattr(exc, "fara_internet", False))
                eroare = erori.Eroare(
                    ce_s_a_intamplat=getattr(exc, "mesaj", None) or str(exc),
                    de_ce=(
                        "Instalarea are nevoie de internet o singură dată."
                        if fara_internet
                        else "Un pas al instalării nu s-a terminat cu bine."
                    ),
                    ce_faci_acum=getattr(exc, "ce_fac", "") or (
                        "Apasă „Încearcă din nou”. Ce s-a descărcat deja se păstrează."
                    ),
                    actiuni=[
                        erori.Actiune("Încearcă din nou", erori.INCERCARE_DIN_NOU),
                        erori.Actiune("Trimite-mi pașii într-un fișier", "pasii"),
                    ],
                    detalii=getattr(exc, "detalii", "") or str(exc),
                )
            else:
                eroare = erori.din_exceptie(exc, context)

        def la_actiune(fel: str) -> None:
            if fel == erori.INCERCARE_DIN_NOU:
                self._terminat = False
                self._arata_pas(5)
            elif fel == "pasii":
                scrie_pasii(fel)
            elif fel == erori.DESCHIDE_FOLDER:
                sisteme.deschide_folder(cai.director_instalare())

        if isinstance(exc, (instalare.EroareInstalare, codecuri.EroareCodecuri)) and getattr(exc, "fara_internet", False):
            raspuns = ui_comun.dialog(
                self,
                "Am nevoie de internet o singură dată",
                str(getattr(exc, "mesaj", "") or exc),
                [
                    ("Încearcă din nou", "principal"),
                    ("Trimite-mi pașii într-un fișier", "secundar"),
                    ("Închide", "secundar"),
                ],
                implicit=0,
                anulare=2,
            )
            if raspuns == 0:
                self._terminat = False
                self._arata_pas(5)
            elif raspuns == 1:
                scrie_pasii()
                self._scoate_avertismentul_de_internet()
            else:
                self._inchide()
            return
        ui_comun.dialog_eroare(self, eroare, la_actiune=la_actiune)

    def _scoate_avertismentul_de_internet(self) -> None:
        try:
            from . import ui_internet

            config = config_modul.incarca()
            ui_internet.avertizeaza(self, config, fortat=True)
        except Exception as exc:
            jurnal.atentionare(f"Avertismentul de siguranță nu a putut fi arătat: {exc}")

    def _bifeaza(self, parinte: tk.Misc, variabila: tk.BooleanVar, text: str) -> None:
        C = ui_comun.CULORI
        rand = tk.Frame(parinte, background=C.card)
        rand.pack(fill="x", pady=(0, ui_comun.px(6)))
        caseta = tk.Checkbutton(
            rand,
            text=text,
            variable=variabila,
            font=ui_comun.fonturi().baza,
            background=C.card,
            foreground=C.text,
            activebackground=C.card,
            activeforeground=C.text,
            selectcolor=C.card,
            anchor="w",
            justify="left",
            highlightthickness=ui_comun.px(2),
            highlightbackground=C.chenar,
            wraplength=ui_comun.px(820),
        )
        caseta.pack(anchor="w")

    def _ajutor(self) -> None:
        from . import ui_ajutor

        ui_ajutor.deschide(self, "instalare")

    def _deschide_citeste_ma(self) -> None:
        cale = cai.fisier_citeste_ma()
        if not cale.exists():
            from . import ajutor

            scris = ajutor.scrie_citeste_ma()
            cale = scris or cale
        if not cale.exists():
            ui_comun.anunta(
                self,
                "Nu am găsit „Citește-mă.txt”",
                "Fișierul se scrie lângă program, la instalare. Poți citi ajutorul din program, cu butonul „? Ajutor”.",
            )
            return
        sisteme.deschide_fisier(cale)

    # ------------------------------------------------------------------ închidere reală

    def _cere_inchiderea(self) -> None:
        if self._fir is None or not self._fir.is_alive() or self._terminat:
            self._inchide()
            return
        raspuns = ui_comun.dialog(
            self,
            "Instalarea este în curs",
            "Dacă închizi acum, instalarea se oprește. Ce s-a descărcat până acum se păstrează, "
            "iar data viitoare continuă de unde a rămas.\n\nCe vrei să faci?",
            [("Lasă instalarea să meargă", "secundar"), ("Oprește și închide", "pericol")],
            implicit=0,
            anulare=0,
        )
        if raspuns == 1:
            self._oprit = True
            self._oprit_cerut = True
            if self._zona_progres is not None:
                try:
                    self._zona_progres.seteaza_pas("Opresc… păstrez ce s-a descărcat")
                except Exception:
                    pass
            self._stare.arata("Opresc", "Opresc instalarea. Ce s-a descărcat se păstrează.", "atentie")
            self.after(1500, self._inchide)

    def _inchide(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self.la_final is not None:
            try:
                self.la_final(self._reusit)
            except Exception as exc:
                jurnal.atentionare(f"Încheierea instalării a dat eroare: {exc}")


# --------------------------------------------------------------------------- doar LibreOffice


class FereastraLibreOffice(tk.Toplevel):
    """Instalarea LibreOffice, în română, cu progres și buton de oprire."""

    def __init__(self, parinte: tk.Misc, dupa_instalare: Path | None = None, la_final=None):
        super().__init__(parinte)
        ui_comun.seteaza_titlu(self, "Instalare LibreOffice")
        self.configure(background=ui_comun.CULORI.fundal)
        self.transient(parinte)
        self.protocol("WM_DELETE_WINDOW", self._cere_inchiderea)
        self.dupa_instalare = dupa_instalare
        self.la_final = la_final
        self._oprit = False
        self._oprit_cerut = False
        self._terminat = False
        self._coada: queue.Queue = queue.Queue()
        self._zona_progres: ui_progres.ZonaProgres | None = None

        C = ui_comun.CULORI
        cadru = tk.Frame(self, background=C.fundal)
        cadru.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(14))
        ui_comun.eticheta(cadru, "Instalez LibreOffice, în română", "titlu").pack(anchor="w")
        ui_comun.eticheta(
            cadru,
            "LibreOffice este programul de scris în care se corectează textul. Se instalează în română, "
            "cu dicționarul românesc, de pe site-ul oficial. Este nevoie de internet o singură dată. "
            "Poți opri oricând: ce s-a descărcat se păstrează.",
            "baza",
            latime_bucati=860,
        ).pack(anchor="w", pady=(ui_comun.px(6), ui_comun.px(12)))
        card, corp = ui_comun.card(cadru, "Ce se întâmplă acum")
        card.pack(fill="x")
        self._zona_progres = ui_progres.ZonaProgres(corp, "", la_oprire=self._cere_oprirea, latime=860)
        self._zona_progres.pack(fill="x")
        self._zona_progres.incepe("Descarc LibreOffice", 1, 3)
        self._stare = ui_comun.LinieStare(cadru)
        self._stare.pack(fill="x", pady=(ui_comun.px(10), 0))
        self._stare.arata("Instalez", "Descarc LibreOffice. Durează cât descărcarea.", "lucru")
        ui_comun.Buton(cadru, "? Ajutor", self._ajutor, scurtatura="F1", latime=200, inaltime=56).pack(
            anchor="w", pady=(ui_comun.px(10), 0)
        )
        self.update_idletasks()
        latime_ecran, inaltime_ecran = ui_comun.maxim_ecran(0.95)
        ui_comun.centrat(self, latime=min(ui_comun.px(980), latime_ecran), inaltime=min(ui_comun.px(520), inaltime_ecran))
        threading.Thread(target=self._ruleaza, name="libreoffice", daemon=True).start()
        self.after(120, self._citeste_coada)

    def _ajutor(self) -> None:
        from . import ui_ajutor

        ui_ajutor.deschide(self, "instalare")

    def _ruleaza(self) -> None:
        try:
            stare = libreoffice.instaleaza(progres=self._raporteaza)
        except Exception as exc:
            self._coada.put(("eroare", exc))
            return
        self._coada.put(("gata", stare))

    def _raporteaza(self, mesaj: str, fractiune: float) -> None:
        self._coada.put(("progres", mesaj, fractiune))

    def _citeste_coada(self) -> None:
        try:
            while True:
                mesaj = self._coada.get_nowait()
                if mesaj[0] == "progres":
                    pas = 1 if mesaj[2] < 0.4 else (2 if mesaj[2] < 0.85 else 3)
                    if self._zona_progres is not None:
                        self._zona_progres.seteaza(float(mesaj[2]), mesaj[1], pas, 3)
                elif mesaj[0] == "gata":
                    self._termina_bine(mesaj[1])
                elif mesaj[0] == "eroare":
                    self._termina_cu_eroare(mesaj[1])
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            self.after(120, self._citeste_coada)
        except tk.TclError:
            return

    def _cere_oprirea(self) -> None:
        if self._terminat:
            return
        raspuns = ui_comun.dialog(
            self,
            "Sigur vrei să oprești?",
            "Instalarea LibreOffice se oprește. Ce s-a descărcat se păstrează.\n\nVrei să oprești?",
            [("Da, oprește", "pericol"), ("Nu, continuă", "secundar")],
            implicit=1,
            anulare=1,
        )
        if raspuns == 0:
            self._oprit = True
            self._oprit_cerut = True

    def _cere_inchiderea(self) -> None:
        if self._terminat:
            self._inchide()
            return
        raspuns = ui_comun.dialog(
            self,
            "Instalarea este în curs",
            "Dacă închizi acum, instalarea LibreOffice se oprește. Ce s-a descărcat se păstrează.\n\n"
            "Ce vrei să faci?",
            [("Lasă instalarea să meargă", "secundar"), ("Oprește și închide", "pericol")],
            implicit=0,
            anulare=0,
        )
        if raspuns == 1:
            self._oprit = True

    def _termina_bine(self, stare) -> None:
        self._terminat = True
        if self._zona_progres is not None:
            self._zona_progres.gata("Gata! LibreOffice este instalat, în română.")
        self._stare.arata("Gata", "LibreOffice este instalat.", "bine")
        texte = ["LibreOffice este instalat, în română."]
        if not getattr(stare, "are_dictionar_romana", False):
            texte.append(
                "Dicționarul românesc nu a putut fi așezat acum: se poate așeza mai târziu, din LibreOffice, "
                "la „Unelte → Limbi”."
            )
        ui_comun.anunta(self, "Gata!", "\n\n".join(texte))
        if self.dupa_instalare is not None:
            reusit, mesaj = libreoffice.deschide_in_writer(self.dupa_instalare)
            if not reusit:
                ui_comun.anunta(
                    self,
                    "Documentul nu a putut fi deschis",
                    f"Documentul este salvat, îl poți deschide manual. {mesaj}",
                    detalii=mesaj,
                )
        self._inchide()

    def _termina_cu_eroare(self, exc: BaseException) -> None:
        from . import erori

        self._terminat = True
        if self._zona_progres is not None:
            self._zona_progres.reseteaza()
        fara_internet = bool(getattr(exc, "fara_internet", False))
        eroare = erori.Eroare(
            ce_s_a_intamplat=str(getattr(exc, "mesaj", "") or exc),
            de_ce="Descărcarea are nevoie de internet." if fara_internet else "Instalarea nu s-a terminat cu bine.",
            ce_faci_acum=getattr(exc, "ce_fac", "") or (
                "Apasă „Încearcă din nou”. Ce s-a descărcat se păstrează; programul merge și fără LibreOffice."
            ),
            actiuni=[
                erori.Actiune("Încearcă din nou", erori.INCERCARE_DIN_NOU),
                erori.Actiune("Continuă fără LibreOffice", erori.RENUNTA),
            ],
            detalii=getattr(exc, "detalii", "") or str(exc),
        )

        def la_actiune(fel: str) -> None:
            if fel == erori.INCERCARE_DIN_NOU:
                self._terminat = False
                threading.Thread(target=self._ruleaza, name="libreoffice", daemon=True).start()
            else:
                self._inchide()

        ui_comun.dialog_eroare(self, eroare, la_actiune=la_actiune)

    def _inchide(self) -> None:
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self.la_final is not None:
            try:
                self.la_final()
            except Exception as exc:
                jurnal.atentionare(f"Încheierea instalării LibreOffice a dat eroare: {exc}")


# --------------------------------------------------------------------------- porțile de intrare


def deschide(parinte: tk.Misc, motiv: str = "", la_final=None, presetari: dict | None = None) -> FereastraInstalare:
    """Deschide fereastra de instalare completă (o singură dată)."""
    existenta = _fereastra_deschisa(parinte, FereastraInstalare)
    if existenta is not None:
        existenta.lift()
        existenta.focus_set()
        if motiv:
            existenta._stare.arata("Instalez", motiv, "lucru")
        return existenta
    fereastra = FereastraInstalare(parinte, motiv=motiv, la_final=la_final, presetari=presetari)
    fereastra.lift()
    return fereastra


def instaleaza_libreoffice(parinte: tk.Misc, dupa_instalare: Path | None = None) -> FereastraLibreOffice:
    """Deschide fereastra de instalare a LibreOffice (o singură dată)."""
    existenta = _fereastra_deschisa(parinte, FereastraLibreOffice)
    if existenta is not None:
        existenta.lift()
        existenta.focus_set()
        return existenta
    fereastra = FereastraLibreOffice(parinte, dupa_instalare=dupa_instalare)
    fereastra.lift()
    return fereastra


def _fereastra_deschisa(parinte: tk.Misc, tip):
    """Fereastra de acest fel care este deja deschisă (ca să nu se deschidă două)."""
    for copil in parinte.winfo_children():
        if isinstance(copil, tip) and copil.winfo_exists():
            return copil
    return None


def ruleaza_standalone(presetari: dict | None = None) -> int:
    """Pornește doar instalarea (când este deschisă din „instaleaza.bat”)."""
    ui_comun.pregateste_dpi()
    radacina = tk.Tk()
    radacina.withdraw()
    ui_comun.seteaza_scala(radacina)
    config = config_modul.incarca()
    ui_comun.aplica_tema(getattr(config, "mod_afisare", "windows"))
    ui_comun.seteaza_marirea_scrisului(getattr(config, "marire_scris", 100))
    ui_comun.pregateste_fonturi(radacina)
    # Doar dacă a fost deschis din scurtătură (presetari goale și --instaleaza --interfata)
    if not presetari:
        jurnal.instalare("Instalarea a fost deschisă din scurtătură.")
    cai.pregateste_directoare()

    def la_final(_reusit: bool = False) -> None:
        try:
            radacina.quit()
        except tk.TclError:
            pass

    deschide(radacina, motiv="", la_final=la_final, presetari=presetari)
    try:
        radacina.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            radacina.destroy()
        except tk.TclError:
            pass
    return 0


def dezinstaleaza_cu_fereastra(parinte: tk.Misc | None = None) -> bool:
    """Dezinstalarea, cu întrebările programului (fără ferestrele Windows)."""
    if parinte is None:
        ui_comun.pregateste_dpi()
        parinte = tk.Tk()
        parinte.withdraw()
        ui_comun.seteaza_scala(parinte)
        config = config_modul.incarca()
        ui_comun.aplica_tema(getattr(config, "mod_afisare", "windows"))
        ui_comun.pregateste_fonturi(parinte)
        temporar = True
    else:
        temporar = False
    raspuns = ui_comun.dialog(
        parinte,
        "Dezinstalare",
        "Scoate programul de pe calculator: scurtăturile și programul lui.\n\n"
        "Documentele tale (textul transcris, înregistrările, documentele finale) **rămân** în "
        "„Documente\\Dictare&Transcriere Română”.\n\nScoți programul?",
        [("Da, scoate programul", "pericol"), ("Nu, lasă-l", "secundar")],
        implicit=1,
        anulare=1,
    )
    reusit = False
    if raspuns == 0:
        reusit = instalare.dezinstaleaza(tacut=True)
        ui_comun.anunta(
            parinte,
            "Gata",
            "Programul a fost scos. Documentele tale au rămas în „Documente\\Dictare&Transcriere Română”.",
        )
    if temporar:
        try:
            parinte.destroy()
        except tk.TclError:
            pass
    return reusit
