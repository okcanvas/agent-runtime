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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP075A_ACCEPTANCE.json"
STEP = "STEP075A_WINDOWS_DOCKER_TMPFS_NORMALIZATION_AND_FAILURE_EVIDENCE_FIX"
VERSION = "2.55.1"


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
    bindings = [AgentRuntimeBindingCatalog(ROOT).resolve(item) for item in definitions]
    sandbox_definition = AgentDefinitionCatalog(ROOT).resolve("sandbox-readonly-coding-agent")
    sandbox_binding = AgentRuntimeBindingCatalog(ROOT).resolve(sandbox_definition)
    tool = FunctionToolRuntimeCatalog(ROOT).resolve("sandbox_project_readonly_inspect")
    service_policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    step074_windows = _load_json(ROOT / "docs/evidence/STEP074_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    step075_failure = _load_json(ROOT / "docs/evidence/STEP075_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json")

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    snapshot_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/read_only_workspace.py")).read_text(encoding="utf-8")
    gateway_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    catalog_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/catalog.py")).read_text(encoding="utf-8")
    agent_catalog_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/agent_definitions/catalog.py")).read_text(encoding="utf-8")
    product_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "okcanvas_agent_runtime").rglob("*.py"))
    )
    deterministic_launcher = (ROOT / "sh_run_step075a_acceptance.cmd").read_text(encoding="utf-8")
    live_launcher = (ROOT / "sh_run_step075a_live_acceptance.cmd").read_text(encoding="utf-8")
    windows_entrypoint = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
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
            "scripts/run_step075a_acceptance.py",
            "scripts/run_step075a_live_acceptance.py",
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

    original_agents = [item for item in definitions if item.agent_id != "sandbox-readonly-coding-agent"]
    required_docs = (
        ROOT / "docs/plans/STEP075A_WINDOWS_DOCKER_TMPFS_NORMALIZATION_AND_FAILURE_EVIDENCE_FIX.md",
        ROOT / "docs/reference/STEP075A_WINDOWS_DOCKER_TMPFS_NORMALIZATION_AND_FAILURE_EVIDENCE_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP075_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json",
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-001-STEP075-WINDOWS-DOCKER-TMPFS-NORMALIZATION.md",
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
        "step074_windows_docker_live_closure_exact": (
            step074_windows.get("state") == "PASSED"
            and step074_windows.get("deterministic_acceptance") == {"passed_checks": 28, "total_checks": 28}
            and step074_windows.get("live_acceptance") == {"passed_checks": 27, "total_checks": 27}
            and step074_windows.get("docker_calls") == 8
            and step074_windows.get("cleanup_state") == "COMPLETED"
            and step074_windows.get("orphan_count") == 0
            and info.product_owned_docker_lifecycle_windows_live_accepted is True
        ),
        "step075_windows_live_failure_recorded_exact": (
            step075_failure.get("state") == "FAILED"
            and step075_failure.get("deterministic_acceptance") == {"passed_checks": 28, "total_checks": 28}
            and step075_failure.get("live_acceptance") == {"passed_checks": 13, "total_checks": 28}
            and step075_failure.get("model_calls") == 1
            and step075_failure.get("terminal_status") == "FAILED"
            and step075_failure.get("acceptance_workspace_state") == "PRESERVED"
            and step075_failure.get("product_database_relative_path") == "databases/product.sqlite3"
        ),
        "tmpfs_semantic_normalization_and_fail_closed_checks_present": (
            "_tmpfs_workspace_semantically_matches" in snapshot_source
            and '"tmpfs_workspace_semantic"' in snapshot_source
            and 'required_flags = {"rw", "noexec", "nosuid", "nodev"}' in snapshot_source
            and 'forbidden_flags = {"ro", "exec", "suid", "dev"}' in snapshot_source
            and '== 0o755' in snapshot_source
        ),
        "bounded_sandbox_tool_failure_evidence_present": (
            '"tool.failed"' in gateway_source
            and '"code": exc.code' in gateway_source
            and 'payload_schema_version="okcanvas-function-tool-failed-v1"' in gateway_source
            and '"arguments_persisted": False' in gateway_source
            and '"result_persisted": False' in gateway_source
        ),
        "step075_runtime_flags_exact": (
            info.product_owned_readonly_sandbox_agent_implemented is True
            and info.product_owned_readonly_sandbox_agent_id == "sandbox-readonly-coding-agent"
            and info.product_owned_readonly_sandbox_tool_id == "sandbox_project_readonly_inspect"
            and info.product_owned_readonly_sandbox_workspace_mode == "sandbox-readonly-v1"
            and info.product_owned_readonly_sandbox_materialization_mode == "docker-cp-to-root-owned-tmpfs"
            and info.product_owned_readonly_sandbox_network_enabled is False
            and info.product_owned_readonly_sandbox_shell_enabled is False
            and info.product_owned_readonly_sandbox_apply_patch_enabled is False
            and info.product_owned_readonly_sandbox_windows_live_accepted is False
            and info.product_owned_readonly_sandbox_tmpfs_semantic_validation_implemented is True
            and info.product_owned_readonly_sandbox_failure_evidence_implemented is True
            and info.next_selected_step == "UNSELECTED_PENDING_STEP075A_WINDOWS_LIVE_RERUN"
        ),
        "sandbox_policy_readonly_mode_exact": (
            foundation.policy.version == "1.2.0"
            and foundation.policy.agent_execution_enabled is True
            and foundation.policy.active_workspace_access_modes == ("none", "sandbox-readonly-v1")
            and foundation.policy.physical_workspace_materialization_enabled is True
            and foundation.policy.network_mode == "none"
            and foundation.policy.shell_enabled is False
            and foundation.policy.apply_patch_enabled is False
            and foundation.policy.skill_materialization_enabled is False
        ),
        "sandbox_provider_readonly_workspace_contract_exact": (
            foundation.provider.version == "1.2.0"
            and foundation.provider.implementation_mode == "product-owned-readonly-workspace-agent-v1"
            and foundation.provider.workspace_materialization_mode == "docker-cp-to-root-owned-tmpfs"
            and foundation.provider.workspace_mount_path == "/workspace"
            and foundation.provider.workspace_tmpfs_max_bytes == 33_554_432
            and foundation.provider.workspace_max_files == 3_000
            and foundation.provider.workspace_max_total_bytes == 33_554_432
            and foundation.provider.workspace_max_file_bytes == 524_288
            and foundation.provider.workspace_allowed_commands == ("find", "cat", "grep", "tail")
        ),
        "single_readonly_sandbox_agent_exact": (
            len(definitions) == 27
            and len(original_agents) == 26
            and all(item.workspace_access == "none" for item in original_agents)
            and sandbox_definition.workspace_access == "sandbox-readonly-v1"
            and sandbox_definition.tools == ("sandbox_project_readonly_inspect",)
            and not sandbox_definition.mcp_servers
            and not sandbox_definition.hosted_tools
            and not sandbox_definition.skills
            and not sandbox_definition.handoffs
            and not sandbox_definition.agent_tools
        ),
        "readonly_sandbox_tool_contract_exact": (
            tool.factory_id == "sandbox_project_readonly_inspect_v1"
            and tool.read_only is True
            and tool.filesystem_access == "sandbox-read-only"
            and tool.network_access == "none"
            and tool.shell_access == "none"
            and tool.arguments_persisted is False
            and tool.result_persisted_in_events is False
            and tool.output_model.__name__ == "SandboxProjectReadonlyInspectOutput"
        ),
        "runtime_binding_contains_step075_foundation": (
            sandbox_binding.execution_path == "product-owned-readonly-sandbox-agent-execution-v1"
            and sandbox_binding.sandbox_runtime_foundation["policy"]["agent_execution_enabled"] is True
            and sandbox_binding.sandbox_runtime_foundation["provider"]["workspace_mount_path"] == "/workspace"
            and len({item.sandbox_runtime_foundation["foundation_sha256"] for item in bindings}) == 1
        ),
        "snapshot_is_bounded_canonical_utf8_and_symlink_closed": all(
            token in snapshot_source
            for token in (
                "workspace_max_files", "workspace_max_total_bytes", "workspace_max_file_bytes",
                "SANDBOX_SOURCE_SYMLINK_FORBIDDEN", 'decoded.encode("utf-8")',
                ".okcanvas-snapshot-manifest.json", "snapshot_sha256",
            )
        ),
        "workspace_materialization_uses_tmpfs_and_docker_cp": (
            '"--tmpfs", tmpfs_value' in snapshot_source
            and '"container", "cp"' in snapshot_source
            and '"--pull=never"' in snapshot_source
            and '"--network", "none"' in snapshot_source
            and '"--read-only"' in snapshot_source
            and '"--cap-drop", "ALL"' in snapshot_source
        ),
        "readonly_tool_commands_are_fixed_without_shell": (
            '("find", "cat", "grep", "tail")' in snapshot_source
            and '"container", "exec", container_id, "find"' in snapshot_source
            and '"container", "exec", container_id, "cat"' in snapshot_source
            and '"sh", "-c"' not in snapshot_source
            and '"bash", "-c"' not in snapshot_source
            and "shell=True" not in snapshot_source
        ),
        "selected_container_file_hashes_verified": (
            "SANDBOX_SELECTED_FILE_HASH_MISMATCH" in snapshot_source
            and "selected_file_hashes_verified" in snapshot_source
            and "image_binding_sha256" in gateway_source
            and "raw_workspace_content_persisted" in gateway_source
        ),
        "sandbox_cleanup_and_orphan_reconciliation_present": (
            '"container", "rm", "--force", "--volumes"' in snapshot_source
            and '"container", "ls", "--all", "--quiet", "--filter"' in snapshot_source
            and "SANDBOX_CLEANUP_FAILED" in snapshot_source
        ),
        "no_sdk_sandbox_agent_or_default_capabilities": (
            "SandboxAgent(" not in product_source
            and "Capabilities.default(" not in product_source
            and "DockerSandboxClient(" not in product_source
            and "from agents.sandbox" not in product_source
        ),
        "agent_catalog_rejects_unapproved_workspace_modes": (
            '"sandbox-readonly-v1"' in agent_catalog_source
            and '"sandbox-patch-v1"' not in agent_catalog_source
            and '"sandbox-shell-v1"' not in agent_catalog_source
        ),
        "service_metadata_and_policy_select_step075_gate": (
            service_policy.get("next_selected_step") == "UNSELECTED_PENDING_STEP075A_WINDOWS_LIVE_RERUN"
            and service_policy.get("sandbox_execution_enabled") is True
            and service_policy.get("sandbox_foundation_step") == STEP
        ),
        "windows_launchers_use_isolation_and_data_loader": (
            "python_bytecode_isolation.py scripts\\run_step075a_acceptance.py" in deterministic_launcher
            and "python_bytecode_isolation.py scripts\\windows_entrypoint.py readonly-sandbox-workspace-normalized-live-acceptance" in live_launcher
            and "readonly-sandbox-workspace-normalized-live-acceptance" in windows_entrypoint
            and "run_step075a_live_acceptance.py" in windows_entrypoint
        ),
        "live_evidence_and_local_secrets_are_packaging_ignored": (
            "docs/evidence/step075-live/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
            and ".env.local" in package_source
            and "step075-live" in package_source
        ),
        "step075a_documents_present": all(path.is_file() for path in required_docs),
        "focused_step075a_tests_pass": focused_ok,
        "historical_skill_trace_service_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "deterministic_docker_network_and_model_calls_zero": True,
        "source_package_default_is_step075a": (
            "step075a-windows-docker-tmpfs-normalization-and-failure-evidence-fix" in package_source
            and "STEP075A_WINDOWS_DOCKER_TMPFS_NORMALIZATION_AND_FAILURE_EVIDENCE_FIX" in package_source
        ),
    }
    payload = {
        "schema_version": "okcanvas-step075a-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "agent_definition_count": len(definitions),
        "workspace_none_agent_count": len(original_agents),
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
        "live_launcher": "sh_run_step075a_live_acceptance.cmd",
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
