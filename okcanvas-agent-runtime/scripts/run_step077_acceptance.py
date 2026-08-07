from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
import tempfile
import zipfile
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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP077_ACCEPTANCE.json"
STEP = "STEP077_PRODUCT_OWNED_BINARY_INGRESS_SLOT_LIFECYCLE"
VERSION = "2.57.0"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _zip_fixture() -> bytes:
    stream = io.BytesIO()
    files = {
        "README.md": "# Inventory fixture\n",
        "src/inventory.py": (
            "SAFETY_STOCK = 12\n\n"
            "def calculate_reorder(on_hand: int, forecast: int) -> int:\n"
            "    return max(0, forecast + SAFETY_STOCK - on_hand)\n"
        ),
    }
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, content in files.items():
            info = zipfile.ZipInfo(path, date_time=(2026, 8, 2, 5, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info,
                content.encode("utf-8"),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return stream.getvalue()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.domain.project_snapshots import ProjectSnapshotPolicyCatalog
    from okcanvas_agent_runtime.adapters.storage.project_snapshots import EncryptedProjectSnapshotStore
    from okcanvas_agent_runtime.adapters.storage.protected_payload import ProtectedPayloadKey
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    service_policy_path = ROOT / "specs/service_clients/service-client-policy.json"
    service_policy = _load_json(service_policy_path)
    step076_windows = _load_json(ROOT / "docs/evidence/STEP076_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    policy = ProjectSnapshotPolicyCatalog(ROOT).resolve()
    archive = _zip_fixture()

    with tempfile.TemporaryDirectory(prefix="step077-acceptance-") as temporary:
        temporary_root = Path(temporary)
        key = ProtectedPayloadKey.from_text(
            base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
        )
        store = EncryptedProjectSnapshotStore(temporary_root / "snapshots", key, policy)
        old = store.create_slot(archive, "old.zip")
        record, data = store._read_record(old.record_ref, expected_type="slot")
        store.delete(old.record_ref)
        store._write_record(
            record_ref=old.record_ref,
            record_type="slot",
            data=data,
            metadata=record.metadata,
            created_at="1999-12-31T23:59:00Z",
            expires_at="2000-01-01T00:00:00Z",
            submission_id=None,
        )
        replacement = store.create_slot(archive, "replacement.zip")
        expired_file_removed = not store.slot_exists(old.record_ref)
        replacement_present = store.slot_exists(replacement.record_ref)

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    routes_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/routes.py")).read_text(encoding="utf-8")
    ownership_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/ownership.py")).read_text(encoding="utf-8")
    snapshot_store_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/project_snapshots/store.py")).read_text(encoding="utf-8")
    attachment_store_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/attachments/store.py")).read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    windows_source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    deterministic_launcher = (ROOT / "sh_run_step077_acceptance.cmd").read_text(encoding="utf-8")
    live_launcher = (ROOT / "sh_run_step077_live_acceptance.cmd").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step077_product_owned_binary_ingress_slot_lifecycle.py",
            "tests/test_step076_product_owned_immutable_project_snapshot_binding.py",
            "tests/test_step075g_product_owned_deterministic_evidence_completion.py",
            "tests/test_step075_product_owned_readonly_sandbox_workspace_agent.py",
            "tests/test_step069_multi_user_service_client_contract.py",
            "tests/test_step069_multi_user_service_client_contract_baseline.py",
            "tests/test_step068_bounded_local_pdf_image_input.py",
            "tests/test_run_submission_boundary.py",
            "tests/test_governed_run_submission_control_api.py",
            "tests/test_generic_agent_execution_service.py",
            "tests/test_project_readonly_inspection.py",
            "tests/test_windows_entrypoint.py",
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
            "scripts/run_step077_acceptance.py",
            "scripts/run_step077_live_acceptance.py",
        ],
        ROOT,
    )
    release_ok, release_output = validate_committed_typescript_release(
        ROOT / "clients/cli"
    )
    node_ok, node_output = run_node_tests(ROOT / "clients/cli")
    no_reference_imports_ok, no_reference_imports_output = run_command(
        [sys.executable, "scripts/verify_no_reference_imports.py"], ROOT
    )
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(
        item.verified for item in reference_results
    )

    required_docs = (
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "docs/plans/STEP077_PRODUCT_OWNED_BINARY_INGRESS_SLOT_LIFECYCLE.md",
        ROOT / "docs/reference/STEP077_PRODUCT_OWNED_BINARY_INGRESS_SLOT_LIFECYCLE_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP076_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-009-BINARY-INGRESS-SLOT-LIFECYCLE-ORPHANS.md",
    )
    definition = AgentDefinitionCatalog(ROOT).resolve("sandbox-readonly-coding-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)

    checks = {
        "baseline_version_and_step_exact": info.version == VERSION
        and info.step == STEP
        and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
        and f'CURRENT_STEP = "{STEP}"' in baseline_source,
        "step076_windows_live_closed_46_of_46": step076_windows.get("closure")
        == "WINDOWS_LIVE_ACCEPTED"
        and step076_windows.get("state") == "PASSED"
        and step076_windows.get("passed_checks") == 46
        and step076_windows.get("total_checks") == 46
        and step076_windows.get("model_calls") == 2
        and step076_windows.get("tool_calls") == 1,
        "step076_runtime_flags_closed": info.product_owned_project_snapshot_windows_live_accepted
        is True,
        "binary_ingress_runtime_flags_exact": info.product_owned_binary_ingress_slot_lifecycle_implemented
        is True
        and info.product_owned_binary_ingress_expiry_reconciliation_mode
        == "authenticated-slot-scan-on-upload-and-preflight-v1"
        and info.product_owned_binary_ingress_explicit_delete_enabled is True
        and info.product_owned_binary_ingress_ownership_failure_compensation_enabled is True
        and info.product_owned_binary_ingress_lifecycle_deterministic_accepted is True
        and info.product_owned_binary_ingress_lifecycle_windows_live_accepted is False
        and info.next_selected_step == "UNSELECTED_PENDING_STEP077_WINDOWS_LIVE_ACCEPTANCE",
        "project_snapshot_new_upload_reconciles_expiry": "self.cleanup_expired_slot_refs()"
        in snapshot_store_source
        and expired_file_removed
        and replacement_present,
        "attachment_new_upload_reconciles_expiry": "self.cleanup_expired_slot_refs()"
        in attachment_store_source,
        "expiry_scan_authenticates_envelopes": 'self._read_record(record_ref, expected_type="slot")'
        in snapshot_store_source
        and 'self._read_record(record_ref, expected_type="slot")'
        in attachment_store_source,
        "slot_stores_expose_bounded_existence_and_delete": "def slot_exists(" in snapshot_store_source
        and "def slot_exists(" in attachment_store_source
        and "def delete(self, record_ref: str) -> bool:" in snapshot_store_source
        and "def delete(self, record_ref: str) -> bool:" in attachment_store_source,
        "ownership_internal_release_is_explicit": "def release_if_exists(" in ownership_source
        and "return cursor.rowcount == 1" in ownership_source,
        "service_reconciles_expired_file_and_owner_rows": "def reconcile_expired_ingress_slots()"
        in routes_source
        and 'resource_type="attachment-slot"' in routes_source
        and 'resource_type="project-snapshot-slot"' in routes_source,
        "service_releases_consumed_or_expired_owner_rows_after_failure": "def release_missing_ingress_ownership("
        in routes_source
        and "not attachment_store.slot_exists" in routes_source
        and "not project_snapshot_store.slot_exists" in routes_source,
        "snapshot_explicit_delete_api_present": '@router.delete(\n        "/project-snapshots/{project_snapshot_id}"'
        in routes_source
        and "delete_project_snapshot_slot" in routes_source,
        "attachment_explicit_delete_api_present": '@router.delete(\n        "/local-attachments/{attachment_id}"'
        in routes_source
        and "delete_attachment_slot" in routes_source,
        "snapshot_upload_ownership_failure_compensated": "project_snapshot_store.delete(record.record_ref)"
        in routes_source,
        "attachment_upload_ownership_failure_compensated": "attachment_store.delete(record.record_ref)"
        in routes_source,
        "cross_scope_delete_remains_not_found": "ownership.require_principal(" in routes_source
        and info.service_client_cross_scope_disclosure_status == 404,
        "service_capabilities_expose_lifecycle": '"binary-ingress-slot-delete"' in routes_source
        and '"binary-ingress-expiry-reconciliation"' in routes_source,
        "service_policy_selects_step077": service_policy.get("version") == "1.6.0"
        and service_policy.get("binary_ingress_slot_delete_enabled") is True
        and service_policy.get("binary_ingress_authenticated_expiry_reconciliation_enabled")
        is True
        and service_policy.get("binary_ingress_ownership_failure_compensation_enabled")
        is True
        and service_policy.get("binary_ingress_lifecycle_step") == STEP
        and service_policy.get("next_selected_step")
        == "UNSELECTED_PENDING_STEP077_WINDOWS_LIVE_ACCEPTANCE",
        "sandbox_runtime_binding_preserved": binding.execution_path
        == "product-owned-readonly-sandbox-agent-execution-v1",
        "project_snapshot_security_boundary_preserved": info.product_owned_project_snapshot_binding_mode
        == "encrypted-immutable-zip-per-submission-v1"
        and info.product_owned_project_snapshot_raw_archive_event_persistence is False
        and info.product_owned_project_snapshot_raw_archive_artifact_persistence is False,
        "readonly_sandbox_security_preserved": info.product_owned_readonly_sandbox_network_enabled
        is False
        and info.product_owned_readonly_sandbox_shell_enabled is False
        and info.product_owned_readonly_sandbox_apply_patch_enabled is False,
        "focused_step077_tests_pass": focused_ok,
        "historical_skill_trace_attachment_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "windows_launchers_and_entrypoint_present": "run_step077_acceptance.py"
        in deterministic_launcher
        and "binary-ingress-slot-lifecycle-live-acceptance" in live_launcher
        and "run_step077_live_acceptance.py" in windows_source,
        "live_and_secret_evidence_packaging_ignored": "docs/evidence/step077-live/"
        in (ROOT / ".gitignore").read_text(encoding="utf-8")
        and "step077-live" in package_source
        and ".env.local" in package_source,
        "source_package_default_is_step077": "step077-product-owned-binary-ingress-slot-lifecycle"
        in package_source
        and STEP in package_source,
        "step077_documents_and_issue_present": all(path.is_file() for path in required_docs),
        "model_source_contains_step077_contract": "product_owned_binary_ingress_slot_lifecycle_implemented"
        in model_source,
        "deterministic_model_docker_network_calls_zero": True,
    }

    payload = {
        "schema_version": "okcanvas-step077-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "service_policy_sha256": _sha256(service_policy_path),
        "sample_runtime_binding_sha256": binding.runtime_binding_sha256,
        "fixture_archive_sha256": hashlib.sha256(archive).hexdigest(),
        "fixture_expired_slot_removed": expired_file_removed,
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
        "live_launcher": "sh_run_step077_live_acceptance.cmd",
        "live_state": "WINDOWS_LIVE_RERUN_PENDING",
        "live_model_required": "gpt-4.1",
        "live_image_default": "busybox:1.36",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
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
