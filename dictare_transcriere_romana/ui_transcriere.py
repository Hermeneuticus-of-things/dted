"""Ecranul „Transcriere fișier audio”: patru pași, cu progres și „Anulează”.

Pașii sunt scriși pe ecran, numerotați, exact cum cere cerința:

 1. **Alege fișierul** — îl tragi peste fereastră sau îl alegi cu butonul;
    programul arată durata și cât va dura transcrierea (estimare).
 2. **Spune ce se face cu textul** — se adaugă la textul de pe ecran ori îl
    înlocuiește, și în ce limbă se vorbește.
 3. **Transcrie** — bara de progres, procentul, timpul rămas și textul care
    apare pe rând în editor. „Anulează” oprește imediat, iar textul scris până
    atunci se păstrează.
 4. **Gata** — bannerul „Gata! …” și cele patru butoane (LibreOffice, DOCX,
    ODT, alte formate).

Sunetul se taie în bucăți de 30 de secunde, cu o mică suprapunere, ca textul să
apară pe rând și ca oprirea să fie imediată. Fișierul original nu este niciodată
modificat.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk

from . import (
    biblioteca,
    erori,
    jurnal,
    motor,
    stare as stare_modul,
    text_ro,
    ui_comun,
    ui_drag,
    ui_final,
    ui_internet,
)
from .ui_dictare import fara_suprapunere

#: Cât sunet se transcrie o dată (secunde).
SECUNDE_BUCATA = 30.0
#: Cât sunet se suprapune între bucăți, ca să nu se taie cuvintele.
SECUNDE_SUPRAPUNERE = 2.0
#: Extensiile acceptate, pentru scrisul de pe ecran.
FORMATE = "MP3, WAV, M4A, OGG sau FLAC"


class PaginaTranscriere(tk.Frame):
    """Ecranul „Transcriere fișier audio”."""

    def __init__(self, parinte: tk.Misc, aplicatie):
        super().__init__(parinte, background=ui_comun.CULORI.fundal)
        self.aplicatie = aplicatie
        self.stare = aplicatie.stare
        self.config = aplicatie.config
        self.editor = aplicatie.editor

        self._cale = None
        self._info = None
        self._fir: threading.Thread | None = None
        self._anulat = threading.Event()
        self._motor_local: motor.MotorWhisper | None = None
        self._secunde_audio = 0.0
        self._inceput = 0.0
        self._procesat = 0.0
        self._text_brut_anterior = ""
        self._adauga_la_text = False
        self._limba = "ro"
        self._indicator: ui_internet.IndicatorInternet | None = None
        self._are_gpu = False
        self._construieste()
        threading.Thread(target=self._afla_placa_video, daemon=True).start()

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        C = ui_comun.CULORI
        zona = ui_comun.ZonaDerulare(self, latime_minima=900)
        zona.pack(fill="both", expand=True)
        corp = tk.Frame(zona.interior, background=C.fundal)
        corp.pack(fill="both", expand=True, padx=ui_comun.px(16), pady=ui_comun.px(12))

        rand_titlu = tk.Frame(corp, background=C.fundal)
        rand_titlu.pack(fill="x")
        ui_comun.eticheta(rand_titlu, "Transcriere fișier audio", "titlu").pack(side="left")
        self._indicator = ui_internet.indicator(rand_titlu, self.config)
        self._indicator.pack(side="right")

        ui_comun.eticheta(
            corp,
            "Alegi un fișier audio (MP3, WAV, M4A, OGG sau FLAC) și programul scrie textul. "
            "Transcrierea se face pe acest calculator: fișierul nu pleacă pe internet.",
            "baza",
            latime_bucati=900,
        ).pack(anchor="w", pady=(0, ui_comun.px(10)))

        # ---------- pasul 1: fișierul
        card_1, corp_1 = ui_comun.card(corp, "1. Alege fișierul audio")
        card_1.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        self.zona_drop = tk.Frame(
            corp_1,
            background=C.galben_fundal,
            highlightthickness=ui_comun.px(2),
            highlightbackground=C.chenar,
            bd=0,
        )
        self.zona_drop.pack(fill="x", pady=(0, ui_comun.px(8)))
        self.eticheta_drop = ui_comun.eticheta(
            self.zona_drop,
            "Trage fișierul audio aici, cu mouse-ul, și lasă-l să cadă.",
            "buton",
            fundal=C.galben_fundal,
            latime_bucati=860,
            ancora="center",
        )
        self.eticheta_drop.configure(justify="center")
        self.eticheta_drop.pack(fill="x", padx=ui_comun.px(10), pady=ui_comun.px(28))

        rand_alege = tk.Frame(corp_1, background=C.card)
        rand_alege.pack(fill="x")
        self.buton_alege = ui_comun.Buton(
            rand_alege,
            "Alege fișierul audio",
            self._alege_fisier,
            fel="principal",
            scurtatura="Ctrl+O",
            latime=300,
            inaltime=64,
        )
        self.buton_alege.pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        self.buton_scoate = ui_comun.Buton(
            rand_alege, "Scoate fișierul ales", self._scoate_fisierul, latime=260, inaltime=64
        )
        self.buton_scoate.pack(side="left")
        self.buton_scoate.activeaza(False)

        self.eticheta_fisier = ui_comun.eticheta(
            corp_1, "Nu ai ales încă niciun fișier audio.", "baza", fundal=C.card, latime_bucati=880
        )
        self.eticheta_fisier.pack(anchor="w", pady=(ui_comun.px(8), 0))
        self.eticheta_estimare = ui_comun.eticheta(
            corp_1, "", "baza", fundal=C.card, latime_bucati=880
        )
        self.eticheta_estimare.pack(anchor="w")

        # ---------- pasul 2: ce se face cu textul
        card_2, corp_2 = ui_comun.card(corp, "2. Spune ce se face cu textul")
        card_2.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        rand_text = tk.Frame(corp_2, background=C.card)
        rand_text.pack(fill="x")
        self.buton_inlocuieste = ui_comun.Buton(
            rand_text,
            "Înlocuiește textul de pe ecran",
            lambda: self._seteaza_mod_text(False),
            fel="principal",
            latime=340,
            inaltime=64,
        )
        self.buton_inlocuieste.pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        self.buton_adauga = ui_comun.Buton(
            rand_text,
            "Adaugă la textul de pe ecran",
            lambda: self._seteaza_mod_text(True),
            latime=340,
            inaltime=64,
        )
        self.buton_adauga.pack(side="left")
        ui_comun.eticheta(
            corp_2,
            "„Adaugă” este bun când ai deja un text scris (de exemplu, dictat) și vrei să "
            "adaugi și vorbele din fișier.",
            "mica",
            fundal=C.card,
            latime_bucati=880,
        ).pack(anchor="w", pady=(ui_comun.px(6), 0))

        rand_limba = tk.Frame(corp_2, background=C.card)
        rand_limba.pack(fill="x", pady=(ui_comun.px(10), 0))
        ui_comun.eticheta(rand_limba, "Limba vorbită:", "buton", fundal=C.card).pack(side="left")
        self.buton_ro = ui_comun.Buton(
            rand_limba, "Română", lambda: self._seteaza_limba("ro"), fel="principal", latime=200, inaltime=56
        )
        self.buton_ro.pack(side="left", padx=(ui_comun.px(ui_comun.SPATIU), 0))

        # ---------- pasul 3: transcrierea
        card_3, corp_3 = ui_comun.card(corp, "3. Transcrie")
        card_3.pack(fill="x", pady=(0, ui_comun.px(ui_comun.SPATIU)))
        rand_pornire = tk.Frame(corp_3, background=C.card)
        rand_pornire.pack(fill="x")
        self.buton_incepe = ui_comun.Buton(
            rand_pornire,
            "● Începe transcrierea",
            self._incepe,
            fel="principal",
            scurtatura="Ctrl+T",
            latime=360,
            inaltime=72,
        )
        self.buton_incepe.pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        self.buton_anuleaza = ui_comun.Buton(
            rand_pornire, "Anulează", self._anuleaza, fel="pericol", latime=240, inaltime=72
        )
        self.buton_anuleaza.pack(side="left")
        self.buton_anuleaza.activeaza(False)

        self.bara = ui_comun.BaraProgres(corp_3, latime=880, inaltime=34)
        self.bara.pack(fill="x", pady=(ui_comun.px(12), ui_comun.px(6)))
        rand_progres = tk.Frame(corp_3, background=C.card)
        rand_progres.pack(fill="x")
        self.eticheta_procent = ui_comun.eticheta(rand_progres, "0%", "imens", fundal=C.card)
        self.eticheta_procent.pack(side="left", padx=(0, ui_comun.px(16)))
        self.eticheta_ramas = ui_comun.eticheta(
            rand_progres, "", "baza", fundal=C.card, latime_bucati=600
        )
        self.eticheta_ramas.pack(side="left")
        self.eticheta_text_nou = ui_comun.eticheta(
            corp_3, "", "baza", fundal=C.card, latime_bucati=880
        )
        self.eticheta_text_nou.pack(anchor="w", pady=(ui_comun.px(6), 0))

        # ---------- pasul 4: gata
        self.zona_finala = ui_final.ZonaFinala(corp, self.aplicatie)

        self.zona_editor = tk.Frame(corp, background=C.fundal)
        self.zona_editor.pack(fill="both", expand=True, pady=(ui_comun.px(10), 0))

        rand_final = tk.Frame(corp, background=C.fundal)
        rand_final.pack(fill="x", pady=(ui_comun.px(12), 0))
        ui_comun.Buton(
            rand_final,
            "← Înapoi la început",
            lambda: self.aplicatie.arata_ecran("principal"),
            latime=280,
            inaltime=56,
        ).pack(side="left", padx=(0, ui_comun.px(ui_comun.SPATIU)))
        ui_comun.Buton(
            rand_final, "Ajutor pentru acest ecran", self._ajutor, scurtatura="F1", latime=320, inaltime=56
        ).pack(side="left")

        # Tragerea fișierelor peste fereastră (dacă Windowsul o permite).
        self._drag_pornit = ui_drag.activeaza(self, self._fisiere_trase)
        if not self._drag_pornit:
            self.eticheta_drop.configure(
                text=(
                    "Apasă „Alege fișierul audio” ca să alegi fișierul. "
                    "(Tragerea cu mouse-ul nu este disponibilă pe acest calculator.)"
                )
            )
        self._porneste_ceasurile()

    # ------------------------------------------------------------------ ceasuri

    def _porneste_ceasurile(self) -> None:
        self.after(1000, self._ceas_internet)

    def _ceas_internet(self) -> None:
        try:
            if self._indicator is not None:
                self._indicator.actualizeaza()
        finally:
            self.after(10_000, self._ceas_internet)

    def _ajutor(self) -> None:
        self.aplicatie.arata_ajutor("transcriere")

    def _afla_placa_video(self) -> None:
        """Află dacă există placă video CUDA pentru estimarea duratei (fără să încarce modelul).

        Cu faster-whisper nu mai avem PyTorch, deci verificăm prezența nvcuda.dll
        direct, ca face și MotorWhisper.
        """
        try:
            import ctypes

            ctypes.WinDLL("nvcuda.dll")
            self._are_gpu = True
        except Exception:
            self._are_gpu = False
        if self._info is not None and getattr(self._info, "ok", False):
            self._trimite(self._arata_estimarea)

    def _trimite(self, functie, *argumente) -> None:
        coada = getattr(self.aplicatie, "coada", None)
        if coada is not None:
            coada.trimite(functie, *argumente)
        else:  # pragma: no cover - doar la teste
            functie(*argumente)

    # ------------------------------------------------------------------ pasul 1

    def _alege_fisier(self) -> None:
        cale = ui_comun.alege_fisier_audio(
            self, titlu="Alege fișierul audio de transcris"
        )
        if cale is None:
            return
        self._ia_fisierul(cale)

    def _fisiere_trase(self, cai) -> None:
        if not cai:
            return
        if len(cai) > 1:
            ui_comun.anunta(
                self,
                "Un singur fișier o dată",
                f"Ai lăsat {len(cai)} fișiere. Se ia primul: „{cai[0].name}”. "
                "Pentru restul, trage-le pe rând.",
            )
        self._ia_fisierul(cai[0])

    def _ia_fisierul(self, cale) -> None:
        self.eticheta_drop.configure(
            text=f"Fișier ales: {cale.name}", background=ui_comun.CULORI.verde_fundal
        )
        self.zona_drop.configure(background=ui_comun.CULORI.verde_fundal)
        self._cale = cale
        self.buton_scoate.activeaza(True)
        self.eticheta_fisier.configure(text=f"Se transcrie: {cale.name}")
        self.eticheta_estimare.configure(text="Verific fișierul…")
        threading.Thread(target=self._citeste_informatii, args=(cale,), daemon=True).start()

    def _citeste_informatii(self, cale) -> None:
        info = motor.informatii_audio(cale)
        self._trimite(self._dupa_informatii, info)

    def _dupa_informatii(self, info) -> None:
        self._info = info
        if not info.ok:
            self.eticheta_estimare.configure(text="")
            ui_comun.dialog_eroare(
                self,
                erori.Eroare(
                    ce_s_a_intamplat=info.mesaj or f"Fișierul „{getattr(self._cale, 'name', '')}” nu poate fi folosit.",
                    de_ce="fișierul lipsește, nu este audio sau este deteriorat.",
                    ce_faci_acum=info.ce_fac
                    or f"Alege un fișier audio în formatul {FORMATE}, apoi încearcă din nou.",
                    actiuni=[erori.Actiune("Alege alt fișier", erori.ALEGE_FISIER)],
                ),
                la_actiune=lambda fel: self._alege_fisier() if fel == erori.ALEGE_FISIER else None,
            )
            return
        self._secunde_audio = float(info.secunde or 0.0)
        self._arata_estimarea()

    def _arata_estimarea(self) -> None:
        durata = text_ro.durata_text(self._secunde_audio) if self._secunde_audio else "puțin"
        estimare = text_ro.durata_pentru_transcriere(self._secunde_audio, self._are_gpu)
        self.eticheta_fisier.configure(
            text=(
                f"Se transcrie: {self._cale.name} — sunet de {durata} "
                f"({(self._info.format or '').upper() or 'audio'})"
            )
        )
        self.eticheta_estimare.configure(
            text=f"Transcrierea va dura {estimare} (estimare, depinde de calculator)."
        )

    def _scoate_fisierul(self) -> None:
        if self._fir is not None and self._fir.is_alive():
            ui_comun.anunta(
                self,
                "Transcrierea merge",
                "Apasă mai întâi „Anulează”, apoi poți scoate fișierul.",
            )
            return
        self._cale = None
        self._info = None
        self._secunde_audio = 0.0
        self.zona_drop.configure(background=ui_comun.CULORI.galben_fundal)
        self.eticheta_drop.configure(
            text="Trage fișierul audio aici, cu mouse-ul, și lasă-l să cadă.",
            background=ui_comun.CULORI.galben_fundal,
        )
        self.eticheta_fisier.configure(text="Nu ai ales încă niciun fișier audio.")
        self.eticheta_estimare.configure(text="")
        self.buton_scoate.activeaza(False)

    # ------------------------------------------------------------------ pasul 2

    def _seteaza_mod_text(self, adauga: bool) -> None:
        self._adauga_la_text = bool(adauga)
        self.buton_adauga.seteaza_fel("principal" if adauga else "secundar")
        self.buton_inlocuieste.seteaza_fel("secundar" if adauga else "principal")

    def _seteaza_limba(self, limba: str) -> None:
        self._limba = limba
        self.buton_ro.seteaza_fel("principal" if limba == "ro" else "secundar")

    # ------------------------------------------------------------------ pasul 3

    def _incepe(self) -> None:
        if self._cale is None:
            ui_comun.dialog(
                self,
                "Alege mai întâi fișierul",
                "Nu ai ales încă niciun fișier audio. Îl alegi acum?",
                [("Alege fișierul audio", "principal"), ("Înapoi", "secundar")],
                implicit=0,
                anulare=1,
            )
            if self._cale is None:
                self._alege_fisier()
            if self._cale is None:
                return
        if self._fir is not None and self._fir.is_alive():
            return
        # Internetul (cerința 22) și părțile necesare.
        self.aplicatie.avertizeaza_internet()
        if self._indicator is not None:
            self._indicator.actualizeaza()
        if not motor.biblioteci_disponibile():
            ui_comun.dialog_eroare(
                self,
                erori.Eroare(
                    ce_s_a_intamplat="Părțile de transcriere nu sunt instalate încă.",
                    de_ce="instalarea programului nu s-a terminat până la capăt.",
                    ce_faci_acum=(
                        "Rulează din nou instalarea programului (scurtătura „Instalare "
                        "Dictare&Transcriere Română”), apoi încearcă din nou."
                    ),
                    actiuni=[erori.Actiune("Am înțeles", erori.RENUNTA)],
                ),
            )
            return
        # Textul de pe ecran: se adaugă ori se înlocuiește (după alegerea de la pasul 2).
        if self._adauga_la_text:
            if not self.editor.text_ecran().strip():
                self._adauga_la_text = False
        elif self.editor.text_ecran().strip():
            if not stare_modul.pregateste_schimbarea(
                self, self.stare, "Transcrierea înlocuiește textul de pe ecran."
            ):
                return
            self.editor.seteaza_text("")
            self.zona_finala.ascunde()
        else:
            self.editor.seteaza_text("")
            self.zona_finala.ascunde()

        self._anulat.clear()
        self._procesat = 0.0
        self._text_brut_anterior = ""
        self._inceput = time.monotonic()
        self.stare.sursa = "fisier"
        self.stare.marca = biblioteca.marca_din_nume(self._cale)
        self.stare.segmente = []
        self.bara.seteaza(0.0)
        self.eticheta_procent.configure(text="0%")
        self.eticheta_ramas.configure(text="Pregătesc transcrierea…")
        self.eticheta_text_nou.configure(text="")
        self.buton_incepe.seteaza_text("Se transcrie…")
        self.buton_incepe.activeaza(False)
        self.buton_alege.activeaza(False)
        self.buton_scoate.activeaza(False)
        self.buton_anuleaza.activeaza(True)
        self.aplicatie.bara_stare.arata(
            "Transcriu", f"Se transcrie „{self._cale.name}”. Poți apăsa „Anulează” oricând.", "lucru"
        )
        self._fir = threading.Thread(target=self._transcrie, name="transcriere-fisier", daemon=True)
        self._fir.start()

    def _anuleaza(self) -> None:
        self._anulat.set()
        try:
            self._motor_de_folosit().anuleaza()
        except Exception as exc:
            jurnal.atentionare(f"Oprirea transcrierii a dat eroare: {exc}")
        self.eticheta_ramas.configure(text="Opresc… textul scris până acum se păstrează.")

    def _motor_de_folosit(self) -> motor.MotorWhisper:
        existent = getattr(self.aplicatie, "motor", None)
        if existent is not None:
            return existent
        if self._motor_local is None:
            self._motor_local = motor.MotorWhisper(getattr(self.config, "dispozitiv", "auto"))
        return self._motor_local

    def _transcrie(self) -> None:
        """Taie sunetul în bucăți și le transcrie pe rând, într-un fir de lucru."""
        motor_local = self._motor_de_folosit()
        try:
            sunet = motor.incarca_audio(self._cale)
        except Exception as exc:
            self._trimite(self._termina_cu_eroare, exc)
            return
        total = int(len(sunet))
        if total <= 0:
            self._trimite(
                self._termina_cu_eroare,
                motor.EroareMotor(
                    "Fișierul audio nu are sunet.",
                    ce_fac="Verifică fișierul: se aude ceva când îl asculți? Alege alt fișier.",
                ),
            )
            return
        pas = int((SECUNDE_BUCATA - SECUNDE_SUPRAPUNERE) * 16_000)
        lungime_bucata = int(SECUNDE_BUCATA * 16_000)
        start = 0
        while start < total:
            if self._anulat.is_set():
                break
            sfarsit = min(total, start + lungime_bucata)
            bucata = sunet[start:sfarsit]
            offset = start / 16_000.0
            try:
                rezultat = motor_local.transcrie(
                    bucata,
                    limba=self._limba,
                    progres=self._progres_bucata(offset, len(bucata)),
                )
            except motor.Anulat:
                break
            except Exception as exc:
                self._trimite(self._termina_cu_eroare, exc)
                return
            brut = (rezultat.text or "").strip()
            text = fara_suprapunere(self._text_brut_anterior, brut)
            self._text_brut_anterior = brut
            segmente = [
                motor.Segment(offset + segment.start, offset + segment.end, segment.text, [motor.Cuvant(offset + c.start, offset + c.end, c.text) for c in (getattr(segment, 'cuvinte', None) or [])])
                for segment in (rezultat.segmente or [])
            ]
            self._procesat = sfarsit / 16_000.0
            self._trimite(self._bucata_gata, text, segmente, self._procesat / max(0.1, total / 16_000.0))
            start += pas
        self._trimite(self._gata, self._anulat.is_set())

    def _progres_bucata(self, offset: float, lungime: int):
        """Progresul din interiorul unei bucăți, transformat în progresul total."""
        total = max(0.1, self._secunde_audio)

        def raporteaza(fractiune: float) -> None:
            if self._anulat.is_set():
                return
            cat = offset + max(0.0, min(1.0, fractiune)) * (lungime / 16_000.0)
            self._trimite(self._arata_progres, cat / total)

        return raporteaza

    def _arata_progres(self, fractiune: float) -> None:
        fractiune = max(0.0, min(1.0, fractiune))
        self.bara.seteaza(fractiune)
        self.eticheta_procent.configure(text=f"{int(round(fractiune * 100))}%")
        trecut = time.monotonic() - self._inceput
        if fractiune > 0.02:
            ramas = max(0.0, trecut / fractiune - trecut)
            self.eticheta_ramas.configure(
                text=f"Mai durează {text_ro.durata_text(ramas)} (estimare)."
            )
        else:
            self.eticheta_ramas.configure(text="Măsor cât de repede merge calculatorul…")

    def _bucata_gata(self, text: str, segmente: list, fractiune: float) -> None:
        if segmente:
            self.stare.segmente.extend(segmente)
        if text:
            self.editor.finalizeaza_provizoriu(salveaza=False)
            self.editor.arata_provizoriu(text)
            self.eticheta_text_nou.configure(text=f"Ultimele cuvinte: {text_ro.scurteaza(text, 90)}")
        self._arata_progres(fractiune)

    def _termina_cu_eroare(self, exc: Exception) -> None:
        jurnal.eroare(f"Transcrierea fișierului a eșuat: {exc}")
        self._curata_dupa_transcriere()
        ui_comun.dialog_eroare(
            self,
            erori.din_exceptie(exc, "transcrierea fișierului audio"),
            la_actiune=lambda fel: self._incepe() if fel == erori.INCERCARE_DIN_NOU
            else (self._alege_fisier() if fel == erori.ALEGE_FISIER else None),
        )

    def _gata(self, anulat: bool) -> None:
        """Transcrierea s-a terminat (sau a fost oprită): se păstrează tot textul."""
        self.editor.finalizeaza_provizoriu(salveaza=False)
        self.stare.provizoriu = ""
        self.editor.sincronizeaza(salveaza=False)
        marca = self.stare.marca or biblioteca.marca_din_nume(self._cale)
        self.stare.marca = marca
        self.stare.durata_audio = self._secunde_audio
        text = self.editor.text_ecran().strip()
        if text:
            biblioteca.scrie_text_legat(text, marca)
            self.editor.salveaza_automat()
        try:  # sunetul se păstrează și el, legat de text
            cale_audio = biblioteca.copiaza_audio(self._cale)
            self.stare.audio_cale = cale_audio
        except Exception as exc:
            jurnal.atentionare(f"Sunetul nu a putut fi copiat în folderul Audio: {exc}")
        self._curata_dupa_transcriere()
        if not text:
            self.aplicatie.bara_stare.arata(
                "Text gol",
                "Nu am găsit vorbe în fișierul audio. Verifică dacă se aude ceva în el.",
                "atentie",
            )
            return
        self.zona_finala.arata()
        if anulat:
            self.aplicatie.bara_stare.arata(
                "Oprit",
                "Ai oprit transcrierea. Textul scris până acum este păstrat mai jos.",
                "atentie",
            )
        else:
            self.aplicatie.bara_stare.arata(
                "Gata", "Textul este scris mai jos. Verifică-l și salvează-l.", "bine"
            )
        improspateaza = getattr(self.aplicatie, "reimprospateaza_aspectul", None)
        if improspateaza is not None:
            improspateaza()

    def _curata_dupa_transcriere(self) -> None:
        self.buton_incepe.seteaza_text("● Începe transcrierea")
        self.buton_incepe.activeaza(True)
        self.buton_alege.activeaza(True)
        self.buton_scoate.activeaza(True)
        self.buton_anuleaza.activeaza(False)
        self.eticheta_ramas.configure(text="")

    # ------------------------------------------------------------------ curățenie

    def opreste_tot(self) -> None:
        """Se cheamă la închiderea programului."""
        self._anulat.set()
        try:
            self._motor_de_folosit().anuleaza()
        except Exception:
            pass


def _extensii() -> tuple[str, ...]:
    from .constante import FORMATE_AUDIO

    return tuple(sorted(FORMATE_AUDIO))
