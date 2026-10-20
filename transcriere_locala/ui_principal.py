"""Fereastra principală: alege fișier, dictează, transcrie, salvează, deschide.

Toată munca grea (transcriere, salvare) rulează în fire separate, iar
interfața rămâne mereu răspunsătoare și arată progresul.
"""

from __future__ import annotations

import queue
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import cai, config, documente, jurnal, microfon, motor, wordcraft
from .constante import FORMATE_AUDIO, LIMBI
from .ui_comun import deschide_folder, pregateste_fereastra, ruleaza_in_fir


class AplicatiePrincipala(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.font = pregateste_fereastra(self, "Transcriere locală — dictare și transcriere")
        self.configurare = config.incarca()
        self.evenimente: queue.Queue[tuple[str, object]] = queue.Queue()

        self.fisier_audio: Path | None = None
        self.rezultat: motor.Rezultat | None = None
        self.ultimul_document: Path | None = None
        self.microfon: microfon.Microfon | None = None
        self.motor = motor.MotorWhisper(self.configurare.dispozitiv)
        self.inceput_inregistrare = 0.0
        self.ocupat = False
        self.inregistrez = False

        self._construieste()
        self.after(120, self._proceseaza_evenimente)
        self.protocol("WM_DELETE_WINDOW", self._la_inchidere)
        jurnal.adauga_ascultator(self._jurnal_nou)
        self._verifica_stare_instalare()

    # ------------------------------------------------------------------ construcție

    def _construieste(self) -> None:
        cadru = ttk.Frame(self, padding=(20, 14))
        cadru.pack(fill="both", expand=True)

        # --- titlu ----------------------------------------------------------
        antet = ttk.Frame(cadru)
        antet.pack(fill="x")
        ttk.Label(antet, text="Transcriere locală", style="Titlu.TLabel").pack(side="left")
        self.stare_serviciu = ttk.Label(antet, text="", style="Info.TLabel")
        self.stare_serviciu.pack(side="right")

        ttk.Label(
            cadru,
            text="Totul rulează pe acest calculator. După instalare nu este nevoie de internet.",
            style="Subtitlu.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        # --- rândul 1: fișier + dictează -----------------------------------
        rand1 = ttk.Frame(cadru)
        rand1.pack(fill="x", pady=(0, 8))

        self.btn_fisier = ttk.Button(
            rand1,
            text="Alege fișierul audio",
            style="Mare.TButton",
            command=self.alege_fisier,
        )
        self.btn_fisier.pack(side="left")

        self.eticheta_fisier = ttk.Label(
            rand1, text="Niciun fișier ales", style="Info.TLabel", wraplength=420, justify="left"
        )
        self.eticheta_fisier.pack(side="left", padx=(12, 0), fill="x", expand=True)

        self.btn_dicteaza = ttk.Button(
            rand1, text="Dictează", style="Mare.TButton", command=self.comuta_dictare
        )
        self.btn_dicteaza.pack(side="right")

        # --- rândul 2: transcrie + limbă ------------------------------------
        rand2 = ttk.Frame(cadru)
        rand2.pack(fill="x", pady=(0, 8))

        self.btn_transcrie = ttk.Button(
            rand2, text="Transcrie", style="Pornire.TButton", command=self.transcrie
        )
        self.btn_transcrie.pack(side="left")

        ttk.Label(rand2, text="Limba:").pack(side="left", padx=(18, 6))
        self.limba_var = tk.StringVar()
        etichete = [nume for nume, _ in LIMBI]
        self.limba_box = ttk.Combobox(
            rand2, values=etichete, state="readonly", width=24, textvariable=self.limba_var
        )
        self.limba_box.pack(side="left")
        self.limba_box.current(self._index_limba(self.configurare.limba))
        self.limba_box.bind("<<ComboboxSelected>>", lambda _: self._salveaza_limba())

        self.btn_anuleaza = ttk.Button(
            rand2, text="Oprește transcrierea", style="Normal.TButton", command=self.anuleaza, state="disabled"
        )
        self.btn_anuleaza.pack(side="right")

        # --- progres --------------------------------------------------------
        self.progres = ttk.Progressbar(
            cadru, mode="determinate", maximum=100, style="Progres.Horizontal.TProgressbar"
        )
        self.progres.pack(fill="x", pady=(4, 4))
        self.stare = ttk.Label(cadru, text="Gata de lucru.", style="Info.TLabel", wraplength=940, justify="left")
        self.stare.pack(anchor="w")

        # --- nivel microfon -------------------------------------------------
        self.nivel = tk.Canvas(cadru, height=10, highlightthickness=0, background="#e6e6e6")
        self.nivel.pack(fill="x", pady=(6, 10))
        self.bara_nivel = self.nivel.create_rectangle(0, 0, 0, 10, fill="#2da44e", width=0)

        # --- text -----------------------------------------------------------
        cadru_text = ttk.Frame(cadru)
        cadru_text.pack(fill="both", expand=True)

        self.text = tk.Text(
            cadru_text,
            wrap="word",
            undo=True,
            font=(self.font, 12),
            padx=10,
            pady=8,
            relief="solid",
            borderwidth=1,
        )
        bara = ttk.Scrollbar(cadru_text, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=bara.set)
        self.text.pack(side="left", fill="both", expand=True)
        bara.pack(side="right", fill="y")

        # --- rândul 3: salvare ----------------------------------------------
        rand3 = ttk.Frame(cadru)
        rand3.pack(fill="x", pady=(12, 0))

        self.btn_docx = ttk.Button(
            rand3, text="Salvează ca DOCX", style="Mare.TButton", command=lambda: self.salveaza("docx")
        )
        self.btn_docx.pack(side="left")

        self.btn_odt = ttk.Button(
            rand3, text="Salvează ca ODT", style="Mare.TButton", command=lambda: self.salveaza("odt")
        )
        self.btn_odt.pack(side="left", padx=(10, 0))

        self.btn_wordcraft = ttk.Button(
            rand3, text="Deschide în WordCraft", style="Mare.TButton", command=self.deschide_wordcraft
        )
        self.btn_wordcraft.pack(side="left", padx=(10, 0))

        self.btn_folder = ttk.Button(
            rand3, text="Deschide folderul", style="Normal.TButton", command=self.deschide_folder_iesiri
        )
        self.btn_folder.pack(side="right")

        # --- meniu ----------------------------------------------------------
        meniu = tk.Menu(self)
        meniu_fisier = tk.Menu(meniu, tearoff=0)
        meniu_fisier.add_command(label="Alege fișierul audio…", command=self.alege_fisier)
        meniu_fisier.add_command(label="Salvează ca DOCX…", command=lambda: self.salveaza("docx"))
        meniu_fisier.add_command(label="Salvează ca ODT…", command=lambda: self.salveaza("odt"))
        meniu_fisier.add_separator()
        meniu_fisier.add_command(label="Deschide folderul documentelor", command=self.deschide_folder_iesiri)
        meniu_fisier.add_separator()
        meniu_fisier.add_command(label="Ieși", command=self._la_inchidere)
        meniu.add_cascade(label="Fișier", menu=meniu_fisier)

        meniu_unelte = tk.Menu(meniu, tearoff=0)
        meniu_unelte.add_command(label="Verifică instalarea", command=self.verifica_instalarea)
        meniu_unelte.add_command(label="Eliberează memoria modelului", command=self.elibereaza_memoria)
        meniu_unelte.add_command(label="Deschide jurnalul", command=self.deschide_jurnal)
        meniu_unelte.add_separator()
        meniu_unelte.add_command(label="Setări…", command=self.deschide_setari)
        meniu.add_cascade(label="Unelte", menu=meniu_unelte)

        meniu_ajutor = tk.Menu(meniu, tearoff=0)
        meniu_ajutor.add_command(label="Cum se folosește", command=self.ajutor)
        meniu_ajutor.add_command(label="Despre program", command=self.despre)
        meniu.add_cascade(label="Ajutor", menu=meniu_ajutor)
        self.configure(menu=meniu)

    # ------------------------------------------------------------------ stare

    def _index_limba(self, cod: str) -> int:
        for index, (_, cod_limba) in enumerate(LIMBI):
            if cod_limba == cod:
                return index
        return 0

    def _cod_limba(self) -> str:
        index = self.limba_box.current()
        return LIMBI[index][1] if 0 <= index < len(LIMBI) else "ro"

    def _salveaza_limba(self) -> None:
        self.configurare.limba = self._cod_limba()
        config.salveaza(self.configurare)

    def _verifica_stare_instalare(self) -> None:
        probleme = []
        if not motor.biblioteci_disponibile():
            probleme.append("bibliotecile de transcriere")
        if not cai.fisier_model().exists():
            probleme.append("modelul de transcriere")
        if probleme:
            self.stare_serviciu.configure(
                text="Instalarea nu este completă: lipsește " + " și ".join(probleme) + ".",
                foreground="#b3261e",
            )
        else:
            dispozitiv = "placă video" if self.configurare.dispozitiv == "cuda" else "procesor"
            self.stare_serviciu.configure(
                text=f"Pregătit · transcriere pe {dispozitiv}", foreground="#1a7f37"
            )

    # ------------------------------------------------------------------ evenimente

    def _proceseaza_evenimente(self) -> None:
        try:
            while True:
                tip, date = self.evenimente.get_nowait()
                self._trateaza(tip, date)
        except queue.Empty:
            pass
        if self.inregistrez and self.microfon:
            latime = max(1, self.nivel.winfo_width())
            self.nivel.coords(self.bara_nivel, 0, 0, int(latime * self.microfon.nivel), 10)
            secunde = int(time.time() - self.inceput_inregistrare)
            self.stare.configure(text=f"Înregistrez… {secunde // 60:02d}:{secunde % 60:02d} · apasă din nou pe „Oprește dictarea”")
        self.after(120, self._proceseaza_evenimente)

    def _trateaza(self, tip: str, date: object) -> None:
        if tip == "stare":
            self.stare.configure(text=str(date))
        elif tip == "progres":
            self.progres.configure(value=float(date))  # type: ignore[arg-type]
        elif tip == "text":
            self.text.delete("1.0", "end")
            self.text.insert("1.0", str(date))
        elif tip == "rezultat":
            self.rezultat = date  # type: ignore[assignment]
            self._dupa_transcriere()
        elif tip == "eroare":
            self._afiseaza_eroare(str(date))
        elif tip == "ocupat":
            self._seteaza_ocupat(bool(date))
        elif tip == "inregistrare":
            self._seteaza_inregistrare(bool(date))
        elif tip == "info":
            self.stare.configure(text=str(date))

    def _seteaza_ocupat(self, ocupat: bool) -> None:
        self.ocupat = ocupat
        stare = "disabled" if ocupat else "normal"
        for buton in (self.btn_fisier, self.btn_transcrie, self.btn_docx, self.btn_odt):
            buton.configure(state=stare)
        self.btn_anuleaza.configure(state="normal" if ocupat else "disabled")
        if not ocupat:
            self.progres.configure(value=0)

    def _seteaza_inregistrare(self, activ: bool) -> None:
        self.inregistrez = activ
        if activ:
            self.btn_dicteaza.configure(text="Oprește dictarea")
            self.btn_transcrie.configure(state="disabled")
            self.inceput_inregistrare = time.time()
        else:
            self.btn_dicteaza.configure(text="Dictează")
            self.btn_transcrie.configure(state="normal" if not self.ocupat else "disabled")
            self.nivel.coords(self.bara_nivel, 0, 0, 0, 10)

    def _jurnal_nou(self, text: str) -> None:
        try:
            self.evenimente.put(("info", text))
        except Exception:
            pass

    # ------------------------------------------------------------------ fișier

    def alege_fisier(self) -> None:
        tipuri = [
            ("Fișiere audio", " ".join(f"*{ext}" for ext in FORMATE_AUDIO)),
            ("Toate fișierele", "*.*"),
        ]
        initial = self.configurare.ultimul_folder_audio or str(Path.home())
        cale = filedialog.askopenfilename(
            title="Alege fișierul audio", filetypes=tipuri, initialdir=initial
        )
        if not cale:
            return
        self.fisier_audio = Path(cale)
        self.configurare.ultimul_folder_audio = str(self.fisier_audio.parent)
        config.salveaza(self.configurare)
        nume = self.fisier_audio.name
        marime = self.fisier_audio.stat().st_size / 1024**2
        self.eticheta_fisier.configure(text=f"{nume} ({marime:.1f} MB)")
        self.stare.configure(text="Fișier ales. Apasă „Transcrie”.")
        self.text.delete("1.0", "end")
        self.rezultat = None
        self.ultimul_document = None

    # ------------------------------------------------------------------ dictare

    def comuta_dictare(self) -> None:
        if self.inregistrez:
            self.opreste_dictarea()
        else:
            self.porneste_dictarea()

    def porneste_dictarea(self) -> None:
        if self.ocupat:
            return
        if self.microfon is None:
            self.microfon = microfon.Microfon()
        try:
            self.microfon.porneste()
        except microfon.EroareMicrofon as exc:
            self._afiseaza_eroare(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self._afiseaza_eroare(
                "Nu găsesc microfonul. Verifică dacă e conectat și încearcă din nou.\n"
                f"(detaliu: {exc})"
            )
            return
        self.evenimente.put(("inregistrare", True))
        self.evenimente.put(("stare", "Înregistrez… vorbește, apoi apasă „Oprește dictarea”."))

    def opreste_dictarea(self) -> None:
        if not self.microfon:
            return
        inregistrare = self.microfon.opreste()
        self.evenimente.put(("inregistrare", False))
        if inregistrare.secunde < 0.5:
            self.evenimente.put(("stare", "Înregistrarea a fost prea scurtă. Încearcă din nou."))
            return
        self.evenimente.put(("stare", f"Am înregistrat {inregistrare.secunde:.1f} secunde. Transcriu…"))
        self.fisier_audio = None
        self.eticheta_fisier.configure(text="Înregistrare de la microfon")
        self._porneste_transcrierea(inregistrare.pcm)

    # ------------------------------------------------------------------ transcriere

    def transcrie(self) -> None:
        if self.ocupat:
            return
        if self.rezultat is not None and not self.fisier_audio:
            # Reia transcrierea ultimei înregistrări, dacă există text.
            pass
        if self.fisier_audio is None:
            if self.text.get("1.0", "end").strip():
                self.evenimente.put(("stare", "Textul este deja transcris. Poți salva documentul."))
                return
            messagebox.showinfo(
                "Alege un fișier",
                "Mai întâi alege un fișier audio cu butonul „Alege fișierul audio”, "
                "sau folosește butonul „Dictează”.",
                parent=self,
            )
            return
        self._porneste_transcrierea(self.fisier_audio)

    def _porneste_transcrierea(self, sursa) -> None:
        if not cai.fisier_model().exists():
            self._afiseaza_eroare(
                "Modelul de transcriere lipsește. Rulează din nou instalarea programului "
                "sau folosește „Unelte → Verifică instalarea”."
            )
            return
        self._seteaza_ocupat(True)
        self.progres.configure(value=0)
        self.evenimente.put(("stare", "Pregătesc transcrierea…"))
        ruleaza_in_fir(self._transcrie_in_fundal, sursa)

    def _transcrie_in_fundal(self, sursa) -> None:
        def progres(fractiune: float) -> None:
            self.evenimente.put(("progres", fractiune * 100))

        def faza(mesaj: str) -> None:
            self.evenimente.put(("stare", mesaj))

        try:
            rezultat = self.motor.transcrie(
                sursa, limba=self._cod_limba(), progres=progres, faza=faza
            )
        except motor.Anulat:
            self.evenimente.put(("ocupat", False))
            self.evenimente.put(("stare", "Transcrierea a fost oprită."))
            return
        except motor.EroareMotor as exc:
            self.evenimente.put(("ocupat", False))
            self.evenimente.put(("eroare", str(exc)))
            return
        except Exception as exc:  # noqa: BLE001
            jurnal.eroare(f"Transcriere eșuată: {exc}")
            self.evenimente.put(("ocupat", False))
            self.evenimente.put(
                (
                    "eroare",
                    "Transcrierea nu a putut fi făcută. Verifică fișierul audio și încearcă din nou.\n"
                    f"(detaliu: {exc})",
                )
            )
            return
        self.evenimente.put(("rezultat", rezultat))

    def _dupa_transcriere(self) -> None:
        rezultat = self.rezultat
        self._seteaza_ocupat(False)
        if rezultat is None:
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", rezultat.text)
        if not rezultat.text.strip():
            self.evenimente.put(
                ("stare", "Nu am găsit voce în înregistrare. Verifică volumul microfonului.")
            )
            return
        viteza = ""
        if rezultat.secunde_audio and rezultat.secunde_calcul:
            viteza = (
                f" · {rezultat.secunde_audio:.0f}s audio în {rezultat.secunde_calcul:.0f}s "
                f"({rezultat.dispozitiv})"
            )
        self.evenimente.put(
            (
                "stare",
                f"Gata: {rezultat.cuvinte} cuvinte{viteza}. Poți salva documentul.",
            )
        )
        if self.configurare.salveaza_automat:
            self.salveaza("docx", tacut=True)

    def anuleaza(self) -> None:
        if self.ocupat:
            self.motor.anuleaza()
            self.evenimente.put(("stare", "Opresc transcrierea…"))

    # ------------------------------------------------------------------ salvare

    def salveaza(self, format_dorit: str, tacut: bool = False) -> None:
        text = self.text.get("1.0", "end").strip()
        if not text:
            if not tacut:
                messagebox.showinfo(
                    "Nimic de salvat",
                    "Nu există text. Alege un fișier audio și apasă „Transcrie”, "
                    "sau folosește butonul „Dictează”.",
                    parent=self,
                )
            return

        folder = config.director_iesiri(self.configurare)
        folder.mkdir(parents=True, exist_ok=True)
        sufix = ".docx" if format_dorit == "docx" else ".odt"
        nume_implicit = documente.nume_document(
            self.fisier_audio.stem if self.fisier_audio else "Dictare"
        ) + sufix

        if tacut:
            destinatie = folder / nume_implicit
            contor = 2
            while destinatie.exists():
                destinatie = folder / f"{Path(nume_implicit).stem}_{contor}{sufix}"
                contor += 1
        else:
            cale = filedialog.asksaveasfilename(
                title="Salvează documentul",
                defaultextension=sufix,
                initialdir=str(folder),
                initialfile=nume_implicit,
                filetypes=[("Document Word", "*.docx")] if sufix == ".docx" else [("Document OpenDocument", "*.odt")],
            )
            if not cale:
                return
            destinatie = Path(cale)

        titlu = documente.titlu_din_text(text)
        try:
            if format_dorit == "docx":
                documente.scrie_docx(text, destinatie, titlu=titlu)
            else:
                documente.scrie_odt(text, destinatie, titlu=titlu)
        except OSError as exc:
            self._afiseaza_eroare(
                "Documentul nu a putut fi salvat. Verifică dacă ai dreptul să scrii în folderul "
                "ales și dacă discul nu este plin.\n"
                f"(detaliu: {exc})"
            )
            return

        self.ultimul_document = destinatie
        self.evenimente.put(("stare", f"Salvat: {destinatie}"))
        if not tacut:
            messagebox.showinfo(
                "Document salvat",
                f"Documentul a fost salvat aici:\n{destinatie}",
                parent=self,
            )

    def deschide_wordcraft(self) -> None:
        text = self.text.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo(
                "Nimic de deschis", "Scrie sau transcrie mai întâi un text.", parent=self
            )
            return

        # Dacă documentul nu a fost salvat încă, îl salvăm într-un fișier temporar
        # în folderul de documente, ca WordCraft să îl poată deschide.
        document = self.ultimul_document
        if document is None or not document.exists():
            folder = config.director_iesiri(self.configurare)
            folder.mkdir(parents=True, exist_ok=True)
            document = folder / (documente.nume_document("Transcriere") + ".docx")
            try:
                documente.scrie_docx(text, document, titlu=documente.titlu_din_text(text))
            except OSError as exc:
                self._afiseaza_eroare(
                    "Documentul nu a putut fi pregătit pentru WordCraft. Verifică spațiul "
                    f"liber pe disc. (detaliu: {exc})"
                )
                return
            self.ultimul_document = document

        executabil = self._gaseste_wordcraft()
        if executabil is None:
            raspuns = messagebox.askyesno(
                "WordCraft nu este instalat",
                "Nu găsesc WordCraft pe acest calculator.\n\n"
                "Documentul este salvat, iar tu poți să îl deschizi cu orice editor care "
                "citește fișiere DOCX.\n\n"
                "Vrei să deschizi folderul documentului?",
                parent=self,
            )
            if raspuns:
                deschide_folder(document.parent)
            return
        try:
            wordcraft.deschide(executabil, document)
            self.evenimente.put(("stare", f"WordCraft a fost deschis cu {document.name}."))
        except wordcraft.EroareWordCraft as exc:
            self._afiseaza_eroare(str(exc))

    def _gaseste_wordcraft(self) -> Path | None:
        if self.configurare.wordcraft_executabil:
            cale = Path(self.configurare.wordcraft_executabil)
            if cale.exists():
                return cale
        gasit = wordcraft.gaseste_wordcraft_instalat()
        if gasit:
            self.configurare.wordcraft_executabil = str(gasit)
            config.salveaza(self.configurare)
        return gasit

    def deschide_folder_iesiri(self) -> None:
        deschide_folder(config.director_iesiri(self.configurare))

    # ------------------------------------------------------------------ unelte

    def verifica_instalarea(self) -> None:
        probleme = []
        if not motor.biblioteci_disponibile():
            probleme.append("• lipsesc bibliotecile de transcriere (Whisper, PyTorch)")
        if not cai.fisier_model().exists():
            probleme.append("• lipsește modelul de transcriere")
        if not self._gaseste_wordcraft():
            probleme.append("• WordCraft nu este instalat (opțional)")
        if probleme:
            messagebox.showwarning(
                "Verificarea instalării",
                "Am găsit următoarele probleme:\n\n" + "\n".join(probleme) +
                "\n\nRulează din nou instalarea programului pentru a le rezolva.",
                parent=self,
            )
        else:
            messagebox.showinfo(
                "Verificarea instalării", "Totul este instalat corect.", parent=self
            )

    def elibereaza_memoria(self) -> None:
        self.motor.elibereaza()
        self.evenimente.put(("stare", "Memoria modelului a fost eliberată."))

    def deschide_jurnal(self) -> None:
        cale = cai.fisier_jurnal_aplicatie()
        if not cale.exists():
            messagebox.showinfo("Jurnal", "Jurnalul este gol.", parent=self)
            return
        try:
            import os

            os.startfile(str(cale))  # type: ignore[attr-defined]
        except Exception:
            deschide_folder(cale.parent)

    def deschide_setari(self) -> None:
        fereastra = tk.Toplevel(self)
        fereastra.title("Setări")
        fereastra.transient(self)
        fereastra.grab_set()
        cadru = ttk.Frame(fereastra, padding=20)
        cadru.pack(fill="both", expand=True)

        ttk.Label(cadru, text="Folder pentru documente:", style="Sectiune.TLabel").pack(anchor="w")
        cale_var = tk.StringVar(value=str(config.director_iesiri(self.configurare)))
        rand = ttk.Frame(cadru)
        rand.pack(fill="x", pady=(4, 12))
        ttk.Entry(rand, textvariable=cale_var, width=60).pack(side="left", fill="x", expand=True)

        def alege() -> None:
            aleasa = filedialog.askdirectory(title="Alege folderul pentru documente", parent=fereastra)
            if aleasa:
                cale_var.set(aleasa)

        ttk.Button(rand, text="Alege…", command=alege).pack(side="left", padx=(8, 0))

        salveaza_auto = tk.BooleanVar(value=self.configurare.salveaza_automat)
        ttk.Checkbutton(
            cadru,
            text="Salvează automat documentul DOCX după fiecare transcriere",
            variable=salveaza_auto,
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(
            cadru,
            text=(
                "Modelul de transcriere: Whisper large-v3-turbo, rulat local.\n"
                f"Dispozitiv: {'placă video' if self.configurare.dispozitiv == 'cuda' else 'procesor'}."
            ),
            style="Info.TLabel",
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        def salveaza() -> None:
            self.configurare.director_iesiri = cale_var.get().strip()
            self.configurare.salveaza_automat = bool(salveaza_auto.get())
            config.salveaza(self.configurare)
            fereastra.destroy()
            self.evenimente.put(("stare", "Setările au fost salvate."))

        butoane = ttk.Frame(cadru)
        butoane.pack(fill="x")
        ttk.Button(butoane, text="Salvează", style="Mare.TButton", command=salveaza).pack(side="right")
        ttk.Button(butoane, text="Renunță", style="Normal.TButton", command=fereastra.destroy).pack(
            side="right", padx=(0, 10)
        )

    def ajutor(self) -> None:
        messagebox.showinfo(
            "Cum se folosește",
            "1. Apasă „Alege fișierul audio” și alege o înregistrare (MP3, WAV, M4A, OGG, FLAC).\n"
            "2. Alege limba (implicit română).\n"
            "3. Apasă „Transcrie” și așteaptă bara de progres.\n"
            "4. Corectează textul dacă este nevoie.\n"
            "5. Apasă „Salvează ca DOCX” sau „Salvează ca ODT”.\n\n"
            "Pentru dictare: apasă „Dictează”, vorbește, apoi apasă „Oprește dictarea”. "
            "Transcrierea pornește automat.\n\n"
            "Totul se face pe acest calculator, fără internet.",
            parent=self,
        )

    def despre(self) -> None:
        messagebox.showinfo(
            "Despre program",
            "Transcriere locală 1.0\n\n"
            "Dictare și transcriere 100% offline.\n"
            "Model: Whisper large-v3-turbo (OpenAI, rulat local).\n"
            "Editor compatibil: WordCraft 0.8.0.\n\n"
            f"Documentele se salvează în:\n{config.director_iesiri(self.configurare)}",
            parent=self,
        )

    # ------------------------------------------------------------------ erori

    def _afiseaza_eroare(self, mesaj: str) -> None:
        jurnal.eroare(mesaj)
        self.stare.configure(text=mesaj.splitlines()[0])
        messagebox.showerror("A apărut o problemă", mesaj, parent=self)

    # ------------------------------------------------------------------ închidere

    def _la_inchidere(self) -> None:
        if self.inregistrez and self.microfon:
            self.microfon.anuleaza()
        jurnal.scoate_ascultator(self._jurnal_nou)
        self.destroy()
