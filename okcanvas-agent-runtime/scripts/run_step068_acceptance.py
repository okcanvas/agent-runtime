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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP068_ACCEPTANCE.json"
STEP = "STEP068_BOUNDED_LOCAL_PDF_AND_IMAGE_INPUT_FOUNDATION"
VERSION = "2.48.0"
ATTACHMENT_POLICY_SHA = "1b5b656d1f81a3ab4d32745f297c2c1944009583715c44f66c49a02312b1e579"
MODEL_POLICY_SHA = "a64b711c54b276c42aa74dbb4e80f8a1a76a08302e019c61c097a636bb900324"
SDK_LOCAL_FILE_EXAMPLE_SHA = "9c778baefd9ea58cdf06c2f947fd09bb6025afd721f7a5c2c3399af4e321fc1c"
SDK_LOCAL_IMAGE_EXAMPLE_SHA = "9a32d52ff6016164838d501fd5827a37e30f7903d560827d7f4d0bf0b1e466a5"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.domain.attachments import LocalAttachmentPolicyCatalog, MultimodalModelPolicyCatalog
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    attachment_policy = LocalAttachmentPolicyCatalog(ROOT).resolve()
    model_policy = MultimodalModelPolicyCatalog(ROOT).resolve()
    definition = AgentDefinitionCatalog(ROOT).resolve("local-document-review-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    predecessor = _load_json(ROOT / "docs/evidence/STEP067_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    validation_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/attachments/validation.py")).read_text(encoding="utf-8")
    store_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/attachments/store.py")).read_text(encoding="utf-8")
    protected_models = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/protected_payload/models.py")).read_text(encoding="utf-8")
    protected_store = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/protected_payload/store.py")).read_text(encoding="utf-8")
    gateway_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    service_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(encoding="utf-8")
    submission_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/service.py")).read_text(encoding="utf-8")
    execution_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/execution.py")).read_text(encoding="utf-8")
    lifecycle_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/lifecycle.py")).read_text(encoding="utf-8")
    app_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/app.py")).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/plans/ROADMAP.md").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    product_python = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "okcanvas_agent_runtime").rglob("*.py"))
    )

    focused_ok, focused_output = run_command(
        [
            sys.executable, "-m", "pytest", "-q",
            "tests/test_step068_bounded_local_pdf_image_input.py",
            "tests/test_step068_bounded_local_pdf_image_input_baseline.py",
        ],
        ROOT,
    )
    historical_ok, historical_output = run_command(
        [
            sys.executable, "-m", "pytest", "-q",
            "tests/test_step067_hosted_web_search_foundation.py",
            "tests/test_step066_remote_mcp_streamable_http_foundation.py",
            "tests/test_run_submission_boundary.py",
            "tests/test_governed_run_submission_control_api.py",
            "tests/test_terminal_outcome_reconciliation.py",
            "tests/test_generic_agent_execution_service.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [sys.executable, "-m", "compileall", "-q", "src", "scripts/run_step068_acceptance.py"],
        ROOT,
    )
    release_ok, release_output = validate_committed_typescript_release(ROOT / "clients/cli")
    node_ok, node_output = run_node_tests(ROOT / "clients/cli")
    no_reference_imports_ok, no_reference_imports_output = run_command(
        [sys.executable, "scripts/verify_no_reference_imports.py"], ROOT
    )
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    sdk_file = ROOT / "reference/upstream/openai-agents-python-0.19.0/examples/basic/local_file.py"
    sdk_image = ROOT / "reference/upstream/openai-agents-python-0.19.0/examples/basic/local_image.py"
    required_docs = [
        ROOT / "docs/plans/STEP068_BOUNDED_LOCAL_PDF_AND_IMAGE_INPUT_FOUNDATION.md",
        ROOT / "docs/reference/STEP068_BOUNDED_LOCAL_PDF_AND_IMAGE_INPUT_FOUNDATION_CODE_AUDIT.md",
        ROOT / "docs/25-BOUNDED-LOCAL-PDF-IMAGE-INPUT.md",
        ROOT / "docs/evidence/STEP067_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "specs/attachments/contracts/BOUNDED_LOCAL_PDF_IMAGE_INPUT_V1.md",
        ROOT / "HANDOFF.md", ROOT / "PLANS.md", ROOT / "docs/plans/ROADMAP.md", ROOT / "README.md",
    ]

    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step067_windows_live_closure_exact": (
            predecessor.get("reported_state") == "PASSED"
            and predecessor.get("reported_passed_checks") == 26
            and predecessor.get("reported_total_checks") == 26
            and info.hosted_web_search_windows_live_accepted is True
        ),
        "mvp_roadmap_selects_document_input_before_file_search": (
            "STEP068 — bounded local PDF/PNG/JPEG input: current" in roadmap
            and "Hosted File Search remains post-MVP" in roadmap
            and "STEP069 is not selected" in roadmap
        ),
        "step068_runtime_flags_exact": (
            info.bounded_local_pdf_image_input_implemented is True
            and info.bounded_local_attachment_count == 1
            and info.bounded_local_attachment_max_bytes == 8388608
            and info.bounded_local_attachment_max_pdf_pages == 50
            and info.bounded_local_attachment_remote_urls_enabled is False
            and info.bounded_local_attachment_provider_file_ids_enabled is False
            and info.bounded_local_attachment_raw_bytes_in_events is False
            and info.bounded_local_attachment_raw_bytes_in_artifacts is False
            and info.bounded_local_attachment_encrypted_store_implemented is True
            and info.bounded_local_attachment_allowed_model_ids == "gpt-4.1"
            and info.bounded_local_attachment_deterministic_accepted is True
            and info.bounded_local_attachment_windows_live_accepted is False
            and "bounded_local_pdf_image_input_implemented" in model_source
        ),
        "attachment_policy_identity_sha_and_bounds_exact": (
            attachment_policy.policy_sha256 == ATTACHMENT_POLICY_SHA
            and attachment_policy.max_attachments == 1
            and attachment_policy.max_bytes == 8388608
            and attachment_policy.allowed_media_types == ("application/pdf", "image/png", "image/jpeg")
            and attachment_policy.max_pdf_pages == 50
            and attachment_policy.max_image_pixels == 20000000
            and attachment_policy.remote_urls_allowed is False
            and attachment_policy.provider_file_ids_allowed is False
        ),
        "multimodal_model_policy_exact": (
            model_policy.policy_sha256 == MODEL_POLICY_SHA
            and model_policy.provider_id == "openai"
            and model_policy.api == "responses"
            and model_policy.allowed_model_ids == ("gpt-4.1",)
            and model_policy.input_file is True
            and model_policy.input_image is True
            and model_policy.structured_output is True
            and model_policy.store is False
        ),
        "local_document_agent_isolated_and_strict": (
            definition.input_mode == "local-attachment-v1"
            and definition.output_contract == "LocalDocumentReviewResult"
            and definition.max_turns == 1 and definition.session_mode == "disabled"
            and not definition.tools and not definition.mcp_servers and not definition.hosted_tools
            and not definition.handoffs and not definition.agent_tools
            and not definition.orchestration_children and not definition.guardrails
            and definition.workspace_access == "none"
        ),
        "signature_and_structural_validation_present": (
            "%PDF-" in validation_source and "%%EOF" in validation_source and "/Encrypt" in validation_source
            and "IHDR" in validation_source and "IEND" in validation_source and "acTL" in validation_source
            and "JPEG dimensions were not found" in validation_source
            and "Image pixel count exceeds policy" in validation_source
        ),
        "encrypted_attachment_store_separate_domain_exact": (
            "okcanvas-local-attachment-store-v1" in store_source
            and "AES-256-GCM" in store_source
            and "derive_subkey" in protected_store
            and 'record_type="slot"' in store_source
            and 'record_type="bound"' in store_source
            and "bind_slot" in store_source and "read_bound" in store_source
        ),
        "protected_payload_v4_binds_metadata_not_bytes": (
            "okcanvas-protected-payload-content-v4" in protected_models
            and "ProtectedAttachmentBinding" in protected_models
            and "attachment_sha256" in protected_store
            and "attachment.data" not in protected_models
        ),
        "one_time_upload_and_governed_preflight_present": (
            '"/v1/local-attachments"' in app_source
            and "X-OKCanvas-Attachment-Filename" in app_source
            and "request.stream()" in app_source
            and "attachment_slot_id=request.attachment_id" in app_source
            and "bind_slot" in submission_source
        ),
        "idempotency_race_fails_closed": (
            "Concurrent attachment preflight must be retried with a new upload slot" in submission_source
        ),
        "sdk_direct_local_examples_exact": (
            _sha256(sdk_file) == SDK_LOCAL_FILE_EXAMPLE_SHA
            and _sha256(sdk_image) == SDK_LOCAL_IMAGE_EXAMPLE_SHA
        ),
        "typed_sdk_input_file_and_image_present": (
            '"type": "input_file"' in gateway_source
            and '"file_data": f"data:{attachment.metadata.media_type};base64,{encoded}"' in gateway_source
            and '"type": "input_image"' in gateway_source
            and '"image_url": f"data:{attachment.metadata.media_type};base64,{encoded}"' in gateway_source
            and "runner_input = [" in gateway_source
        ),
        "text_only_agents_remain_string_only": (
            "elif attachment is not None" in gateway_source
            and "Text-only Agent cannot receive a local attachment" in gateway_source
            and 'else:\n                runner_input = (' in gateway_source
        ),
        "runtime_binding_attachment_policy_bound": (
            binding.execution_path == "bounded-local-pdf-image-input-execution-v1"
            and binding.attachment_policy.get("policy_sha256") == ATTACHMENT_POLICY_SHA
            and binding.multimodal_model_policy.get("policy_sha256") == MODEL_POLICY_SHA
            and bool(binding.attachment_runtime_sha256)
        ),
        "execution_decrypts_only_at_schedule_time": (
            "read_bound" in execution_source and "attachment=prepared_attachment" in execution_source
        ),
        "metadata_only_attachment_artifact_present": (
            '"agent.local-attachment-evidence"' in service_source
            and '"local-attachment-evidence.json"' in service_source
            and '"raw_attachment_persisted": False' in service_source
            and "to_evidence_dict" in service_source
        ),
        "attachment_retention_follows_payload_cleanup": (
            "payload.attachment.attachment_ref" in lifecycle_source
            and "self._attachments.delete(attachment_ref)" in lifecycle_source
        ),
        "file_search_and_provider_resource_lifecycle_not_implemented": (
            "FileSearchTool" not in product_python and "vector_store_ids" not in product_python
            and info.hosted_file_search_implemented is False
        ),
        "focused_step068_tests_pass": focused_ok and "passed" in focused_output,
        "historical_text_search_mcp_submission_tests_pass": historical_ok and "passed" in historical_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step068_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launcher_present": (
            (ROOT / "sh_run_step068_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step068_acceptance.py").is_file()
        ),
        "step069_not_selected": "STEP069 remains unselected" in handoff and "STEP069 is not selected" in roadmap,
    }
    passed = sum(1 for value in checks.values() if value)
    payload = {
        "schema_version": "okcanvas-step068-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if passed == len(checks) else "FAILED",
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "attachment_policy": attachment_policy.to_binding_dict(),
        "multimodal_model_policy": model_policy.to_binding_dict(),
        "focused_test_output": focused_output[-2000:],
        "historical_test_output": historical_output[-2000:],
        "python_compile_output": compile_output[-1000:],
        "node_release_output": release_output[-1000:],
        "node_test_output_tail": node_output[-1000:],
        "reference_import_output_tail": no_reference_imports_output[-1000:],
        "reference_count": len(reference_results),
        "external_network_calls": 0,
        "model_calls": 0,
        "file_search_implemented": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
