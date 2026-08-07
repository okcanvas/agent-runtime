from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from scripts.node_acceptance import run_command, run_node_tests, validate_committed_typescript_release

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP063A_ACCEPTANCE.json"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    failure = _load_json(
        ROOT / "docs/evidence/STEP063_WINDOWS_SYMLINK_TEST_SKIP_FAILURE_SUMMARY.json"
    )
    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(
        encoding="utf-8"
    )
    test_source = (ROOT / "tests/test_sqlite_session_runtime.py").read_text(encoding="utf-8")
    start = test_source.index("def test_session_database_symlink_is_rejected")
    end = test_source.index("\ndef test_clear_failure_restores_active_state", start)
    symlink_test_block = test_source[start:end]

    with tempfile.TemporaryDirectory(prefix="okcanvas-step063a-") as temp_dir:
        predecessor_output = Path(temp_dir) / "step063.json"
        predecessor_ok, predecessor_console = run_command(
            [
                sys.executable,
                "scripts/run_step063_acceptance.py",
                "--output",
                str(predecessor_output),
            ],
            ROOT,
        )
        predecessor = _load_json(predecessor_output) if predecessor_output.is_file() else {}

    symlink_ok, symlink_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_sqlite_session_runtime.py::test_session_database_symlink_is_rejected",
        ],
        ROOT,
    )
    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step063a_windows_symlink_integrity_test_portability_fix.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "src",
            "scripts/run_step063_acceptance.py",
            "scripts/run_step063a_acceptance.py",
        ],
        ROOT,
    )
    release_ok, release_output = validate_committed_typescript_release(
        ROOT / "clients/cli"
    )
    node_ok, node_output = run_node_tests(ROOT / "clients/cli")
    no_reference_imports_ok, no_reference_imports_output = run_command(
        [sys.executable, "scripts/verify_no_reference_imports.py"], ROOT
    )
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    unchanged_runtime_hashes = {
        "okcanvas_agent_runtime/sessions/encryption.py": "b2127cf828e1e4d44663295edac0b4451d8b452a352e73789b3272d6e7a781b0",
        "okcanvas_agent_runtime/sessions/service.py": "9315367f067d3ebbba31a5babd37aca7159c37c7f6839c5f8dd7417e30bd9e9c",
        "okcanvas_agent_runtime/sessions/policy.py": "6c488cb3200c9b2f94f0428e7f37684857d500ae0d5bd4ce169e4da75475208d",
        "specs/runtime/sqlite-session-policy.json": "bde341bbe78d35511695554a8932a34d449e4f2b1316fcc0ea28f2986298a48d",
    }
    actual_runtime_hashes = {
        path: _sha256(ROOT / path) for path in unchanged_runtime_hashes
    }

    required_docs = [
        ROOT / "docs/plans/STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX.md",
        ROOT
        / "docs/reference/STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP063_WINDOWS_SYMLINK_TEST_SKIP_FAILURE_SUMMARY.json",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    ]
    docs_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in [ROOT / "HANDOFF.md", ROOT / "PLANS.md", ROOT / "docs/plans/ROADMAP.md"]
    )

    checks = {
        "baseline_version_and_step_exact": (
            info.version == "2.43.1"
            and info.step == "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"
            and 'PROJECT_VERSION = "2.43.1"' in baseline_source
            and 'CURRENT_STEP = "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"'
            in baseline_source
        ),
        "step063_windows_failure_evidence_exact": (
            failure.get("state") == "FAILED"
            and failure.get("passed_checks") == 32
            and failure.get("total_checks") == 33
            and failure.get("failed_checks") == ["focused_strict_encryption_tests_pass"]
            and failure.get("focused_test_output")
            == "52 passed, 1 skipped, 1 warning in 5.57s"
        ),
        "step063_product_runtime_sources_unchanged": (
            actual_runtime_hashes == unchanged_runtime_hashes
        ),
        "step063a_runtime_flags_exact": (
            info.windows_symlink_integrity_test_portability_fix_implemented is True
            and info.windows_symlink_integrity_test_uses_real_symlink is False
            and info.windows_symlink_integrity_test_uses_deterministic_path_simulation is True
            and info.windows_symlink_integrity_test_deterministic_accepted is True
            and info.windows_symlink_integrity_test_windows_live_accepted is False
        ),
        "symlink_test_has_no_environment_skip": (
            "pytest.skip" not in symlink_test_block
            and "Symlink creation is unavailable" not in symlink_test_block
        ),
        "symlink_test_does_not_create_real_symlink": ".symlink_to(" not in symlink_test_block,
        "symlink_test_simulates_exact_filesystem_observations": all(
            marker in symlink_test_block
            for marker in (
                'monkeypatch.setattr(Path, "exists", simulated_exists)',
                'monkeypatch.setattr(Path, "is_symlink", simulated_is_symlink)',
                "if path == history_db:",
            )
        ),
        "symlink_test_asserts_exact_runtime_rejection": (
            'match="Session database path is unsafe"' in symlink_test_block
            and 'runtime.raw_sdk_session("session_" + "a" * 32)' in symlink_test_block
        ),
        "corrected_step063_acceptance_pass": (
            predecessor_ok
            and predecessor.get("state") == "PASSED"
            and predecessor.get("passed_checks") == 33
            and predecessor.get("total_checks") == 33
        ),
        "corrected_step063_focused_tests_have_no_skip": (
            predecessor.get("focused_test_output", "").startswith("53 passed")
            and "skipped" not in predecessor.get("focused_test_output", "")
        ),
        "focused_symlink_test_pass": symlink_ok and "1 passed" in symlink_output,
        "focused_step063a_tests_pass": focused_ok and "4 passed" in focused_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok and "VERIFIED" in release_output,
        "node_tests_pass": node_ok and "# pass 14" in node_output,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step063a_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launchers_present": (
            (ROOT / "sh_run_step063_acceptance.cmd").is_file()
            and (ROOT / "sh_run_step063a_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step063a_acceptance.py").is_file()
        ),
        "step064_not_selected": "STEP064_" not in docs_text,
    }

    payload = {
        "schema_version": "okcanvas-step063a-acceptance-v1",
        "step": "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX",
        "version": "2.43.1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "corrected_step063_state": predecessor.get("state"),
        "corrected_step063_passed_checks": predecessor.get("passed_checks"),
        "corrected_step063_total_checks": predecessor.get("total_checks"),
        "corrected_step063_focused_test_output": predecessor.get("focused_test_output"),
        "focused_symlink_test_output": symlink_output.splitlines()[-1] if symlink_output else "",
        "focused_step063a_test_output": focused_output.splitlines()[-1] if focused_output else "",
        "python_compile_output": compile_output.splitlines()[-1] if compile_output else "",
        "node_release_output": release_output.splitlines()[-1] if release_output else "",
        "node_test_output_tail": node_output.splitlines()[-1] if node_output else "",
        "reference_import_output_tail": no_reference_imports_output.splitlines()[-1]
        if no_reference_imports_output
        else "",
        "predecessor_console_tail": predecessor_console.splitlines()[-1]
        if predecessor_console
        else "",
        "runtime_hashes": actual_runtime_hashes,
        "reference_count": len(reference_results),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
