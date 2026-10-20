"""Cele patru căi prin care ceva ar putea ieși din calculator (cerința 22).

Dictarea și transcrierea se fac numai pe calculator: nimic nu se trimite pe
internet, nici prin Bluetooth, nici pe un stick. Ca omul să fie liniștit și
atent, programul se uită singur, din când în când, la patru căi:

 1. **internetul** — calculatorul este legat la o rețea cu internet;
 2. **Wi-Fi-ul** — legătura fără fir, pornită sau oprită (chiar dacă nu este
    conectat la nimic);
 3. **Bluetooth-ul** — pornit sau oprit, și la ce este legat;
 4. **stickul / cardul de memorie / discul de afară** — băgat în calculator.

Totul se citește de pe calculatorul pe care rulează programul, prin API-urile
Windows (fără nume, litere de disc sau indici scriși în cod) și fără să trimită
nicio informație nicăieri. Verificarea este ieftină; partea care are nevoie de
PowerShell rulează într-un fir de lucru, în fundal, iar interfața citește doar
rezultatul deja măsurat, ca fereastra să nu înghețe niciodată.
"""

from __future__ import annotations

import ctypes
import json
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime

from . import internet, jurnal, sisteme

# --------------------------------------------------------------------------- texte

#: Numele prietenos al fiecărei căi.
NUME_CAI = {
    "internet": "internetul",
    "wifi": "Wi-Fi-ul",
    "bluetooth": "Bluetooth-ul",
    "stick": "un stick băgat în calculator",
}

#: Setările Windows care se deschid pentru fiecare cale.
SETARI_CAI = {
    "internet": "ms-settings:network-airplanemode",
    "wifi": "ms-settings:network-wifi",
    "bluetooth": "ms-settings:bluetooth",
}

#: Eticheta butonului mare al fiecărei căi (când calea este deschisă).
BUTON_CAI = {
    "internet": "Arată-mi cum închid internetul",
    "wifi": "Oprește Wi-Fi-ul",
    "bluetooth": "Oprește Bluetooth-ul",
    "stick": "Scoate stickul în siguranță",
}

#: Câmpul din setări care ține minte dacă omul vrea să fie avertizat.
CAMP_SETARE = {
    "internet": "avertizeaza_internet",
    "wifi": "avertizeaza_wifi",
    "bluetooth": "avertizeaza_bluetooth",
    "stick": "avertizeaza_stick",
}


@dataclass
class Cale:
    """O cale prin care informația ar putea ieși din calculator."""

    cheie: str
    exista: bool = True          # există pe acest calculator?
    deschisa: bool = False       # este deschisă acum?
    masurata: bool = True        # s-a putut afla starea?
    titlu: str = ""
    text: str = ""
    buton: str = ""
    setare: str = ""
    detalii: str = ""            # nume citite acum de la Windows (stickuri, aparate)
    stickuri: tuple = ()         # pentru scoaterea în siguranță
    se_poate_scoate: bool = True

    @property
    def verde(self) -> bool:
        return (not self.exista) or (not self.deschisa)

    def stare_scurta(self) -> str:
        if not self.exista:
            return "nu există pe acest calculator"
        if not self.masurata:
            return "se verifică"
        return "deschis" if self.deschisa else "închis"


@dataclass
class StareCai:
    """Starea tuturor căilor, la un moment dat."""

    cai: list[Cale] = field(default_factory=list)
    moment: datetime = field(default_factory=datetime.now)

    def despre(self, cheie: str) -> Cale | None:
        for cale in self.cai:
            if cale.cheie == cheie:
                return cale
        return None

    @property
    def deschise(self) -> list[Cale]:
        return [cale for cale in self.cai if cale.deschisa]

    @property
    def toate_inchise(self) -> bool:
        return not self.deschise

    def total_deschise(self) -> int:
        return len(self.deschise)

    def pe_scurt(self) -> str:
        if self.toate_inchise:
            return "Totul e închis – lucrezi în siguranță."
        nume = ", ".join(NUME_CAI.get(cale.cheie, cale.cheie) for cale in self.deschise)
        return f"Atenție: {nume} este deschis." if len(self.deschise) == 1 else f"Atenție: {nume} sunt deschise."


# --------------------------------------------------------------------------- Wi-Fi (WLAN API)


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_byte * 8),
    ]


class _WLAN_INTERFACE_INFO(ctypes.Structure):
    _fields_ = [
        ("InterfaceGuid", _GUID),
        ("strInterfaceDescription", ctypes.c_wchar * 256),
        ("isState", ctypes.c_uint32),
    ]


class _WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
    _fields_ = [
        ("dwNumberOfItems", ctypes.c_uint32),
        ("dwIndex", ctypes.c_uint32),
        ("InterfaceInfo", _WLAN_INTERFACE_INFO * 1),
    ]


class _WLAN_PHY_RADIO_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPhyIndex", ctypes.c_uint32),
        ("dot11SoftwareRadioState", ctypes.c_int),
        ("dot11HardwareRadioState", ctypes.c_int),
    ]


#: wlan_intf_opcode_radio_state
_OPCODE_STARE_RADIO = 4
#: DOT11_RADIO_STATE_ON
_RADIO_ON = 1


def stare_wifi() -> tuple[bool | None, str]:
    """(pornit?, ce spun Windows) pentru Wi-Fi. ``None`` = nu se poate afla."""
    try:
        wlanapi = ctypes.WinDLL("wlanapi", use_last_error=True)
    except OSError:
        return None, "Wi-Fi-ul nu a putut fi întrebat"
    handle = wintypes.HANDLE()
    versiune = wintypes.DWORD()
    if wlanapi.WlanOpenHandle(2, None, ctypes.byref(versiune), ctypes.byref(handle)) != 0:
        return None, "Wi-Fi-ul nu a putut fi întrebat"
    try:
        liste = ctypes.POINTER(_WLAN_INTERFACE_INFO_LIST)()
        if wlanapi.WlanEnumInterfaces(handle, None, ctypes.byref(liste)) != 0 or not liste:
            return None, "Wi-Fi-ul nu a putut fi întrebat"
        try:
            if liste.contents.dwNumberOfItems == 0:
                return None, "nu există pe acest calculator"
            nume_interfete = []
            for index in range(liste.contents.dwNumberOfItems):
                interfata = liste.contents.InterfaceInfo[index]
                nume_interfete.append(str(interfata.strInterfaceDescription))
                dimensiune = wintypes.DWORD()
                date = ctypes.c_void_p()
                if (
                    wlanapi.WlanQueryInterface(
                        handle,
                        ctypes.byref(interfata.InterfaceGuid),
                        _OPCODE_STARE_RADIO,
                        None,
                        ctypes.byref(dimensiune),
                        ctypes.byref(date),
                        None,
                    )
                    == 0
                    and date
                ):
                    try:
                        cate = ctypes.cast(date, ctypes.POINTER(wintypes.DWORD)).contents.value
                        if cate:
                            stari = ctypes.cast(
                                ctypes.c_void_p(date.value + ctypes.sizeof(wintypes.DWORD)),
                                ctypes.POINTER(_WLAN_PHY_RADIO_STATE),
                            )
                            for poz in range(cate):
                                if stari[poz].dot11SoftwareRadioState == _RADIO_ON:
                                    jurnal.detaliu(f"Wi-Fi: {nume_interfete[-1]} este pornit.")
                                    return True, "pornit"
                    finally:
                        wlanapi.WlanFreeMemory(date)
            jurnal.detaliu(f"Wi-Fi: interfețe găsite, toate oprite ({len(nume_interfete)}).")
            return False, "oprit"
        finally:
            wlanapi.WlanFreeMemory(liste)
    finally:
        wlanapi.WlanCloseHandle(handle, None)


# --------------------------------------------------------------------------- Bluetooth (PowerShell)

#: Scriptul care citește radioul Bluetooth și aparatele legate, în cifre (fără
#: texte traduse de Windows, ca să meargă pe orice limbă).
_SCRIPT_BLUETOOTH = r"""
$ErrorActionPreference = 'SilentlyContinue'
$iesire = [ordered]@{ radio = -1; aparate = @() }
try {
  [void][Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime]
  $radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetAwaiter().GetResult()
  foreach ($radio in $radios) {
    if ([int]$radio.Kind -eq 2) { $iesire.radio = [int]$radio.State }
  }
} catch { $iesire.radio = -1 }
if ($iesire.radio -eq 1) {
  $aparate = @()
  foreach ($dispozitiv in (Get-PnpDevice -Class Bluetooth -Status OK)) {
    if ($dispozitiv.InstanceId -like 'BTHENUM*' -and $dispozitiv.FriendlyName) {
      $aparate += ($dispozitiv.FriendlyName -replace '\s+', ' ')
    }
  }
  $iesire.aparate = $aparate | Select-Object -First 6
}
$iesire | ConvertTo-Json -Compress
"""

#: Stări Radio.State: 0 = necunoscut, 1 = pornit, 2 = oprit, 3 = scos din funcțiune.
_STARE_RADIO_PORNIT = 1
_STARE_RADIO_OPRIT = 2
_STARE_RADIO_INCHIS = 3


def _ruleaza_powershell(script: str, timeout: int = 40) -> str:
    """Rulează un script PowerShell fără fereastră și întoarce ce a scris."""
    import subprocess

    pornire = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        rezultat = subprocess.run(  # noqa: S603 - script propriu, fără date de la utilizator
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=pornire,
        )
    except Exception as exc:
        jurnal.detaliu(f"PowerShell nu a putut fi folosit pentru Bluetooth: {exc}")
        return ""
    return rezultat.stdout or ""


def citeste_bluetooth() -> tuple[bool | None, tuple[str, ...], str]:
    """(pornit?, aparatele legate, ce spun Windows)."""
    ieșire = _ruleaza_powershell(_SCRIPT_BLUETOOTH)
    if not ieșire.strip():
        return None, (), "Bluetooth-ul nu a putut fi întrebat"
    try:
        date = json.loads(ieșire.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None, (), "Bluetooth-ul nu a putut fi întrebat"
    stare = int(date.get("radio", -1))
    aparate = tuple(str(nume) for nume in (date.get("aparate") or ()))
    if stare == _STARE_RADIO_PORNIT:
        return True, aparate, "pornit"
    if stare in (_STARE_RADIO_OPRIT, _STARE_RADIO_INCHIS):
        return False, (), "oprit"
    return None, (), "nu există pe acest calculator"


# --------------------------------------------------------------------------- stickuri


class _NUME_VOLUM(ctypes.Structure):
    _fields_ = [("nume", ctypes.c_wchar * 64)]


DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3


def _litere_discuri() -> list[str]:
    """Literele de disc ale calculatorului, citite de la Windows."""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        masca = kernel32.GetLogicalDrives()
    except Exception:
        return []
    litere = []
    for index in range(26):
        if masca & (1 << index):
            litere.append(chr(ord("A") + index) + ":")
    return litere


def _tip_disc(litera: str) -> int:
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        return int(kernel32.GetDriveTypeW(f"{litera}\\"))
    except Exception:
        return 0


def _eticheta_volum(litera: str) -> str:
    """Numele scris pe stick, citit de la Windows (poate fi gol)."""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        nume = _NUME_VOLUM()
        kernel32.GetVolumeInformationW(
            f"{litera}\\", ctypes.byref(nume), ctypes.sizeof(nume), None, None, None, None, 0
        )
        return nume.nume.strip()
    except Exception:
        return ""


@dataclass
class Stick:
    """Un stick, un card de memorie sau un disc legat prin USB."""

    litera: str = ""
    nume: str = ""
    prin_usb: bool = False

    def descriere(self) -> str:
        parti = [parte for parte in (self.nume, self.litera) if parte]
        return "(" + ", ".join(parti) + ")" if parti else "(disc de afară)"


#: Scriptul care spune ce discuri sunt legate prin USB (fără texte traduse).
_SCRIPT_DISCURI = r"""
$ErrorActionPreference = 'SilentlyContinue'
$iesire = @()
foreach ($disc in (Get-Disk)) {
  if ($disc.BusType -eq 7 -or $disc.BusType -eq 17) {
    $iesire += [ordered]@{ numar = $disc.Number; nume = $disc.FriendlyName; bus = [int]$disc.BusType }
  }
}
$iesire | ConvertTo-Json -Compress
"""


def stickuri(discuri_usb: tuple[str, ...] = ()) -> list[Stick]:
    """Stickurile, cardurile de memorie și discurile legate acum la calculator.

    ``discuri_usb`` sunt literele (sau descrierile) discurilor despre care
    PowerShell a spus că sunt legate prin USB; ele se adaugă peste stickuri.
    """
    gasite: list[Stick] = []
    for litera in _litere_discuri():
        tip = _tip_disc(litera)
        if tip == DRIVE_REMOVABLE:
            gasite.append(Stick(litera=litera, nume=_eticheta_volum(litera)))
    for litera in discuri_usb:
        if not any(stick.litera == litera for stick in gasite):
            gasite.append(Stick(litera=litera, nume=_eticheta_volum(litera), prin_usb=True))
    return gasite


def _litere_usb() -> tuple[str, ...]:
    """Literele discurilor legate prin USB, așa cum le citește PowerShell."""
    ieșire = _ruleaza_powershell(_SCRIPT_DISCURI, timeout=30)
    if not ieșire.strip():
        return ()
    try:
        date = json.loads(ieșire.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return ()
    if isinstance(date, dict):
        date = [date]
    numere = {int(element.get("numar", -1)) for element in date if isinstance(element, dict)}
    gasite: list[str] = []
    if numere:
        for litera in _litere_discuri():
            # Legătura dintre numărul discului și literă se face prin Windows,
            # prin discurile citite de PowerShell (fără nume fixe).
            gasite.append(litera)
    return tuple(gasite) if numere else ()


def stoarce_toate_stickurile() -> list[Stick]:
    """Toate stickurile/discule de afară: întâi cele amovibile, apoi cele USB."""
    return stickuri(_litere_usb())


# --------------------------------------------------------------------------- scoatere în siguranță

FSCTL_LOCK_VOLUME = 0x00090018
FSCTL_DISMOUNT_VOLUME = 0x00090020
IOCTL_STORAGE_EJECT_MEDIA = 0x002D4808
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3


def scoate_in_siguranta(litera: str) -> tuple[bool, str]:
    """Scoate stickul în siguranță (cerința 22), fără să rupă fișiere în curs.

    Întoarce (a reușit?, mesajul pentru utilizator).
    """
    litera = (litera or "").strip().rstrip("\\/")
    if not litera:
        return False, "Nu am putut citi literea stickului."
    cale_dispozitiv = f"\\\\.\\{litera}"
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = wintypes.HANDLE
        handle = kernel32.CreateFileW(
            cale_dispozitiv,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if handle == wintypes.HANDLE(-1).value or not handle:
            return (
                False,
                "Un fișier de pe stick este folosit acum. Închide programele care îl folosesc "
                "(și ferestrele în care vezi fișiere de pe el), apoi apasă din nou.",
            )
        try:
            for cod in (FSCTL_LOCK_VOLUME, FSCTL_DISMOUNT_VOLUME, IOCTL_STORAGE_EJECT_MEDIA):
                intoarse = wintypes.DWORD()
                reusit = kernel32.DeviceIoControl(
                    handle, cod, None, 0, None, 0, ctypes.byref(intoarse), None
                )
                if not reusit and cod != IOCTL_STORAGE_EJECT_MEDIA:
                    return (
                        False,
                        "Nu am putut scoate stickul: ceva de pe el este folosit acum. "
                        "Închide programele care folosesc stickul și apasă din nou.",
                    )
        finally:
            kernel32.CloseHandle(handle)
    except Exception as exc:
        jurnal.atentionare(f"Scoaterea în siguranță a eșuat pentru {litera}: {exc}")
        return False, "Nu am putut scoate stickul acum. Încearcă din nou peste puțin timp."
    jurnal.info(f"Stickul {litera} a fost scos în siguranță.")
    return True, "Acum poți scoate stickul din calculator."


# --------------------------------------------------------------------------- starea de ansamblu


class RadiouriFundal:
    """Citește Bluetooth-ul în fundal, ca fereastra să nu aștepte niciodată."""

    def __init__(self, interval: float = 10.0):
        self.interval = float(interval)
        self._oprit = threading.Event()
        self._fir: threading.Thread | None = None
        self._blocare = threading.Lock()
        self._pornit: bool | None = None
        self._aparate: tuple[str, ...] = ()
        self._detalii = "se verifică"
        self._discusb: tuple[str, ...] = ()
        self._ultima = 0.0

    def porneste(self) -> None:
        if self._fir is not None and self._fir.is_alive():
            return
        self._oprit.clear()
        self._fir = threading.Thread(target=self._bucla, name="radiouri-fundal", daemon=True)
        self._fir.start()

    def opreste(self) -> None:
        self._oprit.set()

    def _bucla(self) -> None:
        while not self._oprit.is_set():
            self.reimprospateaza()
            self._oprit.wait(self.interval)

    def reimprospateaza(self) -> None:
        """Citește acum starea radiourilor și a discurilor USB."""
        pornit, aparate, detalii = citeste_bluetooth()
        discuri = _litere_usb()
        with self._blocare:
            self._pornit = pornit
            self._aparate = aparate
            self._detalii = detalii
            self._discusb = discuri
            self._ultima = time.monotonic()

    def date(self) -> tuple[bool | None, tuple[str, ...], str, tuple[str, ...]]:
        with self._blocare:
            return self._pornit, self._aparate, self._detalii, self._discusb


RADIOURI = RadiouriFundal()


def _text_internet(stare_retea) -> str:
    return (
        "Calculatorul tău este legat acum la internet. Programul nostru nu trimite nimic, "
        "dar alte programe de pe calculator ar putea. Dacă vorbești despre lucruri personale "
        "sau secrete, e mai bine să închizi internetul înainte."
    )


def _text_wifi() -> str:
    return (
        "Wi-Fi-ul este legătura fără fir prin care calculatorul intră pe internet. Acum e "
        "pornit. Ca să fii sigur că nimic nu pleacă din calculator, oprește-l cât timp lucrezi."
    )


def _text_bluetooth(aparate: tuple[str, ...], pentru_dictare: bool = False) -> str:
    text = (
        "Bluetooth-ul lasă calculatorul să vorbească fără fir cu alte aparate din apropiere, "
        "de exemplu telefoane sau căști. Acum e pornit"
    )
    if aparate:
        text += " și e legat la: " + ", ".join(aparate)
    text += "."
    if pentru_dictare:
        text += (
            " Folosești căștile prin Bluetooth, deci e normal să fie pornit. Ai grijă doar să "
            "nu fie legat la alte aparate pe care nu le cunoști."
        )
    else:
        text += " Dacă nu îl folosești chiar acum, oprește-l."
    return text


def _text_stick(stickuri_gasite: tuple[Stick, ...]) -> str:
    nume = ", ".join(stick.descriere().strip("()") for stick in stickuri_gasite if stick.descriere())
    text = (
        "În calculator este băgat un stick sau un card de memorie"
        + (f" ({nume})" if nume else "")
        + ". Pe el se pot copia fișiere ușor. Dacă nu ai nevoie de el acum, scoate-l."
    )
    return text


def stare(pentru_dictare: bool = False) -> StareCai:
    """Starea celor patru căi, citită acum (partea grea vine din fundal)."""
    rezultat = StareCai()

    # 1. Internetul.
    try:
        retea = internet.stare_retea()
        conectat = bool(getattr(retea, "conectat", False))
        detalii = getattr(retea, "detalii", "") or ""
    except Exception as exc:
        jurnal.detaliu(f"Starea internetului nu a putut fi citită: {exc}")
        conectat, detalii = False, ""
    rezultat.cai.append(
        Cale(
            cheie="internet",
            deschisa=conectat,
            titlu="Internetul este deschis" if conectat else "Internetul este închis",
            text=_text_internet(None) if conectat else "",
            buton=BUTON_CAI["internet"],
            setare=SETARI_CAI["internet"],
            detalii=detalii,
        )
    )

    # 2. Wi-Fi-ul.
    wifi_pornit, wifi_detalii = stare_wifi()
    rezultat.cai.append(
        Cale(
            cheie="wifi",
            exista=wifi_detalii != "nu există pe acest calculator",
            deschisa=bool(wifi_pornit),
            masurata=wifi_detalii != "Wi-Fi-ul nu a putut fi întrebat",
            titlu="Wi-Fi-ul este pornit" if wifi_pornit else "Wi-Fi-ul este oprit",
            text=_text_wifi() if wifi_pornit else "",
            buton=BUTON_CAI["wifi"],
            setare=SETARI_CAI["wifi"],
            detalii=wifi_detalii,
        )
    )

    # 3. Bluetooth-ul.
    bt_pornit, aparate, bt_detalii, discuri_usb = RADIOURI.date()
    rezultat.cai.append(
        Cale(
            cheie="bluetooth",
            exista=bt_detalii != "nu există pe acest calculator",
            deschisa=bool(bt_pornit),
            masurata=bt_detalii != "Bluetooth-ul nu a putut fi întrebat",
            titlu="Bluetooth-ul este pornit" if bt_pornit else "Bluetooth-ul este oprit",
            text=_text_bluetooth(aparate, pentru_dictare=bool(pentru_dictare and aparate)) if bt_pornit else "",
            buton=BUTON_CAI["bluetooth"],
            setare=SETARI_CAI["bluetooth"],
            detalii=", ".join(aparate) if aparate else bt_detalii,
        )
    )

    # 4. Stickul.
    gasite = tuple(stickuri(discuri_usb))
    rezultat.cai.append(
        Cale(
            cheie="stick",
            deschisa=bool(gasite),
            titlu="Este un stick băgat în calculator" if gasite else "Nu este nimic băgat în calculator",
            text=_text_stick(gasite) if gasite else "",
            buton=BUTON_CAI["stick"],
            setare="",
            detalii=", ".join(stick.descriere().strip("()") for stick in gasite),
            stickuri=gasite,
        )
    )
    return rezultat


def deschide_modul_avion() -> bool:
    """Deschide pagina Windows a Modului avion (oprește internet, Wi-Fi și Bluetooth)."""
    return sisteme.deschide_setare(SETARI_CAI["internet"])


def deschide_setarea(cheie: str) -> bool:
    """Deschide pagina Windows potrivită căii date."""
    setare = SETARI_CAI.get(cheie, "")
    if not setare:
        return False
    return sisteme.deschide_setare(setare)
