"""Folderele programului, numele fișierelor și copiile de siguranță (punctul 5).

Toate fișierele utilizatorului stau într-un singur loc ușor de găsit, în
„Documente”, iar numele sunt legate între ele: o dictare numită
„Dictare 2026-10-19 10-35” are și sunetul (``.wav``), și textul (``.txt``), și
documentul final (``.docx``), toate cu același nume.

Nimic aici nu presupune o cale fixă: folderul de bază se cere de la Windows
(„Documente” adevărat, chiar mutat în OneDrive) sau din setările programului.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import cai, jurnal, sisteme, text_ro

#: Subfolderele din folderul programului.
FOLDER_AUDIO = "Audio"
FOLDER_TEXT = "Text transcris"
FOLDER_DOCUMENTE = "Documente finale"
FOLDER_TERMINATE = "Terminate"
SUBFOLDERE = (FOLDER_AUDIO, FOLDER_TEXT, FOLDER_DOCUMENTE, FOLDER_TERMINATE)

#: Numele folosite când programul nu poate scrie în „Documente”.
SUFIX_CADERE = " - nesalvat"


@dataclass
class Element:
    """Un fișier din folderele programului, așa cum îl vede utilizatorul."""

    cale: Path
    nume: str
    data: dt.datetime | None = None
    detalii: str = ""
    fel: str = ""                 # „audio”, „text” sau „document”
    marca: str = ""               # numele comun, fără extensie (pentru legături)

    @property
    def exista(self) -> bool:
        return self.cale.exists()


# --------------------------------------------------------------------------- foldere


def radacina(config=None) -> Path:
    """Folderul de bază al documentelor („Dictare&Transcriere Română”)."""
    if config is not None and getattr(config, "director_iesiri", ""):
        return Path(config.director_iesiri)
    return cai.director_iesiri()


def asigura(radacina_aleasa: Path | None = None) -> dict[str, Path]:
    """Creează folderele programului și întoarce căile lor."""
    baza = Path(radacina_aleasa) if radacina_aleasa else radacina()
    foldere: dict[str, Path] = {}
    for nume in SUBFOLDERE:
        folder = baza / nume
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            jurnal.atentionare(f"Nu am putut crea folderul {folder}: {exc}")
        foldere[nume] = folder
    return foldere


def folder(fel: str, radacina_aleasa: Path | None = None) -> Path:
    """Folderul unui anumit fel de fișiere („audio”, „text”, „documente”)."""
    perechi = {
        "audio": FOLDER_AUDIO,
        "text": FOLDER_TEXT,
        "document": FOLDER_DOCUMENTE,
        "documente": FOLDER_DOCUMENTE,
        "terminate": FOLDER_TERMINATE,
    }
    nume = perechi.get(fel, FOLDER_AUDIO)
    baza = Path(radacina_aleasa) if radacina_aleasa else radacina()
    cale = baza / nume
    try:
        cale.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return cale


def verificare_folder(cale: Path) -> tuple[bool, str]:
    """Spune dacă se poate scrie într-un folder, cu mesaj simplu."""
    try:
        cale.mkdir(parents=True, exist_ok=True)
        proba = cale / ".proba_de_scriere"
        proba.write_text("proba", encoding="utf-8")
        proba.unlink(missing_ok=True)
        return True, ""
    except OSError as exc:
        return False, str(exc)


# --------------------------------------------------------------------------- nume


def nume_unic(folder_destinatie: Path, nume: str) -> Path:
    """Alege un nume care nu există încă („raport.txt”, apoi „raport (2).txt”)."""
    folder_destinatie = Path(folder_destinatie)
    nume = text_ro.nume_sigur(nume) or "document"
    propus = folder_destinatie / nume
    if not propus.exists():
        return propus
    trunchi = propus.stem
    terminatie = propus.suffix
    numar = 2
    while numar < 1000:
        altul = folder_destinatie / f"{trunchi} ({numar}){terminatie}"
        if not altul.exists():
            return altul
        numar += 1
    return propus


def nume_legat(marca: str, extensie: str) -> str:
    """Numele unui fișier legat de altele, toate cu aceeași marcă de timp."""
    marca = text_ro.nume_sigur(marca) or text_ro.marca_timp()
    if extensie and not extensie.startswith("."):
        extensie = "." + extensie
    return f"{marca}{extensie}"


def marca_acum() -> str:
    """Marcă de timp pentru o dictare nouă: „Dictare 2026-10-19 10-35”."""
    return f"Dictare {text_ro.marca_timp()}"


def marca_din_nume(cale: Path) -> str:
    """Numele comun, fără extensie (folosit ca legătură între fișiere)."""
    return Path(cale).stem


# --------------------------------------------------------------------------- scriere


def copiaza_audio(sursa: Path, radacina_aleasa: Path | None = None) -> Path:
    """Copiază sunetul în folderul „Audio”, păstrându-i numele.

    Fișierele cu același nume primesc „(2)”, „(3)”, ca nimic să nu se
    suprascrie. Fișierul original al utilizatorului nu se atinge niciodată.
    """
    sursa = Path(sursa)
    destinatie = nume_unic(folder("audio", radacina_aleasa), sursa.name)
    try:
        shutil.copy2(sursa, destinatie)
        jurnal.info(f"Sunet copiat în {destinatie}")
        return destinatie
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut copia sunetul în {destinatie}: {exc}")
        return sursa


def scrie_text(text: str, marca: str, radacina_aleasa: Path | None = None) -> Path:
    """Scrie textul transcris („Text transcris/….txt”)."""
    cale = nume_unic(folder("text", radacina_aleasa), nume_legat(marca, ".txt"))
    try:
        cale.write_text(text, encoding="utf-8", newline="\r\n")
        jurnal.info(f"Text salvat în {cale}")
        return cale
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut salva textul în {cale}: {exc}")
        return cale


def scrie_text_legat(text: str, marca: str, radacina_aleasa: Path | None = None) -> Path:
    """Scrie (sau rescrie) textul din „Text transcris”, la aceeași marcă de timp.

    Se folosește la salvarea automată: la fiecare 30 de secunde textul este
    pus în același fișier, nu într-o grămadă de fișiere cu „(2)”, „(3)”.
    """
    cale = folder("text", radacina_aleasa) / nume_legat(marca, ".txt")
    try:
        cale.write_text(text, encoding="utf-8", newline="\r\n")
        return cale
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut salva textul în {cale}: {exc}")
        return cale


def scrie_audio(pcm, marca: str, radacina_aleasa: Path | None = None) -> Path | None:
    """Scrie o dictare în folderul „Audio” (fișier ``.wav``, 16 kHz mono)."""
    try:
        import wave

        import numpy as np  # type: ignore[import-not-found]

        cale = nume_unic(folder("audio", radacina_aleasa), nume_legat(marca, ".wav"))
        date = np.asarray(pcm, dtype="float32")
        if date.ndim > 1:
            date = date.mean(axis=1)
        bucati = np.clip(date, -1.0, 1.0)
        intregi = (bucati * 32767.0).astype("<i2")
        with wave.open(str(cale), "wb") as fisier:
            fisier.setnchannels(1)
            fisier.setsampwidth(2)
            fisier.setframerate(16000)
            fisier.writeframes(intregi.tobytes())
        jurnal.info(f"Sunet salvat în {cale}")
        return cale
    except Exception as exc:
        jurnal.atentionare(f"Nu am putut salva sunetul: {exc}")
        return None


def citeste(cale: Path) -> str:
    """Citește un fișier text al programului (fără să strice diacriticele)."""
    try:
        return Path(cale).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut citi {cale}: {exc}")
        return ""


# --------------------------------------------------------------------------- liste


def _detalii_audio(cale: Path) -> str:
    """Durata unui fișier audio, dacă se poate afla repede."""
    try:
        from . import motor

        informatii = motor.informatii_audio(cale)
        if informatii.ok and informatii.secunde > 0:
            return text_ro.durata_text(informatii.secunde)
        return ""
    except Exception:
        return ""


def _dimensiune(cale: Path) -> str:
    try:
        marime = cale.stat().st_size
    except OSError:
        return ""
    if marime < 1024:
        return f"{marime} octeți"
    if marime < 1024 * 1024:
        return f"{max(1, round(marime / 1024))} KB"
    return f"{marime / (1024 * 1024):.1f} MB"


def element(cale: Path, fel: str = "") -> Element:
    """Descrie un fișier: nume, dată, mărime sau durată."""
    cale = Path(cale)
    data: dt.datetime | None = None
    try:
        data = dt.datetime.fromtimestamp(cale.stat().st_mtime)
    except OSError:
        data = None
    if not fel:
        extensie = cale.suffix.lower()
        if extensie in (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".opus", ".webm", ".mp4", ".aac", ".wma"):
            fel = "audio"
        elif extensie == ".txt":
            fel = "text"
        else:
            fel = "document"
    detalii = _detalii_audio(cale) if fel == "audio" else _dimensiune(cale)
    return Element(cale=cale, nume=cale.name, data=data, detalii=detalii, fel=fel,
                   marca=cale.stem)


def listeaza(fel: str, radacina_aleasa: Path | None = None, maxim: int = 200) -> list[Element]:
    """Fișierele dintr-un folder al programului, cele mai noi primele."""
    cale = folder(fel, radacina_aleasa)
    elemente: list[Element] = []
    try:
        fisiere = [f for f in cale.iterdir() if f.is_file()]
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut citi folderul {cale}: {exc}")
        return []
    for fisier in fisiere:
        try:
            elemente.append(element(fisier, "audio" if fel == "audio" else ""))
        except Exception as exc:
            jurnal.atentionare(f"Nu am putut citi informațiile pentru {fisier}: {exc}")
    elemente.sort(key=lambda item: item.data or dt.datetime.min, reverse=True)
    return elemente[:maxim]


def ultimele_documente(maxim: int = 5, radacina_aleasa: Path | None = None) -> list[Element]:
    """Ultimele documente finalizate (pentru ecranul de început)."""
    elemente = listeaza("document", radacina_aleasa, maxim=maxim)
    if len(elemente) < maxim:
        elemente += listeaza("text", radacina_aleasa, maxim=maxim - len(elemente))
    elemente.sort(key=lambda item: item.data or dt.datetime.min, reverse=True)
    return elemente[:maxim]


def text_pentru_audio(cale_audio: Path, radacina_aleasa: Path | None = None) -> Path | None:
    """Textul legat de un sunet („Dictare ….wav” → „Dictare ….txt”)."""
    marca = marca_din_nume(cale_audio)
    for candidat in (
        folder("text", radacina_aleasa) / f"{marca}.txt",
        Path(cale_audio).with_suffix(".txt"),
    ):
        if candidat.exists():
            return candidat
    return None


def document_pentru(marca: str, radacina_aleasa: Path | None = None) -> Path | None:
    """Documentul final legat de o marcă (DOCX sau ODT)."""
    for extensie in (".docx", ".odt", ".pdf", ".rtf"):
        candidat = folder("documente", radacina_aleasa) / f"{marca}{extensie}"
        if candidat.exists():
            return candidat
    candidat = folder("documente", radacina_aleasa) / f"{marca}.txt"
    return candidat if candidat.exists() else None


# --------------------------------------------------------------------------- schimbare nume / ștergere


def redenumeste(cale: Path, nume_nou: str) -> tuple[Path | None, str]:
    """Redenumește un fișier al programului (numele vechi nu se pierde)."""
    cale = Path(cale)
    if not cale.exists():
        return None, "Fișierul nu mai există."
    nume_curat = text_ro.nume_sigur(nume_nou)
    if not nume_curat:
        return None, "Numele nu poate fi gol."
    if Path(nume_curat).suffix.lower() != cale.suffix.lower():
        nume_curat = nume_curat + cale.suffix
    tinta = cale.with_name(nume_curat)
    if tinta.exists() and tinta != cale:
        return None, (
            f"Există deja un fișier cu numele „{nume_curat}”. Alege alt nume "
            "sau lasă numele care era."
        )
    try:
        cale.rename(tinta)
        jurnal.info(f"Redenumit: {cale.name} → {tinta.name}")
        return tinta, ""
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut redenumi {cale}: {exc}")
        return None, "Numele nu a putut fi schimbat. Încearcă din nou."


def la_gunoi(cale: Path) -> tuple[bool, str]:
    """Trimite un fișier la Coșul de reciclare (niciodată șters definitiv)."""
    cale = Path(cale)
    if not cale.exists():
        return False, "Fișierul nu mai există."
    if sisteme.muta_la_gunoi(cale):
        return True, ""
    return False, (
        "Windows nu a putut muta fișierul la Coșul de reciclare. "
        "Îl poți șterge singur din folder, dacă vrei."
    )


def muta_la_terminate(cale: Path, radacina_aleasa: Path | None = None) -> tuple[bool, str]:
    """Mută un fișier terminat în arhiva „Terminate" (nu se șterge).

    Fișierele terminate se arhivează în folderul „Terminate", ca să nu mai stea
    printre cele în lucru, dar fără să se șteargă definitiv (cerința 41).
    """
    cale = Path(cale)
    if not cale.exists():
        return False, "Fișierul nu mai există."
    arhiva = folder("terminate", radacina_aleasa)
    try:
        destinatie = nume_unic(arhiva, cale.name)
    except OSError as exc:
        return False, f"Nu am putut crea arhiva „Terminate”: {exc}"
    try:
        shutil.move(str(cale), str(destinatie))
        jurnal.info(f"Arhivat: {cale.name} → {destinatie.name}")
        return True, ""
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut arhiva {cale}: {exc}")
        return False, "Fișierul nu a putut fi mutat în arhiva „Terminate”."


# --------------------------------------------------------------------------- copie de siguranță


def _folder_recuperare() -> Path:
    cale = cai.director_recuperare()
    try:
        cale.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return cale


def fisier_recuperare_text() -> Path:
    return _folder_recuperare() / "text_nesalvat.txt"


def fisier_recuperare_info() -> Path:
    return _folder_recuperare() / "text_nesalvat.json"


def scrie_recuperare(text: str, marca: str = "", detalii: str = "") -> bool:
    """Păstrează o copie de siguranță a textului de pe ecran."""
    try:
        fisier_recuperare_text().write_text(text, encoding="utf-8", newline="\r\n")
        fisier_recuperare_info().write_text(
            json.dumps(
                {
                    "marca": marca,
                    "detalii": detalii,
                    "salvat": dt.datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return True
    except OSError as exc:
        jurnal.atentionare(f"Nu am putut scrie copia de siguranță: {exc}")
        return False


def citeste_recuperare() -> tuple[str, str, str] | None:
    """Citește copia de siguranță, dacă există și are text.

    Întoarce ``(text, marca, momentul)`` sau ``None``.
    """
    cale = fisier_recuperare_text()
    if not cale.exists():
        return None
    text = citeste(cale)
    if not text.strip():
        return None
    marca = ""
    moment = ""
    try:
        date = json.loads(fisier_recuperare_info().read_text(encoding="utf-8"))
        marca = str(date.get("marca", ""))
        moment = str(date.get("salvat", ""))
    except (OSError, json.JSONDecodeError):
        pass
    return text, marca, moment


def sterge_recuperare() -> None:
    """Șterge copia de siguranță (după ce textul a fost salvat de adevărat)."""
    for cale in (fisier_recuperare_text(), fisier_recuperare_info()):
        try:
            cale.unlink(missing_ok=True)
        except OSError:
            pass


def ora_salvarii(scris_la: dt.datetime | None = None) -> str:
    """Textul afișat lângă editor: „Salvat automat la 10:42”."""
    moment = scris_la or dt.datetime.now()
    return moment.strftime("%H:%M")

def copiaza_siguranta_zip(cale_text: Path, destinatie: Path | None = None) -> tuple[Path | None, str]:
    """Creeaza o copie de siguranta ZIP a unui fisier de text (cerinta 59).

    Arhiva contine fisierul de text sub numele lui original, astfel incat
    sa poata fi recuperat oricand. Returneaza (calea arhivei, mesaj).
    """
    import zipfile
    cale_text = Path(cale_text)
    if not cale_text.exists():
        return None, "Fisierul nu mai exista."
    if destinatie is None:
        destinatie = cale_text.with_suffix(cale_text.suffix + ".zip")
    destinatie = Path(destinatie)
    try:
        with zipfile.ZipFile(destinatie, "w", zipfile.ZIP_DEFLATED) as arhiva:
            arhiva.write(cale_text, cale_text.name)
        return destinatie, ""
    except (OSError, zipfile.BadZipFile) as exc:
        return None, f"Copia de siguranta nu a putut fi creata: {exc}"
