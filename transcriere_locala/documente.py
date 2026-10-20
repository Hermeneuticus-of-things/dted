"""Scrierea documentelor DOCX și ODT fără dependențe externe.

DOCX este un pachet ZIP cu XML Office Open XML, iar ODT un pachet ZIP cu XML
OpenDocument. Ambele pot fi scrise cu biblioteca standard, ceea ce ține
programul ușor și complet offline.
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

# --------------------------------------------------------------------------- text


def _paragrafe(text: str) -> list[str]:
    """Împarte textul în paragrafe, păstrând rândurile goale."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text:
        return []
    return [linie.strip() for linie in text.split("\n")]


def _curata_xml(text: str) -> str:
    """Elimină caracterele de control care nu sunt permise în XML."""
    return "".join(
        ch for ch in text if ch in "\t\n\r" or (ord(ch) >= 32 and ord(ch) != 0x7F)
    )


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

_DOCX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
        <w:sz w:val="24"/>
        <w:szCs w:val="24"/>
        <w:lang w:val="ro-RO"/>
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
</w:styles>
"""


def _docx_document(paragrafe: list[str], titlu: str) -> str:
    corp: list[str] = []
    if titlu:
        corp.append(
            "<w:p><w:pPr><w:pStyle w:val=\"Title\"/><w:spacing w:after=\"240\"/></w:pPr>"
            f"<w:r><w:rPr><w:b/><w:sz w:val=\"32\"/></w:rPr><w:t xml:space=\"preserve\">{escape(_curata_xml(titlu))}</w:t></w:r></w:p>"
        )
    for paragraf in paragrafe:
        if not paragraf:
            corp.append("<w:p/>")
            continue
        corp.append(
            "<w:p><w:r><w:t xml:space=\"preserve\">"
            f"{escape(_curata_xml(paragraf))}"
            "</w:t></w:r></w:p>"
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


def _docx_core(titlu: str) -> str:
    acum = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(_curata_xml(titlu or 'Transcriere'))}</dc:title>"
        "<dc:creator>Transcriere locală</dc:creator>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{acum}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{acum}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _docx_app() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        "<Application>Transcriere locală</Application>"
        "</Properties>"
    )


def scrie_docx(text: str, destinatie: Path, titlu: str = "") -> Path:
    """Scrie un fișier DOCX simplu, cu un paragraf pentru fiecare rând."""
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    paragrafe = _paragrafe(text)
    with zipfile.ZipFile(destinatie, "w", zipfile.ZIP_DEFLATED) as arhiva:
        arhiva.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        arhiva.writestr("_rels/.rels", _DOCX_RELS)
        arhiva.writestr("word/document.xml", _docx_document(paragrafe, titlu))
        arhiva.writestr("word/styles.xml", _DOCX_STYLES)
        arhiva.writestr("word/_rels/document.xml.rels", _DOCX_DOCUMENT_RELS)
        arhiva.writestr("docProps/core.xml", _docx_core(titlu))
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
      <style:text-properties style:font-name="Liberation Serif" fo:font-size="12pt" fo:language="ro" fo:country="RO"/>
    </style:default-style>
    <style:style style:name="Standard" style:family="paragraph" style:class="text"/>
    <style:style style:name="Titlu" style:family="paragraph" style:parent-style-name="Standard">
      <style:text-properties fo:font-size="18pt" fo:font-weight="bold"/>
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

_ODT_META = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
    xmlns:dc="http://purl.org/dc/elements/1.1/" office:version="1.2">
  <office:meta>
    <meta:generator>Transcriere locală</meta:generator>
    <dc:creator>Transcriere locală</dc:creator>
  </office:meta>
</office:document-meta>
"""

_ODT_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-settings xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" office:version="1.2">
  <office:settings/>
</office:document-settings>
"""


def _odt_content(paragrafe: list[str], titlu: str) -> str:
    corp: list[str] = []
    if titlu:
        corp.append(
            f'<text:h text:style-name="Titlu" text:outline-level="1">{escape(_curata_xml(titlu))}</text:h>'
        )
    for paragraf in paragrafe:
        if not paragraf:
            corp.append("<text:p/>")
        else:
            corp.append(f'<text:p text:style-name="Standard">{escape(_curata_xml(paragraf))}</text:p>')
    if not corp:
        corp.append("<text:p/>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2">'
        "<office:automatic-styles>"
        '<style:style style:name="Standard" style:family="paragraph" style:parent-style-name="Standard"/>'
        "</office:automatic-styles>"
        "<office:body><office:text>"
        + "".join(corp)
        + "</office:text></office:body></office:document-content>"
    )


def scrie_odt(text: str, destinatie: Path, titlu: str = "") -> Path:
    """Scrie un fișier ODT simplu, cu un paragraf pentru fiecare rând."""
    destinatie.parent.mkdir(parents=True, exist_ok=True)
    paragrafe = _paragrafe(text)
    with zipfile.ZipFile(destinatie, "w", zipfile.ZIP_DEFLATED) as arhiva:
        # Fișierul "mimetype" trebuie să fie primul și necomprimat.
        arhiva.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/vnd.oasis.opendocument.text",
            compress_type=zipfile.ZIP_STORED,
        )
        arhiva.writestr("content.xml", _odt_content(paragrafe, titlu))
        arhiva.writestr("styles.xml", _ODT_STYLES)
        arhiva.writestr("meta.xml", _ODT_META)
        arhiva.writestr("settings.xml", _ODT_SETTINGS)
        arhiva.writestr("META-INF/manifest.xml", _ODT_MANIFEST)
    return destinatie


# --------------------------------------------------------------------------- nume fișiere


def nume_sigur(text: str, maxim: int = 60) -> str:
    """Transformă un text într-un nume de fișier valid pe Windows."""
    curatat = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", text).strip(" .")
    curatat = re.sub(r"\s+", " ", curatat)
    if not curatat:
        curatat = "Transcriere"
    return curatat[:maxim].strip(" .") or "Transcriere"


def nume_document(prefix: str = "Transcriere") -> str:
    """Nume implicit, cu data și ora, fără caractere interzise."""
    return f"{nume_sigur(prefix)}_{datetime.now().strftime('%Y-%m-%d_%H-%M')}"


def titlu_din_text(text: str, maxim: int = 70) -> str:
    """Prima propoziție, folosită ca titlu al documentului."""
    prima = ""
    for linie in text.splitlines():
        linie = linie.strip()
        if linie:
            prima = linie
            break
    if not prima:
        return ""
    potrivire = re.match(r"(.+?[.!?])(\s|$)", prima)
    titlu = potrivire.group(1) if potrivire else prima
    if len(titlu) > maxim:
        titlu = titlu[:maxim].rsplit(" ", 1)[0] + "…"
    return titlu
