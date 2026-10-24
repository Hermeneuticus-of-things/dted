"""Pregătirea de la prima pornire, complet automată (fără pași manuali).

1. Modelul de transcriere ``large-v3-turbo-ct2`` (toate cele 5 fișiere), descărcat
   de pe Hugging Face la o revizie fixă, cu reluare și verificare SHA-256.
2. Dacă există o placă NVIDIA: bibliotecile cuBLAS 12 și cuDNN 9 (pachetele
   oficiale „nvidia-*” de pe PyPI), despachetate în folderul de date al programului
   (``<date>/cuda/nvidia/*/bin`` pe Windows, ``.../lib`` pe Linux). Fără NVIDIA nu se
   descarcă nimic în plus. ``motor.py`` le face apoi vizibile și testează placa;
   dacă testul eșuează, transcrierea merge pe procesor, fără eroare.

Nu folosește PyTorch. Mesajele de progres sunt în română.

Variabile de test (nu apar în interfață):
* ``DICTARE_DIR`` – alt folder de date (pentru o instalare curată de probă);
* ``DTED_SURSA_MODEL`` – un folder local din care se copiază modelul în loc de
  descărcare (verificarea SHA-256 se face la fel);
* ``DTED_FARA_CUDA_DESCARCARE=1`` – nu descărca bibliotecile CUDA.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Callable

from . import cai, jurnal
from .descarcare import EroareDescarcare, SumaGresita, descarca, sha256_fisier, text_progres

Progres = Callable[[str, float], None]

# --------------------------------------------------------------------------- modelul

MODEL_REPO = "deepdml/faster-whisper-large-v3-turbo-ct2"
MODEL_REVIZIE = "4df90f75321148c3a29a9e2351b7ddf8f5b115a8"
#: nume -> (mărime în octeți, SHA-256)
MODEL_FISIERE: dict[str, tuple[int, str]] = {
    "config.json": (2_263, "b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e"),
    "preprocessor_config.json": (340, "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711"),
    "tokenizer.json": (2_710_337, "297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd"),
    "vocabulary.json": (1_068_114, "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1"),
    "model.bin": (1_617_884_929, "e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da"),
}


_MODEL_EEK_REPO = "https://huggingface.co/eek/whisper-turbo-ro-en/resolve/main/ctranslate2-int8"

#: Modelul optimizat pentru română (v0.4.0): mărime + SHA-256 per fișier.
MODEL_EEK_FISIERE: dict[str, tuple[int, str]] = {
    "config.json": (2_238, "323f514961672d9279a718725f0df33645b49e8a02796e63c2507f8a0135652d"),
    "preprocessor_config.json": (357, "654cf18d3e163b948ceaf9766da56ce0b52de265d58673cf61c9376f126bd499"),
    "tokenizer.json": (3_930_645, "5c1bf30c9e716e1477bedef846b01be0013daecb89e9e3ef7ab89b23c178df1b"),
    "vocabulary.json": (1_068_114, "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1"),
    "model.bin": (820_316_291, "2ad5bcb5491f232eb2b3363ef69eba486dc8b68079df7d4e3f1b9eca432efdc8"),
}

#: Manifestele modelelor cunoscute: folder → (fișiere, adresă de descărcare).
#: Folderul din kit NU se descarcă niciodată; adresa e doar pentru refacere.
_MANIFESTE: dict[str, tuple[dict, str]] = {}


def _manifest(folder: Path):
    """Manifestul modelului din folderul dat (None dacă nu e unul cunoscut)."""
    from .constante import WHISPER_NUME, WHISPER_NUME_EEK

    if not _MANIFESTE:
        _MANIFESTE[WHISPER_NUME] = (MODEL_FISIERE, "")
        _MANIFESTE[WHISPER_NUME_EEK] = (MODEL_EEK_FISIERE, _MODEL_EEK_REPO)
    return _MANIFESTE.get(folder.name)


# --------------------------------------------------------------------------- CUDA

#: (pachet, versiune, {platformă: (fișier wheel, SHA-256)}).
#: nvrtc NU e necesar pentru CTranslate2 (verificat: transcrierea pe GPU merge fără el).
CUDA_PACHETE = (
    ("nvidia-cublas-cu12", "12.9.2.10", {
        "win": ("nvidia_cublas_cu12-12.9.2.10-py3-none-win_amd64.whl",
                "623f43027d40d44ceadf0043f002bd25cf353e8f13ce90b9a87057019f560661"),
        "linux": ("nvidia_cublas_cu12-12.9.2.10-py3-none-manylinux_2_27_x86_64.whl",
                  "e4f53a8ca8c5d6e8c492d0d0a3d565ecb59a751b19cfdaa4f6da0ab2104c1702"),
    }),
    ("nvidia-cudnn-cu12", "9.27.0.42", {
        "win": ("nvidia_cudnn_cu12-9.27.0.42-py3-none-win_amd64.whl",
                "06e9b0026f3bad97d2b58666330fabec04fe1672f776661ecb0ce0029c27f142"),
        "linux": ("nvidia_cudnn_cu12-9.27.0.42-py3-none-manylinux_2_27_x86_64.whl",
                  "0a4aa3a7d2264256506c6857fc41fc0c499982f78d70195b1cfcc9055c1957cd"),
    }),
)
_PYPI_JSON = "https://pypi.org/pypi/{pachet}/{versiune}/json"


def _platforma() -> str:
    return "win" if os.name == "nt" else "linux"


def director_cuda() -> Path:
    return cai.director_instalare() / "cuda"


_ULTIMUL_JURNALIZAT = [""]


def _anunta(progres: Progres | None, mesaj: str, fractiune: float) -> None:
    # În jurnal: doar etapele și pașii de 10% (nu fiecare MB descărcat).
    cheie = re.sub(r"(\d+)% \(.*\)$", lambda m: f"{int(m.group(1)) // 10 * 10}%", mesaj)
    if cheie != _ULTIMUL_JURNALIZAT[0]:
        _ULTIMUL_JURNALIZAT[0] = cheie
        jurnal.info(mesaj)
    if progres is not None:
        try:
            progres(mesaj, max(0.0, min(1.0, fractiune)))
        except Exception:
            pass


# --------------------------------------------------------------------------- ce lipsește


_MARCAJ_VERIFICARE = f".verificat-{MODEL_REVIZIE[:7]}.json"
_SHA_MEREU_SUB = 16 * 1024 * 1024  # fișierele mici se verifică la fiecare pornire


def fisiere_model_gresite(complet: bool = False) -> dict[str, str]:
    """{fișier: motiv} pentru ce lipsește sau nu e la revizia fixată (MODEL_REVIZIE).

    Mărimea se verifică mereu, SHA-256 se verifică mereu la fișierele mici. model.bin
    (1,6 GB) se verifică cu SHA-256 o singură dată (sau cu ``complet=True``), iar
    rezultatul se ține minte (mărime + dată) în ``.verificat-4df90f7.json``, ca pornirea
    să rămână rapidă și fără rețea.
    """
    folder = cai.fisier_model()
    marcaj = folder / _MARCAJ_VERIFICARE
    verificate: dict = {}
    if marcaj.exists() and not complet:
        try:
            verificate = json.loads(marcaj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            verificate = {}
    gresite: dict[str, str] = {}
    bune: dict[str, list] = {}
    manifest = _manifest(folder)
    asteptari = manifest[0] if manifest else {nume: (0, "") for nume in MODEL_FISIERE}
    for nume, (marime, suma) in asteptari.items():
        cale = folder / nume
        if not cale.is_file():
            gresite[nume] = "lipsește"
            continue
        info = cale.stat()
        semnatura = [info.st_size, int(info.st_mtime)]
        if manifest is None:
            bune[nume] = semnatura  # model necunoscut: fișierul există, e bine
            continue
        if info.st_size != marime:
            gresite[nume] = f"are {info.st_size} B în loc de {marime} B"
            continue
        if verificate.get(nume) == semnatura:
            bune[nume] = semnatura
            continue
        if not complet and marime > _SHA_MEREU_SUB:
            continue  # mărimea e bună; SHA-256 complet se face o dată, în fundal
        if sha256_fisier(cale).lower() != suma:
            gresite[nume] = "conținut diferit (SHA-256)"
            continue
        bune[nume] = semnatura
    # Marcajul se scrie DOAR după o verificare completă în care model.bin a trecut
    # efectiv prin SHA-256. Verificarea rapidă nu scrie nimic.
    if complet and not gresite and "model.bin" in bune:
        try:
            marcaj.write_text(json.dumps(bune), encoding="utf-8")
        except OSError:
            pass
    return gresite


def model_verificat_complet() -> bool:
    """Adevărat dacă marcajul spune că model.bin (așa cum e acum pe disc) a trecut SHA-256."""
    cale = cai.fisier_model() / "model.bin"
    marcaj = cai.fisier_model() / _MARCAJ_VERIFICARE
    try:
        verificate = json.loads(marcaj.read_text(encoding="utf-8"))
        info = cale.stat()
    except (OSError, ValueError):
        return False
    return verificate.get("model.bin") == [info.st_size, int(info.st_mtime)]


def fisiere_model_lipsa() -> list[str]:
    """Fișierele modelului care lipsesc sau nu se potrivesc (verificare rapidă)."""
    return list(fisiere_model_gresite())


def are_placa_nvidia() -> bool:
    """Adevărat dacă driverul NVIDIA (CUDA) este instalat."""
    import ctypes

    try:
        if os.name == "nt":
            ctypes.WinDLL("nvcuda.dll")
        else:
            ctypes.CDLL("libcuda.so.1")
        return True
    except OSError:
        return False


def _biblioteci_cuda_gasite() -> bool:
    from . import motor

    if os.name == "nt":
        cautate = ("cublas64_12.dll", "cudnn64_9.dll")
    else:
        cautate = ("libcublas.so.12", "libcudnn.so.9")
    # În folderul de date contează doar ce s-a despachetat complet (marcajul .gata).
    tinta = director_cuda()
    date_complete = all(
        (tinta / f".{pachet}-{versiune}.gata").exists() for pachet, versiune, _ in CUDA_PACHETE
    )
    gasite = set()
    for folder in motor.foldere_biblioteci_cuda():
        if not date_complete and tinta in folder.parents:
            continue
        for nume in cautate:
            if (folder / nume).exists():
                gasite.add(nume)
    return len(gasite) == len(cautate)


def trebuie_cuda() -> bool:
    if os.environ.get("DTED_FARA_CUDA_DESCARCARE") == "1":
        return False
    return are_placa_nvidia() and not _biblioteci_cuda_gasite()


CUDA_MARIME_TEXT = "aproximativ 1,2 GB de descărcat, 1,9 GB pe disc"


def stare_cuda(configurare=None) -> tuple[str, str, str]:
    """(stare, data, detaliu) salvate în setări: stare = "", "ok", "esuat" sau "refuzat"."""
    if configurare is None:
        from . import config

        configurare = config.incarca()
    return (
        getattr(configurare, "cuda_stare", ""),
        getattr(configurare, "cuda_stare_data", ""),
        getattr(configurare, "cuda_stare_detaliu", ""),
    )


def salveaza_stare_cuda(stare: str, detaliu: str = "", configurare=None) -> None:
    """Ține minte permanent rezultatul (ca să nu mai întrebăm/descărcăm la fiecare pornire)."""
    from datetime import datetime

    from . import config

    if configurare is None:
        configurare = config.incarca()
    configurare.cuda_stare = stare
    configurare.cuda_stare_data = datetime.now().strftime("%Y-%m-%d %H:%M")
    configurare.cuda_stare_detaliu = (detaliu or "")[:300]
    config.salveaza(configurare)
    jurnal.info(f"Bibliotecile plăcii video: stare „{stare}” ({configurare.cuda_stare_data}). {detaliu}".strip())


def cuda_de_propus(configurare=None) -> bool:
    """Adevărat doar dacă lipsesc bibliotecile și utilizatorul nu a refuzat / nu a eșuat deja.

    Nu folosește rețeaua. Reîncercarea după „refuzat”/„esuat” se face doar din butonul
    din Verificare sau Setări.
    """
    if not trebuie_cuda():
        return False
    return stare_cuda(configurare)[0] not in ("esuat", "refuzat")


def text_stare_cuda(configurare=None) -> str:
    """Rând suplimentar pentru Verificare/Setări (gol dacă nu e nimic de spus)."""
    try:
        if not trebuie_cuda():
            return ""
    except Exception:
        return ""
    stare, data, detaliu = stare_cuda(configurare)
    if stare == "esuat":
        return (f"Bibliotecile pentru placa video nu s-au putut descărca ({data}): {detaliu} "
                "Poți reîncerca cu butonul de mai jos.")
    if stare == "refuzat":
        return (f"Ai ales să nu descarci bibliotecile pentru placa video ({data}). "
                "Le poți descărca oricând cu butonul de mai jos.")
    return "Bibliotecile pentru placa video nu sunt descărcate încă."


def ce_lipseste(configurare=None) -> list[str]:
    lipsa = []
    if fisiere_model_lipsa():
        lipsa.append("modelul de transcriere (aproximativ 1,6 GB)")
    if cuda_de_propus(configurare):
        lipsa.append(f"bibliotecile pentru placa video NVIDIA ({CUDA_MARIME_TEXT})")
    return lipsa


def trebuie_pregatire() -> bool:
    return bool(ce_lipseste())


# --------------------------------------------------------------------------- modelul


def asigura_model(progres: Progres | None = None, baza: float = 0.0, spatiu: float = 0.6) -> Path:
    folder = cai.fisier_model()
    folder.mkdir(parents=True, exist_ok=True)
    gresite = fisiere_model_gresite(complet=True)
    lipsa = list(gresite)
    from datetime import datetime

    marca = datetime.now().strftime("%Y%m%d-%H%M")
    for nume, motiv in gresite.items():
        vechi = folder / nume
        if vechi.exists():  # fișier nepotrivit: îl păstrăm alături, apoi îl luăm din nou
            backup = folder / f"{nume}.bak-{marca}"
            if not backup.exists():
                vechi.replace(backup)
            else:
                vechi.unlink()
            jurnal.atentionare(f"Model: {nume} {motiv}; păstrat ca {backup.name}, îl iau din nou.")
    if not lipsa:
        _anunta(progres, "Modelul de transcriere este gata.", baza + spatiu)
        return folder
    manifest = _manifest(folder)
    fisiere_model = manifest[0] if manifest else MODEL_FISIERE
    adresa_model = manifest[1] if manifest else ""
    sursa_locala = os.environ.get("DTED_SURSA_MODEL", "")
    total = sum(fisiere_model[n][0] for n in lipsa) or 1
    facut = 0
    for nume in lipsa:
        marime, suma = fisiere_model[nume]
        dest = folder / nume
        inceput = facut

        def arata(descarcat: int, total_fisier: int, _i=inceput) -> None:
            _anunta(
                progres,
                text_progres(_i + descarcat, total, "Descarc modelul de transcriere"),
                baza + spatiu * ((_i + descarcat) / total),
            )

        if sursa_locala:
            _anunta(progres, f"Copiez modelul de transcriere ({nume}) din folderul local…", baza + spatiu * facut / total)
            temporar = dest.with_suffix(dest.suffix + ".partial")
            shutil.copyfile(Path(sursa_locala) / nume, temporar)
            gasit = sha256_fisier(temporar)
            if gasit.lower() != suma:
                temporar.unlink(missing_ok=True)
                raise SumaGresita(nume, suma, gasit)
            temporar.replace(dest)
        else:
            if adresa_model:
                url = f"{adresa_model}/{nume}?download=true"
            else:
                url = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVIZIE}/{nume}?download=true"
            _anunta(progres, f"Descarc modelul de transcriere ({nume})…", baza + spatiu * facut / total)
            descarca(url, dest, arata, suma_asteptata=suma)
        facut += marime
        jurnal.info(f"Model: {nume} descărcat și verificat (SHA-256).")
    rest = fisiere_model_gresite(complet=True)
    if rest:
        raise EroareDescarcare(f"Modelul nu s-a verificat: {rest}")
    _anunta(progres, "Modelul de transcriere a fost descărcat și verificat.", baza + spatiu)
    return folder


# --------------------------------------------------------------------------- CUDA


def _url_wheel(pachet: str, versiune: str, fisier: str) -> str:
    """Adresa oficială a fișierului de pe PyPI (din API-ul JSON)."""
    import urllib.request

    from .descarcare import AGENT

    cerere = urllib.request.Request(
        _PYPI_JSON.format(pachet=pachet, versiune=versiune), headers={"User-Agent": AGENT}
    )
    try:
        with urllib.request.urlopen(cerere, timeout=60) as raspuns:
            date = json.load(raspuns)
    except Exception as exc:
        raise EroareDescarcare(
            "Nu am putut afla de unde se descarcă bibliotecile pentru placa video. "
            "Verifică internetul; programul merge oricum, pe procesor.",
            fara_internet=True,
        ) from exc
    for intrare in date.get("urls", []):
        if intrare.get("filename") == fisier:
            return intrare["url"]
    raise EroareDescarcare(f"Pe PyPI nu există fișierul {fisier}.")


def _despacheteaza(wheel: Path, destinatie: Path) -> int:
    """Scoate din wheel doar bibliotecile (nvidia/*/bin sau nvidia/*/lib)."""
    sub = "/bin/" if os.name == "nt" else "/lib/"
    scrise = 0
    with zipfile.ZipFile(wheel) as arhiva:
        for membru in arhiva.infolist():
            nume = membru.filename
            if not nume.startswith("nvidia/") or sub not in nume or nume.endswith("/"):
                continue
            tinta = destinatie / Path(*nume.split("/"))
            tinta.parent.mkdir(parents=True, exist_ok=True)
            with arhiva.open(membru) as sursa, open(tinta, "wb") as iesire:
                shutil.copyfileobj(sursa, iesire, 1024 * 1024)
            scrise += 1
    return scrise


def asigura_cuda(progres: Progres | None = None, baza: float = 0.6, spatiu: float = 0.4) -> bool:
    """Descarcă și despachetează cuBLAS/cuDNN; întoarce True dacă sunt gata."""
    if not trebuie_cuda():
        return True
    platforma = _platforma()
    tinta = director_cuda()
    descarcari = tinta / "_descarcari"
    descarcari.mkdir(parents=True, exist_ok=True)
    pas = spatiu / max(1, len(CUDA_PACHETE))
    for index, (pachet, versiune, fisiere) in enumerate(CUDA_PACHETE):
        fisier, suma = fisiere[platforma]
        inceput = baza + pas * index
        marcaj = tinta / f".{pachet}-{versiune}.gata"
        if marcaj.exists():
            continue
        _anunta(progres, f"Descarc bibliotecile pentru placa video ({pachet})…", inceput)
        wheel = descarcari / fisier

        def arata(descarcat: int, total: int, _i=inceput, _p=pachet) -> None:
            _anunta(
                progres,
                text_progres(descarcat, total, f"Descarc bibliotecile pentru placa video ({_p})"),
                _i + pas * 0.8 * (descarcat / total if total else 0),
            )

        if not (wheel.exists() and sha256_fisier(wheel).lower() == suma):
            descarca(_url_wheel(pachet, versiune, fisier), wheel, arata, suma_asteptata=suma)
        _anunta(progres, f"Pregătesc bibliotecile pentru placa video ({pachet})…", inceput + pas * 0.85)
        _despacheteaza(wheel, tinta)
        marcaj.write_text(suma, encoding="utf-8")
        wheel.unlink(missing_ok=True)  # arhiva nu mai trebuie; bibliotecile rămân
    _anunta(progres, "Bibliotecile pentru placa video sunt gata.", baza + spatiu)
    from . import motor

    motor._FOLDERE_CUDA_ADAUGATE.clear()
    motor.pregateste_biblioteci_cuda()
    return True


# --------------------------------------------------------------------------- tot


def pregateste(
    progres: Progres | None = None, cu_cuda: bool = False, configurare=None, cu_model: bool = True
) -> dict:
    """Tot ce trebuie la prima pornire. Modelul e obligatoriu; CUDA doar cu acordul utilizatorului."""
    rezultat = {"model": "", "cuda": "nu e nevoie"}
    # cu_model=False (context „cuda”: butonul plăcii video): modelul NU se atinge aici;
    # verificarea lui rămâne pe seama verificării din fundal de la pornire.
    model_de_pregatit = cu_model and (bool(fisiere_model_lipsa()) or not model_verificat_complet())
    if model_de_pregatit:
        _anunta(progres, "Pregătesc modelul de transcriere…", 0.0)
    else:
        _anunta(progres, "Pregătesc bibliotecile pentru placa video…", 0.0)
    if model_de_pregatit:
        rezultat["model"] = str(asigura_model(progres))
    elif not cu_model:
        rezultat["model"] = "neatins (doar placa video)"
    else:
        rezultat["model"] = str(cai.fisier_model())
    if trebuie_cuda():
        if not cu_cuda:
            rezultat["cuda"] = "nedescărcate (fără acord)"
        else:
            try:
                asigura_cuda(progres)
                rezultat["cuda"] = "gata"
                salveaza_stare_cuda("ok", "", configurare)
            except Exception as exc:  # placa video e un bonus: continuăm pe procesor
                jurnal.atentionare(f"Bibliotecile pentru placa video nu au putut fi pregătite: {exc}")
                rezultat["cuda"] = f"nepregătite: {exc}"
                salveaza_stare_cuda("esuat", str(exc), configurare)
    _anunta(progres, "Gata! Programul este pregătit.", 1.0)
    return rezultat


def main(argv: list[str] | None = None) -> int:
    """Rulare din consolă (folosită de install.sh și de teste): ``python -m … --pregateste``."""
    ultimul = [""]

    def tipareste(mesaj: str, fractiune: float) -> None:
        scurt = re.sub(r" \(.*\)$", "", mesaj)
        linie = f"[{int(fractiune * 100):3d}%] {scurt}"
        if linie != ultimul[0]:
            ultimul[0] = linie
            print(linie, flush=True)

    cu_cuda = False
    if trebuie_cuda():
        print(f"Am găsit o placă video NVIDIA. Bibliotecile pentru ea: {CUDA_MARIME_TEXT}.", flush=True)
        if os.environ.get("DTED_CUDA_DA") == "1":
            cu_cuda = True
        elif sys.stdin is not None and sys.stdin.isatty():
            raspuns = input("Le descarc acum? [d/N] ").strip().lower()
            cu_cuda = raspuns in ("d", "da", "y", "yes")
            if not cu_cuda:
                salveaza_stare_cuda("refuzat")
        else:
            print("Nu le descarc fără confirmare. Le poți descărca din program: Verificare → "
                  "„Descarcă bibliotecile pentru placa video”.", flush=True)
    try:
        rezultat = pregateste(tipareste, cu_cuda=cu_cuda)
    except Exception as exc:
        print(f"Pregătirea nu s-a terminat: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(rezultat, ensure_ascii=False))
    return 0
