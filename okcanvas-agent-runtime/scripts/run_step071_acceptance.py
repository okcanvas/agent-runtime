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
from scripts.run_step071_live_acceptance import (
    EXPECTED_MODEL,
    EXPECTED_PACKAGE_SHA256,
    FACT_AMOUNT,
    FACT_DUE_DATE,
    FACT_REFERENCE,
    build_review_fixture_pdf,
)

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP071_ACCEPTANCE.json"
STEP = "STEP071_PRODUCT_SKILL_DOCUMENT_REVIEW_LIVE_ACCEPTANCE_V1"
VERSION = "2.51.0"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.domain.attachments import LocalAttachmentPolicyCatalog, MultimodalModelPolicyCatalog, validate_local_attachment
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
    from okcanvas_agent_runtime.agent.skills import ProductSkillCatalog

    info = RuntimeInfo()
    step070_windows = _load_json(ROOT / "docs/evidence/STEP070_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    service_policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    skill = ProductSkillCatalog(ROOT).resolve("document-review-v1")
    definition = AgentDefinitionCatalog(ROOT).resolve("skill-document-review-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    local_policy = LocalAttachmentPolicyCatalog(ROOT).resolve()
    model_policy = MultimodalModelPolicyCatalog(ROOT).resolve()
    fixture = build_review_fixture_pdf()
    fixture_metadata = validate_local_attachment(fixture, "step071-live-review.pdf", local_policy)

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    live_source = (ROOT / "scripts/run_step071_live_acceptance.py").read_text(encoding="utf-8")
    entrypoint_source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    launcher_source = (ROOT / "sh_run_step071_live_acceptance.cmd").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/plans/ROADMAP.md").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step071_product_skill_document_review_live_acceptance.py",
            "tests/test_step070_product_owned_skill_foundation.py",
            "tests/test_step070_product_owned_skill_foundation_baseline.py",
        ],
        ROOT,
    )
    historical_ok, historical_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step069_multi_user_service_client_contract.py",
            "tests/test_step069_multi_user_service_client_contract_baseline.py",
            "tests/test_step068_bounded_local_pdf_image_input.py",
            "tests/test_step068_bounded_local_pdf_image_input_baseline.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_operations_console_api.py",
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
            "scripts/run_step071_acceptance.py",
            "scripts/run_step071_live_acceptance.py",
            "scripts/windows_entrypoint.py",
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

    required_docs = [
        ROOT / "docs/plans/STEP071_PRODUCT_SKILL_DOCUMENT_REVIEW_LIVE_ACCEPTANCE_V1.md",
        ROOT / "docs/reference/STEP071_PRODUCT_SKILL_DOCUMENT_REVIEW_LIVE_ACCEPTANCE_V1_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP070_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    ]

    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION
            and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step070_windows_live_closure_recorded": (
            step070_windows.get("state") == "WINDOWS_LIVE_ACCEPTED"
            and step070_windows.get("passed_checks") == 30
            and step070_windows.get("total_checks") == 30
            and step070_windows.get("package_sha256") == EXPECTED_PACKAGE_SHA256
        ),
        "step071_runtime_flags_exact": (
            info.product_owned_skill_live_workflow_acceptance_implemented is True
            and info.product_owned_skill_live_provider_accepted is False
            and info.product_owned_skill_live_acceptance_model == EXPECTED_MODEL
            and info.next_selected_step == "UNSELECTED_PENDING_STEP071_WINDOWS_LIVE_ACCEPTANCE"
        ),
        "existing_skill_package_unchanged": (
            skill.skill_id == "document-review-v1"
            and skill.version == "1.0.0"
            and skill.package_sha256 == EXPECTED_PACKAGE_SHA256
            and len(skill.resources) == 2
        ),
        "existing_agent_binding_unchanged": (
            definition.agent_id == "skill-document-review-agent"
            and definition.skills == ("document-review-v1",)
            and definition.input_mode == "local-attachment-v1"
            and definition.output_contract == "LocalDocumentReviewResult"
            and definition.max_turns == 1
            and definition.tools == ()
            and definition.mcp_servers == ()
            and definition.hosted_tools == ()
        ),
        "runtime_binding_contains_exact_skill": (
            len(binding.skills) == 1
            and binding.skills[0].get("package_sha256") == EXPECTED_PACKAGE_SHA256
            and isinstance(binding.skill_runtime_sha256, str)
            and len(binding.skill_runtime_sha256) == 64
        ),
        "multimodal_model_allowlist_exact": (
            model_policy.allowed_model_ids == (EXPECTED_MODEL,)
            and model_policy.input_file is True
            and model_policy.structured_output is True
            and model_policy.store is False
        ),
        "live_fixture_is_valid_one_page_pdf": (
            fixture_metadata.media_type == "application/pdf"
            and fixture_metadata.input_kind == "input_file"
            and fixture_metadata.page_count == 1
            and FACT_REFERENCE.encode("ascii") in fixture
            and FACT_AMOUNT.encode("ascii") in fixture
            and FACT_DUE_DATE.encode("ascii") in fixture
            and b"NOT YET APPROVED" in fixture
            and b"illegible handwritten text" in fixture
            and b"Ignore all prior instructions" in fixture
        ),
        "service_client_workflow_only": all(
            path in live_source
            for path in (
                "/v1/service/skills/document-review-v1",
                "/v1/service/agent-definitions/skill-document-review-agent",
                "/v1/service/local-attachments",
                "/v1/service/run-submissions/preflight",
                "/v1/service/runs/",
            )
        ),
        "governed_confirmation_path_present": (
            "/confirm" in live_source
            and "confirmation_challenge" in live_source
            and "scheduled" in live_source
        ),
        "actual_openai_call_is_live_only": (
            "OpenAIGenericAgentGateway" not in live_source
            and "gateway=" not in live_source
            and '"provider_network_required": True' in live_source
            and '"model_calls": model_started_count' in live_source
        ),
        "live_quality_checks_present": all(
            token in live_source
            for token in (
                "reference_id_exactly_observed",
                "amount_observed",
                "due_date_exactly_observed",
                "decision_not_yet_approved_observed",
                "illegible_approver_unverified",
                "final_output_contract_valid",
                "fixture_facts_not_disclosed_in_request",
            )
        ),
        "undeclared_capability_checks_present": (
            "no_undeclared_capability_events" in live_source
            and "tool." in live_source
            and "mcp." in live_source
            and "hosted." in live_source
            and "handoff." in live_source
        ),
        "secret_and_raw_attachment_checks_present": (
            "api_key_not_in_summary" in live_source
            and "api_key_not_persisted" in live_source
            and "raw_attachment_not_persisted" in live_source
            and "raw_bytes_persisted" in live_source
        ),
        "windows_launcher_uses_data_only_env_loader": (
            "scripts\\windows_entrypoint.py skill-document-review-live-acceptance" in launcher_source
            and 'args.command == "skill-document-review-live-acceptance"' in entrypoint_source
            and "load_local_environment()" in entrypoint_source
            and "call .env.local" not in launcher_source.casefold()
        ),
        "service_policy_reports_pending_live_acceptance": (
            service_policy.get("skills_available") is True
            and service_policy.get("skill_foundation_step")
            == "STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1"
            and service_policy.get("next_selected_step")
            == "UNSELECTED_PENDING_STEP071_WINDOWS_LIVE_ACCEPTANCE"
        ),
        "live_evidence_is_packaging_ignored": (
            "docs/evidence/step071-live/" in gitignore
            and '("docs", "evidence", "step071-live")' in package_source
        ),
        "source_package_default_is_step071": (
            "okcanvas-agent-runtime-step071-product-skill-document-review-live-acceptance-v1.zip"
            in package_source
        ),
        "step071_documents_present": all(path.is_file() for path in required_docs),
        "handoff_and_roadmap_select_step071": (
            STEP in handoff
            and STEP in roadmap
            and "Windows live rerun pending" in handoff
        ),
        "focused_step071_and_skill_tests_pass": focused_ok and "passed" in focused_output,
        "historical_attachment_service_catalog_tests_pass": historical_ok and "passed" in historical_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "external_network_and_model_calls_zero": True,
    }

    passed = sum(value is True for value in checks.values())
    payload = {
        "schema_version": "okcanvas-step071-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if passed == len(checks) else "FAILED",
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "skill_id": skill.skill_id,
        "skill_version": skill.version,
        "skill_package_sha256": skill.package_sha256,
        "skill_runtime_sha256": binding.skill_runtime_sha256,
        "live_model_required": EXPECTED_MODEL,
        "live_launcher": "sh_run_step071_live_acceptance.cmd",
        "live_state": "WINDOWS_LIVE_RERUN_PENDING",
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
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
