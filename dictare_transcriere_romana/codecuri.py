"""Ce are nevoie programul ca să poată asculta fișierele audio (cerința 24).

La instalare și la fiecare pornire, programul se uită singur dacă poate deschide
fișierele audio obișnuite (MP3, WAV, M4A, OGG, FLAC). Dacă ceva lipsește, îl
aduce singur, ca dependență a lui, într-un dosar propriu — fără să schimbe
setările Windows și fără drepturi de administrator (acelea se cer doar dacă nu
există altă cale, și atunci se explică de ce, în cuvinte simple).

Descărcarea se face numai de pe surse oficiale și se verifică amprenta
SHA-256. Dacă amprenta nu se potrivește, nu se instalează nimic și se încearcă
din nou (de până la trei ori, prin ``descarcare.descarca``).

Când un fișier audio are un format ciudat, programul îl transformă singur într-un
WAV pe care îl citește sigur (``transforma_in_wav``), înainte să spună că nu
merge.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import cai, descarcare, jurnal

#: Sursele oficiale de unde se aduce ffmpeg, cu fișierul de amprentă de lângă.
#: Amândouă sunt construcțiile de Windows arătate de site-ul oficial ffmpeg.org.
SURSE_FFMPEG: tuple[tuple[str, str], ...] = (
    (
        "FFmpeg (construcția oficială BtbN)",
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest-win64-gpl.zip",
    ),
    (
        "FFmpeg (construcția gyan.dev)",
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    ),
)

#: Biblioteca Python care aduce, în ea, un ffmpeg gata de folosit.
PACHET_FFMPEG = "imageio-ffmpeg"
VERSIUNE_PACHET_FFMPEG = "0.6.0"
INDEX_PYPI = "https://pypi.org/pypi"

#: Câte secunde așteptăm după ffmpeg la o comandă scurtă.
TIMEOUT_COMANDA = 60

#: Decodoarele de care are nevoie programul, pe nume (fără cuvinte tehnice mari).
DECODOARE = ("mp3", "aac", "vorbis", "flac", "opus", "pcm_s16le")

#: Mesajul cerut de cerință, fără cuvântul „codec”.
MESAJ_PREGATIRE = (
    "Programul pregătește ce îi trebuie ca să poată asculta fișierul tău. "
    "Durează puțin, nu trebuie să faci nimic."
)

#: Mesajul de când lipsește internetul.
MESAJ_FARA_INTERNET = (
    "Ca să pot deschide acest fișier, am nevoie de internet o singură dată, "
    "pentru câteva minute. Pornește internetul și apasă „Încearcă din nou”."
)

#: Mesajul de când amprenta nu se potrivește (se încearcă din nou).
MESAJ_SUMA_GRESITA = "Fișierul descărcat nu e bun. Încerc din nou."


class EroareCodecuri(RuntimeError):
    """Ceva lipsește și nu a putut fi adus; mesajul este pentru utilizator."""

    def __init__(self, mesaj: str, fara_internet: bool = False, ce_fac: str = "", detalii: str = ""):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.fara_internet = fara_internet
        self.ce_fac = ce_fac
        self.detalii = detalii


@dataclass
class StareCodecuri:
    """Ce am găsit pe calculator, la verificarea de la pornire."""

    ffmpeg: Path | None = None
    sursa: str = ""
    decodoare_lipsa: tuple[str, ...] = ()
    versiune: str = ""
    mesaj: str = ""

    @property
    def ok(self) -> bool:
        return self.ffmpeg is not None and not self.decodoare_lipsa

    def pentru_utilizator(self) -> str:
        if self.ok:
            sursa = f" ({self.sursa})" if self.sursa else ""
            return f"Fișierele audio se pot deschide{sursa}."
        if self.ffmpeg is None:
            return "Lipsește ce îi trebuie programului ca să asculte fișierele audio."
        return (
            "Unele fișiere audio nu pot fi deschise deocamdată: "
            + ", ".join(self.decodoare_lipsa)
            + "."
        )


# --------------------------------------------------------------------------- unde este ffmpeg


def ffmpeg_din_program() -> Path | None:
    """ffmpeg adus de program în dosarul lui, dacă este acolo."""
    for parte in ("ffmpeg/ffmpeg.exe", "ffmpeg.exe", "ffmpeg/bin/ffmpeg.exe"):
        cale = cai.director_program() / parte
        if cale.exists() and cale.is_file():
            return cale
    return None


def ffmpeg_din_biblioteca() -> Path | None:
    """ffmpeg care vine în biblioteca Python instalată de program (imageio-ffmpeg)."""
    try:
        import imageio_ffmpeg  # type: ignore

        cale = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if cale.exists():
            return cale
    except Exception as exc:  # biblioteca poate lipsi; nu este o eroare gravă
        jurnal.detaliu(f"ffmpeg din bibliotecă nu a putut fi găsit: {exc}")
    return None


def ffmpeg_din_windows() -> Path | None:
    """ffmpeg instalat de utilizator în Windows (dacă folosește programul pe acela)."""
    gasit = shutil.which("ffmpeg")
    return Path(gasit) if gasit else None


def ffmpeg_disponibil() -> tuple[Path | None, str]:
    """Caută ffmpeg peste tot unde poate fi: întoarce calea și de unde vine."""
    for cauta, nume in (
        (ffmpeg_din_program, "adus de program"),
        (ffmpeg_din_biblioteca, "din biblioteca programului"),
        (ffmpeg_din_windows, "instalat în Windows"),
    ):
        try:
            cale = cauta()
        except Exception as exc:
            jurnal.detaliu(f"Verificarea ffmpeg ({nume}) a dat eroare: {exc}")
            continue
        if cale is not None:
            return cale, nume
    return None, ""


def _ruleaza(executabil: Path, argumente: list[str], timeout: int = TIMEOUT_COMANDA) -> subprocess.CompletedProcess:
    """Rulează ffmpeg fără fereastră neagră și întoarce rezultatul."""
    pornire = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(  # noqa: S603 - pornim doar ffmpeg, cu argumente proprii
        [str(executabil), *argumente],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=pornire,
    )


def _decodoare_lipsa(executabil: Path | None) -> tuple[str, ...]:
    """Ce decodoare nu are ffmpeg-ul găsit (verificare pe lista lui reală)."""
    if executabil is None:
        return tuple(DECODOARE)
    try:
        rezultat = _ruleaza(executabil, ["-hide_banner", "-decoders"])
    except Exception as exc:
        jurnal.atentionare(f"Lista decodoarelor nu a putut fi citită: {exc}")
        return tuple(DECODOARE)
    lista = (rezultat.stdout or "").lower()
    return tuple(nume for nume in DECODOARE if nume not in lista)


def _versiune(executabil: Path | None) -> str:
    if executabil is None:
        return ""
    try:
        rezultat = _ruleaza(executabil, ["-hide_banner", "-version"])
    except Exception:
        return ""
    prima = (rezultat.stdout or "").splitlines()
    return prima[0][:120] if prima else ""


def verifica() -> StareCodecuri:
    """Verifică, ieftin, dacă programul poate asculta fișierele audio acceptate."""
    executabil, sursa = ffmpeg_disponibil()
    lipsa = _decodoare_lipsa(executabil) if executabil is not None else ()
    stare = StareCodecuri(
        ffmpeg=executabil,
        sursa=sursa,
        decodoare_lipsa=lipsa,
        versiune=_versiune(executabil),
    )
    stare.mesaj = stare.pentru_utilizator()
    return stare


def are_nevoie() -> bool:
    """Adevărat dacă lipsește ceva (ffmpeg sau un decodor)."""
    return not verifica().ok


# --------------------------------------------------------------------------- aduce ffmpeg


def _citeste_text(url: str, timeout: int = 30) -> str:
    """Citește un fișier mic de text de la o adresă oficială (pentru amprentă)."""
    return descarcare._citeste_text(url, timeout=timeout)  # noqa: SLF001 - ajutor comun


def _suma_din_text(text: str) -> str:
    """Amprenta SHA-256 scrisă într-un fișier oficial de sume."""
    potrivire = re.search(r"\b([0-9a-fA-F]{64})\b", text or "")
    return potrivire.group(1).lower() if potrivire else ""


def _suma_oficiala_ffmpeg(url: str) -> str:
    """Amprenta publicată lângă arhiva de ffmpeg (``….zip.sha256``)."""
    return _suma_din_text(_citeste_text(url + ".sha256", timeout=30))


def _suma_pip(pachet: str, versiune: str) -> tuple[str, str]:
    """(suma SHA-256, numele fișierului) pentru pachetul de pe PyPI."""
    date = json.loads(_citeste_text(f"{INDEX_PYPI}/{pachet}/{versiune}/json", timeout=30))
    potrivite = [
        fisier
        for fisier in date.get("urls", [])
        if fisier.get("filename", "").endswith(("win_amd64.whl", "win_arm64.whl", "any.whl"))
    ]
    if not potrivite:
        raise EroareCodecuri(
            "Nu am găsit pachetul potrivit pe site-ul oficial.",
            ce_fac="Verifică dacă internetul funcționează și încearcă din nou.",
        )
    arhitectura = cai.arhitectura()
    preferat = next(
        (f for f in potrivite if arhitectura.lower().replace("x86", "win_") in f["filename"].lower()),
        potrivite[0],
    )
    return preferat["sha256"], preferat["filename"]


def _instaleaza_prin_pip(progres=None) -> bool:
    """Aduce ffmpeg ca dependență a programului, cu amprenta verificată de pip."""
    try:
        suma, nume_fisier = _suma_pip(PACHET_FFMPEG, VERSIUNE_PACHET_FFMPEG)
    except Exception as exc:
        jurnal.atentionare(f"Amprenta pachetului {PACHET_FFMPEG} nu a putut fi citită: {exc}")
        return False
    if progres is not None:
        progres(0.05, f"descarc ce are nevoie programul ({nume_fisier})")
    folder = Path(tempfile.mkdtemp(prefix="dictare-cerinte-"))
    cerinte = folder / "cerinte.txt"
    cerinte.write_text(
        f"{PACHET_FFMPEG}=={VERSIUNE_PACHET_FFMPEG} --hash=sha256:{suma}\n", encoding="utf-8"
    )
    comanda = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-deps",
        "--no-input",
        "--disable-pip-version-check",
        "--require-hashes",
        "‑‑quiet" if False else "--quiet",
        "-r",
        str(cerinte),
    ]
    try:
        rezultat = _ruleaza(Path(sys.executable), comanda[1:], timeout=1800)
    except Exception as exc:
        jurnal.atentionare(f"Instalarea bibliotecii audio a eșuat: {exc}")
        return False
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if rezultat.returncode != 0:
        jurnal.atentionare(
            f"Instalarea bibliotecii audio nu a reușit (cod {rezultat.returncode}): "
            f"{(rezultat.stderr or '')[-400:]}"
        )
        return False
    jurnal.info(f"Biblioteca audio {PACHET_FFMPEG}=={VERSIUNE_PACHET_FFMPEG} a fost instalată.")
    if progres is not None:
        progres(0.9, "verific ce am adus")
    return ffmpeg_din_biblioteca() is not None


def _despacheteaza_ffmpeg(arhiva: Path) -> Path | None:
    """Scoate ``ffmpeg.exe`` din arhiva oficială, în dosarul programului."""
    destinatie = cai.director_program() / "ffmpeg"
    destinatie.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(arhiva) as pachet:
            for nume in pachet.namelist():
                if nume.lower().endswith("bin/ffmpeg.exe") or nume.lower() == "ffmpeg.exe":
                    with pachet.open(nume) as sursa, open(destinatie / "ffmpeg.exe", "wb") as iesire:
                        shutil.copyfileobj(sursa, iesire)
                    jurnal.info(f"ffmpeg a fost pus în {destinatie}.")
                    return destinatie / "ffmpeg.exe"
    except (zipfile.BadZipFile, OSError) as exc:
        jurnal.atentionare(f"Arhiva de ffmpeg nu a putut fi deschisă: {exc}")
    return None


def _descarca_ffmpeg(progres=None) -> Path | None:
    """Descarcă ffmpeg de pe sursa oficială, cu amprenta verificată."""
    ultima_eroare: Exception | None = None
    for nume_sursa, url in SURSE_FFMPEG:
        try:
            suma = _suma_oficiala_ffmpeg(url)
            if not suma:
                jurnal.atentionare(f"Amprenta oficială lipsește la {nume_sursa}.")
                continue
            if progres is not None:
                progres(0.1, f"descarc ce are nevoie programul ({nume_sursa})")
            arhiva = descarcare.descarca(
                url,
                cai.director_descarcari() / Path(url).name,
                progres=None,
                suma_asteptata=suma,
                reincercari=3,
            )
            if progres is not None:
                progres(0.85, "pregătesc ce am descărcat")
            gasit = _despacheteaza_ffmpeg(arhiva)
            if gasit is not None:
                return gasit
        except descarcare.SumaGresita as exc:
            ultima_eroare = exc
            jurnal.atentionare(f"{MESAJ_SUMA_GRESITA} ({nume_sursa})")
            if progres is not None:
                progres(0.1, "fișierul descărcat nu e bun; încerc din nou")
            continue
        except descarcare.EroareDescarcare as exc:
            if exc.fara_internet:
                raise EroareCodecuri(
                    MESAJ_FARA_INTERNET,
                    fara_internet=True,
                    ce_fac="Pornește internetul, apoi apasă „Încearcă din nou”.",
                ) from exc
            ultima_eroare = exc
            continue
    if ultima_eroare is not None:
        jurnal.atentionare(f"ffmpeg nu a putut fi adus: {ultima_eroare}")
    return None


def asigura(progres=None) -> Path | None:
    """Se asigură că programul poate asculta fișiere audio; aduce ce lipsește.

    ``progres(fractiune, mesaj)`` este chemat din când în când, ca omul să vadă
    ce se întâmplă. Întoarce calea către ffmpeg sau ``None`` dacă nu s-a putut.
    Ridică ``EroareCodecuri`` când lipsește internetul.
    """
    stare = verifica()
    if stare.ok:
        return stare.ffmpeg
    if progres is not None:
        progres(0.02, "verific ce am pe calculator")
    if _instaleaza_prin_pip(progres):
        din_nou = verifica()
        if din_nou.ok:
            return din_nou.ffmpeg
    gasit = _descarca_ffmpeg(progres)
    if gasit is not None:
        din_nou = verifica()
        return din_nou.ffmpeg
    return None


# --------------------------------------------------------------------------- transformări


def transforma_in_wav(cale: str | Path, progres=None) -> Path | None:
    """Transformă orice fișier audio într-un WAV pe care programul îl citește sigur.

    Se folosește doar când citirea obișnuită nu merge: unele fișiere au formate
    ciudate, iar programul încearcă singur să le facă bune, înainte să spună că
    nu se poate.
    """
    executabil, _sursa = ffmpeg_disponibil()
    if executabil is None:
        return None
    sursa = Path(cale)
    if not sursa.exists():
        return None
    if progres is not None:
        progres(0.05, MESAJ_PREGATIRE)
    folder = cai.director_descarcari() / "pregatite"
    folder.mkdir(parents=True, exist_ok=True)
    destinatie = folder / (sursa.stem + ".wav")
    try:
        rezultat = _ruleaza(
            executabil,
            [
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(sursa),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(destinatie),
            ],
            timeout=1800,
        )
    except Exception as exc:
        jurnal.atentionare(f"Transformarea în WAV a eșuat: {exc}")
        return None
    if rezultat.returncode != 0 or not destinatie.exists():
        jurnal.atentionare(
            f"Transformarea în WAV nu a reușit (cod {rezultat.returncode}): "
            f"{(rezultat.stderr or '')[-300:]}"
        )
        return None
    if progres is not None:
        progres(1.0, "fișierul este pregătit")
    jurnal.info(f"Fișierul {sursa.name} a fost transformat în {destinatie.name}.")
    return destinatie


def se_descarca(cale: str | Path) -> bool:
    """Adevărat dacă fișierul chiar poate fi citit de ffmpeg (probă scurtă)."""
    executabil, _sursa = ffmpeg_disponibil()
    if executabil is None:
        return False
    try:
        rezultat = _ruleaza(
            executabil,
            ["-hide_banner", "-loglevel", "error", "-i", str(cale), "-f", "null", "-"],
            timeout=300,
        )
    except Exception:
        return False
    return rezultat.returncode == 0


def numara_sunetul(cale: str | Path) -> float:
    """Câte secunde are fișierul audio, citite de ffmpeg (0 dacă nu se poate)."""
    executabil, _sursa = ffmpeg_disponibil()
    if executabil is None:
        return 0.0
    try:
        rezultat = _ruleaza(executabil, ["-hide_banner", "-i", str(cale), "-f", "null", "-"])
    except Exception:
        return 0.0
    potrivire = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", rezultat.stderr or "")
    if not potrivire:
        return 0.0
    ore, minute, secunde = potrivire.groups()
    return int(ore) * 3600 + int(minute) * 60 + float(secunde)


# --------------------------------------------------------------------------- pași (cerința 24)


def text_pasi() -> str:
    """Pașii simpli, pentru „Citește-mă.txt” sau pentru [Trimite-mi pașii într-un fișier]."""
    executabil, sursa = ffmpeg_disponibil()
    linii = [
        "PREGĂTIREA SUNETULUI (dacă fișierele audio nu se deschid)",
        "",
        "Programul are nevoie, pentru a citi fișierele audio, de un mic program de sunet",
        "(ffmpeg) și de câteva bucăți care știu să citească MP3, WAV, M4A, OGG și FLAC.",
        "De obicei, programul le aduce singur la instalare. Dacă nu a reușit, iată ce faci:",
        "",
        "1. Pornește internetul.",
        "2. Deschide programul și apasă din nou pe „Transcriere fișier audio”; programul",
        "   încearcă să le aducă din nou, fără să te întrebe nimic.",
        "3. Dacă îți scrie că tot lipsesc, apasă butonul „Trimite-mi pașii într-un fișier”,",
        "   ca să primești pașii potriviți pentru calculatorul tău.",
        "4. După ce programul a terminat pregătirea, oprește internetul dacă lucrezi cu",
        "   informații importante: programul funcționează fără internet.",
        "",
        f"Pe acest calculator: {'am găsit ce trebuie' if executabil is not None else 'lipsește'}"
        + (f" ({sursa})" if sursa else ""),
    ]
    if executabil is not None:
        versiune = _versiune(executabil)
        if versiune:
            linii.append(f"Versiune: {versiune}")
    return "\n".join(linii)


def scrie_pasii_in_citeste_ma() -> Path:
    """Pune pașii în „Citește-mă.txt”, lângă program, și întoarce calea fișierului."""
    cale = cai.fisier_citeste_ma()
    bucata = "\n\n" + text_pasi() + "\n"
    try:
        with open(cale, "a", encoding="utf-8") as fisier:
            fisier.write(bucata)
        jurnal.info(f"Pașii de pregătire a sunetului au fost scriși în {cale}.")
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut scrie pașii în {cale}: {exc}")
    return cale


def curata_temporare() -> None:
    """Șterge fișierele tre trebuie create pentru citirea sunetului (WAV-uri pregătite)."""
    folder = cai.director_descarcari() / "pregatite"
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)


def biblioteci_audio_ok() -> bool:
    """Verificare ieftină, pentru ecranul de verificare: sunetul se poate citi."""
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return verifica().ok
