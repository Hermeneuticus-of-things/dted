"""Intrarea în program: interfața, instalarea sau sarcinile din linia de comandă.

Aici se hotărăște ce face programul când este pornit:

* fără nicio opțiune (dublu-clic pe pictogramă) se deschide **interfața**:
  fereastra mare, cu dictare, transcriere de fișiere și editor;
* cu ``--instaleaza`` se deschide **instalarea** (un singur pas, fără întrebări
  tehnice);
* cu ``--verifica`` se tipărește în consolă ce are calculatorul (utile pentru
  depanare, fără să se deschidă vreo fereastră);
* cu ``--transcrie fisier.mp3 --format docx`` se transcrie un fișier fără
  interfață, pentru cine vrea să folosească programul din linia de comandă;
* cu ``--serviciu`` programul lucrează pentru alt program (de exemplu Scribner): primește
  comenzi și trimite textul prin intrarea și ieșirea standard, câte un JSON pe linie
  (vezi ``serviciu.py``); merge și când fereastra D&TED este deja deschisă;
* cu ``--dezinstaleaza`` se scoate programul de pe calculator, cu întrebare în
  fereastra programului.

Consola este adusă pe UTF-8 înainte de orice, ca diacriticele românești să se
scrie corect în orice terminal Windows.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _pregateste_consola() -> None:
    """Aduce consola Windows pe UTF-8, ca diacriticele să se vadă corect."""
    if os.name == "nt":
        try:
            os.system("chcp 65001 > nul")
        except Exception:
            pass
    for fir in (sys.stdout, sys.stderr):
        try:
            fir.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def _argumente(argv: list[str] | None = None) -> argparse.Namespace:
    """Citește opțiunile din linia de comandă."""
    parser = argparse.ArgumentParser(
        prog="dictare_transcriere_romana",
        description=(
            "Dictate & Transcription Express Digital (D&TED) — scrie text din vocea ta sau dintr-un "
            "fișier audio. Totul se face pe calculatorul tău, fără internet."
        ),
    )
    parser.add_argument("--instaleaza", action="store_true", help="deschide instalarea")
    parser.add_argument("--interfata", action="store_true", help="deschide fereastra programului (implicit)")
    parser.add_argument("--dezinstaleaza", action="store_true", help="scoate programul de pe calculator")
    parser.add_argument("--verifica", action="store_true", help="scrie în consolă ce are calculatorul")
    parser.add_argument("--pregateste", action="store_true", help="descarcă modelul (și CUDA, cu placă NVIDIA), fără ferestre")
    parser.add_argument("--serviciu", action="store_true", help="lucrează pentru alt program (Scribner): comenzi JSON pe intrarea standard")
    parser.add_argument("--transcrie", metavar="FIȘIER", help="transcrie un fișier audio, fără interfață")
    parser.add_argument("--format", default="docx", help="în ce format se salvează (docx, odt, txt, srt, vtt)")
    parser.add_argument("--limba", default="", help="limba vorbită în înregistrare (implicit: cea din setări)")
    parser.add_argument("--folder", default="", help="folderul în care se salvează documentele")
    parser.add_argument("--folder-instalare", default="", help="folderul în care se instalează programul")
    parser.add_argument("--sari-verificarea", action="store_true", help="la instalare: nu opri instalarea pe cerințe")
    parser.add_argument("--fara-gpu", action="store_true", help="la instalare: folosește doar procesorul")
    parser.add_argument("--fara-libreoffice", action="store_true", help="la instalare: nu instala LibreOffice")
    return parser.parse_args(argv)


def _pune_folderele(argumente: argparse.Namespace) -> None:
    """Ține minte folderele cerute din linia de comandă."""
    if argumente.folder:
        os.environ["DICTARE_IESIRI"] = str(Path(argumente.folder))
    if argumente.folder_instalare:
        os.environ["DICTARE_DIR"] = str(Path(argumente.folder_instalare))


def _verifica() -> int:
    """Tipărește, în cuvinte simple, ce are calculatorul. Fără ferestre."""
    from . import cai, codecuri, config as config_modul, drivere, instalare, libreoffice, resurse

    print(f"Verificarea calculatorului pentru program:")
    raport = resurse.verifica(config_modul.director_iesiri(config_modul.incarca()))
    print(resurse.text_pentru_consola(raport))
    print()
    print("Ce este instalat acum:")
    lipsa = instalare.verifica_instalare()
    if lipsa:
        for rand in lipsa:
            print(f"  ✘ {rand}")
    else:
        print("  ✔ Părțile de transcriere sunt la locul lor.")
    if raport.are_gpu and cai.python_mediu().exists() and not getattr(instalare, "_are_cuda", lambda _p: True)(cai.python_mediu()):
        print("  ! Accelerarea CUDA nu este instalată; transcrierea folosește procesorul.")
    try:
        stare_codecuri = codecuri.verifica()
        semn = "✔" if stare_codecuri.ok else "!"
        print(f"  {semn} Fișierele audio: {stare_codecuri.pentru_utilizator()}")
    except Exception as exc:
        print(f"  ! Fișierele audio: nu am putut verifica ({exc})")
    try:
        stare_lo = libreoffice.stare()
        semn = "✔" if stare_lo.gasit else "!"
        print(f"  {semn} LibreOffice: {stare_lo.pentru_utilizator()}")
    except Exception as exc:
        print(f"  ! LibreOffice: nu am putut verifica ({exc})")
    try:
        stare_dr = drivere.verifica()
        semn = "✔" if stare_dr.totul_ok else "!"
        print(f"  {semn} Drivere: {stare_dr.rezumat()}")
    except Exception as exc:
        print(f"  ! Drivere: nu am putut verifica ({exc})")

    def este_ok() -> bool:
        try:
            raport_calculator = resurse.verifica()
        except Exception:
            return True
        return raport_calculator.poate_instala

    return 0 if este_ok() and not lipsa else 2


def _transcrie(argumente: argparse.Namespace) -> int:
    """Transcrie un fișier audio fără interfață și salvează documentul."""
    from . import biblioteca, config as config_modul, documente, motor as motor_mod, text_ro

    cale = Path(argumente.transcrie).expanduser()
    if not cale.exists():
        print(f"Nu găsesc fișierul „{cale}”.")
        return 1
    setari = config_modul.incarca()
    limba = argumente.limba or setari.limba or "ro"
    print(f"Transcriu „{cale.name}” (limba: {limba}). Durează în funcție de lungimea înregistrării.")
    motor = motor_mod.MotorWhisper(getattr(setari, "dispozitiv", "auto"))

    def progres(fractiune: float) -> None:
        print(f"\r  {int(round(max(0.0, min(1.0, fractiune)) * 100)):3d}%", end="", flush=True)

    def faza(mesaj: str) -> None:
        print(f"\n  {mesaj}")

    try:
        rezultat = motor.transcrie(cale, limba=limba, progres=progres, faza=faza)
    except Exception as exc:
        print(f"\nTranscrierea nu a reușit: {exc}")
        return 1
    finally:
        try:
            motor.elibereaza()
        except Exception:
            pass
    print()
    if not rezultat.text.strip():
        print("Nu am auzit nicio vorbă în acest fișier. Textul este gol.")
        return 1
    marca = biblioteca.marca_din_nume(cale)
    format_cerut = documente.extensie_potrivita(argumente.format) or "docx"
    if format_cerut == "pdf":
        print("PDF-ul se face din interfață (are nevoie de LibreOffice). Salvez ca ODT.")
        format_cerut = "odt"
    destinatie = biblioteca.nume_unic(
        biblioteca.folder("documente"), biblioteca.nume_legat(marca, f".{format_cerut}")
    )
    documente.salveaza(
        rezultat.text,
        destinatie,
        titlu=marca,
        subtitlu="Transcriere făcută cu programul „Dictate & Transcription Express Digital (D&TED)”.",
        segmente=rezultat.segmente,
        secunde=rezultat.secunde_audio,
    )
    cale_text = biblioteca.folder("text") / f"{marca}.txt"
    try:
        cale_text.write_text(rezultat.text, encoding="utf-8", newline="\r\n")
    except OSError:
        pass
    print(f"Gata! {text_ro.durata_text(rezultat.secunde_calcul)} de calcul pentru "
          f"{text_ro.durata_text(rezultat.secunde_audio)} de sunet.")
    print(f"Documentul este salvat aici: {destinatie}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Pornește programul în felul cerut."""
    _pregateste_consola()
    argumente = _argumente(argv)
    _pune_folderele(argumente)

    # Modul serviciu (Scribner): fără ferestre, deci și lângă fereastra deja deschisă.
    if argumente.serviciu:
        from . import serviciu

        return serviciu.ruleaza()

    # Cerinta 44: o singura instanta. Daca programul ruleaza deja, iesim.
    try:
        import ctypes
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "DTED_SingleInstance_Mutex_v1")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            try:
                from . import ui_comun
                ui_comun.anunta(None, "Programul este deja deschis",
                                 "D&TED ruleaza deja. Foloseste fereastra existenta.")
            except Exception:
                pass
            return 1
    except Exception:
        pass

    from . import cai, jurnal

    cai.pregateste_directoare()
    jurnal.info(
        "Pornire: "
        + " ".join(
            optiune
            for optiune in (
                "--instaleaza" if argumente.instaleaza else "",
                "--dezinstaleaza" if argumente.dezinstaleaza else "",
                "--verifica" if argumente.verifica else "",
                f"--transcrie {argumente.transcrie}" if argumente.transcrie else "",
            )
            if optiune
        )
        or "interfață"
    )

    if argumente.verifica:
        return _verifica()
    if argumente.pregateste:
        from . import pregatire

        return pregatire.main()
    if argumente.dezinstaleaza:
        from . import ui_instalare

        reusit = ui_instalare.dezinstaleaza_cu_fereastra()
        return 0 if reusit else 1
    if argumente.transcrie:
        return _transcrie(argumente)
    if argumente.instaleaza:
        from . import ui_instalare

        return ui_instalare.ruleaza_standalone(
            presetari={
                "sari_verificarea": bool(argumente.sari_verificarea),
                "fara_gpu": bool(argumente.fara_gpu),
                "fara_libreoffice": bool(argumente.fara_libreoffice),
            }
        )
    if argumente.interfata:
        # Forțează deschiderea interfeței, chiar dacă instalarea e incompletă
        from .ui_qt import principal as ui_principal_qt

        return ui_principal_qt.ruleaza()

    # Fără nicio opțiune: verificăm instalarea înainte de fereastra principală.
    from . import instalare

    if instalare._biblioteci_in_proces():
        # Bibliotecile sunt în pachet: fereastra principală descarcă singură, la prima
        # pornire, ce mai lipsește (modelul și, cu placă NVIDIA, bibliotecile CUDA).
        from .ui_qt import principal as ui_principal_qt

        return ui_principal_qt.ruleaza()

    lipsuri = instalare.verifica_instalare()
    if lipsuri:
        jurnal.info(f"Instalare incompletă ({lipsuri}). Pornește asistentul de instalare.")
        from . import ui_instalare

        cod = ui_instalare.ruleaza_standalone(
            presetari={
                "sari_verificarea": bool(argumente.sari_verificarea),
                "fara_gpu": bool(argumente.fara_gpu),
                "fara_libreoffice": bool(argumente.fara_libreoffice),
            }
        )
        if cod != 0:
            return cod
        if not instalare.verifica_instalare():
            from .ui_qt import principal as ui_principal_qt

            return ui_principal_qt.ruleaza()
        return 0

    # Fereastra programului principal.
    from .ui_qt import principal as ui_principal_qt

    return ui_principal_qt.ruleaza()


if __name__ == "__main__":  # pragma: no cover - se rulează doar din linia de comandă
    raise SystemExit(main())
