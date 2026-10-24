"""Teste pentru modulul de criptare AES-256-GCM (CNG Windows)."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform != "win32":
    import unittest

    raise unittest.SkipTest("criptare folosește CNG (bcrypt.dll), disponibil doar pe Windows")

from dictare_transcriere_romana import criptare


def _cheie(n: int = 0) -> bytes:
    return bytes([(n + i) % 256 for i in range(32)])


def test_roundtrip_bytes():
    cheie = _cheie(1)
    text = "Dictare în română: ăâîșț ȘȚĂ 123".encode("utf-8")
    pachet = criptare.cripteaza_bytes(cheie, text)
    assert criptare.decripteaza_bytes(cheie, pachet) == text
    print("roundtrip bytes OK")


def test_chei_diferite():
    pachet = criptare.cripteaza_bytes(_cheie(1), b"secret")
    try:
        criptare.decripteaza_bytes(_cheie(2), pachet)
        raise AssertionError("decriptarea cu altă cheie trebuia să eșueze")
    except criptare.CriptareInvalida:
        print("cheie greșită -> CriptareInvalida OK")


def test_tamper():
    cheie = _cheie()
    pachet = bytearray(criptare.cripteaza_bytes(cheie, b"aaaaBBBB" * 16))
    pachet[30] ^= 0x01  # strică un bit din textul criptat
    try:
        criptare.decripteaza_bytes(cheie, bytes(pachet))
        raise AssertionError("decriptarea datelor modificate trebuia să eșueze")
    except criptare.CriptareInvalida:
        print("tamper -> CriptareInvalida OK")


def test_aad():
    cheie = _cheie()
    pachet = criptare.cripteaza_bytes(cheie, b"date", aad=b"nume.txt")
    assert criptare.decripteaza_bytes(cheie, pachet, aad=b"nume.txt") == b"date"
    try:
        criptare.decripteaza_bytes(cheie, pachet, aad=b"alt-nume.txt")
        raise AssertionError("AAD diferit trebuia să eșueze")
    except criptare.CriptareInvalida:
        print("AAD legat -> eșec la AAD diferit OK")


def test_gol():
    cheie = _cheie()
    pachet = criptare.cripteaza_bytes(cheie, b"")
    assert criptare.decripteaza_bytes(cheie, pachet) == b""
    print("date goale OK")


def test_fisier():
    cheie = _cheie()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        sursa = tmp / "original.txt"
        criptat = tmp / "original.txt.enc"
        decriptat = tmp / "inapoi.txt"
        sursa.write_text("Text criptat pe disc — nu se citește din Explorer.\n", encoding="utf-8")

        criptare.cripteaza_fisier(cheie, sursa, criptat, aad=b"original.txt")
        assert criptare.este_criptat(criptat)
        assert not criptare.este_criptat(sursa)

        criptare.decripteaza_fisier(cheie, criptat, decriptat, aad=b"original.txt")
        assert decriptat.read_text(encoding="utf-8") == sursa.read_text(encoding="utf-8")

        # altă cheie la decriptare -> eșec
        try:
            criptare.decripteaza_fisier(_cheie(9), criptat, tmp / "gol.txt", aad=b"original.txt")
            raise AssertionError("decriptarea cu cheia greșită trebuia să eșueze")
        except criptare.CriptareInvalida:
            pass
    print("fișiere OK")


if __name__ == "__main__":
    test_roundtrip_bytes()
    test_chei_diferite()
    test_tamper()
    test_aad()
    test_gol()
    test_fisier()
    print("TOATE OK")