from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from scripts.node_acceptance import run_command, run_node_tests, validate_committed_typescript_release

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP066_ACCEPTANCE.json"
STEP = "STEP066_REMOTE_MCP_STREAMABLE_HTTP_MVP_FOUNDATION"
VERSION = "2.46.0"
SDK_SERVER_SHA = "920c52936da4e02377680e55a5c7d90164e9b31f4ba800c41411524e5c34b118"
SDK_MANAGER_SHA = "1516644f5b85c7c325a0c09b0799b27aeb6ba9357407582d0fab89a8e0ec127d"
SDK_UTIL_SHA = "10d2ee686c76a5d99fea9f1bc8348865e80d9e09608d67fef3f248d9712a9077"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    predecessor = _load_json(ROOT / "docs/evidence/STEP064A_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    decision = _load_json(ROOT / "docs/evidence/STEP065_MVP_REPRIORITIZATION_DECISION.json")
    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    catalog_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/mcp_definitions/catalog.py")
    ).read_text(encoding="utf-8")
    model_definition_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/mcp_definitions/models.py")
    ).read_text(encoding="utf-8")
    factory_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/mcp_clients/openai_factory.py")
    ).read_text(encoding="utf-8")
    binding_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")
    ).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/plans/ROADMAP.md").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    template = _load_json(ROOT / "specs/mcp/examples/remote-streamable-http.server.json")
    allowlist = _load_json(ROOT / "specs/mcp/allowlist.json")

    sdk_server = (
        ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/server.py"
    )
    sdk_manager = (
        ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/manager.py"
    )
    sdk_util = ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/util.py"

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step066_remote_mcp_streamable_http_foundation.py",
            "tests/test_step066_remote_mcp_streamable_http_mvp_foundation_baseline.py",
        ],
        ROOT,
    )
    historical_ok, historical_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_mcp_definition_catalog.py",
            "tests/test_mcp_factory_contract.py",
            "tests/test_generic_mcp_gateway_contract.py",
            "tests/test_generic_mcp_execution_service.py",
            "tests/test_step009_mcp_baseline.py",
            "tests/test_step050_sqlite_session_native_mcp_composition_baseline.py",
            "tests/test_agent_runtime_binding.py",
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
            "scripts/run_step066_acceptance.py",
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

    local_definition = MCPServerCatalog(ROOT).resolve("reference-catalog")
    required_docs = [
        ROOT / "docs/plans/STEP066_REMOTE_MCP_STREAMABLE_HTTP_MVP_FOUNDATION.md",
        ROOT
        / "docs/reference/STEP066_REMOTE_MCP_STREAMABLE_HTTP_MVP_FOUNDATION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP065_MVP_REPRIORITIZATION_DECISION.json",
        ROOT / "specs/mcp/contracts/REMOTE_STREAMABLE_HTTP_V1.md",
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
        "step064a_windows_live_baseline_preserved": (
            predecessor.get("reported_state") == "PASSED"
            and predecessor.get("reported_passed_checks") == 19
            and predecessor.get("reported_total_checks") == 19
            and predecessor.get("corrected_step064_state") == "PASSED"
        ),
        "step065_reprioritized_without_false_windows_claim": (
            decision.get("decision") == "OPERATIONS_STABILITY_AFTER_MVP"
            and decision.get("accepted_windows_baseline", {}).get("step")
            == "STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX"
            and decision.get("implemented_but_not_windows_accepted", {}).get("step")
            == "STEP065_STRICT_SESSION_HISTORY_KEY_ROTATION_AND_RECOVERY_V1"
            and decision.get("implemented_but_not_windows_accepted", {}).get("classification")
            == "POST_MVP_OPERATIONAL_HARDENING_FROZEN"
            and info.sqlite_session_key_rotation_windows_live_accepted is False
        ),
        "mvp_core_roadmap_exact": (
            "Remote MCP Streamable HTTP foundation: current" in roadmap
            and "Hosted Web/File Search foundation" in roadmap
            and "Multimodal image/PDF/file input foundation" in roadmap
            and "Real bounded orchestration workflow" in roadmap
            and "Post-MVP operational hardening" in roadmap
        ),
        "step066_runtime_flags_exact": (
            info.remote_mcp_streamable_http_implemented is True
            and info.remote_mcp_streamable_http_mode
            == "single-exact-https-read-only-static-tool-allowlist"
            and info.remote_mcp_streamable_http_authorization_modes == "none,bearer-env"
            and info.remote_mcp_streamable_http_redirects_enabled is False
            and info.remote_mcp_streamable_http_proxy_environment_enabled is False
            and info.remote_mcp_streamable_http_retry_attempts == 0
            and info.remote_mcp_streamable_http_session_composition_enabled is False
            and info.remote_mcp_streamable_http_deterministic_accepted is True
            and info.remote_mcp_streamable_http_windows_live_accepted is False
            and info.post_mvp_operational_hardening_frozen is True
            and "remote_mcp_streamable_http_implemented" in model_source
        ),
        "local_stdio_mcp_predecessor_preserved": (
            local_definition.schema_version == "okcanvas-mcp-server-v1"
            and local_definition.kind == "builtin-stdio"
            and local_definition.module
            == "okcanvas_agent_runtime.adapters.mcp.servers.reference_catalog"
            and local_definition.allowed_tools == ("search_reference", "read_reference_file")
        ),
        "remote_definition_schema_and_kind_exact": (
            '"okcanvas-mcp-server-v2"' in catalog_source
            and '"remote-streamable-http"' in catalog_source
            and "is_remote_streamable_http" in model_definition_source
        ),
        "remote_exact_https_contract_present": (
            'parts.scheme != "https"' in catalog_source
            and "Remote MCP URL query and fragment are forbidden" in catalog_source
            and "Remote MCP URL authority is invalid" in catalog_source
            and "explicit endpoint path" in catalog_source
        ),
        "remote_single_server_no_transport_mixing": (
            "exactly one MCP server and no transport mixing" in catalog_source
            and "exactly one MCP server and no transport mixing" in factory_source
        ),
        "remote_readonly_static_tool_policy_exact": (
            "Only read-only MCP servers are supported" in catalog_source
            and "Remote Streamable HTTP V1 requires cache_tools_list=true" in catalog_source
            and "Remote Streamable HTTP V1 requires max_retry_attempts=0" in catalog_source
            and "create_static_tool_filter" in factory_source
            and '"require_approval": "never"' in factory_source
        ),
        "remote_bearer_secret_external_only": (
            "remote_mcp_headers" in factory_source
            and 'return {"Authorization": f"Bearer {token}"}' in factory_source
            and "authorization_env" in binding_source
            and "secret-token" not in handoff
            and "secret-token" not in roadmap
        ),
        "strict_http_client_no_redirect_or_proxy_env": (
            '"follow_redirects": False' in factory_source
            and '"trust_env": False' in factory_source
            and "strict_remote_http_client_factory" in factory_source
        ),
        "remote_result_bounded_before_return": (
            "class _BoundedRemoteMCPServer" in factory_source
            and "Remote MCP Tool result exceeds the configured limit" in factory_source
            and "result = await self._delegate.call_tool" in factory_source
        ),
        "official_sdk_streamable_http_sources_exact": (
            _sha256(sdk_server) == SDK_SERVER_SHA
            and _sha256(sdk_manager) == SDK_MANAGER_SHA
            and _sha256(sdk_util) == SDK_UTIL_SHA
            and "class MCPServerStreamableHttp" in sdk_server.read_text(encoding="utf-8")
            and "class MCPServerManager" in sdk_manager.read_text(encoding="utf-8")
            and "def create_static_tool_filter" in sdk_util.read_text(encoding="utf-8")
        ),
        "official_sdk_factory_path_present": (
            "from agents.mcp import MCPServerStreamableHttp" in factory_source
            and "MCPServerManager(" in factory_source
            and '"terminate_on_close": True' in factory_source
            and '"ignore_initialized_notification_failure": False' in factory_source
        ),
        "runtime_binding_remote_transport_exact": (
            'execution_path = "remote-mcp-streamable-http-execution-v1"' in binding_source
            and '"url": server.url' in binding_source
            and '"authorization_mode": server.authorization_mode' in binding_source
            and '"factory_sha256": mcp_factory_sha' in binding_source
            and '"redirects_enabled": "false"' in binding_source
        ),
        "remote_session_composition_disabled": (
            "STEP050 requires exactly one read-only builtin-stdio MCP server" in binding_source
            and info.remote_mcp_streamable_http_session_composition_enabled is False
        ),
        "remote_template_non_enabled_exact": (
            template.get("schema_version") == "okcanvas-mcp-server-v2"
            and template.get("kind") == "remote-streamable-http"
            and template.get("url") == "https://mcp.example.invalid/mcp"
            and template.get("server_id") not in allowlist.get("allowed_server_ids", [])
        ),
        "focused_remote_mcp_tests_pass": focused_ok and "19 passed" in focused_output,
        "historical_mcp_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok and "VERIFIED" in release_output,
        "node_tests_pass": node_ok and "# pass 14" in node_output,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step066_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launcher_present": (
            (ROOT / "scripts/run_step066_acceptance.py").is_file()
            and (ROOT / "sh_run_step066_acceptance.cmd").is_file()
        ),
        "step067_not_selected": "STEP067_" not in roadmap and "STEP067_" not in handoff,
    }

    payload = {
        "schema_version": "okcanvas-step066-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "mvp_priority": decision.get("mvp_core_priority", []),
        "remote_contract": {
            "transport": "streamable-http",
            "server_count": 1,
            "tls_required": True,
            "read_only": True,
            "static_tool_filter": True,
            "max_retry_attempts": 0,
            "redirects_enabled": False,
            "proxy_environment_enabled": False,
            "authorization_modes": ["none", "bearer-env"],
            "session_composition": False,
        },
        "focused_test_output": focused_output.splitlines()[-1] if focused_output else "",
        "historical_mcp_output": historical_output.splitlines()[-1]
        if historical_output
        else "",
        "python_compile_output": compile_output.splitlines()[-1] if compile_output else "",
        "node_release_output": release_output.splitlines()[-1] if release_output else "",
        "node_test_output_tail": node_output.splitlines()[-1] if node_output else "",
        "reference_import_output_tail": no_reference_imports_output.splitlines()[-1]
        if no_reference_imports_output
        else "",
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
