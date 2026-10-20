"""Punctul de intrare al programului.

Exemple:
    python -m transcriere_locala                 # deschide fereastra (instalează dacă lipsește)
    python -m transcriere_locala --sari-verificarea
    python -m transcriere_locala --verifica      # doar verifică resursele, fără interfață
    python -m transcriere_locala --instaleaza --fara-gpu
    python -m transcriere_locala --transcrie fisier.mp3 --iesire rezultat.docx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcriere_locala",
        description="Transcriere și dictare locală, cu Whisper large-v3-turbo (offline după instalare).",
    )
    parser.add_argument(
        "--sari-verificarea",
        action="store_true",
        help="Sari peste verificarea resurselor (doar pentru utilizatori avansați).",
    )
    parser.add_argument(
        "--verifica", action="store_true", help="Verifică resursele și afișează rezultatul, apoi ieși."
    )
    parser.add_argument(
        "--instaleaza", action="store_true", help="Rulează instalarea din linia de comandă, fără fereastră."
    )
    parser.add_argument(
        "--interfata",
        action="store_true",
        help="Arată fereastra de verificare și instalare (se folosește împreună cu --instaleaza).",
    )
    parser.add_argument(
        "--fara-gpu", action="store_true", help="Instalează varianta pentru procesor (fără accelerare video)."
    )
    parser.add_argument(
        "--fara-wordcraft", action="store_true", help="Nu instala WordCraft."
    )
    parser.add_argument(
        "--transcrie", metavar="FISIER", help="Transcrie un fișier audio și salvează documentul."
    )
    parser.add_argument(
        "--iesire", metavar="FISIER", help="Unde se salvează documentul (.docx sau .odt)."
    )
    parser.add_argument(
        "--limba", default="ro", help="Limba transcrierii (implicit: ro)."
    )
    parser.add_argument(
        "--director", metavar="CALE", help="Folderul unde se instalează programul."
    )
    parser.add_argument(
        "--forteaza", action="store_true", help="Pornește fereastra principală chiar dacă instalarea pare incompletă."
    )
    return parser


def _verifica_consola() -> int:
    from . import resurse
    from .constante import DISC_MINIM_CU_GPU_GB, DISC_MINIM_GB, WHISPER_MIN_RAM_GB

    raport = resurse.verifica()
    print(resurse.text_pentru_consola(raport))
    print()
    print(f"Praguri scrise în cod: RAM minim {WHISPER_MIN_RAM_GB:.0f} GB, "
          f"disc minim {DISC_MINIM_GB:.0f} GB ({DISC_MINIM_CU_GPU_GB:.0f} GB cu placă video).")
    return 0 if raport.poate_instala else 2


def _instaleaza_consola(sari: bool, fara_gpu: bool, fara_wordcraft: bool, director: str | None) -> int:
    from . import instalare, resurse
    from .descarcare import SumaGresita

    if not sari:
        raport = resurse.verifica(Path(director) if director else None)
        print(resurse.text_pentru_consola(raport))
        if not raport.poate_instala:
            print("\nInstalarea nu poate continua: lipsește ceva obligatoriu (vezi mai sus).")
            return 2
        cu_gpu = raport.are_gpu
    else:
        print("Verificarea resurselor a fost sărită (--sari-verificarea).")
        cu_gpu = False

    if fara_gpu:
        cu_gpu = False

    def progres(mesaj: str, fractiune: float) -> None:
        bara = int(fractiune * 40)
        print(f"\r[{'#' * bara}{'.' * (40 - bara)}] {int(fractiune * 100):3d}%  {mesaj[:90]}", end="", flush=True)
        if fractiune >= 1.0:
            print()

    optiuni = instalare.Optiuni(
        cu_gpu=cu_gpu, instaleaza_wordcraft=not fara_wordcraft, sari_verificarea=sari
    )
    try:
        rezumat = instalare.instaleaza(optiuni, progres=progres, director=Path(director) if director else None)
    except SumaGresita as exc:
        print("\n\nInstalarea a fost oprită: un fișier nu corespunde sumei oficiale.")
        print(exc)
        return 3
    except instalare.EroareInstalare as exc:
        print("\n\nInstalarea nu s-a terminat.")
        print(exc)
        return 1
    print("\nInstalare încheiată:")
    for cheie, valoare in rezumat.items():
        print(f"  {cheie}: {valoare}")
    return 0


def _transcrie_consola(fisier: str, iesire: str | None, limba: str) -> int:
    from . import cai, documente, motor
    from .instalare import verifica_instalare

    probleme = verifica_instalare()
    if probleme:
        print("Transcrierea nu poate porni:")
        for problema in probleme:
            print("  •", problema)
        print("\nRulează: python -m transcriere_locala --instaleaza")
        return 1

    sursa = Path(fisier)
    if not sursa.exists():
        print(f"Fișierul nu există: {sursa}")
        return 1

    def progres(fractiune: float) -> None:
        bara = int(fractiune * 40)
        print(f"\r[{'#' * bara}{'.' * (40 - bara)}] {int(fractiune * 100):3d}%", end="", flush=True)

    def faza(mesaj: str) -> None:
        print(f"\n{mesaj}")

    print(f"Transcriu: {sursa.name} (limba: {limba})")
    rezultat = motor.MotorWhisper().transcrie(sursa, limba=limba, progres=progres, faza=faza)
    print(f"\nGata: {rezultat.cuvinte} cuvinte, {rezultat.secunde_audio:.0f}s audio în {rezultat.secunde_calcul:.0f}s.")

    if iesire:
        destinatie = Path(iesire)
    else:
        destinatie = cai.director_iesiri() / (documente.nume_document(sursa.stem) + ".docx")
    if destinatie.suffix.lower() == ".odt":
        documente.scrie_odt(rezultat.text, destinatie, titlu=documente.titlu_din_text(rezultat.text))
    else:
        documente.scrie_docx(rezultat.text, destinatie, titlu=documente.titlu_din_text(rezultat.text))
    print(f"Document salvat: {destinatie}")
    return 0


def _pregateste_consola() -> None:
    """Face ca diacriticele românești să se afișeze corect în consolă.

    Ferestrele de comandă vechi folosesc codificări care nu cunosc ș și ț;
    trecem ieșirea pe UTF-8 și, dacă nu se poate, înlocuim caracterele.
    """
    for flux in (sys.stdout, sys.stderr):
        if flux is None:
            continue
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _pregateste_consola()
    argumente = _parser().parse_args(argv)

    if argumente.director:
        import os

        os.environ["TRANSCRIERE_DIR"] = str(Path(argumente.director).expanduser().resolve())

    from . import cai, jurnal

    cai.pregateste_directoare()

    if argumente.verifica:
        return _verifica_consola()
    if argumente.instaleaza and argumente.interfata:
        from .ui_instalare import porneste

        porneste(sari_verificarea=argumente.sari_verificarea)
        return 0
    if argumente.instaleaza:
        return _instaleaza_consola(
            argumente.sari_verificarea, argumente.fara_gpu, argumente.fara_wordcraft, argumente.director
        )
    if argumente.transcrie:
        return _transcrie_consola(argumente.transcrie, argumente.iesire, argumente.limba)

    # Fără argumente: dacă instalarea e completă, deschidem direct aplicația.
    from . import config

    if config.instalare_completa() or argumente.forteaza:
        from .ui_principal import AplicatiePrincipala

        jurnal.info("Pornire aplicație principală.")
        AplicatiePrincipala().mainloop()
        return 0

    from .ui_instalare import porneste

    instalat = porneste(sari_verificarea=argumente.sari_verificarea)
    if instalat:
        # Fereastra de instalare s-a închis după o instalare reușită:
        # deschidem programul propriu-zis.
        from .ui_principal import AplicatiePrincipala

        jurnal.info("Instalare încheiată; pornesc aplicația principală.")
        AplicatiePrincipala().mainloop()
    return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
