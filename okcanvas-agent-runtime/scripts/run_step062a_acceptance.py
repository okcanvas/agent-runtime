from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from scripts.node_acceptance import (
    node_test_command,
    npm_script_command,
    run_command,
    run_node_tests,
    validate_committed_typescript_release,
)

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP062A_ACCEPTANCE.json"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def run(output: Path) -> int:
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    cli_root = ROOT / "clients" / "cli"
    package = _load_json(cli_root / "package.json")
    failure = _load_json(
        ROOT / "docs/evidence/STEP062_WINDOWS_NODE_ACCEPTANCE_FAILURE_SUMMARY.json"
    )
    helper_source = (ROOT / "scripts/node_acceptance.py").read_text(encoding="utf-8")
    step062_source = (ROOT / "scripts/run_step062_acceptance.py").read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="okcanvas-step062a-") as temp_dir:
        predecessor_output = Path(temp_dir) / "step062.json"
        predecessor_ok, predecessor_console = run_command(
            [
                sys.executable,
                "scripts/run_step062_acceptance.py",
                "--output",
                str(predecessor_output),
            ],
            ROOT,
        )
        predecessor = _load_json(predecessor_output) if predecessor_output.is_file() else {}

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step062a_windows_node_acceptance_portability_fix.py",
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
            "scripts/node_acceptance.py",
            "scripts/run_step062_acceptance.py",
            "scripts/run_step062a_acceptance.py",
        ],
        ROOT,
    )
    node_build_ok, node_build_output = validate_committed_typescript_release(cli_root)
    node_test_ok, node_test_output = run_node_tests(cli_root)

    windows_command = npm_script_command(
        r"C:\Program Files\nodejs\npm.cmd",
        "build",
        platform_name="nt",
        comspec=r"C:\Windows\System32\cmd.exe",
    )
    explicit_test_command = node_test_command("node", cli_root)

    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    required_docs = [
        ROOT / "docs/plans/STEP062A_WINDOWS_NODE_ACCEPTANCE_PORTABILITY_FIX.md",
        ROOT / "docs/evidence/STEP062_WINDOWS_NODE_ACCEPTANCE_FAILURE_SUMMARY.json",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    ]
    checks = {
        "baseline_version_and_step_exact": (
            info.version == "2.43.1"
            and info.step == "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"
        ),
        "step062_failure_evidence_exact": (
            failure.get("state") == "FAILED"
            and failure.get("passed_checks") == 27
            and failure.get("total_checks") == 29
            and failure.get("failed_checks")
            == ["node_typescript_build_pass", "node_tests_pass"]
        ),
        "step062_orchestration_boundary_preserved": (
            info.bounded_multi_agent_orchestration_implemented is True
            and info.bounded_multi_agent_orchestration_child_count == 2
            and info.bounded_multi_agent_orchestration_root_model_calls == 0
            and info.bounded_multi_agent_orchestration_windows_live_accepted is True
        ),
        "portability_runtime_flags_exact": (
            info.windows_node_acceptance_portability_fix_implemented is True
            and info.windows_node_acceptance_uses_cmd_for_npm_batch is False
            and info.windows_node_acceptance_uses_explicit_test_files is True
            and info.windows_node_acceptance_deterministic_accepted is True
            and info.windows_node_acceptance_windows_live_accepted is True
        ),
        "windows_npm_command_uses_cmd_call": (
            windows_command
            == [
                r"C:\Windows\System32\cmd.exe",
                "/d",
                "/c",
                "call",
                r"C:\Program Files\nodejs\npm.cmd",
                "run",
                "build",
            ]
            and "return [command_processor, \"/d\", \"/c\", \"call\", npm, \"run\", script]" in helper_source
        ),
        "node_tests_use_explicit_sorted_files": (
            explicit_test_command
            == [
                "node",
                "--test",
                str(Path("test/config.test.mjs")),
                str(Path("test/render.test.mjs")),
            ]
            and all("*" not in item for item in explicit_test_command)
        ),
        "package_test_script_cross_platform": package.get("scripts", {}).get("test")
        == "node --test",
        "forced_utf8_subprocess_decode_removed": (
            "text=True" not in helper_source
            and "stdout=subprocess.PIPE" in helper_source
            and "_decode_output(completed.stdout)" in helper_source
            and '"cp949"' in helper_source
        ),
        "step062_acceptance_uses_portable_helpers": (
            "validate_committed_typescript_release(cli_root)" in step062_source
            and "run_node_tests(cli_root)" in step062_source
            and "shutil.which(\"npm.cmd\")" not in step062_source
        ),
        "corrected_step062_acceptance_pass": (
            predecessor_ok
            and predecessor.get("state") == "PASSED"
            and predecessor.get("passed_checks") == 29
            and predecessor.get("total_checks") == 29
        ),
        "focused_portability_tests_pass": focused_ok and "4 passed" in focused_output,
        "python_compileall_pass": compile_ok,
        "node_typescript_build_pass": node_build_ok,
        "node_tests_pass": node_test_ok and "# pass 14" in node_test_output,
        "step062a_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launchers_present": (
            (ROOT / "sh_run_step062_acceptance.cmd").is_file()
            and (ROOT / "sh_run_step062a_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step062a_acceptance.py").is_file()
        ),
        "references_unchanged": references_ok,
        "step064_not_selected": "STEP064_" not in "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in [ROOT / "HANDOFF.md", ROOT / "PLANS.md", ROOT / "docs/plans/ROADMAP.md"]
        ),
    }

    payload = {
        "schema_version": "okcanvas-step062a-acceptance-v1",
        "step": "STEP062A_WINDOWS_NODE_ACCEPTANCE_PORTABILITY_FIX",
        "version": "2.43.1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "corrected_step062_state": predecessor.get("state"),
        "corrected_step062_passed_checks": predecessor.get("passed_checks"),
        "corrected_step062_total_checks": predecessor.get("total_checks"),
        "focused_test_output": focused_output.splitlines()[-1] if focused_output else "",
        "python_compile_output": compile_output.splitlines()[-1] if compile_output else "",
        "node_build_output_tail": node_build_output.splitlines()[-1] if node_build_output else "",
        "node_test_output_tail": node_test_output.splitlines()[-1] if node_test_output else "",
        "predecessor_console_tail": predecessor_console.splitlines()[-1]
        if predecessor_console
        else "",
        "reference_count": len(reference_results),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
