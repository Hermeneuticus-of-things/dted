"""LibreOffice: descărcare verificată, instalare silențioasă, română gata.

Programul de scris folosit de acest program este **LibreOffice** (suita
gratuită și open-source a The Document Foundation). Aici se fac:

* descărcarea pachetului oficial (Windows x86_64 / aarch64 / x86) și a
  ajutorului în română, cu verificarea sumei SHA-256 publicate oficial;
* instalarea silențioasă, fără ferestre și fără întrebări tehnice;
* configurarea pentru limba română (meniuri, dicționar, ortografie automată)
  și oprirea verificărilor de actualizări și a trimiterii de date;
* deschiderea documentelor în LibreOffice Writer și conversia în PDF.

Pe Windows, pachetul principal LibreOffice conține deja toate limbile de
meniu și dicționarele, iar româna se alege la instalare (``UI_LANGS=ro``).
Ajutorul în română vine în pachetul separat „helppack_ro”.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import cai, jurnal
from .constante import (
    LIBREOFFICE_AJUTOR_MSI,
    LIBREOFFICE_FISIER_MENIU,
    LIBREOFFICE_FOLDER,
    LIBREOFFICE_FOLDER_MENIU,
    LIBREOFFICE_LIMBA,
    LIBREOFFICE_MSI,
    LIBREOFFICE_VERSIUNE,
    NUME_APLICATIE,
)
from .descarcare import EroareDescarcare, SumaGresita, descarca_verificat, suma_oficiala

Progres = Callable[[str, float], None]
FLAG_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Coduri de ieșire msiexec care înseamnă „a mers”.
CODURI_OK = {0, 3010, 1641}


class EroareLibreOffice(RuntimeError):
    """Instalarea LibreOffice nu a reușit; mesajul este pentru utilizator."""

    def __init__(self, mesaj: str, ce_fac: str = "", detalii: str = ""):
        super().__init__(mesaj)
        self.ce_fac = ce_fac
        self.detalii = detalii


@dataclass
class StareLibreOffice:
    """Ce s-a găsit sau ce s-a instalat."""

    executabil: Path | None = None
    versiune: str = ""
    are_meniu_romana: bool = False
    are_dictionar_romana: bool = False
    are_ajutor_romana: bool = False
    instalat_acum: bool = False

    @property
    def gasit(self) -> bool:
        return self.executabil is not None

    def ce_lipseste(self) -> list[str]:
        """Lista simplă a lucrurilor de care lipsește în limba română."""
        lipsa: list[str] = []
        if not self.gasit:
            lipsa.append("LibreOffice nu este instalat deloc.")
            return lipsa
        if not self.are_meniu_romana:
            lipsa.append("Meniurile și ferestrele nu sunt în română.")
        if not self.are_dictionar_romana:
            lipsa.append("Lipsește dicționarul ortografic românesc.")
        if not self.are_ajutor_romana:
            lipsa.append("Lipsește ajutorul în română (se poate adăuga oricând).")
        return lipsa

    def pentru_utilizator(self) -> str:
        """Mesajul simplu, în română, despre starea LibreOffice."""
        if not self.gasit:
            return (
                "LibreOffice nu este instalat. Poți totuși salva documentele ca DOCX, "
                "ODT sau PDF și le poți deschide cu orice alt program de scris."
            )
        if self.are_meniu_romana and self.are_dictionar_romana:
            return (
                "LibreOffice s-a instalat în română, cu dicționarul românesc. "
                "Poți începe să scrii."
            )
        return (
            "LibreOffice este instalat, dar lipsește: "
            + " ".join(self.ce_lipseste())
            + " Apasă «Încearcă din nou» ca să adaug ce lipsește."
        )


# --------------------------------------------------------------------------- găsire


def _citeste_registru() -> Path | None:
    """Calea către LibreOffice, citită din registrul Windows."""
    try:
        import winreg  # type: ignore[import-not-found]
    except Exception:
        return None

    cale = r"SOFTWARE\LibreOffice\UNO\InstallPath"
    variante = [
        (winreg.HKEY_CURRENT_USER, 0),
        (winreg.HKEY_LOCAL_MACHINE, 0),
        (winreg.HKEY_LOCAL_MACHINE, getattr(winreg, "KEY_WOW64_64KEY", 0)),
        (winreg.HKEY_LOCAL_MACHINE, getattr(winreg, "KEY_WOW64_32KEY", 0)),
    ]
    for radacina, flag in variante:
        try:
            with winreg.OpenKey(radacina, cale, 0, winreg.KEY_READ | flag) as handle:
                valoare, _ = winreg.QueryValueEx(handle, "")
        except OSError:
            continue
        folder = Path(str(valoare))
        executabil = _soffice_din(folder)
        if executabil:
            return executabil
    return None


def _soffice_din(folder: Path) -> Path | None:
    """Caută ``soffice.exe`` în folderul indicat (direct sau în ``program``)."""
    candidati = [
        Path(folder) / "soffice.exe",
        Path(folder) / "program" / "soffice.exe",
    ]
    for candidat in candidati:
        if candidat.exists():
            return candidat
    return None


def _locatii_obisnuite() -> list[Path]:
    """Locații în care Windows instalează de obicei LibreOffice."""
    radacini = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramW6432"),
        os.environ.get("LOCALAPPDATA"),
    ]
    locatii: list[Path] = []
    for radacina in radacini:
        if not radacina:
            continue
        baza = Path(radacina)
        locatii.append(baza / "LibreOffice" / "program" / "soffice.exe")
        if radacina == os.environ.get("LOCALAPPDATA"):
            locatii.append(baza / "Programs" / "LibreOffice" / "program" / "soffice.exe")
    return locatii


def gaseste_libreoffice() -> Path | None:
    """Găsește LibreOffice pe calculator, indiferent cum a fost instalat."""
    din_registru = _citeste_registru()
    if din_registru:
        return din_registru
    for cale in _locatii_obisnuite():
        if cale.exists():
            return cale
    import shutil

    gasit = shutil.which("soffice")
    return Path(gasit) if gasit else None


def versiune(executabil: Path | None) -> str:
    """Versiunea LibreOffice, citită din fișierul oficial „version.ini”."""
    if not executabil:
        return ""
    fisiere = [
        executabil.parent / "version.ini",
        executabil.parent.parent / "program" / "version.ini",
    ]
    for fisier in fisiere:
        try:
            if not fisier.exists():
                continue
            for linie in fisier.read_text(encoding="utf-8", errors="replace").splitlines():
                if linie.startswith("AboutBoxProductVersion") or linie.startswith("AboutBoxVersion"):
                    valoare = linie.split("=", 1)[1].strip()
                    if valoare:
                        return valoare
            return ""
        except OSError:
            continue
    return ""


def _folder_instalare(executabil: Path) -> Path:
    """Folderul principal al instalării LibreOffice."""
    parinte = executabil.parent
    return parinte.parent if parinte.name.lower() == "program" else parinte


def are_dictionar_romana(executabil: Path | None) -> bool:
    """Verifică dacă instalarea are dicționarul românesc (pentru ortografie)."""
    if not executabil:
        return False
    baza = _folder_instalare(executabil)
    # 1. dicționarele clasice
    for folder in (baza / "share" / "dict" / "ooo", baza / "share" / "dict"):
        try:
            if folder.exists() and any(folder.glob("ro_RO.*")):
                return True
        except OSError:
            continue
    # 2. extensiile de dicționare (dic-ro, dict-ro etc.)
    extensii = baza / "share" / "extensions"
    try:
        for intrare in extensii.iterdir():
            nume = intrare.name.lower()
            if not intrare.is_dir():
                continue
            if "ro" in nume.split("-")[-1:] or nume in ("dict-ro", "dic-ro"):
                return True
            dictionare = intrare / "dictionaries"
            try:
                if dictionare.exists() and any(dictionare.glob("ro*")):
                    return True
            except OSError:
                continue
    except OSError:
        pass
    # 3. dicționarul poate fi și în profilul utilizatorului
    profil = _cale_profil()
    try:
        if (profil / "wordbook").exists():
            pass
        if profil.exists() and any(profil.rglob("ro_RO.dic")):
            return True
    except OSError:
        pass
    return False


def are_meniu_romana(executabil: Path | None) -> bool:
    """Verifică dacă instalarea are meniurile și ferestrele în română.

    Pe Windows, instalatorul principal LibreOffice conține deja toate limbile
    de meniu: pentru fiecare limbă există un fișier ``Langpack-<limba>.xcd``
    în folderul ``share/registry``. Prezența lui arată că româna este
    disponibilă pentru interfață.
    """
    if not executabil:
        return False
    baza = _folder_instalare(executabil)
    registru = baza / LIBREOFFICE_FOLDER_MENIU
    try:
        if (registru / LIBREOFFICE_FISIER_MENIU).exists():
            return True
        # Variante scrise cu altă literă mare sau cu locale complet.
        if registru.exists():
            for candidat in registru.glob(f"Langpack-{LIBREOFFICE_LIMBA}*.xcd"):
                return True
            for candidat in registru.glob(f"*{LIBREOFFICE_LIMBA}_RO*.xcd"):
                return True
    except OSError:
        pass
    return False


def are_ajutor_romana(executabil: Path | None) -> bool:
    """Verifică dacă instalarea are ajutorul în română (pachetul helppack_ro)."""
    if not executabil:
        return False
    baza = _folder_instalare(executabil)
    for folder in (baza / "help" / "ro", baza / "help" / "ro-RO"):
        try:
            if folder.exists():
                return True
        except OSError:
            continue
    return False


def stare() -> StareLibreOffice:
    """Starea completă: unde este, ce versiune, dacă are româna."""
    executabil = gaseste_libreoffice()
    return StareLibreOffice(
        executabil=executabil,
        versiune=versiune(executabil),
        are_meniu_romana=are_meniu_romana(executabil),
        are_dictionar_romana=are_dictionar_romana(executabil),
        are_ajutor_romana=are_ajutor_romana(executabil),
    )


# --------------------------------------------------------------------------- profil

_ITEMI_PROFIL = [
    # meniuri și ferestre în română
    ('/org.openoffice.Setup/L10N', 'ooSetupSystemLocale', 'ro-RO'),
    ('/org.openoffice.Setup/L10N', 'ooLocale', 'ro'),
    # limba implicită a documentelor: română (România)
    ('/org.openoffice.Office.Linguistic/General', 'DefaultLocale', 'ro-RO'),
    ('/org.openoffice.Office.Linguistic/General', 'DefaultLocaleCtl', 'ro-RO'),
    ('/org.openoffice.Office.Linguistic/General', 'DefaultLocaleAsian', 'ro-RO'),
    # verificarea ortografică automată, cât se scrie
    ('/org.openoffice.Office.Common/SpellChecking', 'AutoSpellcheck', 'true'),
    ('/org.openoffice.Office.Writer/Content', 'AutoSpellcheck', 'true'),
    # fără verificarea actualizărilor și fără trimiterea de date
    (
        "/org.openoffice.Office.Jobs/Jobs/org.openoffice.Office.Jobs:Job['UpdateCheck']/Arguments",
        'Enabled',
        'false',
    ),
    (
        "/org.openoffice.Office.Jobs/Jobs/org.openoffice.Office.Jobs:Job['CrashReport']/Arguments",
        'Enabled',
        'false',
    ),
    ('/org.openoffice.Office.Common/SendCrashMail', 'SendCrashMail', 'false'),
]


def _cale_profil() -> Path:
    """Folderul de setări al LibreOffice pentru utilizatorul curent."""
    appdata = os.environ.get("APPDATA")
    baza = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return baza / "LibreOffice" / "4" / "user"


def _fisier_profil() -> Path:
    return _cale_profil() / "registrymodifications.xcu"


_ANTET_PROFIL = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
    'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
)
_FINAL_PROFIL = "</oor:items>\n"


def _valoare_profil(valoare: str, tip: str) -> str:
    if tip == "bool":
        return f'<value>{valoare}</value>'
    return f'<value>{valoare}</value>'


def configureaza_profil_romana() -> bool:
    """Pregătește LibreOffice pentru română, pentru utilizatorul curent.

    Se scriu doar valorile necesare, păstrând tot ce era deja în fișierul de
    setări al utilizatorului (adică setările lui nu sunt pierdute).
    """
    fisier = _fisier_profil()
    try:
        fisier.parent.mkdir(parents=True, exist_ok=True)
        continut = fisier.read_text(encoding="utf-8", errors="replace") if fisier.exists() else _ANTET_PROFIL + _FINAL_PROFIL
        if "<oor:items" not in continut:
            continut = _ANTET_PROFIL + _FINAL_PROFIL

        for cale, nume, valoare in _ITEMI_PROFIL:
            continut = _seteaza_prop(continut, cale, nume, valoare)

        if not continut.rstrip().endswith("</oor:items>"):
            continut = continut.replace(_FINAL_PROFIL, "") + _FINAL_PROFIL
        fisier.write_text(continut, encoding="utf-8")
        jurnal.instalare(
            "LibreOffice a fost configurat în română (meniuri, limbă implicită, "
            "ortografie automată, fără actualizări automate)."
        )
        return True
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut scrie setările LibreOffice: {exc}")
        return False


def _seteaza_prop(continut: str, cale: str, nume: str, valoare: str) -> str:
    """Pune (sau înlocuiește) o valoare în fișierul de setări LibreOffice."""
    import re

    item = (
        f'<item oor:path="{cale}"><prop oor:name="{nume}" oor:op="fuse">'
        f"<value>{valoare}</value></prop></item>\n"
    )
    model = re.compile(
        r'<item\s+oor:path="' + re.escape(cale) + r'">\s*'
        r'<prop\s+oor:name="' + re.escape(nume) + r'".*?</item>\s*',
        re.DOTALL,
    )
    if model.search(continut):
        return model.sub(item, continut, count=1)
    return continut.replace(_FINAL_PROFIL, item + _FINAL_PROFIL, 1)


# --------------------------------------------------------------------------- instalare


def _url_pachet(descriere: dict) -> str:
    return f"{LIBREOFFICE_FOLDER}/{descriere['folder']}/{descriere['nume']}"


def _spune(progres: Progres | None, mesaj: str, fractiune: float) -> None:
    jurnal.instalare(mesaj)
    if progres:
        try:
            progres(mesaj, max(0.0, min(1.0, fractiune)))
        except Exception:
            pass


def _descarca_pachet(descriere: dict, progres: Progres | None, baza: float, spatiu: float) -> Path:
    """Descarcă un pachet oficial, după ce îi află suma publicată oficial."""
    url = _url_pachet(descriere)
    destinatie = cai.director_descarcari() / descriere["nume"]

    _spune(progres, f"Verific pachetul oficial {descriere['nume']}…", baza)
    suma = suma_oficiala(url, descriere.get("sha256", ""))
    if not suma:
        raise EroareLibreOffice(
            "Nu am putut afla suma de control a pachetului LibreOffice.",
            ce_fac=(
                "Verifică legătura la internet, apoi apasă «Încearcă din nou». "
                "Fără suma oficială nu pot verifica fișierul, deci nu îl instalez."
            ),
        )

    def arata(descarcat: int, total: int) -> None:
        estimat = total or descriere.get("bytes") or 0
        procent = (descarcat / estimat) if estimat else 0.0
        from .descarcare import text_progres

        _spune(
            progres,
            text_progres(descarcat, estimat, "Descarc LibreOffice" if "helppack" not in descriere["nume"] else "Descarc ajutorul în română"),
            baza + spatiu * min(1.0, procent),
        )

    try:
        return descarca_verificat(url, destinatie, suma, arata, eticheta=descriere["nume"])
    except SumaGresita:
        raise
    except EroareDescarcare as exc:
        raise EroareLibreOffice(
            "Pachetul LibreOffice nu a putut fi descărcat.",
            ce_fac=str(exc),
            detalii=str(exc),
        ) from exc


def _argumente_msiexec(pachet: Path, jurnal_msi: Path, per_utilizator: bool) -> list[str]:
    """Argumentele msiexec, ca listă, cu româna aleasă și fără întrebări.

    Se folosește o listă (nu un text împărțit după spații), ca numele și căile
    care conțin spații, diacritice sau semnul „&” să rămână un singur
    argument și să nu strice comanda.
    """
    argumente = [
        "/i",
        str(pachet),
        "/qn",
        "/norestart",
        "/l*v",
        str(jurnal_msi),
        f"UI_LANGS={LIBREOFFICE_LIMBA}",
        "CREATEDESKTOPLINK=0",
        "REGISTER_NO_MSO_TYPES=1",
        "ISCHECKFORPRODUCTUPDATES=0",
        "REBOOT=ReallySuppress",
        "SELECT_WORD=1",
        "SELECT_EXCEL=0",
        "SELECT_POWERPOINT=0",
    ]
    if per_utilizator:
        argumente += ["ALLUSERS=2", "MSIINSTALLPERUSER=1"]
    else:
        argumente.append("ALLUSERS=1")
    return argumente


def _linie_comanda(argumente: list[str]) -> str:
    """Aceleași argumente, ca text, pentru cererea de drepturi de administrator.

    Fiecare argument care conține spații sau semnul „&” este pus între
    ghilimele, ca Windows să îl trateze ca o singură bucată.
    """
    parti: list[str] = []
    for argument in argumente:
        if any(semn in argument for semn in ' &()^"'):
            parti.append('"' + argument.replace('"', '\\"') + '"')
        else:
            parti.append(argument)
    return " ".join(parti)


def _ruleaza_msiexec(argumente: list[str], asteapta: bool = True) -> int:
    """Rulează msiexec; dacă are nevoie de drepturi, Windows cere permisiunea."""
    if asteapta:
        try:
            rezultat = subprocess.run(
                ["msiexec.exe", *argumente],
                capture_output=True,
                text=True,
                timeout=5400,
                creationflags=FLAG_NO_WINDOW,
            )
            return rezultat.returncode
        except (OSError, subprocess.SubprocessError) as exc:
            jurnal.instalare(f"msiexec nu a pornit: {exc}")
            return -1
    # Pornire cu cerere de drepturi de administrator (Windows afișează o
    # singură întrebare, pe care utilizatorul o acceptă).
    try:
        rezultat = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "msiexec.exe", _linie_comanda(argumente), None, 0
        )
        return 0 if rezultat > 32 else -2
    except Exception as exc:  # pragma: no cover - depinde de Windows
        jurnal.instalare(f"Nu am putut cere drepturi pentru msiexec: {exc}")
        return -2


def _asteapta_msiexec(secunde_max: int = 5400) -> None:
    """Așteaptă terminarea instalării cerute cu drepturi de administrator."""
    import shutil

    tasklist = shutil.which("tasklist")
    if not tasklist:
        time.sleep(60)
        return
    inceput = time.time()
    while time.time() - inceput < secunde_max:
        try:
            rezultat = subprocess.run(
                [tasklist, "/FI", "IMAGENAME eq msiexec.exe", "/NH"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=FLAG_NO_WINDOW,
            )
            if "msiexec.exe" not in (rezultat.stdout or "").lower():
                return
        except (OSError, subprocess.SubprocessError):
            return
        time.sleep(5)


def instaleaza_pachet(pachet: Path, progres: Progres | None, baza: float, este_ajutor: bool) -> bool:
    """Instalează un pachet MSI: întâi fără drepturi, apoi cu permisiune."""
    eticheta = "ajutorul în română" if este_ajutor else "LibreOffice"
    jurnal_msi = cai.director_libreoffice() / f"msiexec_{pachet.stem}.log"
    cai.director_libreoffice().mkdir(parents=True, exist_ok=True)

    _spune(progres, f"Instalez {eticheta}… (nu închide calculatorul)", baza)

    cod = _ruleaza_msiexec(_argumente_msiexec(pachet, jurnal_msi, per_utilizator=True))
    if cod in CODURI_OK:
        return True
    jurnal.instalare(
        f"Instalarea fără drepturi de administrator a codului {pachet.name} a "
        f"returnat codul {cod}; încerc varianta pentru toți utilizatorii."
    )

    _spune(
        progres,
        "Windows va cere permisiunea de administrator pentru a instala "
        f"{eticheta} pentru toți utilizatorii. Apasă «Da» în fereastra care apare.",
        baza,
    )
    cod = _ruleaza_msiexec(_argumente_msiexec(pachet, jurnal_msi, per_utilizator=False), asteapta=False)
    if cod < 0:
        return False
    _asteapta_msiexec()
    return gaseste_libreoffice() is not None


def instaleaza(progres: Progres | None = None, fortat: bool = False) -> StareLibreOffice:
    """Aduce LibreOffice în română pe calculator, dacă nu este deja gata.

    Pașii: pachetul principal (cu meniurile în română, alese prin ``UI_LANGS=ro``
    și cu dicționarul românesc care vine în el), ajutorul în română, apoi
    verificarea faptului că meniurile și dicționarul chiar există. Dacă
    pachetul există deja și are tot ce trebuie, nu se reinstalează nimic.
    """
    existent = stare()
    if existent.gasit and existent.are_meniu_romana and existent.are_dictionar_romana and not fortat:
        _spune(
            progres,
            "LibreOffice este deja instalat, cu meniurile și dicționarul în română.",
            0.9,
        )
        configureaza_profil_romana()
        return existent

    arhitectura = cai.arhitectura()
    descriere = LIBREOFFICE_MSI.get(arhitectura) or LIBREOFFICE_MSI["AMD64"]
    ajutor = LIBREOFFICE_AJUTOR_MSI.get(arhitectura) or LIBREOFFICE_AJUTOR_MSI["AMD64"]

    _spune(
        progres,
        "Descarc LibreOffice (programul de scris) cu limba română, direct de pe "
        "site-ul oficial. Are aproximativ 360 MB, deci durează câteva minute.",
        0.0,
    )
    pachet = _descarca_pachet(descriere, progres, 0.05, 0.35)
    if not instaleaza_pachet(pachet, progres, 0.40, este_ajutor=False):
        instalat = stare()
        if not instalat.gasit:
            raise EroareLibreOffice(
                "LibreOffice nu a putut fi instalat.",
                ce_fac=(
                    "Poți folosi programul fără LibreOffice: transcrierea funcționează, "
                    "iar documentele se salvează ca DOCX, ODT sau PDF. Dacă vrei să încerci "
                    "din nou instalarea LibreOffice, apasă «Încearcă din nou»."
                ),
                detalii=f"Jurnal msiexec: {cai.director_libreoffice()}",
            )

    # Dicționarul românesc: pe Windows vine în pachetul principal, iar
    # UI_LANGS=ro îl aduce împreună cu meniurile. Verificăm și, dacă lipsește,
    # mai încercăm o dată instalarea, înainte de a spune ce lipsește.
    stare_dupa = stare()
    if not (stare_dupa.are_meniu_romana and stare_dupa.are_dictionar_romana):
        jurnal.instalare(
            "După instalare lipsesc componente în română: "
            + " ".join(stare_dupa.ce_lipseste())
            + ". Mai încerc o dată instalarea pachetului principal."
        )
        _spune(
            progres,
            "Verific dicționarul românesc și meniurile. Mai adaug o dată "
            "componentele în română…",
            0.52,
        )
        try:
            instaleaza_pachet(pachet, progres, 0.55, este_ajutor=False)
        except EroareLibreOffice as exc:  # nu oprim instalarea din atâta lucru
            jurnal.atentionare(f"A doua încercare pentru componentele în română: {exc}")

    # Ajutorul în română (pentru folosire fără internet).
    try:
        pachet_ajutor = _descarca_pachet(ajutor, progres, 0.65, 0.10)
        instaleaza_pachet(pachet_ajutor, progres, 0.78, este_ajutor=True)
    except (EroareLibreOffice, SumaGresita) as exc:
        jurnal.atentionare(f"Ajutorul LibreOffice în română nu a fost instalat: {exc}")

    configureaza_profil_romana()
    rezultat = stare()
    rezultat.instalat_acum = True
    jurnal.instalare(
        "LibreOffice după instalare: versiune "
        f"{rezultat.versiune or 'necunoscută'}, meniu română="
        f"{rezultat.are_meniu_romana}, dicționar română={rezultat.are_dictionar_romana}, "
        f"ajutor română={rezultat.are_ajutor_romana}"
    )
    _spune(progres, rezultat.pentru_utilizator(), 0.90)
    return rezultat


# --------------------------------------------------------------------------- folosire


def deschide_in_writer(cale: Path) -> tuple[bool, str]:
    """Deschide un document direct în LibreOffice Writer, gata de editat."""
    executabil = gaseste_libreoffice()
    if not executabil:
        return False, (
            "Nu găsesc LibreOffice pe acest calculator. Salvează documentul cu "
            "butonul «Salvează ca DOCX» și deschide-l cu programul pe care îl ai."
        )
    try:
        subprocess.Popen(
            [str(executabil), "--norestore", "--writer", str(cale)],
            creationflags=FLAG_NO_WINDOW,
        )
        return True, ""
    except OSError as exc:
        return False, (
            "LibreOffice nu a pornit. Închide LibreOffice dacă era deschis și încearcă "
            f"din nou. (detaliu tehnic: {exc})"
        )


def converteste(sursa: Path, format_iesire: str = "pdf", folder: Path | None = None) -> tuple[Path | None, str]:
    """Convertește un document cu LibreOffice (folosit pentru PDF).

    Se folosește un profil separat, ca lucrul să meargă și dacă utilizatorul
    are LibreOffice deschis în același timp.
    """
    executabil = gaseste_libreoffice()
    if not executabil:
        return None, (
            "Pentru PDF este nevoie de LibreOffice. Salvează documentul ca DOCX sau "
            "ODT și încearcă din nou după ce LibreOffice este instalat."
        )
    folder = folder or sursa.parent
    profil = cai.director_libreoffice() / "profil_convertire"
    profil.mkdir(parents=True, exist_ok=True)
    comanda = [
        str(executabil),
        f"-env:UserInstallation={profil.resolve().as_uri()}",
        "--headless",
        "--norestore",
        "--convert-to",
        f"{format_iesire}:writer_pdf_Export" if format_iesire == "pdf" else format_iesire,
        "--outdir",
        str(folder),
        str(sursa),
    ]
    try:
        subprocess.run(comanda, capture_output=True, text=True, timeout=600, creationflags=FLAG_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"Conversia nu a reușit: {exc}"
    rezultat = Path(folder) / (sursa.stem + f".{format_iesire}")
    if rezultat.exists():
        return rezultat, ""
    return None, (
        "Documentul nu a putut fi transformat. Închide LibreOffice dacă era deschis, "
        "apoi încearcă din nou."
    )


def valideaza_instalarea() -> list[str]:
    """Probleme legate de LibreOffice, pentru verificarea instalării."""
    stare_curenta = stare()
    if not stare_curenta.gasit:
        return ["LibreOffice nu este instalat (poți salva documentele și fără el)."]
    probleme: list[str] = []
    if not stare_curenta.are_meniu_romana:
        probleme.append("LibreOffice nu are meniurile în română.")
    if not stare_curenta.are_dictionar_romana:
        probleme.append("LibreOffice nu are dicționarul românesc (verificarea cu roșu la scriere).")
    if stare_curenta.versiune and stare_curenta.versiune.split(".")[0].isdigit():
        if stare_curenta.versiune.split(".")[:2] < LIBREOFFICE_VERSIUNE.split(".")[:2]:
            probleme.append(
                f"LibreOffice este versiunea {stare_curenta.versiune}, mai veche decât "
                f"{LIBREOFFICE_VERSIUNE}. Se poate actualiza."
            )
    return probleme


def nume_pentru_utilizator() -> str:
    """Numele programului de scris, așa cum îl vede utilizatorul."""
    return "LibreOffice (programul de scris folosit de D&TED)"


def _foloseste_si_sistemul() -> bool:
    return sys.platform.startswith("win")
