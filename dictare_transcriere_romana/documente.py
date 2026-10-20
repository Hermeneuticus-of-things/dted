"""Scrierea documentelor, fără dependențe externe.

Formatele sunt scrise direct cu biblioteca standard (ZIP + XML), ca programul
să rămână ușor și complet offline:

* **DOCX** — pachet ZIP cu XML Office Open XML;
* **ODT** — pachet ZIP cu XML OpenDocument (se deschide și în OpenOffice);
* **TXT, RTF, HTML** — text simplu, cu/fără formatare;
* **SRT, VTT** — subtitrări cu timpi, luate din segmentele transcrierii;
* **PDF** — se face cu LibreOffice (vezi ``libreoffice.converteste``).

Toate fișierele sunt scrise în UTF-8, marchează textul ca **română (ro-RO)**
și poartă numele programului în proprietățile lor.
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from .constante import TITLU_FEREASTRA as NUME_AFISARE  # doar numele afișat (căile nu se schimbă)
from .text_ro import (
    curata_xml,
    durata_text,
    normalizeaza,
    paragrafe,
    timp_subtitrare,
)

# --------------------------------------------------------------------------- ajutoare


def _titlu_xml(titlu: str) -> str:
    """Titlul, gata de pus în XML (semnul „&” devine „&amp;”)."""
    return escape(curata_xml(normalizeaza(titlu)))


def _text_xml(text: str) -> str:
    return escape(curata_xml(normalizeaza(text)))


def verifica_folder_scriere(folder: Path) -> tuple[bool, str]:
    """Verifică, înainte de salvare, dacă în folder se poate scrie."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        proba = folder / ".proba_salvare"
        proba.write_text("ok", encoding="utf-8")
        proba.unlink(missing_ok=True)
        return True, ""
    except OSError as exc:
        return False, str(exc)


def _segmente_pentru_subtitrare(segmente, text: str, secunde: float):
    """Segmentele transcrierii sau, dacă lipsesc, un singur bloc de text."""
    if segmente:
        return [(s.start, s.end, normalizeaza(s.text)) for s in segmente if normalizeaza(s.text)]
    curat = normalizeaza(text).strip()
    if not curat:
        return []
    return [(0.0, max(1.0, secunde), curat)]


# --------------------------------------------------------------------------- DOCX

_DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""

_DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""

_DOCX_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""

#: Stilurile documentului. Limba este română (ro-RO), ca LibreOffice să
#: verifice ortografia în română de la prima deschidere.
_DOCX_STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
        <w:sz w:val="24"/>
        <w:szCs w:val="24"/>
        <w:lang w:val="ro-RO" w:eastAsia="ro-RO" w:bidi="ar-SA"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="160" w:line="276" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:type="character" w:styleId="Subtitlu">
    <w:name w:val="Subtitle"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:i/></w:rPr>
  </w:style>
</w:styles>
"""


def _docx_document(lista: list[str], titlu: str, subtitlu: str = "") -> str:
    corp: list[str] = []
    limba = '<w:lang w:val="ro-RO"/>'
    if titlu:
        corp.append(
            "<w:p><w:pPr><w:pStyle w:val=\"Title\"/><w:spacing w:after=\"240\"/></w:pPr>"
            f'<w:r><w:rPr><w:b/><w:sz w:val="32"/>{limba}</w:rPr>'
            f'<w:t xml:space="preserve">{_titlu_xml(titlu)}</w:t></w:r></w:p>'
        )
    if subtitlu:
        corp.append(
            "<w:p><w:pPr><w:pStyle w:val=\"Subtitle\"/></w:pPr>"
            f'<w:r><w:rPr><w:i/>{limba}</w:rPr>'
            f'<w:t xml:space="preserve">{_titlu_xml(subtitlu)}</w:t></w:r></w:p>'
        )
    for paragraf in lista:
        if not paragraf:
            corp.append("<w:p/>")
            continue
        corp.append(
            f"<w:p><w:r><w:rPr>{limba}</w:rPr><w:t xml:space=\"preserve\">"
            f"{_text_xml(paragraf)}</w:t></w:r></w:p>"
        )
    if not corp:
        corp.append("<w:p/>")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<w:body>" + "".join(corp) +
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
        'w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )


def _docx_core(titlu: str, subiect: str = "") -> str:
    acum = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{_titlu_xml(titlu or 'Transcriere')}</dc:title>"
        f"<dc:subject>{_titlu_xml(subiect or NUME_AFISARE)}</dc:subject>"
        f"<dc:creator>{_titlu_xml(NUME_AFISARE)}</dc:creator>"
        f"<cp:lastModifiedBy>{_titlu_xml(NUME_AFISARE)}</cp:lastModifiedBy>"
        "<dc:language>ro-RO</dc:language>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{acum}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{acum}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _docx_app() -> str:
    """Proprietățile „aplicația care a creat documentul”."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        f"<Application>{_titlu_xml(NUME_AFISARE)}</Application>"
        f"<Company>{_titlu_xml(NUME_AFISARE)}</Company>"
        "<DocSecurity>0</DocSecurity>"
        "<ScaleCrop>false</ScaleCrop>"
        "<SharedDoc>false</SharedDoc>"
        "<HyperlinksChanged>false</HyperlinksChanged>"
        "<AppVersion>1.0</AppVersion>"
        "</Properties>"
    )


def scrie_docx(text: str, destinatie: Path, titlu: str = "", subtitlu: str = "") -> Path:
    """Scrie un fișier DOCX, cu un paragraf pentru fiecare rând."""
    destinatie = Path(destinatie).with_suffix(".docx")
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    lista = paragrafe(text)
    with zipfile.ZipFile(destinatie, "w", zipfile.ZIP_DEFLATED) as arhiva:
        arhiva.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        arhiva.writestr("_rels/.rels", _DOCX_RELS)
        arhiva.writestr("word/document.xml", _docx_document(lista, titlu, subtitlu))
        arhiva.writestr("word/styles.xml", _DOCX_STYLES)
        arhiva.writestr("word/_rels/document.xml.rels", _DOCX_DOCUMENT_RELS)
        arhiva.writestr("docProps/core.xml", _docx_core(titlu, subtitlu))
        arhiva.writestr("docProps/app.xml", _docx_app())
    return destinatie


# --------------------------------------------------------------------------- ODT

_ODT_MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="settings.xml" manifest:media-type="text/xml"/>
</manifest:manifest>
"""

_ODT_STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
    office:version="1.2">
  <office:styles>
    <style:default-style style:family="paragraph">
      <style:paragraph-properties fo:margin-bottom="0.25cm"/>
      <style:text-properties style:font-name="Liberation Serif" fo:font-size="12pt"
          fo:language="ro" fo:country="RO" style:language-asian="ro" style:country-asian="RO"/>
    </style:default-style>
    <style:style style:name="Standard" style:family="paragraph" style:class="text">
      <style:text-properties fo:language="ro" fo:country="RO"/>
    </style:style>
    <style:style style:name="Titlu" style:family="paragraph" style:parent-style-name="Standard">
      <style:text-properties fo:font-size="18pt" fo:font-weight="bold"
          fo:language="ro" fo:country="RO"/>
    </style:style>
    <style:style style:name="Subtitlu" style:family="paragraph" style:parent-style-name="Standard">
      <style:text-properties fo:font-size="12pt" fo:font-style="italic"
          fo:language="ro" fo:country="RO"/>
    </style:style>
  </office:styles>
  <office:automatic-styles>
    <style:page-layout style:name="pagina">
      <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm"
          fo:margin-top="2cm" fo:margin-bottom="2cm" fo:margin-left="2cm" fo:margin-right="2cm"/>
    </style:page-layout>
  </office:automatic-styles>
  <office:master-styles>
    <style:master-page style:name="Standard" style:page-layout-name="pagina"/>
  </office:master-styles>
</office:document-styles>
"""

_ODT_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-settings xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" office:version="1.2">
  <office:settings>
    <config:config-item-set config:name="ooo:view-settings">
      <config:config-item config:name="ViewAreaTop" config:type="int">0</config:config-item>
      <config:config-item config:name="ViewAreaLeft" config:type="int">0</config:config-item>
    </config:config-item-set>
  </office:settings>
</office:document-settings>
"""


def _odt_meta(titlu: str, subtitlu: str = "") -> str:
    acum = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" office:version="1.2">'
        "<office:meta>"
        f"<meta:generator>{_titlu_xml(NUME_AFISARE)}</meta:generator>"
        f"<dc:title>{_titlu_xml(titlu or 'Transcriere')}</dc:title>"
        f"<dc:subject>{_titlu_xml(subtitlu or NUME_AFISARE)}</dc:subject>"
        f"<dc:creator>{_titlu_xml(NUME_AFISARE)}</dc:creator>"
        f"<meta:initial-creator>{_titlu_xml(NUME_AFISARE)}</meta:initial-creator>"
        "<dc:language>ro-RO</dc:language>"
        f'<meta:creation-date>{acum}</meta:creation-date>'
        "</office:meta>"
        "</office:document-meta>"
    )


def _odt_content(lista: list[str], titlu: str, subtitlu: str = "") -> str:
    corp: list[str] = []
    if titlu:
        corp.append(
            f'<text:h text:style-name="Titlu" text:outline-level="1">{_titlu_xml(titlu)}</text:h>'
        )
    if subtitlu:
        corp.append(f'<text:p text:style-name="Subtitlu">{_titlu_xml(subtitlu)}</text:p>')
    for paragraf in lista:
        if not paragraf:
            corp.append("<text:p/>")
        else:
            corp.append(
                f'<text:p text:style-name="Standard">{_text_xml(paragraf)}</text:p>'
            )
    if not corp:
        corp.append("<text:p/>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2">'
        "<office:automatic-styles>"
        '<style:style style:name="Standard" style:family="paragraph" style:parent-style-name="Standard">'
        '<style:text-properties fo:language="ro" fo:country="RO"/>'
        "</style:style>"
        "</office:automatic-styles>"
        "<office:body><office:text>"
        + "".join(corp)
        + "</office:text></office:body></office:document-content>"
    )


def scrie_odt(text: str, destinatie: Path, titlu: str = "", subtitlu: str = "") -> Path:
    """Scrie un fișier ODT (se deschide în LibreOffice și în OpenOffice)."""
    destinatie = Path(destinatie).with_suffix(".odt")
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    lista = paragrafe(text)
    with zipfile.ZipFile(destinatie, "w", zipfile.ZIP_DEFLATED) as arhiva:
        # „mimetype” trebuie să fie primul în arhivă și necomprimat.
        arhiva.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/vnd.oasis.opendocument.text",
            compress_type=zipfile.ZIP_STORED,
        )
        arhiva.writestr("content.xml", _odt_content(lista, titlu, subtitlu))
        arhiva.writestr("styles.xml", _ODT_STYLES)
        arhiva.writestr("meta.xml", _odt_meta(titlu, subtitlu))
        arhiva.writestr("settings.xml", _ODT_SETTINGS)
        arhiva.writestr("META-INF/manifest.xml", _ODT_MANIFEST)
    return destinatie


# --------------------------------------------------------------------------- text simplu


def scrie_txt(text: str, destinatie: Path, titlu: str = "", subtitlu: str = "") -> Path:
    """Scrie un fișier text simplu, în UTF-8, cu diacritice corecte."""
    destinatie = Path(destinatie).with_suffix(".txt")
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    parti: list[str] = []
    if titlu:
        parti.append(normalizeaza(titlu))
        parti.append("=" * min(60, max(10, len(titlu))))
    if subtitlu:
        parti.append(normalizeaza(subtitlu))
    parti.extend(paragrafe(text))
    destinatie.write_text("\n".join(parti).strip() + "\n", encoding="utf-8")
    return destinatie


# --------------------------------------------------------------------------- RTF


def _rtf_text(text: str) -> str:
    """Text RTF: diacriticele devin secvențe ``\\uN?``, ca să nu se strice."""
    bucati: list[str] = []
    for caracter in normalizeaza(text):
        cod = ord(caracter)
        if caracter == "\\":
            bucati.append("\\\\")
        elif caracter == "{":
            bucati.append("\\{")
        elif caracter == "}":
            bucati.append("\\}")
        elif caracter == "\n":
            bucati.append("\\line ")
        elif cod < 128:
            bucati.append(caracter)
        else:
            semnat = cod if cod < 32768 else cod - 65536
            bucati.append(f"\\u{semnat}?")
    return "".join(bucati)


def scrie_rtf(text: str, destinatie: Path, titlu: str = "", subtitlu: str = "") -> Path:
    """Scrie un fișier RTF, care se deschide în orice editor de texte."""
    destinatie = Path(destinatie).with_suffix(".rtf")
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    parti = [
        r"{\rtf1\ansi\ansicpg1250\deff0",
        r"{\fonttbl{\f0\fnil\fcharset0 Calibri;}}",
        r"{\colortbl ;\red0\green0\blue0;}",
        r"\viewkind4\uc1\pard\f0\fs24 ",
    ]
    if titlu:
        parti.append(r"\b\fs32 " + _rtf_text(titlu) + r"\b0\fs24\par\par ")
    if subtitlu:
        parti.append(r"\i " + _rtf_text(subtitlu) + r"\i0\par\par ")
    for paragraf in paragrafe(text):
        parti.append(_rtf_text(paragraf) + r"\par ")
    parti.append("}")
    destinatie.write_text("".join(parti), encoding="utf-8")
    return destinatie


# --------------------------------------------------------------------------- HTML


def scrie_html(text: str, destinatie: Path, titlu: str = "", subtitlu: str = "") -> Path:
    """Scrie o pagină HTML simplă, cu textul transcris."""
    destinatie = Path(destinatie).with_suffix(".html")
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    corp = "\n".join(
        f"  <p>{_text_xml(paragraf)}</p>" if paragraf else "  <p>&nbsp;</p>"
        for paragraf in paragrafe(text)
    )
    titlu_pagina = _titlu_xml(titlu or "Transcriere")
    antet = f"  <h1>{titlu_pagina}</h1>\n" if titlu else ""
    sub = f"  <p class=\"subtitlu\">{_titlu_xml(subtitlu)}</p>\n" if subtitlu else ""
    pagina = (
        "<!DOCTYPE html>\n"
        '<html lang="ro">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{titlu_pagina}</title>\n"
        "<style>\n"
        "  body { font-family: Calibri, \"Segoe UI\", Arial, sans-serif; font-size: 12pt;\n"
        "         max-width: 45em; margin: 3em auto; padding: 0 1em; line-height: 1.5; }\n"
        "  h1 { font-size: 1.6em; }\n"
        "  .subtitlu { color: #555; margin-top: -0.6em; }\n"
        "  footer { margin-top: 3em; color: #777; font-size: 0.85em; }\n"
        "</style>\n</head>\n<body>\n"
        f"{antet}{sub}{corp}\n"
        f"  <footer>{_titlu_xml(NUME_AFISARE)}</footer>\n"
        "</body>\n</html>\n"
    )
    destinatie.write_text(pagina, encoding="utf-8")
    return destinatie


# --------------------------------------------------------------------------- subtitrări


def scrie_srt(
    segmente, text: str, destinatie: Path, secunde: float = 0.0, titlu: str = ""
) -> Path:
    """Scrie subtitrări în format SRT (pentru filme și playere obișnuite)."""
    destinatie = Path(destinatie).with_suffix(".srt")
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    blocuri: list[str] = []
    for index, (start, end, continut) in enumerate(
        _segmente_pentru_subtitrare(segmente, text, secunde), start=1
    ):
        blocuri.append(
            f"{index}\n{timp_subtitrare(start, ',')} --> {timp_subtitrare(end, ',')}\n{continut}\n"
        )
    destinatie.write_text("\n".join(blocuri).strip() + "\n", encoding="utf-8")
    return destinatie


def scrie_vtt(
    segmente, text: str, destinatie: Path, secunde: float = 0.0, titlu: str = ""
) -> Path:
    """Scrie subtitrări în format WebVTT (pentru pagini web)."""
    destinatie = Path(destinatie).with_suffix(".vtt")
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    parti = ["WEBVTT", ""]
    if titlu:
        parti.extend([f"NOTE {normalizeaza(titlu)}", ""])
    for index, (start, end, continut) in enumerate(
        _segmente_pentru_subtitrare(segmente, text, secunde), start=1
    ):
        parti.append(str(index))
        parti.append(f"{timp_subtitrare(start, '.')} --> {timp_subtitrare(end, '.')}")
        parti.append(continut)
        parti.append("")
    destinatie.write_text("\n".join(parti).strip() + "\n", encoding="utf-8")
    return destinatie


# --------------------------------------------------------------------------- dispecer


def extensie_potrivita(extensie: str) -> str:
    """Extensia curată, fără punct, în litere mici."""
    return (extensie or "").lower().lstrip(".")


def salveaza(
    text: str,
    destinatie: Path,
    titlu: str = "",
    subtitlu: str = "",
    segmente=None,
    secunde: float = 0.0,
) -> Path:
    """Salvează transcrierea în formatul cerut de extensia fișierului.

    Pentru PDF este nevoie de LibreOffice: fișierul se scrie întâi ca ODT,
    apoi se convertește (vezi ``libreoffice``).
    """
    extensie = extensie_potrivita(Path(destinatie).suffix)
    if extensie == "docx":
        return scrie_docx(text, destinatie, titlu, subtitlu)
    if extensie == "odt":
        return scrie_odt(text, destinatie, titlu, subtitlu)
    if extensie == "txt":
        return scrie_txt(text, destinatie, titlu, subtitlu)
    if extensie == "rtf":
        return scrie_rtf(text, destinatie, titlu, subtitlu)
    if extensie in ("html", "htm"):
        return scrie_html(text, destinatie, titlu, subtitlu)
    if extensie == "srt":
        return scrie_srt(segmente, text, destinatie, secunde, titlu)
    if extensie == "vtt":
        return scrie_vtt(segmente, text, destinatie, secunde, titlu)
    raise ValueError(
        f"Formatul „{extensie}” nu este acceptat. Formatele acceptate sunt: "
        "DOCX, ODT, TXT, RTF, HTML, SRT, VTT."
    )


def descriere_durata(rezultat) -> str:
    """Text scurt despre durata transcrierii, pentru interfață."""
    return (
        f"{durata_text(rezultat.secunde_calcul)} de calcul pentru "
        f"{durata_text(rezultat.secunde_audio)} de sunet"
    )


# --------------------------------------------------------------------------- citire înapoi


def _text_din_xml_docx(date: bytes) -> str:
    """Scoate textul din ``word/document.xml`` (paragrafele devin rânduri noi)."""
    import xml.etree.ElementTree as ET

    spatiu_w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    radacina = ET.fromstring(date)
    randuri: list[str] = []
    for paragraf in radacina.iter(f"{spatiu_w}p"):
        bucati: list[str] = []
        for nod in paragraf.iter():
            if nod.tag == f"{spatiu_w}t" and nod.text:
                bucati.append(nod.text)
            elif nod.tag == f"{spatiu_w}tab":
                bucati.append("\t")
            elif nod.tag == f"{spatiu_w}br":
                bucati.append("\n")
        randuri.append("".join(bucati))
    return "\n".join(randuri)


def _text_din_xml_odt(date: bytes) -> str:
    """Scoate textul din ``content.xml`` (paragrafele devin rânduri noi)."""
    import xml.etree.ElementTree as ET

    spatiu = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    radacina = ET.fromstring(date)
    randuri: list[str] = []

    def aduna(nod) -> str:
        bucati: list[str] = []
        if nod.text:
            bucati.append(nod.text)
        for copil in nod:
            if copil.tag == f"{spatiu}s":
                bucati.append(" " * max(1, int(copil.get(f"{spatiu}c", "1") or 1)))
            elif copil.tag == f"{spatiu}tab":
                bucati.append("\t")
            elif copil.tag == f"{spatiu}line-break":
                bucati.append("\n")
            elif copil.tag == f"{spatiu}p":
                bucati.append("\n" + aduna(copil) + "\n")
            else:
                bucati.append(aduna(copil))
            if copil.tail:
                bucati.append(copil.tail)
        return "".join(bucati)

    for paragraf in radacina.iter(f"{spatiu}p"):
        randuri.append(aduna(paragraf).strip())
    return "\n".join(randuri)


def _text_din_rtf(continut: str) -> str:
    """Scoate textul dintr-un RTF, cât se poate de simplu și de sigur."""
    iesire: list[str] = []
    i = 0
    sarit_grup = 0
    while i < len(continut):
        caracter = continut[i]
        if caracter == "\\":
            i += 1
            if i >= len(continut):
                break
            urmator = continut[i]
            if urmator in "\\{}":
                iesire.append(urmator)
                i += 1
                continue
            if urmator == "*":
                # grup ignorat (de exemplu fonturi, culori)
                i += 1
                continue
            if urmator == "'":
                cod = continut[i + 1 : i + 3]
                try:
                    iesire.append(bytes([int(cod, 16)]).decode("cp1252", "replace"))
                except ValueError:
                    pass
                i += 3
                continue
            j = i
            while j < len(continut) and (continut[j].isalpha()):
                j += 1
            cuvant = continut[i:j]
            argument = ""
            k = j
            if k < len(continut) and continut[k] == "-":
                k += 1
            while k < len(continut) and continut[k].isdigit():
                argument += continut[k]
                k += 1
            if cuvant == "par" or cuvant == "line":
                iesire.append("\n")
            elif cuvant == "tab":
                iesire.append("\t")
            elif cuvant == "u" and argument:
                try:
                    cod = int(argument)
                except ValueError:
                    cod = 63
                if cod < 0:
                    cod += 65536
                try:
                    iesire.append(chr(cod))
                except ValueError:
                    pass
            elif cuvant == "fonttbl" or cuvant == "colortbl" or cuvant == "stylesheet" or cuvant == "info":
                sarit_grup += 1
            if k < len(continut) and continut[k] == " ":
                k += 1
            i = k
            continue
        if caracter == "{":
            i += 1
            continue
        if caracter == "}":
            if sarit_grup:
                sarit_grup -= 1
            i += 1
            continue
        if sarit_grup == 0:
            iesire.append(caracter)
        i += 1
    text = "".join(iesire)
    text = curata_xml(normalizeaza(text))
    randuri = [rand.strip() for rand in text.split("\n")]
    return "\n".join(randuri).strip()


def _text_din_html(continut: str) -> str:
    """Scoate textul dintr-o pagină HTML, fără etichete."""
    import re
    from html import unescape

    fara_script = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", continut)
    cu_randuri = re.sub(r"(?is)<(br|/p|/div|/h[1-6]|/li|/tr)[^>]*>", "\n", fara_script)
    fara_etichete = re.sub(r"(?s)<[^>]+>", " ", cu_randuri)
    text = unescape(fara_etichete)
    randuri = [" ".join(rand.split()) for rand in text.split("\n")]
    return "\n".join(rand for rand in randuri).strip()


def citeste_text(cale: str | Path) -> str:
    """Citește textul unui document salvat de program (sau al unui text simplu).

    Este folosit când utilizatorul redeschide un document din „Fișierele mele”
    ca să-l continue în editorul integrat. Formatele citite sunt: DOCX, ODT,
    TXT, RTF, HTML, SRT, VTT și Markdown. Fișierul nu este modificat niciodată.
    """
    import re

    cale = Path(cale)
    extensie = extensie_potrivita(cale.suffix)
    if extensie in ("docx", "odt"):
        with zipfile.ZipFile(cale) as arhiva:
            nume = "word/document.xml" if extensie == "docx" else "content.xml"
            try:
                date = arhiva.read(nume)
            except KeyError:
                date = b""
        text = (
            _text_din_xml_docx(date)
            if extensie == "docx"
            else _text_din_xml_odt(date)
        )
        randuri = [rand.strip() for rand in text.split("\n")]
        # scoatem rândurile goale de la început și de la sfârșit
        while randuri and not randuri[0]:
            randuri.pop(0)
        while randuri and not randuri[-1]:
            randuri.pop()
        return normalizeaza("\n".join(randuri))
    if extensie == "rtf":
        return _text_din_rtf(cale.read_text(encoding="latin-1", errors="replace"))
    if extensie in ("html", "htm"):
        return _text_din_html(_citeste_text_adaptat(cale))
    if extensie in ("srt", "vtt"):
        continut = _citeste_text_adaptat(cale)
        randuri = []
        for rand in continut.splitlines():
            rand = rand.strip()
            if not rand or (rand.isdigit() and randuri and not randuri[-1]) or "-->" in rand:
                continue
            if rand == "WEBVTT":
                continue
            randuri.append(rand)
        return normalizeaza(" ".join(randuri))
    if extensie in ("md", "markdown"):
        continut = _citeste_text_adaptat(cale)
        continut = re.sub(r"^#{1,6}\s*", "", continut, flags=re.M)
        continut = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), continut)
        return normalizeaza(continut)
    return normalizeaza(_citeste_text_adaptat(cale))


def _citeste_text_adaptat(cale: Path) -> str:
    """Citește un fișier text încercând UTF-8, apoi codificările vechi Windows."""
    for codificare in ("utf-8-sig", "utf-8", "cp1250", "cp1252", "latin-1"):
        try:
            return cale.read_text(encoding=codificare)
        except UnicodeDecodeError:
            continue
        except OSError:
            raise
    return cale.read_text(encoding="utf-8", errors="replace")
