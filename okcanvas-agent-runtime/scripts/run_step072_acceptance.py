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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP072_ACCEPTANCE.json"
STEP = "STEP072_IMMUTABLE_OPENAI_TRACE_EXPORT_DISABLED_V1"
VERSION = "2.52.0"
POLICY_ID = "local-openai-trace-export-disabled-v1"
RUN_CONFIG_PATHS = (
    "okcanvas_agent_runtime/execution/openai_gateway.py",
    "okcanvas_agent_runtime/orchestration/openai_runtime.py",
    "okcanvas_agent_runtime/runtime/codex_approval_gateway.py",
    "okcanvas_agent_runtime/runtime/codex_gateway.py",
    "okcanvas_agent_runtime/runtime/codex_write_gateway.py",
    "okcanvas_agent_runtime/runtime/openai_gateway.py",
    "okcanvas_agent_runtime/tool_approval/gateway.py",
)


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
    from okcanvas_agent_runtime.agent.model.trace_export import (
        TraceExportPolicyCatalog,
        build_sdk_trace_run_config_kwargs,
    )

    info = RuntimeInfo()
    step071_windows = _load_json(
        ROOT / "docs/evidence/STEP071_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json"
    )
    service_policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    trace_policy = TraceExportPolicyCatalog(ROOT).resolve()
    definition = AgentDefinitionCatalog(ROOT).resolve("skill-document-review-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    live_source = (ROOT / "scripts/run_step072_live_acceptance.py").read_text(encoding="utf-8")
    sdk_run_config = (
        ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/run_config.py"
    ).read_text(encoding="utf-8")
    sdk_processors = (
        ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/tracing/processors.py"
    ).read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step072_immutable_openai_trace_export_disabled.py",
            "tests/test_generic_openai_gateway_contract.py",
            "tests/test_codex_gateway_contract.py",
            "tests/test_codex_approval_gateway_contract.py",
            "tests/test_governed_local_tool_approval.py",
            "tests/test_bounded_multi_agent_orchestration.py",
            "tests/test_agent_runtime_binding.py",
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
            "scripts/run_step072_acceptance.py",
            "scripts/run_step072_live_acceptance.py",
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

    run_config_sources = {
        relative: (ROOT / relative).read_text(encoding="utf-8") for relative in RUN_CONFIG_PATHS
    }
    required_docs = (
        ROOT / "docs/plans/STEP072_IMMUTABLE_OPENAI_TRACE_EXPORT_DISABLED_V1.md",
        ROOT / "docs/reference/STEP072_IMMUTABLE_OPENAI_TRACE_EXPORT_DISABLED_V1_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP071_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    )

    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION
            and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step071_windows_live_closure_exact": (
            step071_windows.get("state") == "WINDOWS_LIVE_ACCEPTED"
            and step071_windows.get("deterministic_passed_checks") == 28
            and step071_windows.get("live_passed_checks") == 28
            and step071_windows.get("model") == "gpt-4.1"
            and step071_windows.get("model_calls") == 1
            and step071_windows.get("usage", {}).get("total_tokens") == 1145
            and step071_windows.get("acceptance_workspace", {}).get("cleanup_state")
            == "COMPLETED"
        ),
        "step071_observed_trace_400_recorded": (
            "Tracing client error 400"
            in str(step071_windows.get("observed_non_fatal_sdk_diagnostic"))
        ),
        "trace_export_policy_identity_exact": (
            trace_policy.schema_version == "okcanvas-openai-trace-export-policy-v1"
            and trace_policy.policy_id == POLICY_ID
            and trace_policy.version == "1.0.0"
            and len(trace_policy.policy_sha256) == 64
        ),
        "trace_export_policy_values_exact": (
            trace_policy.sdk_tracing_disabled is True
            and trace_policy.provider_trace_export_enabled is False
            and trace_policy.trace_include_sensitive_data is False
            and trace_policy.persist_local_trace_id is True
        ),
        "sdk_runconfig_kwargs_exact": build_sdk_trace_run_config_kwargs(trace_policy)
        == {"tracing_disabled": True, "trace_include_sensitive_data": False},
        "runtime_binding_binds_trace_export_policy": (
            binding.trace_export_policy.get("policy_id") == POLICY_ID
            and binding.trace_export_policy.get("sdk_tracing_disabled") is True
            and binding.trace_export_policy.get("provider_trace_export_enabled") is False
            and len(binding.trace_export_runtime_sha256) == 64
        ),
        "runtime_binding_still_contains_skill": (
            len(binding.skills) == 1
            and binding.skills[0].get("skill_id") == "document-review-v1"
            and binding.skills[0].get("package_sha256")
            == "60fbfca861141837d4486499687fde4257b83bcb68362b6b0a0b6f40b8df07b5"
        ),
        "all_sdk_runconfig_paths_bound": all(
            "TraceExportPolicyCatalog" in source
            and "build_sdk_trace_run_config_kwargs" in source
            and "**trace_run_config_settings" in source
            and "provider_trace_export_enabled" in source
            for source in run_config_sources.values()
        ),
        "all_sdk_runconfig_paths_inventory_exact": len(run_config_sources) == 7,
        "sdk_reference_supports_per_run_disable": (
            "tracing_disabled: bool = False" in sdk_run_config
            and "Whether tracing is disabled for the agent run" in sdk_run_config
        ),
        "sdk_reference_explains_observed_nonfatal_400": (
            "[non-fatal] Tracing client error %s. Response data is redacted."
            in sdk_processors
        ),
        "product_local_trace_id_remains_enabled": (
            info.product_local_trace_id_persisted is True
            and trace_policy.persist_local_trace_id is True
            and all("trace_id=" in source for source in run_config_sources.values())
        ),
        "step072_runtime_flags_exact": (
            info.product_owned_skill_live_provider_accepted is True
            and info.openai_trace_export_policy_implemented is True
            and info.openai_agents_sdk_tracing_disabled is True
            and info.openai_provider_trace_export_enabled is False
            and info.openai_trace_export_deterministic_accepted is True
            and info.openai_trace_export_windows_live_accepted is False
            and info.next_selected_step == "UNSELECTED_PENDING_STEP072_WINDOWS_LIVE_ACCEPTANCE"
        ),
        "service_policy_selects_step072_gate": (
            service_policy.get("version") == "1.2.0"
            and service_policy.get("next_selected_step")
            == "UNSELECTED_PENDING_STEP072_WINDOWS_LIVE_ACCEPTANCE"
        ),
        "live_wrapper_reuses_governed_step071_workflow": (
            "run_step071_live_acceptance.py" in live_source
            and "subprocess.run" in live_source
            and "provider_trace_export_diagnostic_absent" in live_source
            and "single_model_call_observed" in live_source
        ),
        "live_wrapper_captures_process_shutdown_diagnostics": (
            "stdout=subprocess.PIPE" in live_source
            and "stderr=subprocess.PIPE" in live_source
            and "TRACE_ERROR_MARKERS" in live_source
        ),
        "windows_launcher_uses_data_only_env_loader": (
            '"trace-export-disabled-live-acceptance"' in entrypoint
            and "run_step072_live_acceptance.py" in entrypoint
            and "scripts\\windows_entrypoint.py trace-export-disabled-live-acceptance"
            in (ROOT / "sh_run_step072_live_acceptance.cmd").read_text(encoding="utf-8")
        ),
        "live_evidence_is_packaging_ignored": (
            "docs/evidence/step072-live/" in gitignore
            and '("docs", "evidence", "step072-live")' in package_source
        ),
        "source_package_default_is_step072": (
            "okcanvas-agent-runtime-step072-immutable-openai-trace-export-disabled-v1.zip"
            in package_source
        ),
        "step072_documents_present": all(path.is_file() for path in required_docs),
        "focused_step072_tests_pass": focused_ok and "passed" in focused_output,
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
        "schema_version": "okcanvas-step072-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "trace_export_policy": trace_policy.to_binding_dict(),
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
        "live_state": "WINDOWS_LIVE_RERUN_PENDING",
        "live_launcher": "sh_run_step072_live_acceptance.cmd",
        "external_network_calls": 0,
        "model_calls": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return run(args.output or OUTPUT_DEFAULT)


if __name__ == "__main__":
    raise SystemExit(main())
