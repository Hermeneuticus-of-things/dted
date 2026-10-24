"""Modul serviciu: D&TED folosit de alte programe (de exemplu Scribner), fără fereastră.

Pornire: ``python -m dictare_transcriere_romana --serviciu`` (sau ``dted.exe --serviciu``).

Programul citește comenzi de la intrarea standard și scrie răspunsuri la ieșirea standard,
câte un obiect JSON pe linie, în UTF-8. Nimic nu pleacă pe internet; sunetul și textul rămân
pe calculator.

Comenzi (``id`` e ales de programul care cere și se întoarce în răspunsuri):

* ``{"cmd": "stare"}`` → ``{"ev": "stare", "versiune", "dispozitiv", "model_incarcat"}``
* ``{"cmd": "transcrie", "id", "cale", "limba"?, "termeni"?}`` → ``faza`` / ``progres``,
  apoi ``{"ev": "rezultat", "id", "text", "segmente": [{start, end, text}], "secunde_audio"}``
* ``{"cmd": "dictare_start", "id", "limba"?, "termeni"?}`` → ``{"ev": "dictare_pornita"}``, apoi
  ``{"ev": "fragment", "id", "text"}`` la fiecare bucată de vorbire (≈ 4 s) și ``{"ev": "nivel"}``
* ``{"cmd": "dictare_stop", "id"}`` → ultimul fragment, apoi ``{"ev": "dictare_oprita", "id", "text"}``
* ``{"cmd": "anuleaza", "id"}`` oprește o transcriere sau o dictare fără rezultat
* ``{"cmd": "iesire"}`` închide serviciul (la fel și închiderea intrării standard)

Erori: ``{"ev": "eroare", "id", "mesaj", "ce_fac"}``, cu mesaje în română simplă.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from typing import Callable

PROTOCOL = 1
SECUNDE_BUCATA = 4.0
RATA = 16_000


class Serviciu:
    """Execută comenzile; ``scrie`` primește fiecare răspuns (un dict)."""

    def __init__(
        self,
        scrie: Callable[[dict], None],
        motor_fabrica: Callable[[], object] | None = None,
        microfon_fabrica: Callable[[], object] | None = None,
        secunde_bucata: float = SECUNDE_BUCATA,
    ):
        self._scrie_brut = scrie
        self._scriere = threading.Lock()
        self._motor_fabrica = motor_fabrica or _motor_implicit
        self._microfon_fabrica = microfon_fabrica or _microfon_implicit
        self._motor = None
        self._motor_blocare = threading.Lock()  # un singur calcul pe model odată
        self._secunde_bucata = secunde_bucata
        self._dictare: dict | None = None
        self._transcrieri: dict[str, threading.Event] = {}
        self._fire: list[threading.Thread] = []

    # ------------------------------------------------------------------ ieșire

    def scrie(self, mesaj: dict) -> None:
        with self._scriere:
            self._scrie_brut(mesaj)

    def _eroare(self, id_, exc: BaseException | str, ce_fac: str = "") -> None:
        mesaj = str(exc) or "Ceva nu a mers."
        self.scrie({"ev": "eroare", "id": id_, "mesaj": mesaj, "ce_fac": getattr(exc, "ce_fac", "") or ce_fac})

    def motor(self):
        if self._motor is None:
            self._motor = self._motor_fabrica()
        return self._motor

    def _porneste_fir(self, tinta, *args) -> threading.Thread:
        fir = threading.Thread(target=tinta, args=args, daemon=True)
        self._fire.append(fir)
        fir.start()
        return fir

    def asteapta(self, secunde: float = 30.0) -> None:
        """Așteaptă firele pornite (folosit la închidere și în teste)."""
        limita = time.time() + secunde
        for fir in list(self._fire):
            fir.join(max(0.0, limita - time.time()))

    # ------------------------------------------------------------------ comenzi

    def executa(self, comanda: dict) -> bool:
        """Execută o comandă. Întoarce False când serviciul trebuie să se oprească."""
        if not isinstance(comanda, dict):
            self._eroare(None, "Comandă necunoscută.")
            return True
        cmd = comanda.get("cmd")
        id_ = comanda.get("id")
        if cmd == "iesire":
            self._opreste_dictarea(anulat=True)
            for semnal in self._transcrieri.values():
                semnal.set()
            return False
        if cmd == "stare":
            self.scrie(self._stare())
        elif cmd == "transcrie":
            cale = str(comanda.get("cale") or "")
            if not cale:
                self._eroare(id_, "Lipsește fișierul audio.")
            else:
                semnal = threading.Event()
                self._transcrieri[str(id_)] = semnal
                self._porneste_fir(self._transcrie, id_, cale, comanda.get("limba") or "ro", comanda.get("termeni") or "", semnal)
        elif cmd == "dictare_start":
            if self._dictare is not None:
                self._eroare(id_, "Dictarea este deja pornită.", "Oprește dictarea de acum, apoi pornește alta.")
            else:
                self._porneste_dictarea(id_, comanda.get("limba") or "ro", comanda.get("termeni") or "")
        elif cmd == "dictare_stop":
            self._opreste_dictarea(anulat=False)
        elif cmd == "anuleaza":
            semnal = self._transcrieri.get(str(id_))
            if semnal is not None:
                semnal.set()
                motor = self._motor
                if motor is not None and hasattr(motor, "anuleaza"):
                    motor.anuleaza()
            elif self._dictare is not None and self._dictare["id"] == id_:
                self._opreste_dictarea(anulat=True)
        else:
            self._eroare(id_, f"Comandă necunoscută: {cmd}")
        return True

    def _stare(self) -> dict:
        from .constante import VERSIUNE as versiune  # noqa: PLC0415

        motor = self._motor
        return {
            "ev": "stare",
            "protocol": PROTOCOL,
            "versiune": versiune,
            "model_incarcat": bool(motor is not None and getattr(motor, "incarcat", False)),
            "dispozitiv": getattr(motor, "dispozitiv", "") if motor is not None else "",
        }

    # ------------------------------------------------------------------ transcriere fișier

    def _transcrie(self, id_, cale: str, limba: str, termeni: str, semnal: threading.Event) -> None:
        try:
            motor = self.motor()
            with self._motor_blocare:
                if semnal.is_set():
                    raise _Anulat()
                rezultat = motor.transcrie(
                    cale,
                    limba=limba,
                    termeni=termeni,
                    progres=lambda p: self.scrie({"ev": "progres", "id": id_, "p": round(float(p), 3)}),
                    faza=lambda f: self.scrie({"ev": "faza", "id": id_, "text": str(f)}),
                )
            if semnal.is_set():
                raise _Anulat()
            self.scrie(
                {
                    "ev": "rezultat",
                    "id": id_,
                    "text": rezultat.text,
                    "segmente": [{"start": s.start, "end": s.end, "text": s.text} for s in rezultat.segmente],
                    "secunde_audio": rezultat.secunde_audio,
                    "dispozitiv": getattr(rezultat, "dispozitiv", ""),
                }
            )
        except BaseException as exc:  # noqa: BLE001 — orice eroare ajunge la programul care a cerut
            if isinstance(exc, _Anulat) or type(exc).__name__ == "Anulat":
                self.scrie({"ev": "anulat", "id": id_})
            else:
                self._eroare(id_, exc)
        finally:
            self._transcrieri.pop(str(id_), None)

    # ------------------------------------------------------------------ dictare

    def _porneste_dictarea(self, id_, limba: str, termeni: str) -> None:
        try:
            microfon = self._microfon_fabrica()
            microfon.porneste()
        except Exception as exc:  # noqa: BLE001
            self._eroare(id_, exc, "Verifică microfonul în setările Windows (Confidențialitate → Microfon).")
            return
        stare = {"id": id_, "microfon": microfon, "oprit": threading.Event(), "anulat": False, "text": [], "limba": limba, "termeni": termeni}
        self._dictare = stare
        self.scrie({"ev": "dictare_pornita", "id": id_})
        stare["fir"] = self._porneste_fir(self._bucla_dictare, stare)

    def _opreste_dictarea(self, anulat: bool) -> None:
        stare = self._dictare
        if stare is None:
            return
        stare["anulat"] = anulat
        stare["oprit"].set()

    def _fragment(self, stare: dict, sunet) -> None:
        if sunet is None or len(sunet) < int(0.5 * RATA):  # prea puțin sunet
            return
        try:
            with self._motor_blocare:
                rezultat = self.motor().transcrie(sunet, limba=stare["limba"], termeni=stare["termeni"], progres=None, faza=None)
        except BaseException as exc:  # noqa: BLE001
            if type(exc).__name__ != "Anulat":
                self._eroare(stare["id"], exc)
            return
        text = (rezultat.text or "").strip()
        if text and not stare["anulat"]:
            stare["text"].append(text)
            self.scrie({"ev": "fragment", "id": stare["id"], "text": text})

    def _bucla_dictare(self, stare: dict) -> None:
        microfon = stare["microfon"]
        try:
            while not stare["oprit"].is_set():
                if microfon.scurgere() < self._secunde_bucata:
                    stare["oprit"].wait(0.1)
                    self.scrie({"ev": "nivel", "id": stare["id"], "nivel": round(float(getattr(microfon, "nivel", 0.0)), 2)})
                    continue
                self._fragment(stare, microfon.preia())
            if stare["anulat"]:
                microfon.anuleaza()
            else:
                self._fragment(stare, microfon.opreste().pcm)
        except Exception as exc:  # noqa: BLE001 — microfonul deconectat în timpul dictării
            try:
                microfon.anuleaza()
            except Exception:  # noqa: BLE001
                pass
            self._eroare(stare["id"], exc, "Verifică dacă microfonul este conectat, apoi pornește dictarea din nou.")
        finally:
            self._dictare = None
            if stare["anulat"]:
                self.scrie({"ev": "anulat", "id": stare["id"]})
            else:
                self.scrie({"ev": "dictare_oprita", "id": stare["id"], "text": " ".join(stare["text"])})


class _Anulat(Exception):
    pass


def _motor_implicit():
    from .motor import MotorWhisper  # noqa: PLC0415

    return MotorWhisper()


def _microfon_implicit():
    from .inregistrare import Microfon  # noqa: PLC0415

    return Microfon()


def _flux_windows(handle: int, mod: str):
    """În programul împachetat fără consolă (DTED.exe) ``sys.stdin``/``sys.stdout`` sunt None, deși
    Scribner a pornit programul cu canale legate: le deschidem direct din handle-urile Windows."""
    try:
        import ctypes  # noqa: PLC0415
        import msvcrt  # noqa: PLC0415
        import os  # noqa: PLC0415

        h = ctypes.windll.kernel32.GetStdHandle(handle)
        if not h or h == -1:
            return None
        fd = msvcrt.open_osfhandle(h, os.O_RDONLY if mod == "r" else os.O_WRONLY)
        return open(fd, mod, encoding="utf-8", errors="replace", buffering=1 if mod == "w" else -1, closefd=False)
    except Exception:  # noqa: BLE001 — nu e Windows sau nu există canale
        return None


def ruleaza(intrare=None, iesire=None, **optiuni) -> int:
    """Bucla serviciului: citește comenzi până la ``iesire`` sau sfârșitul intrării."""
    if intrare is None:
        intrare = sys.stdin or _flux_windows(-10, "r")
        try:
            intrare.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass
    iesire = iesire or sys.stdout or _flux_windows(-11, "w")
    if intrare is None or iesire is None:
        return 2

    def scrie(mesaj: dict) -> None:
        iesire.write(json.dumps(mesaj, ensure_ascii=False) + "\n")
        iesire.flush()

    serviciu = Serviciu(scrie, **optiuni)
    serviciu.scrie({"ev": "gata", "protocol": PROTOCOL})
    for linie in intrare:
        linie = linie.strip()
        if not linie:
            continue
        try:
            comanda = json.loads(linie)
        except ValueError:
            serviciu.scrie({"ev": "eroare", "id": None, "mesaj": "Comanda nu este JSON valid.", "ce_fac": ""})
            continue
        if not serviciu.executa(comanda):
            break
    serviciu.executa({"cmd": "iesire"})
    serviciu.asteapta(10.0)
    return 0
