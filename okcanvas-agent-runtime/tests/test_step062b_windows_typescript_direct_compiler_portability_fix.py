from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.node_acceptance import (
    resolve_typescript_compiler,
    typescript_build_command,
    typescript_compiler_candidates,
)

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clients" / "cli"


def test_step062b_runtime_baseline_and_flags_are_exact() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.windows_typescript_direct_compiler_fix_implemented is True
    assert info.windows_typescript_build_uses_node_direct_compiler is False
    assert info.windows_typescript_build_avoids_npm_batch is True
    assert info.windows_typescript_direct_compiler_deterministic_accepted is True
    assert info.windows_typescript_direct_compiler_windows_live_accepted is True
    assert info.bounded_multi_agent_orchestration_implemented is True


def test_windows_tsc_cmd_resolves_sibling_javascript_compiler(tmp_path: Path) -> None:
    prefix = tmp_path / "npm-prefix"
    shim = prefix / "tsc.cmd"
    compiler = prefix / "node_modules" / "typescript" / "bin" / "tsc"
    compiler.parent.mkdir(parents=True)
    shim.write_text("@echo off\r\n", encoding="utf-8")
    compiler.write_text("require('../lib/tsc.js')\n", encoding="utf-8")

    resolved = resolve_typescript_compiler(CLI, str(shim))
    assert resolved == compiler.resolve()
    command = typescript_build_command("node.exe", CLI, tsc_command=str(shim))
    assert command == ["node.exe", str(compiler.resolve()), "-p", "tsconfig.json"]
    assert all(not item.lower().endswith((".cmd", ".bat")) for item in command)


def test_compiler_candidates_include_project_and_global_npm_layouts(tmp_path: Path) -> None:
    prefix = tmp_path / "global"
    shim = prefix / "tsc.cmd"
    candidates = typescript_compiler_candidates(CLI, str(shim))
    assert (CLI / "node_modules/typescript/bin/tsc").resolve() in candidates
    assert (prefix / "node_modules/typescript/bin/tsc").resolve() in candidates
    assert (prefix / "node_modules/typescript/lib/tsc.js").resolve() in candidates


def test_step062_and_step062a_build_paths_bypass_npm_batch() -> None:
    step062 = (ROOT / "scripts/run_step062_acceptance.py").read_text(encoding="utf-8")
    step062a = (ROOT / "scripts/run_step062a_acceptance.py").read_text(encoding="utf-8")
    for source in (step062, step062a):
        assert "validate_committed_typescript_release(cli_root)" in source
        assert 'run_npm_script("build", cli_root)' not in source


def test_second_windows_failure_evidence_is_exact() -> None:
    failure = json.loads(
        (ROOT / "docs/evidence/STEP062A_WINDOWS_TYPESCRIPT_BUILD_FAILURE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert failure["passed_checks"] == 16
    assert failure["total_checks"] == 18
    assert failure["failed_checks"] == [
        "corrected_step062_acceptance_pass",
        "node_typescript_build_pass",
    ]
    assert failure["corrected_step062_passed_checks"] == 28
    assert failure["corrected_step062_total_checks"] == 29
    assert failure["node_build_output_tail"] == "배치 파일이 아닙니다."
    assert failure["node_test_passed"] is True
