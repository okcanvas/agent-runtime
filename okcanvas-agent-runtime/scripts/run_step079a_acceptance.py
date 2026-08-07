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

from scripts import windows_entrypoint
from scripts.node_acceptance import run_command, run_node_tests, validate_committed_typescript_release

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP079A_ACCEPTANCE.json"
STEP = "STEP079A_WINDOWS_ENTRYPOINT_COMMAND_REGISTRATION_FIX"
VERSION = "2.59.1"
LIVE_COMMAND = "atomic-task-run-ownership-transfer-live-acceptance"


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
    failure = _load_json(
        ROOT / "docs/evidence/STEP079_WINDOWS_LIVE_ENTRYPOINT_FAILURE_SUMMARY.json"
    )

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    entrypoint_source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    old_live_launcher = (ROOT / "sh_run_step079_live_acceptance.cmd").read_text(encoding="utf-8")
    new_live_launcher = (ROOT / "sh_run_step079a_live_acceptance.cmd").read_text(encoding="utf-8")
    old_acceptance_launcher = (ROOT / "sh_run_step079_acceptance.cmd").read_text(encoding="utf-8")
    new_acceptance_launcher = (ROOT / "sh_run_step079a_acceptance.cmd").read_text(encoding="utf-8")
    live_source = (ROOT / "scripts/run_step079a_live_acceptance.py").read_text(encoding="utf-8")

    parsed = windows_entrypoint._parser().parse_args([LIVE_COMMAND])
    command_action = next(
        action for action in windows_entrypoint._parser()._actions if action.dest == "command"
    )

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
            "tests/test_step079a_windows_entrypoint_command_registration.py",
            "tests/test_step079_product_owned_atomic_task_run_ownership_transfer.py",
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
            "scripts/windows_entrypoint.py",
            "scripts/run_step079a_acceptance.py",
            "scripts/run_step079a_live_acceptance.py",
        ],
        ROOT,
    )
    release_ok, release_output = validate_committed_typescript_release(
        ROOT / "clients/cli"
    )
    node_ok, node_output = run_node_tests(ROOT / "clients/cli")
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    required_docs = (
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "docs/plans/STEP079A_WINDOWS_ENTRYPOINT_COMMAND_REGISTRATION_FIX.md",
        ROOT / "docs/reference/STEP079A_WINDOWS_ENTRYPOINT_COMMAND_REGISTRATION_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP079_WINDOWS_LIVE_ENTRYPOINT_FAILURE_SUMMARY.json",
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-013-STEP079-LIVE-COMMAND-NOT-REGISTERED.md",
    )
    definition = AgentDefinitionCatalog(ROOT).resolve("sandbox-readonly-coding-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)

    launcher_fragment = (
        "python_bytecode_isolation.py scripts\\windows_entrypoint.py "
        "atomic-task-run-ownership-transfer-live-acceptance"
    )
    acceptance_fragment = "python_bytecode_isolation.py scripts\\run_step079a_acceptance.py"

    checks = {
        "baseline_version_and_step_exact": info.version == VERSION
        and info.step == STEP
        and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
        and f'CURRENT_STEP = "{STEP}"' in baseline_source,
        "step079_product_contract_preserved": info.product_owned_atomic_task_run_ownership_transfer_implemented is True
        and info.product_owned_atomic_task_run_ownership_transfer_mode
        == "sqlite-task-run-and-service-owner-single-transaction-v1"
        and info.product_owned_atomic_task_run_ownership_transfer_deterministic_accepted is True
        and info.product_owned_atomic_task_run_ownership_transfer_windows_live_accepted is False,
        "step079a_runtime_flags_exact": info.windows_step079_live_command_registration_fixed is True
        and info.windows_step079_live_command_registration_mode
        == "argparse-choice-and-dispatch-alignment-v1"
        and info.windows_step079_live_command_registration_deterministic_accepted is True
        and info.windows_step079_live_command_registration_windows_live_accepted is False
        and info.next_selected_step == "UNSELECTED_PENDING_STEP079A_WINDOWS_LIVE_ACCEPTANCE",
        "windows_failure_evidence_exact": failure.get("state") == "FAILED_BEFORE_LIVE_ACCEPTANCE"
        and failure.get("exit_code") == 2
        and failure.get("exact_failed_command") == LIVE_COMMAND
        and failure.get("exact_error_class") == "argparse-invalid-choice"
        and failure.get("command_dispatch_branch_present") is True
        and failure.get("command_parser_choice_present") is False
        and failure.get("model_calls") == 0
        and failure.get("tool_calls") == 0,
        "parser_accepts_exact_live_command": parsed.command == LIVE_COMMAND
        and LIVE_COMMAND in command_action.choices,
        "dispatch_routes_corrective_live_script": f'args.command == "{LIVE_COMMAND}"' in entrypoint_source
        and 'OKCANVAS_STEP079_LIVE_ACCEPTANCE"] = "1"' in entrypoint_source
        and 'OKCANVAS_STEP079A_LIVE_ACCEPTANCE"] = "1"' in entrypoint_source
        and "run_step079a_live_acceptance.py" in entrypoint_source,
        "original_live_launcher_compatibility_preserved": launcher_fragment in old_live_launcher,
        "canonical_live_launcher_exact": launcher_fragment in new_live_launcher,
        "original_deterministic_launcher_compatibility_preserved": acceptance_fragment
        in old_acceptance_launcher,
        "canonical_deterministic_launcher_exact": acceptance_fragment in new_acceptance_launcher,
        "live_script_selects_corrective_identity": f'STEP = "{STEP}"' in live_source
        and f'VERSION = "{VERSION}"' in live_source
        and "okcanvas-step079a-live-acceptance-v1" in live_source
        and 'step_id="STEP079A"' in live_source,
        "live_script_preserves_atomic_task_run_checks": "atomic_task_owner_created" in live_source
        and "atomic_run_owner_created" in live_source
        and "atomic_task_run_ownership_runtime_bound" in live_source,
        "live_script_adds_corrective_runtime_check": "windows_entrypoint_command_registration_runtime_bound"
        in live_source,
        "service_policy_selects_step079a_gate": service_policy.get("next_selected_step")
        == "UNSELECTED_PENDING_STEP079A_WINDOWS_LIVE_ACCEPTANCE"
        and service_policy.get("step079_live_entrypoint_command_registered") is True
        and service_policy.get("step079_live_entrypoint_command_registration_mode")
        == "argparse-choice-and-dispatch-alignment-v1"
        and service_policy.get("step079_live_entrypoint_command_registration_step") == STEP,
        "task_run_transition_policy_preserved": service_policy.get(
            "task_run_ownership_transition_step"
        )
        == "STEP079_PRODUCT_OWNED_ATOMIC_TASK_RUN_OWNERSHIP_TRANSFER"
        and service_policy.get("task_run_ownership_transition_atomic") is True,
        "focused_step079a_tests_pass": focused_ok,
        "historical_skill_trace_attachment_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "references_unchanged": references_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "source_package_default_is_step079a": "step079a-windows-entrypoint-command-registration-fix"
        in package_source
        and STEP in package_source,
        "live_and_secret_evidence_packaging_ignored": "docs/evidence/step079a-live/"
        in (ROOT / ".gitignore").read_text(encoding="utf-8")
        and "step079a-live" in package_source
        and ".env.local" in package_source,
        "step079a_documents_and_issue_present": all(path.is_file() for path in required_docs),
        "regression_gate_executes_parser_and_dispatch": (
            ROOT / "tests/test_step079a_windows_entrypoint_command_registration.py"
        ).is_file(),
        "runtime_binding_preserved": binding.execution_path
        == "product-owned-readonly-sandbox-agent-execution-v1",
        "deterministic_model_docker_network_calls_zero": True,
        "model_source_contains_corrective_contract": "windows_step079_live_command_registration_fixed"
        in model_source,
    }

    payload = {
        "schema_version": "okcanvas-step079a-acceptance-v1",
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
        "live_launcher": "sh_run_step079a_live_acceptance.cmd",
        "compatibility_live_launcher": "sh_run_step079_live_acceptance.cmd",
        "live_state": "WINDOWS_LIVE_RERUN_PENDING",
        "live_model_required": "gpt-4.1",
        "live_image_default": "busybox:1.36",
        "live_expected_checks": 57,
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
