from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = [
    "resolve_organization_context",
    "search_organization_context",
    "get_organization_entity",
    "resolve_organization_terms",
    "search_organization_terms",
    "get_organization_term",
    "get_organization_catalog_state",
    "get_organization_changes",
]


def main() -> int:
    commands = {
        "compileall": [sys.executable, "-m", "compileall", "-q", "organization_context_mcp_server", "tests", "scripts"],
        "pytest": [sys.executable, "-m", "pytest", "-q"],
    }
    results: dict[str, object] = {}
    for name, command in commands.items():
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        results[name] = {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    binding = json.loads((ROOT / "contracts/connector-binding-contract.json").read_text(encoding="utf-8"))
    runtime = json.loads((ROOT / "contracts/runtime-provider-contract.json").read_text(encoding="utf-8"))
    api = json.loads((ROOT / "contracts/organization-context-http-api-v1.json").read_text(encoding="utf-8"))
    source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "organization_context_mcp_server").rglob("*.py"))
    tests = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_*.py"))
    checks = {
        "identity_exact": binding.get("required_role") == "agent-user" and binding.get("credential_reference_transmitted") is False,
        "read_tools_exact": binding.get("tool_names") == EXPECTED_TOOLS,
        "unified_entity_contract_exact": binding.get("supported_entity_types") == ["TERM", "DEPARTMENT", "POSITION", "EMPLOYEE", "PRODUCT", "CLIENT", "PROJECT", "SYSTEM", "CAPABILITY"] and "POST /context/resolve" in api.get("read_endpoints", []),
        "production_db_sot_explicit": binding.get("production_source_of_truth") == "DATABASE" and api.get("production_source_of_truth") == "DATABASE" and runtime.get("production_source_of_truth") == "DATABASE",
        "runtime_boundary_wired": runtime.get("pre_routing_integration") == "IMPLEMENTED_RUNTIME_POLICY_CALL" and runtime.get("agent_grounding_integration") == "IMPLEMENTED_STATELESS_CHILD_MCP",
        "bounded_context_response_contract": '"maximum": 20' in (ROOT / "organization_context_mcp_server/mcp_protocol.py").read_text(encoding="utf-8") and "response_shape" in source and "candidate_count" in source and "truncated" in source,
        "compileall_passed": results["compileall"]["returncode"] == 0,
        "pytest_passed": results["pytest"]["returncode"] == 0,
        "fake_mode_absent": "FAKE_MODE" not in source and "organization-context-api-fake" not in source,
        "async_test_runner_dependency_closed": "pytest.mark.asyncio" not in tests and "pytest_asyncio" not in tests,
        "admin_mutation_tools_absent": all(not name.startswith(("create_", "update_", "delete_")) for name in binding.get("tool_names", [])),
    }
    payload = {
        "schema_version": "okcanvas-organization-context-connector-step002-acceptance-v1",
        "step": "CONNECTOR_ORGANIZATION_CONTEXT_STEP002R2_BOUNDED_CONTEXT_RESPONSE_ALIGNMENT",
        "version": "0.2.2",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "processes": results,
    }
    output = ROOT / "docs/evidence/CONNECTOR_ORGANIZATION_CONTEXT_STEP002R2_ACCEPTANCE.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
