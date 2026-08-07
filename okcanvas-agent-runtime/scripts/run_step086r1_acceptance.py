from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane
from scripts.validate_step086r1_groupware_boundaries import validate as validate_groupware_boundaries

STEP = "STEP086R1_GROUPWARE_SUBAGENT_AND_EXTERNAL_MCP_BOUNDARY_ALIGNMENT"
VERSION = "2.66.1"
OUTPUT_DEFAULT = ROOT / "docs/evidence/step086r1-local/STEP086R1_ACCEPTANCE.json"
WINDOWS_PARENT = ROOT / "docs/evidence/STEP086_WINDOWS_DETERMINISTIC_ACCEPTANCE.json"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def run(output: Path) -> int:
    started = _now()
    info = RuntimeInfo()
    groupware = validate_groupware_boundaries()
    windows_parent = json.loads(WINDOWS_PARENT.read_text(encoding="utf-8"))
    execution = validate_execution_plane()
    distribution = validate_distribution()
    registry = validate_registry()
    architecture, architecture_process = run_json_python_validator(
        root=ROOT, script=ROOT / "scripts/validate_step081_architecture.py"
    )
    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step086r1_groupware_subagent_and_external_mcp_boundary_alignment.py",
            "tests/test_step086_groupware_read_only_vertical.py",
            "tests/test_step085_multi_mcp_and_delegated_identity_foundation.py",
            "tests/test_output_contract_runtime_registry.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_baseline_version.py",
            "tests/test_runtime_info.py",
            "tests/test_step082b_coding_execution_plane_and_distribution_boundary.py",
            "tests/test_step080a_acceptance_launcher_registry.py",
            "tests/test_step081_windows_entrypoint_and_launcher_registry.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "okcanvas_agent_runtime",
            "okcanvas_agent_protocols",
            "okcanvas_agent_clients",
            "scripts",
            "tests",
        ],
        ROOT,
    )
    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP
        and PROJECT_VERSION == info.version == VERSION,
        "step086_windows_parent_accepted": windows_parent.get("state") == "PASSED"
        and windows_parent.get("passed_checks") == windows_parent.get("total_checks") == 14,
        "groupware_boundary_validation_passed": groupware.get("state") == "PASSED"
        and groupware.get("passed_checks") == groupware.get("total_checks") == 25,
        "step082b_execution_plane_retained": execution.get("state") == "PASSED"
        and execution.get("passed_checks") == execution.get("total_checks") == 13,
        "step082b_distribution_retained": distribution.get("state") == "PASSED"
        and distribution.get("passed_checks") == distribution.get("total_checks") == 14,
        "architecture_regression_passed": architecture_process.get("returncode") == 0
        and architecture.get("state") == "PASSED"
        and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "launcher_registry_passed": registry.get("state") == "PASSED"
        and registry.get("current_step") == STEP
        and registry.get("current_record_count") == 2,
        "focused_regression_passed": focused_ok,
        "compileall_passed": compile_ok,
        "full_vertical_not_claimed": info.groupware_read_only_vertical_implemented is False
        and info.groupware_read_integration_boundary_implemented is True,
        "external_provider_not_claimed": info.groupware_read_mcp_provider_implemented_in_runtime
        is False
        and info.groupware_read_mcp_provider_live_verified is False,
        "read_agent_permanent_and_future_write_separate": info.groupware_read_permanently_read_only
        is True
        and info.groupware_action_agent_implemented is False
        and info.groupware_action_mcp_server_implemented is False,
        "next_step_unselected": info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION",
    }
    payload = {
        "schema_version": "okcanvas-step086r1-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "groupware_boundary_validation": groupware,
        "step086_windows_parent": windows_parent,
        "execution_plane_validation": execution,
        "distribution_validation": distribution,
        "architecture_validation": architecture,
        "architecture_validation_process": architecture_process,
        "launcher_registry": registry,
        "focused_output": focused_output,
        "compile_output": compile_output,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
