import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_release_contract.py"
FILES = (
    "README.md",
    "versiuni.json",
    "dted-bootstrap.ps1",
    "_build_kits.py",
    "dictare_transcriere_romana/constante.py",
    "dictare_transcriere_romana/actualizare.py",
    "instalator/setup.iss",
    "docs/ACTUALIZARI.md",
)


def _copy_contract_files(destination: Path) -> None:
    for relative in FILES:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    shutil.copytree(ROOT / "docs" / "img", destination / "docs" / "img")


def test_release_contract_accepts_current_repository():
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_release_contract_rejects_stale_readme_version(tmp_path):
    _copy_contract_files(tmp_path)
    readme_path = tmp_path / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    readme_path.write_text(
        readme.replace("Ce e nou în v0.6.11", "Ce e nou în v0.6.10", 1),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(CHECKER), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "must include a user-facing changelog" in result.stdout


def test_release_contract_rejects_out_of_order_readme_sections(tmp_path):
    _copy_contract_files(tmp_path)
    readme_path = tmp_path / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    readme = readme.replace("## Funcțiile, pe rând", "## TEMP", 1)
    readme = readme.replace("## Cum lucrăm împreună", "## Funcțiile, pe rând", 1)
    readme_path.write_text(readme.replace("## TEMP", "## Cum lucrăm împreună", 1), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(CHECKER), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "user-first order" in result.stdout
