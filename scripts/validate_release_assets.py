#!/usr/bin/env python3
"""Validate all checksums and required structures for a stable GitHub release."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath


CHECKSUM_PATTERN = re.compile(r"\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*")


def _read_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = CHECKSUM_PATTERN.fullmatch(line)
        if not match:
            raise ValueError(f"Invalid checksum entry: {line}")
        digest, name = match.groups()
        if name in checksums:
            raise ValueError(f"Duplicate checksum entry: {name}")
        checksums[name] = digest.lower()
    return checksums


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_release_assets(tag: str, directory: Path, metadata_path: Path) -> list[str]:
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag)
    if not match:
        return [f"Invalid stable release tag: {tag}"]
    version = match.group(1)
    issues: list[str] = []
    sums_path = directory / "SHA256SUMS.txt"
    if not sums_path.is_file():
        return ["Required release asset is missing: SHA256SUMS.txt"]

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assets = metadata if isinstance(metadata, list) else metadata["assets"]
        checksums = _read_checksums(sums_path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        return [f"Could not read release metadata or checksums: {error}"]

    if not isinstance(assets, list):
        return ["Release metadata does not contain an asset list."]

    asset_by_name: dict[str, dict] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            issues.append(f"Invalid release asset metadata: {asset!r}")
            continue
        name = asset.get("name")
        if not isinstance(name, str) or not name or Path(name).name != name or "\\" in name:
            issues.append(f"Invalid release asset name: {name!r}")
            continue
        if name in asset_by_name:
            issues.append(f"Duplicate release asset: {name}")
            continue
        asset_by_name[name] = asset

    required = {
        "SHA256SUMS.txt",
        f"Setup.DTED-{version}.exe",
        f"program-{version}.zip",
        "program.zip",
        f"portabil-DTED-{version}.zip",
        f"dted-{version}-linux.tar.gz",
    }
    missing = required - asset_by_name.keys()
    if missing:
        issues.append(f"Missing required release assets: {', '.join(sorted(missing))}")

    checksum_assets = set(asset_by_name) - {"SHA256SUMS.txt"}
    if checksum_assets != set(checksums):
        absent = checksum_assets - set(checksums)
        stale = set(checksums) - checksum_assets
        if absent:
            issues.append(f"SHA256SUMS.txt is missing: {', '.join(sorted(absent))}")
        if stale:
            issues.append(f"SHA256SUMS.txt references non-release assets: {', '.join(sorted(stale))}")

    for name in checksum_assets:
        asset = asset_by_name[name]
        digest = asset.get("digest")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            issues.append(f"GitHub has no SHA-256 digest for release asset: {name}")
        elif checksums.get(name) != digest.removeprefix("sha256:").lower():
            issues.append(f"SHA-256 in SHA256SUMS.txt does not match GitHub for {name}")
        size = asset.get("size")
        if not isinstance(size, int) or size <= 0:
            issues.append(f"GitHub reports an invalid size for release asset: {name}")

    for name in (
        "SHA256SUMS.txt",
        "program.zip",
        f"program-{version}.zip",
        f"dted-{version}-linux.tar.gz",
    ):
        asset = asset_by_name.get(name)
        path = directory / name
        if asset is None or not path.is_file():
            if asset is not None:
                issues.append(f"Downloaded release asset is missing: {name}")
            continue
        if path.stat().st_size != asset.get("size"):
            issues.append(f"Downloaded asset size differs from GitHub metadata: {name}")
        downloaded_digest = _sha256(path)
        metadata_digest = asset.get("digest")
        if (
            isinstance(metadata_digest, str)
            and metadata_digest.startswith("sha256:")
            and downloaded_digest != metadata_digest.removeprefix("sha256:").lower()
        ):
            issues.append(f"Downloaded asset checksum does not match GitHub metadata: {name}")
        if name != "SHA256SUMS.txt" and checksums.get(name) != downloaded_digest:
            issues.append(f"Downloaded asset checksum does not match SHA256SUMS.txt: {name}")

    stable = directory / "program.zip"
    versioned = directory / f"program-{version}.zip"
    if stable.is_file() and versioned.is_file():
        if stable.read_bytes() != versioned.read_bytes():
            issues.append("program.zip is not identical to the versioned program archive.")
        try:
            with zipfile.ZipFile(stable) as archive:
                names = archive.namelist()
                corrupt_member = archive.testzip()
            prefix = "dictare_transcriere_romana/"
            if not names or not names[0].startswith(prefix):
                issues.append("The first update ZIP entry must be inside the app package.")
            for name in names:
                posix_path = PurePosixPath(name)
                windows_path = PureWindowsPath(name)
                if (
                    not name.startswith(prefix)
                    or posix_path.is_absolute()
                    or windows_path.is_absolute()
                    or ".." in posix_path.parts
                ):
                    issues.append(f"The update ZIP contains an invalid path: {name}")
            if f"{prefix}__init__.py" not in names:
                issues.append("The update ZIP is missing the app package __init__.py.")
            if corrupt_member is not None:
                issues.append(f"The update ZIP has a corrupt member: {corrupt_member}")
        except (OSError, zipfile.BadZipFile) as error:
            issues.append(f"Update ZIP is invalid: {error}")

    linux_archive = directory / f"dted-{version}-linux.tar.gz"
    if linux_archive.is_file():
        try:
            with tarfile.open(linux_archive, "r:gz") as archive:
                names = archive.getnames()
            for name in names:
                posix_path = PurePosixPath(name)
                windows_path = PureWindowsPath(name)
                if (
                    posix_path.is_absolute()
                    or windows_path.is_absolute()
                    or ".." in posix_path.parts
                ):
                    issues.append(f"Linux archive contains a non-relative path: {name}")
            if "README.md" not in names:
                issues.append("Linux archive must contain README.md at its root.")
        except (OSError, tarfile.TarError) as error:
            issues.append(f"Linux archive is invalid: {error}")

    return issues


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3:
        print("Usage: validate_release_assets.py v<version> <release-dir> <asset-metadata.json>")
        return 2
    tag, directory, metadata = args
    issues = validate_release_assets(tag, Path(directory), Path(metadata))
    if issues:
        print("Release asset validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"Release assets validated for {tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
