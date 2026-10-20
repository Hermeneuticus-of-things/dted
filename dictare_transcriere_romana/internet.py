"""Verificarea legăturii la internet.

Internetul este necesar **doar la instalare**, ca să fie descărcate modelul de
transcriere și LibreOffice de pe site-urile lor oficiale. După instalare
programul nu mai are nevoie de internet și nu încearcă să se conecteze.
"""

from __future__ import annotations

import socket
import urllib.request
from dataclasses import dataclass

from . import jurnal

#: Adrese pe care le folosim la instalare (site-urile oficiale).
GAZDE_NECESARE = {
    "modelul de transcriere (OpenAI)": "openaipublic.azureedge.net",
    "editorul LibreOffice (The Document Foundation)": "download.documentfoundation.org",
    "Python (python.org)": "www.python.org",
    "bibliotecile PyTorch": "download.pytorch.org",
}
#: Adresă care merge testată fără să depindă de un singur site.
GAZDA_TEST = ("1.1.1.1", 443)


@dataclass
class RezultatInternet:
    """Ce s-a putut verifica."""

    are_internet: bool
    gazde_ok: list[str]
    gazde_lipsa: list[str]
    mesaj: str

    @property
    def poate_instala(self) -> bool:
        """Este nevoie de cel puțin site-urile de descărcare."""
        return self.are_internet and not self.gazde_lipsa


def _port_deschis(gazda: str, port: int = 443, timeout: float = 4.0) -> bool:
    try:
        with socket.create_connection((gazda, port), timeout=timeout):
            return True
    except OSError:
        return False


def _raspunde_la_http(url: str, timeout: float = 6.0) -> bool:
    cerere = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "DictareTranscriereRomana/1.0"})
    try:
        with urllib.request.urlopen(cerere, timeout=timeout):
            return True
    except Exception:
        return False


def verifica(gazde: dict[str, str] | None = None, complet: bool = False) -> RezultatInternet:
    """Verifică dacă există internet și dacă site-urile oficiale răspund.

    ``complet=False`` verifică doar existența unei legături (rapid, folosit la
    fiecare pornire a instalării). ``complet=True`` verifică și site-urile
    necesare, înainte de descărcări.
    """
    gazde = gazde if gazde is not None else GAZDE_NECESARE
    are = _port_deschis(*GAZDA_TEST) or _raspunde_la_http("https://www.python.org/", 6.0)
    if not are:
        jurnal.instalare("Verificarea internetului: nu am găsit nicio legătură.")
        return RezultatInternet(
            False,
            [],
            list(gazde),
            "Nu am internet. Conectează calculatorul la Wi-Fi sau la cablu, "
            "apoi apasă «Încearcă din nou».",
        )

    if not complet:
        return RezultatInternet(True, list(gazde), [], "Internetul funcționează.")

    ok: list[str] = []
    lipsa: list[str] = []
    for eticheta, gazda in gazde.items():
        if _port_deschis(gazda, 443, 5.0):
            ok.append(eticheta)
        else:
            lipsa.append(eticheta)

    if lipsa:
        mesaj = (
            "Internetul funcționează, dar nu ajung la: "
            + ", ".join(lipsa)
            + ". Verifică legătura (sau rețeaua care blochează aceste site-uri) "
            "și apasă «Încearcă din nou»."
        )
    else:
        mesaj = "Internetul funcționează și site-urile oficiale răspund."
    jurnal.instalare(f"Verificare internet: ok={ok} lipsă={lipsa}")
    return RezultatInternet(True, ok, lipsa, mesaj)


def are_internet() -> bool:
    """Verificare rapidă, folosită înainte de a începe descărcările."""
    return verifica(complet=False).are_internet


# --------------------------------------------------------------------------- starea rețelei (punctul 22)


@dataclass
class StareRetea:
    """Starea legăturii de rețea, citită de la Windows, fără niciun trafic."""

    conectat: bool
    metoda: str = ""
    detalii: str = ""

    @property
    def mesaj_scurt(self) -> str:
        if self.conectat:
            return "Internet pornit"
        return "Internet oprit – lucrezi în siguranță"


#: Câte niveluri de legătură are Windows (enum-ul din netlistmgr.h).
_NIVEL_FARA = 0
_NIVEL_LOCAL = 1
_NIVEL_INTERNET = 2
_NIVEL_LIMITAT = 3

#: Identificatorul serviciului Windows care știe starea rețelei.
_CLSID_NLM = "{DCB00C01-570F-4A9B-8D69-199FDBA5723B}"
_IID_NLM = "{DCB00000-570F-4A9B-8D69-199FDBA5723B}"


def _retea_prin_indiciu() -> StareRetea | None:
    """Starea rețelei prin funcția Windows „GetNetworkConnectivityHint”.

    Este cea mai simplă cale și nu trimite absolut nimic: Windows spune doar
    dacă există legătură la internet, acces doar la rețeaua locală sau deloc.
    """
    try:
        import ctypes
        from ctypes import wintypes

        class _Indiciu(ctypes.Structure):
            _fields_ = [
                ("nivel", ctypes.c_int),
                ("cost", ctypes.c_int),
                ("limitat", ctypes.c_byte),
                ("aproape_de_limita", ctypes.c_byte),
                ("peste_limita", ctypes.c_byte),
                ("in_deplasare", ctypes.c_byte),
            ]

        iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
        functia = getattr(iphlpapi, "GetNetworkConnectivityHint", None)
        if functia is None:
            return None
        indiciu = _Indiciu()
        cod = functia(ctypes.byref(indiciu))
        if cod != 0:
            return None
        conectat = indiciu.nivel in (_NIVEL_INTERNET, _NIVEL_LIMITAT)
        detalii = {
            _NIVEL_FARA: "Windows spune că nu este nicio legătură.",
            _NIVEL_LOCAL: "Windows spune că ești doar în rețeaua locală, fără internet.",
            _NIVEL_INTERNET: "Windows spune că internetul este pornit.",
            _NIVEL_LIMITAT: "Windows spune că internetul este pornit, dar cu trafic limitat.",
        }.get(indiciu.nivel, "Windows spune că legătura este necunoscută.")
        if indiciu.limitat:
            detalii += " (rețeaua este socotită „cu limită de trafic”)"
        return StareRetea(conectat, "GetNetworkConnectivityHint", detalii)
    except Exception as exc:  # pragma: no cover - depinde de versiunea Windows
        jurnal.info(f"Starea rețelei (indiciu Windows) nu a putut fi citită: {exc}")
        return None


def _retea_prin_nlm() -> StareRetea | None:
    """Starea rețelei prin serviciul Windows de rețea (INetworkListManager).

    Se citește doar starea rețelei („este legat de internet?”), nimic altceva.
    """
    try:
        import ctypes

        ole32 = ctypes.windll.ole32
        clsid = ctypes.create_string_buffer(16)
        iid = ctypes.create_string_buffer(16)
        if ole32.CLSIDFromString(ctypes.c_wchar_p(_CLSID_NLM), clsid) != 0:
            return None
        if ole32.CLSIDFromString(ctypes.c_wchar_p(_IID_NLM), iid) != 0:
            return None
        obiect = ctypes.c_void_p()
        rezultat = ole32.CoCreateInstance(
            clsid, None, 1, iid, ctypes.byref(obiect)  # 1 = CLSCTX_INPROC_SERVER
        )
        if rezultat != 0 or not obiect.value:
            return None
        tabel = ctypes.cast(obiect, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        if not tabel:
            return None

        def _metoda(index: int):
            adresa = tabel[index]
            return ctypes.CFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_short)
            )(adresa)

        conectat_internet = ctypes.c_short(0)
        conectat_retea = ctypes.c_short(0)
        cod_internet = _metoda(11)(obiect, ctypes.byref(conectat_internet))
        cod_retea = _metoda(12)(obiect, ctypes.byref(conectat_retea))
        eliberare = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(tabel[2])
        eliberare(obiect)
        if cod_internet != 0 and cod_retea != 0:
            return None
        if cod_internet == 0:
            conectat = bool(conectat_internet.value)
        else:
            # Dacă Windows nu răspunde la prima întrebare, ne mulțumim cu
            # „este legat la o rețea” (Wi-Fi, cablu sau telefon).
            conectat = bool(conectat_retea.value)
        detalii = (
            "Windows (serviciul de rețea) spune că internetul este pornit."
            if conectat
            else "Windows (serviciul de rețea) spune că internetul este oprit."
        )
        return StareRetea(conectat, "INetworkListManager", detalii)
    except Exception as exc:  # pragma: no cover - depinde de versiunea Windows
        jurnal.info(f"Starea rețelei (serviciul Windows) nu a putut fi citită: {exc}")
        return None


def _retea_prin_adaptoare() -> StareRetea | None:
    """Ultima verificare: există vreo placă de rețea pornită, cu poartă de ieșire?

    Nu trimite nimic nicăieri: se citesc doar plăcile de rețea ale
    calculatorului, așa cum le vede Windows, câmp cu câmp (fără poziții
    presupuse în memorie).
    """
    try:
        import ctypes
        from ctypes import wintypes

        class _AdaptorRetea(ctypes.Structure):
            pass

        _AdaptorPointer = ctypes.POINTER(_AdaptorRetea)
        _AdaptorRetea._fields_ = [
            ("length", wintypes.ULONG),
            ("if_index", wintypes.ULONG),
            ("urmator", _AdaptorPointer),
            ("nume", ctypes.c_char_p),
            ("prima_adresa_individuala", ctypes.c_void_p),
            ("prima_adresa_anycast", ctypes.c_void_p),
            ("prima_adresa_multicast", ctypes.c_void_p),
            ("primul_serviciu_dns", ctypes.c_void_p),
            ("sufix_dns", ctypes.c_wchar_p),
            ("descriere", ctypes.c_wchar_p),
            ("nume_prietenos", ctypes.c_wchar_p),
            ("adresa_fizica", ctypes.c_ubyte * 8),
            ("lungime_adresa_fizica", wintypes.ULONG),
            ("marcaje", wintypes.ULONG),
            ("mtu", wintypes.ULONG),
            ("tip_interfata", wintypes.ULONG),
            ("stare_interfata", wintypes.ULONG),
            ("index_ipv6", wintypes.ULONG),
            ("zone", wintypes.ULONG * 16),
            ("primul_prefix", ctypes.c_void_p),
            ("viteza_emisie", ctypes.c_ulonglong),
            ("viteza_receptie", ctypes.c_ulonglong),
            ("primul_server_wins", ctypes.c_void_p),
            ("prima_poarta", ctypes.c_void_p),
        ]

        iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
        functia = iphlpapi.GetAdaptersAddresses
        marime = wintypes.ULONG(15_000)
        buffer = ctypes.create_string_buffer(marime.value)
        AF_UNSPEC = 0
        GAA_FLAG_INCLUDE_GATEWAYS = 0x0080
        while True:
            cod = functia(
                AF_UNSPEC,
                GAA_FLAG_INCLUDE_GATEWAYS,
                None,
                ctypes.cast(buffer, _AdaptorPointer),
                ctypes.byref(marime),
            )
            if cod == 0:
                break
            if cod == 111:  # bufferul a fost prea mic: îl mărim și încercăm iar
                buffer = ctypes.create_string_buffer(marime.value)
                continue
            return None
        adaptor = ctypes.cast(buffer, _AdaptorPointer)
        gasit = False
        while adaptor:
            date = adaptor.contents
            if date.stare_interfata == 1 and date.prima_poarta:
                gasit = True
                break
            adaptor = date.urmator
        return StareRetea(
            gasit,
            "plăci de rețea",
            "Este o placă de rețea pornită, cu poartă de ieșire."
            if gasit
            else "Nicio placă de rețea nu este pornită.",
        )
    except Exception as exc:  # pragma: no cover - depinde de versiunea Windows
        jurnal.info(f"Citirea plăcilor de rețea nu a reușit: {exc}")
        return None


def stare_retea() -> StareRetea:
    """Spune dacă internetul este conectat, citind doar starea de la Windows.

    Se încearcă, în ordine: funcția „GetNetworkConnectivityHint”, serviciul de
    rețea al Windows, apoi plăcile de rețea. **Nu se trimite niciodată nimic**
    pe internet; se citește doar ce știe deja Windows.
    """
    for verificare in (_retea_prin_indiciu, _retea_prin_nlm, _retea_prin_adaptoare):
        rezultat = verificare()
        if rezultat is not None:
            return rezultat
    return StareRetea(False, "necunoscut", "Starea rețelei nu a putut fi citită.")


def internet_conectat() -> bool:
    """Adevărat dacă Windows spune că există legătură la internet."""
    return stare_retea().conectat

