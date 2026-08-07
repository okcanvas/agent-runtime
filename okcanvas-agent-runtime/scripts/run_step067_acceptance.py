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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP067_ACCEPTANCE.json"
STEP = "STEP067_HOSTED_WEB_SEARCH_SOURCE_POLICY_AND_EVIDENCE_FOUNDATION"
VERSION = "2.47.0"
POLICY_SHA = "0d6badcb01779ec33e937509334e88bc794d606f05e878433e60ec8a41261e82"
SDK_TOOL_SHA = "1ba4d71d2e6b59638ce2bfee53529b36373ba6e8dadd1fdf68c6fea040bf6a3e"
SDK_RESPONSES_SHA = "37817cc1ba836f5cdfc59d4ab519f19f29432b0fb60d7c713cc5fba7a682a252"
SDK_TURN_SHA = "3bf639e8730785a591a0c70210f80cc1022be43b59b297df7c64a40387df36ae"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.agent.tools.hosted_search import HostedWebSearchPolicyCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    policy = HostedWebSearchPolicyCatalog(ROOT).resolve()
    definition = AgentDefinitionCatalog(ROOT).resolve("hosted-web-search-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    predecessor = _load_json(ROOT / "docs/evidence/STEP066_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    separation = _load_json(ROOT / "docs/evidence/STEP067_FILE_SEARCH_SCOPE_SEPARATION.json")
    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    agent_models = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/agent_definitions/models.py")).read_text(encoding="utf-8")
    agent_catalog = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/agent_definitions/catalog.py")).read_text(encoding="utf-8")
    hosted_runtime = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/hosted_search/runtime.py")).read_text(encoding="utf-8")
    gateway_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    service_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(encoding="utf-8")
    binding_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text(encoding="utf-8")
    contracts_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/contracts.py")).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/plans/ROADMAP.md").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    product_python = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "okcanvas_agent_runtime").rglob("*.py"))
    )

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step067_hosted_web_search_foundation.py",
            "tests/test_step067_hosted_web_search_foundation_baseline.py",
        ],
        ROOT,
    )
    historical_ok, historical_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step066_remote_mcp_streamable_http_foundation.py",
            "tests/test_step066_remote_mcp_streamable_http_mvp_foundation_baseline.py",
            "tests/test_agent_definition_catalog.py",
            "tests/test_agent_runtime_binding.py",
            "tests/test_generic_openai_gateway_contract.py",
            "tests/test_generic_agent_execution_service.py",
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
            "scripts/run_step067_acceptance.py",
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

    sdk_tool = ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/tool.py"
    sdk_responses = ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/models/openai_responses.py"
    sdk_turn = ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/run_internal/turn_resolution.py"
    required_docs = [
        ROOT / "docs/plans/STEP067_HOSTED_WEB_SEARCH_SOURCE_POLICY_AND_EVIDENCE_FOUNDATION.md",
        ROOT / "docs/reference/STEP067_HOSTED_WEB_SEARCH_SOURCE_POLICY_AND_EVIDENCE_FOUNDATION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP066_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/evidence/STEP067_FILE_SEARCH_SCOPE_SEPARATION.json",
        ROOT / "specs/hosted_tools/contracts/HOSTED_WEB_SEARCH_V1.md",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    ]

    checks = {
        "baseline_version_and_step_exact": (
            info.version == VERSION
            and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step066_windows_live_closure_exact": (
            predecessor.get("reported_state") == "PASSED"
            and predecessor.get("reported_passed_checks") == 28
            and predecessor.get("reported_total_checks") == 28
            and predecessor.get("external_network_calls") == 0
            and predecessor.get("model_calls") == 0
            and info.remote_mcp_streamable_http_windows_live_accepted is True
        ),
        "mvp_roadmap_and_file_search_separation_exact": (
            "STEP067 — Hosted Web Search source policy and evidence: current" in roadmap
            and "Hosted File Search resource-lifecycle decision" in roadmap
            and "STEP068 is not selected" in roadmap
            and separation.get("decision") == "SEPARATE_WEB_SEARCH_FROM_FILE_SEARCH"
            and separation.get("step067_includes") == ["WebSearchTool"]
            and separation.get("step067_excludes") == ["FileSearchTool", "vector-store-lifecycle"]
        ),
        "step067_runtime_flags_exact": (
            info.hosted_web_search_implemented is True
            and info.hosted_web_search_tool_id == "web-search-v1"
            and info.hosted_web_search_allowed_domains == "developers.openai.com"
            and info.hosted_web_search_max_calls == 1
            and info.hosted_web_search_max_sources == 8
            and info.hosted_web_search_max_citations == 8
            and info.hosted_web_search_user_location_enabled is False
            and info.hosted_web_search_store_enabled is False
            and info.hosted_web_search_parallel_tool_calls_enabled is False
            and info.hosted_web_search_raw_query_persisted is False
            and info.hosted_web_search_raw_content_persisted is False
            and info.hosted_web_search_provider_call_id_persisted is False
            and info.hosted_web_search_evidence_artifact_implemented is True
            and info.hosted_file_search_implemented is False
            and info.hosted_web_search_deterministic_accepted is True
            and info.hosted_web_search_windows_live_accepted is False
            and info.hosted_web_search_live_provider_accepted is False
            and "hosted_web_search_implemented" in model_source
        ),
        "policy_identity_sha_and_bounds_exact": (
            policy.policy_sha256 == POLICY_SHA
            and policy.policy_id == "official-openai-docs-web-search-v1"
            and policy.tool_id == "web-search-v1"
            and policy.allowed_domains == ("developers.openai.com",)
            and policy.search_context_size == "medium"
            and policy.external_web_access is True
            and policy.user_location_enabled is False
            and policy.max_search_calls == 1
            and policy.max_retrieved_sources == 8
            and policy.max_citations == 8
            and policy.max_title_chars == 200
            and policy.max_turns == 2
        ),
        "hosted_agent_isolated_and_strict": (
            definition.hosted_tools == ("web-search-v1",)
            and not definition.tools
            and not definition.mcp_servers
            and not definition.handoffs
            and not definition.agent_tools
            and not definition.orchestration_children
            and not definition.guardrails
            and definition.session_mode == "disabled"
            and definition.workspace_access == "none"
            and definition.output_contract == "HostedWebSearchResult"
            and definition.max_turns == 2
            and "hosted_tools" in agent_models
            and "Hosted Web Search Agent must be isolated" in agent_catalog
        ),
        "output_contract_reserves_urls_for_product_evidence": (
            "class HostedWebSearchResult" in contracts_source
            and "Hosted Web Search URLs belong only to Product source evidence" in contracts_source
            and "INSUFFICIENT_EVIDENCE" in contracts_source
        ),
        "official_sdk_hosted_sources_exact": (
            _sha256(sdk_tool) == SDK_TOOL_SHA
            and _sha256(sdk_responses) == SDK_RESPONSES_SHA
            and _sha256(sdk_turn) == SDK_TURN_SHA
            and binding.hosted_tools[0].get("sdk_tool_source_sha256") == SDK_TOOL_SHA
            and binding.hosted_tools[0].get("sdk_responses_source_sha256") == SDK_RESPONSES_SHA
            and binding.hosted_tools[0].get("sdk_turn_resolution_source_sha256") == SDK_TURN_SHA
        ),
        "sdk_web_search_tool_factory_exact": (
            "WebSearchTool(" in hosted_runtime
            and '"allowed_domains": list(policy.allowed_domains)' in hosted_runtime
            and "user_location=None" in hosted_runtime
            and "external_web_access=policy.external_web_access" in hosted_runtime
            and "build_sdk_web_search_tool" in gateway_source
        ),
        "input_only_source_include_store_false_exact": (
            policy.response_include == ("web_search_call.action.sources",)
            and policy.tool_choice == "required"
            and policy.parallel_tool_calls is False
            and '"store": False' in hosted_runtime
            and '"tool_choice": policy.tool_choice' in hosted_runtime
            and '"parallel_tool_calls": policy.parallel_tool_calls' in hosted_runtime
            and "previous_response_id" not in hosted_runtime
        ),
        "result_items_source_and_citation_validation_present": (
            "extract_hosted_web_search_evidence" in gateway_source
            and "web_search_call" in hosted_runtime
            and "file_search_call" in hosted_runtime
            and "url_citation" in hosted_runtime
            and "did not complete" in hosted_runtime
            and "no inline citation" in hosted_runtime
        ),
        "strict_url_policy_present": (
            "urlsplit" in hosted_runtime
            and "allowed_domains" in hosted_runtime
            and "port is not None" in hosted_runtime
            and "_BLOCKED_SUFFIXES" in hosted_runtime
            and "urlunsplit" in hosted_runtime
        ),
        "raw_search_material_not_product_evidence": (
            policy.raw_query_persisted is False
            and policy.raw_content_persisted is False
            and policy.provider_call_id_persisted is False
            and "raw_query_persisted" in service_source
            and "raw_content_persisted" in service_source
            and "provider_call_id_persisted" in service_source
            and "raw query" in handoff.lower()
        ),
        "separate_hosted_search_artifact_present": (
            '"agent.hosted-search-evidence"' in service_source
            and '"hosted-search-evidence.json"' in service_source
            and '"agent.final-output"' in service_source
            and "hosted_search_evidence_artifact_id" in service_source
        ),
        "runtime_binding_hosted_policy_and_sdk_bound": (
            binding.execution_path == "hosted-web-search-execution-v1"
            and len(binding.hosted_tools) == 1
            and binding.hosted_tools[0].get("policy_sha256") == POLICY_SHA
            and bool(binding.hosted_tool_runtime_sha256)
            and "hosted_tool_runtime_sha256" in binding_source
        ),
        "file_search_runtime_not_implemented": (
            "FileSearchTool" not in product_python
            and info.hosted_file_search_implemented is False
        ),
        "focused_hosted_search_tests_pass": focused_ok and "passed" in focused_output,
        "historical_remote_and_generic_tests_pass": historical_ok and "passed" in historical_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok,
        "node_tests_pass": node_ok,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step067_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launcher_present": (
            (ROOT / "sh_run_step067_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step067_acceptance.py").is_file()
        ),
        "step068_not_selected": (
            "STEP068 is not selected" in roadmap
            and "STEP068 remains" in handoff and "unselected" in handoff
        ),
    }
    passed = sum(1 for value in checks.values() if value)
    payload = {
        "schema_version": "okcanvas-step067-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if passed == len(checks) else "FAILED",
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "policy": {
            "policy_id": policy.policy_id,
            "policy_sha256": policy.policy_sha256,
            "tool_id": policy.tool_id,
            "allowed_domains": list(policy.allowed_domains),
            "max_search_calls": policy.max_search_calls,
            "max_retrieved_sources": policy.max_retrieved_sources,
            "max_citations": policy.max_citations,
            "response_include": list(policy.response_include),
            "store": False,
            "tool_choice": policy.tool_choice,
            "parallel_tool_calls": policy.parallel_tool_calls,
        },
        "focused_test_output": focused_output[-2000:],
        "historical_test_output": historical_output[-2000:],
        "python_compile_output": compile_output[-1000:],
        "node_release_output": release_output[-1000:],
        "node_test_output_tail": node_output[-1000:],
        "reference_import_output_tail": no_reference_imports_output[-1000:],
        "reference_count": len(reference_results),
        "external_network_calls": 0,
        "model_calls": 0,
        "file_search_implemented": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=False))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
