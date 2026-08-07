from __future__ import annotations

import argparse
import ast
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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP080A_ACCEPTANCE.json"
STEP = "STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES"
VERSION = "2.60.1"
LIVE_COMMAND = "architecture-constitution-live-acceptance"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _live_check_count(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    counts = [
        len(node.value.keys)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "checks" for target in node.targets)
        and isinstance(node.value, ast.Dict)
    ]
    if counts != [66]:
        return -1
    return counts[0] + 1


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.agent.capabilities.topology import (
        AgentCapabilityTopologyCatalog,
        CapabilityFoundationCatalog,
        SDKExampleCatalog,
    )
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.core.governance import (
        resolve_architecture_constitution,
        validate_step_compliance_record,
    )
    from scripts.validate_architecture_constitution import validate as validate_constitution
    from scripts.validate_acceptance_launcher_registry import validate as validate_launcher_registry
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
    from scripts.verify_no_reference_imports import find_violations

    info = RuntimeInfo()
    foundation = CapabilityFoundationCatalog(ROOT).resolve()
    examples = SDKExampleCatalog(ROOT).resolve()
    definitions = AgentDefinitionCatalog(ROOT).list_definitions()
    topologies = tuple(
        AgentCapabilityTopologyCatalog(ROOT).resolve(definition) for definition in definitions
    )
    sample_definition = AgentDefinitionCatalog(ROOT).resolve("sandbox-readonly-coding-agent")
    sample_binding = AgentRuntimeBindingCatalog(ROOT).resolve(sample_definition)
    service_policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    architecture_constitution = resolve_architecture_constitution()
    constitution_validation = validate_constitution()
    launcher_registry_validation = validate_launcher_registry()
    compliance_payload = _load_json(ROOT / "docs/evidence/STEP080A_CONSTITUTION_COMPLIANCE.json")
    compliance_summary = validate_step_compliance_record(compliance_payload)
    predecessor = _load_json(ROOT / "docs/evidence/STEP079A_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    entrypoint_source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    live_source_path = ROOT / "scripts/run_step080a_live_acceptance.py"
    live_source = live_source_path.read_text(encoding="utf-8")
    launcher = (ROOT / "sh_run_step080a_live_acceptance.cmd").read_text(encoding="utf-8")
    acceptance_launcher = (ROOT / "sh_run_step080a_acceptance.cmd").read_text(encoding="utf-8")
    discovery_policy = _load_json(ROOT / "specs/capabilities/tool-discovery-policy.json")
    inventory_payload = _load_json(
        ROOT / "specs/capabilities/examples/openai-agents-python-0.19.0.json"
    )

    command_action = next(
        action for action in windows_entrypoint._parser()._actions if action.dest == "command"
    )
    parsed = windows_entrypoint._parser().parse_args([LIVE_COMMAND])

    reference_import_violations = find_violations(ROOT)
    no_reference_imports_output = json.dumps(
        {"ok": not reference_import_violations, "violations": reference_import_violations},
        indent=2,
        sort_keys=True,
    )

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step080a_architecture_constitution_and_compliance_gates.py",
            "tests/test_step080a_windows_entrypoint_architecture_constitution_registration.py",
            "tests/test_step080a_acceptance_launcher_registry.py",
            "tests/test_step080_product_owned_capability_topology_and_tool_discovery_foundation.py",
            "tests/test_step080_windows_entrypoint_capability_topology_registration.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_agent_runtime_binding.py",
            "tests/test_step069_multi_user_service_client_contract.py",
            "tests/test_step079a_windows_entrypoint_command_registration.py",
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
            "tests/test_step070_product_owned_skill_foundation.py",
            "tests/test_step067_hosted_web_search_foundation_baseline.py",
            "tests/test_step066_remote_mcp_streamable_http_mvp_foundation_baseline.py",
            "tests/test_step044_native_guardrail_runtime_baseline.py",
            "tests/test_step042_agent_as_tool_runtime_baseline.py",
            "tests/test_step041_native_handoff_runtime_baseline.py",
            "tests/test_step062_bounded_multi_agent_orchestration_baseline.py",
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
            "scripts/run_step080a_acceptance.py",
            "scripts/run_step080a_live_acceptance.py",
            "scripts/validate_architecture_constitution.py",
            "scripts/windows_entrypoint.py",
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
        ROOT / "docs/plans/STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES.md",
        ROOT / "docs/reference/STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP079A_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/evidence/STEP080A_CONSTITUTION_COMPLIANCE.json",
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-015-CONSTITUTION-OUTSIDE-PRODUCT-AND-NOT-ENFORCED.md",
        ROOT / "docs/issues/OR-ISSUE-016-SERVICE-CAPABILITIES-CONSTITUTION-SNAPSHOT-NOT-INITIALIZED.md",
        ROOT / "specs/architecture/constitution/OKCANVAS_AGENT_RUNTIME_ARCHITECTURE_CONSTITUTION.md",
        ROOT / "specs/architecture/constitution/OKCANVAS_AGENT_RUNTIME_ARCHITECTURE_CONSTITUTION.json",
        ROOT / "specs/acceptance/launcher-registry.json",
    )

    binding_items = sample_binding.capability_topology.get("bindings", [])
    example_ids = {record.example_id for record in examples.records}
    checks = {
        "baseline_version_and_step_exact": info.version == VERSION
        and info.step == STEP
        and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
        and f'CURRENT_STEP = "{STEP}"' in baseline_source,
        "step079a_windows_live_closed_exact": predecessor.get("state") == "PASSED"
        and predecessor.get("passed_checks") == predecessor.get("total_checks") == 57
        and predecessor.get("model") == "gpt-4.1"
        and predecessor.get("model_calls") == 2
        and predecessor.get("tool_calls") == 1
        and predecessor.get("terminal_status") == "SUCCEEDED",
        "step079_and_step079a_runtime_flags_closed": info.product_owned_atomic_task_run_ownership_transfer_windows_live_accepted is True
        and info.windows_step079_live_command_registration_windows_live_accepted is True,
        "capability_foundation_runtime_flags_exact": info.product_owned_capability_topology_foundation_implemented is True
        and info.product_owned_capability_topology_schema == "okcanvas-agent-capability-topology-v1"
        and info.product_owned_capability_foundation_schema == "okcanvas-capability-foundation-v1"
        and info.product_owned_capability_family_count == 8
        and info.product_owned_capability_agent_topology_count == 27
        and info.product_owned_capability_binding_count == 33
        and info.product_owned_capability_topology_deterministic_accepted is True
        and info.product_owned_capability_topology_windows_live_accepted is False
        and info.next_selected_step == "UNSELECTED_PENDING_STEP080A_WINDOWS_LIVE_ACCEPTANCE",
        "all_agent_topologies_resolve": len(definitions) == len(topologies) == 27
        and len({topology.agent_id for topology in topologies}) == 27
        and all(len(topology.topology_sha256) == 64 for topology in topologies),
        "foundation_counts_exact": foundation.agent_topology_count == 27
        and foundation.binding_count == 33
        and dict(foundation.family_counts)
        == {
            "guardrail": 6,
            "input": 2,
            "mcp": 2,
            "session": 7,
            "skill": 1,
            "sub-agent": 6,
            "tool": 8,
            "workspace": 1,
        },
        "foundation_root_sha_bound": len(foundation.topology_root_sha256) == 64,
        "tool_search_structure_only": discovery_policy["tool_search"]["runtime_enabled"] is False
        and foundation.discovery_policy.tool_search_runtime_enabled is False
        and info.product_owned_capability_tool_search_structure_ready is True
        and info.product_owned_capability_tool_search_runtime_enabled is False
        and all(item.get("loading") != "DEFERRED" for item in binding_items),
        "programmatic_structure_only": discovery_policy["programmatic_tool_calling"]["runtime_enabled"] is False
        and foundation.discovery_policy.programmatic_tool_calling_runtime_enabled is False
        and info.product_owned_capability_programmatic_tool_calling_structure_ready is True
        and info.product_owned_capability_programmatic_tool_calling_runtime_enabled is False
        and all(item.get("programmatic_call_allowed") is False for item in binding_items),
        "function_tools_have_future_discovery_metadata": any(
            item.get("kind") == "function-tool" and item.get("tool_search_eligible") is True
            for topology in topologies
            for item in topology.to_public_dict()["bindings"]
        ),
        "current_mcp_not_falsely_tool_search_eligible": all(
            item.get("tool_search_eligible") is False
            for topology in topologies
            for item in topology.to_public_dict()["bindings"]
            if item.get("family") == "mcp"
        ),
        "product_skill_remains_instruction_only": any(
            item.get("family") == "skill"
            and item.get("kind") == "product-instruction-skill"
            and item.get("sdk_surface") == "Agent.instructions/Product-owned Skill"
            and item.get("loading") == "INSTRUCTION_COMPOSED"
            for topology in topologies
            for item in topology.to_public_dict()["bindings"]
        )
        and info.product_owned_skill_executable_code_enabled is False
        and info.product_owned_skill_shell_enabled is False,
        "sdk_example_inventory_exact": len(examples.records) == 30
        and len(inventory_payload["records"]) == 30
        and examples.inventory_sha256 == foundation.sdk_example_inventory.inventory_sha256
        and {"tool-search", "programmatic-tool-calling", "local-shell-skill"}.issubset(example_ids),
        "sdk_examples_are_hash_verified_not_imported": all(
            len(record.sha256) == 64 for record in examples.records
        )
        and not reference_import_violations,
        "agent_public_contract_contains_topology": sample_definition.to_public_dict().get("capability_topology")
        == sample_binding.capability_topology,
        "runtime_binding_fingerprints_topology_examples_and_constitution": sample_binding.to_fingerprint_dict().get("capability_topology")
        == sample_binding.capability_topology
        and len(sample_binding.capability_topology_runtime_sha256) == 64
        and sample_binding.sdk_example_inventory_sha256 == examples.inventory_sha256
        and sample_binding.architecture_constitution.get("constitution_sha256")
        == architecture_constitution.constitution_sha256
        and len(sample_binding.architecture_constitution_runtime_sha256) == 64,
        "service_policy_selects_step080a": service_policy.get("version") == "1.10.0"
        and service_policy.get("next_selected_step") == "UNSELECTED_PENDING_STEP080A_WINDOWS_LIVE_ACCEPTANCE"
        and service_policy.get("capability_topology_available") is True
        and service_policy.get("capability_tool_search_runtime_enabled") is False
        and service_policy.get("capability_programmatic_tool_calling_runtime_enabled") is False
        and service_policy.get("architecture_constitution_integrated") is True
        and service_policy.get("architecture_constitution_sha256")
        == architecture_constitution.constitution_sha256
        and service_policy.get("architecture_constitution_source_movement_allowed") is False,
        "service_capability_contract_fields_present": all(
            token in (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/contracts.py")).read_text(encoding="utf-8")
            for token in (
                "capability_topology_available",
                "capability_discovery_policy_sha256",
                "capability_sdk_example_inventory_sha256",
                "capability_topology_root_sha256",
                "architecture_constitution_id",
                "architecture_constitution_sha256",
                "architecture_constitution_clause_count",
                "architecture_constitution_required_gate_count",
                "architecture_constitution_source_movement_allowed",
            )
        ),
        "live_command_registered": parsed.command == LIVE_COMMAND
        and LIVE_COMMAND in command_action.choices
        and f'args.command == "{LIVE_COMMAND}"' in entrypoint_source
        and "run_step080a_live_acceptance.py" in entrypoint_source,
        "windows_launchers_exact": "architecture-constitution-live-acceptance" in launcher
        and "run_step080a_acceptance.py" in acceptance_launcher,
        "live_contract_exact_67": _live_check_count(live_source_path) == 67
        and 'payload["checks"]["api_key_not_in_summary"]' in live_source,
        "package_default_is_step080a": "step080a-ratified-architecture-constitution-integration-and-compliance-gates.zip"
        in package_source
        and f'PACKAGE_STEP = "{STEP}"' in package_source,
        "step080a_documents_and_issue_present": all(path.is_file() for path in required_docs)
        and all(issue_id in (ROOT / "docs/issues/ISSUE_REGISTRY.md").read_text(encoding="utf-8") for issue_id in ("OR-ISSUE-015", "OR-ISSUE-016")),
        "architecture_constitution_identity_exact": architecture_constitution.constitution_sha256
        == "262b1db8549d7de5baf09307336b3ad5da07b7397f70cc2d6f5a1374eeb08bfa"
        and architecture_constitution.clause_count == 127
        and architecture_constitution.required_gate_count == 32,
        "architecture_constitution_bundle_validation_pass": constitution_validation.get("state") == "PASSED"
        and constitution_validation.get("passed_checks") == constitution_validation.get("total_checks") == 16,
        "acceptance_launcher_registry_complete": launcher_registry_validation.get("state") == "PASSED"
        and launcher_registry_validation.get("passed_checks")
        == launcher_registry_validation.get("total_checks")
        == 6
        and launcher_registry_validation.get("script_count") == 125
        and launcher_registry_validation.get("launcher_count") == 120,
        "architecture_step_compliance_complete": compliance_summary.state
        == "DETERMINISTIC_COMPLETE_WINDOWS_PENDING"
        and compliance_summary.pending_external_gate_count == 1
        and compliance_summary.step == STEP
        and compliance_summary.version == VERSION,
        "architecture_source_movement_remains_blocked": info.architecture_constitution_source_movement_allowed is False
        and architecture_constitution.product_source_movement_allowed is False
        and (ROOT / "okcanvas_agent_runtime").is_dir()
        and not (ROOT / "okcanvas_agent_runtime").exists(),
        "architecture_runtime_flags_exact": info.architecture_constitution_integrated is True
        and info.architecture_constitution_sha256 == architecture_constitution.constitution_sha256
        and info.architecture_constitution_clause_count == 127
        and info.architecture_constitution_required_gate_count == 32
        and info.architecture_step_compliance_gate_implemented is True
        and info.architecture_constitution_deterministic_accepted is True
        and info.architecture_constitution_windows_live_accepted is False,
        "focused_step080a_tests_pass": focused_ok,
        "historical_capability_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "references_unchanged": references_ok,
        "no_direct_reference_imports": not reference_import_violations,
        "model_source_contains_no_runtime_activation": "product_owned_capability_tool_search_runtime_enabled: bool = False"
        in model_source
        and "product_owned_capability_programmatic_tool_calling_runtime_enabled: bool = False"
        in model_source,
    }

    payload = {
        "schema_version": "okcanvas-step080a-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "checks": checks,
        "agent_topology_count": foundation.agent_topology_count,
        "capability_binding_count": foundation.binding_count,
        "capability_family_counts": dict(foundation.family_counts),
        "capability_kind_counts": dict(foundation.kind_counts),
        "capability_topology_root_sha256": foundation.topology_root_sha256,
        "capability_discovery_policy_sha256": foundation.discovery_policy.policy_sha256,
        "sdk_example_inventory_count": len(examples.records),
        "sdk_example_inventory_sha256": examples.inventory_sha256,
        "sample_runtime_binding_sha256": sample_binding.runtime_binding_sha256,
        "sample_capability_topology_sha256": sample_binding.capability_topology.get(
            "topology_sha256"
        ),
        "architecture_constitution": architecture_constitution.to_public_dict(),
        "architecture_constitution_runtime_sha256": sample_binding.architecture_constitution_runtime_sha256,
        "constitution_validation_checks": constitution_validation.get("total_checks"),
        "launcher_registry_validation": launcher_registry_validation,
        "step_compliance": compliance_summary.to_public_dict(),
        "service_policy_sha256": _sha256(ROOT / "specs/service_clients/service-client-policy.json"),
        "focused_test_output": focused_output,
        "historical_test_output": historical_output,
        "python_compile_output": compile_output,
        "node_release_output": release_output,
        "node_test_output_tail": node_output[-4000:],
        "reference_count": len(reference_results),
        "reference_import_output_tail": no_reference_imports_output[-4000:],
        "docker_calls": 0,
        "external_network_calls": 0,
        "model_calls": 0,
        "live_launcher": "sh_run_step080a_live_acceptance.cmd",
        "live_model_required": "gpt-4.1",
        "live_total_checks": 67,
        "live_state": "WINDOWS_LIVE_RERUN_PENDING",
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args(argv)
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
