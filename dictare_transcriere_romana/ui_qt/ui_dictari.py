"""Lista dictărilor recente (stil Express Dictate): tabel sus, text jos.

Fiecare rând e o dictare de-a utilizatorului: data, ora, durata sunetului și
numele (marca). Un clic pe rând încarcă textul în editor; dacă există și
înregistrarea sunetului, aceasta devine gata de ascultat în transportul de jos.
"""

from __future__ import annotations

import wave
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .comun import fonturi, seteaza_rol


def _durata_wav(cale: Path) -> str:
    """Durata unui WAV, ca text („12 s", „3 min 05 s"); „—" dacă nu se poate."""
    try:
        with wave.open(str(cale), "rb") as w:
            secunde = w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return "—"
    if secunde >= 60:
        return f"{int(secunde // 60)} min {int(secunde % 60):02d} s"
    return f"{int(secunde)} s"


class ListaDictari(QWidget):
    """Tabelul cu dictările recente (Text transcris + Audio din folderul programului)."""

    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie
        self._cai: list[tuple[Path, Path | None]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.tabel = QTableWidget(0, 4)
        self.tabel.setHorizontalHeaderLabels(["Data", "Ora", "Durata", "Numele"])
        self.tabel.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabel.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabel.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setAlternatingRowColors(True)
        self.tabel.horizontalHeader().setStretchLastSection(True)
        self.tabel.setColumnWidth(0, 90)
        self.tabel.setColumnWidth(1, 70)
        self.tabel.setColumnWidth(2, 90)
        self.tabel.setMaximumHeight(150)
        self.tabel.currentItemChanged.connect(self._la_selectie)
        layout.addWidget(self.tabel)

    # ------------------------------------------------------------------ umplere

    def reimprospateaza(self) -> None:
        """Recitește folderul programului și umple tabelul (cea mai nouă sus)."""
        from .. import biblioteca

        self.tabel.setRowCount(0)
        self._cai = []
        try:
            folder_text = biblioteca.folder("text")
        except Exception:
            return
        try:
            folder_audio = biblioteca.folder("audio")
        except Exception:
            folder_audio = folder_text
        fisiere = sorted(
            [f for f in folder_text.glob("*.txt") if f.is_file()],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:50]
        for fisier in fisiere:
            marca = fisier.stem
            audio = None
            for candidat in (folder_audio / f"{marca}.wav", folder_audio / f"{marca}.mp3"):
                if candidat.is_file():
                    audio = candidat
                    break
            import datetime as _dt

            moment = _dt.datetime.fromtimestamp(fisier.stat().st_mtime)
            rand = self.tabel.rowCount()
            self.tabel.insertRow(rand)
            for coloana, valoare in (
                (0, moment.strftime("%d.%m.%Y")),
                (1, moment.strftime("%H:%M")),
                (2, _durata_wav(audio) if audio else "—"),
                (3, marca),
            ):
                obiect = QTableWidgetItem(valoare)
                obiect.setFlags(obiect.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tabel.setItem(rand, coloana, obiect)
            self._cai.append((fisier, audio))

    # ------------------------------------------------------------------ selecție

    def _la_selectie(self, curent, precedent) -> None:
        if curent is None:
            return
        rand = curent.row()
        if rand < 0 or rand >= len(self._cai):
            return
        cale_text, cale_audio = self._cai[rand]
        try:
            self.aplicatie.deschide_dictare(cale_text, cale_audio)
        except Exception:
            pass
