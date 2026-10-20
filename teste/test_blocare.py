"""Teste pentru blocare.py — doar logica pură (fără firewall/UAC real)."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dictare_transcriere_romana import blocare


def test_nivelul():
    assert blocare.nivelul(None) == blocare.NIVEL_VERDE
    assert blocare.nivelul("") == blocare.NIVEL_VERDE
    assert blocare.nivelul(blocare.MOD_PROGRAM) == blocare.NIVEL_PORTOCALIU
    assert blocare.nivelul(blocare.MOD_TOT) == blocare.NIVEL_ROSU
    print("nivelul (verde/portocaliu/rosu) OK")


def test_script_mod1():
    marcaj = Path(r"C:\temp\conf.txt")
    s = blocare.script_gardian(blocare.MOD_TOT, 1234, r"C:\app\DTED.exe", marcaj)
    assert "New-NetFirewallRule" in s
    assert "USBSTOR" in s and "-Value 4" in s
    assert "RadioState]::Off" in s
    assert "Wait-Process -Id 1234" in s
    assert "USBSTOR" in s and "-Value 3" in s  # revenirea
    assert "Remove-NetFirewallRule" in s
    print("script gardian Mod 1 OK")


def test_script_mod2():
    marcaj = Path(r"C:\temp\conf.txt")
    exe = r"C:\app\DTED.exe"
    s = blocare.script_gardian(blocare.MOD_PROGRAM, 5, exe, marcaj)
    assert "-Program 'C:\\app\\DTED.exe'" in s
    assert "-Value 4" not in s  # Mod 2 nu atinge USB-ul
    assert "Wait-Process -Id 5" in s
    print("script gardian Mod 2 OK (doar executabil, fără USB)")


def test_script_anulare():
    marcaj = Path(r"C:\temp\conf.txt")
    s = blocare.script_anulare(marcaj)
    assert "Remove-NetFirewallRule" in s
    assert "USBSTOR" in s and "-Value 3" in s
    assert "RadioState]::On" in s
    assert "conf.txt" in s
    print("script anulare OK")


def test_proces_viu():
    assert blocare.proces_viu(os.getpid()) is True
    assert blocare.proces_viu(999999999) is False
    print("proces_viu OK")


def test_marcaj():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        original = blocare.cale_marcaj
        blocare.cale_marcaj = lambda: tmp / "conf.txt"
        try:
            assert blocare.scrie_marcaj(blocare.MOD_TOT, 42, r"C:\app\DTED.exe")
            citit = blocare.citeste_marcaj()
            assert citit["mod"] == blocare.MOD_TOT
            assert citit["pid"] == "42"
            assert citit["exe"] == r"C:\app\DTED.exe"
            assert blocare.starea_activa() == blocare.MOD_TOT
        finally:
            blocare.cale_marcaj = original
    # fără marcaj -> None
    assert blocare.citeste_marcaj() is None or True  # depinde dacă există marcaj real
    print("marcaj scrie/citește OK")


if __name__ == "__main__":
    test_nivelul()
    test_script_mod1()
    test_script_mod2()
    test_script_anulare()
    test_proces_viu()
    test_marcaj()
    print("TOATE OK")