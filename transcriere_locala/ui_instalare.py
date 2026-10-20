"""Ecranul de verificare a resurselor și de instalare.

Ordinea este impusă de cerințe:
 1. se afișează cerințele minime și ce are calculatorul (bife verzi / X roșii);
 2. butonul de instalare apare doar dacă tot ce e obligatoriu este îndeplinit;
 3. dacă lipsește doar placa video, se explică mai încet viteza și se cere
    acordul explicit („Continuă oricum” / „Ieși”);
 4. „Sari peste verificare” este o opțiune mică, separată, cu avertisment.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from . import cai, config, instalare, jurnal, resurse, wordcraft
from .constante import DISC_MINIM_CU_GPU_GB, DISC_MINIM_GB, WHISPER_MIN_RAM_GB
from .descarcare import SumaGresita
from .ui_comun import centru, pregateste_fereastra, ruleaza_in_fir

CULOARE_OK = "#1a7f37"
CULOARE_RAU = "#b3261e"
CULOARE_ATENTIE = "#9a6700"
CULOARE_INFO = "#57606a"


class EcranInstalare(tk.Toplevel):
    """Fereastra de verificare + instalare, în limba română."""

    def __init__(self, parinte: tk.Misc | None = None, sari_verificarea: bool = False):
        super().__init__(parinte)
        self.font = pregateste_fereastra(self, "Transcriere locală — pregătire")
        self.raport: resurse.Raport | None = None
        self.sari_verificarea = sari_verificarea
        self.gpu_acceptat = False
        self.instalare_pornita = False
        self.instalare_terminata = False
        self._randuri: list[ttk.Frame] = []
        self._oprire_ceruta = False

        jurnal.adauga_ascultator(self._jurnal_nou)

        self._construieste()
        self.after(150, self.verifica)

    # ------------------------------------------------------------------ construcție

    def _construieste(self) -> None:
        container = ttk.Frame(self, padding=(24, 18))
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Înainte de instalare verificăm calculatorul",
            style="Titlu.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=(
                "Programul transcrie sunetul local, fără internet, cu modelul Whisper "
                "large-v3-turbo. Mai jos vezi de ce are nevoie și ce are acest calculator."
            ),
            style="Subtitlu.TLabel",
            wraplength=880,
            justify="left",
        ).pack(anchor="w", pady=(6, 14))

        # --- lista de cerințe ------------------------------------------------
        cadru_lista = ttk.LabelFrame(container, text=" Cerințe minime ", padding=(14, 10))
        cadru_lista.pack(fill="both", expand=True)

        antet = ttk.Frame(cadru_lista)
        antet.pack(fill="x")
        ttk.Label(antet, text="Cerință", style="Sectiune.TLabel", width=30).pack(side="left")
        ttk.Label(antet, text="Minim necesar", style="Sectiune.TLabel", width=34).pack(side="left")
        ttk.Label(antet, text="Ce are calculatorul", style="Sectiune.TLabel").pack(side="left")

        self.lista = ttk.Frame(cadru_lista)
        self.lista.pack(fill="both", expand=True, pady=(4, 0))

        # --- explicații -----------------------------------------------------
        self.explicatie = tk.Text(
            container,
            height=4,
            wrap="word",
            relief="flat",
            background=self.cget("background"),
            font=(self.font, 10),
            state="disabled",
        )
        self.explicatie.pack(fill="x", pady=(10, 6))

        # --- bara de progres -------------------------------------------------
        self.progres = ttk.Progressbar(
            container, mode="determinate", maximum=100, style="Progres.Horizontal.TProgressbar"
        )
        self.progres.pack(fill="x", pady=(4, 4))
        self.mesaj_progres = ttk.Label(container, text="", style="Info.TLabel", wraplength=880, justify="left")
        self.mesaj_progres.pack(anchor="w")

        self.jurnal_text = tk.Text(
            container, height=5, wrap="none", font=("Consolas", 8), state="disabled"
        )

        # --- butoane ---------------------------------------------------------
        jos = ttk.Frame(container)
        jos.pack(fill="x", pady=(12, 0))

        self.btn_verifica = ttk.Button(
            jos, text="Verifică din nou", style="Normal.TButton", command=self.verifica
        )
        self.btn_verifica.pack(side="left")

        self.btn_iesi = ttk.Button(jos, text="Ieși", style="Normal.TButton", command=self._iesi)
        self.btn_iesi.pack(side="left", padx=(8, 0))

        self.btn_instaleaza = ttk.Button(
            jos,
            text="Confirm, pornește instalarea",
            style="Pornire.TButton",
            command=self.confirma_si_instaleaza,
            state="disabled",
        )
        self.btn_instaleaza.pack(side="right")

        # Opțiunea pentru avansați: mică, discretă, separată de butoanele principale.
        self.btn_sari = ttk.Button(
            container,
            text="Sari peste verificare (doar pentru utilizatori avansați)",
            style="Legatura.TButton",
            command=self.sari_peste_verificare,
        )
        self.btn_sari.pack(anchor="w", pady=(10, 0))

        self.dupa_verificare()

    # ------------------------------------------------------------------ verificare

    def dupa_verificare(self) -> None:
        if self.sari_verificarea:
            self.sari_peste_verificare(initial=True)

    def verifica(self) -> None:
        """Rulează verificarea și redesenează lista."""
        self.btn_verifica.configure(state="disabled")
        self._scrie_explicatie("Verific calculatorul…")
        ruleaza_in_fir(self._verifica_in_fundal)

    def _verifica_in_fundal(self) -> None:
        try:
            raport = resurse.verifica(cai.director_instalare())
        except Exception as exc:  # noqa: BLE001 - orice eroare trebuie arătată simplu
            jurnal.eroare(f"Verificarea resurselor a eșuat: {exc}")
            self.after(0, lambda: self._verificare_esuata(str(exc)))
            return
        self.after(0, lambda: self._afiseaza_raport(raport))

    def _verificare_esuata(self, detaliu: str) -> None:
        self.btn_verifica.configure(state="normal")
        self._scrie_explicatie(
            "Verificarea nu a putut fi făcută complet. Poți încerca din nou sau poți "
            "continua pe răspunderea ta, cu butonul pentru utilizatori avansați."
        )
        jurnal.atentionare(detaliu)

    def _afiseaza_raport(self, raport: resurse.Raport) -> None:
        self.raport = raport
        for rand in self._randuri:
            rand.destroy()
        self._randuri.clear()

        for cerinta in raport.cerinte:
            rand = ttk.Frame(self.lista)
            rand.pack(fill="x", pady=2)
            self._randuri.append(rand)

            culoare = {
                "ok": CULOARE_OK,
                "lipsa": CULOARE_RAU,
                "atentionare": CULOARE_ATENTIE,
                "optioanala": CULOARE_INFO,
            }[cerinta.stare]

            simbol = ttk.Label(rand, text=cerinta.simbol, font=(self.font, 13, "bold"), foreground=culoare, width=3)
            simbol.pack(side="left")
            ttk.Label(rand, text=cerinta.nume, width=26).pack(side="left")
            ttk.Label(rand, text=cerinta.cerinta, width=34, wraplength=250).pack(side="left")
            ttk.Label(rand, text=cerinta.gasit, foreground=culoare, wraplength=330).pack(side="left", fill="x", expand=True)

        # Explicația: fie totul e bine, fie spunem exact ce lipsește.
        if raport.poate_instala:
            text = raport.rezumat() + "\n"
            if not raport.are_gpu:
                text += (
                    "Placa video lipsește sau nu este compatibilă. Transcrierea va rula pe procesor: "
                    + resurse.estimare_viteza(raport)
                )
            else:
                text += resurse.estimare_viteza(raport)
            self.btn_instaleaza.configure(state="normal")
            self.btn_instaleaza.focus_set()
        else:
            linii = ["Nu putem începe instalarea, pentru că lipsește:"]
            for cerinta in raport.blocante:
                linii.append(f"• {cerinta.nume}: ai {cerinta.gasit}. {cerinta.sfat}")
            text = "\n".join(linii)
            self.btn_instaleaza.configure(state="disabled")

        self._scrie_explicatie(text)
        self.btn_verifica.configure(state="normal")

        # Dacă lipsește doar placa video, cerem acordul explicit.
        if raport.doar_gpu_lipsa and not self.gpu_acceptat and not self.instalare_pornita:
            self.after(400, self._intreaba_fara_gpu)

    def _scrie_explicatie(self, text: str) -> None:
        self.explicatie.configure(state="normal")
        self.explicatie.delete("1.0", "end")
        self.explicatie.insert("1.0", text)
        self.explicatie.configure(state="disabled")

    # ------------------------------------------------------------------ fără placă video

    def _intreaba_fara_gpu(self) -> None:
        if self.raport is None:
            return
        estimare = resurse.estimare_viteza(self.raport, 10)
        fereastra = tk.Toplevel(self)
        fereastra.title("Fără accelerare video")
        fereastra.transient(self)
        fereastra.grab_set()
        fereastra.resizable(False, False)
        cadru = ttk.Frame(fereastra, padding=22)
        cadru.pack(fill="both", expand=True)
        ttk.Label(cadru, text="Calculatorul nu are o placă video compatibilă", style="Sectiune.TLabel").pack(anchor="w")
        ttk.Label(
            cadru,
            text=(
                "Programul funcționează și fără placă video, dar transcrierea se face pe "
                "procesor, deci este mai lentă.\n\n" + estimare
            ),
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(8, 14))
        butoane = ttk.Frame(cadru)
        butoane.pack(fill="x")
        ttk.Button(
            butoane,
            text="Continuă oricum",
            style="Mare.TButton",
            command=lambda: (setattr(self, "gpu_acceptat", True), fereastra.destroy()),
        ).pack(side="right")
        ttk.Button(butoane, text="Ieși", style="Normal.TButton", command=self._iesi).pack(side="right", padx=(0, 10))
        centru(fereastra)

    # ------------------------------------------------------------------ sări peste verificare

    def sari_peste_verificare(self, initial: bool = False) -> None:
        """Avertisment clar, apoi pornirea instalării fără verificare."""
        if self.instalare_pornita:
            return
        fereastra = tk.Toplevel(self)
        fereastra.title("Sari peste verificare")
        fereastra.transient(self)
        fereastra.grab_set()
        fereastra.resizable(False, False)
        cadru = ttk.Frame(fereastra, padding=22)
        cadru.pack(fill="both", expand=True)
        ttk.Label(cadru, text="Ești sigur?", style="Sectiune.TLabel").pack(anchor="w")
        ttk.Label(
            cadru,
            text=(
                "Instalarea poate eșua sau programul poate merge foarte încet dacă resursele "
                "nu ajung. Continui pe răspunderea ta?"
            ),
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(8, 16))
        butoane = ttk.Frame(cadru)
        butoane.pack(fill="x")

        def da() -> None:
            fereastra.destroy()
            self.sari_verificarea = True
            jurnal.instalare(
                "Utilizatorul a ales „Sari peste verificare (doar pentru utilizatori avansați)”."
            )
            self._incepe_instalarea()

        def napoi() -> None:
            fereastra.destroy()
            self.sari_verificarea = False
            jurnal.instalare("Utilizatorul a renunțat la „Sari peste verificare”.")
            self.verifica()

        ttk.Button(butoane, text="Da, continui", style="Mare.TButton", command=da).pack(side="right")
        ttk.Button(butoane, text="Înapoi", style="Normal.TButton", command=napoi).pack(side="right", padx=(0, 10))
        centru(fereastra)

    # ------------------------------------------------------------------ instalare

    def confirma_si_instaleaza(self) -> None:
        if self.raport is None or not self.raport.poate_instala:
            return
        self._incepe_instalarea()

    def _incepe_instalarea(self) -> None:
        if self.instalare_pornita:
            return
        self.instalare_pornita = True
        self.btn_instaleaza.configure(state="disabled")
        self.btn_verifica.configure(state="disabled")
        self.btn_sari.configure(state="disabled")
        self.jurnal_text.pack(fill="both", expand=True, pady=(8, 0))
        self._scrie_explicatie("Instalez programul. Nu închide fereastra.")
        self.progres.configure(value=0)
        self.mesaj_progres.configure(text="Pregătesc instalarea…")

        optiuni = instalare.Optiuni(
            cu_gpu=bool(self.raport and self.raport.are_gpu),
            instaleaza_wordcraft=True,
            sari_verificarea=self.sari_verificarea,
        )
        jurnal.instalare(
            "Pornesc instalarea: "
            + ("cu accelerare video" if optiuni.cu_gpu else "pe procesor")
            + f" · arhitectură {cai.arhitectura()}"
            + (" · verificare sărită" if optiuni.sari_verificarea else " · verificare aplicată")
        )
        ruleaza_in_fir(self._instaleaza_in_fundal, optiuni)

    def _instaleaza_in_fundal(self, optiuni: instalare.Optiuni) -> None:
        def progres(mesaj: str, fractiune: float) -> None:
            self.after(0, lambda: self._arata_progres(mesaj, fractiune))

        try:
            rezumat = instalare.instaleaza(optiuni, progres=progres)
        except SumaGresita as exc:
            self.after(0, lambda: self._eroare_suma(exc))
            return
        except instalare.EroareInstalare as exc:
            self.after(0, lambda: self._eroare_instalare(str(exc)))
            return
        except Exception as exc:  # noqa: BLE001
            jurnal.eroare(f"Instalare eșuată neașteptat: {exc}")
            self.after(0, lambda: self._eroare_instalare(str(exc)))
            return
        self.after(0, lambda: self._instalare_gata(rezumat))

    def _arata_progres(self, mesaj: str, fractiune: float) -> None:
        self.progres.configure(value=max(0.0, min(100.0, fractiune * 100)))
        self.mesaj_progres.configure(text=mesaj)

    def _jurnal_nou(self, text: str) -> None:
        """Adaugă o linie în jurnalul vizibil (doar în timpul instalării)."""
        if not self.instalare_pornita:
            return

        def adauga() -> None:
            try:
                self.jurnal_text.configure(state="normal")
                self.jurnal_text.insert("end", text + "\n")
                self.jurnal_text.see("end")
                self.jurnal_text.configure(state="disabled")
            except tk.TclError:
                pass

        try:
            self.after(0, adauga)
        except tk.TclError:
            pass

    def _eroare_suma(self, exc: SumaGresita) -> None:
        self.progres.configure(value=0)
        self.mesaj_progres.configure(text="Instalarea a fost oprită din siguranță.")
        self._scrie_explicatie(
            "Un fișier descărcat nu corespunde cu cel oficial, așa că instalarea a fost "
            "oprită. Acest lucru poate însemna o descărcare întreruptă sau un fișier "
            "modificat pe drum.\n\n"
            f"Fișier: {exc.nume}\nSumă așteptată: {exc.asteptat}\nSumă primită: {exc.gasit}\n\n"
            "Ce poți face: verifică legătura la internet și apasă «Verifică din nou»; "
            "dacă problema apare din nou, descarcă fișierul manual din linkul oficial."
        )
        messagebox.showerror(
            "Instalare oprită",
            "Un fișier descărcat nu este cel oficial, așa că instalarea a fost oprită.\n\n"
            f"Fișier: {exc.nume}",
            parent=self,
        )
        self._permite_repornire()

    def _eroare_instalare(self, mesaj: str) -> None:
        self.progres.configure(value=0)
        self.mesaj_progres.configure(text="Instalarea nu s-a terminat.")
        self._scrie_explicatie(mesaj)
        messagebox.showerror(
            "Instalarea nu s-a terminat",
            mesaj + f"\n\nJurnalul complet: {cai.fisier_jurnal_instalare()}",
            parent=self,
        )
        self._permite_repornire()

    def _permite_repornire(self) -> None:
        self.instalare_pornita = False
        self.btn_verifica.configure(state="normal")
        self.btn_instaleaza.configure(state="normal" if (self.raport and self.raport.poate_instala) else "disabled")
        self.btn_sari.configure(state="normal")

    def _instalare_gata(self, rezumat: dict[str, str]) -> None:
        self.progres.configure(value=100)
        self.mesaj_progres.configure(text="Gata! Programul este instalat.")
        self.instalare_terminata = True
        wordcraft_info = rezumat.get("wordcraft", "")
        nota = ""
        if not wordcraft_info.endswith(".exe"):
            nota = (
                "\n\nWordCraft nu a fost instalat automat. Poți salva documentele ca DOCX "
                "sau ODT și le poți deschide cu orice editor."
            )
        self._scrie_explicatie(
            "Instalarea s-a terminat cu succes. Modelul de transcriere și WordCraft au fost "
            "verificate cu sumele oficiale." + nota
        )
        messagebox.showinfo(
            "Instalare încheiată",
            "Programul este gata de folosire.\n\nSe deschide fereastra principală.",
            parent=self,
        )
        jurnal.scoate_ascultator(self._jurnal_nou)
        radacina = self.master
        self.destroy()
        if radacina is not None:
            radacina.destroy()

    # ------------------------------------------------------------------ ieșire

    def _iesi(self) -> None:
        jurnal.scoate_ascultator(self._jurnal_nou)
        radacina = self.master
        self.destroy()
        if radacina is not None:
            radacina.destroy()


def deschide_aplicatia_principala() -> None:
    """Pornește fereastra principală după instalare."""
    from .ui_principal import AplicatiePrincipala

    fereastra = AplicatiePrincipala()
    fereastra.mainloop()


def porneste(sari_verificarea: bool = False) -> bool:
    """Deschide ecranul de verificare/instalare.

    Întoarce ``True`` dacă instalarea s-a terminat, ca apelantul să poată
    deschide fereastra principală după ce fereastra de instalare se închide.
    """
    radacina = tk.Tk()
    radacina.withdraw()
    ecran = EcranInstalare(radacina, sari_verificarea=sari_verificarea)

    def la_inchidere() -> None:
        jurnal.scoate_ascultator(ecran._jurnal_nou)
        radacina.destroy()

    ecran.protocol("WM_DELETE_WINDOW", la_inchidere)
    radacina.mainloop()
    return ecran.instalare_terminata
