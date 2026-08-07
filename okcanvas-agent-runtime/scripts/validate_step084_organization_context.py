from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationAccessContext,
    OrganizationCatalogState,
    OrganizationContextCatalog,
    OrganizationContextService,
)
from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

STEP = "STEP084_ORGANIZATION_KNOWLEDGE_GLOSSARY_AND_DIRECTORY_FOUNDATION"
VERSION = "2.64.0"
FIXTURE = ROOT / "fixtures" / "organization" / "step084-ready"


def _runtime_paths() -> set[str]:
    temp = Path(tempfile.mkdtemp(prefix="okcanvas-step084-routes-"))
    app = create_app(
        project_root=ROOT,
        product_db=temp / "product.sqlite3",
        artifact_root=temp / "artifacts",
        admin_key="step084-validator-admin-key-123456",
        run_submitter_key="step084-validator-submitter-key-123456",
        protected_payload_root=temp / "payloads",
        protected_payload_key=base64.urlsafe_b64encode(bytes(range(32))).decode("ascii"),
        session_root=temp / "sessions",
        session_history_key=base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii"),
        organization_catalog_root=FIXTURE,
    )
    return {str(getattr(route, "path", "")) for route in app.routes}


def validate() -> dict[str, object]:
    info = RuntimeInfo()
    default_catalog = OrganizationContextCatalog(ROOT)
    ready = OrganizationContextService(ROOT, FIXTURE)
    access = OrganizationAccessContext(
        tenant_id="step084-tenant", principal_id="step084-user", roles=("agent-user",)
    )
    other = OrganizationAccessContext(
        tenant_id="other-tenant", principal_id="step084-other", roles=("agent-user",)
    )
    glossary = ready.glossary("우리 회사에서 PI가 무슨 뜻이야?", access)
    knowledge = ready.knowledge("휴가 정책", access)
    directory = ready.directory("플랫폼팀장", access)
    hidden = ready.combined("PI", other)
    default_router = OrganizationAssistantRoutingService(str(ROOT))
    ready_router = OrganizationAssistantRoutingService(str(ROOT), FIXTURE)
    default_route = default_router.route(
        request="우리 회사에서 PI가 무슨 뜻이야?",
        tenant_id="step084-tenant",
        principal_id="step084-user",
        roles=("agent-user",),
    )
    ready_route = ready_router.route(
        request="우리 회사에서 PI가 무슨 뜻이야?",
        tenant_id="step084-tenant",
        principal_id="step084-user",
        roles=("agent-user",),
    )
    no_match = ready_router.route(
        request="우리 회사에서 존재하지 않는 ZXQ 용어가 무슨 뜻이야?",
        tenant_id="step084-tenant",
        principal_id="step084-user",
        roles=("agent-user",),
    )
    model_request = ready_router.build_model_request(ready_route, "우리 회사에서 PI가 무슨 뜻이야?")
    paths = _runtime_paths()
    expected_paths = {
        "/v1/organization/glossary/resolve",
        "/v1/organization/knowledge/search",
        "/v1/organization/directory/search",
        "/v1/service/organization/glossary/resolve",
        "/v1/service/organization/knowledge/search",
        "/v1/service/organization/directory/search",
    }
    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP and PROJECT_VERSION == info.version == VERSION,
        "runtime_info_contract_exact": info.organization_context_foundation_implemented is True
        and info.organization_context_route_schema == "okcanvas-assistant-route-v2"
        and info.organization_context_external_sync_configured is False,
        "default_catalog_empty_and_valid": default_catalog.state is OrganizationCatalogState.EMPTY
        and default_catalog.record_count == 0,
        "fixture_catalog_ready_and_exact": ready.catalog.state is OrganizationCatalogState.READY
        and ready.catalog.record_count == 4
        and len(ready.catalog.glossary_records) == 1
        and len(ready.catalog.knowledge_records) == 1
        and len(ready.catalog.directory_records) == 2,
        "manifest_hashes_bound": all(
            len(value) == 64
            for value in (
                ready.catalog.manifest_sha256,
                ready.catalog.glossary_sha256,
                ready.catalog.knowledge_sha256,
                ready.catalog.directory_sha256,
            )
        ),
        "glossary_exact_match": glossary.authoritative_match_found
        and glossary.matches[0].record_id == "term.pi"
        and glossary.matches[0].source_reference == "org://demo/glossary/pi",
        "knowledge_exact_match": knowledge.authoritative_match_found
        and knowledge.matches[0].record_id == "knowledge.leave-policy",
        "directory_exact_match": directory.authoritative_match_found
        and {item.record_id for item in directory.matches} == {"unit.platform", "person.demo-lead"},
        "cross_tenant_filtering_exact": not hidden.matches and hidden.filtered_count == 4,
        "default_empty_route_fails_closed": default_route.status.value == "NOT_CONFIGURED"
        and not default_route.executable_now
        and default_route.grounding_state == "NOT_CONFIGURED",
        "ready_route_is_grounded_and_executable": ready_route.status.value == "EXECUTABLE"
        and ready_route.executable_now
        and ready_route.grounding_state == "MATCHED"
        and ready_route.grounding is not None
        and ready_route.grounding.matches[0].record_id == "term.pi",
        "no_match_blocks_model_submission": no_match.status.value == "NO_MATCH"
        and not no_match.executable_now
        and no_match.grounding_state == "NO_MATCH",
        "grounding_context_is_authoritative_and_versioned": '"organization_grounding"' in model_request
        and '"authoritative_only": true' in model_request
        and "org://demo/glossary/pi" in model_request
        and "2026.08" in model_request,
        "organization_routes_registered": expected_paths.issubset(paths),
        "routing_policy_promoted": ready_router.policy.policy_id == "organization-assistant-routing-v1"
        and ready_router.policy.version == "1.1.0"
        and ready_router.policy.capabilities["organization-knowledge-read-v1"].availability.value == "AVAILABLE",
        "enterprise_write_remains_unconfigured": info.organization_assistant_enterprise_write_configured is False,
        "durable_automation_remains_unconfigured": info.organization_assistant_durable_automation_configured is False,
        "tool_search_remains_disabled": info.organization_assistant_tool_search_runtime_enabled is False
        and info.organization_assistant_programmatic_tool_calling_runtime_enabled is False,
        "external_sync_not_claimed": info.organization_context_external_sync_configured is False,
        "next_step_exact": info.next_selected_step == "STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION",
    }
    return {
        "schema_version": "okcanvas-step084-organization-context-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "default_catalog": {
            "catalog_id": default_catalog.catalog_id,
            "version": default_catalog.version,
            "state": default_catalog.state.value,
            "record_count": default_catalog.record_count,
        },
        "fixture_catalog": {
            "catalog_id": ready.catalog.catalog_id,
            "version": ready.catalog.version,
            "state": ready.catalog.state.value,
            "record_count": ready.catalog.record_count,
        },
        "runtime_organization_routes": sorted(expected_paths & paths),
        "ready_route": ready_route.to_public_dict(),
        "no_match_route": no_match.to_public_dict(),
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["state"] == "PASSED" else 1)
