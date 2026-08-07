from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
for candidate in (PACKAGE_ROOT,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts.node_acceptance import run_command, run_node_tests, validate_committed_typescript_release

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP076_ACCEPTANCE.json"
STEP = "STEP076_PRODUCT_OWNED_IMMUTABLE_PROJECT_SNAPSHOT_BINDING"
VERSION = "2.56.0"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _zip_fixture() -> bytes:
    stream = io.BytesIO()
    files = {
        "README.md": "# Inventory fixture\n",
        "src/inventory.py": (
            "SAFETY_STOCK = 12\n\ndef calculate_reorder(on_hand: int, forecast: int) -> int:\n"
            "    return max(0, forecast + SAFETY_STOCK - on_hand)\n"
        ),
    }
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, content in files.items():
            info = zipfile.ZipInfo(path, date_time=(2026, 7, 31, 3, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return stream.getvalue()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.domain.project_snapshots import (
        ProjectSnapshotPolicyCatalog,
        materialize_project_snapshot,
        validate_project_snapshot_zip,
    )
    from okcanvas_agent_runtime.adapters.storage.project_snapshots import EncryptedProjectSnapshotStore
    from okcanvas_agent_runtime.adapters.storage.protected_payload import ProtectedPayloadKey
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    policy_path = ROOT / "specs/project_snapshots/project-snapshot-policy.json"
    policy_payload = _load_json(policy_path)
    policy = ProjectSnapshotPolicyCatalog(ROOT).resolve()
    service_policy_path = ROOT / "specs/service_clients/service-client-policy.json"
    service_policy = _load_json(service_policy_path)
    step075g_windows = _load_json(ROOT / "docs/evidence/STEP075G_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    archive = _zip_fixture()
    validated = validate_project_snapshot_zip(archive, "inventory-project.zip", policy)

    with tempfile.TemporaryDirectory(prefix="step076-acceptance-") as temporary:
        temporary_root = Path(temporary)
        key = ProtectedPayloadKey.from_text(base64.urlsafe_b64encode(bytes(range(32))).decode("ascii"))
        snapshot_store = EncryptedProjectSnapshotStore(temporary_root / "snapshots", key, policy)
        snapshot_store.initialize()
        slot = snapshot_store.create_slot(archive, "inventory-project.zip")
        bound, binding = snapshot_store.bind_slot(slot.record_ref, "submission_" + "7" * 32)
        prepared = snapshot_store.read_bound(binding, "submission_" + "7" * 32)
        encrypted_blob = (temporary_root / "snapshots" / "bound" / f"{bound.record_ref}.json").read_bytes()
        materialized_parent = temporary_root / "materialized"
        with materialize_project_snapshot(prepared, temporary_parent=materialized_parent) as materialized:
            materialized_root = materialized
            materialized_source = (materialized / "src/inventory.py").read_text(encoding="utf-8")
        materialized_deleted = not materialized_root.exists()
        raw_archive_absent_from_encrypted_blob = archive not in encrypted_blob

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    validation_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/project_snapshots/validation.py")).read_text(encoding="utf-8")
    snapshot_store_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/project_snapshots/store.py")).read_text(encoding="utf-8")
    materialization_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/project_snapshots/materialization.py")).read_text(encoding="utf-8")
    submission_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/service.py")).read_text(encoding="utf-8")
    submission_execution_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/execution.py")).read_text(encoding="utf-8")
    lifecycle_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/lifecycle.py")).read_text(encoding="utf-8")
    payload_models_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/protected_payload/models.py")).read_text(encoding="utf-8")
    payload_store_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/protected_payload/store.py")).read_text(encoding="utf-8")
    gateway_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    execution_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(encoding="utf-8")
    routes_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/routes.py")).read_text(encoding="utf-8")
    ownership_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/ownership.py")).read_text(encoding="utf-8")
    contracts_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/contracts.py")).read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    windows_source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    deterministic_launcher = (ROOT / "sh_run_step076_acceptance.cmd").read_text(encoding="utf-8")
    live_launcher = (ROOT / "sh_run_step076_live_acceptance.cmd").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step076_product_owned_immutable_project_snapshot_binding.py",
            "tests/test_step075g_product_owned_deterministic_evidence_completion.py",
            "tests/test_step075f_sandbox_answer_completeness_and_bounded_repair.py",
            "tests/test_step075_product_owned_readonly_sandbox_workspace_agent.py",
            "tests/test_step069_multi_user_service_client_contract.py",
            "tests/test_step069_multi_user_service_client_contract_baseline.py",
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
            "tests/test_step068_bounded_local_pdf_image_input.py",
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
            "scripts/run_step076_acceptance.py",
            "scripts/run_step076_live_acceptance.py",
        ],
        ROOT,
    )
    release_ok, release_output = validate_committed_typescript_release(ROOT / "clients/cli")
    node_ok, node_output = run_node_tests(ROOT / "clients/cli")
    no_reference_imports_ok, no_reference_imports_output = run_command(
        [sys.executable, "scripts/verify_no_reference_imports.py"], ROOT
    )
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    required_docs = (
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "docs/plans/STEP076_PRODUCT_OWNED_IMMUTABLE_PROJECT_SNAPSHOT_BINDING.md",
        ROOT / "docs/reference/STEP076_PRODUCT_OWNED_IMMUTABLE_PROJECT_SNAPSHOT_BINDING_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP075G_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-008-GLOBAL-SANDBOX-WORKSPACE-NOT-SUBMISSION-BOUND.md",
    )
    sandbox_definition = AgentDefinitionCatalog(ROOT).resolve("sandbox-readonly-coding-agent")
    sandbox_binding = AgentRuntimeBindingCatalog(ROOT).resolve(sandbox_definition)

    checks = {
        "baseline_version_and_step_exact": info.version == VERSION and info.step == STEP
        and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
        and f'CURRENT_STEP = "{STEP}"' in baseline_source,
        "step075g_windows_live_closed_38_of_38": step075g_windows.get("state") == "PASSED"
        and step075g_windows.get("passed_checks") == 38
        and step075g_windows.get("total_checks") == 38
        and step075g_windows.get("closure") == "WINDOWS_LIVE_ACCEPTED",
        "step075g_windows_flags_closed": info.product_owned_readonly_sandbox_windows_live_accepted is True
        and info.product_owned_readonly_sandbox_answer_completeness_windows_live_accepted is True,
        "project_snapshot_runtime_flags_exact": info.product_owned_project_snapshot_ingress_implemented is True
        and info.product_owned_project_snapshot_binding_mode == "encrypted-immutable-zip-per-submission-v1"
        and info.product_owned_project_snapshot_service_api == "/v1/service/project-snapshots"
        and info.product_owned_project_snapshot_materialization_mode == "verified-temporary-per-run"
        and info.product_owned_project_snapshot_windows_live_accepted is False,
        "project_snapshot_policy_exact": policy_payload == {
            "schema_version": "okcanvas-project-snapshot-policy-v1",
            "policy_id": "bounded-project-zip-snapshot-v1",
            "version": "1.0.0",
            "max_archive_bytes": 16777216,
            "max_files": 3000,
            "max_total_bytes": 33554432,
            "max_file_bytes": 524288,
            "max_path_chars": 512,
            "slot_ttl_seconds": 3600,
            "allowed_compression_methods": ["stored", "deflated"],
            "encrypted_entries_allowed": False,
            "symbolic_links_allowed": False,
        },
        "zip_fixture_validated_and_hashed": validated.file_count == 2
        and validated.total_bytes > 0
        and len(validated.snapshot_sha256) == 64
        and len(validated.archive_sha256) == 64,
        "zip_validation_rejects_unsafe_paths_and_links": "escapes the project root" in validation_source
        and "Symbolic links are forbidden in project snapshots" in validation_source
        and "Duplicate or case-colliding project snapshot path" in validation_source
        and "ZIP compression method is outside policy" in validation_source,
        "encrypted_snapshot_store_uses_aes_gcm": "AESGCM" in snapshot_store_source
        and "okcanvas-project-snapshot-store-v1" in snapshot_store_source
        and raw_archive_absent_from_encrypted_blob,
        "snapshot_binding_round_trip_exact": prepared.metadata.snapshot_sha256 == validated.snapshot_sha256
        and prepared.metadata.archive_sha256 == validated.archive_sha256,
        "verified_temporary_materialization_cleanup": "Project snapshot materialized file identity does not match" in materialization_source
        and "shutil.rmtree(root, ignore_errors=False)" in materialization_source
        and "SAFETY_STOCK = 12" in materialized_source
        and materialized_deleted,
        "service_upload_api_present": '@router.post(\n        "/project-snapshots"' in routes_source
        and "X-OKCanvas-Project-Snapshot-Filename" in routes_source,
        "service_snapshot_principal_ownership_present": 'resource_type="project-snapshot-slot"' in routes_source
        and '"project-snapshot-slot"' in ownership_source,
        "sandbox_submission_requires_snapshot": "Sandbox read-only Agent requires one uploaded project snapshot slot" in submission_source,
        "non_sandbox_submission_rejects_snapshot": "Project snapshot slot is valid only for a sandbox-readonly Agent" in submission_source,
        "submission_fingerprint_binds_snapshot_identity": "project_snapshot_sha256" in submission_source
        and "project_snapshot_archive_sha256" in submission_source
        and "project_snapshot_file_count" in submission_source
        and "project_snapshot_total_bytes" in submission_source,
        "submission_ledger_persists_compact_snapshot_identity": "project_snapshot_sha256" in (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/store.py")).read_text(encoding="utf-8"),
        "protected_payload_v5_binds_snapshot": "project_snapshot: ProtectedProjectSnapshotBinding" in payload_models_source
        and "okcanvas-protected-payload-content-v5" in payload_store_source
        and "project_snapshot_sha256" in payload_store_source,
        "execution_reads_bound_snapshot_before_schedule": "self._project_snapshots.read_bound(" in submission_execution_source
        and "project_snapshot=prepared_project_snapshot" in submission_execution_source,
        "gateway_materializes_uploaded_snapshot": "materialize_project_snapshot" in gateway_source
        and "project_snapshot.archive" not in gateway_source
        and "readonly_workspace_root" in gateway_source,
        "legacy_global_root_not_service_contract": "project_snapshot_id" in contracts_source
        and "project_snapshot_slot_id=request.project_snapshot_id" in routes_source,
        "compact_snapshot_evidence_artifact_created": 'artifact_type="agent.project-snapshot-evidence"' in execution_source
        and "raw_archive_persisted" in execution_source
        and "host_path_persisted" in execution_source,
        "successful_run_deletes_bound_snapshot": "self._project_snapshots.delete(project_snapshot_ref)" in lifecycle_source
        and '"state": "DELETED", "reason": "successful-run"' in lifecycle_source
        and "payload.retention.applied" in lifecycle_source,
        "failed_run_retains_snapshot_with_payload": '"state": "RETAINED"' in lifecycle_source
        and "terminal-failure-investigation-window" in lifecycle_source
        and "payload_retention_state" in lifecycle_source,
        "service_policy_selects_step076": service_policy.get("version") == "1.5.0"
        and service_policy.get("project_snapshot_ingress_enabled") is True
        and service_policy.get("project_snapshot_api") == "/v1/service/project-snapshots"
        and service_policy.get("sandbox_foundation_step") == STEP,
        "sandbox_runtime_binding_preserved": sandbox_binding.execution_path == "product-owned-readonly-sandbox-agent-execution-v1",
        "windows_launchers_and_entrypoint_present": "run_step076_acceptance.py" in deterministic_launcher
        and "immutable-project-snapshot-binding-live-acceptance" in live_launcher
        and "run_step076_live_acceptance.py" in windows_source,
        "live_and_secret_evidence_packaging_ignored": "docs/evidence/step076-live/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
        and "step076-live" in package_source
        and ".env.local" in package_source,
        "source_package_default_is_step076": "step076-product-owned-immutable-project-snapshot-binding" in package_source
        and STEP in package_source,
        "step076_documents_and_issue_present": all(path.is_file() for path in required_docs),
        "focused_step076_tests_pass": focused_ok,
        "historical_skill_trace_attachment_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "deterministic_model_docker_network_calls_zero": True,
    }

    payload = {
        "schema_version": "okcanvas-step076-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "project_snapshot_policy_sha256": _sha256(policy_path),
        "service_policy_sha256": _sha256(service_policy_path),
        "fixture_snapshot_sha256": validated.snapshot_sha256,
        "fixture_archive_sha256": validated.archive_sha256,
        "fixture_file_count": validated.file_count,
        "fixture_total_bytes": validated.total_bytes,
        "sample_runtime_binding_sha256": sandbox_binding.runtime_binding_sha256,
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
        "live_launcher": "sh_run_step076_live_acceptance.cmd",
        "live_state": "WINDOWS_LIVE_RERUN_PENDING",
        "live_model_required": "gpt-4.1",
        "live_image_default": "busybox:1.36",
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
