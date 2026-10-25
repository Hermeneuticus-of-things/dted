"""Valori fixe ale programului: nume, linkuri oficiale, sume, praguri.

Toate pragurile de resurse sunt derivate din cerințele oficiale ale modelului
Whisper large-v3-turbo (809 M parametri, checkpoint de ~1,6 GB) și din spațiul
necesar pentru Python, biblioteci, ffmpeg și LibreOffice.

Nimic din acest fișier nu depinde de calculatorul pe care rulează programul:
aici sunt doar valori publice, verificabile, fiecare cu sursa ei.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- aplicație

NUME_APLICATIE = "Dictare&Transcriere Română"  # nume tehnic vechi: căi, scurtături vechi, registru
NUME_FOLDER = NUME_APLICATIE          # folderul programului, în LOCALAPPDATA (NU se schimbă)

# Numele afișat (doar în interfață). Ierarhie: numele englezesc complet,
# forma scurtă, apoi subtitlul românesc, mai mic, dedesubt.
NUME_AFISAT = "Dictate & Transcription Express Digital"
NUME_SCURT = "D&TED"
SUBTITLU_RO = "Dictare și transcriere în limba română"
TITLU_FEREASTRA = f"{NUME_AFISAT} ({NUME_SCURT})"
#: Numele scurtăturilor (Desktop, meniul Start) și al executabilului (fără „&” în fișier).
NUME_SCURTATURA = f"{NUME_SCURT} – {NUME_AFISAT}"
NUME_EXE = "DTED"
NUME_PACHET = "dictare_transcriere_romana"  # numele tehnic (fără diacritice)
NUME_PUBLICATOR = "D&TED"
VERSIUNE = "0.5.2"
VERSIUNE_COMPLETA = f"{VERSIUNE}-beta (2026-10)"

#: Variabila de mediu care poate muta instalarea în alt folder.
VAR_MEDIU_FOLDER = "DICTARE_DIR"
#: Varianta veche a variabilei de mediu, păstrată pentru compatibilitate.
VAR_MEDIU_FOLDER_VECHI = "TRANSCRIERE_DIR"
#: Variabila de mediu care mută folderul de salvare a documentelor.
VAR_MEDIU_IESIRI = "DICTARE_IESIRI"

# --------------------------------------------------------------------------- Whisper (faster-whisper / CTranslate2)

#: Numele folderului cu modelul CTranslate2 (faster-whisper citește un folder,
#: nu un fișier .pt). Modelul este convertit din openai/whisper-large-v3-turbo.
WHISPER_NUME = "large-v3-turbo-ct2"

#: Modelul îmbunătățit pentru română (v0.1.2): Whisper large-v3-turbo
#: fine-tunat pe Common Voice 20 (41 431 de înregistrări românești),
#: WER 4,69% vs 20,72% la modelul de bază; licență CC-BY-NC-4.0.
#: Sursă: https://huggingface.co/TransferRapid/whisper-large-v3-turbo_ro
WHISPER_NUME_RO = "large-v3-turbo-ro-ct2"

#: Repository Hugging Face care găzduiește modelul CTranslate2 gata convertit.
WHISPER_CT2_REPO = "deepdml/faster-whisper-large-v3-turbo-ct2"

#: Modelul optimizat pentru română vorbită (v0.4.0): Whisper large-v3-turbo
#: fine-tunat de eek pe română conversațională; WER 5,8% vs 10,9% pentru
#: standard, măsurat pe mostre de carte; MIT; 788 MB.
#: Sursă: https://huggingface.co/eek/whisper-turbo-ro-en
WHISPER_NUME_EEK = "whisper-turbo-ro-en-ct2"

#: Modelele de transcriere cunoscute (folder → descriere pentru utilizator).
MODELE_TRANSCRIBERE = {
    WHISPER_NUME_EEK: "Optimizat pentru română (recomandat — WER 5,8%)",
    WHISPER_NUME: "Standard multilingv (cadou dacă schimbi limba)",
    WHISPER_NUME_RO: "Fine-tunat RO — doar clipuri scurte (taie textul lung)",
}

#: Fișierele care compun modelul CTranslate2 (descărcate la instalare).
WHISPER_CT2_FISIERE = (
    "config.json",
    "model.bin",
    "vocabulary.json",
    # Fără acestea, faster-whisper caută tokenizerul pe internet și folosește
    # 80 de benzi mel în loc de 128 (large-v3-turbo) → transcrierea crapă.
    "tokenizer.json",
    "preprocessor_config.json",
)

#: Dimensiunea aproximativă a model.bin (~1,5 GB), pentru verificarea spațiului.
WHISPER_BYTES = 1_617_884_929

# Cerințe derivate din model:
#  - modelul ocupă ~1,6 GB în memorie la precizie float16/float32;
#  - transcrierea pe procesor are nevoie de spațiu de lucru suplimentar;
#  - pe placa video NVIDIA cu CUDA, fp16 are nevoie de aproximativ 6 GB de memorie video.
WHISPER_MIN_RAM_GB = 8.0        # sub această valoare modelul nu are loc în memorie
WHISPER_RECOMANDAT_RAM_GB = 16.0
WHISPER_MIN_VRAM_MB = 6000
WHISPER_MIN_VRAM_GB = (WHISPER_MIN_VRAM_MB + 1023) // 1024

# --------------------------------------------------------------------------- LibreOffice

#: Versiunea stabilă folosită de program (The Document Foundation).
LIBREOFFICE_VERSIUNE = "26.8.1"
LIBREOFFICE_FOLDER = (
    "https://download.documentfoundation.org/libreoffice/stable/"
    f"{LIBREOFFICE_VERSIUNE}/win"
)

#: Numele fișierelor oficiale, pe arhitecturi. Sumele pentru x86_64 sunt
#: publicate în pagina „.mirrorlist” a fișierului și sunt scrise și aici.
#: Pentru celelalte arhitecturi suma este citită la instalare din chiar
#: pagina oficială „.mirrorlist” (sau din fișierul „.meta4”), înainte de a
#: folosi fișierul descărcat.
LIBREOFFICE_MSI = {
    "AMD64": {
        "folder": "x86_64",
        "nume": f"LibreOffice_{LIBREOFFICE_VERSIUNE}_Win_x86-64.msi",
        "sha256": "c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312",
        "bytes": 374_870_016,
    },
    "ARM64": {
        "folder": "aarch64",
        "nume": f"LibreOffice_{LIBREOFFICE_VERSIUNE}_Win_aarch64.msi",
        "sha256": "",  # citită din pagina oficială .mirrorlist
        "bytes": 0,
    },
    "x86": {
        "folder": "x86",
        "nume": f"LibreOffice_{LIBREOFFICE_VERSIUNE}_Win_x86.msi",
        "sha256": "",  # citită din pagina oficială .mirrorlist
        "bytes": 0,
    },
}

#: Pachetul de ajutor în limba română („helppack_ro”), pe arhitecturi.
LIBREOFFICE_AJUTOR_MSI = {
    "AMD64": {
        "folder": "x86_64",
        "nume": f"LibreOffice_{LIBREOFFICE_VERSIUNE}_Win_x86-64_helppack_ro.msi",
        "sha256": "beb3880a84399c6354b3065a0ac0e11468c0d2b3729781b7595feaecdc79964c",
        "bytes": 3_637_248,
    },
    "ARM64": {
        "folder": "aarch64",
        "nume": f"LibreOffice_{LIBREOFFICE_VERSIUNE}_Win_aarch64_helppack_ro.msi",
        "sha256": "",
        "bytes": 0,
    },
    "x86": {
        "folder": "x86",
        "nume": f"LibreOffice_{LIBREOFFICE_VERSIUNE}_Win_x86_helppack_ro.msi",
        "sha256": "",
        "bytes": 0,
    },
}

#: Limba cerută la instalarea LibreOffice (meniuri, dicționar, despărțire).
LIBREOFFICE_LIMBA = "ro"

#: Locale-ul complet, folosit pentru limba documentelor.
LIBREOFFICE_LOCALE = "ro-RO"

#: Fișierele care arată că instalarea are meniurile și dicționarul în română.
#: Pe Windows, instalatorul principal LibreOffice conține toate limbile de
#: meniu (nu există pachet separat de limbă); româna se alege la instalare.
LIBREOFFICE_FISIER_MENIU = f"Langpack-{LIBREOFFICE_LIMBA}.xcd"
LIBREOFFICE_FOLDER_MENIU = "share/registry"

#: Pachetul de dicționar românesc (despărțire în silabe și sinonime vin în el).
LIBREOFFICE_FOLDER_DICTIONAR = ("share/extensions/dict-ro", "share/dict/ooo", "share/dict")
LIBREOFFICE_FISIER_DICTIONAR = ("ro_RO.dic", "ro.dic")

# --------------------------------------------------------------------------- resurse

WINDOWS_BUILD_MINIM = 17763      # Windows 10 versiunea 1809
WINDOWS_BUILD_RECOMANDAT = 22000  # Windows 11
DISC_REZERVA_GB = 2.0            # rezervă pentru fișiere temporare și actualizări

#: Cât ocupă fiecare componentă, în GB (valori rotunjite în sus, în siguranță).
DIMENSIUNI_GB = {
    "model": 1.6,          # modelul Whisper large-v3-turbo (~1,51 GiB)
    "libreoffice": 1.8,    # pachetul MSI + instalarea + ajutorul în română
    "program": 1.4,        # mediul Python + biblioteci (pe procesor)
    "program_gpu": 3.4,    # bibliotecile CUDA, când există placă video
    "ffmpeg": 0.2,
    "rezerva": DISC_REZERVA_GB,
}

#: Pragurile afișate utilizatorului (rotunjite în sus, ca să nu aibă surprize).
#: Se calculează din DIMENSIUNI_GB, cu o marjă de siguranță pentru fișiere
#: temporare și pentru documentele care se adună în timp.
DISC_MINIM_GB = 8.0              # 1,6 + 1,8 + 1,4 + 0,2 + 2,0 = 7,0 → rotunjit la 8
DISC_MINIM_CU_GPU_GB = 10.0      # 1,6 + 1,8 + 3,4 + 0,2 + 2,0 = 9,0 → rotunjit la 10
DISC_RECOMANDAT_GB = 20.0        # loc pentru multe documente și pentru actualizări

# --------------------------------------------------------------------------- limbi

#: Perechi (etichetă în română, cod ISO 639-1 pentru Whisper).
LIMBI = [
    ("Română", "ro"),
    ("Engleză", "en"),
    ("Franceză", "fr"),
    ("Germană", "de"),
    ("Italiană", "it"),
    ("Spaniolă", "es"),
    ("Portugheză", "pt"),
    ("Olandeză", "nl"),
    ("Poloneză", "pl"),
    ("Rusă", "ru"),
    ("Ucraineană", "uk"),
    ("Turcă", "tr"),
    ("Maghiară", "hu"),
    ("Bulgară", "bg"),
    ("Greacă", "el"),
]

#: Prompt care ajută modelul să scrie diacriticele românești corect.
PROMPT_ROMANA = (
    "Aceasta este o transcriere în limba română, cu diacritice corecte: "
    "ă, â, î, ș, ț."
)


def prompt_romana(termeni: str = "") -> str:
    """Promptul de transcriere: diacritice + numele și termenii utilizatorului.

    ``termeni`` e un șir cu nume și termeni despărțiți prin virgulă (sau ``;``).
    faster-whisper nu acceptă hotwords separat, așa că termenii intră în
    ``initial_prompt`` — mecanismul recunoscut de orientare a vocabularului.
    """
    prompt = PROMPT_ROMANA
    if termeni:
        curat = [t.strip() for t in termeni.replace(";", ",").split(",") if t.strip()]
        if curat:
            prompt += f" Termeni și nume importante: {', '.join(curat)}."
    return prompt

# --------------------------------------------------------------------------- fișiere

#: Formatele audio acceptate la intrare.
FORMATE_AUDIO = (
    ".mp3", ".wav", ".m4a", ".ogg", ".flac",
    ".opus", ".webm", ".mp4", ".aac", ".wma",
)

#: Formatele în care se pot salva transcrierile.
#: (cheie, etichetă pentru buton, extensie, descriere pentru utilizator)
FORMATE_DOCUMENT = [
    ("docx", "DOCX (Word și LibreOffice)", ".docx", "Document obișnuit, merge peste tot."),
    ("odt", "ODT (LibreOffice Writer)", ".odt", "Documentul standard al LibreOffice."),
    ("txt", "TXT (text simplu)", ".txt", "Doar text, fără formatare."),
    ("rtf", "RTF (formatare simplă)", ".rtf", "Text cu fonturi, deschis de orice editor."),
    ("html", "HTML (pentru internet)", ".html", "Pagină care se poate deschide în browser."),
    ("srt", "SRT (subtitrări)", ".srt", "Subtitrări cu timpi, pentru filme."),
    ("vtt", "VTT (subtitrări web)", ".vtt", "Subtitrări pentru pagini web."),
    ("pdf", "PDF (se face cu LibreOffice)", ".pdf", "Document care nu se modifică ușor."),
]

# --------------------------------------------------------------------------- Python

#: Pachetul oficial de Python, în varianta portabilă: nu cere drepturi de
#: administrator, nu scrie nimic în registru și nu are instalator cu întrebări.
#: Sumele SHA-256 sunt publicate de python.org în fișierul
#: „windows-3.12.10.json”; programul îl citește la instalare și folosește
#: suma publicată, iar valorile de mai jos sunt aceleași sume, scrise în cod
#: ca rezervă (dacă lista nu poate fi citită).
PYTHON_VERSIUNE = "3.12.10"
PYTHON_FOLDER = f"https://www.python.org/ftp/python/{PYTHON_VERSIUNE}"
PYTHON_ARHIVA = {
    "AMD64": f"python-{PYTHON_VERSIUNE}-amd64.zip",
    "ARM64": f"python-{PYTHON_VERSIUNE}-arm64.zip",
    "x86": f"python-{PYTHON_VERSIUNE}-win32.zip",
}
PYTHON_SHA256 = {
    # valorile din windows-3.12.10.json (python.org), verificate
    "AMD64": "8649692de846c56a7189d6dae5c322ab20deb1b5908b6f39426b62a36f39415d",
    "ARM64": "20a5b1a707d899ffdfc5e3086d7372f7cc95eeea344d48ae256047cb7075cf63",
    "x86": "b665393cbead6570e9445d9178e30160581149de2b09f29c8230a28718324801",
}
#: Lista oficială de sume pentru toate arhivele de Windows.
PYTHON_JSON_SUME = f"{PYTHON_FOLDER}/windows-{PYTHON_VERSIUNE}.json"

#: Indexurile oficiale PyTorch (CPU și CUDA 13, necesar pentru GPU-urile recente).
#: Își mai țin placea, dar nu sunt necesare cu faster-whisper (CTranslate2).
TORCH_INDEX_CPU = "https://download.pytorch.org/whl/cpu"
TORCH_INDEX_CUDA = "https://download.pytorch.org/whl/cu130"

#: Manifestul actualizărilor pe componente (cerința 8 / N-2): aceeași formă ca
#: „versiuni.json” din folderul de instalare (versiune, dimensiune, adresă,
#: sumă SHA-256). Se citește DOAR la apăsarea butonului „Caută actualizări”.
URL_MANIFEST_ACTUALIZARI = (
    "https://raw.githubusercontent.com/Hermeneuticus-of-things/dted/main/versiuni.json"
)

#: Parola implicită a programului, scrisă și în Ajutor. Se precompletează la
#: punerea parolei; utilizatorul o poate schimba oricând cu a lui.
PAROLA_IMPLICITA = "Dictare"

#: Versiunea bibliotecii de transcriere (aceeași pe procesor și pe placă video).
#: Înlocuim torch + openai-whisper cu faster-whisper (CTranslate2), de câteva
#: ori mai rapid și mai ușor pe memoria video.
PACHET_FASTER_WHISPER = "faster-whisper==1.2.1"
# faster-whisper 1.2.1 încă pasează metadata_errors, eliminat în PyAV 18.
PACHET_PYAV = "av==17.1.0"

#: Pachetele programului, cu versiuni fixe (se instalează în mediul propriu,
#: nu în Windows). Versiunile au fost verificate că există oficial.
PACHETE = [
    PACHET_PYAV,
    "numpy==2.2.6",
    "sounddevice==0.5.2",
    "imageio-ffmpeg==0.6.0",
]
PACHET_FASTER_WHISPER_PIN = PACHET_FASTER_WHISPER

# --------------------------------------------------------------------------- diverse

#: Numele fișierelor pe care le creează programul lângă el.
NUME_CITESTE_MA = "Citește-mă.txt"
NUME_GHD_AJUTOR = "Ghid de folosire.txt"

#: Textul afișat pe ecranul principal despre internet.
MESAJ_FARA_INTERNET = "Programul funcționează fără internet."
