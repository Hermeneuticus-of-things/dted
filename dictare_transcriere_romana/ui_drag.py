"""Trage și lasă fișierul audio peste fereastră (doar Windows, fără pachete noi).

Windows trimite fereastrei mesajul „WM_DROPFILES” când utilizatorul trage un
fișier peste ea. Aici se pornește această primire, se citesc căile fișierelor și
se trimit mai departe programului. Dacă nu reușește (Windows neobișnuit),
întoarce ``False`` și butonul „Alege fișierul audio” rămâne calea de rezervă, deci
programul merge mai departe.

Nu se folosește niciun pachet suplimentar și nimic nu pleacă pe internet.
"""

from __future__ import annotations

import ctypes
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from . import jurnal

WM_DROPFILES = 0x0233
GWLP_WNDPROC = -4

_SemnaturaFereastra = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,  # LRESULT
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


def _cai_din_drop(hdrop: int) -> list[Path]:
    """Citește căile fișierelor lăsate peste fereastră."""
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.DragQueryFileW.restype = wintypes.UINT
    shell32.DragQueryFileW.argtypes = [
        wintypes.HANDLE,
        wintypes.UINT,
        wintypes.LPWSTR,
        wintypes.UINT,
    ]
    cate = int(shell32.DragQueryFileW(wintypes.HANDLE(hdrop), 0xFFFFFFFF, None, 0))
    cai: list[Path] = []
    for index in range(cate):
        lungime = int(shell32.DragQueryFileW(wintypes.HANDLE(hdrop), index, None, 0))
        if lungime <= 0:
            continue
        buffer = ctypes.create_unicode_buffer(lungime + 1)
        shell32.DragQueryFileW(wintypes.HANDLE(hdrop), index, buffer, lungime + 1)
        if buffer.value:
            cai.append(Path(buffer.value))
    return cai


class _Legatura:
    """Primirea fișierelor traselor, legată de o fereastră Windows."""

    def __init__(self, hwnd: int, la_fisiere):
        self.hwnd = hwnd
        self.la_fisiere = la_fisiere
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        self._procedura = _SemnaturaFereastra(self._tratare)
        self._vechi = None
        self._user32.CallWindowProcW.restype = ctypes.c_ssize_t
        self._user32.CallWindowProcW.argtypes = [
            ctypes.c_void_p,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self._instaleaza()

    def _instaleaza(self) -> None:
        nou = ctypes.cast(self._procedura, ctypes.c_void_p)
        try:
            functia = self._user32.SetWindowLongPtrW
        except AttributeError:  # Windows pe 32 de biți
            functia = self._user32.SetWindowLongW
        functia.restype = ctypes.c_void_p
        functia.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        self._vechi = functia(wintypes.HWND(self.hwnd), GWLP_WNDPROC, nou)
        if not self._vechi:
            raise OSError(ctypes.get_last_error(), "SetWindowLongW nu a reușit")
        self._shell32.DragAcceptFiles(wintypes.HWND(self.hwnd), True)

    def _tratare(self, hwnd, mesaj, wparam, lparam):  # noqa: ANN001
        if mesaj == WM_DROPFILES:
            cai: list[Path] = []
            try:
                cai = _cai_din_drop(int(wparam))
            except Exception as exc:  # pragma: no cover - depinde de Windows
                jurnal.atentionare(f"Fișierele trase nu au putut fi citite: {exc}")
            finally:
                self._shell32.DragFinish(wintypes.HANDLE(wparam))
            if cai:
                try:
                    self.la_fisiere(cai)
                except Exception as exc:  # pragma: no cover - nu oprește programul
                    jurnal.eroare(f"Tratarea fișierelor trase a eșuat: {exc}")
            return 0
        return self._user32.CallWindowProcW(self._vechi, hwnd, mesaj, wparam, lparam)

    def opreste(self) -> None:
        try:
            self._shell32.DragAcceptFiles(wintypes.HWND(self.hwnd), False)
        except Exception:
            pass


def activeaza(fereastra: tk.Misc, la_fisiere) -> bool:
    """Pornește primirea fișierelor trase peste ``fereastra``.

    ``la_fisiere`` primește lista căilor. Întoarce ``True`` dacă a reușit.
    """
    try:
        fereastra.update_idletasks()
    except tk.TclError:
        return False
    legaturi: list[_Legatura] = []
    for hwnd in _ferestre_windows(fereastra):
        try:
            legaturi.append(_Legatura(hwnd, la_fisiere))
        except Exception as exc:  # pragma: no cover - depinde de Windows
            jurnal.atentionare(f"Tragerea fișierelor nu a putut fi pornită ({hwnd}): {exc}")
    if not legaturi:
        return False
    existente = getattr(fereastra, "_legaturi_dnd", None) or []
    fereastra._legaturi_dnd = list(existente) + legaturi  # type: ignore[attr-defined]
    jurnal.info(f"Tragerea fișierelor peste fereastră este pornită ({len(legaturi)} ferestre).")
    return True


def _ferestre_windows(fereastra: tk.Misc) -> list[int]:
    """Handle-urile Windows ale ferestrei și ale părinților ei (fără repetări)."""
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetParent.restype = wintypes.HWND
        user32.GetParent.argtypes = [wintypes.HWND]
        hwnd = int(fereastra.winfo_id())
    except Exception:
        return []
    gasite: list[int] = []
    while hwnd and hwnd not in gasite and len(gasite) < 4:
        gasite.append(hwnd)
        tata = user32.GetParent(wintypes.HWND(hwnd))
        hwnd = int(tata) if tata else 0
    return gasite
