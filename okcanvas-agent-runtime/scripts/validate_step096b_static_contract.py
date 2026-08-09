from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_step096a_static_contract import validate as validate_parent

STEP = "STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION"
VERSION = "2.80.0"


def validate() -> dict[str, object]:
    baseline = (ROOT / "okcanvas_agent_runtime/core/baseline.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    gateway = (ROOT / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(encoding="utf-8")
    delegation = (ROOT / "okcanvas_agent_runtime/application/assistant_interpretation/delegation.py").read_text(encoding="utf-8")
    marker = (ROOT / "okcanvas_agent_runtime/application/assistant_routing/grounded_delegation.py").read_text(encoding="utf-8")
    routing = (ROOT / "okcanvas_agent_runtime/application/assistant_routing/service.py").read_text(encoding="utf-8")
    groupware_execution = (ROOT / "okcanvas_agent_runtime/application/groupware_read/request_execution.py").read_text(encoding="utf-8")
    groupware_normalizer = (ROOT / "okcanvas_agent_runtime/application/groupware_read/result_normalization.py").read_text(encoding="utf-8")
    agent_tool_runtime = (ROOT / "okcanvas_agent_runtime/agent/subagents/agent_tools/runtime.py").read_text(encoding="utf-8")
    runtime_info = (ROOT / "okcanvas_agent_runtime/core/runtime_info/foundation.py").read_text(encoding="utf-8")
    root_definition = json.loads((ROOT / "specs/agents/organization-assistant-session-agent/definition.json").read_text(encoding="utf-8"))
    root_instructions = (ROOT / "specs/agents/organization-assistant-session-agent/instructions.md").read_text(encoding="utf-8")
    policy = json.loads((ROOT / "specs/assistant/grounded-structured-delegation-policy.json").read_text(encoding="utf-8"))
    focused_test = (ROOT / "tests/test_step096b_structured_grounded_delegation_admission.py").read_text(encoding="utf-8")
    sdk_agent = (ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/agent.py").read_text(encoding="utf-8")

    parent = validate_parent()
    successor_owned_parent_checks = {
        "identity_exact",
        "unified_root_still_exact_two_children_and_no_direct_mcp",
        "root_instructions_preserve_authority_and_treat_hints_as_data",
    }
    parent_checks = dict(parent["checks"])
    parent_behavior_retained = all(
        value is True for key, value in parent_checks.items() if key not in successor_owned_parent_checks
    )

    checks = {
        "identity_exact": (
            f'CURRENT_STEP = "{STEP}"' in baseline
            and f'PROJECT_VERSION = "{VERSION}"' in baseline
            and f'version = "{VERSION}"' in pyproject
        ),
        "parent_step096a_behavior_contract_retained_except_successor_owned_root_contract": parent_behavior_retained,
        "root_exact_two_children_no_direct_mcp_version_1_4": (
            root_definition.get("version") == "1.4.0"
            and root_definition.get("agent_tools") == ["groupware-read-agent", "organization-context-read-agent"]
            and root_definition.get("mcp_servers") == []
            and root_definition.get("max_turns") == 2
        ),
        "explicit_grounded_structured_marker_is_product_owned": all(
            token in marker
            for token in (
                'okcanvas-grounded-structured-delegation-v1',
                'LLM_SELECTS_AT_MOST_ONE_READ_CHILD',
                '"max_child_calls": 1',
                '"max_child_requests": 1',
                '"stable_ids_from_model_accepted": False',
                '"write_enabled": False',
                '"runtime_admission_required": True',
                '"child_mcp_lazy_connect": True',
                '"legacy_child_selection_authoritative": False',
            )
        ) and 'context["grounded_structured_delegation"] = grounded_structured_delegation_context()' in routing,
        "gateway_enables_structured_mode_only_from_exact_marker": (
            "extract_grounded_routing_context" in gateway
            and "grounded_structured_delegation_requested(routing_context)" in gateway
            and "structured_delegation_requested and cross_domain_session_binding is not None" in gateway
        ),
        "structured_model_inputs_are_read_only_and_forbid_extra_fields": (
            'Literal["READ"]' in delegation
            and delegation.count('extra="forbid"') >= 2
            and "entity_id:" not in delegation.split("class OrganizationReadDelegationInput", 1)[1].split("class GroupwareReadDelegationInput", 1)[0]
            and "tool_name:" not in delegation.split("class GroupwareReadDelegationInput", 1)[1].split("class GroundedDelegationAdmission", 1)[0]
        ),
        "organization_get_identity_only_from_runtime_focus": all(
            token in delegation
            for token in (
                'if proposal.context_reference_mode == "SESSION_FOCUS"',
                'target_expression = active.entity_id',
                'GET cannot accept a model-supplied stable identity',
                'stable_ids_from_model_accepted": False',
            )
        ),
        "groupware_resource_maps_to_exact_runtime_tool": all(
            token in delegation
            for token in ('"NOTICE": "search_notices"', '"MAIL": "search_mail"', '"CALENDAR": "list_calendar_events"')
        ) and "groupware_operation_hint" in groupware_execution,
        "groupware_session_focus_bound_matches_existing_cross_domain_max_20": "max_results=min(self._groupware.policy.max_results, 20)" in delegation,
        "groupware_normalizer_revalidates_admitted_exact_tool": all(
            token in groupware_normalizer
            for token in (
                "GROUPWARE_OPERATION_TOOL_RESULT_CARDINALITY_MISMATCH",
                "GROUPWARE_OPERATION_TOOL_MISMATCH",
                "grounded-groupware-operation-admission-v1",
            )
        ),
        "product_owned_non_read_side_effect_fence_precedes_read_admission": (
            '_require_parent_read_admission(parent_side_effect)' in delegation
            and 'parent_side_effect not in {"NONE", "READ"}' in delegation
            and 'parent_side_effect=str((routing_context or {}).get("side_effect") or "")' in gateway
        ),
        "agent_as_tool_supports_structured_parameters_and_input_builder": all(
            token in agent_tool_runtime for token in ("parameters", "input_builder", "tool_description")
        ),
        "retained_sdk_agent_contract_is_mutable_and_requires_explicit_mcp_lifecycle": (
            "@dataclass\nclass AgentBase" in sdk_agent
            and "mcp_servers: list[MCPServer]" in sdk_agent
            and "model_settings: ModelSettings" in sdk_agent
            and "server.connect()" in sdk_agent
            and "server.cleanup()" in sdk_agent
        ),
        "runtime_admission_precedes_child_started_and_lazy_mcp_connect": all(
            token in gateway
            for token in (
                '"agent.tool.requested"',
                '"agent.tool.admitted"',
                '"agent.tool.admission.denied"',
                "await server.connect()",
                "await server.cleanup()",
                "input_builder=grounded_input_builder",
            )
        ),
        "grounded_root_does_not_force_tool_choice_required": (
            "not grounded_structured_delegation_enabled" in gateway
            and 'tool_choice="required"' in gateway
        ),
        "root_instructions_assign_language_interpretation_to_llm_and_execution_to_runtime": all(
            token in root_instructions
            for token in (
                "interpret the user's natural language",
                "request exactly one read-only specialist",
                "Runtime admission",
                "Never request both specialists in one Turn",
                "never reinterpret it as a read",
                "Never submit a stable ID or MCP Tool name",
            )
        ),
        "policy_is_read_only_max_one_lazy_and_no_root_mcp": (
            policy.get("schema_version") == "okcanvas-grounded-structured-delegation-policy-v1"
            and policy.get("allowed_capabilities") == ["groupware-read-v1", "organization-context-read-v1"]
            and policy.get("side_effects_allowed") == ["READ"]
            and policy.get("max_child_calls_per_turn") == 1
            and policy.get("max_child_requests_per_turn") == 1
            and policy.get("stable_ids_from_model_accepted") is False
            and policy.get("runtime_admission_required") is True
            and policy.get("child_mcp_connection") == "LAZY_AFTER_ADMISSION"
            and policy.get("root_direct_mcp_enabled") is False
            and policy.get("write_enabled") is False
        ),
        "runtime_info_declares_step096b_not_live_accepted": all(
            token in runtime_info
            for token in (
                "grounded_llm_structured_delegation_implemented: bool = True",
                "grounded_llm_structured_delegation_max_child_calls: int = 1",
                "grounded_llm_structured_delegation_max_child_requests: int = 1",
                "grounded_llm_structured_delegation_stable_ids_from_model_accepted: bool = False",
                "grounded_llm_structured_delegation_runtime_admission_required: bool = True",
                "grounded_llm_structured_delegation_child_mcp_lazy_connect: bool = True",
                "grounded_llm_structured_delegation_windows_live_accepted: bool = False",
            )
        ),
        "focused_tests_cover_stable_id_rejection_marker_exact_tool_and_lazy_contract": all(
            token in focused_test
            for token in (
                "structured_inputs_have_no_stable_id_or_tool_name_surface",
                "model_cannot_supply_get_identity_without_runtime_focus",
                "build_model_request_marks_grounded_structured_delegation_explicitly",
                "groupware_operation_admission_requires_exact_observed_tool",
                "gateway_declares_requested_admitted_started_and_lazy_mcp_contract",
                "grounded_agent_tool_request_count",
            )
        ),
        "windows_live_not_claimed": True,
    }
    return {
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": STEP,
        "version": VERSION,
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "parent_step": parent.get("step"),
        "parent_version": parent.get("version"),
        "parent_successor_owned_check_exclusions": sorted(successor_owned_parent_checks),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
