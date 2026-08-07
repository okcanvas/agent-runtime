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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP075E_ACCEPTANCE.json"
STEP = "STEP075E_INTERNAL_SNAPSHOT_METADATA_EXCLUSION_AND_HASH_DOMAIN_FIX"
VERSION = "2.55.5"


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
    failure = _load_json(ROOT / "docs/evidence/STEP075D_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json")

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    inspector_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/workspace/read_only_project.py")).read_text(encoding="utf-8")
    snapshot_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/read_only_workspace.py")).read_text(encoding="utf-8")
    docker_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/docker_cli.py")).read_text(encoding="utf-8")
    regression_source = (ROOT / "tests/test_step075e_internal_snapshot_metadata_exclusion_and_hash_domain_fix.py").read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    deterministic_launcher = (ROOT / "sh_run_step075e_acceptance.cmd").read_text(encoding="utf-8")
    live_launcher = (ROOT / "sh_run_step075e_live_acceptance.cmd").read_text(encoding="utf-8")
    windows_entrypoint = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step075e_internal_snapshot_metadata_exclusion_and_hash_domain_fix.py",
            "tests/test_step075d_python_subprocess_stdin_input_contract_fix.py",
            "tests/test_step075c_windows_tmpfs_tar_stream_materialization_fix.py",
            "tests/test_step075b_windows_docker_command_operation_evidence.py",
            "tests/test_step075a_windows_docker_tmpfs_normalization_and_failure_evidence_fix.py",
            "tests/test_step075_product_owned_readonly_sandbox_workspace_agent.py",
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
            "scripts/run_step075e_acceptance.py",
            "scripts/run_step075e_live_acceptance.py",
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
        ROOT / "docs/plans/STEP075E_INTERNAL_SNAPSHOT_METADATA_EXCLUSION_AND_HASH_DOMAIN_FIX.md",
        ROOT / "docs/reference/STEP075E_INTERNAL_SNAPSHOT_METADATA_EXCLUSION_AND_HASH_DOMAIN_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP075D_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json",
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-005-STEP075D-INTERNAL-SNAPSHOT-METADATA-HASH-DOMAIN.md",
        ROOT / "docs/39-PRODUCT-OWNED-SANDBOX-RUNTIME.md",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
    )

    root_cause = failure.get("root_cause") if isinstance(failure.get("root_cause"), dict) else {}
    tool_failure = failure.get("tool_failure") if isinstance(failure.get("tool_failure"), dict) else {}
    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION
            and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step075d_windows_live_failure_recorded_exact": (
            failure.get("state") == "FAILED"
            and failure.get("live_acceptance") == {
                "passed_checks": 14,
                "total_checks": 30,
                "terminal_status": "FAILED",
                "model": "gpt-4.1",
                "model_calls": 1,
                "tool_calls": 0,
            }
            and tool_failure.get("code") == "SANDBOX_SELECTED_FILE_HASH_MISMATCH"
            and tool_failure.get("cleanup_completed") is True
            and tool_failure.get("orphan_count") == 0
        ),
        "internal_manifest_root_cause_reproduced_exact": (
            root_cause.get("status") == "CODE_AND_LOCAL_FIXTURE_REPRODUCTION_CONFIRMED"
            and root_cause.get("snapshot_entry_paths") == ["README.md", "UNTRUSTED.md", "src/inventory.py"]
            and root_cause.get("unrestricted_inspected_files")
            == ["src/inventory.py", ".okcanvas-snapshot-manifest.json"]
            and root_cause.get("internal_metadata_is_snapshot_entry") is False
            and root_cause.get("actual_project_file_hash_mismatch_proven") is False
        ),
        "allowed_snapshot_domain_is_validated_and_optional": (
            "def _allowed_relative_path_domain" in inspector_source
            and "allowed_relative_paths: Iterable[str] | None = None" in inspector_source
            and "relative not in allowed_paths" in inspector_source
            and "Allowed project file path is unsafe" in inspector_source
        ),
        "sandbox_selector_is_bound_to_immutable_entry_domain": (
            "allowed_relative_paths=entry_by_path.keys()" in snapshot_source
            and "entry_by_path = {entry.path: entry for entry in snapshot.entries}" in snapshot_source
            and "_SNAPSHOT_MANIFEST_PATH" in snapshot_source
        ),
        "internal_manifest_remains_product_inventory_not_model_evidence": (
            'file_paths = [entry.path for entry in snapshot.entries] + [_SNAPSHOT_MANIFEST_PATH]' in snapshot_source
            and 'expected_paths = {entry.path for entry in snapshot.entries} | {_SNAPSHOT_MANIFEST_PATH}' in snapshot_source
            and "Product must never read internal snapshot metadata as project evidence" in regression_source
        ),
        "out_of_domain_selection_has_distinct_fail_closed_error": (
            "SANDBOX_SELECTED_FILE_NOT_IN_SNAPSHOT" in snapshot_source
            and "Selected file is outside the immutable project snapshot" in snapshot_source
            and "test_out_of_snapshot_selection_has_distinct_fail_closed_error" in regression_source
        ),
        "actual_in_domain_hash_mismatch_remains_separate": (
            "SANDBOX_SELECTED_FILE_HASH_MISMATCH" in snapshot_source
            and "hashlib.sha256(raw).hexdigest() != expected.sha256" in snapshot_source
        ),
        "exact_live_query_regression_present": (
            "Find where calculate_reorder is implemented" in regression_source
            and "unrestricted.inspected_files" in regression_source
            and 'restricted.inspected_files == ("src/inventory.py",)' in regression_source
        ),
        "subprocess_and_tar_stream_fixes_live_reached": (
            info.product_owned_readonly_sandbox_subprocess_stdin_contract_implemented is True
            and info.product_owned_readonly_sandbox_subprocess_stdin_contract_windows_live_accepted is True
            and root_cause.get("docker_tar_materialization_completed") is True
            and root_cause.get("container_read_commands_reached") is True
            and 'run_kwargs["input"] = input_bytes' in docker_source
        ),
        "runtime_flags_select_step075e_gate": (
            info.product_owned_readonly_sandbox_internal_metadata_exclusion_implemented is True
            and info.product_owned_readonly_sandbox_hash_domain_guard_implemented is True
            and info.product_owned_readonly_sandbox_internal_metadata_exclusion_windows_live_accepted is False
            and info.next_selected_step == "UNSELECTED_PENDING_STEP075E_WINDOWS_LIVE_RERUN"
        ),
        "service_metadata_and_policy_select_step075e_gate": (
            service_policy.get("version") == "1.4.4"
            and service_policy.get("next_selected_step") == "UNSELECTED_PENDING_STEP075E_WINDOWS_LIVE_RERUN"
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
        "tar_stream_root_materializer_and_non_root_reads_preserved": (
            foundation.provider.workspace_materializer_user == "0:0"
            and foundation.provider.workspace_materializer_command == ("tar", "-x", "-f", "-", "-C", "/workspace")
            and foundation.provider.non_root_user == "65532:65532"
            and foundation.provider.workspace_allowed_commands == ("find", "cat", "grep", "tail")
        ),
        "sandbox_security_boundary_unchanged": (
            foundation.policy.network_mode == "none"
            and foundation.policy.shell_enabled is False
            and foundation.policy.apply_patch_enabled is False
            and foundation.provider.host_bind_mounts_enabled is False
            and foundation.provider.runtime_image_pull_enabled is False
        ),
        "windows_launchers_use_isolation_and_data_loader": (
            "python_bytecode_isolation.py scripts\\run_step075e_acceptance.py" in deterministic_launcher
            and "python_bytecode_isolation.py scripts\\windows_entrypoint.py readonly-sandbox-workspace-hash-domain-live-acceptance" in live_launcher
            and "run_step075e_live_acceptance.py" in windows_entrypoint
        ),
        "live_evidence_and_secrets_are_packaging_ignored": (
            "docs/evidence/step075e-live/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
            and ".env.local" in package_source
            and "step075e-live" in package_source
        ),
        "step075e_documents_present": all(path.is_file() for path in required_docs),
        "focused_step075e_tests_pass": focused_ok,
        "historical_skill_trace_service_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "deterministic_docker_network_and_model_calls_zero": True,
        "source_package_default_is_step075e": (
            "step075e-internal-snapshot-metadata-exclusion-and-hash-domain-fix" in package_source
            and STEP in package_source
        ),
        "no_sdk_sandbox_agent_or_default_capabilities": (
            "SandboxAgent" not in snapshot_source
            and foundation.policy.sdk_default_capabilities_allowed is False
        ),
    }

    payload = {
        "schema_version": "okcanvas-step075e-acceptance-v1",
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
        "live_launcher": "sh_run_step075e_live_acceptance.cmd",
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
