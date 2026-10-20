"""Starea comună a programului: textul de pe ecran, sunetul și documentele.

Aici stă tot ce trebuie păstrat între ecrane: textul transcris, bucata de text
încă nesigură (scrisă cu gri), fișierul audio folosit, marca de timp care leagă
numele fișierelor între ele și documentul final.

Modulul se ocupă și de regula cea mai importantă a programului: **nimic nu se
pierde**. Textul se salvează automat, iar când ceva urmează să înlocuiască
textul de pe ecran, utilizatorul este întrebat mai întâi.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from . import biblioteca, config as config_modul, jurnal


@dataclass
class Stare:
    """Tot ce știe programul despre lucrul în curs."""

    config: config_modul.Config = field(default_factory=config_modul.Config)
    text: str = ""                      # textul sigur (negru)
    provizoriu: str = ""                # textul încă nesigur (gri)
    audio_cale: Path | None = None      # sunetul din folderul „Audio”
    durata_audio: float = 0.0
    segmente: list = field(default_factory=list)
    marca: str = ""                     # „Dictare 2026-10-19 10-35”
    document_cale: Path | None = None   # ultimul document salvat
    sursa: str = ""                     # „dictare”, „fisier”, „editor”
    nesalvat: bool = False
    ultima_salvare: dt.datetime | None = None

    # ------------------------------------------------------------------ text

    def text_complet(self) -> str:
        """Textul întreg: partea sigură plus bucata încă nesigură."""
        parti = [self.text.strip()]
        if self.provizoriu.strip():
            parti.append(self.provizoriu.strip())
        return "\n\n".join(parte for parte in parti if parte)

    def are_text(self) -> bool:
        return bool(self.text_complet().strip())

    def numara_cuvinte(self) -> int:
        return len([cuvant for cuvant in self.text_complet().split() if cuvant])

    def fixeaza_text(self, text: str, sursa: str = "") -> None:
        """Pune un text nou pe ecran (înlocuiește ce era)."""
        self.text = text or ""
        self.provizoriu = ""
        if sursa:
            self.sursa = sursa
        self.marcheaza_modificat()

    def adauga_text(self, bucata: str) -> None:
        """Adaugă text la sfârșitul textului sigur („continuă dictarea”)."""
        bucata = (bucata or "").strip()
        if not bucata:
            return
        self.text = (self.text.rstrip() + "\n\n" + bucata).strip() if self.text.strip() else bucata
        self.marcheaza_modificat()

    def arata_provizoriu(self, text: str) -> None:
        """Arată o propoziție încă nesigură (se scrie cu gri pe ecran)."""
        self.provizoriu = (text or "").strip()

    def finalizeaza_provizoriu(self) -> None:
        """Trece textul nesigur în textul sigur (când modelul l-a hotărât)."""
        if self.provizoriu.strip():
            self.adauga_text(self.provizoriu)
        self.provizoriu = ""

    # ------------------------------------------------------------------ stare

    def marcheaza_modificat(self) -> None:
        self.nesalvat = True

    def marcheaza_salvat(self, moment: dt.datetime | None = None) -> None:
        self.nesalvat = False
        self.ultima_salvare = moment or dt.datetime.now()

    def pregateste_dictare_noua(self) -> str:
        """Pregătește o dictare nouă: marcă de timp nouă, text gol."""
        if not self.marca or self.text.strip():
            self.marca = biblioteca.marca_acum()
        elif not self.marca:
            self.marca = biblioteca.marca_acum()
        return self.marca

    def pregateste_fisier(self, cale_audio: Path) -> str:
        """Pregătește transcrierea unui fișier: marca vine din numele fișierului."""
        self.marca = biblioteca.marca_din_nume(cale_audio)
        return self.marca

    def marca_pentru_salvare(self) -> str:
        """Marca de timp folosită la salvare (se creează dacă lipsește)."""
        if not self.marca:
            self.marca = biblioteca.marca_acum()
        return self.marca

    def goleste(self, si_audio: bool = True) -> None:
        """Golește lucrul curent (după ce textul a fost salvat sau părăsit)."""
        self.text = ""
        self.provizoriu = ""
        if si_audio:
            self.audio_cale = None
            self.durata_audio = 0.0
            self.marca = ""
        self.segmente = []
        self.sursa = ""
        self.nesalvat = False

    # ------------------------------------------------------------------ copie de siguranță

    def salveaza_de_siguranta(self, detalii: str = "") -> bool:
        """Scrie o copie de siguranță a textului (la 30 de secunde și la acțiuni)."""
        text = self.text_complet()
        if not text.strip():
            return False
        reusit = biblioteca.scrie_recuperare(
            text,
            marca=self.marca or self.marca_acum(),
            detalii=detalii or f"ecran: {self.sursa or 'nespecificat'}",
        )
        if reusit:
            self.ultima_salvare = dt.datetime.now()
        return reusit

    def text_nesalvat(self) -> bool:
        """Adevărat dacă pe ecran este text care nu a fost salvat ca document."""
        return self.are_text() and (self.nesalvat or self.document_cale is None)


# --------------------------------------------------------------------------- întrebări


def intreaba_nesalvat(parinte, motiv: str = "") -> str:
    """Întrebarea „Ai un text nesalvat. Ce vrei să faci?”.

    Întoarce ``„salveaza”``, ``„nu”`` sau ``„napoi”``. Butonul „Înapoi” este cel
    ales implicit, ca o apăsare greșită de Enter să nu piardă textul.
    """
    from . import ui_comun

    text = "Ai un text nesalvat. Ce vrei să faci?"
    if motiv:
        text = f"{motiv}\n\n{text}"
    rezultat = ui_comun.dialog(
        parinte,
        "Text nesalvat",
        text,
        [("Salvează și continuă", "principal"), ("Nu salva", "secundar"), ("Înapoi", "secundar")],
        implicit=2,
        anulare=2,
    )
    if rezultat == 0:
        return "salveaza"
    if rezultat == 1:
        return "nu"
    return "napoi"


def pregateste_schimbarea(parinte, stare: Stare, motiv: str = "") -> bool:
    """Verifică dacă se poate înlocui textul de pe ecran.

    Întoarce ``True`` dacă se poate continua. Dacă textul este salvat sau
    utilizatorul alege „Nu salva”, se continuă; dacă alege „Salvează și
    continuă”, textul este salvat mai întâi.
    """
    from . import ui_comun

    if not stare.text_nesalvat():
        return True
    alegere = intreaba_nesalvat(parinte, motiv)
    if alegere == "napoi":
        return False
    if alegere == "salveaza":
        cale = salveaza_document(parinte, stare)
        if cale is None:
            # Salvarea nu a reușit: rămânem pe loc, ca să nu se piardă text.
            return False
        stare.marcheaza_salvat()
    stare.goleste()
    jurnal.info("Text nesalvat: utilizatorul a ales să continue.")
    return True


def salveaza_document(parinte, stare: Stare, fel: str = "docx", radacina_aleasa: Path | None = None):
    """Salvează textul de pe ecran ca document, în folderul „Documente finale”.

    Întoarce calea fișierului salvat sau ``None`` dacă salvarea nu a reușit
    (mesajul pentru utilizator este arătat aici).
    """
    from . import documente, erori, ui_comun

    text = stare.text_complet()
    if not text.strip():
        ui_comun.anunta(
            parinte,
            "Nu este nimic de salvat",
            "Textul transcris este gol. Dictează sau transcrie un fișier, apoi salvează.",
        )
        return None
    marca = stare.marca_pentru_salvare()
    destinatie = biblioteca.nume_unic(biblioteca.folder("documente", radacina_aleasa), biblioteca.nume_legat(marca, f".{fel}"))
    try:
        documente.salveaza(
            text,
            destinatie,
            titlu=marca,
            subtitlu="Transcriere făcută cu programul „Dictate & Transcription Express Digital (D&TED)”.",
            segmente=stare.segmente,
            secunde=stare.durata_audio,
        )
    except Exception as exc:
        jurnal.eroare(f"Salvarea în {destinatie} a eșuat: {exc}")
        ui_comun.dialog_eroare(
            parinte,
            erori.Eroare(
                ce_s_a_intamplat=f"Nu am putut salva documentul „{destinatie.name}”.",
                de_ce="Folderul nu poate fi scris sau discul este aproape plin.",
                ce_faci_acum=(
                    "Încearcă din nou. Dacă nu merge, alege alt folder din „Setări” "
                    "(de exemplu, Desktopul) și salvează acolo."
                ),
                actiuni=[erori.Actiune("Încearcă din nou", erori.INCERCARE_DIN_NOU)],
                detalii=str(exc),
            ),
        )
        return None
    stare.document_cale = destinatie
    stare.marcheaza_salvat()
    # Textul salvat ajunge și în „Text transcris”, ca toate numele să fie legate.
    cale_text = biblioteca.folder("text", radacina_aleasa) / f"{marca}.txt"
    try:
        if not cale_text.exists():
            cale_text.write_text(text, encoding="utf-8", newline="\r\n")
    except OSError:
        pass
    return destinatie


def pregateste_iesire(parinte, stare: Stare) -> bool:
    """Întrebarea de la închiderea programului: nu se pierde niciodată text."""
    if not stare.text_nesalvat():
        return True
    alegere = intreaba_nesalvat(parinte, "Închizi programul.")
    if alegere == "napoi":
        return False
    if alegere == "salveaza":
        if salveaza_document(parinte, stare) is None:
            return False
    stare.goleste()
    return True
