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
    QInputDialog,
    QLabel,
    QMenu,
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

        self.tabel = QTableWidget(0, 6)
        self.tabel.setHorizontalHeaderLabels(
            ["Data", "Ora", "Durata", "Prioritate", "Numele", "Notițe"]
        )
        self.tabel.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabel.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabel.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setAlternatingRowColors(True)
        self.tabel.horizontalHeader().setStretchLastSection(True)
        self.tabel.setColumnWidth(0, 85)
        self.tabel.setColumnWidth(1, 65)
        self.tabel.setColumnWidth(2, 80)
        self.tabel.setColumnWidth(3, 80)
        self.tabel.setColumnWidth(4, 190)
        self.tabel.setMaximumHeight(160)
        self.tabel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabel.customContextMenuRequested.connect(self._meniu_contextual)
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
            try:
                prima = next(
                    (lin for lin in fisier.read_text(encoding="utf-8", errors="replace").splitlines() if lin.strip()),
                    "",
                )
            except OSError:
                prima = ""
            notițe = prima.replace("=", " ").strip()[:90]
            rand = self.tabel.rowCount()
            self.tabel.insertRow(rand)
            for coloana, valoare in (
                (0, moment.strftime("%d.%m.%Y")),
                (1, moment.strftime("%H:%M")),
                (2, _durata_wav(audio) if audio else "—"),
                (3, "Normal"),
                (4, marca),
                (5, notițe),
            ):
                obiect = QTableWidgetItem(valoare)
                obiect.setFlags(obiect.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tabel.setItem(rand, coloana, obiect)
            self._cai.append((fisier, audio))

    # ------------------------------------------------------------------ selecție

    def _meniu_contextual(self, pozitie) -> None:
        """Meniul listei: Deschide / Redenumește (F2) / Șterge (Ctrl+Delete)."""
        if self.tabel.currentRow() < 0:
            return
        meniu = QMenu(self)
        meniu.addAction("Deschide", self._deschide_selectat)
        meniu.addSeparator()
        meniu.addAction("Redenumește (F2)", self._redenumeste)
        meniu.addAction("Șterge (Ctrl+Delete)", self._sterge)
        meniu.exec(self.tabel.viewport().mapToGlobal(pozitie))

    def _deschide_selectat(self) -> None:
        rand = self.tabel.currentRow()
        if 0 <= rand < len(self._cai):
            self._la_selectie(self.tabel.item(rand, 0), None)

    def _redenumeste(self) -> None:
        """F2: redenumește dictarea (textul + sunetul, legătura rămâne)."""
        rand = self.tabel.currentRow()
        if rand < 0 or rand >= len(self._cai):
            return
        cale_text, cale_audio = self._cai[rand]
        nume_nou, ok = QInputDialog.getText(
            self, "Redenumește dictarea", "Noul nume:", text=str(cale_text.stem)
        )
        if not ok or not nume_nou.strip():
            return
        nume_nou = nume_nou.strip()
        try:
            cale_noua = cale_text.with_name(nume_nou + cale_text.suffix)
            if cale_noua.exists():
                raise OSError(f"există deja {cale_noua.name}")
            cale_text.rename(cale_noua)
            if cale_audio is not None and cale_audio.exists():
                cale_audio.rename(cale_audio.with_name(nume_nou + cale_audio.suffix))
        except OSError as exc:
            from .comun import anunta

            anunta(self, "Numele nu s-a putut schimba", str(exc))
            return
        self.reimprospateaza()
        from .comun import seteaza_rol  # noqa: F401  (mentine importurile folosite)

        self.aplicatie.bara_stare.arata(
            "Redenumit", f"dictarea se numește acum „{nume_nou}”.", "succes"
        )

    def _sterge(self) -> None:
        """Ctrl+Delete: mută dictarea (text + sunet) la Coșul de reciclare."""
        rand = self.tabel.currentRow()
        if rand < 0 or rand >= len(self._cai):
            return
        cale_text, cale_audio = self._cai[rand]
        from .. import biblioteca
        from .comun import intreaba

        if not intreaba(
            self,
            "Ștergi dictarea?",
            f"„{cale_text.stem}” ajunge în Coșul de reciclare (textul"
            + (" și sunetul" if cale_audio else "")
            + "). Nu se șterge definitiv.",
        ):
            return
        reusit, mesaj = biblioteca.la_gunoi(cale_text)
        if cale_audio is not None and cale_audio.exists():
            biblioteca.la_gunoi(cale_audio)
        if not reusit:
            from .comun import anunta

            anunta(self, "Nu am putut șterge", mesaj or "Windows a refuzat mutarea.")
            return
        self.reimprospateaza()
        self.aplicatie.bara_stare.arata("Șters", "dictarea e în Coșul de reciclare.", "atentie")

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
