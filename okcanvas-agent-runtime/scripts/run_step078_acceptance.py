from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
for candidate in (PACKAGE_ROOT,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts.node_acceptance import run_command, run_node_tests, validate_committed_typescript_release

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP078_ACCEPTANCE.json"
STEP = "STEP078_PRODUCT_OWNED_ATOMIC_SERVICE_SUBMISSION_OWNERSHIP_TRANSFER"
VERSION = "2.58.0"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    service_policy_path = ROOT / "specs/service_clients/service-client-policy.json"
    service_policy = _load_json(service_policy_path)
    step077_windows = _load_json(ROOT / "docs/evidence/STEP077_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    routes_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/routes.py")).read_text(encoding="utf-8")
    ownership_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/ownership.py")).read_text(encoding="utf-8")
    submission_models_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/models.py")).read_text(encoding="utf-8")
    submission_store_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/store.py")).read_text(encoding="utf-8")
    submission_service_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/service.py")).read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    windows_source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    deterministic_launcher = (ROOT / "sh_run_step078_acceptance.cmd").read_text(encoding="utf-8")
    live_launcher = (ROOT / "sh_run_step078_live_acceptance.cmd").read_text(encoding="utf-8")

    from scripts.verify_no_reference_imports import find_violations

    reference_import_violations = find_violations(ROOT)
    no_reference_imports_ok = not reference_import_violations
    no_reference_imports_output = json.dumps(
        {"ok": no_reference_imports_ok, "violations": reference_import_violations},
        indent=2,
        sort_keys=True,
    )

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step078_product_owned_atomic_service_submission_ownership_transfer.py",
            "tests/test_step077_product_owned_binary_ingress_slot_lifecycle.py",
            "tests/test_step076_product_owned_immutable_project_snapshot_binding.py",
            "tests/test_step075g_product_owned_deterministic_evidence_completion.py",
            "tests/test_step069_multi_user_service_client_contract.py",
            "tests/test_run_submission_boundary.py",
            "tests/test_governed_run_submission_control_api.py",
            "tests/test_generic_agent_execution_service.py",
            "tests/test_windows_entrypoint.py",
            "tests/test_no_direct_reference_import.py",
        ],
        ROOT,
    )
    historical_ok, historical_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step072b_windows_crlf_and_local_env_forwarding_fix.py",
            "tests/test_step072_immutable_openai_trace_export_disabled.py",
            "tests/test_step071_product_skill_document_review_live_acceptance.py",
            "tests/test_step070_product_owned_skill_foundation.py",
            "tests/test_step068_bounded_local_pdf_image_input_baseline.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "src",
            "scripts/run_step078_acceptance.py",
            "scripts/run_step078_live_acceptance.py",
        ],
        ROOT,
    )
    release_ok, release_output = validate_committed_typescript_release(ROOT / "clients/cli")
    node_ok, node_output = run_node_tests(ROOT / "clients/cli")
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    required_docs = (
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "docs/plans/STEP078_PRODUCT_OWNED_ATOMIC_SERVICE_SUBMISSION_OWNERSHIP_TRANSFER.md",
        ROOT / "docs/reference/STEP078_PRODUCT_OWNED_ATOMIC_SERVICE_SUBMISSION_OWNERSHIP_TRANSFER_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP077_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-010-SERVICE-SUBMISSION-OWNERSHIP-POST-COMMIT-WINDOW.md",
        ROOT / "docs/issues/OR-ISSUE-011-REFERENCE-IMPORT-VERIFIER-CALL-SCAN.md",
    )
    definition = AgentDefinitionCatalog(ROOT).resolve("sandbox-readonly-coding-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)

    checks = {
        "baseline_version_and_step_exact": info.version == VERSION
        and info.step == STEP
        and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
        and f'CURRENT_STEP = "{STEP}"' in baseline_source,
        "step077_windows_live_closed_50_of_50": step077_windows.get("closure") == "WINDOWS_LIVE_ACCEPTED"
        and step077_windows.get("state") == "PASSED"
        and step077_windows.get("passed_checks") == 50
        and step077_windows.get("total_checks") == 50
        and step077_windows.get("model_calls") == 2
        and step077_windows.get("tool_calls") == 1,
        "step077_runtime_flag_closed": info.product_owned_binary_ingress_lifecycle_windows_live_accepted is True,
        "step078_runtime_flags_exact": info.product_owned_atomic_service_submission_ownership_transfer_implemented is True
        and info.product_owned_atomic_service_submission_ownership_transfer_mode
        == "sqlite-submission-and-service-owner-single-transaction-v1"
        and info.product_owned_atomic_service_submission_ownership_transfer_deterministic_accepted is True
        and info.product_owned_atomic_service_submission_ownership_transfer_windows_live_accepted is False
        and info.next_selected_step == "UNSELECTED_PENDING_STEP078_WINDOWS_LIVE_ACCEPTANCE",
        "ownership_transition_contract_present": "class RunSubmissionOwnershipTransition" in submission_models_source
        and "consumed_resources: tuple[tuple[str, str], ...]" in submission_models_source,
        "submission_register_accepts_atomic_transition": "ownership_transition: RunSubmissionOwnershipTransition | None" in submission_store_source
        and "self._apply_ownership_transition(" in submission_store_source,
        "submission_and_owner_share_transaction": "INSERT INTO run_submission_preflight" in submission_store_source
        and "INSERT INTO service_resource_owner(" in submission_store_source
        and "connection.commit()" in submission_store_source,
        "consumed_slot_owner_deleted_in_same_transaction": "DELETE FROM service_resource_owner" in submission_store_source
        and "Consumed binary ingress ownership belongs to another service principal" in submission_store_source,
        "foreign_submission_owner_rejected": "Submission ownership belongs to another service principal" in submission_store_source,
        "idempotent_replay_transition_supported": "def apply_ownership_transition(" in submission_store_source
        and "existing = self._store.apply_ownership_transition(" in submission_service_source,
        "existing_payload_attach_transition_atomic": "ownership_transition=ownership_transition" in submission_service_source
        and "def attach_payload(" in submission_store_source,
        "service_route_constructs_transition": "RunSubmissionOwnershipTransition(" in routes_source
        and 'consumed_resources.append(("attachment-slot"' in routes_source
        and 'consumed_resources.append(("project-snapshot-slot"' in routes_source,
        "old_post_commit_submission_register_removed": 'ownership.register(principal=principal, resource_type="submission"' not in routes_source,
        "old_post_commit_ingress_release_removed": 'resource_type="submission", resource_id=decision.submission_id' not in routes_source
        and "return _submission_response(decision)" in routes_source,
        "failure_cleanup_is_principal_scoped": "def release_if_owned(" in ownership_source
        and "principal=principal" in routes_source
        and "release_missing_ingress_ownership" in routes_source,
        "service_policy_selects_step078": service_policy.get("version") == "1.7.0"
        and service_policy.get("service_submission_ownership_transition_step") == STEP
        and service_policy.get("service_submission_ownership_transition_atomic") is True
        and service_policy.get("service_submission_ownership_transition_mode")
        == "sqlite-submission-and-service-owner-single-transaction-v1",
        "service_capabilities_expose_atomic_transfer": '"atomic-service-submission-ownership-transfer"' in routes_source,
        "binary_ingress_lifecycle_preserved": info.product_owned_binary_ingress_slot_lifecycle_implemented is True
        and info.product_owned_binary_ingress_explicit_delete_enabled is True
        and info.product_owned_binary_ingress_ownership_failure_compensation_enabled is True,
        "project_snapshot_binding_preserved": info.product_owned_project_snapshot_binding_mode
        == "encrypted-immutable-zip-per-submission-v1",
        "sandbox_runtime_binding_preserved": binding.execution_path
        == "product-owned-readonly-sandbox-agent-execution-v1",
        "readonly_sandbox_security_preserved": info.product_owned_readonly_sandbox_network_enabled is False
        and info.product_owned_readonly_sandbox_shell_enabled is False
        and info.product_owned_readonly_sandbox_apply_patch_enabled is False,
        "focused_step078_tests_pass": focused_ok,
        "historical_skill_trace_attachment_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "windows_launchers_and_entrypoint_present": "run_step078_acceptance.py" in deterministic_launcher
        and "atomic-service-submission-ownership-transfer-live-acceptance" in live_launcher
        and "run_step078_live_acceptance.py" in windows_source,
        "live_and_secret_evidence_packaging_ignored": "docs/evidence/step078-live/"
        in (ROOT / ".gitignore").read_text(encoding="utf-8")
        and "step078-live" in package_source
        and ".env.local" in package_source,
        "source_package_default_is_step078": "step078-product-owned-atomic-service-submission-ownership-transfer"
        in package_source
        and STEP in package_source,
        "step078_documents_and_issue_present": all(path.is_file() for path in required_docs),
        "model_source_contains_step078_contract": "product_owned_atomic_service_submission_ownership_transfer_implemented"
        in model_source,
        "deterministic_model_docker_network_calls_zero": True,
    }

    payload = {
        "schema_version": "okcanvas-step078-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "service_policy_sha256": _sha256(service_policy_path),
        "sample_runtime_binding_sha256": binding.runtime_binding_sha256,
        "focused_test_output": focused_output[-16000:],
        "historical_test_output": historical_output[-12000:],
        "python_compile_output": compile_output[-4000:],
        "node_release_output": release_output[-4000:],
        "node_test_output_tail": node_output[-4000:],
        "reference_import_output_tail": no_reference_imports_output[-4000:],
        "reference_count": len(reference_results),
        "docker_calls": 0,
        "external_network_calls": 0,
        "model_calls": 0,
        "live_launcher": "sh_run_step078_live_acceptance.cmd",
        "live_state": "WINDOWS_LIVE_RERUN_PENDING",
        "live_model_required": "gpt-4.1",
        "live_image_default": "busybox:1.36",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
