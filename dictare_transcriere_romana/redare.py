"""Redarea înregistrării în editor: play, pauză, poziție, taste rapide (32/34/35).

Semnele puse în timpul dictării — ``[01:23]`` — devin puncte de start: cu
cursorul lângă un semn, redarea începe exact de acolo, ca să asculți bucata
respectivă și s-o corectezi „ascultând”.

Redarea nu blochează interfața: pornirea/pauza sunt comenzi rapide
(Ctrl+R = ascultă/pauză, Ctrl+Shift+R = oprește), iar poziția curentă
se arată în bara de jos (``▶ 01:23 / 05:40``).
"""

from __future__ import annotations

import re
import time

#: Un semn de dictare: [mm:ss] sau [h:mm:ss].
_SEMN = re.compile(r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]")


def secunde_din_marca(marca: str) -> float | None:
    """„01:23” (sau „0:01:23”) → secunde; ``None`` dacă marca nu e bună."""
    try:
        parti = [int(bucata) for bucata in marca.strip("[]").split(":")]
    except ValueError:
        return None
    if len(parti) == 2 and 0 <= parti[1] < 60:
        return parti[0] * 60 + parti[1]
    if len(parti) == 3 and parti[1] < 60 and parti[2] < 60:
        return parti[0] * 3600 + parti[1] * 60 + parti[2]
    return None


def marca_din_secunde(secunde: float) -> str:
    """Secunde → „mm:ss”, pentru afișat în bara de stare."""
    secunde = max(0, int(secunde))
    return f"{secunde // 60:02d}:{secunde % 60:02d}"


def semn_la_cursor(text: str, pozitia: int) -> float | None:
    """Cel mai apropiat semn [mm:ss] DEAINTEA cursorului, în secunde.

    Dacă cursorul e imediat după un semn (sau în mijlocul textului), redarea
    începe de la semnul de dinainte — așa „asculți zona semnului” (cerința 32).
    Fără niciun semn înaintea cursorului → ``None`` (redare de la început).
    """
    cel_mai_bun: float | None = None
    for potrivire in _SEMN.finditer(text or ""):
        if potrivire.start() > max(0, pozitia):
            break
        parti = [int(g or 0) for g in potrivire.groups()]
        if len([g for g in potrivire.groups() if g is not None]) == 3:
            secunde = parti[0] * 3600 + parti[1] * 60 + parti[2]
        else:
            secunde = parti[0] * 60 + parti[1]
        cel_mai_bun = float(secunde)
    return cel_mai_bun


class Redare:
    """Un „reportofon” pentru înregistrarea dictării, cu pauză și poziție.

    Nu atinge dispozitivele direct: primește două funcții (pornire/oprire
    sunet), ca să poată fi testat fără boxe — în program primesc funcțiile
    din ``inregistrare``.
    """

    def __init__(self, porneste_sunet=None, opreste_sunet=None):
        self._porneste_sunet = porneste_sunet
        self._opreste_sunet = opreste_sunet
        self._pcm = None
        self._rata = 16000
        self._offset = 0.0
        self._pornit_la: float | None = None

    # ------------------------------------------------------------------ încărcare

    def incarca(self, pcm, rata: int) -> None:
        """Schimbă înregistrarea (oprește orice redare, revine la început)."""
        self.opreste()
        self._pcm = pcm
        self._rata = int(rata) if rata else 16000
        self._offset = 0.0

    def are(self) -> bool:
        return self._pcm is not None and len(self._pcm) > 0

    def durata(self) -> float:
        if not self.are():
            return 0.0
        return len(self._pcm) / float(self._rata)

    # ------------------------------------------------------------------ comenzi

    def porneste(self, de_la: float | None = None) -> bool:
        """Pornește de la secunda dată (sau de unde a rămas). Întoarce succesul."""
        if not self.are():
            return False
        if self.ruleaza():
            return True
        start = self._offset if de_la is None else float(de_la)
        start = max(0.0, min(start, max(0.0, self.durata() - 0.2)))
        if self._porneste_sunet is not None:
            try:
                self._porneste_sunet(self._pcm[int(start * self._rata):], self._rata)
            except Exception:
                return False
        self._offset = start
        self._pornit_la = time.monotonic()
        return True

    def pauza(self) -> None:
        """Oprește sunetul dar ține minte poziția (continuă de acolo)."""
        if not self.ruleaza():
            return
        self._offset = self.pozitie()
        self._oprire()

    def opreste(self) -> None:
        """Oprește și revine la început."""
        self._oprire()
        self._offset = 0.0

    def _oprire(self) -> None:
        self._pornit_la = None
        if self._opreste_sunet is not None:
            try:
                self._opreste_sunet()
            except Exception:
                pass

    # ------------------------------------------------------------------ stare

    def ruleaza(self) -> bool:
        return self._pornit_la is not None

    def pozitie(self) -> float:
        """Poziția curentă în secunde (și cât timp e pe pauză)."""
        if not self.are():
            return 0.0
        if self._pornit_la is None:
            return min(self._offset, self.durata())
        scurs = time.monotonic() - self._pornit_la
        return min(self._offset + scurs, self.durata())

    def la_capat(self) -> bool:
        """A ajuns la sfârșit (redarea se oprește singură)."""
        return self.are() and self.pozitie() >= self.durata() - 0.05
