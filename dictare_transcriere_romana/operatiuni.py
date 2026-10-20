"""Lucrul neterminat: ca programul să poată relua după o oprire sau o pană.

Cerința 26 vrea ca, dacă programul se închide neașteptat (pană de curent, blocare
sau apăsarea butonului [Oprește]), la pornirea următoare să întrebe:

    „Data trecută nu am terminat. Vrei să continui de unde am rămas?”

Aici se ține minte ce operațiune era în curs: felul ei, fișierul audio folosit,
câte secunde s-au făcut din câte, marca de timp și textul scris până atunci.
Textul stă în copia de siguranță din ``biblioteca`` (nu se dublează).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import biblioteca, cai, jurnal

#: Numele fișierului în care se ține minte lucrul neterminat.
NUME_FISIER = "operatiune.json"


def _cale() -> Path:
    return cai.director_recuperare() / NUME_FISIER


@dataclass
class Operatiune:
    """O operațiune lungă, începută și neterminată încă."""

    fel: str = ""                     # „transcriere”, „dictare”, „instalare”
    cale_audio: str = ""
    nume_audio: str = ""
    secunde_facute: float = 0.0
    secunde_total: float = 0.0
    marca: str = ""
    detalii: dict = field(default_factory=dict)
    moment: str = ""

    def text_procent(self) -> str:
        if self.secunde_total > 0 and self.secunde_facute > 0:
            from . import text_ro

            return (
                f"{text_ro.durata_text(self.secunde_facute)} din "
                f"{text_ro.durata_text(self.secunde_total)}"
            )
        return ""

    def propozitie(self) -> str:
        """Textul simplu arătat utilizatorului la pornirea următoare."""
        if self.fel == "transcriere" and self.cale_audio:
            ramas = f" Mai era de scris: {self.text_procent()}." if self.text_procent() else ""
            return (
                f"Data trecută nu am terminat transcrierea fișierului „{self.nume_audio or Path(self.cale_audio).name}”.{ramas}"
            )
        if self.fel == "dictare":
            return "Data trecută nu am terminat o dictare."
        if self.fel == "instalare":
            pas = self.detalii.get("pas", "")
            return f"Data trecută nu am terminat instalarea{(' (' + pas + ')') if pas else ''}."
        return "Data trecută nu am terminat o operațiune."


def scrie(operatiune: Operatiune | None = None, **campuri) -> bool:
    """Ține minte lucrul în curs (se cheamă des, este ieftin)."""
    if operatiune is None:
        operatiune = Operatiune(**campuri)
    if not operatiune.moment:
        operatiune.moment = dt.datetime.now().isoformat(timespec="seconds")
    try:
        cale = _cale()
        cale.parent.mkdir(parents=True, exist_ok=True)
        temporar = cale.with_suffix(".tmp")
        temporar.write_text(
            json.dumps(asdict(operatiune), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporar.replace(cale)
        return True
    except OSError as exc:
        jurnal.atentionare(f"Lucrul neterminat nu a putut fi notat: {exc}")
        return False


def citeste() -> Operatiune | None:
    """Citește lucrul neterminat, dacă există și se poate citi."""
    cale = _cale()
    if not cale.exists():
        return None
    try:
        date = json.loads(cale.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    permise = {camp: valoare for camp, valoare in date.items() if camp in Operatiune.__dataclass_fields__}
    try:
        return Operatiune(**permise)
    except TypeError:
        return None


def sterge() -> None:
    """Operațiunea s-a terminat: nu mai rămâne nimic de reluat."""
    try:
        _cale().unlink(missing_ok=True)
    except OSError as exc:
        jurnal.atentionare(f"Notarea lucrului neterminat nu a putut fi ștearsă: {exc}")


def are_text_salvat() -> bool:
    """Adevărat dacă mai există și textul scris până la oprire."""
    try:
        return bool(biblioteca.citeste_recuperare())
    except Exception:
        return False
