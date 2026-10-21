"""Teste pentru parola.py (cheie maestră, scrypt, recuperare, schimbare)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform != "win32":
    import unittest

    raise unittest.SkipTest("criptare folosește CNG (bcrypt.dll), disponibil doar pe Windows")

from dictare_transcriere_romana import criptare, parola


def test_definire_deschidere():
    seif, rec, cheie_maestra = parola.defineste("Parola123!")
    assert parola.deschide_cu_parola(seif, "Parola123!") == cheie_maestra
    print("definire + deschidere cu parolă OK")


def test_parola_gresita():
    seif, _, _ = parola.defineste("corecta")
    try:
        parola.deschide_cu_parola(seif, "gresita")
        raise AssertionError("parola greșită trebuia să eșueze")
    except parola.ParolaGresita:
        print("parolă greșită -> ParolaGresita OK")


def test_recuperare():
    seif, rec, cheie_maestra = parola.defineste("Parola123!")
    assert parola.deschide_cu_recuperare(seif, rec) == cheie_maestra
    # recuperare greșită (cheie de lungime validă, dar greșită)
    cheie_gresita = parola.codifica_recuperare(bytes(32))
    try:
        parola.deschide_cu_recuperare(seif, cheie_gresita)
        raise AssertionError("recuperare greșită trebuia să eșueze")
    except parola.ParolaGresita:
        pass
    # format invalid
    try:
        parola.deschide_cu_recuperare(seif, "AAAAAA==")
        raise AssertionError("format invalid trebuia să eșueze")
    except parola.ParolaGresita:
        pass
    print("cheie de recuperare OK")


def test_schimbare_parola_aceeasi_cheie():
    seif, rec, cheie_maestra = parola.defineste("veche123")
    # criptează un „fișier” cu cheia maestră inițială
    pachet = criptare.cripteaza_bytes(cheie_maestra, b"continut secret")

    seif_nou = parola.schimba_parola(seif, "veche123", "noua456")
    # parola veche nu mai merge
    try:
        parola.deschide_cu_parola(seif_nou, "veche123")
        raise AssertionError("parola veche trebuia să eșueze după schimbare")
    except parola.ParolaGresita:
        pass
    # parola nouă merge și întoarce ACEEAȘI cheie maestră
    cheie_dupa = parola.deschide_cu_parola(seif_nou, "noua456")
    assert cheie_dupa == cheie_maestra
    # deci fișierul vechi încă se decriptează (0.11.6-b)
    assert criptare.decripteaza_bytes(cheie_dupa, pachet) == b"continut secret"
    print("schimbare parolă (fișiere vechi OK, aceeași cheie) OK")


def test_serializare():
    seif, rec, cheie = parola.defineste("Parola123!")
    dict_ = seif.la_dict()
    seif2 = parola.Seif.din_dict(dict_)
    assert parola.deschide_cu_parola(seif2, "Parola123!") == cheie
    assert parola.deschide_cu_recuperare(seif2, rec) == cheie
    print("serializare la_dict/din_dict OK")


def test_pauza():
    p1 = parola.pauza_greseli(1)
    p2 = parola.pauza_greseli(2)
    p3 = parola.pauza_greseli(3)
    assert p1 == 2.0 and p2 == 4.0 and p3 == 8.0
    assert p1 < p2 < p3
    assert parola.pauza_greseli(0) == 0.0
    assert parola.pauza_greseli(100) == 256.0  # plafonat la ~4 minute
    print("pauză crescătoare OK")


if __name__ == "__main__":
    test_definire_deschidere()
    test_parola_gresita()
    test_recuperare()
    test_schimbare_parola_aceeasi_cheie()
    test_serializare()
    test_pauza()
    print("TOATE OK")