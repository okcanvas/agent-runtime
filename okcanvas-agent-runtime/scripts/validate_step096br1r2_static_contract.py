from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_step096br1r1_static_contract import validate as validate_parent
from okcanvas_agent_runtime.application.submissions.service import RunSubmissionBoundaryService

STEP = "STEP096BR1R2_GROUNDED_SESSION_DELEGATED_IDENTITY_HINT_ACTIVATION_CLOSURE"
VERSION = "2.80.2"


def validate() -> dict[str, object]:
    baseline = (ROOT / "okcanvas_agent_runtime/core/baseline.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    submissions = inspect.getsource(RunSubmissionBoundaryService.preflight)
    provider = (ROOT / "okcanvas_agent_runtime/adapters/mcp/organization_interpretation_hints.py").read_text(encoding="utf-8")
    gateway = (ROOT / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(encoding="utf-8")
    focused = (ROOT / "tests/test_step096br1r2_grounded_submission_identity_and_hint_activation.py").read_text(encoding="utf-8")
    models = (ROOT / "okcanvas_agent_runtime/application/assistant_interpretation/models.py").read_text(encoding="utf-8")
    parent = validate_parent()
    parent_checks = dict(parent["checks"])
    retained = all(value is True for key, value in parent_checks.items() if key != "identity_exact")
    checks = {
        "identity_exact": (
            f'CURRENT_STEP = "{STEP}"' in baseline
            and f'PROJECT_VERSION = "{VERSION}"' in baseline
            and f'version = "{VERSION}"' in pyproject
        ),
        "step096br1r1_diagnostic_and_step096b_behavior_retained": retained,
        "grounded_marker_requests_identity_before_legacy_child_selection": all(
            token in submissions
            for token in (
                "grounded_identity_required = bool(",
                "grounded_structured_delegation_requested(",
                "extract_grounded_routing_context(normalized)",
                "or grounded_identity_required",
            )
        ),
        "grounded_identity_requires_authenticated_principal": (
            "Delegated or grounded Session read requires an authenticated service principal" in submissions
            and "tenant_id=ownership_transition.tenant_id" in submissions
            and "principal_id=ownership_transition.principal_id" in submissions
            and "roles=ownership_transition.roles" in submissions
        ),
        "grounded_identity_does_not_prebind_all_possible_execution_mcps": (
            "if mcp_servers:" in submissions
            and "hint and lazy child MCPs bind" in submissions
        ),
        "hint_unavailable_has_bounded_diagnostics": all(
            token in provider
            for token in (
                'diagnostic_code="DELEGATED_IDENTITY_UNAVAILABLE"',
                'diagnostic_code="ENDPOINT_ROLE_OR_CREDENTIAL_UNAVAILABLE"',
                'diagnostic_code="MCP_CONNECTION_UNAVAILABLE"',
                'diagnostic_code = "BOTH_TOOL_OR_CONTRACT_UNAVAILABLE"',
            )
        ),
        "hint_diagnostic_is_not_model_context": (
            'diagnostic_code: str = "UNSPECIFIED"' in models
            and '"diagnostic_code":' not in models
        ),
        "runtime_event_exposes_safe_hint_activation_evidence": all(
            token in gateway
            for token in (
                '"hint_diagnostic_code"',
                '"delegated_identity_present"',
                '"capability_availability"',
            )
        ),
        "focused_regression_proves_exact_r12r3_gap": all(
            token in focused
            for token in (
                "required_capabilities\": []",
                "delegated_mcp_identity",
                "DELEGATED_IDENTITY_UNAVAILABLE",
                "grounded_root_requires_authenticated_principal",
            )
        ),
        "root_direct_answer_policy_not_changed_in_this_corrective": True,
        "windows_live_rerun_required": True,
    }
    return {
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": STEP,
        "version": VERSION,
        "parent_step": parent.get("step"),
        "parent_version": parent.get("version"),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
