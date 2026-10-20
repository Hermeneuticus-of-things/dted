"""Progres vizibil peste tot: bară, procent, pasul curent, timp rămas, [Oprește].

Cerințele 25 și 26 spun că nicio operațiune mai lungă de 2 secunde nu are voie
să lase utilizatorul fără explicații. Modulul acesta este folosit de toate
ecranele care au de așteptat:

* bara de progres care se mișcă;
* procentul („37%”);
* pasul curent, în cuvinte simple („Pasul 2 din 5: descarc modelul”);
* timpul rămas, calculat din viteza reală a calculatorului; cât timp nu se poate
  estima, scrie „Calculez cât mai durează…”, niciodată un număr inventat;
* semnul că programul trăiește (un indicator care se mișcă neîncetat);
* mesajele de încetinire (după 60 de secunde) și de posibilă blocare (după 5
  minute), cu buton de oprire și cu explicație;
* butonul mare [Oprește], care întreabă mai întâi „Sigur vrei să oprești?”.

Toată munca grea stă în alte fire de lucru: fereastra răspunde mereu la clicuri.
"""

from __future__ import annotations

import time
import tkinter as tk

from . import jurnal, text_ro, ui_comun

#: După câte secunde fără nicio schimbare spunem că merge mai încet.
SECUNDE_INCETINIRE = 60.0
#: După câte secunde fără nicio schimbare spunem că pare blocat.
SECUNDE_BLOCARE = 300.0
#: La cât timp se mișcă indicatorul „programul trăiește”.
MILLISECUNDE_ANIMATIE = 120


class ZonaProgres(tk.Frame):
    """Bara de progres cu tot ce trebuie ca omul să știe ce se întâmplă."""

    def __init__(
        self,
        parinte: tk.Misc,
        titlu: str = "",
        la_oprire=None,
        latime: int = 880,
        cu_oprire: bool = True,
    ):
        super().__init__(parinte, background=ui_comun.CULORI.card)
        self._la_oprire = la_oprire
        self._latime = latime
        self._inceput = time.monotonic()
        self._ultima_schimbare = time.monotonic()
        self._fractiune = 0.0
        self._pas = ""
        self._cate_pasi = 0
        self._pas_curent = 0
        self._ruleaza = False
        self._animatie = 0
        self._sens = 1
        self._mesaj_incetinire = ""
        self._id_tic = None

        C = ui_comun.CULORI
        if titlu:
            ui_comun.eticheta(self, titlu, "subtitlu", fundal=C.card, latime_bucati=latime).pack(anchor="w")
        rand_sus = tk.Frame(self, background=C.card)
        rand_sus.pack(fill="x", pady=(ui_comun.px(6), 0))

        self.bara = ui_comun.BaraProgres(rand_sus, latime=latime - 280, inaltime=34)
        self.bara.pack(side="left", fill="x", expand=True)
        self.buton_opreste_dialog = None
        if cu_oprire:
            self.buton_opreste = ui_comun.Buton(
                rand_sus, "■ Oprește", self.cere_oprirea, fel="pericol", latime=240, inaltime=64
            )
            self.buton_opreste.pack(side="left", padx=(ui_comun.px(ui_comun.SPATIU), 0))
        else:
            self.buton_opreste = None

        rand_jos = tk.Frame(self, background=C.card)
        rand_jos.pack(fill="x", pady=(ui_comun.px(8), 0))
        self.eticheta_procent = ui_comun.eticheta(rand_jos, "0%", "imens", fundal=C.card)
        self.eticheta_procent.pack(side="left", padx=(0, ui_comun.px(16)))
        coloana = tk.Frame(rand_jos, background=C.card)
        coloana.pack(side="left", fill="x", expand=True)
        self.eticheta_pas = ui_comun.eticheta(coloana, "", "buton", fundal=C.card, latime_bucati=600)
        self.eticheta_pas.pack(anchor="w")
        self.eticheta_ramas = ui_comun.eticheta(coloana, "", "baza", fundal=C.card, latime_bucati=600)
        self.eticheta_ramas.pack(anchor="w")

        # Semnul că programul trăiește: o bucată care alunecă neîncetat.
        self.vietati = tk.Canvas(
            self,
            width=ui_comun.px(300),
            height=ui_comun.px(14),
            background=C.bara_goala,
            highlightthickness=ui_comun.px(1),
            highlightbackground=C.chenar,
            bd=0,
        )
        self.vietati.pack(anchor="w", pady=(ui_comun.px(8), 0))
        self._bucata_vietati = self.vietati.create_rectangle(
            0, 0, ui_comun.px(60), ui_comun.px(14), fill=C.principal, width=0
        )

        self.anunt = ui_comun.Banner(self, "atentie")
        self.rand_anunt = tk.Frame(self, background=C.card)
        self.buton_explica = ui_comun.Buton(
            self.rand_anunt,
            "De ce durează atât?",
            self._explica_intarzierea,
            latime=300,
            inaltime=56,
            imagine=None,
        )
        self.buton_explica.pack(side="left")

    # ------------------------------------------------------------------ date

    def seteaza(
        self,
        fractiune: float,
        pas: str = "",
        pas_curent: int | None = None,
        cate_pasi: int | None = None,
    ) -> None:
        """Arată unde suntem. Se cheamă des, din orice fir, prin ``CoadaUI``."""
        self._fractiune = max(0.0, min(1.0, float(fractiune)))
        self._ultima_schimbare = time.monotonic()
        self.bara.seteaza(self._fractiune)
        self.eticheta_procent.configure(text=f"{int(round(self._fractiune * 100))}%")
        if pas_curent is not None:
            self._pas_curent = int(pas_curent)
        if cate_pasi is not None:
            self._cate_pasi = int(cate_pasi)
        if pas:
            self._pas = pas
        self._scrie_pasul()
        self._scrie_timpul_ramas()
        if self._mesaj_incetinire:
            self.anunt.pack_forget()
            self.rand_anunt.pack_forget()
            self._mesaj_incetinire = ""

    def seteaza_pas(self, pas: str, pas_curent: int | None = None, cate_pasi: int | None = None) -> None:
        """Schimbă doar textul pasului curent (fără să atingă bara)."""
        self._pas = pas
        if pas_curent is not None:
            self._pas_curent = int(pas_curent)
        if cate_pasi is not None:
            self._cate_pasi = int(cate_pasi)
        self._ultima_schimbare = time.monotonic()
        self._scrie_pasul()

    def _scrie_pasul(self) -> None:
        if self._cate_pasi and self._pas_curent:
            text = f"Pasul {self._pas_curent} din {self._cate_pasi}"
            if self._pas:
                text += f": {self._pas}"
        else:
            text = self._pas
        self.eticheta_pas.configure(text=text or "Se pregătește…")

    def _scrie_timpul_ramas(self) -> None:
        trecut = time.monotonic() - self._inceput
        if self._fractiune > 0.02 and trecut > 1.5:
            ramas = max(0.0, trecut / self._fractiune - trecut)
            if ramas < 2.0:
                self.eticheta_ramas.configure(text="Aproape gata…")
                return
            self.eticheta_ramas.configure(
                text=f"Mai durează aproximativ {text_ro.durata_text(ramas)} (estimare din viteza calculatorului)."
            )
        else:
            self.eticheta_ramas.configure(text="Calculez cât mai durează…")

    def descriere_scurta(self) -> str:
        """Un text de o linie, pentru linia de stare de jos."""
        procent = f"{int(round(self._fractiune * 100))}%"
        return f"{procent} · {self._pas or 'se lucrează'}"

    # ------------------------------------------------------------------ pornire / oprire

    def incepe(self, pas: str = "", pas_curent: int | None = None, cate_pasi: int | None = None) -> None:
        """Pornește o operațiune: curăță tot și începe să măsoare timpul."""
        self._inceput = time.monotonic()
        self._ultima_schimbare = time.monotonic()
        self._fractiune = 0.0
        self._pas = pas
        self._pas_curent = int(pas_curent or 0)
        self._cate_pasi = int(cate_pasi or 0)
        self._mesaj_incetinire = ""
        self.bara.seteaza(0.0)
        self.eticheta_procent.configure(text="0%")
        self._scrie_pasul()
        self.eticheta_ramas.configure(text="Calculez cât mai durează…")
        self.anunt.pack_forget()
        self.rand_anunt.pack_forget()
        self._ruleaza = True
        if self.buton_opreste is not None:
            self.buton_opreste.activeaza(True)
        if self._id_tic is None:
            self._tic()

    def gata(self, mesaj: str = "") -> None:
        """Operațiunea s-a terminat: bara devine plină, indicatorul se oprește."""
        self._ruleaza = False
        self.bara.seteaza(1.0)
        self.eticheta_procent.configure(text="100%")
        self.eticheta_ramas.configure(text=mesaj or f"Gata! A durat {self.durata_text()}.")
        if self.buton_opreste is not None:
            self.buton_opreste.activeaza(False)
        self.anunt.pack_forget()
        self.rand_anunt.pack_forget()

    def reseteaza(self) -> None:
        """Ascunde tot (operațiunea nu mai rulează)."""
        self._ruleaza = False
        self._fractiune = 0.0
        self.bara.seteaza(0.0)
        self.eticheta_procent.configure(text="0%")
        self.eticheta_pas.configure(text="")
        self.eticheta_ramas.configure(text="")
        self.anunt.pack_forget()
        self.rand_anunt.pack_forget()
        if self.buton_opreste is not None:
            self.buton_opreste.activeaza(False)

    def durata(self) -> float:
        return max(0.0, time.monotonic() - self._inceput)

    def durata_text(self) -> str:
        return text_ro.durata_text(self.durata())

    def cere_oprirea(self) -> None:
        """Butonul [Oprește]: întreabă mai întâi, apoi oprește curat."""
        if not self._ruleaza:
            return
        raspuns = ui_comun.dialog(
            self,
            "Sigur vrei să oprești?",
            "Se oprește lucrul acum. Ce s-a scris sau s-a descărcat până acum se păstrează.",
            [("Da, oprește", "principal"), ("Nu, continuă", "secundar")],
            implicit=1,
            anulare=1,
        )
        if raspuns != 0:
            return
        jurnal.info("Utilizatorul a oprit operațiunea în curs.")
        self.eticheta_ramas.configure(text="Opresc… durează câteva secunde.")
        if self._la_oprire is not None:
            try:
                self._la_oprire()
            except Exception as exc:
                jurnal.eroare(f"Oprirea nu a putut fi făcută curat: {exc}")

    # ------------------------------------------------------------------ animație și paznic

    def _tic(self) -> None:
        self._id_tic = None
        try:
            self._animeaza()
            if self._ruleaza:
                self._paznic()
                self._scrie_timpul_ramas()
        except tk.TclError:
            return
        self._id_tic = self.after(MILLISECUNDE_ANIMATIE, self._tic)

    def _animeaza(self) -> None:
        latime = max(2, self.vietati.winfo_width())
        bucata = max(20, ui_comun.px(60))
        pas = max(4, ui_comun.px(12))
        pozitie = self.vietati.coords(self._bucata_vietati)[0] + pas * self._sens
        if pozitie <= 0:
            pozitie = 0
            self._sens = 1
        elif pozitie + bucata >= latime:
            pozitie = max(0, latime - bucata)
            self._sens = -1
        self.vietati.coords(self._bucata_vietati, pozitie, 0, pozitie + bucata, ui_comun.px(14))

    def _paznic(self) -> None:
        tacere = time.monotonic() - self._ultima_schimbare
        if tacere >= SECUNDE_BLOCARE and self._mesaj_incetinire != "blocare":
            self._mesaj_incetinire = "blocare"
            self.anunt.arata(
                "Pare că s-a blocat. Poți să mai aștepți sau să apeși [Oprește]."
            )
            self.anunt.pack(fill="x", pady=(ui_comun.px(8), 0))
            self.rand_anunt.pack(fill="x")
            jurnal.atentionare("Operațiunea nu a mai dat semne de progres de 5 minute.")
        elif tacere >= SECUNDE_INCETINIRE and not self._mesaj_incetinire:
            self._mesaj_incetinire = "incetinire"
            self.anunt.arata(
                "Calculatorul tău lucrează mai încet acum. Programul merge în continuare, "
                "te rog să mai aștepți."
            )
            self.anunt.pack(fill="x", pady=(ui_comun.px(8), 0))
            self.rand_anunt.pack(fill="x")

    def _explica_intarzierea(self) -> None:
        ui_comun.dialog(
            self,
            "De ce durează atât?",
            "Programul nu s-a blocat: lucrează. La fișiere lungi și pe calculatoare mai slabe, "
            "transcrierea durează. Bara și indicatorul care se mișcă arată că lucrul merge mai departe.\n\n"
            "Dacă ești grăbit, apasă „Oprește”: ce s-a scris până acum se păstrează, iar mai târziu "
            "poți continua de unde ai rămas.",
            [("Am înțeles", "principal")],
        )
