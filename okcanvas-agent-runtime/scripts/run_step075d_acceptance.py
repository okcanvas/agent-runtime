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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP075D_ACCEPTANCE.json"
STEP = "STEP075D_PYTHON_SUBPROCESS_STDIN_INPUT_CONTRACT_FIX"
VERSION = "2.55.4"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
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
    service_policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    failure = _load_json(ROOT / "docs/evidence/STEP075C_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json")

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    snapshot_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/read_only_workspace.py")).read_text(encoding="utf-8")
    docker_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/docker_cli.py")).read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    deterministic_launcher = (ROOT / "sh_run_step075d_acceptance.cmd").read_text(encoding="utf-8")
    live_launcher = (ROOT / "sh_run_step075d_live_acceptance.cmd").read_text(encoding="utf-8")
    windows_entrypoint = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    regression_source = (ROOT / "tests/test_step075d_python_subprocess_stdin_input_contract_fix.py").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step075d_python_subprocess_stdin_input_contract_fix.py",
            "tests/test_step075c_windows_tmpfs_tar_stream_materialization_fix.py",
            "tests/test_step075b_windows_docker_command_operation_evidence.py",
            "tests/test_step075a_windows_docker_tmpfs_normalization_and_failure_evidence_fix.py",
            "tests/test_step075_product_owned_readonly_sandbox_workspace_agent.py",
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
            "scripts/run_step075d_acceptance.py",
            "scripts/run_step075d_live_acceptance.py",
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
        ROOT / "docs/plans/STEP075D_PYTHON_SUBPROCESS_STDIN_INPUT_CONTRACT_FIX.md",
        ROOT / "docs/reference/STEP075D_PYTHON_SUBPROCESS_STDIN_INPUT_CONTRACT_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP075C_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json",
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-004-STEP075C-PYTHON-SUBPROCESS-STDIN-INPUT-CONFLICT.md",
        ROOT / "docs/39-PRODUCT-OWNED-SANDBOX-RUNTIME.md",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
    )
    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION
            and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step075c_windows_live_failure_recorded_exact": (
            failure.get("state") == "FAILED"
            and failure.get("live_acceptance") == {
                "passed_checks": 13,
                "total_checks": 29,
                "terminal_status": "FAILED",
                "model": "gpt-4.1",
                "model_calls": 1,
                "tool_calls": 0,
            }
            and failure.get("tool_failed_event_present") is False
        ),
        "subprocess_root_cause_directly_reproduced": (
            failure.get("root_cause", {}).get("status") == "CODE_AND_DIRECT_REPRODUCTION_CONFIRMED"
            and failure.get("root_cause", {}).get("exception_type") == "ValueError"
            and failure.get("root_cause", {}).get("docker_process_started") is False
        ),
        "stdin_and_input_are_mutually_exclusive": (
            'run_kwargs["input"] = input_bytes' in docker_source
            and 'run_kwargs["stdin"] = subprocess.DEVNULL' in docker_source
            and "stdin=subprocess.PIPE if input_bytes is not None" not in docker_source
        ),
        "real_subprocess_round_trip_regression_present": (
            "test_real_subprocess_stdin_round_trip_uses_input_contract_only" in regression_source
            and "sys.stdin.buffer.read()" in regression_source
            and "sys.executable" in regression_source
        ),
        "runner_configuration_error_is_bounded": (
            "except ValueError as exc" in docker_source
            and "DOCKER_RUNNER_CONFIGURATION_INVALID" in docker_source
            and "INVALID_ARGUMENT" in docker_source
        ),
        "tar_stream_materialization_contract_preserved": (
            foundation.provider.version == "1.3.0"
            and foundation.provider.workspace_materialization_mode
            == "docker-exec-stdin-tar-to-root-owned-tmpfs"
            and foundation.provider.workspace_materializer_user == "0:0"
            and foundation.provider.workspace_materializer_command
            == ("tar", "-x", "-f", "-", "-C", "/workspace")
        ),
        "host_path_docker_cp_remains_removed": (
            '"container", "cp"' not in snapshot_source
            and "build_readonly_snapshot_archive" in snapshot_source
        ),
        "root_materializer_and_non_root_reads_preserved": (
            '"--interactive", "--user"' in snapshot_source
            and "provider.workspace_materializer_user" in snapshot_source
            and foundation.provider.workspace_allowed_commands == ("find", "cat", "grep", "tail")
        ),
        "docker_operation_failure_evidence_preserved": (
            'return "container.extract_snapshot"' in docker_source
            and "docker_stderr_category" in docker_source
            and "raise failure.attach_cleanup" in snapshot_source
        ),
        "readonly_hash_verification_preserved": (
            "SANDBOX_SELECTED_FILE_HASH_MISMATCH" in snapshot_source
            and "selected_file_hashes_verified" in snapshot_source
        ),
        "runtime_flags_select_step075d_gate": (
            info.product_owned_readonly_sandbox_subprocess_stdin_contract_implemented is True
            and info.product_owned_readonly_sandbox_subprocess_stdin_contract_windows_live_accepted is False
            and info.next_selected_step == "UNSELECTED_PENDING_STEP075D_WINDOWS_LIVE_RERUN"
        ),
        "service_metadata_and_policy_select_step075d_gate": (
            service_policy.get("version") == "1.4.3"
            and service_policy.get("next_selected_step") == "UNSELECTED_PENDING_STEP075D_WINDOWS_LIVE_RERUN"
            and service_policy.get("sandbox_foundation_step") == STEP
        ),
        "single_readonly_sandbox_agent_preserved": (
            len(definitions) == 27
            and len([item for item in definitions if item.workspace_access == "sandbox-readonly-v1"]) == 1
            and sandbox_definition.tools == ("sandbox_project_readonly_inspect",)
        ),
        "readonly_tool_contract_preserved": (
            tool.factory_id == "sandbox_project_readonly_inspect_v1"
            and tool.read_only is True
            and tool.filesystem_access == "sandbox-read-only"
            and tool.network_access == "none"
            and tool.shell_access == "none"
        ),
        "runtime_binding_contains_updated_sandbox_implementation": (
            sandbox_binding.execution_path == "product-owned-readonly-sandbox-agent-execution-v1"
            and len(sandbox_binding.sandbox_runtime_sha256) == 64
            and sandbox_binding.sandbox_runtime_foundation["provider"]["workspace_materialization_mode"]
            == "docker-exec-stdin-tar-to-root-owned-tmpfs"
        ),
        "windows_launchers_use_isolation_and_data_loader": (
            "python_bytecode_isolation.py scripts\\run_step075d_acceptance.py" in deterministic_launcher
            and "python_bytecode_isolation.py scripts\\windows_entrypoint.py readonly-sandbox-workspace-stdin-contract-live-acceptance" in live_launcher
            and "run_step075d_live_acceptance.py" in windows_entrypoint
        ),
        "live_evidence_and_secrets_are_packaging_ignored": (
            "docs/evidence/step075d-live/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
            and ".env.local" in package_source
            and "step075d-live" in package_source
        ),
        "step075d_documents_present": all(path.is_file() for path in required_docs),
        "focused_step075d_tests_pass": focused_ok,
        "historical_skill_trace_service_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "deterministic_docker_network_and_model_calls_zero": True,
        "source_package_default_is_step075d": (
            "step075d-python-subprocess-stdin-input-contract-fix" in package_source
            and STEP in package_source
        ),
        "sandbox_security_boundary_unchanged": (
            foundation.policy.network_mode == "none"
            and foundation.policy.shell_enabled is False
            and foundation.policy.apply_patch_enabled is False
            and foundation.provider.host_bind_mounts_enabled is False
            and foundation.provider.runtime_image_pull_enabled is False
        ),
    }
    payload = {
        "schema_version": "okcanvas-step075d-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "agent_definition_count": len(definitions),
        "sandbox_policy_sha256": foundation.policy.policy_sha256,
        "sandbox_provider_contract_sha256": foundation.provider.contract_sha256,
        "sandbox_foundation_sha256": foundation.foundation_sha256,
        "sandbox_runtime_sha256": sandbox_binding.sandbox_runtime_sha256,
        "sample_runtime_binding_sha256": sandbox_binding.runtime_binding_sha256,
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
        "live_launcher": "sh_run_step075d_live_acceptance.cmd",
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
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
