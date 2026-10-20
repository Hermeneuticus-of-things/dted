"""Verifică contrastul de culoare (WCAG, prag 4,5:1) al paletei din ``comun.py``.

Citește culorile reale (temele luminos/întunecat din ``comun.Culori``), nu valori
hardcodate, ca testul să reflecte exact QSS-ul aplicat. Accentul (principal /
pericol / succes) se verifică și pe fundal, și pe card — cazul care, pe tema
întunecată, dădea înainte doar 3,78 pe card.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dictare_transcriere_romana.ui_qt import comun


def lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def lum(hexc):
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def crat(fg, bg):
    l1, l2 = lum(fg), lum(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def _pairs(t):
    """Perchi (etichetă, prim-plan, fundal) care trebuie să aibă contrast >= 4,5."""
    perechi = [
        ("text / fundal", t.text, t.fundal),
        ("text / card", t.text, t.card),
        ("text_secundar / fundal", t.text_secundar, t.fundal),
        ("text_secundar / card", t.text_secundar, t.card),
        ("rosu / rosu_fundal", t.rosu_text, t.rosu_fundal),
        ("verde / verde_fundal", t.verde_text, t.verde_fundal),
        ("atentie / galben_fundal", t.galben_text, t.galben_fundal),
        ("alb / buton principal", t.principal_text, t.principal),
        ("alb / buton pericol", t.pericol_text, t.pericol),
        ("alb / buton succes", t.succes_text, t.succes),
    ]
    # Accentele de text se verifică pe fundal ȘI pe card (cerința de accesibilitate).
    for nume, accent in (
        ("principal_acc", t.principal_accent),
        ("pericol_acc", t.pericol_accent),
        ("succes_acc", t.succes_accent),
    ):
        perechi.append((f"{nume} / fundal", accent, t.fundal))
        perechi.append((f"{nume} / card", accent, t.card))
    return perechi


def main() -> int:
    teme = (
        ("LUMINOS", comun.Culori()),
        ("ÎNTUNECAT", comun._TEMA_INTUNECATA),
    )
    esec = 0
    for nume, t in teme:
        print(f"== {nume} ==")
        for desc, fg, bg in _pairs(t):
            r = crat(fg, bg)
            ok = r >= 4.5
            if not ok:
                esec += 1
            print(f"  {r:5.2f}  {'OK' if ok else 'SUB 4,5!':9} {desc}  ({fg} pe {bg})")
    if esec:
        print(f"\n{esec} perechi SUB prag!")
        return 1
    print("\nToate perechile au contrast >= 4,5:1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())