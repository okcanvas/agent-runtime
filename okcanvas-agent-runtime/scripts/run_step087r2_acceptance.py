from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.groupware_read import GroupwareSessionDelegationCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane

STEP = "STEP087R2_SESSION_REFERENTIAL_RESTATEMENT_ROUTING_CLOSURE"
VERSION = "2.67.2"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP087R2_DETERMINISTIC_ACCEPTANCE.json"
STEP087R1_PARENT = ROOT / "docs/evidence/STEP087R1_DETERMINISTIC_ACCEPTANCE.json"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def run(output: Path) -> int:
    started = _now()
    info = RuntimeInfo()
    definitions = AgentDefinitionCatalog(ROOT)
    root_definition = definitions.resolve("organization-assistant-session-agent")
    child_definition = definitions.resolve("groupware-read-agent")
    composition = GroupwareSessionDelegationCatalog(ROOT).resolve(root_definition)
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root_definition)
    parent = json.loads(STEP087R1_PARENT.read_text(encoding="utf-8"))
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
            "tests/test_step087r1_live_agent_tool_turn_budget_closure.py",
            "tests/test_step087r2_session_referential_continuation_routing.py",
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
        "step087r1_parent_retained": parent.get("state") == "PASSED"
        and parent.get("passed_checks") == parent.get("total_checks") == 17,
        "root_live_turn_budget_exact": root_definition.max_turns == 2,
        "child_live_turn_budget_exact": child_definition.max_turns == 2,
        "child_session_remains_disabled": child_definition.session_mode == "disabled",
        "child_mcp_ownership_retained": child_definition.mcp_servers == ("groupware-read",)
        and not root_definition.mcp_servers,
        "composition_contract_retained": composition.policy.policy_id
        == "main-assistant-stateless-groupware-subagent-v1"
        and composition.policy.max_agent_tool_calls_per_turn == 1
        and composition.policy.max_depth == 1,
        "runtime_binding_retained": binding.execution_path
        == "sqlite-session-stateless-groupware-subagent-execution-v1",
        "session_referential_restatement_routing_exact": info.main_assistant_session_referential_restatement_routing_implemented is True
        and info.main_assistant_session_referential_restatement_policy_version == "1.3.0",
        "runtime_info_turn_budget_exact": info.main_assistant_groupware_root_max_turns == 2
        and info.main_assistant_groupware_child_max_turns == 2
        and info.main_assistant_groupware_child_tool_choice_required is True
        and info.main_assistant_groupware_live_agent_tool_turn_budget_closed is True,
        "live_provider_not_claimed": info.main_assistant_groupware_live_openai_provider_verified
        is False,
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
        "current_windows_acceptance_not_claimed": getattr(
            info, "step087r2_windows_deterministic_accepted", False
        ) is False,
    }
    payload = {
        "schema_version": "okcanvas-step087r2-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_LIVE_RUN_LOOP_READINESS",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step087r1_parent": parent,
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
            "windows_step087r2_executed": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # ASCII escaping keeps redirected Windows CP949 stdout valid JSON.
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
