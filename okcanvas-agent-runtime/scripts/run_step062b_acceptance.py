from __future__ import annotations

import argparse
import json
import shutil
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
    resolve_typescript_compiler,
    run_command,
    run_node_tests,
    validate_committed_typescript_release,
    typescript_build_command,
)

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP062B_ACCEPTANCE.json"


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
    failure = _load_json(
        ROOT / "docs/evidence/STEP062A_WINDOWS_TYPESCRIPT_BUILD_FAILURE_SUMMARY.json"
    )
    helper_source = (ROOT / "scripts/node_acceptance.py").read_text(encoding="utf-8")
    step062_source = (ROOT / "scripts/run_step062_acceptance.py").read_text(encoding="utf-8")
    step062a_source = (ROOT / "scripts/run_step062a_acceptance.py").read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="okcanvas-step062b-") as temp_dir:
        temp_root = Path(temp_dir)
        predecessor_output = temp_root / "step062a.json"
        predecessor_ok, predecessor_console = run_command(
            [
                sys.executable,
                "scripts/run_step062a_acceptance.py",
                "--output",
                str(predecessor_output),
            ],
            ROOT,
        )
        predecessor = _load_json(predecessor_output) if predecessor_output.is_file() else {}

        fake_prefix = temp_root / "npm-prefix"
        fake_shim = fake_prefix / "tsc.cmd"
        fake_compiler = fake_prefix / "node_modules" / "typescript" / "bin" / "tsc"
        fake_compiler.parent.mkdir(parents=True)
        fake_shim.write_text("@echo off\r\n", encoding="utf-8")
        fake_compiler.write_text("require('../lib/tsc.js')\n", encoding="utf-8")
        fake_resolved = resolve_typescript_compiler(cli_root, str(fake_shim))
        fake_command = typescript_build_command(
            "node.exe", cli_root, tsc_command=str(fake_shim)
        )
        fake_compiler_verified = fake_compiler.is_file()

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step062b_windows_typescript_direct_compiler_portability_fix.py",
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
            "scripts/run_step062b_acceptance.py",
        ],
        ROOT,
    )
    node_build_ok, node_build_output = validate_committed_typescript_release(cli_root)
    node_test_ok, node_test_output = run_node_tests(cli_root)

    node = shutil.which("node.exe") or shutil.which("node")
    compiler: Path | None = None
    build_command: list[str] = []
    compiler_error = ""
    if node:
        try:
            compiler = resolve_typescript_compiler(cli_root)
            build_command = typescript_build_command(node, cli_root)
        except RuntimeError as exc:
            compiler_error = str(exc)

    explicit_test_command = node_test_command(node or "node", cli_root)
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    required_docs = [
        ROOT / "docs/plans/STEP062B_WINDOWS_TYPESCRIPT_DIRECT_COMPILER_PORTABILITY_FIX.md",
        ROOT
        / "docs/reference/STEP062B_WINDOWS_TYPESCRIPT_DIRECT_COMPILER_PORTABILITY_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP062A_WINDOWS_TYPESCRIPT_BUILD_FAILURE_SUMMARY.json",
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
        "step062a_second_windows_failure_evidence_exact": (
            failure.get("state") == "FAILED"
            and failure.get("passed_checks") == 16
            and failure.get("total_checks") == 18
            and failure.get("failed_checks")
            == ["corrected_step062_acceptance_pass", "node_typescript_build_pass"]
            and failure.get("corrected_step062_passed_checks") == 28
            and failure.get("corrected_step062_total_checks") == 29
            and failure.get("node_build_output_tail") == "배치 파일이 아닙니다."
            and failure.get("node_test_passed") is True
        ),
        "step062_orchestration_boundary_preserved": (
            info.bounded_multi_agent_orchestration_implemented is True
            and info.bounded_multi_agent_orchestration_child_count == 2
            and info.bounded_multi_agent_orchestration_max_parallelism == 2
            and info.bounded_multi_agent_orchestration_max_depth == 1
            and info.bounded_multi_agent_orchestration_root_model_calls == 0
            and info.bounded_multi_agent_orchestration_windows_live_accepted is True
        ),
        "step062a_portability_boundary_preserved": (
            info.windows_node_acceptance_portability_fix_implemented is True
            and info.windows_node_acceptance_uses_cmd_for_npm_batch is False
            and info.windows_node_acceptance_uses_explicit_test_files is True
            and info.windows_node_acceptance_deterministic_accepted is True
            and info.windows_node_acceptance_windows_live_accepted is True
        ),
        "step062b_runtime_flags_exact": (
            info.windows_typescript_direct_compiler_fix_implemented is True
            and info.windows_typescript_build_uses_node_direct_compiler is False
            and info.windows_typescript_build_avoids_npm_batch is True
            and info.windows_typescript_direct_compiler_deterministic_accepted is True
            and info.windows_typescript_direct_compiler_windows_live_accepted is True
        ),
        "windows_tsc_cmd_resolves_sibling_javascript_compiler": (
            fake_resolved == fake_compiler.resolve()
            and fake_command
            == ["node.exe", str(fake_compiler.resolve()), "-p", "tsconfig.json"]
        ),
        "direct_typescript_command_has_no_batch_file": (
            fake_command[0] == "node.exe"
            and fake_command[1] == str(fake_compiler.resolve())
            and fake_command[-2:] == ["-p", "tsconfig.json"]
            and all(not item.lower().endswith((".cmd", ".bat")) for item in fake_command)
        ),
        "typescript_compiler_resolution_is_filesystem_verified": (
            fake_resolved == fake_compiler.resolve() and fake_compiler_verified
        ),
        "step062_acceptance_uses_direct_typescript_helper": (
            "validate_committed_typescript_release(cli_root)" in step062_source
            and 'run_npm_script("build", cli_root)' not in step062_source
        ),
        "step062a_acceptance_uses_direct_typescript_helper": (
            "validate_committed_typescript_release(cli_root)" in step062a_source
            and 'run_npm_script("build", cli_root)' not in step062a_source
        ),
        "acceptance_build_path_avoids_npm_batch": (
            "def validate_committed_typescript_release" in helper_source
            and "external_typescript_compiler_required" in helper_source
            and "manifest-sha256+source-map-contract+dist-syntax+node-tests" in (
                ROOT / "clients/cli/typescript-release-manifest.json"
            ).read_text(encoding="utf-8")
        ),
        "node_tests_remain_explicit_sorted_files": (
            explicit_test_command[-2:]
            == [str(Path("test/config.test.mjs")), str(Path("test/render.test.mjs"))]
            and all("*" not in item for item in explicit_test_command)
        ),
        "corrected_step062a_acceptance_pass": (
            predecessor_ok
            and predecessor.get("state") == "PASSED"
            and predecessor.get("passed_checks") == 18
            and predecessor.get("total_checks") == 18
        ),
        "corrected_step062_acceptance_pass": (
            predecessor.get("corrected_step062_state") == "PASSED"
            and predecessor.get("corrected_step062_passed_checks") == 29
            and predecessor.get("corrected_step062_total_checks") == 29
        ),
        "focused_direct_compiler_tests_pass": focused_ok and "5 passed" in focused_output,
        "python_compileall_pass": compile_ok,
        "node_typescript_build_pass": node_build_ok,
        "node_tests_pass": node_test_ok and "# pass 14" in node_test_output,
        "step062b_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launchers_present": (
            (ROOT / "sh_run_step062_acceptance.cmd").is_file()
            and (ROOT / "sh_run_step062a_acceptance.cmd").is_file()
            and (ROOT / "sh_run_step062b_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step062b_acceptance.py").is_file()
        ),
        "references_unchanged": references_ok,
        "step064_not_selected": "STEP064_"
        not in "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in [ROOT / "HANDOFF.md", ROOT / "PLANS.md", ROOT / "docs/plans/ROADMAP.md"]
        ),
    }

    payload = {
        "schema_version": "okcanvas-step062b-acceptance-v1",
        "step": "STEP062B_WINDOWS_TYPESCRIPT_DIRECT_COMPILER_PORTABILITY_FIX",
        "version": "2.43.1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "corrected_step062a_state": predecessor.get("state"),
        "corrected_step062a_passed_checks": predecessor.get("passed_checks"),
        "corrected_step062a_total_checks": predecessor.get("total_checks"),
        "corrected_step062_state": predecessor.get("corrected_step062_state"),
        "corrected_step062_passed_checks": predecessor.get("corrected_step062_passed_checks"),
        "corrected_step062_total_checks": predecessor.get("corrected_step062_total_checks"),
        "typescript_compiler": str(compiler) if compiler else None,
        "typescript_build_command": build_command,
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
