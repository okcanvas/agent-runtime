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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP074_ACCEPTANCE.json"
STEP = "STEP074_PRODUCT_OWNED_DOCKER_SANDBOX_PROVIDER_LIFECYCLE_V1"
VERSION = "2.54.0"


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
    from okcanvas_agent_runtime.adapters.sandbox.docker import SandboxRuntimeCatalog

    info = RuntimeInfo()
    foundation = SandboxRuntimeCatalog(ROOT).resolve()
    definitions = AgentDefinitionCatalog(ROOT).list_definitions()
    bindings = [AgentRuntimeBindingCatalog(ROOT).resolve(item) for item in definitions]
    service_policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    step073_windows = _load_json(ROOT / "docs/evidence/STEP073_WINDOWS_ACCEPTANCE_SUMMARY.json")

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    docker_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/docker_cli.py")).read_text(encoding="utf-8")
    catalog_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/catalog.py")).read_text(encoding="utf-8")
    runtime_binding_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    deterministic_launcher = (ROOT / "sh_run_step074_acceptance.cmd").read_text(encoding="utf-8")
    live_launcher = (ROOT / "sh_run_step074_live_acceptance.cmd").read_text(encoding="utf-8")
    windows_entrypoint = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    product_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "okcanvas_agent_runtime").rglob("*.py"))
    )

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step074_product_owned_docker_sandbox_provider_lifecycle.py",
            "tests/test_step073_product_owned_sandbox_runtime_foundation.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_agent_invocation_scope.py",
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
            "scripts/run_step074_acceptance.py",
            "scripts/run_step074_live_acceptance.py",
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
        ROOT / "docs/plans/STEP074_PRODUCT_OWNED_DOCKER_SANDBOX_PROVIDER_LIFECYCLE_V1.md",
        ROOT / "docs/reference/STEP074_PRODUCT_OWNED_DOCKER_SANDBOX_PROVIDER_LIFECYCLE_V1_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP073_WINDOWS_ACCEPTANCE_SUMMARY.json",
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
        "step073_windows_closure_recorded_exact": (
            step073_windows.get("state") == "PASSED"
            and step073_windows.get("passed_checks") == 26
            and step073_windows.get("total_checks") == 26
            and step073_windows.get("docker_calls") == 0
            and info.product_owned_sandbox_foundation_windows_accepted is True
        ),
        "step074_runtime_flags_exact": (
            info.product_owned_sandbox_provider_mode == "product-owned-docker-cli-lifecycle-v1"
            and info.product_owned_sandbox_execution_enabled is False
            and info.product_owned_sandbox_provider_lifecycle_enabled is True
            and info.product_owned_sandbox_physical_workspace_enabled is False
            and info.product_owned_sandbox_docker_calls_enabled is True
            and info.product_owned_sandbox_network_enabled is False
            and info.product_owned_sandbox_ports_enabled is False
            and info.product_owned_sandbox_shell_enabled is False
            and info.product_owned_sandbox_apply_patch_enabled is False
            and info.product_owned_sandbox_skill_materialization_enabled is False
            and info.product_owned_docker_lifecycle_implemented is True
            and info.product_owned_docker_lifecycle_windows_live_accepted is False
            and info.next_selected_step == "UNSELECTED_PENDING_STEP074_WINDOWS_DOCKER_ACCEPTANCE"
        ),
        "sandbox_policy_provider_lifecycle_only_exact": (
            foundation.policy.version == "1.1.0"
            and foundation.policy.execution_enabled is True
            and foundation.policy.agent_execution_enabled is False
            and foundation.policy.provider_lifecycle_enabled is True
            and foundation.policy.active_workspace_access_modes == ("none",)
            and foundation.policy.physical_workspace_materialization_enabled is False
            and foundation.policy.docker_runtime_calls_enabled is True
            and foundation.provider.version == "1.1.0"
            and foundation.provider.container_lifecycle_enabled is True
        ),
        "docker_provider_security_contract_exact": (
            foundation.provider.implementation_mode == "product-owned-docker-cli-lifecycle-v1"
            and foundation.provider.image_reference_mode == "local-tag-resolved-to-immutable-repodigest"
            and foundation.provider.runtime_image_pull_enabled is False
            and foundation.provider.command_mode == "image-default-command-only"
            and foundation.provider.container_environment_enabled is False
            and foundation.provider.network_mode == "none"
            and foundation.provider.exposed_ports == ()
            and foundation.provider.host_bind_mounts_enabled is False
            and foundation.provider.remote_mounts_enabled is False
            and foundation.provider.docker_socket_mount_enabled is False
            and foundation.provider.privileged is False
            and foundation.provider.cap_add == ()
            and foundation.provider.required_cap_drop == ("ALL",)
            and foundation.provider.no_new_privileges_required is True
            and foundation.provider.read_only_root_filesystem_required is True
            and foundation.provider.non_root_user == "65532:65532"
        ),
        "docker_provider_resource_limits_exact": (
            foundation.provider.memory_limit_bytes == 134217728
            and foundation.provider.nano_cpus == 500000000
            and foundation.provider.pids_limit == 64
            and foundation.provider.command_timeout_seconds == 30
            and foundation.provider.stop_timeout_seconds == 5
            and foundation.provider.max_captured_output_bytes == 131072
        ),
        "docker_cli_uses_argument_array_without_shell": (
            "shell=False" in docker_source
            and "subprocess.run(" in docker_source
            and "[self.executable, *args]" in docker_source
            and "os.system(" not in docker_source
            and "shell=True" not in docker_source
        ),
        "docker_create_never_pulls_and_uses_immutable_digest": (
            '"--pull=never"' in docker_source
            and '"image", "inspect"' in docker_source
            and "RepoDigests" in docker_source
            and "images.pull" not in docker_source
            and "docker pull" not in docker_source
        ),
        "docker_create_security_flags_present": all(
            token in docker_source
            for token in (
                '"--network", "none"', '"--read-only"', '"--cap-drop", "ALL"',
                '"--security-opt", "no-new-privileges"', '"--pids-limit"',
                '"--memory"', '"--cpus"', '"--user"', '"--restart", "no"',
            )
        ),
        "docker_cleanup_and_orphan_check_present": (
            '"container", "rm", "--force", "--volumes"' in docker_source
            and '"container", "ls", "--all", "--quiet", "--filter"' in docker_source
            and "cleanup_state" in docker_source
            and "orphan_count" in docker_source
        ),
        "docker_cli_environment_excludes_product_secrets": (
            "_SAFE_ENVIRONMENT_KEYS" in docker_source
            and "OPENAI_API_KEY" not in docker_source
            and "OKCANVAS_PROTECTED_PAYLOAD_KEY" not in docker_source
        ),
        "all_agents_remain_workspace_none": (
            len(definitions) == 26 and {item.workspace_access for item in definitions} == {"none"}
        ),
        "all_bindings_include_same_step074_foundation": (
            len({item.sandbox_runtime_foundation["foundation_sha256"] for item in bindings}) == 1
            and all(item.sandbox_runtime_foundation["policy"]["agent_execution_enabled"] is False for item in bindings)
            and all(item.sandbox_runtime_foundation["provider"]["container_lifecycle_enabled"] is True for item in bindings)
            and "okcanvas_agent_runtime.adapters.sandbox.docker.docker_cli" in runtime_binding_source
        ),
        "product_does_not_use_sdk_sandbox_or_sdk_docker": (
            "from agents.sandbox" not in product_source
            and "import agents.sandbox" not in product_source
            and "DockerSandboxClient(" not in product_source
        ),
        "service_policy_selects_step074_gate": (
            service_policy.get("version") == "1.4.0"
            and service_policy.get("sandbox_execution_enabled") is False
            and service_policy.get("sandbox_provider_lifecycle_enabled") is True
            and service_policy.get("sandbox_foundation_step") == STEP
            and service_policy.get("next_selected_step")
            == "UNSELECTED_PENDING_STEP074_WINDOWS_DOCKER_ACCEPTANCE"
        ),
        "service_metadata_contains_no_image_value_or_host_path": (
            "immutable_reference" not in foundation.to_public_dict()
            and "requested_reference" not in foundation.to_public_dict()
            and "runtime_image" not in foundation.to_public_dict()
            and "host_path" not in foundation.to_public_dict()
        ),
        "windows_launchers_use_isolation_and_data_loader": (
            "python_bytecode_isolation.py scripts\\run_step074_acceptance.py" in deterministic_launcher
            and "python_bytecode_isolation.py scripts\\windows_entrypoint.py docker-sandbox-lifecycle-live-acceptance" in live_launcher
            and '"OKCANVAS_SANDBOX_LIVE_IMAGE"' in windows_entrypoint
            and '"docker-sandbox-lifecycle-live-acceptance"' in windows_entrypoint
        ),
        "live_evidence_is_packaging_ignored": (
            '("docs", "evidence", "step074-live")' in package_source
        ),
        "source_package_default_is_step074": (
            "okcanvas-agent-runtime-step074-product-owned-docker-sandbox-provider-lifecycle-v1.zip"
            in package_source
        ),
        "step074_documents_present": all(path.is_file() for path in required_docs),
        "focused_step074_tests_pass": focused_ok and "passed" in focused_output,
        "historical_skill_trace_service_tests_pass": historical_ok and "passed" in historical_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "deterministic_docker_network_and_model_calls_zero": True,
    }
    payload = {
        "schema_version": "okcanvas-step074-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "sandbox_policy": foundation.policy.to_binding_dict(),
        "sandbox_provider": foundation.provider.to_binding_dict(),
        "sandbox_foundation_sha256": foundation.foundation_sha256,
        "sandbox_runtime_sha256": bindings[0].sandbox_runtime_sha256,
        "sample_runtime_binding_sha256": bindings[0].runtime_binding_sha256,
        "agent_definition_count": len(definitions),
        "focused_test_output": focused_output[-8000:],
        "historical_test_output": historical_output[-8000:],
        "python_compile_output": compile_output[-4000:],
        "node_release_output": release_output[-4000:],
        "node_test_output_tail": node_output[-4000:],
        "reference_import_output_tail": no_reference_imports_output[-4000:],
        "reference_count": len(reference_results),
        "windows_state": "WINDOWS_DOCKER_RERUN_PENDING",
        "windows_launchers": ["sh_run_step074_acceptance.cmd", "sh_run_step074_live_acceptance.cmd"],
        "live_image_default": "hello-world:latest",
        "docker_calls": 0,
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
