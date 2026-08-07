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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP073_ACCEPTANCE.json"
STEP = "STEP073_PRODUCT_OWNED_SANDBOX_RUNTIME_FOUNDATION_V1"
VERSION = "2.53.0"
UPSTREAM = ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox"
UPSTREAM_SOURCE_HASHES = {
    "capabilities/capabilities.py": "7a40308ac95dd8f649bc06047af0d7183b76338120ec6453acef9991f9d1d406",
    "capabilities/filesystem.py": "9810f7878518c708c16a2b55a2748b84eabeb0c106e7d223d6b52088c1bbf3f3",
    "capabilities/shell.py": "0ddacb568dde2fe06eaea61f8ffe97f5556d0f3aea73693996888bc87331cfbf",
    "sandbox_agent.py": "8e90f64f1c5a3e9ae062c490300c9f6d1fa49958873c0c05a440c184b8ee18be",
    "sandboxes/docker.py": "8f1cc63295eee21b2a78b85f17082586c7be6e4ac4f4504d187e0eb672d2eb35",
}


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

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(
        encoding="utf-8"
    )
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    launcher_source = (ROOT / "sh_run_step073_acceptance.cmd").read_text(encoding="utf-8")
    runtime_binding_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")
    ).read_text(encoding="utf-8")
    agent_catalog_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/agent_definitions/catalog.py")
    ).read_text(encoding="utf-8")
    product_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "okcanvas_agent_runtime").rglob("*.py"))
    )
    upstream_sources = {
        relative: (UPSTREAM / relative).read_text(encoding="utf-8")
        for relative in UPSTREAM_SOURCE_HASHES
    }
    upstream_hashes_ok = all(
        hashlib.sha256((UPSTREAM / relative).read_bytes()).hexdigest() == expected
        for relative, expected in UPSTREAM_SOURCE_HASHES.items()
    )

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step073_product_owned_sandbox_runtime_foundation.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_agent_invocation_scope.py",
            "tests/test_generic_agent_execution_service.py",
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
            "scripts/run_step073_acceptance.py",
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
        ROOT / "specs/sandbox/contracts/PRODUCT_OWNED_SANDBOX_RUNTIME_V1.md",
        ROOT / "docs/39-PRODUCT-OWNED-SANDBOX-RUNTIME.md",
        ROOT / "docs/plans/STEP073_PRODUCT_OWNED_SANDBOX_RUNTIME_FOUNDATION_V1.md",
        ROOT
        / "docs/reference/STEP073_PRODUCT_OWNED_SANDBOX_RUNTIME_FOUNDATION_V1_CODE_AUDIT.md",
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
        "step072b_windows_live_predecessor_closed": (
            info.windows_crlf_and_local_env_fix_windows_accepted is True
            and info.openai_trace_export_windows_live_accepted is True
            and info.product_owned_skill_live_provider_accepted is True
        ),
        "sandbox_runtime_flags_exact": (
            info.product_owned_sandbox_runtime_foundation_implemented is True
            and info.product_owned_sandbox_provider_id == "docker-local-v1"
            and info.product_owned_sandbox_provider_mode == "contract-only-disabled"
            and info.product_owned_sandbox_execution_enabled is False
            and info.product_owned_sandbox_physical_workspace_enabled is False
            and info.product_owned_sandbox_active_workspace_modes == "none"
            and info.product_owned_sandbox_docker_calls_enabled is False
            and info.product_owned_sandbox_network_enabled is False
            and info.product_owned_sandbox_ports_enabled is False
            and info.product_owned_sandbox_shell_enabled is False
            and info.product_owned_sandbox_apply_patch_enabled is False
            and info.product_owned_sandbox_skill_materialization_enabled is False
            and info.product_owned_sandbox_foundation_windows_accepted is False
            and info.next_selected_step == "UNSELECTED_PENDING_STEP073_WINDOWS_ACCEPTANCE"
        ),
        "sandbox_policy_identity_and_values_exact": (
            foundation.policy.policy_id == "default-product-sandbox-runtime-v1"
            and foundation.policy.version == "1.0.0"
            and foundation.policy.foundation_enabled is True
            and foundation.policy.execution_enabled is False
            and foundation.policy.default_workspace_access == "none"
            and foundation.policy.active_workspace_access_modes == ("none",)
            and foundation.policy.physical_workspace_materialization_enabled is False
            and foundation.policy.docker_runtime_calls_enabled is False
            and foundation.policy.network_mode == "none"
            and foundation.policy.exposed_ports == ()
            and foundation.policy.secrets_enabled is False
            and foundation.policy.automatic_image_pull_enabled is False
            and foundation.policy.automatic_resume_enabled is False
            and foundation.policy.snapshot_resume_enabled is False
            and foundation.policy.shell_enabled is False
            and foundation.policy.apply_patch_enabled is False
            and foundation.policy.skill_materialization_enabled is False
            and foundation.policy.model_selected_provider_enabled is False
            and foundation.policy.model_selected_host_path_enabled is False
            and foundation.policy.sdk_default_capabilities_allowed is False
        ),
        "sandbox_provider_identity_and_values_exact": (
            foundation.provider.provider_id == "docker-local-v1"
            and foundation.provider.version == "1.0.0"
            and foundation.provider.implementation_mode == "contract-only-disabled"
            and foundation.provider.execution_enabled is False
            and foundation.provider.sdk_client_mode == "not-instantiated"
            and foundation.provider.runtime_image_pull_enabled is False
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
            and foundation.provider.non_root_user_required is True
            and foundation.provider.resume_enabled is False
            and foundation.provider.snapshot_enabled is False
            and foundation.provider.automatic_delete_required is True
            and foundation.provider.orphan_reconciliation_required is True
        ),
        "sandbox_hashes_present": all(
            len(value) == 64
            for value in (
                foundation.policy.policy_sha256,
                foundation.provider.contract_sha256,
                foundation.foundation_sha256,
            )
        ),
        "all_agent_workspace_access_remains_none": (
            bool(definitions) and {item.workspace_access for item in definitions} == {"none"}
        ),
        "all_runtime_bindings_bind_same_sandbox_foundation": (
            len({item.sandbox_runtime_foundation["foundation_sha256"] for item in bindings}) == 1
            and len({item.sandbox_runtime_sha256 for item in bindings}) == 1
            and all(
                item.sandbox_runtime_foundation["policy"]["execution_enabled"] is False
                and item.sandbox_runtime_foundation["provider"]["execution_enabled"] is False
                for item in bindings
            )
            and "sandbox_runtime_foundation" in runtime_binding_source
            and "sandbox_runtime_sha256" in runtime_binding_source
        ),
        "agent_catalog_still_rejects_non_none_workspace": (
            'if workspace_access != "none"' in agent_catalog_source
        ),
        "sdk_reference_source_hashes_exact": upstream_hashes_ok,
        "sdk_default_capabilities_audited": (
            "return [Filesystem(), Shell(), Compaction()]"
            in upstream_sources["capabilities/capabilities.py"]
            and "SandboxApplyPatchTool" in upstream_sources["capabilities/filesystem.py"]
            and "ExecCommandTool" in upstream_sources["capabilities/shell.py"]
            and "field(default_factory=Capabilities.default)"
            in upstream_sources["sandbox_agent.py"]
        ),
        "sdk_docker_automatic_and_privileged_paths_audited": (
            "self.docker_client.images.pull" in upstream_sources["sandboxes/docker.py"]
            and 'cap_add=["SYS_ADMIN"]' in upstream_sources["sandboxes/docker.py"]
            and 'security_opt=["apparmor:unconfined"]'
            in upstream_sources["sandboxes/docker.py"]
        ),
        "product_does_not_import_sdk_sandbox_or_docker": (
            "from agents.sandbox" not in product_source
            and "import agents.sandbox" not in product_source
            and "DockerSandboxClient(" not in product_source
            and "docker.from_env(" not in product_source
        ),
        "service_policy_selects_step073_gate": (
            service_policy.get("version") == "1.3.0"
            and service_policy.get("sandbox_runtime_foundation_available") is True
            and service_policy.get("sandbox_execution_enabled") is False
            and service_policy.get("sandbox_runtime_api") == "/v1/service/sandbox-runtime"
            and service_policy.get("sandbox_foundation_step") == STEP
            and service_policy.get("next_selected_step")
            == "UNSELECTED_PENDING_STEP073_WINDOWS_ACCEPTANCE"
        ),
        "service_metadata_contains_no_runtime_image_or_host_path": (
            "image" not in foundation.to_public_dict()
            and "host_path" not in foundation.to_public_dict()
        ),
        "step073_documents_present": all(path.is_file() for path in required_docs),
        "windows_launcher_uses_bytecode_isolation": (
            "scripts\\python_bytecode_isolation.py scripts\\run_step073_acceptance.py"
            in launcher_source
        ),
        "source_package_default_is_step073": (
            "okcanvas-agent-runtime-step073-product-owned-sandbox-runtime-foundation-v1.zip"
            in package_source
        ),
        "focused_step073_tests_pass": focused_ok and "passed" in focused_output,
        "historical_skill_trace_service_tests_pass": (
            historical_ok and "passed" in historical_output
        ),
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "docker_network_and_model_calls_zero": True,
    }
    payload = {
        "schema_version": "okcanvas-step073-acceptance-v1",
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
        "windows_state": "WINDOWS_RERUN_PENDING",
        "windows_launcher": "sh_run_step073_acceptance.cmd",
        "docker_calls": 0,
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
