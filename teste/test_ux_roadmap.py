"""Teste pentru restanțele UX din roadmap: drag & drop (UX-28) și indicatorul
de rețea care se actualizează (UX-31)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADACINA = Path(__file__).resolve().parents[1]
if str(RADACINA) not in sys.path:
    sys.path.insert(0, str(RADACINA))

from PySide6.QtCore import QMimeData, QPointF, QUrl, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication, QToolButton

from dictare_transcriere_romana.ui_qt.principal import Aplicatie
from dictare_transcriere_romana.ui_qt.ui_transcriere import EXTENSII_DROP, _ZonaDrop, _are_audio


def _app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_extensiile_de_drop_sunt_cele_de_la_buton():
    assert {".mp3", ".wav", ".m4a", ".ogg", ".flac"} <= EXTENSII_DROP


def test_are_audio_accepta_doar_fișiere_audio():
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("C:/probe/inregistrare.mp3")])
    assert _are_audio(mime) is True

    mime_doc = QMimeData()
    mime_doc.setUrls([QUrl.fromLocalFile("C:/probe/document.docx")])
    assert _are_audio(mime_doc) is False

    mime_text = QMimeData()
    mime_text.setText("doar text")
    assert _are_audio(mime_text) is False


def test_zona_drop_primeste_toate_fișierele_audio():
    _app()
    zona = _ZonaDrop()
    assert zona.acceptDrops() is True
    primite = []
    zona.la_primire = primite.append

    mime = QMimeData()
    mime.setUrls(
        [
            QUrl.fromLocalFile("C:/probe/poze.txt"),
            QUrl.fromLocalFile("C:/probe/convorbire.wav"),
            QUrl.fromLocalFile("C:/probe/interviu.mp3"),
        ]
    )
    eveniment = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    zona.dropEvent(eveniment)
    assert primite and isinstance(primite[0], list)
    assert [cale.name for cale in primite[0]] == ["convorbire.wav", "interviu.mp3"]


def test_indicatorul_de_retea_arată_starea_reală():
    _app()

    class _Stub:
        pass

    stub = _Stub()
    stub.btn_retea = QToolButton()

    Aplicatie._pune_indicator_retea(stub, True)
    assert "Internet pornit" in stub.btn_retea.text()

    Aplicatie._pune_indicator_retea(stub, False)
    assert "Fără internet" in stub.btn_retea.text()

    Aplicatie._pune_indicator_retea(stub, None)
    assert "neprecizată" in stub.btn_retea.text()
