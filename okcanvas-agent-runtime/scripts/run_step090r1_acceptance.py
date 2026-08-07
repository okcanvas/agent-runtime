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
from okcanvas_agent_runtime.application.assistant_routing import AssistantRoutingPolicyCatalog
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationContextReadCatalog,
    OrganizationContextSessionDelegationCatalog,
    organization_context_named_tool_choice,
)
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.package_source import DEFAULT_OUTPUT, PACKAGE_STEP
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane

STEP = "STEP090R1_ORGANIZATION_CONTEXT_MCP_TOOL_OUTPUT_PROTOCOL_AND_SHORT_LIST_TOOL_CHOICE_CLOSURE"
VERSION = "2.70.1"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP090R1_DETERMINISTIC_ACCEPTANCE.json"
PARENT_PATH = ROOT / "docs/evidence/STEP090_DETERMINISTIC_ACCEPTANCE.json"
EXPECTED_PACKAGE_NAME = (
    "okcanvas-agent-runtime-step090r1-organization-context-mcp-tool-output-protocol-and-short-list-tool-choice-closure.zip"
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def run(output: Path, *, emit_stdout: bool = True) -> int:
    started = _now()
    info = RuntimeInfo()
    definitions = AgentDefinitionCatalog(ROOT)
    root_definition = definitions.resolve("organization-context-session-agent")
    child_definition = definitions.resolve("organization-context-read-agent")
    composition = OrganizationContextSessionDelegationCatalog(ROOT).resolve(root_definition)
    catalog = OrganizationContextReadCatalog(ROOT)
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root_definition)
    routing_policy = AssistantRoutingPolicyCatalog(ROOT).resolve()
    parent = json.loads(PARENT_PATH.read_text(encoding="utf-8"))

    print("[STEP090R1] execution-plane", file=sys.stderr, flush=True)
    execution = validate_execution_plane()
    print("[STEP090R1] distribution", file=sys.stderr, flush=True)
    distribution = validate_distribution()
    print("[STEP090R1] launcher-registry", file=sys.stderr, flush=True)
    registry = validate_registry()
    print("[STEP090R1] architecture", file=sys.stderr, flush=True)
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

    print("[STEP090R1] focused-regression", file=sys.stderr, flush=True)
    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step091_organization_context_mcp_output_adapter_and_tool_choice.py",
            "tests/test_step090_organization_context_ambiguous_result_normalization.py",
            "tests/test_step089_organization_context_short_expression_routing.py",
            "tests/test_step088r1_organization_context_bounded_response_diagnostics.py",
            "tests/test_step088_organization_context_session_delegation.py",
            "tests/test_step087r2_session_referential_continuation_routing.py",
            "tests/test_step087_main_assistant_stateless_groupware_subagent_delegation.py",
            "tests/test_step083_organization_assistant_main_agent_and_action_routing.py",
            "tests/test_model_routing_policy.py",
            "tests/test_step084_organization_knowledge_glossary_and_directory_foundation.py",
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
    print("[STEP090R1] compileall", file=sys.stderr, flush=True)
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

    short_cases = {
        "김민수 정보": "organization-context-entity-detail-short-v1",
        "김선임 연락처": "organization-context-contact-field-short-v1",
        "김민수 직책": "organization-context-position-field-short-v1",
        "과장들 목록": "organization-context-position-members-short-v1",
    }
    short_matches = {
        query: routing_policy.match_organization_context_short_read(query)
        for query in short_cases
    }

    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP
        and PROJECT_VERSION == info.version == VERSION,
        "step090_parent_retained": parent.get("state") == "PASSED"
        and parent.get("passed_checks") == parent.get("total_checks") == 24,
        "routing_policy_exact": routing_policy.policy_id == "organization-assistant-routing-v1"
        and routing_policy.version == "1.5.0",
        "short_expression_rules_exact": len(routing_policy.organization_context_short_read_rules)
        == 4
        and all(
            short_matches[query] is not None
            and short_matches[query].pattern_id == pattern_id
            for query, pattern_id in short_cases.items()
        ),
        "request_hint_contract_exact": info.organization_context_request_hint_schema
        == "okcanvas-organization-context-request-hint-v1"
        and info.organization_context_short_expression_routing_implemented is True
        and info.organization_context_short_expression_rule_count == 4
        and info.organization_context_short_expression_entity_guessing_enabled is False,
        "organization_context_root_exact": root_definition.agent_id
        == "organization-context-session-agent"
        and root_definition.session_mode == "sqlite-v1"
        and root_definition.agent_tools == ("organization-context-read-agent",),
        "organization_context_child_exact": child_definition.agent_id
        == "organization-context-read-agent"
        and child_definition.session_mode == "disabled"
        and child_definition.output_contract == "OrganizationContextReadResult",
        "skills_remain_empty": not root_definition.skills and not child_definition.skills,
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
        "mcp_tool_output_protocol_and_named_tool_choice_exact": (
            organization_context_named_tool_choice(
                "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
                + json.dumps({"organization_context_request_hint": {"preferred_operation": "SEARCH"}})
                + "\n\nUSER REQUEST:\n과장들 목록"
            ) == "search_organization_context"
            and info.organization_context_ambiguous_result_normalization_implemented is True
        ),
        "ambiguous_result_normalization_and_diagnostics_exact": (
            info.organization_context_ambiguous_result_normalization_implemented is True
            and info.organization_context_ambiguous_result_normalization_strategy
            == "product-owned-mcp-evidence-normalization-v1"
            and info.organization_context_safe_structured_output_diagnostics_implemented is True
            and info.organization_context_raw_model_output_persisted is False
        ),
        "package_identity_exact": PACKAGE_STEP == STEP
        and DEFAULT_OUTPUT.name == EXPECTED_PACKAGE_NAME,
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
        "current_windows_acceptance_not_claimed": info.step090_windows_deterministic_accepted
        is False,
    }
    payload = {
        "schema_version": "okcanvas-step090r1-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_AMBIGUOUS_RESULT_NORMALIZATION_AND_LIVE_DIAGNOSTIC_GATE",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step090_parent": parent,
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
            "windows_step090r1_executed": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if emit_stdout:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--quiet", action="store_true", help="write the full acceptance payload only to --output")
    args = parser.parse_args()
    return run(args.output.resolve(), emit_stdout=not args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
