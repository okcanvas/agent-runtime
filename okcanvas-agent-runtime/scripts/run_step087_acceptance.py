from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.application.groupware_read import GroupwareSessionDelegationCatalog
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane

STEP = "STEP087_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_DELEGATION"
VERSION = "2.67.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP087_DETERMINISTIC_ACCEPTANCE.json"
STEP086R2_PARENT = ROOT / "docs/evidence/STEP086R2_ACCEPTANCE.json"
STEP086R1_WINDOWS_PARENT = ROOT / "docs/evidence/STEP086R1_WINDOWS_DETERMINISTIC_ACCEPTANCE.json"
STEP086R2_CONNECTOR = ROOT / "docs/evidence/STEP086R2_CONNECTOR_CONTRACT_VALIDATION.json"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def run(output: Path) -> int:
    started = _now()
    info = RuntimeInfo()
    root_definition = AgentDefinitionCatalog(ROOT).resolve(
        "organization-assistant-session-agent"
    )
    composition = GroupwareSessionDelegationCatalog(ROOT).resolve(root_definition)
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root_definition)
    step086r2_parent = json.loads(STEP086R2_PARENT.read_text(encoding="utf-8"))
    step086r1_windows_parent = json.loads(
        STEP086R1_WINDOWS_PARENT.read_text(encoding="utf-8")
    )
    connector = json.loads(STEP086R2_CONNECTOR.read_text(encoding="utf-8"))
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
            "tests/test_step087_main_assistant_stateless_groupware_subagent_delegation.py",
            "tests/test_agent_as_tool_runtime.py",
            "tests/test_generic_mcp_gateway_contract.py",
            "tests/test_step085_multi_mcp_and_delegated_identity_foundation.py",
            "tests/test_step086_groupware_read_only_vertical.py",
            "tests/test_step086r1_groupware_subagent_and_external_mcp_boundary_alignment.py",
            "tests/test_step086r2_delegated_role_header_and_external_connector_contract_closure.py",
            "tests/test_agent_invocation_scope.py",
            "tests/test_run_submission_boundary.py",
            "tests/test_agent_runtime_binding.py",
            "tests/test_output_contract_runtime_registry.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_baseline_version.py",
            "tests/test_runtime_info.py",
            "tests/test_step081_root_package_and_architecture_restructuring.py",
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
        "composition_contract_exact": composition.policy.policy_id
        == "main-assistant-stateless-groupware-subagent-v1"
        and composition.parent.agent_id == "organization-assistant-session-agent"
        and composition.child.agent_id == "groupware-read-agent"
        and composition.child.session_mode == "disabled"
        and composition.policy.max_agent_tool_calls_per_turn == 1
        and composition.policy.max_depth == 1,
        "runtime_binding_exact": binding.execution_path
        == "sqlite-session-stateless-groupware-subagent-execution-v1"
        and binding.mcp_servers[0]["owner_agent_id"] == "groupware-read-agent",
        "runtime_info_exact": info.groupware_read_only_vertical_implemented is True
        and info.main_assistant_groupware_session_delegation_implemented is True
        and info.main_assistant_groupware_child_write_enabled is False
        and info.main_assistant_groupware_deterministic_gateway_verified is True,
        "step086r2_parent_retained": step086r2_parent.get("state") == "PASSED"
        and step086r2_parent.get("passed_checks")
        == step086r2_parent.get("total_checks")
        == 15,
        "step086r1_windows_parent_retained": step086r1_windows_parent.get("state")
        == "PASSED"
        and step086r1_windows_parent.get("passed_checks")
        == step086r1_windows_parent.get("total_checks")
        == 13,
        "connector_contract_retained": connector.get("state") == "PASSED"
        and connector.get("passed_checks") == connector.get("total_checks") == 11,
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
        "live_openai_provider_not_claimed": info.main_assistant_groupware_live_openai_provider_verified
        is False,
        "current_windows_acceptance_not_claimed": info.step087_windows_deterministic_accepted
        is False,
    }
    payload = {
        "schema_version": "okcanvas-step087-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_WITH_FAKE_OPENAI_AGENTS_BOUNDARY",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step086r2_parent": step086r2_parent,
        "step086r1_windows_parent": step086r1_windows_parent,
        "connector_contract_validation": connector,
        "execution_plane_validation": execution,
        "distribution_validation": distribution,
        "architecture_validation": architecture,
        "architecture_validation_process": architecture_process,
        "launcher_registry": registry,
        "focused_output": focused_output,
        "compile_output": compile_output,
        "limitations": {
            "live_openai_model_called": False,
            "live_groupware_provider_called": False,
            "windows_step087_executed": False,
        },
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
