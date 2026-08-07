from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP064A_ACCEPTANCE.json"
EXPECTED_RUNTIME_HASHES = {
    "okcanvas_agent_runtime/sessions/compaction.py": "0775e58c3ee126a6d5d4327960e57e75de56b82221f8f59216410387b0f23c2e",
    "okcanvas_agent_runtime/sessions/service.py": "0906f3ef39dec46b19ac611f384312e4545baa0759e124b41aca283164bda7ad",
    "specs/runtime/sqlite-session-policy.json": "379e868d22b7b6c216fe2988d875846ed021f53cd8cb86f5630c399f68519d99",
    "okcanvas_agent_runtime/execution/service.py": "f1c7c0f2d0b96a06f0732ab691e7fb8a258f814cb9ed49f26c1ded764c56dec9",
    "okcanvas_agent_runtime/tool_approval/service.py": "a289ce3fc90bf82b84308e5f220818519f8768648a3833c96bc2bbf2989991c8",
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_without_plugin_autoload(command: list[str]) -> tuple[bool, str]:
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return completed.returncode == 0, completed.stdout.decode("utf-8", errors="replace").strip()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    failure = _load_json(ROOT / "docs/evidence/STEP064_WINDOWS_PYTEST_ASYNC_PLUGIN_FAILURE_SUMMARY.json")
    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    focused_source = (
        ROOT / "tests/test_step064_bounded_encrypted_sqlite_session_compaction.py"
    ).read_text(encoding="utf-8")
    pyproject_source = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    requirements_source = (ROOT / "requirements-direct.txt").read_text(encoding="utf-8").lower()

    with tempfile.TemporaryDirectory(prefix="okcanvas-step064a-") as temp_dir:
        predecessor_output = Path(temp_dir) / "step064.json"
        predecessor_ok, predecessor_console = run_command(
            [
                sys.executable,
                "scripts/run_step064_acceptance.py",
                "--output",
                str(predecessor_output),
            ],
            ROOT,
        )
        predecessor = _load_json(predecessor_output) if predecessor_output.is_file() else {}

    plugin_independent_ok, plugin_independent_output = _run_without_plugin_autoload(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step064_bounded_encrypted_sqlite_session_compaction.py",
        ]
    )
    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step064a_pytest_async_plugin_independence_fix.py",
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
            "scripts/run_step064_acceptance.py",
            "scripts/run_step064a_acceptance.py",
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

    actual_runtime_hashes = {
        path: _sha256(ROOT / path) for path in EXPECTED_RUNTIME_HASHES
    }
    required_docs = [
        ROOT / "docs/plans/STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX.md",
        ROOT / "docs/reference/STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP064_WINDOWS_PYTEST_ASYNC_PLUGIN_FAILURE_SUMMARY.json",
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
            info.version == "2.44.1"
            and info.step == "STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX"
            and 'PROJECT_VERSION = "2.44.1"' in baseline_source
            and 'CURRENT_STEP = "STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX"'
            in baseline_source
        ),
        "step064_windows_failure_evidence_exact": (
            failure.get("state") == "FAILED"
            and failure.get("passed_checks") == 28
            and failure.get("total_checks") == 29
            and failure.get("failed_checks") == ["focused_compaction_tests_pass"]
            and failure.get("focused_test_output")
            == "7 failed, 4 passed, 7 warnings in 1.90s"
            and failure.get("diagnosis", {}).get("async_test_count") == 7
            and failure.get("diagnosis", {}).get("warning_count") == 7
        ),
        "step064_product_runtime_sources_unchanged": (
            actual_runtime_hashes == EXPECTED_RUNTIME_HASHES
        ),
        "step064a_runtime_flags_exact": (
            info.step064_async_test_portability_fix_implemented is True
            and info.step064_focused_tests_require_pytest_asyncio is False
            and info.step064_focused_tests_use_asyncio_run is True
            and info.step064_focused_tests_plugin_independent_deterministic_accepted is True
            and info.step064_focused_tests_windows_live_accepted is False
        ),
        "pytest_asyncio_is_not_declared_dependency": (
            "pytest-asyncio" not in pyproject_source
            and "pytest_asyncio" not in pyproject_source
            and "pytest-asyncio" not in requirements_source
            and "pytest_asyncio" not in requirements_source
        ),
        "focused_tests_have_no_pytest_asyncio_marker": (
            "pytest.mark.asyncio" not in focused_source
            and "pytest_asyncio" not in focused_source
        ),
        "focused_tests_use_standard_library_asyncio_run": (
            focused_source.count("@_async_test") == 7
            and "return asyncio.run(function(*args, **kwargs))" in focused_source
            and "@wraps(function)" in focused_source
        ),
        "plugin_autoload_disabled_focused_tests_pass": (
            plugin_independent_ok
            and "11 passed" in plugin_independent_output
            and "failed" not in plugin_independent_output.lower()
            and "skipped" not in plugin_independent_output.lower()
            and "warning" not in plugin_independent_output.lower()
        ),
        "corrected_step064_acceptance_pass": (
            predecessor_ok
            and predecessor.get("state") == "PASSED"
            and predecessor.get("passed_checks") == 29
            and predecessor.get("total_checks") == 29
        ),
        "corrected_step064_focused_tests_pass": (
            predecessor.get("focused_test_output", "").startswith("11 passed")
            and "failed" not in predecessor.get("focused_test_output", "").lower()
            and "skipped" not in predecessor.get("focused_test_output", "").lower()
        ),
        "focused_step064a_tests_pass": focused_ok and "5 passed" in focused_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok and "VERIFIED" in release_output,
        "node_tests_pass": node_ok and "# pass 14" in node_output,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step064a_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launchers_present": (
            (ROOT / "sh_run_step064_acceptance.cmd").is_file()
            and (ROOT / "sh_run_step064a_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step064a_acceptance.py").is_file()
        ),
        "step065_not_selected": "STEP065_" not in docs_text,
    }

    payload = {
        "schema_version": "okcanvas-step064a-acceptance-v1",
        "step": "STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX",
        "version": "2.44.1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "corrected_step064_state": predecessor.get("state"),
        "corrected_step064_passed_checks": predecessor.get("passed_checks"),
        "corrected_step064_total_checks": predecessor.get("total_checks"),
        "corrected_step064_focused_test_output": predecessor.get("focused_test_output"),
        "plugin_independent_test_output": plugin_independent_output.splitlines()[-1]
        if plugin_independent_output
        else "",
        "focused_step064a_test_output": focused_output.splitlines()[-1]
        if focused_output
        else "",
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
