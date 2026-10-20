"""Pictograma programului (fișier .ico), desenată fără biblioteci externe.

Se folosește la scurtăturile de pe Desktop și din meniul Start, la fereastra
programului și în lista de programe din Windows. Este desenată cu cod simplu
(un microfon alb pe fundal albastru), ca programul să nu depindă de fișiere
externe sau de biblioteci de imagini.
"""

from __future__ import annotations

import struct
from pathlib import Path

#: Dimensiunile incluse în fișierul .ico.
DIMENSIUNI = (16, 24, 32, 48, 64, 128, 256)

#: Culorile pictogramei.
_ALBASTRU_SUS = (44, 94, 176)
_ALBASTRU_JOS = (21, 56, 120)
_ALB = (255, 255, 255)
_ALB_UMBRA = (226, 235, 250)


def _interpolare(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))  # type: ignore[return-value]


def _in_rotunjit(x: float, y: float, raza: float) -> bool:
    """Adevărat dacă punctul este în pătratul rotunjit [-1,1]x[-1,1]."""
    if abs(x) > 1.0 or abs(y) > 1.0:
        return False
    colt = 1.0 - raza
    if abs(x) > colt and abs(y) > colt:
        return (abs(x) - colt) ** 2 + (abs(y) - colt) ** 2 <= raza**2
    return True


def _in_capsula_microfon(x: float, y: float) -> bool:
    """Corpul microfonului: o capsulă rotunjită, în partea de sus."""
    jumatate = 0.20
    sus, jos = -0.62, 0.10
    if abs(x) > jumatate:
        return False
    if y < sus - jumatate or y > jos + jumatate:
        return False
    if y < sus:
        return (y - sus) ** 2 + x**2 <= jumatate**2
    if y > jos:
        return (y - jos) ** 2 + x**2 <= jumatate**2
    return True


def _in_arc_suport(x: float, y: float) -> bool:
    """Arcul care ține microfonul (ca o potcoavă întoarsă)."""
    raza = 0.40
    grosime = 0.045
    distanta = (x**2 + y**2) ** 0.5
    return 0.0 <= y <= 0.45 and abs(distanta - raza) <= grosime


def _in_tija(x: float, y: float) -> bool:
    """Tija verticală și baza microfonului."""
    if abs(x) <= 0.045 and 0.38 <= y <= 0.66:
        return True
    return abs(x) <= 0.20 and 0.62 <= y <= 0.72


def _pixel(x: float, y: float) -> tuple[int, int, int, int] | None:
    """Culoarea unui punct, în coordonate normale (-1..1). ``None`` = gol."""
    if not _in_rotunjit(x, y, 0.34):
        return None
    culoare = _interpolare(_ALBASTRU_SUS, _ALBASTRU_JOS, (y + 1) / 2)
    if _in_capsula_microfon(x, y) or _in_arc_suport(x, y) or _in_tija(x, y):
        # Microfonul este alb, cu o umbră ușoară la dreapta, ca să pară rotund.
        culoare_microfon = _ALB_UMBRA if x > 0.10 else _ALB
        return (*culoare_microfon, 255)
    return (*culoare, 255)


def _deseneaza(dimensiune: int) -> list[list[tuple[int, int, int, int] | None]]:
    """Desenează pictograma, cu 3x3 mostre pe pixel (margini netede)."""
    randuri: list[list[tuple[int, int, int, int] | None]] = []
    for rand in range(dimensiune):
        linie: list[tuple[int, int, int, int] | None] = []
        for coloana in range(dimensiune):
            r_sum = g_sum = b_sum = a_sum = 0
            for sub_rand in range(3):
                for sub_coloana in range(3):
                    x = (coloana + (sub_coloana + 0.5) / 3) / dimensiune * 2 - 1
                    y = (rand + (sub_rand + 0.5) / 3) / dimensiune * 2 - 1
                    pixel = _pixel(x, y)
                    if pixel is None:
                        continue
                    r_sum += pixel[0]
                    g_sum += pixel[1]
                    b_sum += pixel[2]
                    a_sum += 255
            if a_sum == 0:
                linie.append(None)
                continue
            acoperire = a_sum / (9 * 255)
            linie.append(
                (
                    int(round(r_sum / (a_sum / 255))),
                    int(round(g_sum / (a_sum / 255))),
                    int(round(b_sum / (a_sum / 255))),
                    int(round(acoperire * 255)),
                )
            )
        randuri.append(linie)
    return randuri


def _imagine_ico(dimensiune: int) -> bytes:
    """Datele unei dimensiuni, în formatul cerut de un fișier .ico."""
    randuri = _deseneaza(dimensiune)
    date = bytearray()
    # Antetul imaginii (BITMAPINFOHEADER), cu înălțime dublă (mască + culoare).
    date += struct.pack(
        "<IiiHHIIiiII", 40, dimensiune, dimensiune * 2, 1, 32, 0, 0, 0, 0, 0, 0
    )
    # Punctele, de jos în sus, în ordinea BGRA.
    for rand in reversed(randuri):
        for pixel in rand:
            if pixel is None:
                date += b"\x00\x00\x00\x00"
            else:
                r, g, b, a = pixel
                date += bytes((b, g, r, a))
    # Masca de transparență (1 bit pe pixel, rânduri de 4 octeți).
    latime_masca = ((dimensiune + 31) // 32) * 4
    for rand in reversed(randuri):
        linie = bytearray(latime_masca)
        for coloana, pixel in enumerate(rand):
            if pixel is None or pixel[3] < 128:
                linie[coloana // 8] |= 1 << (7 - (coloana % 8))
        date += bytes(linie)
    return bytes(date)


def construieste_ico() -> bytes:
    """Conținutul complet al fișierului .ico, cu toate dimensiunile."""
    imagini = [_imagine_ico(dimensiune) for dimensiune in DIMENSIUNI]
    antet = struct.pack("<HHH", 0, 1, len(imagini))
    offset = len(antet) + 16 * len(imagini)
    intrari = bytearray()
    for dimensiune, imagine in zip(DIMENSIUNI, imagini):
        latime = 0 if dimensiune >= 256 else dimensiune
        intrari += struct.pack("<BBBBHHII", latime, latime, 0, 0, 1, 32, len(imagine), offset)
        offset += len(imagine)
    return antet + bytes(intrari) + b"".join(imagini)


def scrie_iconita(cale: Path) -> Path | None:
    """Scrie fișierul .ico — preferă fișierul artistic existent, altfel generează."""
    try:
        cale = Path(cale)
        if cale.exists() and cale.stat().st_size > 0:
            return cale
        # Încearcă să copieze pictograma artistică din pachetul sursă.
        sursa_pachet = Path(__file__).with_name("iconita_dictare.ico")
        if sursa_pachet.exists() and sursa_pachet.stat().st_size > 0:
            cale.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(sursa_pachet, cale)
            return cale
        # Fallback: generează programatic.
        cale.parent.mkdir(parents=True, exist_ok=True)
        cale.write_bytes(construieste_ico())
        return cale
    except OSError:
        return None
