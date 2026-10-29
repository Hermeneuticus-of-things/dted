from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release-update-manifest.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_release_manifest_workflow_uses_pull_request_not_direct_main_push():
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "gh pr create" in workflow
    assert "git push origin HEAD:main" not in workflow
    assert "pull-requests: write" in workflow


def test_manifest_pull_request_dispatches_required_ci_checks():
    release_workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "actions: write" in release_workflow
    assert "gh workflow run ci.yml" in release_workflow
    assert "on: [push, pull_request, workflow_dispatch]" in ci_workflow
    assert "name: Teste ${{ matrix.os }}" in ci_workflow
    assert "os: [windows-latest, ubuntu-latest]" in ci_workflow
