from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.project_source_identity import force_project_root_first
force_project_root_first(ROOT)

from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from scripts.node_acceptance import run_command, run_node_tests, run_npm_pack, validate_committed_typescript_release
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.step081_architecture import STEP, VERSION, canonical_modules
from scripts.validate_acceptance_launcher_registry import validate as validate_launcher_registry
from scripts.validate_architecture_constitution import validate as validate_constitution
from scripts.validate_windows_subprocess_portability import validate as validate_windows_portability

OUTPUT_DEFAULT = ROOT / "docs/evidence/step081d-local/STEP081D_ACCEPTANCE.json"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def run(output: Path) -> int:
    started_at = _utc_now()
    architecture, architecture_process = run_json_python_validator(
        root=ROOT,
        script=ROOT / "scripts/validate_step081_architecture.py",
    )
    compliance, compliance_process = run_json_python_validator(
        root=ROOT,
        script=ROOT / "scripts/validate_step081_compliance.py",
    )
    architecture = architecture or {}
    compliance = compliance or {}
    constitution = validate_constitution()
    launcher_registry = validate_launcher_registry()
    windows_portability = validate_windows_portability(ROOT)

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step081_root_package_and_architecture_restructuring.py",
            "tests/test_agent_runtime_binding.py",
            "tests/test_step069_multi_user_service_client_contract.py",
            "tests/test_control_api.py",
            "tests/test_operations_console_api.py",
            "tests/test_step039_native_sdk_streaming_baseline.py",
            "tests/test_step043_sqlite_session_runtime_baseline.py",
            "tests/test_step080a_architecture_constitution_and_compliance_gates.py",
            "tests/test_step081_windows_entrypoint_and_launcher_registry.py",
            "tests/test_step081a_windows_npm_command_resolution_and_subprocess_portability.py",
            "tests/test_step081b_live_architecture_validator_isolation.py",
            "tests/test_step081d_windows_source_identity_router_registration_and_workspace_residue.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "okcanvas_agent_runtime",
            "okcanvas_agent_protocols",
            "okcanvas_agent_clients",
            "scripts",
            "tests",
        ],
        ROOT,
    )
    import_failures: list[dict[str, str]] = []
    for module in sorted(canonical_modules(ROOT)):
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 - deterministic evidence
            import_failures.append({"module": module, "error": f"{type(exc).__name__}: {exc}"})

    from scripts.verify_no_reference_imports import find_violations

    reference_results = ReferenceCatalogService(ROOT).verify_all()
    direct_reference_violations = find_violations(ROOT)
    node_root = ROOT / "clients/cli"
    node_release_ok, node_release_output = validate_committed_typescript_release(node_root)
    node_ok, node_output = run_node_tests(node_root)
    npm_pack_ok, npm_pack_output = run_npm_pack(node_root)

    checks = {
        "identity_exact": CURRENT_STEP == STEP and PROJECT_VERSION == VERSION,
        "architecture_validator_passed": architecture_process.get("completed") is True
        and architecture_process.get("returncode") == 0
        and architecture_process.get("json_parsed") is True
        and architecture.get("state") == "PASSED"
        and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "constitution_bundle_passed": constitution.get("state") == "PASSED"
        and constitution.get("passed_checks") == constitution.get("total_checks") == 16,
        "step081_compliance_passed": compliance_process.get("completed") is True
        and compliance_process.get("returncode") == 0
        and compliance_process.get("json_parsed") is True
        and compliance.get("state") == "PASSED",
        "launcher_registry_passed": launcher_registry.get("state") == "PASSED"
        and launcher_registry.get("current_record_count") == 4,
        "focused_regression_passed": focused_ok,
        "python_compileall_passed": compile_ok,
        "all_canonical_modules_import": not import_failures,
        "reference_integrity_passed": len(reference_results) == 4
        and all(item.verified for item in reference_results),
        "direct_reference_imports_absent": not direct_reference_violations,
        "node_release_manifest_passed": node_release_ok,
        "node_tests_passed": node_ok,
        "npm_pack_dry_run_passed": npm_pack_ok,
        "windows_subprocess_portability_passed": windows_portability.get("state") == "PASSED"
        and windows_portability.get("passed_checks") == windows_portability.get("total_checks") == 7,
        "step081a_failure_issue_recorded": (ROOT / "docs/issues/OR-ISSUE-040-STEP081-WINDOWS-NPM-PACK-EXECUTABLE-NOT-RESOLVED.md").is_file()
        and (ROOT / "docs/evidence/STEP081_WINDOWS_NPM_PACK_EXECUTABLE_RESOLUTION_FAILURE_SUMMARY.json").is_file(),
        "step081b_failure_issue_recorded": (ROOT / "docs/issues/OR-ISSUE-046-STEP081A-LIVE-INPROCESS-ARCHITECTURE-REVALIDATION-LOST-FAILURE-DETAIL.md").is_file()
        and (ROOT / "docs/evidence/STEP081A_WINDOWS_LIVE_ACCEPTANCE_75_OF_77_FAILURE_SUMMARY.json").is_file()
        and (ROOT / "scripts/json_subprocess_validation.py").is_file(),
        "step081d_documents_present": (ROOT / "docs/plans/STEP081D_WINDOWS_SOURCE_IDENTITY_ROUTER_REGISTRATION_AND_WORKSPACE_RESIDUE_NORMALIZATION.md").is_file()
        and (ROOT / "docs/reference/STEP081D_WINDOWS_SOURCE_IDENTITY_ROUTER_REGISTRATION_AND_WORKSPACE_RESIDUE_NORMALIZATION_CODE_AUDIT.md").is_file()
        and (ROOT / "docs/issues/OR-ISSUE-051-STEP081C-WINDOWS-RUNTIME-ROUTER-REGISTRATION-DIVERGED-FROM-SOURCE-INVENTORY.md").is_file()
        and (ROOT / "docs/issues/OR-ISSUE-052-STEP081C-WINDOWS-COMPLIANCE-INCLUDED-NONPRODUCT-WORKSPACE-RESIDUE.md").is_file()
        and (ROOT / "docs/issues/OR-ISSUE-053-STEP081D-SERVICE-CAPABILITIES-RETAINED-DUPLICATED-STEP081C-PENDING-GATE.md").is_file()
        and (ROOT / "docs/evidence/STEP081C_WINDOWS_DETERMINISTIC_ACCEPTANCE_FAILURE_SUMMARY.json").is_file(),
        "windows_live_remains_external": compliance.get("summary", {}).get(
            "pending_external_gate_count"
        ) == 1
        and compliance.get("checks", {}).get("windows_only_pending") is True,
    }
    payload = {
        "schema_version": "okcanvas-step081d-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started_at,
        "completed_at": _utc_now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "architecture": {
            "passed_checks": architecture.get("passed_checks"),
            "total_checks": architecture.get("total_checks"),
            "canonical_module_count": architecture.get("details", {}).get("canonical_module_count"),
            "alias_count": architecture.get("details", {}).get("alias_count"),
        },
        "architecture_validation": architecture,
        "architecture_validation_process": architecture_process,
        "compliance_validation": compliance,
        "compliance_validation_process": compliance_process,
        "focused_output": focused_output,
        "compile_output": compile_output,
        "canonical_import_failures": import_failures,
        "reference_results": [item.to_dict() for item in reference_results],
        "direct_reference_import_violations": direct_reference_violations,
        "node_release_output": node_release_output,
        "node_output": node_output,
        "npm_pack_output": npm_pack_output,
        "windows_subprocess_portability": windows_portability,
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
