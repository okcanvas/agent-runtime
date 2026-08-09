from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]
FOCUSED = ROOT / "tests/test_step064_bounded_encrypted_sqlite_session_compaction.py"
EXPECTED_RUNTIME_HASHES = {
    "okcanvas_agent_runtime/sessions/compaction.py": "0775e58c3ee126a6d5d4327960e57e75de56b82221f8f59216410387b0f23c2e",
    "okcanvas_agent_runtime/sessions/service.py": "aae6ea45004e66a55db3b30c6c547a27e8977f8b1e5da3b174efec426076ae14",
    "specs/runtime/sqlite-session-policy.json": "379e868d22b7b6c216fe2988d875846ed021f53cd8cb86f5630c399f68519d99",
    "okcanvas_agent_runtime/execution/service.py": "cc15da1d21b3ba1f0dd9a8e0fb10e3bf4335dc5d95427227e12146c10edeb7c1",
    "okcanvas_agent_runtime/tool_approval/service.py": "a289ce3fc90bf82b84308e5f220818519f8768648a3833c96bc2bbf2989991c8",
}


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


def test_step064a_runtime_info_and_baseline_are_exact() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.step064_async_test_portability_fix_implemented is True
    assert info.step064_focused_tests_require_pytest_asyncio is False
    assert info.step064_focused_tests_use_asyncio_run is True
    assert info.step064_focused_tests_plugin_independent_deterministic_accepted is True
    assert info.step064_focused_tests_windows_live_accepted is True


def test_step064_windows_failure_evidence_is_exact() -> None:
    payload = json.loads(
        (ROOT / "docs/evidence/STEP064_WINDOWS_PYTEST_ASYNC_PLUGIN_FAILURE_SUMMARY.json")
        .read_text(encoding="utf-8")
    )
    assert payload["state"] == "FAILED"
    assert payload["passed_checks"] == 28
    assert payload["total_checks"] == 29
    assert payload["failed_checks"] == ["focused_compaction_tests_pass"]
    assert payload["focused_test_output"] == "7 failed, 4 passed, 7 warnings in 1.90s"
    diagnosis = payload["diagnosis"]
    assert diagnosis["pytest_asyncio_declared_dependency"] is False
    assert diagnosis["async_test_count"] == 7
    assert diagnosis["synchronous_test_count"] == 4
    assert diagnosis["warning_count"] == 7


def test_step064_focused_tests_use_standard_library_asyncio_runner_only() -> None:
    source = FOCUSED.read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    requirements = (ROOT / "requirements-direct.txt").read_text(encoding="utf-8").lower()
    assert "pytest.mark.asyncio" not in source
    assert "pytest_asyncio" not in source
    assert source.count("@_async_test") == 7
    assert "return asyncio.run(function(*args, **kwargs))" in source
    assert "@wraps(function)" in source
    assert "pytest-asyncio" not in pyproject
    assert "pytest_asyncio" not in pyproject
    assert "pytest-asyncio" not in requirements
    assert "pytest_asyncio" not in requirements


def test_step064_product_runtime_and_policy_sources_are_unchanged() -> None:
    actual = {path: _sha256(ROOT / path) for path in EXPECTED_RUNTIME_HASHES}
    assert actual == EXPECTED_RUNTIME_HASHES


def test_step064_focused_tests_pass_without_plugin_autoload() -> None:
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            str(FOCUSED.relative_to(ROOT)),
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert "11 passed" in completed.stdout
    assert "failed" not in completed.stdout.lower()
    assert "skipped" not in completed.stdout.lower()
    assert "warning" not in completed.stdout.lower()
