from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.node_acceptance import node_test_command, npm_script_command

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clients" / "cli"


def test_step062a_runtime_baseline_and_flags_are_exact() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.windows_node_acceptance_portability_fix_implemented is True
    assert info.windows_node_acceptance_uses_cmd_for_npm_batch is False
    assert info.windows_node_acceptance_uses_explicit_test_files is True
    assert info.windows_node_acceptance_deterministic_accepted is True
    assert info.windows_node_acceptance_windows_live_accepted is True
    assert info.bounded_multi_agent_orchestration_implemented is True


def test_windows_npm_batch_command_uses_cmd_call() -> None:
    command = npm_script_command(
        r"C:\Program Files\nodejs\npm.cmd",
        "build",
        platform_name="nt",
        comspec=r"C:\Windows\System32\cmd.exe",
    )
    assert command == [
        r"C:\Windows\System32\cmd.exe",
        "/d",
        "/c",
        "call",
        r"C:\Program Files\nodejs\npm.cmd",
        "run",
        "build",
    ]


def test_node_tests_are_explicit_sorted_paths_without_glob() -> None:
    command = node_test_command("node", CLI)
    assert command == [
        "node",
        "--test",
        str(Path("test/config.test.mjs")),
        str(Path("test/render.test.mjs")),
    ]
    assert all("*" not in item for item in command)


def test_package_script_and_failure_evidence_are_exact() -> None:
    package = json.loads((CLI / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["test"] == "node --test"
    failure = json.loads(
        (ROOT / "docs/evidence/STEP062_WINDOWS_NODE_ACCEPTANCE_FAILURE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert failure["passed_checks"] == 27
    assert failure["total_checks"] == 29
    assert failure["failed_checks"] == ["node_typescript_build_pass", "node_tests_pass"]
