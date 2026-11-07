"""Motorul de focus Ionuț ADL (§2): registru de suprafețe, stivă per fereastră,
rutarea comenzilor divergent→convergent pe suprafața activă.

Încadrează focusul nativ Qt (nu îl dublează): Qt ține focusul nativ al
controlului, motorul ține LOGICA de niveluri (aplicație → fereastră →
suprafață → obiect), rutarea comenzilor și revenirea exactă la închidere.

Ids: „editor.document", „ecran.dictare", „dialog.setari", „fereastra.principal".
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InregistrareSuprafata:
    """O suprafață înregistrată: id, nivel, părinte, comenzi locale."""

    id: str
    nivel: str  # „aplicatie", „fereastră", „suprafață", „obiect"
    parinte: str | None = None
    modal: bool = False
    comenzi: dict = field(default_factory=dict)  # nume → apelabil
    onFocus: object = None
    onBlur: object = None


class EroareFocus(KeyError):
    """Suprafața cerută nu e înregistrată."""


class FocusMotor:
    """Stivă de suprafețe per fereastră + rutarea comenzilor.

    * „apasa" — deschide/activează o suprafață (push sau switch la același nivel);
    * „scoate" — închide o suprafață și restaurează părintele (sau anteriorul);
    * „comanda" — o caută mai întâi pe suprafața activă, apoi urcă spre
      părinți (bubbling), conform ADL §2 (local → fereastră → aplicație).
    """

    def __init__(self, radacina: str = "fereastra.principal"):
        self._inregistrari: dict[str, InregistrareSuprafata] = {}
        self._stiva: list[str] = []
        self._radacina = radacina

    # ---------------------------------------------------------------- registru

    def inregistreaza(
        self,
        id: str,
        nivel: str = "suprafață",
        parinte: str | None = None,
        modal: bool = False,
        comenzi: dict | None = None,
        onFocus=None,
        onBlur=None,
    ) -> InregistrareSuprafata:
        reg = InregistrareSuprafata(
            id=id, nivel=nivel, parinte=parinte, modal=modal,
            comenzi=dict(comenzi or {}), onFocus=onFocus, onBlur=onBlur,
        )
        self._inregistrari[id] = reg
        return reg

    def dezregistreaza(self, id: str) -> None:
        self._inregistrari.pop(id, None)
        if id in self._stiva:
            self.scoate(id)

    # ---------------------------------------------------------------- stivă

    def apasa(self, id: str, trigger: str | None = None) -> None:
        reg = self._inregistrari.get(id)
        if reg is None:
            raise EroareFocus(id)
        # suprafața activă anterioară își primește onBlur (ADL §2: blur exact)
        veche = self.suprafata_activa()
        if veche and veche != id:
            reg_veche = self._inregistrari.get(veche)
            if reg_veche and reg_veche.onBlur:
                try:
                    reg_veche.onBlur()
                except Exception:
                    pass
        if id in self._stiva:
            self._stiva.remove(id)  # readucem în vârf (switch)
        self._stiva.append(id)
        if reg.onFocus:
            try:
                reg.onFocus()
            except Exception:
                pass

    def scoate(self, id: str) -> None:
        while id in self._stiva:
            de_scos = self._stiva.pop()
            reg = self._inregistrari.get(de_scos)
            if reg and reg.onBlur:
                try:
                    reg.onBlur()
                except Exception:
                    pass
            if de_scos == id:
                break

    def suprafata_activa(self) -> str | None:
        return self._stiva[-1] if self._stiva else None

    def stiva(self) -> tuple:
        return tuple(self._stiva)

    # ---------------------------------------------------------------- comenzi

    def comanda(self, nume: str, *argumente) -> bool:
        """Rutează comanda: suprafața activă → părinți → rădăcină.

        Întoarce True dacă cineva a tratat-o (divergent la apel, convergent
        la handler-ul potrivit).
        """
        id_curent = self.suprafata_activa()
        if id_curent is None and self._stiva == [] and self._radacina in self._inregistrari:
            id_curent = self._radacina
        vreme = id_curent
        while vreme:
            reg = self._inregistrari.get(vreme)
            if reg is None:
                break
            apel = reg.comenzi.get(nume)
            if apel is not None:
                apel(*argumente)
                return True
            vreme = reg.parinte
        return False
