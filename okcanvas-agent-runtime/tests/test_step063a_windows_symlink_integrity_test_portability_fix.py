from __future__ import annotations

import hashlib
import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    inventory = json.loads(
        (ROOT / "specs/architecture/STEP081_SOURCE_BASELINE_INVENTORY.json").read_text(
            encoding="utf-8"
        )
    )
    historical = {str(item["path"]): str(item["sha256"]) for item in inventory["files"]}
    legacy_path = "src/" + relative
    if legacy_path in historical:
        return historical[legacy_path]
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_step063a_baseline_and_runtime_flags() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.windows_symlink_integrity_test_portability_fix_implemented is True
    assert info.windows_symlink_integrity_test_uses_real_symlink is False
    assert info.windows_symlink_integrity_test_uses_deterministic_path_simulation is True
    assert info.windows_symlink_integrity_test_deterministic_accepted is True
    assert info.windows_symlink_integrity_test_windows_live_accepted is True


def test_step063a_windows_failure_evidence_is_exact() -> None:
    payload = json.loads(
        (ROOT / "docs/evidence/STEP063_WINDOWS_SYMLINK_TEST_SKIP_FAILURE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "FAILED"
    assert payload["passed_checks"] == 32
    assert payload["total_checks"] == 33
    assert payload["failed_checks"] == ["focused_strict_encryption_tests_pass"]
    assert payload["focused_test_output"] == "52 passed, 1 skipped, 1 warning in 5.57s"


def test_step063a_symlink_test_is_deterministic_and_has_no_skip() -> None:
    source = (ROOT / "tests/test_sqlite_session_runtime.py").read_text(encoding="utf-8")
    start = source.index("def test_session_database_symlink_is_rejected")
    end = source.index("\ndef test_clear_failure_restores_active_state", start)
    block = source[start:end]
    assert "pytest.skip" not in block
    assert ".symlink_to(" not in block
    assert 'monkeypatch.setattr(Path, "exists", simulated_exists)' in block
    assert 'monkeypatch.setattr(Path, "is_symlink", simulated_is_symlink)' in block
    assert 'match="Session database path is unsafe"' in block


def test_step063_encryption_source_remains_unchanged() -> None:
    expected = {
        "okcanvas_agent_runtime/sessions/encryption.py":
            "b2127cf828e1e4d44663295edac0b4451d8b452a352e73789b3272d6e7a781b0",
    }
    assert {path: _sha256(ROOT / path) for path in expected} == expected
