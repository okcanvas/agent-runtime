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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP072B_ACCEPTANCE.json"
STEP = "STEP072B_WINDOWS_CRLF_AND_LOCAL_ENV_FORWARDING_FIX"
VERSION = "2.52.2"


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
    windows = _load_json(ROOT / "docs/evidence/STEP072A_WINDOWS_ACCEPTANCE_SUMMARY.json")
    windows_live = _load_json(
        ROOT / "docs/evidence/STEP072B_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json"
    )
    service_policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    trace_policy = TraceExportPolicyCatalog(ROOT).resolve()
    definition = AgentDefinitionCatalog(ROOT).resolve("skill-document-review-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(
        encoding="utf-8"
    )
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    entrypoint_source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    collision_test_source = (
        ROOT / "tests/test_step072a_windows_pycache_overlay_isolation_fix.py"
    ).read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    live_source = (ROOT / "scripts/run_step072b_live_acceptance.py").read_text(
        encoding="utf-8"
    )
    portability_doc = (
        ROOT / "docs/38-WINDOWS-PYTHON-LAUNCHER-PORTABILITY.md"
    ).read_text(encoding="utf-8")
    agents_source = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step072b_windows_crlf_and_local_env_forwarding_fix.py",
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
            "scripts/run_step072a_live_acceptance.py",
            "scripts/run_step072b_acceptance.py",
            "scripts/run_step072b_live_acceptance.py",
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
        ROOT / "docs/plans/STEP072B_WINDOWS_CRLF_AND_LOCAL_ENV_FORWARDING_FIX.md",
        ROOT
        / "docs/reference/STEP072B_WINDOWS_CRLF_AND_LOCAL_ENV_FORWARDING_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP072A_WINDOWS_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/evidence/STEP072B_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/38-WINDOWS-PYTHON-LAUNCHER-PORTABILITY.md",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    )
    launcher_fragments = {
        "sh_run_step072a_live_acceptance.cmd": (
            "scripts\\python_bytecode_isolation.py scripts\\windows_entrypoint.py "
            "windows-pycache-overlay-live-acceptance"
        ),
        "sh_run_step072b_acceptance.cmd": (
            "scripts\\python_bytecode_isolation.py scripts\\run_step072b_acceptance.py"
        ),
        "sh_run_step072b_live_acceptance.cmd": (
            "scripts\\python_bytecode_isolation.py scripts\\windows_entrypoint.py "
            "windows-crlf-local-env-live-acceptance"
        ),
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
        "step072a_deterministic_failure_recorded_exact": (
            deterministic.get("state") == "FAILED"
            and deterministic.get("passed_checks") == 23
            and deterministic.get("total_checks") == 24
            and deterministic.get("failed_checks") == ["focused_step072a_tests_pass"]
            and deterministic.get("failure_class") == "windows-text-newline-translation"
            and deterministic.get("observed_file_size") == 19
            and deterministic.get("expected_utf8_payload_size") == 18
        ),
        "step072a_live_failure_recorded_exact": (
            live.get("state") == "FAILED"
            and live.get("passed_checks") == 5
            and live.get("total_checks") == 15
            and live.get("readiness_issue_codes")
            == ["OPENAI_API_KEY_MISSING", "OKCANVAS_AGENT_MODEL_MISSING"]
            and live.get("bytecode_isolation_environment_present") is True
            and live.get("bytecode_isolation_active_in_interpreter") is True
            and live.get("bytecode_isolation_prefix_outside_project") is True
            and live.get("failure_class") == "local-environment-loader-bypassed"
        ),
        "windows_crlf_collision_fixture_uses_exact_bytes": (
            'module.write_bytes(old_source.encode("utf-8"))' in collision_test_source
            and 'module.write_bytes(new_source.encode("utf-8"))' in collision_test_source
            and "module.write_text(old_source" not in collision_test_source
            and "module.write_text(new_source" not in collision_test_source
        ),
        "data_only_entrypoint_routes_step072a_and_step072b_live": (
            '"windows-pycache-overlay-live-acceptance"' in entrypoint_source
            and '"windows-crlf-local-env-live-acceptance"' in entrypoint_source
            and 'str(ROOT / "scripts" / "run_step072a_live_acceptance.py")'
            in entrypoint_source
            and 'str(ROOT / "scripts" / "run_step072b_live_acceptance.py")'
            in entrypoint_source
        ),
        "current_windows_launchers_use_isolated_data_loader": launchers_ok,
        "local_environment_forwarding_runtime_flags_exact": (
            info.windows_crlf_collision_regression_fixed is True
            and info.windows_local_environment_forwarding_implemented is True
            and info.windows_local_environment_forwarding_mode
            == "data-only-loader-through-isolated-entrypoint"
            and info.windows_crlf_and_local_env_fix_deterministic_accepted is True
            and info.windows_crlf_and_local_env_fix_windows_accepted is True
            and info.windows_pycache_overlay_isolation_windows_accepted is True
            and info.next_selected_step
            == "UNSELECTED_PENDING_FRESH_CODE_AUDIT_AFTER_STEP072B_WINDOWS_LIVE_ACCEPTANCE"
            and 'windows_crlf_collision_regression_fixed: bool = True' in model_source
        ),
        "service_policy_selects_post_live_audit_gate": (
            service_policy.get("version") == "1.2.1"
            and service_policy.get("next_selected_step")
            == "UNSELECTED_PENDING_FRESH_CODE_AUDIT_AFTER_STEP072B_WINDOWS_LIVE_ACCEPTANCE"
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
        "step072_trace_export_live_remains_accepted": info.openai_trace_export_windows_live_accepted
        is True,
        "step072b_windows_live_closure_exact": (
            windows_live.get("state") == "WINDOWS_LIVE_ACCEPTED"
            and windows_live.get("deterministic", {}).get("passed_checks") == 24
            and windows_live.get("deterministic", {}).get("total_checks") == 24
            and windows_live.get("live", {}).get("passed_checks") == 17
            and windows_live.get("live", {}).get("total_checks") == 17
            and windows_live.get("live", {}).get("model") == "gpt-4.1"
            and windows_live.get("live", {}).get("model_calls") == 1
            and windows_live.get("live", {}).get("terminal_status") == "SUCCEEDED"
            and windows_live.get("live", {}).get("python_pycache_prefix_active") is True
            and windows_live.get("live", {}).get("python_pycache_prefix_inside_project") is False
            and windows_live.get("live", {}).get(
                "local_environment_forwarded_to_current_interpreter"
            )
            is True
            and windows_live.get("live", {}).get("sdk_trace_export_observed") is False
            and windows_live.get("live", {}).get("trace_error_markers") == []
            and windows_live.get("security", {}).get("api_key_value_recorded") is False
            and windows_live.get("security", {}).get("api_key_persisted") is False
            and windows_live.get("security", {}).get("raw_attachment_persisted") is False
            and windows_live.get("security", {}).get("workspace_cleanup_completed") is True
        ),
        "windows_launcher_portability_constitution_present": (
            "stale timestamp-and-size bytecode collision" in portability_doc
            and "Path.write_bytes" in portability_doc
            and "python_bytecode_isolation.py" in portability_doc
            and "windows_entrypoint.py" in portability_doc
            and "New Windows launcher review checklist" in portability_doc
            and "docs/38-WINDOWS-PYTHON-LAUNCHER-PORTABILITY.md" in agents_source
        ),
        "pycache_overlay_still_enabled": (
            info.windows_pycache_overlay_isolation_implemented is True
            and info.windows_pycache_overlay_isolation_mode
            == "per-process-temporary-pycache-prefix"
        ),
        "live_wrapper_reuses_step072a_workflow": (
            "run_step072a_live_acceptance.py" in live_source
            and "local_environment_forwarded_to_current_interpreter" in live_source
            and "bytecode_isolation_active_in_interpreter" in live_source
        ),
        "live_evidence_is_packaging_ignored": (
            "docs/evidence/step072b-live/" in gitignore
            and '("docs", "evidence", "step072b-live")' in package_source
        ),
        "source_package_default_is_step072b": (
            "okcanvas-agent-runtime-step072b-windows-crlf-and-local-env-forwarding-fix.zip"
            in package_source
        ),
        "step072b_documents_present": all(path.is_file() for path in required_docs),
        "focused_step072b_tests_pass": focused_ok and "passed" in focused_output,
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
        "schema_version": "okcanvas-step072b-acceptance-v1",
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
        "live_state": "WINDOWS_LIVE_ACCEPTED",
        "live_launcher": "sh_run_step072b_live_acceptance.cmd",
        "windows_live": windows_live.get("live", {}),
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
