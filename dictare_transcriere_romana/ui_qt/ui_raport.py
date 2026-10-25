"""Fereastra „Raportează o problemă” — trimite direct pe GitHub, fără cunoștințe tehnice.

Cum funcționează (pentru utilizator):

1. Detaliile tehnice sunt DEJA completate cu ultimele erori din jurnalul
   programului (mesaj, loc, oră). Tu scrii doar, cu cuvintele tale, ce făceai
   când s-a întâmplat.
2. „Trimite pe GitHub” creează direct un raport (issue) la proiect — dacă pe
   calculator există o cheie GitHub salvată; altfel se deschide pagina
   pregătită și mai rămâne un singur clic. În ambele cazuri raportul e și
   copiat în memoria temporară.
3. „Copiază raportul” îl pune în memoria temporară, să-l trimiți cum vrei tu.

Confidențialitate — raportul NU conține nimic din carte:

- căile de pe disc sunt scurtate (numele tău de utilizator și folderele
  proiectului nu apar);
- se trimite EXACT ce vezi în fereastră: descrierea ta + detaliile tehnice
  de mai sus + versiunea programului și a sistemului.
"""

from __future__ import annotations

import json
import platform
import re
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from .. import jurnal
from ..constante import NUME_SCURT, VERSIUNE_COMPLETA
from .comun import Buton, fonturi, seteaza_rol
from . import comun

#: Repo-ul către care se trimit rapoartele.
REPO_GITHUB = "Hermeneuticus-of-things/dted"

_HOME = str(Path.home())


def anonimizeaza(text: str) -> str:
    """Scurtează căile personale dintr-un text (fără nume de utilizator/proiect)."""
    text = text.replace(_HOME, "%UTILIZATOR%")
    text = re.sub(r"[A-Za-z]:\\Users\\[^\s\\\"']+", "%UTILIZATOR%", text)
    # Any other folder on a drive (cartea, proiectul): only the file name stays.
    text = re.sub(r"[A-Za-z]:\\(?![^\n\"']*%UTILIZATOR%)[^\n\"']*\\", r"%PROIECT%\\", text)
    return text


def creeaza_raport(descriere: str, erori: list[str]) -> str:
    """Textul complet al raportului (ce se vede, aceea se trimite)."""
    descriere = (descriere or "").strip() or "(fără descriere)"
    bucati = [
        "## Ce făceam când s-a întâmplat",
        "",
        descriere,
        "",
        "## Detalii tehnice (ultimele erori din jurnal)",
        "",
    ]
    if erori:
        bucati += ["```\n" + anonimizeaza("\n".join(erori)) + "\n```"]
    else:
        bucati.append("(jurnalul nu conține erori recente)")
    bucati += [
        "",
        f"Versiune: {NUME_SCURT} {VERSIUNE_COMPLETA} · "
        f"Windows {platform.release()} ({platform.machine()})",
    ]
    return "\n".join(bucati)


class FereastraRaport(QDialog):
    """Fereastra de raportare, cu detaliile tehnice pre-completate."""

    def __init__(self, parinte, erori: list[str] | None = None, descriere_initiala: str = ""):
        super().__init__(parinte)
        self.setWindowTitle("Raportează o problemă")
        self.setMinimumSize(640, 560)
        self._erori = jurnal.ultimele_erori(5) if erori is None else list(erori)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        titlu = QLabel("Spune-ne ce s-a întâmplat")
        titlu.setFont(fonturi("titlu"))
        layout.addWidget(titlu)

        intro = QLabel(
            "Detaliile tehnice sunt deja completate cu ultimele erori din jurnal "
            "(vezi jos). Tu adaugă doar, cu cuvintele tale, ce făceai când s-a "
            "întâmplat. Raportul nu conține nimic din textul tău din carte, iar "
            "căile de pe disc sunt scurtate. Se trimite exact ce vezi aici."
        )
        intro.setFont(fonturi("baza"))
        intro.setWordWrap(True)
        seteaza_rol(intro, "secundar")
        layout.addWidget(intro)

        et_descriere = QLabel("Ce făceai când s-a întâmplat?")
        et_descriere.setFont(fonturi("buton"))
        layout.addWidget(et_descriere)
        self.edit_descriere = QTextEdit()
        self.edit_descriere.setPlaceholderText(
            "Ex.: dictam capitolul trei, am apăsat Oprește și programul s-a închis…"
        )
        self.edit_descriere.setFont(fonturi("baza"))
        self.edit_descriere.setAcceptRichText(False)
        layout.addWidget(self.edit_descriere, stretch=2)
        if descriere_initiala:
            self.edit_descriere.setPlainText(descriere_initiala)

        et_detalii = QLabel("Detalii tehnice (completate automat din jurnal)")
        et_detalii.setFont(fonturi("buton"))
        layout.addWidget(et_detalii)
        self.edit_detalii = QTextEdit()
        self.edit_detalii.setFont(fonturi("mica"))
        self.edit_detalii.setAcceptRichText(False)
        self.edit_detalii.setPlainText(
            anonimizeaza("\n".join(self._erori)) if self._erori
            else "(jurnalul nu conține erori recente)"
        )
        layout.addWidget(self.edit_detalii, stretch=3)

        self.et_stare = QLabel("")
        self.et_stare.setFont(fonturi("mica"))
        seteaza_rol(self.et_stare, "secundar")
        self.et_stare.setWordWrap(True)
        layout.addWidget(self.et_stare)

        rand = QHBoxLayout()
        rand.addStretch(1)
        rand.addWidget(Buton(self, "Copiază raportul", self._copiaza, latime=190, inaltime=40))
        rand.addWidget(
            Buton(self, "Trimite pe GitHub", self._trimite, fel="principal", latime=220, inaltime=40)
        )
        layout.addLayout(rand)

    # ------------------------------------------------------------------ acțiuni

    def _text_raport(self) -> str:
        """Raportul final = ce se vede în fereastră (descrierea + detaliile)."""
        erori = [
            linie for linie in self.edit_detalii.toPlainText().splitlines() if linie.strip()
        ]
        return creeaza_raport(self.edit_descriere.toPlainText(), erori)

    def _copiaza(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._text_raport())
        self.et_stare.setText("✔ Raportul e în memoria temporară — îl poți lipi oriunde.")

    def _trimite(self) -> None:
        import threading

        self.et_stare.setText("Se trimite raportul…")
        threading.Thread(target=self._trimite_in_fundal, daemon=True).start()

    def _trimite_in_fundal(self) -> None:
        raport = self._text_raport()
        titlu = "Raport automat: " + (
            (self.edit_descriere.toPlainText().strip()[:70] or "problemă raportată din program")
        )
        trimis, mesaj = _creeaza_issue(titlu, raport)
        self._arata(trimis, mesaj)

    def _arata(self, trimis: bool, mesaj: str) -> None:
        """Actualizează starea și, la succes, închide fereastra."""

        def pas() -> None:
            if trimis:
                comun.anunta(
                    self,
                    "Raport trimis. Mulțumim!",
                    "Raportul a fost trimis direct la proiect:\n\n"
                    f"{mesaj}\n\nNimeni nu se uită în calculatorul tău: s-a trimis "
                    "exact ce era în fereastră.",
                )
                self.accept()
            else:
                self.et_stare.setText(mesaj)

        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, pas)


def _creeaza_issue(titlu: str, corp: str) -> tuple[bool, str]:
    """Încearcă trimiterea directă (issue nou pe GitHub); întoarce (ok, mesaj).

    Folosește o cheie GitHub salvată local (git credential), dacă există.
    Dacă nu există, deschide pagina de raport deja completată în browser —
    mai rămâne un singur clic, fără niciun cont de configurat în program.
    """
    url_issue = _url_prefill(titlu, corp)
    cheie = _cheie_github_locala()
    if cheie:
        cerere = urllib.request.Request(
            f"https://api.github.com/repos/{REPO_GITHUB}/issues",
            data=json.dumps({"title": titlu[:120], "body": corp, "labels": ["raport"]}).encode(
                "utf-8"
            ),
            headers={
                "Authorization": f"token {cheie}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "DTED-Raport/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(cerere, timeout=20) as raspuns:
                date = json.loads(raspuns.read().decode("utf-8"))
                return True, date.get("html_url", "trimis")
        except Exception:
            pass  # cădem pe varianta cu browserul
    _deschide_browser(url_issue)
    return (
        False,
        "Nu am găsit o cheie GitHub salvată, așa că ți-am deschis pagina de raport "
        "deja completată (raportul e și în memoria temporară): apasă „Submit new "
        "issue” în pagină și gata.",
    )


def _url_prefill(titlu: str, corp: str) -> str:
    query = urllib.parse.urlencode({"title": titlu[:120], "body": corp[:6000]})
    return f"https://github.com/{REPO_GITHUB}/issues/new?{query}"


def _deschide_browser(url: str) -> None:
    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:
        pass


def _cheie_github_locala() -> str | None:
    """O cheie GitHub din managerul de credențiale al sistemului, dacă există."""
    try:
        import subprocess

        rezultat = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        for linie in rezultat.stdout.splitlines():
            if linie.startswith("password="):
                cheie = linie.split("=", 1)[1].strip()
                return cheie or None
    except Exception:
        pass
    return None
