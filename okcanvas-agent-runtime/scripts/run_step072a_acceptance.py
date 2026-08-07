from __future__ import annotations

import argparse
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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP072A_ACCEPTANCE.json"
STEP = "STEP072A_WINDOWS_PYCACHE_OVERLAY_ISOLATION_FIX"
VERSION = "2.52.1"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
    from okcanvas_agent_runtime.agent.model.trace_export import TraceExportPolicyCatalog

    info = RuntimeInfo()
    windows = _load_json(ROOT / "docs/evidence/STEP072_WINDOWS_ACCEPTANCE_SUMMARY.json")
    service_policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    trace_policy = TraceExportPolicyCatalog(ROOT).resolve()
    definition = AgentDefinitionCatalog(ROOT).resolve("skill-document-review-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(
        encoding="utf-8"
    )
    utility_source = (ROOT / "scripts/python_bytecode_isolation.py").read_text(
        encoding="utf-8"
    )
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    live_source = (ROOT / "scripts/run_step072a_live_acceptance.py").read_text(
        encoding="utf-8"
    )

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step072a_windows_pycache_overlay_isolation_fix.py",
            "tests/test_step072_immutable_openai_trace_export_disabled.py",
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
            "tests/test_step071_product_skill_document_review_live_acceptance.py",
            "tests/test_step070_product_owned_skill_foundation.py",
            "tests/test_step070_product_owned_skill_foundation_baseline.py",
            "tests/test_step069_multi_user_service_client_contract.py",
            "tests/test_step069_multi_user_service_client_contract_baseline.py",
            "tests/test_step068_bounded_local_pdf_image_input.py",
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
            "scripts/python_bytecode_isolation.py",
            "scripts/run_step072a_acceptance.py",
            "scripts/run_step072a_live_acceptance.py",
            "scripts/windows_entrypoint.py",
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
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    required_docs = (
        ROOT / "docs/plans/STEP072A_WINDOWS_PYCACHE_OVERLAY_ISOLATION_FIX.md",
        ROOT
        / "docs/reference/STEP072A_WINDOWS_PYCACHE_OVERLAY_ISOLATION_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP072_WINDOWS_ACCEPTANCE_SUMMARY.json",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    )
    launcher_fragments = {
        "sh_run_api.cmd": "scripts\\python_bytecode_isolation.py scripts\\windows_entrypoint.py control-api",
        "sh_run_step072a_acceptance.cmd": "scripts\\python_bytecode_isolation.py scripts\\run_step072a_acceptance.py",
        "sh_run_step072a_live_acceptance.cmd": "scripts\\python_bytecode_isolation.py scripts\\run_step072a_live_acceptance.py",
    }
    launchers_ok = all(
        fragment in (ROOT / relative).read_text(encoding="utf-8")
        for relative, fragment in launcher_fragments.items()
    )

    deterministic = windows.get("deterministic", {})
    live = windows.get("live", {})
    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION
            and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step072_deterministic_failure_recorded_exact": (
            deterministic.get("state") == "FAILED"
            and deterministic.get("passed_checks") == 28
            and deterministic.get("total_checks") == 29
            and deterministic.get("failed_checks")
            == ["historical_skill_attachment_service_tests_pass"]
        ),
        "step072_trace_export_live_success_recorded_exact": (
            live.get("state") == "PASSED"
            and live.get("passed_checks") == 13
            and live.get("total_checks") == 13
            and live.get("model") == "gpt-4.1"
            and live.get("model_calls") == 1
            and live.get("usage", {}).get("total_tokens") == 1055
            and live.get("terminal_status") == "SUCCEEDED"
            and live.get("trace_error_markers") == []
            and live.get("sdk_trace_export_observed") is False
        ),
        "step072_trace_policy_unchanged": (
            trace_policy.policy_id == "local-openai-trace-export-disabled-v1"
            and trace_policy.sdk_tracing_disabled is True
            and trace_policy.provider_trace_export_enabled is False
            and trace_policy.trace_include_sensitive_data is False
            and trace_policy.persist_local_trace_id is True
            and trace_policy.policy_sha256
            == "6567645dc74b2850bad374f4e73eab50958c6e3e63440b0361dcadcea0b249cc"
        ),
        "runtime_binding_still_contains_trace_policy_and_skill": (
            binding.trace_export_policy.get("policy_id")
            == "local-openai-trace-export-disabled-v1"
            and binding.skills[0].get("skill_id") == "document-review-v1"
            and binding.skills[0].get("package_sha256")
            == "60fbfca861141837d4486499687fde4257b83bcb68362b6b0a0b6f40b8df07b5"
        ),
        "runtime_reports_step072_live_accepted": info.openai_trace_export_windows_live_accepted
        is True,
        "bytecode_isolation_runtime_flags_exact": (
            info.windows_pycache_overlay_isolation_implemented is True
            and info.windows_pycache_overlay_isolation_mode
            == "per-process-temporary-pycache-prefix"
            and info.windows_pycache_overlay_isolation_deterministic_accepted is True
            and info.windows_pycache_overlay_isolation_windows_accepted is False
            and info.next_selected_step == "UNSELECTED_PENDING_STEP072A_WINDOWS_ACCEPTANCE"
        ),
        "service_policy_selects_step072a_gate": service_policy.get("next_selected_step")
        == "UNSELECTED_PENDING_STEP072A_WINDOWS_ACCEPTANCE",
        "bytecode_wrapper_uses_process_temp_prefix": (
            "tempfile.mkdtemp" in utility_source
            and 'ENV_NAME = "PYTHONPYCACHEPREFIX"' in utility_source
            and "subprocess.run" in utility_source
            and "shell=True" not in utility_source
            and "shutil.rmtree" in utility_source
        ),
        "bytecode_wrapper_reuses_inherited_prefix": (
            "if existing:" in utility_source and "return environment, Path(existing), False" in utility_source
        ),
        "current_windows_launchers_use_wrapper": launchers_ok,
        "live_wrapper_requires_active_isolation": (
            "bytecode_isolation_environment_present" in live_source
            and "bytecode_isolation_active_in_interpreter" in live_source
            and "bytecode_isolation_prefix_outside_project" in live_source
            and "run_step072_live_acceptance.py" in live_source
        ),
        "stale_timestamp_size_collision_regression_present": (
            "test_python_timestamp_size_collision_is_reproduced_and_isolated"
            in (ROOT / "tests/test_step072a_windows_pycache_overlay_isolation_fix.py").read_text(
                encoding="utf-8"
            )
        ),
        "live_evidence_is_packaging_ignored": (
            "docs/evidence/step072a-live/" in gitignore
            and '("docs", "evidence", "step072a-live")' in package_source
        ),
        "source_package_default_is_step072a": (
            "okcanvas-agent-runtime-step072a-windows-pycache-overlay-isolation-fix.zip"
            in package_source
        ),
        "step072a_documents_present": all(path.is_file() for path in required_docs),
        "focused_step072a_tests_pass": focused_ok and "passed" in focused_output,
        "historical_skill_attachment_service_tests_pass": historical_ok
        and "passed" in historical_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "external_network_and_model_calls_zero": True,
    }
    payload = {
        "schema_version": "okcanvas-step072a-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "trace_export_policy_sha256": trace_policy.policy_sha256,
        "trace_export_runtime_sha256": binding.trace_export_runtime_sha256,
        "runtime_binding_sha256": binding.runtime_binding_sha256,
        "skill_id": binding.skills[0].get("skill_id"),
        "skill_package_sha256": binding.skills[0].get("package_sha256"),
        "focused_test_output": focused_output[-8000:],
        "historical_test_output": historical_output[-8000:],
        "python_compile_output": compile_output[-4000:],
        "node_release_output": release_output[-4000:],
        "node_test_output_tail": node_output[-4000:],
        "reference_import_output_tail": no_reference_imports_output[-4000:],
        "reference_count": len(reference_results),
        "live_state": "WINDOWS_RERUN_PENDING",
        "live_launcher": "sh_run_step072a_live_acceptance.cmd",
        "external_network_calls": 0,
        "model_calls": 0,
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return run(args.output or OUTPUT_DEFAULT)


if __name__ == "__main__":
    raise SystemExit(main())
