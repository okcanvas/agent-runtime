from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
for candidate in (PACKAGE_ROOT,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts.node_acceptance import run_command, run_node_tests, validate_committed_typescript_release

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP069_ACCEPTANCE.json"
STEP = "STEP069_MULTI_USER_SERVICE_CLIENT_CONTRACT_FOUNDATION"
VERSION = "2.49.0"
POLICY_SHA = "693c2586778b3a6a15b4c8a0532f3e11aedce528973c4e4260d30f5ed1719f69"
AUTH_SHA = "b6719235374e07358dead5b4ef7206b68ecc3691a3d913b340df5877e5e4923d"
OWNERSHIP_SHA = "aca56a258921c038fd43fbb4a5ff7c270944c6b06c2b96f67d76918930ea161a"
ROUTES_SHA = "238579db7163e4f8ee48aee3cde59328ec7c91b6cc0a670d92b8bd0070491be3"
CONTRACTS_SHA = "d231fca22d645690d72052ed71489c8a7bf1925afec7ce384df6b2cc19abad2d"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    predecessor = _load_json(ROOT / "docs/evidence/STEP068_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    app_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/app.py")).read_text(encoding="utf-8")
    auth_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/auth.py")).read_text(encoding="utf-8")
    ownership_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/ownership.py")).read_text(encoding="utf-8")
    routes_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/routes.py")).read_text(encoding="utf-8")
    contracts_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/contracts.py")).read_text(encoding="utf-8")
    product_ports = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/product/ports.py")).read_text(encoding="utf-8")
    product_store = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/persistence/sqlite_store.py")).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/plans/ROADMAP.md").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    clients_readme = (ROOT / "clients/cli/README.md").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [sys.executable, "-m", "pytest", "-q",
         "tests/test_step069_multi_user_service_client_contract.py",
         "tests/test_step069_multi_user_service_client_contract_baseline.py"], ROOT
    )
    historical_ok, historical_output = run_command(
        [sys.executable, "-m", "pytest", "-q",
         "tests/test_step068_bounded_local_pdf_image_input.py",
         "tests/test_step068_bounded_local_pdf_image_input_baseline.py",
         "tests/test_governed_run_submission_control_api.py",
         "tests/test_run_submission_boundary.py",
         "tests/test_native_sdk_streaming.py",
         "tests/test_agent_invocation_scope.py"], ROOT
    )
    compile_ok, compile_output = run_command(
        [sys.executable, "-m", "compileall", "-q", "src", "scripts/run_step069_acceptance.py"], ROOT
    )
    release_ok, release_output = validate_committed_typescript_release(ROOT / "clients/cli")
    node_ok, node_output = run_node_tests(ROOT / "clients/cli")
    no_reference_imports_ok, no_reference_imports_output = run_command(
        [sys.executable, "scripts/verify_no_reference_imports.py"], ROOT
    )
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    required_docs = [
        ROOT / "docs/plans/STEP069_MULTI_USER_SERVICE_CLIENT_CONTRACT_FOUNDATION.md",
        ROOT / "docs/reference/STEP069_MULTI_USER_SERVICE_CLIENT_CONTRACT_FOUNDATION_CODE_AUDIT.md",
        ROOT / "docs/26-MULTI-USER-SERVICE-CLIENT-API.md",
        ROOT / "docs/evidence/STEP068_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "specs/service_clients/contracts/MULTI_USER_SERVICE_CLIENT_V1.md",
        ROOT / "specs/service_clients/contracts/SERVICE_CLIENT_TOKEN_REGISTRY_V1.md",
        ROOT / "specs/service_clients/service-client-policy.json",
        ROOT / "agent-cli/README.md", ROOT / "agent-web/README.md", ROOT / "agent-desktop/README.md",
        ROOT / "clients/README.md", ROOT / "HANDOFF.md", ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md", ROOT / "README.md",
    ]

    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step068_windows_live_closure_exact": (
            predecessor.get("reported_state") == "PASSED"
            and predecessor.get("reported_passed_checks") == 30
            and predecessor.get("reported_total_checks") == 30
            and info.bounded_local_attachment_windows_live_accepted is True
        ),
        "multi_user_server_runtime_flags_exact": (
            info.multi_user_server_runtime_implemented is True
            and info.service_client_contract_implemented is True
            and info.service_client_api_prefix == "/v1/service"
            and info.control_api_mode == "local-admin-development-and-multi-user-service"
            and "multi_user_server_runtime_implemented" in model_source
        ),
        "service_policy_identity_sha_and_scope_exact": (
            _sha(ROOT / "specs/service_clients/service-client-policy.json") == POLICY_SHA
            and policy.get("policy_id") == "multi-user-service-client-contract-v1"
            and policy.get("api_prefix") == "/v1/service"
            and policy.get("resource_scope") == "tenant-and-principal"
            and policy.get("cross_scope_disclosure_status") == 404
        ),
        "service_runtime_source_hashes_exact": (
            _sha(legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/auth.py")) == AUTH_SHA
            and _sha(legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/ownership.py")) == OWNERSHIP_SHA
            and _sha(legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/routes.py")) == ROUTES_SHA
            and _sha(legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/contracts.py")) == CONTRACTS_SHA
        ),
        "bearer_registry_external_hash_only_exact": (
            policy.get("token_registry_environment") == "OKCANVAS_SERVICE_CLIENT_TOKEN_REGISTRY_JSON"
            and policy.get("raw_bearer_tokens_persisted") is False
            and "token_sha256" in auth_source and "hmac.compare_digest" in auth_source
            and "raw_token" not in auth_source
            and "OKCANVAS_SERVICE_CLIENT_TOKEN_REGISTRY_JSON" in app_source
        ),
        "service_roles_exact": policy.get("roles") == ["agent-user", "approval-operator"],
        "resource_ownership_projection_exact": (
            "CREATE TABLE IF NOT EXISTS service_resource_owner" in ownership_source
            and set(policy.get("owned_resource_types", [])) == {
                "attachment-slot", "session", "submission", "task", "run", "approval"
            }
            and "PRIMARY KEY(resource_type, resource_id)" in ownership_source
        ),
        "cross_scope_404_non_disclosure_exact": (
            info.service_client_cross_scope_disclosure_status == 404
            and ownership_source.count('ControlAPIError(404, "SERVICE_RESOURCE_NOT_FOUND"') >= 3
        ),
        "principal_namespaced_idempotency_exact": (
            policy.get("idempotency_namespace") == "tenant-principal-sha256"
            and "principal.tenant_id" in routes_source and "principal.principal_id" in routes_source
            and 'return f"service-{digest}"' in routes_source
        ),
        "service_prefix_capability_and_identity_routes_present": (
            'APIRouter(prefix="/v1/service"' in routes_source
            and '@router.get("/capabilities"' in routes_source
            and '@router.get("/error-contract"' in routes_source
            and '@router.get("/whoami"' in routes_source
        ),
        "service_agent_and_session_routes_present": (
            '@router.get("/agent-definitions"' in routes_source
            and '@router.post("/sessions"' in routes_source
            and '@router.get("/sessions/{session_id}"' in routes_source
            and '@router.post("/sessions/{session_id}/clear"' in routes_source
        ),
        "service_attachment_and_submission_routes_present": (
            '@router.post("/local-attachments"' in routes_source
            and '@router.post("/run-submissions/preflight"' in routes_source
            and '@router.post("/run-submissions/{submission_id}/confirm"' in routes_source
        ),
        "tenant_approval_operator_separation_present": (
            '@router.get("/tool-approvals"' in routes_source
            and 'ServiceClientRole.APPROVAL_OPERATOR' in routes_source
            and 'require_tenant' in routes_source
        ),
        "persisted_sse_service_contract_exact": (
            policy.get("durable_event_stream") == "persisted-sse-last-event-id"
            and '@router.get("/runs/{run_id}/events/stream")' in routes_source
            and "persisted_event_stream" in routes_source and "Last-Event-ID" in routes_source
        ),
        "native_sdk_stream_not_exposed": (
            info.service_client_native_sdk_stream_exposed is False
            and policy.get("native_sdk_stream_exposed") is False
            and "run_streamed" not in routes_source and "sdk-stream" not in routes_source
        ),
        "artifact_list_and_verified_detail_present": (
            "def list_artifacts" in product_ports and "def list_artifacts" in product_store
            and '@router.get("/runs/{run_id}/artifacts"' in routes_source
            and '@router.get("/runs/{run_id}/artifacts/{artifact_id}"' in routes_source
            and "verify_artifact" in routes_source
        ),
        "runtime_storage_direct_access_forbidden": (
            info.service_client_runtime_storage_direct_access is False
            and policy.get("runtime_storage_direct_access") is False
            and "storage_path" not in contracts_source
            and "workspace" not in routes_source.lower()
        ),
        "development_harnesses_not_final_clients": (
            info.development_tui_is_test_harness is True
            and info.development_node_cli_is_test_harness is True
            and "development" in clients_readme.lower() and "future multi-user" in clients_readme.lower()
        ),
        "future_service_client_roots_present": all(
            (ROOT / name / "README.md").is_file() for name in ("agent-cli", "agent-web", "agent-desktop")
        ),
        "skill_foundation_selected_not_implemented": (
            info.product_owned_skill_foundation_implemented is False
            and info.next_selected_step == "STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1"
            and policy.get("skills_available") is False
            and "STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1" in roadmap
            and not (legacy_source_contract(ROOT, "okcanvas_agent_runtime/skills")).exists()
        ),
        "focused_step069_tests_pass": focused_ok and "passed" in focused_output,
        "historical_step068_and_control_tests_pass": historical_ok and "passed" in historical_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step069_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launcher_present": (
            (ROOT / "sh_run_step069_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step069_acceptance.py").is_file()
        ),
        "step070_selected_but_not_implemented": (
            "Selected next STEP" in handoff and "not implemented" in handoff
            and "STEP070 must not begin" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        ),
    }
    passed = sum(1 for value in checks.values() if value)
    payload = {
        "schema_version": "okcanvas-step069-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if passed == len(checks) else "FAILED",
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "service_contract": {
            "api_prefix": policy.get("api_prefix"),
            "authentication": policy.get("authentication"),
            "resource_scope": policy.get("resource_scope"),
            "cross_scope_disclosure_status": policy.get("cross_scope_disclosure_status"),
            "roles": policy.get("roles"),
            "supported_clients": policy.get("supported_clients"),
            "native_sdk_stream_exposed": policy.get("native_sdk_stream_exposed"),
            "runtime_storage_direct_access": policy.get("runtime_storage_direct_access"),
        },
        "next_selected_step": info.next_selected_step,
        "focused_test_output": focused_output[-4000:],
        "historical_test_output": historical_output[-4000:],
        "python_compile_output": compile_output[-2000:],
        "node_release_output": release_output[-2000:],
        "node_test_output_tail": node_output[-4000:],
        "reference_import_output_tail": no_reference_imports_output[-2000:],
        "reference_count": len(reference_results),
        "external_network_calls": 0,
        "model_calls": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
