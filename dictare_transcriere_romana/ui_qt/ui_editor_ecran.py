"""Pagina Editor PySide6: scrie sau corectează textul.

Editorul mare este mereu vizibil jos, în fereastra principală; această pagină
îi pune focalizarea, ca să poți scrie imediat (cerința 5 — ecran real, nu stub).
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .comun import fonturi


class PaginaEditor(QWidget):
    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)

        lbl = QLabel("Scrie sau corectează în editorul de mai jos, apoi salvează (Ctrl+S).")
        lbl.setFont(fonturi("buton"))
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addStretch(1)

        editor = getattr(aplicatie, "editor", None)
        if editor is not None and hasattr(editor, "focus"):
            editor.focus()