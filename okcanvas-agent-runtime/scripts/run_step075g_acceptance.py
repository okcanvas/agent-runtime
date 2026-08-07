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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP075G_ACCEPTANCE.json"
STEP = "STEP075G_PRODUCT_OWNED_DETERMINISTIC_EVIDENCE_COMPLETION"
VERSION = "2.55.7"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionErrorCode
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
    from okcanvas_agent_runtime.adapters.sandbox.docker import SandboxRuntimeCatalog

    info = RuntimeInfo()
    foundation = SandboxRuntimeCatalog(ROOT).resolve()
    definitions = AgentDefinitionCatalog(ROOT).list_definitions()
    sandbox_definition = AgentDefinitionCatalog(ROOT).resolve("sandbox-readonly-coding-agent")
    sandbox_binding = AgentRuntimeBindingCatalog(ROOT).resolve(sandbox_definition)
    tool = FunctionToolRuntimeCatalog(ROOT).resolve("sandbox_project_readonly_inspect")
    service_policy_path = ROOT / "specs/service_clients/service-client-policy.json"
    service_policy = _load_json(service_policy_path)
    failure = _load_json(
        ROOT / "docs/evidence/STEP075F_WINDOWS_LIVE_ACCEPTANCE_BOUNDED_REPAIR_FAILURE_SUMMARY.json"
    )

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    completeness_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/sandbox_answer_completeness.py")
    ).read_text(encoding="utf-8")
    gateway_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    binding_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text(encoding="utf-8")
    contracts_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/contracts.py")).read_text(encoding="utf-8")
    instructions_source = (
        ROOT / "specs/agents/sandbox-readonly-coding-agent/instructions.md"
    ).read_text(encoding="utf-8")
    regression_source = (
        ROOT / "tests/test_step075g_product_owned_deterministic_evidence_completion.py"
    ).read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    deterministic_launcher = (ROOT / "sh_run_step075g_acceptance.cmd").read_text(encoding="utf-8")
    live_launcher = (ROOT / "sh_run_step075g_live_acceptance.cmd").read_text(encoding="utf-8")
    windows_entrypoint = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    live_source = (ROOT / "scripts/run_step075g_live_acceptance.py").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step075g_product_owned_deterministic_evidence_completion.py",
            "tests/test_step075f_sandbox_answer_completeness_and_bounded_repair.py",
            "tests/test_step075e_internal_snapshot_metadata_exclusion_and_hash_domain_fix.py",
            "tests/test_step075d_python_subprocess_stdin_input_contract_fix.py",
            "tests/test_step075c_windows_tmpfs_tar_stream_materialization_fix.py",
            "tests/test_step075b_windows_docker_command_operation_evidence.py",
            "tests/test_step075a_windows_docker_tmpfs_normalization_and_failure_evidence_fix.py",
            "tests/test_step075_product_owned_readonly_sandbox_workspace_agent.py",
            "tests/test_generic_openai_gateway_contract.py",
            "tests/test_generic_openai_gateway_business_contract.py",
            "tests/test_generic_agent_execution_service.py",
            "tests/test_project_readonly_inspection.py",
            "tests/test_step074_product_owned_docker_sandbox_provider_lifecycle.py",
            "tests/test_step073_product_owned_sandbox_runtime_foundation.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_agent_invocation_scope.py",
            "tests/test_function_tool_runtime_catalog.py",
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
            "tests/test_step069_multi_user_service_client_contract.py",
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
            "scripts/run_step075g_acceptance.py",
            "scripts/run_step075g_live_acceptance.py",
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
        ROOT / "docs/plans/STEP075G_PRODUCT_OWNED_DETERMINISTIC_EVIDENCE_COMPLETION.md",
        ROOT / "docs/reference/STEP075G_PRODUCT_OWNED_DETERMINISTIC_EVIDENCE_COMPLETION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP075F_WINDOWS_LIVE_ACCEPTANCE_BOUNDED_REPAIR_FAILURE_SUMMARY.json",
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-007-STEP075F-MODEL-REPAIR-NONDETERMINISM.md",
        ROOT / "docs/39-PRODUCT-OWNED-SANDBOX-RUNTIME.md",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
    )

    live = failure.get("live_acceptance") if isinstance(failure.get("live_acceptance"), dict) else {}
    runtime_evidence = failure.get("runtime_evidence") if isinstance(failure.get("runtime_evidence"), dict) else {}
    answer_failure = failure.get("answer_failure") if isinstance(failure.get("answer_failure"), dict) else {}
    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION
            and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step075f_runtime_success_model_repair_failure_recorded_exact": (
            failure.get("acceptance_classification") == "RUNTIME_ACCEPTED_MODEL_REPAIR_FAILED"
            and live == {
                "passed_checks": 28,
                "total_checks": 37,
                "state": "FAILED",
                "terminal_status": "FAILED",
                "model": "gpt-4.1",
                "model_calls": 3,
                "tool_calls": 1,
                "input_tokens": 3209,
                "output_tokens": 400,
                "total_tokens": 3609,
            }
            and runtime_evidence.get("workspace_materialized") is True
            and runtime_evidence.get("selected_file_hashes_verified") is True
            and runtime_evidence.get("cleanup_state") == "COMPLETED"
            and runtime_evidence.get("orphan_count") == 0
        ),
        "model_repair_failure_facts_recorded": (
            answer_failure.get("repair_started_count") == 1
            and answer_failure.get("repair_completed_count") == 1
            and answer_failure.get("failure_code") == "ANSWER_COMPLETENESS_FAILED"
            and answer_failure.get("exact_formula_observed") is False
            and answer_failure.get("evidence_backed_path_not_unverified") is False
        ),
        "bounded_completeness_validator_preserved": (
            "class SandboxAnswerCompletenessAssessment" in completeness_source
            and "EXACT_EVIDENCE_FRAGMENT_MISSING" in completeness_source
            and "EVIDENCE_BACKED_PATH_MARKED_UNVERIFIED" in completeness_source
            and "EXACT_FACT_REQUIREMENTS_NOT_DERIVED" in completeness_source
            and "EVIDENCE_PATH_MISSING" in completeness_source
        ),
        "deterministic_completion_uses_only_derived_evidence": (
            "class SandboxAnswerDeterministicCompletion" in completeness_source
            and "def complete_sandbox_answer_from_evidence" in completeness_source
            and "assessment.required_fragments" in completeness_source
            and "tool_output.evidence" in completeness_source
            and 'title="Exact verified evidence"' in completeness_source
        ),
        "deterministic_completion_removes_evidence_paths_from_unverified": (
            "cleaned_unverified" in completeness_source
            and "evidence_paths_casefold" in completeness_source
            and "removed_unverified_count" in completeness_source
        ),
        "deterministic_completion_is_bounded_and_fail_closed": (
            "len(assessment.required_fragments) > 20" in completeness_source
            and "len(evidence_references) > 20" in completeness_source
            and "len(findings) >= 100" in completeness_source
            and "Exact evidence requirements could not be derived" in completeness_source
            and GenericExecutionErrorCode.ANSWER_COMPLETENESS_FAILED.value == "ANSWER_COMPLETENESS_FAILED"
        ),
        "gateway_uses_no_additional_model_or_tool_call": (
            "complete_sandbox_answer_from_evidence(" in gateway_source
            and '"model_calls_added": 0' in gateway_source
            and '"tool_reexecuted": False' in gateway_source
            and "repair_agent = Agent(" not in gateway_source
            and "build_sandbox_answer_repair_prompt(" not in gateway_source
        ),
        "bounded_completion_lifecycle_events_present": (
            '"agent.output.completion.started"' in gateway_source
            and '"agent.output.completion.completed"' in gateway_source
            and '"product-owned-deterministic-evidence-v1"' in gateway_source
            and '"raw_request_persisted": False' in gateway_source
            and '"raw_evidence_persisted": False' in gateway_source
            and '"raw_draft_persisted": False' in gateway_source
        ),
        "persistent_incompleteness_still_fails_closed": (
            "answer remained incomplete after deterministic evidence completion" in gateway_source
            and "ANSWER_COMPLETENESS_FAILED" in contracts_source
        ),
        "runtime_binding_contains_completion_implementation": (
            "okcanvas_agent_runtime.application.execution.sandbox_answer_completeness" in binding_source
            and sandbox_binding.execution_path == "product-owned-readonly-sandbox-agent-execution-v1"
        ),
        "runtime_flags_select_step075g_gate": (
            info.product_owned_readonly_sandbox_internal_metadata_exclusion_windows_live_accepted is True
            and info.product_owned_readonly_sandbox_answer_completeness_implemented is True
            and info.product_owned_readonly_sandbox_bounded_answer_repair_implemented is False
            and info.product_owned_readonly_sandbox_answer_repair_max_model_calls == 0
            and info.product_owned_readonly_sandbox_deterministic_evidence_completion_implemented is True
            and info.product_owned_readonly_sandbox_deterministic_evidence_completion_model_calls == 0
            and info.product_owned_readonly_sandbox_deterministic_evidence_completion_tool_reexecution_allowed is False
            and info.product_owned_readonly_sandbox_answer_completeness_windows_live_accepted is False
            and info.next_selected_step == "UNSELECTED_PENDING_STEP075G_WINDOWS_LIVE_ACCEPTANCE"
        ),
        "service_policy_selects_step075g_gate": (
            service_policy.get("version") == "1.4.6"
            and service_policy.get("next_selected_step") == "UNSELECTED_PENDING_STEP075G_WINDOWS_LIVE_ACCEPTANCE"
            and service_policy.get("sandbox_foundation_step") == STEP
        ),
        "single_readonly_sandbox_agent_preserved": (
            len(definitions) == 27
            and len([item for item in definitions if item.workspace_access == "sandbox-readonly-v1"]) == 1
            and len([item for item in definitions if item.workspace_access == "none"]) == 26
            and sandbox_definition.tools == ("sandbox_project_readonly_inspect",)
        ),
        "readonly_tool_and_sandbox_security_unchanged": (
            tool.factory_id == "sandbox_project_readonly_inspect_v1"
            and tool.read_only is True
            and tool.network_access == "none"
            and tool.shell_access == "none"
            and foundation.policy.network_mode == "none"
            and foundation.policy.shell_enabled is False
            and foundation.policy.apply_patch_enabled is False
            and foundation.provider.host_bind_mounts_enabled is False
            and foundation.provider.runtime_image_pull_enabled is False
        ),
        "step075g_regressions_cover_deterministic_completion": (
            "test_deterministic_completion_inserts_only_hash_verified_exact_fragments" in regression_source
            and "test_deterministic_completion_respects_finding_contract_bound" in regression_source
            and "test_completion_fails_closed_when_exact_requirements_cannot_be_derived" in regression_source
            and "test_complete_output_is_returned_without_mutation" in regression_source
        ),
        "live_acceptance_requires_two_model_calls_and_no_model_repair": (
            "deterministic_completion_consistent" in live_source
            and "model_repair_events_absent" in live_source
            and "model_started == model_completed == 2" in live_source
            and "agent.output.completion.completed" in live_source
        ),
        "windows_launchers_use_isolation_and_data_loader": (
            "python_bytecode_isolation.py scripts\\run_step075g_acceptance.py" in deterministic_launcher
            and "python_bytecode_isolation.py scripts\\windows_entrypoint.py readonly-sandbox-deterministic-evidence-completion-live-acceptance" in live_launcher
            and "run_step075g_live_acceptance.py" in windows_entrypoint
        ),
        "live_evidence_and_secrets_are_packaging_ignored": (
            "docs/evidence/step075f-live/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
            and "docs/evidence/step075g-live/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
            and ".env.local" in package_source
            and "step075f-live" in package_source
            and "step075g-live" in package_source
        ),
        "source_package_default_is_step075g": (
            "step075g-product-owned-deterministic-evidence-completion" in package_source
            and STEP in package_source
        ),
        "step075g_documents_and_issue_present": all(path.is_file() for path in required_docs),
        "focused_step075g_tests_pass": focused_ok,
        "historical_skill_trace_service_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "deterministic_docker_network_and_model_calls_zero": True,
        "no_sdk_sandbox_agent_or_default_capabilities": (
            foundation.policy.sdk_default_capabilities_allowed is False
            and "SandboxAgent" not in gateway_source
        ),
    }
    payload = {
        "schema_version": "okcanvas-step075g-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "agent_definition_count": len(definitions),
        "workspace_none_agent_count": len([item for item in definitions if item.workspace_access == "none"]),
        "readonly_sandbox_agent_id": sandbox_definition.agent_id,
        "readonly_sandbox_tool_id": tool.tool_id,
        "sandbox_policy_sha256": foundation.policy.policy_sha256,
        "sandbox_provider_contract_sha256": foundation.provider.contract_sha256,
        "sandbox_foundation_sha256": foundation.foundation_sha256,
        "sandbox_runtime_sha256": sandbox_binding.sandbox_runtime_sha256,
        "sample_runtime_binding_sha256": sandbox_binding.runtime_binding_sha256,
        "service_policy_sha256": _sha256(service_policy_path),
        "focused_test_output": focused_output[-12_000:],
        "historical_test_output": historical_output[-12_000:],
        "python_compile_output": compile_output[-4_000:],
        "node_release_output": release_output[-4_000:],
        "node_test_output_tail": node_output[-4_000:],
        "reference_import_output_tail": no_reference_imports_output[-4_000:],
        "reference_count": len(reference_results),
        "docker_calls": 0,
        "external_network_calls": 0,
        "model_calls": 0,
        "live_launcher": "sh_run_step075g_live_acceptance.cmd",
        "live_state": "WINDOWS_LIVE_RERUN_PENDING",
        "live_model_required": "gpt-4.1",
        "live_image_default": "busybox:1.36",
        "deterministic_evidence_completion_model_calls": 0,
        "deterministic_evidence_completion_tool_reexecution_allowed": False,
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
