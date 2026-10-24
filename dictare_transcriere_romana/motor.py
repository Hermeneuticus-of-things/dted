"""Motorul de transcriere: faster-whisper (CTranslate2), rulat 100% local.

Modelul este citit dintr-un fișier local (``model/large-v3-turbo``), deci
după instalare nu mai este nevoie de internet. Dacă este disponibilă o placă
NVIDIA cu CUDA, se folosește automat; în rest se folosește procesorul — fără
eroări și fără întrebări tehnice.

Transcrierea pornește mereu cu limba cerută explicit (implicit română),
cu ``task="transcribe"``, ca modelul să nu ghicească altă limbă și să nu
traduce textul în engleză.

faster-whisper folosește aceleași modele Whisper, rulate optimizat prin
CTranslate2, deci acuratetea este practic identică cu Whisper-ul original,
dar este de câteva ori mai rapid și consumă mai puține resurse (nu mai are
nevoie de PyTorch).
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import cai, jurnal
from .constante import prompt_romana
from .text_ro import normalizeaza

try:
    import numpy as np
except Exception:
    np = None


# --------------------------------------------------------------------------- CUDA (cuBLAS 12, cuDNN 9)

_FOLDERE_CUDA_ADAUGATE: list[str] = []
#: Ce s-a ales la ultima încărcare a modelului, în română (pentru jurnal / Verificare).
STARE_PLACA_VIDEO = "Placa video: încă neverificată."


def foldere_biblioteci_cuda() -> list[Path]:
    """Folderele cu bibliotecile NVIDIA (pachetele pip nvidia-cublas-cu12, nvidia-cudnn-cu12).

    Se caută în: programul construit (PyInstaller), site-packages din mediul
    curent și folderul de date al programului (unde le descarcă instalarea).
    """
    import sys

    radacini: list[Path] = []
    doar_date = os.environ.get("DTED_CUDA_DOAR_DATE") == "1"  # test: doar ce a descărcat programul
    if getattr(sys, "_MEIPASS", None) and not doar_date:
        radacini.append(Path(sys._MEIPASS))
    for intrare in ([] if doar_date else sys.path):
        if intrare and intrare.replace("\\", "/").lower().endswith("site-packages"):
            radacini.append(Path(intrare))
    try:
        radacini.append(cai.director_instalare() / "cuda")
    except Exception:
        pass
    sub = "bin" if os.name == "nt" else "lib"
    foldere: list[Path] = []
    for radacina in radacini:
        for folder in sorted((radacina / "nvidia").glob(f"*/{sub}")):
            if folder.is_dir() and folder not in foldere:
                foldere.append(folder)
    return foldere


def pregateste_biblioteci_cuda() -> list[str]:
    """Face vizibile cuBLAS/cuDNN ÎNAINTE ca ctranslate2 să aibă nevoie de ele.

    Windows: ``os.add_dll_directory`` + PATH. Linux: încărcare explicită cu
    ``RTLD_GLOBAL`` (LD_LIBRARY_PATH nu mai contează după pornirea procesului).
    ``DTED_FARA_DLL_CUDA=1`` le ascunde (test pentru trecerea pe procesor).
    """
    if _FOLDERE_CUDA_ADAUGATE or os.environ.get("DTED_FARA_DLL_CUDA") == "1":
        return _FOLDERE_CUDA_ADAUGATE
    for folder in foldere_biblioteci_cuda():
        cale = str(folder)
        if os.name == "nt":
            try:
                os.add_dll_directory(cale)
            except (OSError, AttributeError):
                continue
            os.environ["PATH"] = cale + os.pathsep + os.environ.get("PATH", "")
        else:
            import ctypes

            for biblioteca_so in sorted(folder.glob("lib*.so*")):
                try:
                    ctypes.CDLL(str(biblioteca_so), mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass
            os.environ["LD_LIBRARY_PATH"] = cale + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
        _FOLDERE_CUDA_ADAUGATE.append(cale)
    return _FOLDERE_CUDA_ADAUGATE


def descriere_placa_video() -> str:
    """Starea plăcii video, în română, pentru Verificare și Setări (citită la afișare)."""
    if not STARE_PLACA_VIDEO.startswith("Placa video: încă"):
        return STARE_PLACA_VIDEO
    if os.environ.get("DTED_FORTEAZA_CPU") == "1":
        return "Placa video: nefolosită: procesorul a fost forțat pentru test."
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() <= 0:
            return "Placa video: nefolosită: nu am găsit o placă NVIDIA cu driver CUDA."
    except Exception as exc:
        return f"Placa video: nefolosită: {exc}"
    nume = nume_placa_video() or "NVIDIA"
    return f"Placa video: {nume} – găsită; se testează la prima transcriere."


def nume_placa_video() -> str:
    """Numele plăcii NVIDIA (din nvidia-smi), sau gol."""
    import shutil
    import subprocess

    executabil = shutil.which("nvidia-smi")
    if not executabil:
        return ""
    try:
        rezultat = subprocess.run(
            [executabil, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (rezultat.stdout or "").strip().splitlines()[0].strip() if rezultat.stdout else ""
    except Exception:
        return ""


pregateste_biblioteci_cuda()


class EroareMotor(RuntimeError):
    """Transcrierea nu poate rula; mesajul este scris pentru utilizator."""

    def __init__(self, mesaj: str, ce_fac: str = "", detalii: str = ""):
        super().__init__(mesaj)
        self.ce_fac = ce_fac
        self.detalii = detalii


class Anulat(Exception):
    """Transcrierea a fost oprită de utilizator."""


@dataclass
class Cuvant:
    """Un cuvânt cu timpii lui, pentru legarea textului de sunet."""

    start: float
    end: float
    text: str


@dataclass
class Segment:
    """O bucată de text cu timpii ei, folosită la subtitrări."""

    start: float
    end: float
    text: str
    cuvinte: list[Cuvant] = field(default_factory=list)


@dataclass
class Rezultat:
    """Rezultatul unei transcrieri."""

    text: str
    limba: str
    segmente: list[Segment] = field(default_factory=list)
    dispozitiv: str = "cpu"
    secunde_audio: float = 0.0
    secunde_calcul: float = 0.0

    @property
    def cuvinte(self) -> int:
        return len([cuvânt for cuvânt in self.text.split() if cuvânt])


@dataclass
class InformatiiAudio:
    """Ce s-a putut afla despre un fișier audio, înainte de transcriere."""

    ok: bool
    secunde: float = 0.0
    format: str = ""
    mesaj: str = ""
    ce_fac: str = ""


# --------------------------------------------------------------------------- ffmpeg


def pregateste_ffmpeg() -> str:
    """Pune ffmpeg-ul inclus în PATH, ca faster-whisper să poată citi orice format.

    ``imageio-ffmpeg`` aduce un binar static, fără instalare și fără drepturi
    de administrator, deci programul merge și pe calculatoarele pe care
    ffmpeg nu este instalat separat.
    """
    try:
        import imageio_ffmpeg

        executabil = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""
    folder = str(Path(executabil).parent)
    cale = os.environ.get("PATH", "")
    if folder not in cale.split(os.pathsep):
        os.environ["PATH"] = folder + os.pathsep + cale
    return executabil


def _ffmpeg_exe() -> str:
    """Calea către ffmpeg: cel inclus, apoi cel instalat în Windows."""
    executabil = pregateste_ffmpeg()
    if executabil:
        return executabil
    import shutil

    return shutil.which("ffmpeg") or ""


def biblioteci_disponibile() -> bool:
    """Adevărat dacă interpretorul curent poate importa faster-whisper și microfonul.

    Verificare ieftină, folosită de interfață la pornire: nu încarcă modelul.
    """
    try:
        import sounddevice  # noqa: F401
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        return False


def _decode_audio(cale: str):
    """Încarcă sunetul dintr-un fișier, ca tablou numpy mono la 16 kHz.

    Folosește faster-whisper pentru decodare audio (ffmpeg intern).
    """
    try:
        from faster_whisper.utils import decode_audio
    except Exception:
        from faster_whisper.audio import decode_audio

    pregateste_ffmpeg()
    try:
        return decode_audio(cale)
    except Exception as exc:
        # PyAV nou (>=15) nu mai acceptă metadata_errors din faster-whisper 1.2;
        # citim atunci cu ffmpeg-ul inclus, tot local.
        jurnal.atentionare(f"Decodarea prin PyAV a eșuat ({exc}); folosesc ffmpeg.")
        return _decode_cu_ffmpeg(cale)


def _decode_cu_ffmpeg(cale: str):
    """Sunetul ca numpy float32 mono 16 kHz, prin ffmpeg (fără fereastră de consolă)."""
    import subprocess

    import numpy as _np

    executabil = _ffmpeg_exe()
    if not executabil:
        raise RuntimeError("ffmpeg nu este disponibil")
    comanda = [executabil, "-nostdin", "-v", "error", "-i", str(cale),
               "-f", "s16le", "-ac", "1", "-ar", "16000", "-"]
    fara_fereastra = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    rezultat = subprocess.run(comanda, capture_output=True, check=True, creationflags=fara_fereastra)
    return _np.frombuffer(rezultat.stdout, _np.int16).astype(_np.float32) / 32768.0


def incarca_audio(cale: str | Path):
    """Sunetul dintr-un fișier, ca tablou numpy mono la 16 kHz.

    Se folosește la transcrierea pe bucăți: astfel textul apare pe rând în
    editor, bara de progres arată unde suntem, iar „Anulează” oprește imediat.
    """
    return MotorWhisper._incarca_audio(str(cale))


def informatii_audio(cale: str | Path) -> InformatiiAudio:
    """Verifică fișierul înainte de transcriere: format, durată, citire.

    Se face înainte, ca utilizatorul să afle din timp dacă fișierul nu poate
    fi folosit și cât durează aproximativ transcrierea.
    """
    from .constante import FORMATE_AUDIO

    fisier = Path(cale)
    if not fisier.exists():
        return InformatiiAudio(
            False,
            mesaj=f"Nu găsesc fișierul „{fisier.name}”.",
            ce_fac="Alege din nou fișierul audio, cu butonul «Alege fișierul audio».",
        )
    if fisier.suffix.lower() not in FORMATE_AUDIO:
        acceptate = ", ".join(sorted({f.lstrip('.').upper() for f in FORMATE_AUDIO}))
        return InformatiiAudio(
            False,
            mesaj=f"Fișierul „{fisier.name}” nu pare a fi un fișier audio.",
            ce_fac=f"Formatele acceptate sunt: {acceptate}. Alege un fișier cu una din aceste terminatii.",
        )

    executabil = _ffmpeg_exe()
    if executabil:
        try:
            # imageio_ffmpeg.read_frames cere un flux video și crapă la MP3/WAV;
            # citim durata din ce afișează ffmpeg („Duration: 00:00:18.79”).
            import re
            import subprocess

            fara_fereastra = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proba = subprocess.run(
                [executabil, "-nostdin", "-hide_banner", "-i", str(fisier)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                creationflags=fara_fereastra, timeout=30,
            )
            gasit = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proba.stderr or "")
            if not gasit or "Audio:" not in (proba.stderr or ""):
                raise RuntimeError("ffmpeg nu a găsit sunet în fișier")
            secunde = int(gasit.group(1)) * 3600 + int(gasit.group(2)) * 60 + float(gasit.group(3))
            if secunde > 0:
                return InformatiiAudio(True, secunde, fisier.suffix.lstrip(".").upper())
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut citi durata fișierului {fisier.name}: {exc}")
            return InformatiiAudio(
                False,
                mesaj=f"Fișierul „{fisier.name}” nu a putut fi deschis.",
                ce_fac=(
                    "Verifică dacă este unul din formatele acceptate (MP3, WAV, M4A, "
                    "OGG, FLAC) și dacă nu este deteriorat, apoi alege alt fișier."
                ),
                format=fisier.suffix.lstrip(".").upper(),
            )
    # Fără ffmpeg nu putem citi durata, dar putem încerca transcrierea.
    return InformatiiAudio(True, 0.0, fisier.suffix.lstrip(".").upper())


# --------------------------------------------------------------------------- motor


class MotorWhisper:
    """Încarcă modelul o singură dată și transcrie fișiere sau sunet din memorie."""

    def __init__(self, dispozitiv: str = "auto", model: str | None = None):
        self.dispozitiv_preferat = dispozitiv
        self.model_preferat = model or "auto"
        self._model = None
        self._dispozitiv = "cpu"
        self._blocare = threading.Lock()
        self._anulat = threading.Event()
        self._folosit = False

    # ------------------------------------------------------------------ stare

    @property
    def incarcat(self) -> bool:
        return self._model is not None

    @property
    def dispozitiv(self) -> str:
        """„cuda” sau „cpu”, după ce s-a încercat folosirea plăcii video."""
        return self._dispozitiv

    def anuleaza(self) -> None:
        """Cere oprirea transcrierii în curs (se oprește la următorul pas)."""
        self._anulat.set()

    def elibereaza(self) -> None:
        """Scoate modelul din memorie (folosit când calculatorul are puțină RAM)."""
        with self._blocare:
            self._model = None

    # ------------------------------------------------------------------ încărcare

    def _alege_dispozitiv(self) -> str:
        """Placa video, dacă există și funcționează; altfel procesorul.

        Cu faster-whisper nu mai avem nevoie de PyTorch pentru a verifica
        CUDA. Încercăm să încarcăm nvcuda.dll direct; dacă există, presumăm
        că placa video este disponibilă și faster-whisper o va folosi.
        """
        if os.environ.get("DTED_FORTEAZA_CPU") == "1":
            self._motiv_cpu = "procesorul a fost forțat pentru test (DTED_FORTEAZA_CPU=1)"
            return "cpu"
        if self.dispozitiv_preferat == "cpu":
            self._motiv_cpu = "în setări e ales doar procesorul"
            return "cpu"
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda"
            self._motiv_cpu = "nu am găsit o placă NVIDIA cu driver CUDA"
        except Exception as exc:
            self._motiv_cpu = f"CTranslate2 nu poate verifica placa video ({exc})"
        return "cpu"

    def _proba_placa_video(self) -> None:
        """Test real pe placa video: un encode scurt (aruncă dacă lipsesc cuBLAS/cuDNN)."""
        lungime = 30 * 16_000
        proba = np.zeros(lungime, dtype=np.float32)
        trasaturi = self._model.feature_extractor(proba)[:, :3000]
        self._model.encode(np.ascontiguousarray(trasaturi))

    def _noteaza_placa_video(self) -> None:
        global STARE_PLACA_VIDEO
        nume = nume_placa_video() or "NVIDIA"
        if self._dispozitiv == "cuda":
            STARE_PLACA_VIDEO = f"Placa video: {nume} – folosită (float16)."
        else:
            motiv = getattr(self, "_motiv_cpu", "") or "nu a putut fi folosită"
            STARE_PLACA_VIDEO = f"Placa video: nefolosită: {motiv}. Transcriu pe procesor (float32)."
        jurnal.info(STARE_PLACA_VIDEO)

    def incarca(self) -> None:
        """Încarcă modelul, dacă nu este deja în memorie."""
        if self._model is not None:
            return
        fisier = cai.fisier_model(getattr(self, "model_preferat", None))
        if not fisier.exists():
            raise EroareMotor(
                "Modelul de transcriere lipsește.",
                ce_fac=(
                    "Pornește din nou programul D&TED cu internetul deschis (sau rulează "
                    "din nou instalarea), ca să fie descărcat modelul."
                ),
            )
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise EroareMotor(
                "Părțile de transcriere nu sunt instalate.",
                ce_fac="Rulează din nou instalarea programului, apoi încearcă iar.",
                detalii=str(exc),
            ) from exc

        pregateste_ffmpeg()
        self._dispozitiv = self._alege_dispozitiv()
        jurnal.info(f"Încarc modelul {fisier.name} pe {self._dispozitiv}…")
        try:
            # compute_type: float16 pe GPU (fp16, rapid + puțin mem video),
            # float32 pe CPU (calitate maximă, fără pierderi de precizie).
            compute_type = "float16" if self._dispozitiv == "cuda" else "float32"
            self._model = WhisperModel(
                str(fisier),
                device=self._dispozitiv,
                compute_type=compute_type,
                cpu_threads=0,  # 0 = auto-detect
                num_workers=1,
            )
            if self._dispozitiv == "cuda":
                self._proba_placa_video()
        except Exception as exc:
            if self._dispozitiv == "cuda":
                jurnal.atentionare(
                    f"Placa video nu a putut fi folosită ({exc}); trec pe procesor."
                )
                self._motiv_cpu = f"testul pe placa video a eșuat ({str(exc)[:120]})"
                self._model = None
                self._dispozitiv = "cpu"
                try:
                    self._model = WhisperModel(
                        str(fisier),
                        device="cpu",
                        compute_type="float32",
                        cpu_threads=0,
                        num_workers=1,
                    )
                except Exception as exc2:
                    raise EroareMotor(
                        "Modelul de transcriere nu a putut fi încărcat.",
                        ce_fac=(
                            "Memoria calculatorului poate fi insuficientă. Închide "
                            "programele mari (browser, jocuri) și încearcă din nou."
                        ),
                        detalii=str(exc2),
                    ) from exc2
            else:
                raise EroareMotor(
                    "Modelul de transcriere nu a putut fi încărcat.",
                    ce_fac=(
                        "Memoria calculatorului poate fi insuficientă. Închide "
                        "programele mari (browser, jocuri) și încearcă din nou."
                    ),
                    detalii=str(exc),
                ) from exc
        jurnal.info(f"Model încărcat pe {self._dispozitiv}.")
        self._noteaza_placa_video()
        self._folosit = True

    # ------------------------------------------------------------------ transcriere

    def transcrie(
        self,
        sursa,
        limba: str = "ro",
        termeni: str = "",
        progres: Callable[[float], None] | None = None,
        faza: Callable[[str], None] | None = None,
    ) -> Rezultat:
        """Transcrie un fișier audio sau un tablou numpy mono float32.

        ``progres`` primește o fracțiune între 0 și 1, iar ``faza`` mesaje
        scurte, în română, pentru afișare.
        """
        if faza:
            faza("Pregătesc modelul de transcriere…")
        self.incarca()
        self._anulat.clear()

        # Româna e implicită și forțată pe „auto”/gol: fără detectare automată
        # (cerința 0). Alte limbi rămân doar ca opțiune avansată, în setări.
        limba_faster = limba if limba and limba != "auto" else "ro"
        if faza:
            faza("Transcriu…")
        start = time.time()
        try:
            segmente_rezultat, info = self._ruleaza(sursa, limba_faster, termeni, progres)
        except Anulat:
            raise
        except Exception as exc:
            if self._dispozitiv == "cuda":
                jurnal.atentionare(
                    f"Transcrierea pe placă video a eșuat ({exc}); reiau pe procesor."
                )
                self._dispozitiv = "cpu"
                self._model = None
                self.incarca()
                segmente_rezultat, info = self._ruleaza(sursa, limba_faster, termeni, progres)
            else:
                raise EroareMotor(
                    "Transcrierea nu a putut fi făcută.",
                    ce_fac=(
                        "Verifică dacă fișierul audio se aude corect, apoi apasă "
                        "«Transcrie» din nou. Dacă problema rămâne, încearcă alt fișier."
                    ),
                    detalii=str(exc),
                ) from exc
        durata = time.time() - start

        segmente = []
        for segment in segmente_rezultat:
            if self._anulat.is_set():
                raise Anulat()
            # Cuvintele cu timpi (cerinta 33: text legat de sunet).
            cuvinte_segment = []
            for _cuv in (getattr(segment, 'words', None) or []):
                cuvinte_segment.append(
                    Cuvant(
                        float(_cuv.start),
                        float(_cuv.end),
                        normalizeaza(str(_cuv.word).strip()),
                    )
                )
            segmente.append(
                Segment(
                    float(segment.start),
                    float(segment.end),
                    normalizeaza(str(segment.text).strip()),
                    cuvinte_segment,
                )
            )
        text = normalizeaza(" ".join(s.text for s in segmente).strip())

        secunde_audio = 0.0
        if segmente:
            secunde_audio = max(segment.end for segment in segmente)
        elif hasattr(sursa, "__len__") and not isinstance(sursa, (str, Path)):
            try:
                secunde_audio = len(sursa) / 16_000  # 16 kHz
            except TypeError:
                secunde_audio = 0.0

        if faza:
            faza("Gata.")
        if progres:
            try:
                progres(1.0)
            except Exception:
                pass
        return Rezultat(
            text=text,
            limba=str(getattr(info, "language", None) or limba or ""),
            segmente=segmente,
            dispozitiv=self._dispozitiv,
            secunde_audio=secunde_audio,
            secunde_calcul=durata,
        )

    def _ruleaza(
        self, sursa, limba, termeni: str, progres: Callable[[float], None] | None
    ):
        """Rulează faster-whisper, iterează segmentele și raportează progresul.

        faster-whisper returnează un generator de segmente și un obiect cu
        informații despre limba detectată etc. Iterează manual pentru progres,
        fără a avea nevoie de tqdm shim.
        """
        if isinstance(sursa, (str, Path)):
            audio = self._incarca_audio(str(sursa))
        else:
            audio = sursa

        # Estimăm numărul total de segmente pe durata audio (aprox. 1 segment
        # pe 3-4 secunde de vorbire), ca bara de progres să aibă o destinație.
        durata_secunde = 0.0
        if np is not None and isinstance(audio, np.ndarray):
            durata_secunde = len(audio) / 16000.0
        estimat_total = max(1, int(durata_secunde / 3.5))

        # faster-whisper returnează (iterator_de_segmente, info). Iterează
        # iteratorul manual pentru progres, fără a avea nevoie de tqdm shim.
        segmente_generator, info = self._model.transcribe(
            audio,
            language=limba,
            task="transcribe",
            vad_filter=True,  # detectează pausele în vorbire
            condition_on_previous_text=False,
            word_timestamps=True,  # cerința 33: text legat de sunet
            hotwords=termeni if termeni else None,  # cerinta 55: nume si termeni
            initial_prompt=prompt_romana(termeni) if limba == "ro" else None,
        )

        segmente = []
        facut = 0
        for segment in segmente_generator:
            if self._anulat.is_set():
                raise Anulat()
            segmente.append(segment)
            facut += 1
            if progres and facut % 3 == 0:
                try:
                    progres(min(1.0, facut / estimat_total))
                except Exception:
                    pass

        if progres:
            try:
                progres(1.0)
            except Exception:
                pass
        return segmente, info

    @staticmethod
    def _incarca_audio(cale: str):
        pregateste_ffmpeg()
        try:
            return _decode_audio(cale)
        except Exception as exc:
            nume = Path(cale).name
            raise EroareMotor(
                f"Fișierul „{nume}” nu a putut fi citit.",
                ce_fac=(
                    "Formatele acceptate sunt MP3, WAV, M4A, OGG și FLAC. "
                    "Verifică dacă fișierul nu este deteriorat sau protejat cu parolă."
                ),
                detalii=str(exc),
            ) from exc
