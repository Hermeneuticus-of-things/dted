"""Verificarea sunetului: microfon, difuzor și căști (cerință de accesibilitate).

Fereastra se deschide singură la prima pornire și, după aceea, oricând din
ecranul de început sau din ecranul de dictare. Găsește singură dispozitivele de
pe calculator (fiecare o singură dată), observă când un dispozitiv este scos
sau băgat în timp ce fereastra este deschisă și spune mereu rezultatul în
cuvinte: „Merge”, „Lipsește” sau „Netestat încă”.
"""

from __future__ import annotations

import threading
import tkinter as tk

from . import dispozitive, erori, inregistrare, jurnal, ui_comun

#: Cât durează proba microfonului, în secunde.
SECUNDE_PROBA_MICROFON = 5


class FereastraSunet(tk.Toplevel):
    """Fereastra „Verifică sunetul”, cu trei rânduri și teste."""

    def __init__(self, parinte: tk.Misc, la_terminare=None):
        super().__init__(parinte)
        self.la_terminare = la_terminare
        self.coada = ui_comun.CoadaUI(self)
        self.rezultate = {"microfon": False, "difuzor": False, "casti": False}
        self.stari = {"microfon": "netestat", "difuzor": "netestat", "casti": "netestat"}
        self._dispozitive_vechi: list[str] = []
        self._microfon_activ: inregistrare.Microfon | None = None
        self._test_in_curs = False
        self._randuri: dict[str, dict] = {}

        ui_comun.seteaza_titlu(self, "Verifică sunetul")
        self.configure(background=ui_comun.CULORI.fundal)
        self.transient(parinte)
        self.geometry(f"{ui_comun.px(880)}x{ui_comun.px(640)}")
        self.minsize(ui_comun.px(760), ui_comun.px(520))

        self._construieste()
        self._reimprospateaza()
        ui_comun.centrat(self, latime=880, inaltime=640)
        self.protocol("WM_DELETE_WINDOW", self._inchide)

    # ------------------------------------------------------------------ construire

    def _construieste(self) -> None:
        C = ui_comun.CULORI
        sus = tk.Frame(self, background=C.fundal)
        sus.pack(fill="x", padx=ui_comun.px(14), pady=(ui_comun.px(12), ui_comun.px(4)))
        ui_comun.eticheta(sus, "Verifică sunetul", "titlu", fundal=C.fundal).pack(side="left")
        ui_comun.buton_ajutor(sus, "sunet", latime=170).pack(side="right")

        ui_comun.eticheta(
            self,
            "Apasă butonul de lângă fiecare rând. Verificarea durează sub un minut și nu trimite "
            "nimic pe internet: totul se întâmplă pe calculatorul tău.",
            "baza",
            fundal=C.fundal,
            latime_bucati=820,
        ).pack(anchor="w", padx=ui_comun.px(14))

        self.zona = tk.Frame(self, background=C.fundal)
        self.zona.pack(fill="both", expand=True, padx=ui_comun.px(14), pady=ui_comun.px(8))

        jos = tk.Frame(self, background=C.fundal)
        jos.pack(fill="x", padx=ui_comun.px(14), pady=(0, ui_comun.px(12)))
        ui_comun.Buton(
            jos, "Am terminat verificarea", self._inchide, fel="principal",
            latime=320, inaltime=64,
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(
            jos, "Caută din nou dispozitivele", self._reimprospateaza, latime=300, inaltime=48
        ).pack(side="left", padx=(0, ui_comun.px(8)))
        ui_comun.Buton(
            jos, "Rezolvă driverele lipsă", self._drivere, latime=280, inaltime=48
        ).pack(side="left")

    # ------------------------------------------------------------------ dispozitive

    def _reimprospateaza(self) -> None:
        """Recitește dispozitivele și desenează cele trei rânduri."""
        microfoane, iesiri = dispozitive.listeaza()
        casti = dispozitive.casti()
        difuzoare = [dispozitiv for dispozitiv in iesiri if dispozitiv not in casti]
        self._microfon = microfoane[0] if microfoane else None
        self._difuzor = difuzoare[0] if difuzoare else (iesiri[0] if iesiri else None)
        self._casti = casti[0] if casti else None

        nume_noi = [
            f"in:{getattr(dispozitiv, 'nume_brut', '')}" for dispozitiv in microfoane
        ] + [f"out:{getattr(dispozitiv, 'nume_brut', '')}" for dispozitiv in iesiri]
        if self._dispozitive_vechi and nume_noi != self._dispozitive_vechi:
            jurnal.info("Dispozitivele de sunet s-au schimbat; lista se reîncarcă.")
        self._dispozitive_vechi = nume_noi

        for copil in self.zona.winfo_children():
            copil.destroy()
        self._randuri = {}

        self._rand(
            "microfon",
            "🎤  Microfon",
            self._microfon,
            "Testează microfonul (5 secunde)",
            self._testeaza_microfon,
        )
        self._rand(
            "difuzor",
            "🔊  Difuzor",
            self._difuzor,
            "Testează difuzorul",
            self._testeaza_difuzor,
        )
        self._rand(
            "casti",
            "🎧  Căști",
            self._casti,
            "Testează căștile (stânga, apoi dreapta)",
            self._testeaza_casti,
        )

        if self._microfon is None and self._difuzor is None:
            ui_comun.eticheta(
                self.zona,
                "Pe acest calculator nu se vede niciun dispozitiv de sunet. Probabil lipsește "
                "driverul de sunet. Apasă „Rezolvă driverele lipsă” și urmează pașii de acolo.",
                "baza",
                fundal=ui_comun.CULORI.galben_fundal,
                latime_bucati=800,
            ).pack(anchor="w", pady=ui_comun.px(10))

    def _rand(self, cheie: str, titlu: str, dispozitiv, text_buton: str, comanda) -> None:
        C = ui_comun.CULORI
        card, corp = ui_comun.card(self.zona, "")
        card.pack(fill="x", pady=ui_comun.px(6))
        rand_sus = tk.Frame(corp, background=C.card)
        rand_sus.pack(fill="x")
        ui_comun.eticheta(rand_sus, titlu, "subtitlu", fundal=C.card).pack(side="left")
        stare_cuvant = {
            "netestat": "Netestat încă",
            "merge": "Merge",
            "lipseste": "Lipsește",
            "nu_merge": "Nu merge",
        }[self.stari[cheie] if dispozitiv is not None else "lipseste"]
        if dispozitiv is None and self.stari[cheie] == "netestat":
            stare_cuvant = "Lipsește"
        pictograma = {"netestat": "•", "merge": "✔", "lipseste": "✘", "nu_merge": "✘"}[
            self.stari[cheie] if dispozitiv is not None else "lipseste"
        ]
        culoare = {
            "netestat": C.text_secundar,
            "merge": C.verde_text,
            "lipseste": C.rosu_text,
            "nu_merge": C.rosu_text,
        }[self.stari[cheie] if dispozitiv is not None else "lipseste"]
        eticheta_stare = tk.Label(
            rand_sus,
            text=f"{pictograma}  {stare_cuvant}",
            font=ui_comun.fonturi().buton,
            background=C.card,
            foreground=culoare,
        )
        eticheta_stare.pack(side="right")

        if dispozitiv is not None:
            ui_comun.eticheta(
                corp, getattr(dispozitiv, "nume", "") or getattr(dispozitiv, "nume_brut", ""),
                "baza", fundal=C.card, latime_bucati=760,
            ).pack(anchor="w", pady=(ui_comun.px(2), ui_comun.px(6)))
            buton = ui_comun.Buton(corp, text_buton, comanda, latime=380, inaltime=48)
            buton.pack(anchor="w")
        else:
            ui_comun.eticheta(
                corp,
                "Nu am găsit acest dispozitiv. Poate fi scos din calculator sau poate lipsește "
                "driverul lui. Apasă „Rezolvă driverele lipsă” dacă este vorba de sunet.",
                "baza", fundal=C.card, latime_bucati=760,
            ).pack(anchor="w")
            buton = None
        self._randuri[cheie] = {
            "stare": eticheta_stare,
            "buton": buton,
            "nume": getattr(dispozitiv, "nume", "") if dispozitiv is not None else "",
        }

    def _arata_stare(self, cheie: str, stare: str) -> None:
        date = self._randuri.get(cheie)
        if not date:
            return
        self.stari[cheie] = stare
        text = {"netestat": "•  Netestat încă", "merge": "✔  Merge", "lipseste": "✘  Lipsește",
                "nu_merge": "✘  Nu merge"}[stare]
        culoare = {
            "netestat": ui_comun.CULORI.text_secundar,
            "merge": ui_comun.CULORI.verde_text,
            "lipseste": ui_comun.CULORI.rosu_text,
            "nu_merge": ui_comun.CULORI.rosu_text,
        }[stare]
        date["stare"].configure(text=text, foreground=culoare)

    # ------------------------------------------------------------------ probe

    def _testeaza_microfon(self) -> None:
        if self._test_in_curs or self._microfon is None:
            return
        self._test_in_curs = True
        self._arata_stare("microfon", "netestat")
        self._randuri["microfon"]["stare"].configure(text="●  Ascult…")

        oprire = threading.Event()

        def nivel() -> float:
            microfon = self._microfon_activ
            return float(getattr(microfon, "nivel", 0.0) or 0.0)

        def numara() -> None:
            if oprire.is_set():
                return
            ramas = getattr(numara, "ramas", SECUNDE_PROBA_MICROFON)
            ramas -= 1
            numara.ramas = ramas
            if ramas <= 0:
                return
            try:
                self._randuri["microfon"]["stare"].configure(text=f"●  Vorbește acum… {ramas}")
            except tk.TclError:
                return
            self.after(1000, numara)

        def lucru() -> None:
            microfon = inregistrare.Microfon(self._microfon)
            try:
                microfon.porneste()
            except Exception as exc:
                jurnal.atentionare(f"Proba microfonului nu a pornit: {exc}")
                self.coada.trimite(self._microfon_nu_merge, str(exc))
                return
            self._microfon_activ = microfon
            import time

            nivel_maxim = 0.0
            pas = 0.1
            total = int(SECUNDE_PROBA_MICROFON / pas)
            bucati = []
            for _ in range(total):
                if oprire.is_set():
                    break
                nivel_maxim = max(nivel_maxim, microfon.nivel)
                bucati.append(microfon.nivel)
                time.sleep(pas)
            try:
                inregistrare_obtinuta = microfon.opreste()
            except Exception:
                inregistrare_obtinuta = None
            self._microfon_activ = None
            self.coada.trimite(self._dupa_proba, inregistrare_obtinuta, nivel_maxim)

        self.after(1000, numara)
        threading.Thread(target=lucru, name="proba-microfon", daemon=True).start()

    def _microfon_nu_merge(self, detalii: str) -> None:
        self._test_in_curs = False
        self._arata_stare("microfon", "lipseste")
        ui_comun.dialog_eroare(self, erori.fara_microfon(detalii), la_actiune=self._dupa_eroare_microfon)

    def _dupa_eroare_microfon(self, fel: str) -> None:
        from . import sisteme

        if fel == erori.SETARI_MICROFON:
            sisteme.deschide_setari_microfon()
        elif fel in (erori.INCERCARE_DIN_NOU,):
            self._testeaza_microfon()

    def _dupa_proba(self, inregistrare_obtinuta, nivel_maxim: float) -> None:
        """Redă ce s-a înregistrat și întreabă dacă s-a auzit clar."""
        self._test_in_curs = False
        if inregistrare_obtinuta is None or getattr(inregistrare_obtinuta, "pcm", None) is None:
            self._microfon_nu_merge("Înregistrarea nu a putut fi citită.")
            return
        if nivel_maxim < 0.01:
            self._arata_stare("microfon", "nu_merge")
            rezultat = ui_comun.dialog(
                self,
                "Nu am auzit nimic",
                "În cele 5 secunde nu am primit niciun sunet de la microfon.",
                [("Încearcă din nou", "principal"), ("Am înțeles", "secundar")],
                implicit=0,
                anulare=1,
            )
            if rezultat == 0:
                self._testeaza_microfon()
            return
        self._arata_stare("microfon", "netestat")
        self._randuri["microfon"]["stare"].configure(text="▶  Se redă ce ai spus…")
        try:
            inregistrare.reda(inregistrare_obtinuta.pcm, inregistrare_obtinuta.rata,
                              self._difuzor or self._casti, asteapta=True)
        except Exception as exc:
            jurnal.atentionare(f"Redarea probei nu a reușit: {exc}")
        raspuns = ui_comun.dialog(
            self,
            "Te-ai auzit clar?",
            "S-a auzit înregistrarea pe care tocmai ai făcut-o?",
            [("Da, m-am auzit", "principal"), ("Nu, nu m-am auzit", "secundar")],
            implicit=0,
            anulare=1,
        )
        if raspuns == 0:
            self.rezultate["microfon"] = True
            self._arata_stare("microfon", "merge")
            return
        self._arata_stare("microfon", "nu_merge")
        pasi = ui_comun.dialog(
            self,
            "Microfonul nu se aude bine",
            "Probabil una dintre aceste situații:\n\n"
            "•  Microfonul este pus pe „mut” sau este prea departe;\n"
            "•  Windows nu dă voie programelor să folosească microfonul;\n"
            "•  Microfonul ales nu este cel la care vorbești (poate fi alt dispozitiv conectat).\n\n"
            "Ce faci acum: apasă „Deschide setările Windows pentru microfon”, îngăduie accesul, "
            "apoi „Încearcă din nou”.",
            [
                ("Deschide setările Windows pentru microfon", "principal"),
                ("Încearcă din nou", "secundar"),
                ("Am înțeles", "secundar"),
            ],
            implicit=0,
            anulare=2,
            detalii=str(nivel_maxim),
        )
        if pasi == 0:
            from . import sisteme

            sisteme.deschide_setari_microfon()
        elif pasi == 1:
            self._testeaza_microfon()

    def _testeaza_difuzor(self) -> None:
        if self._difuzor is None:
            self._arata_stare("difuzor", "lipseste")
            return
        if self._test_in_curs:
            return
        self._test_in_curs = True
        self._randuri["difuzor"]["stare"].configure(text="▶  Se aude un sunet scurt…")

        def lucru() -> None:
            fel = "stereo"
            try:
                fel = inregistrare.reda_proba("stereo", self._difuzor, asteapta=True)
            except Exception as exc:
                jurnal.atentionare(f"Redarea probei pentru difuzor a eșuat: {exc}")
            self.coada.trimite(self._dupa_proba_difuzor, fel)

        threading.Thread(target=lucru, name="proba-difuzor", daemon=True).start()

    def _dupa_proba_difuzor(self, fel: str) -> None:
        self._test_in_curs = False
        if ui_comun.intreaba(
            self, "Ai auzit sunetul?", "S-a auzit un sunet scurt, ca un clopoțel, din difuzor?"
        ):
            self.rezultate["difuzor"] = True
            self._arata_stare("difuzor", "merge")
        else:
            self._arata_stare("difuzor", "nu_merge")
            raspuns = ui_comun.dialog(
                self,
                "Nu s-a auzit nimic",
                "Probabil difuzorul este oprit (mut), volumul este la zero, sau ieșirea aleasă "
                "nu este cea la care asculți.\n\nCe faci acum: verifică volumul din colțul din "
                "dreapta jos al ecranului, apoi apasă „Încearcă din nou”.",
                [("Încearcă din nou", "principal"), ("Am înțeles", "secundar")],
                implicit=0,
                anulare=1,
            )
            if raspuns == 0:
                self._testeaza_difuzor()
            return
        if fel == "mono":
            ui_comun.anunta(
                self,
                "Ieșirea are un singur canal",
                "Această ieșire de sunet are un singur canal, așa că nu se poate verifica separat "
                "stânga și dreapta. Sunetul se aude în ambele părți, dacă folosești difuzorul.",
            )

    def _testeaza_casti(self) -> None:
        if self._casti is None:
            self._arata_stare("casti", "lipseste")
            ui_comun.anunta(
                self,
                "Nu am găsit căști",
                "Căștile nu se văd acum pe calculator. Dacă vrei să le verifici, conectează-le și "
                "apasă „Caută din nou dispozitivele”.",
            )
            return
        if self._test_in_curs:
            return
        self._test_in_curs = True

        def lucru() -> None:
            rezultat_mono = False
            try:
                fel = inregistrare.reda_proba("stanga", self._casti, asteapta=True)
                rezultat_mono = fel == "mono"
            except Exception as exc:
                jurnal.atentionare(f"Proba căștilor a eșuat: {exc}")
            self.coada.trimite(self._dupa_proba_casti, rezultat_mono)

        self._randuri["casti"]["stare"].configure(text="▶  Se aude în stânga…")
        threading.Thread(target=lucru, name="proba-casti", daemon=True).start()

    def _dupa_proba_casti(self, mono: bool) -> None:
        if mono:
            self._test_in_curs = False
            ui_comun.anunta(
                self,
                "Ieșirea are un singur canal",
                "Această ieșire are un singur canal, așa că nu se poate verifica separat stânga și "
                "dreapta. Sunetul s-a auzit în ambele părți (dacă ai căștile puse).",
            )
            self._arata_stare("casti", "merge")
            self.rezultate["casti"] = True
            return
        prima = ui_comun.intreaba(
            self,
            "Ai auzit în urechea stângă?",
            "Sunetul s-a auzit doar în urechea stângă a căștilor?",
        )
        if not prima:
            self._test_in_curs = False
            self._arata_stare("casti", "nu_merge")
            ui_comun.anunta(
                self,
                "Căștile nu s-au auzit în stânga",
                "Verifică dacă ștecherul căștilor este băgat bine și dacă volumul nu este la zero. "
                "Poți apăsa din nou „Testează căștile”.",
            )
            return

        def lucru2() -> None:
            try:
                inregistrare.reda_proba("dreapta", self._casti, asteapta=True)
            except Exception as exc:
                jurnal.atentionare(f"Proba căștilor (dreapta) a eșuat: {exc}")
            self.coada.trimite(self._dupa_proba_casti_dreapta)

        self._randuri["casti"]["stare"].configure(text="▶  Se aude în dreapta…")
        threading.Thread(target=lucru2, name="proba-casti-dreapta", daemon=True).start()

    def _dupa_proba_casti_dreapta(self) -> None:
        self._test_in_curs = False
        if ui_comun.intreaba(
            self,
            "Ai auzit în urechea dreaptă?",
            "Sunetul s-a auzit doar în urechea dreaptă a căștilor?",
        ):
            self.rezultate["casti"] = True
            self._arata_stare("casti", "merge")
        else:
            self._arata_stare("casti", "nu_merge")
            ui_comun.anunta(
                self,
                "Căștile nu s-au auzit în dreapta",
                "Probabil căștile sunt doar pe o ureche sau cablul nu este băgat bine. "
                "Poți încerca din nou oricând.",
            )

    # ------------------------------------------------------------------ drivere / închidere

    def _drivere(self) -> None:
        from . import ui_drivere

        ui_drivere.fereastra_lipsesc_drivere(self)

    def _inchide(self) -> None:
        if self._microfon_activ is not None:
            try:
                self._microfon_activ.anuleaza()
            except Exception:
                pass
        self.coada.opreste()
        if self.la_terminare is not None:
            try:
                self.la_terminare(dict(self.rezultate))
            except Exception:
                pass
        try:
            self.destroy()
        except tk.TclError:
            pass


def fereastra_verificare(parinte: tk.Misc, la_terminare=None) -> dict:
    """Deschide verificarea sunetului și întoarce ce s-a testat."""
    fereastra = FereastraSunet(parinte, la_terminare)
    fereastra.wait_window()
    return dict(fereastra.rezultate)


def microfon_merge() -> bool:
    """Adevărat dacă există cel puțin un microfon (fără să testeze sunetul)."""
    try:
        return bool(dispozitive.microfoane())
    except Exception:
        return False
