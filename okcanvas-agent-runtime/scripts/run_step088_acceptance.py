from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationContextReadCatalog,
    OrganizationContextSessionDelegationCatalog,
)
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane

STEP = "STEP088_RUNTIME_ORGANIZATION_CONTEXT_SESSION_DELEGATION_AND_LIVE_OPENAI_E2E_READINESS"
VERSION = "2.68.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP088_DETERMINISTIC_ACCEPTANCE.json"
PARENT_PATH = ROOT / "docs/evidence/STEP087R2_DETERMINISTIC_ACCEPTANCE.json"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def run(output: Path) -> int:
    started = _now()
    info = RuntimeInfo()
    definitions = AgentDefinitionCatalog(ROOT)
    root_definition = definitions.resolve("organization-context-session-agent")
    child_definition = definitions.resolve("organization-context-read-agent")
    composition = OrganizationContextSessionDelegationCatalog(ROOT).resolve(root_definition)
    catalog = OrganizationContextReadCatalog(ROOT)
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root_definition)
    parent = json.loads(PARENT_PATH.read_text(encoding="utf-8"))
    print("[STEP088] execution-plane", file=sys.stderr, flush=True)
    execution = validate_execution_plane()
    print("[STEP088] distribution", file=sys.stderr, flush=True)
    distribution = validate_distribution()
    print("[STEP088] launcher-registry", file=sys.stderr, flush=True)
    registry = validate_registry()
    print("[STEP088] architecture", file=sys.stderr, flush=True)
    architecture, architecture_process = run_json_python_validator(
        root=ROOT, script=ROOT / "scripts/validate_step081_architecture.py"
    )
    identity = DelegatedMCPIdentity.create(
        tenant_id="tenant-a", principal_id="user-001", roles=("agent-user",)
    )
    credential_env = "OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"
    old_secret = os.environ.pop(credential_env, None)
    try:
        readiness_without_secret = catalog.readiness(identity)
    finally:
        if old_secret is not None:
            os.environ[credential_env] = old_secret

    print("[STEP088] focused-regression", file=sys.stderr, flush=True)
    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step088_organization_context_session_delegation.py",
            "tests/test_step087r1_live_agent_tool_turn_budget_closure.py",
            "tests/test_step087r2_session_referential_continuation_routing.py",
            "tests/test_step087_main_assistant_stateless_groupware_subagent_delegation.py",
            "tests/test_step086_groupware_read_only_vertical.py",
            "tests/test_step086r1_groupware_subagent_and_external_mcp_boundary_alignment.py",
            "tests/test_step086r2_delegated_role_header_and_external_connector_contract_closure.py",
            "tests/test_step085_multi_mcp_and_delegated_identity_foundation.py",
            "tests/test_generic_mcp_gateway_contract.py",
            "tests/test_agent_as_tool_runtime.py",
            "tests/test_agent_invocation_scope.py",
            "tests/test_run_submission_boundary.py",
            "tests/test_agent_runtime_binding.py",
            "tests/test_output_contract_runtime_registry.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_baseline_version.py",
            "tests/test_runtime_info.py",
            "tests/test_step080_product_owned_capability_topology_and_tool_discovery_foundation.py",
            "tests/test_step081_root_package_and_architecture_restructuring.py",
            "tests/test_step082b_coding_execution_plane_and_distribution_boundary.py",
            "tests/test_step080a_acceptance_launcher_registry.py",
            "tests/test_step081_windows_entrypoint_and_launcher_registry.py",
        ],
        ROOT,
    )
    print("[STEP088] compileall", file=sys.stderr, flush=True)
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
    print("[STEP088] assemble", file=sys.stderr, flush=True)
    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP
        and PROJECT_VERSION == info.version == VERSION,
        "step087r2_parent_retained": parent.get("state") == "PASSED"
        and parent.get("passed_checks") == parent.get("total_checks") == 18,
        "organization_context_root_exact": root_definition.agent_id
        == "organization-context-session-agent"
        and root_definition.session_mode == "sqlite-v1"
        and root_definition.agent_tools == ("organization-context-read-agent",),
        "organization_context_child_exact": child_definition.agent_id
        == "organization-context-read-agent"
        and child_definition.session_mode == "disabled"
        and child_definition.output_contract == "OrganizationContextReadResult",
        "database_sot_exact": catalog.policy.production_sot == "DATABASE"
        and composition.policy.production_sot == "DATABASE",
        "read_only_tool_allowlist_exact": catalog.policy.allowed_tools
        == (
            "resolve_organization_context",
            "search_organization_context",
            "get_organization_entity",
        )
        and catalog.server.read_only is True,
        "delegated_identity_required": composition.policy.delegated_identity_required is True
        and catalog.server.requires_delegated_identity is True,
        "child_mcp_ownership_exact": child_definition.mcp_servers
        == ("organization-context-read",)
        and not root_definition.mcp_servers,
        "runtime_binding_exact": binding.execution_path
        == "sqlite-session-stateless-organization-context-subagent-execution-v1"
        and binding.mcp_servers[0]["owner_agent_id"] == "organization-context-read-agent",
        "one_child_call_at_depth_one": composition.policy.max_agent_tool_calls_per_turn == 1
        and composition.policy.max_depth == 1,
        "remote_default_fails_closed": readiness_without_secret.executable_now is False
        and readiness_without_secret.credential_value_configured is False,
        "runtime_info_exact": info.main_assistant_organization_context_session_delegation_implemented
        is True
        and info.main_assistant_organization_context_production_sot == "DATABASE"
        and info.main_assistant_organization_context_allowed_tool_count == 3
        and info.main_assistant_organization_context_write_enabled is False,
        "live_provider_not_claimed": info.main_assistant_organization_context_live_openai_provider_verified
        is False
        and info.main_assistant_organization_context_live_connector_verified is False,
        "groupware_vertical_retained": info.main_assistant_groupware_session_delegation_implemented
        is True,
        "session_referential_routing_retained": info.main_assistant_session_referential_restatement_routing_implemented
        is True
        and info.main_assistant_session_referential_restatement_policy_version == "1.4.0",
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
        "current_windows_acceptance_not_claimed": info.step088_windows_deterministic_accepted
        is False,
    }
    payload = {
        "schema_version": "okcanvas-step088-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_ORGANIZATION_CONTEXT_LIVE_READINESS",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step087r2_parent": parent,
        "execution_plane_validation": execution,
        "distribution_validation": distribution,
        "architecture_validation": architecture,
        "architecture_validation_process": architecture_process,
        "launcher_registry": registry,
        "focused_output": focused_output,
        "compile_output": compile_output,
        "limitations": {
            "live_openai_model_called": False,
            "live_organization_context_connector_called": False,
            "production_database_called": False,
            "windows_step088_executed": False,
        },
    }
    print("[STEP088] write", file=sys.stderr, flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("[STEP088] emit", file=sys.stderr, flush=True)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    sys.stdout.flush()
    sys.stderr.flush()
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
