from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_git_repository_policy_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_git_repository_policy.py")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["state"] == "PASSED"
    assert payload["checks"]["runtime_retained_cli_dist_trackable"] is True
    assert payload["checks"]["durable_evidence_log_trackable"] is True
    assert payload["checks"]["local_environment_ignored"] is True
    assert payload["checks"]["environment_example_trackable"] is True
    assert payload["checks"]["product_artifact_package_trackable"] is True
    assert payload["checks"]["retained_upstream_vscode_trackable"] is True
    assert payload["checks"]["runtime_root_artifacts_ignored"] is True
    assert payload["checks"]["workspace_root_vscode_ignored"] is True


def test_repository_metadata_is_owned_at_workspace_root() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    runtime_ignore = (ROOT / "okcanvas-agent-runtime/.gitignore").read_text(encoding="utf-8")

    assert "* text=auto eol=lf" in attributes
    assert "sh_run_step086_acceptance.cmd text eol=crlf" in attributes
    assert "**/node_modules/" in ignore
    assert "!clients/cli/dist/**" in runtime_ignore
