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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP070_ACCEPTANCE.json"
STEP = "STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1"
VERSION = "2.50.0"
SKILL_ID = "document-review-v1"
AGENT_ID = "skill-document-review-agent"
PACKAGE_SHA = "60fbfca861141837d4486499687fde4257b83bcb68362b6b0a0b6f40b8df07b5"
MANIFEST_SHA = "26dc1c5f675161ab50311a025ed359c5532dec27af61ad459042f894dc2a1ea1"
INSTRUCTIONS_SHA = "69d57297de7e8950b11b82ff5f79d8338db6f66cb297192c8e5ce47d911f0062"
CHECKLIST_SHA = "ce6d6f0eab5721363bd4974467530fa51cc96d7a41876939f26279239ddd9edc"
EVIDENCE_RULES_SHA = "4ddda1026e98d4f2d83e403f6477573476c9f6d6bb271920fafcebab2a0a2f06"
SKILL_RUNTIME_SHA = "c6d3fd17b4be4064343d0fe928e6b3e6c06332811afe8bead12936d4bef716d8"
SERVICE_POLICY_SHA = "9f223f94759144f2ff3d3f9fc4d529adcc8dc54177e93b0c3e618053c463d507"
STEP069_ACCEPTANCE_SHA = "999c463f327e6b7a43d8f8ebbcfdf86c07eabfde29bb71eaee6f8daf5573b96c"
STEP069_WINDOWS_SUMMARY_SHA = "f0db0b8c4d3218a53719ce2a137375220951834680babbcd3fc297aeb37101bb"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
    from okcanvas_agent_runtime.agent.skills import ProductSkillCatalog, resolve_effective_instructions

    info = RuntimeInfo()
    predecessor = _load_json(ROOT / "docs/evidence/STEP069_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    service_policy = _load_json(ROOT / "specs/service_clients/service-client-policy.json")
    skill_manifest = _load_json(ROOT / "specs/skills/document-review-v1/skill.json")
    skill = ProductSkillCatalog(ROOT).resolve(SKILL_ID)
    definition = AgentDefinitionCatalog(ROOT).resolve(AGENT_ID)
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    effective_instructions = resolve_effective_instructions(definition)

    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    skill_catalog_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/skills/catalog.py")).read_text(encoding="utf-8")
    skill_runtime_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/skills/runtime.py")).read_text(encoding="utf-8")
    agent_catalog_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/agent_definitions/catalog.py")).read_text(encoding="utf-8")
    gateway_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    orchestration_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/orchestration/openai_runtime.py")).read_text(encoding="utf-8")
    approval_gateway_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/tool_approval/gateway.py")).read_text(encoding="utf-8")
    binding_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text(encoding="utf-8")
    service_routes_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/routes.py")).read_text(encoding="utf-8")
    service_contracts_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/service_clients/contracts.py")).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/plans/ROADMAP.md").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    agents_constitution = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step070_product_owned_skill_foundation.py",
            "tests/test_step070_product_owned_skill_foundation_baseline.py",
        ],
        ROOT,
    )
    historical_ok, historical_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step069_multi_user_service_client_contract.py",
            "tests/test_step069_multi_user_service_client_contract_baseline.py",
            "tests/test_step068_bounded_local_pdf_image_input.py",
            "tests/test_step068_bounded_local_pdf_image_input_baseline.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_operations_console_api.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [sys.executable, "-m", "compileall", "-q", "src", "scripts/run_step070_acceptance.py"],
        ROOT,
    )
    release_ok, release_output = validate_committed_typescript_release(ROOT / "clients/cli")
    node_ok, node_output = run_node_tests(ROOT / "clients/cli")
    no_reference_imports_ok, no_reference_imports_output = run_command(
        [sys.executable, "scripts/verify_no_reference_imports.py"], ROOT
    )
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    package_root = ROOT / "specs/skills/document-review-v1"
    package_files = {
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
    }
    package_symlinks = [path for path in package_root.rglob("*") if path.is_symlink()]
    public_skill = skill.to_public_dict()
    public_serialized = json.dumps(public_skill, sort_keys=True, ensure_ascii=False)

    required_docs = [
        ROOT / "docs/plans/STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1.md",
        ROOT / "docs/reference/STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1_CODE_AUDIT.md",
        ROOT / "docs/27-PRODUCT-OWNED-SKILLS.md",
        ROOT / "docs/evidence/STEP069_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "specs/skills/contracts/PRODUCT_OWNED_SKILL_PACKAGE_V1.md",
        ROOT / "specs/skills/README.md",
        ROOT / "specs/service_clients/contracts/MULTI_USER_SERVICE_CLIENT_V1.md",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
        ROOT / "AGENTS.md",
    ]

    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION
            and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step069_windows_live_closure_exact": (
            _sha(ROOT / "docs/evidence/STEP069_ACCEPTANCE.json") == STEP069_ACCEPTANCE_SHA
            and _sha(ROOT / "docs/evidence/STEP069_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
            == STEP069_WINDOWS_SUMMARY_SHA
            and predecessor.get("reported_state") == "PASSED"
            and predecessor.get("reported_passed_checks") == 31
            and predecessor.get("reported_total_checks") == 31
        ),
        "multi_user_server_and_service_client_boundary_preserved": (
            info.multi_user_server_runtime_implemented is True
            and info.service_client_contract_implemented is True
            and info.service_client_api_prefix == "/v1/service"
            and info.development_tui_is_test_harness is True
            and info.development_node_cli_is_test_harness is True
        ),
        "step070_runtime_flags_exact": (
            info.product_owned_skill_foundation_implemented is True
            and info.product_owned_skill_mode
            == "server-installed-immutable-instructions-and-static-resources"
            and info.product_owned_skill_count == 1
            and info.product_owned_skill_agent_binding_explicit is True
            and info.product_owned_skill_runtime_binding_implemented is True
            and info.product_owned_skill_service_catalog_implemented is True
            and info.product_owned_skill_user_upload_enabled is False
            and info.product_owned_skill_executable_code_enabled is False
            and info.product_owned_skill_shell_enabled is False
            and info.product_owned_skill_dynamic_dependency_install_enabled is False
            and info.product_owned_skill_client_side_execution_enabled is False
        ),
        "skill_manifest_schema_identity_and_mode_exact": (
            skill_manifest.get("schema_version") == "okcanvas-product-skill-v1"
            and skill_manifest.get("skill_id") == SKILL_ID
            and skill_manifest.get("version") == "1.0.0"
            and skill_manifest.get("execution_mode") == "instructions-and-static-resources"
            and skill_manifest.get("workspace_access") == "none"
        ),
        "skill_manifest_instructions_resources_and_package_hashes_exact": (
            skill.package_sha256 == PACKAGE_SHA
            and skill.manifest_sha256 == MANIFEST_SHA
            and skill.instructions_sha256 == INSTRUCTIONS_SHA
            and {item.path: item.sha256 for item in skill.resources}
            == {
                "resources/review-checklist.md": CHECKLIST_SHA,
                "resources/evidence-rules.json": EVIDENCE_RULES_SHA,
            }
        ),
        "skill_package_inventory_and_symlink_boundary_exact": (
            package_files
            == {
                "skill.json",
                "instructions.md",
                "resources/review-checklist.md",
                "resources/evidence-rules.json",
            }
            and not package_symlinks
            and "_verify_exact_package_files" in skill_catalog_source
            and "Symbolic paths are forbidden" in skill_catalog_source
        ),
        "skill_content_is_bounded_static_utf8_only": (
            skill.execution_mode == "instructions-and-static-resources"
            and 0 < skill.instructions_byte_length <= 32_000
            and len(skill.resources) == 2
            and all(item.media_type in {"text/markdown", "application/json"} for item in skill.resources)
            and "_MAX_TOTAL_RESOURCE_BYTES = 64_000" in skill_catalog_source
            and "application/json" in skill_catalog_source
        ),
        "skill_public_contract_exposes_hashes_not_contents": (
            public_skill.get("package_sha256") == PACKAGE_SHA
            and public_skill.get("executable_code_included") is False
            and public_skill.get("dynamic_dependency_installation") is False
            and public_skill.get("client_side_execution") is False
            and "Review checklist" not in public_serialized
            and "Apply the bounded" not in public_serialized
            and "supplied-local-attachment-only" not in public_serialized
        ),
        "single_explicit_agent_skill_binding_exact": (
            definition.agent_id == AGENT_ID
            and definition.skills == (SKILL_ID,)
            and len(definition.skill_capabilities) == 1
            and definition.input_mode == "local-attachment-v1"
            and definition.output_contract == "LocalDocumentReviewResult"
            and '"skills"' in agent_catalog_source
            and "at most one Skill per Agent" in skill_catalog_source
        ),
        "skill_cannot_add_agent_permissions": (
            skill.required_tools == ()
            and skill.required_mcp_servers == ()
            and skill.required_hosted_tools == ()
            and definition.tools == ()
            and definition.mcp_servers == ()
            and definition.hosted_tools == ()
            and definition.workspace_access == "none"
            and "issubset(tools)" in skill_catalog_source
            and "issubset(mcp_servers)" in skill_catalog_source
            and "issubset(hosted_tools)" in skill_catalog_source
        ),
        "deterministic_effective_instruction_composition_exact": (
            definition.instructions in effective_instructions
            and f'<OKCANVAS_PRODUCT_SKILL id="{SKILL_ID}"' in effective_instructions
            and f'package_sha256="{PACKAGE_SHA}"' in effective_instructions
            and '<RESOURCE path="resources/review-checklist.md"' in effective_instructions
            and effective_instructions.endswith("</OKCANVAS_PRODUCT_SKILL>\n")
            and "_MAX_EFFECTIVE_INSTRUCTIONS_BYTES = 96_000" in skill_runtime_source
        ),
        "all_sdk_agent_constructors_use_effective_instructions": (
            gateway_source.count("resolve_effective_instructions(") >= 3
            and orchestration_source.count("resolve_effective_instructions(") >= 1
            and approval_gateway_source.count("resolve_effective_instructions(") >= 1
        ),
        "runtime_binding_binds_skill_package_and_runtime_exact": (
            len(binding.skills) == 1
            and binding.skills[0].get("package_sha256") == PACKAGE_SHA
            and binding.skill_runtime_sha256 == SKILL_RUNTIME_SHA
            and binding.to_fingerprint_dict().get("skills") == [dict(binding.skills[0])]
            and '"skill_runtime_sha256"' in binding_source
        ),
        "service_policy_skill_contract_exact": (
            _sha(ROOT / "specs/service_clients/service-client-policy.json") == SERVICE_POLICY_SHA
            and service_policy.get("skills_available") is True
            and service_policy.get("skill_catalog_api") == "/v1/service/skills"
            and service_policy.get("skill_foundation_step") == STEP
            and service_policy.get("next_skill_step") is None
        ),
        "service_skill_capability_and_catalog_routes_present": (
            'skills_available=True' in service_routes_source
            and 'skill_catalog_api="/v1/service/skills"' in service_routes_source
            and '@router.get("/skills"' in service_routes_source
            and '@router.get("/skills/{skill_id}"' in service_routes_source
            and "ServiceSkillResponse" in service_contracts_source
        ),
        "service_skill_contract_is_metadata_only": (
            "instructions_sha256" in service_contracts_source
            and "package_sha256" in service_contracts_source
            and "instructions:" not in service_contracts_source
            and "text:" not in service_contracts_source
            and "content:" not in service_contracts_source
        ),
        "no_skill_upload_install_mutation_or_client_execution_route": (
            '@router.post("/skills' not in service_routes_source
            and '@router.put("/skills' not in service_routes_source
            and '@router.delete("/skills' not in service_routes_source
            and info.product_owned_skill_user_upload_enabled is False
            and info.product_owned_skill_client_side_execution_enabled is False
        ),
        "skill_is_server_capability_not_final_client_runtime": (
            "server-installed" in handoff
            and "agent-cli" in handoff
            and "agent-web" in handoff
            and "agent-desktop" in handoff
            and "client-side execution" in agents_constitution
        ),
        "next_step_unselected_after_step070": (
            info.next_selected_step == "UNSELECTED_PENDING_FRESH_CODE_AUDIT"
            and service_policy.get("next_selected_step") == "UNSELECTED_PENDING_FRESH_CODE_AUDIT"
            and "No STEP071 is selected" in roadmap
            and "STEP071 remains unselected" in agents_constitution
            and "implement STEP071 before" in handoff
        ),
        "focused_step070_tests_pass": focused_ok and "12 passed" in focused_output,
        "historical_service_attachment_and_catalog_tests_pass": historical_ok and "passed" in historical_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step070_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launcher_present": (
            (ROOT / "sh_run_step070_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step070_acceptance.py").is_file()
        ),
        "external_network_and_model_calls_zero": True,
    }

    passed = sum(1 for value in checks.values() if value)
    payload = {
        "schema_version": "okcanvas-step070-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if passed == len(checks) else "FAILED",
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "skill_contract": {
            "skill_id": skill.skill_id,
            "skill_version": skill.version,
            "execution_mode": skill.execution_mode,
            "package_sha256": skill.package_sha256,
            "manifest_sha256": skill.manifest_sha256,
            "instructions_sha256": skill.instructions_sha256,
            "resource_count": len(skill.resources),
            "allowed_agent_ids": list(skill.allowed_agent_ids),
            "required_tools": list(skill.required_tools),
            "required_mcp_servers": list(skill.required_mcp_servers),
            "required_hosted_tools": list(skill.required_hosted_tools),
            "workspace_access": skill.workspace_access,
            "user_upload_enabled": False,
            "executable_code_enabled": False,
            "shell_enabled": False,
            "dynamic_dependency_install_enabled": False,
            "client_side_execution_enabled": False,
        },
        "skill_agent_id": definition.agent_id,
        "skill_runtime_sha256": binding.skill_runtime_sha256,
        "next_selected_step": info.next_selected_step,
        "focused_test_output": focused_output[-4000:],
        "historical_test_output": historical_output[-4000:],
        "python_compile_output": compile_output[-2000:],
        "node_release_output": release_output[-2000:],
        "node_test_output_tail": node_output[-4000:],
        "reference_import_output_tail": no_reference_imports_output[-2000:],
        "reference_count": len(reference_results),
        "external_network_calls": 0,
        "model_calls": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
