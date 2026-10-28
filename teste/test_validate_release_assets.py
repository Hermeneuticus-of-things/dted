import hashlib
import json
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

from scripts.validate_release_assets import validate_release_assets


VERSION = "0.6.11"
TAG = f"v{VERSION}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _create_package_zip(path: Path, extra_path: str | None = None) -> bytes:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("dictare_transcriere_romana/__init__.py", "")
        archive.writestr("dictare_transcriere_romana/app.py", "pass")
        if extra_path:
            archive.writestr(extra_path, "unexpected")
    return path.read_bytes()


def _create_linux_archive(path: Path, readme_name: str = "README.md") -> bytes:
    with tarfile.open(path, "w:gz") as archive:
        for name, content in (
            (readme_name, b"Linux instructions"),
            ("install.sh", b"#!/bin/sh\n"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, BytesIO(content))
    return path.read_bytes()


def _create_release(
    tmp_path: Path,
    linux_readme_name: str = "README.md",
    package_extra_path: str | None = None,
):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    package_zip = _create_package_zip(assets_dir / "program.zip", package_extra_path)
    (assets_dir / f"program-{VERSION}.zip").write_bytes(package_zip)
    (assets_dir / f"Setup.DTED-{VERSION}.exe").write_bytes(b"installer")
    (assets_dir / f"portabil-DTED-{VERSION}.zip").write_bytes(b"portable kit")
    _create_linux_archive(assets_dir / f"dted-{VERSION}-linux.tar.gz", linux_readme_name)

    checksummed_names = sorted(path.name for path in assets_dir.iterdir())
    sums = "".join(
        f"{_sha256((assets_dir / name).read_bytes())}  {name}\n"
        for name in checksummed_names
    )
    (assets_dir / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")
    assets = [
        {
            "name": path.name,
            "size": path.stat().st_size,
            "digest": f"sha256:{_sha256(path.read_bytes())}",
        }
        for path in assets_dir.iterdir()
    ]
    metadata = tmp_path / "release-assets.json"
    metadata.write_text(json.dumps(assets), encoding="utf-8")
    return assets_dir, metadata


def test_release_assets_accept_valid_release(tmp_path):
    assets_dir, metadata = _create_release(tmp_path)

    assert validate_release_assets(TAG, assets_dir, metadata) == []


def test_release_assets_reject_checksum_mismatch(tmp_path):
    assets_dir, metadata = _create_release(tmp_path)
    sums_path = assets_dir / "SHA256SUMS.txt"
    sums = sums_path.read_text(encoding="utf-8")
    lines = []
    for line in sums.splitlines():
        _, name = line.split(maxsplit=1)
        lines.append(f"{'0' * 64}  {name}" if name == "program.zip" else line)
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    issues = validate_release_assets(TAG, assets_dir, metadata)

    assert any("does not match GitHub" in issue for issue in issues)


def test_release_assets_reject_non_relative_linux_paths(tmp_path):
    assets_dir, metadata = _create_release(tmp_path, "C:/outside/README.md")

    issues = validate_release_assets(TAG, assets_dir, metadata)

    assert any("non-relative path" in issue for issue in issues)


def test_release_assets_reject_update_zip_path_traversal(tmp_path):
    assets_dir, metadata = _create_release(
        tmp_path,
        package_extra_path="dictare_transcriere_romana/../../outside.py",
    )

    issues = validate_release_assets(TAG, assets_dir, metadata)

    assert any("invalid path" in issue for issue in issues)
