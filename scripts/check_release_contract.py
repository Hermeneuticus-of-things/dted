#!/usr/bin/env python3
"""Check that release versions, stable update URLs, README and assets agree."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY = "Hermeneuticus-of-things/dted"
MANIFEST_URL = (
    "https://raw.githubusercontent.com/"
    f"{REPOSITORY}/main/versiuni.json"
)
PROGRAM_URL = (
    f"https://github.com/{REPOSITORY}/releases/latest/download/program.zip"
)
LATEST_RELEASE_URL = f"https://github.com/{REPOSITORY}/releases/latest"
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")
CHANGELOG_PATTERN = re.compile(r"^### 🆕 Ce e nou în v(\d+\.\d+\.\d+)\s*$", re.M)
IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
HTML_IMAGE_PATTERN = re.compile(r"<img\b[^>]*>", re.I)
HTML_SOURCE_PATTERN = re.compile(r"\bsrc=[\"']([^\"']+)[\"']", re.I)
HTML_ALT_PATTERN = re.compile(r"\balt=[\"']([^\"']*)[\"']", re.I)


def _read(path: Path, issues: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        issues.append(f"Cannot read {path.name}: {error}")
        return ""


def _version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def check_repository(root: Path) -> list[str]:
    issues: list[str] = []
    constants = _read(root / "dictare_transcriere_romana" / "constante.py", issues)
    setup = _read(root / "instalator" / "setup.iss", issues)
    readme = _read(root / "README.md", issues)
    bootstrap = _read(root / "dted-bootstrap.ps1", issues)
    update_docs = _read(root / "docs" / "ACTUALIZARI.md", issues)

    version_match = re.search(r'^VERSIUNE\s*=\s*"(\d+\.\d+\.\d+)"\s*$', constants, re.M)
    if not version_match:
        issues.append("Could not read the app version from constante.py.")
        return issues
    version = version_match.group(1)

    setup_values = {
        "MyAppVersion": version,
        "MyDistDir": rf"..\dist-v{version}\DTED",
        "OutputDir": rf"..\output-v{version}",
        "OutputBaseFilename": f"Setup.DTED-{version}",
    }
    for key, expected in setup_values.items():
        if key.startswith("My"):
            pattern = rf'^#define\s+{key}\s+"([^"\r\n]+)"\s*$'
        else:
            pattern = rf"^{key}\s*=\s*([^\r\n]+?)\s*$"
        match = re.search(pattern, setup, re.M)
        if not match or match.group(1) != expected:
            issues.append(f"instalator/setup.iss: {key} must match {expected}.")

    changelog_versions = CHANGELOG_PATTERN.findall(readme)
    if version not in changelog_versions:
        issues.append(f"README.md must include a user-facing changelog for v{version}.")
    if changelog_versions and max(changelog_versions, key=_version_key) != version:
        issues.append("README.md changelog is newer or older than the app version.")
    if not re.search(rf"D&amp;TED v{re.escape(version)}\b", readme):
        issues.append("README.md footer version does not match the app version.")
    required_section_order = (
        "## Ce este",
        "## Pentru cine",
        "## Ce face",
        "## ⚙️ Cum funcționează",
        "## 🎙 Cum lucrezi",
        "## Funcțiile, pe rând",
        "## Cum lucrăm împreună",
        "## Ce s-a făcut și ce urmează",
        "## ⬇️ Instalare",
        "### ❓ Întrebări frecvente",
        "### 🐞 Găsești o problemă?",
        "### ⚙️ Detalii tehnice",
    )
    section_positions = []
    for heading in required_section_order:
        if heading not in readme:
            issues.append(f"README.md is missing the required section: {heading}")
        else:
            section_positions.append(readme.index(heading))
    if section_positions != sorted(section_positions):
        issues.append("README.md sections must follow the documented user-first order.")

    if LATEST_RELEASE_URL not in readme or MANIFEST_URL not in update_docs:
        issues.append("README or update documentation is missing the stable download URLs.")
    if MANIFEST_URL not in constants:
        issues.append("The app manifest URL does not match the documented stable endpoint.")
    if PROGRAM_URL not in update_docs:
        issues.append("Update documentation is missing the stable program download URL.")
    if re.search(r"\b\d+\s+(?:de\s+)?teste automate\b", readme, re.I):
        issues.append("README.md must not hardcode a test count that can become stale.")
    if re.search(r"\b(?:PyAV|Tkinter|PyInstaller|SHA-256)\b", readme.split(
        f"### 🆕 Ce e nou în v{version}", 1
    )[-1].split("\n## ", 1)[0]):
        issues.append("The latest README changelog should describe user benefits, not build internals.")

    try:
        manifest = json.loads(_read(root / "versiuni.json", issues))
        program = manifest["program"]
        manifest_version = program["versiune"]
        if not VERSION_PATTERN.fullmatch(manifest_version):
            issues.append("versiuni.json contains an invalid program version.")
        elif _version_key(manifest_version) > _version_key(version):
            issues.append("The live manifest cannot point to a version newer than the app sources.")
        if program["url"] != PROGRAM_URL:
            issues.append("versiuni.json must use the stable releases/latest/download/program.zip URL.")
        if not re.fullmatch(r"[0-9a-f]{64}", program["sha256"]):
            issues.append("versiuni.json must contain a 64-character SHA-256 digest.")
        if not isinstance(program["dimensiune"], int) or program["dimensiune"] <= 0:
            issues.append("versiuni.json must contain a positive program archive size.")
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        issues.append(f"versiuni.json is invalid: {error}")

    if f'$ApiUrl = "https://api.github.com/repos/$Repo/releases/latest"' not in bootstrap:
        issues.append("The bootstrap must discover the current GitHub latest release dynamically.")
    if re.search(r"\bv\d+\.\d+\.\d+\b", bootstrap):
        issues.append("The bootstrap must not hardcode a release tag.")
    _check_readme_images(root, readme, issues)
    return issues


def _check_readme_images(root: Path, readme: str, issues: list[str]) -> None:
    sources = IMAGE_PATTERN.findall(readme)
    html_images = HTML_IMAGE_PATTERN.findall(readme)
    for tag in html_images:
        src = HTML_SOURCE_PATTERN.search(tag)
        alt = HTML_ALT_PATTERN.search(tag)
        if not alt or not alt.group(1).strip():
            issues.append(f"README image is missing useful alt text: {tag[:100]}")
        if src:
            sources.append(src.group(1))

    for source in dict.fromkeys(sources):
        if source.startswith(("http://", "https://", "data:", "#")):
            continue
        target = (root / source.split("#", 1)[0].split("?", 1)[0]).resolve()
        if not target.is_file():
            issues.append(f"README references a missing local image: {source}")
            continue
        if target.suffix.lower() != ".svg":
            continue
        try:
            svg = ET.parse(target).getroot()
        except ET.ParseError as error:
            issues.append(f"README SVG is invalid ({source}): {error}")
            continue
        tags = {node.tag.rsplit("}", 1)[-1] for node in svg.iter()}
        if "viewBox" not in svg.attrib:
            issues.append(f"README SVG is missing viewBox: {source}")
        if "title" not in tags:
            issues.append(f"README SVG is missing a title: {source}")
        if tags.intersection({"script", "foreignObject"}):
            issues.append(f"README SVG uses unsupported markup: {source}")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parents[1]
    issues = check_repository(root)
    if issues:
        print("Release contract failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Release contract OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
