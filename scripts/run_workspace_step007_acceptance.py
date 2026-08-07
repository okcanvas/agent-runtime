from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from workspace_inventory import snapshot_files
from workspace_process import resolve_executable, resolve_project_python, run_process, workspace_root_errors, write_json_stdout

STEP = "WORKSPACE_STEP007_RUNTIME_ORGANIZATION_CONTEXT_SESSION_DELEGATION_AND_LIVE_OPENAI_E2E_READINESS"
VERSION = "0.7.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP007_ACCEPTANCE.json"


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_last_json(process: dict[str, Any]) -> dict[str, Any] | None:
    text = str(process.get("stdout", "")).strip()
    for index in reversed([i for i, char in enumerate(text) if char == "{"]):
        try:
            return json.loads(text[index:])
        except json.JSONDecodeError:
            continue
    return None


def copy_project(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build", "*.egg-info"))


def manifest_drift() -> dict[str, list[str]]:
    manifest = json.loads((ROOT / "WORKSPACE_MANIFEST.json").read_text(encoding="utf-8"))
    expected = {str(item["path"]): (str(item["sha256"]), int(item["size"])) for item in manifest["files"]}
    actual = snapshot_files(ROOT, workspace=True)
    return {
        "missing": sorted(set(expected) - set(actual)),
        "changed": sorted(path for path in set(expected) & set(actual) if expected[path] != actual[path]),
        "unexpected": sorted(set(actual) - set(expected)),
    }


def failure(started: str, errors: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "okcanvas-agent-platform-workspace-step007-acceptance-v1",
        "step": STEP, "version": VERSION, "state": "FAILED", "started_at": started, "completed_at": now(),
        "execution_platform": "windows" if os.name == "nt" else os.name,
        "checks": {"workspace_root_contract_exact": False}, "passed_checks": 0, "total_checks": 1, "errors": errors,
        "limitations": {"runtime_organization_context_wired": True, "windows_step007_live_executed": False, "real_enterprise_organization_context_called": False, "openai_model_called": False, "production_database_executed": False},
    }


def run(output: Path) -> int:
    started = now()
    errors = workspace_root_errors(ROOT)
    if errors:
        payload = failure(started, errors)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_json_stdout(payload)
        return 2

    connector_root = ROOT / "okcanvas-connectors/organization-context-mcp-server"
    example_root = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"
    runtime_root = ROOT / "okcanvas-agent-runtime"
    try:
        node = resolve_executable("node")
        npm = resolve_executable("npm")
        connector_python = resolve_project_python(connector_root, required_modules=("pytest", "fastapi", "httpx", "pydantic"), fallback_executable=sys.executable, allow_fallback=os.name != "nt")
    except FileNotFoundError as exc:
        payload = failure(started, [str(exc)])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_json_stdout(payload)
        return 2

    drift = manifest_drift()
    before = {"connector": snapshot_files(connector_root), "example": snapshot_files(example_root), "runtime": snapshot_files(runtime_root)}
    unit = run_process(sys.executable, ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], cwd=ROOT)

    with tempfile.TemporaryDirectory(prefix="s007-") as temp_name:
        temp = Path(temp_name)
        connector = temp / "c"
        example = temp / "e"
        copy_project(connector_root, connector)
        copy_project(example_root, example)
        connector_env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        connector_acceptance = run_process(connector_python, ["scripts/run_acceptance.py"], cwd=connector, env=connector_env)
        example_acceptance = run_process(npm, ["run", "acceptance"], cwd=example)
        integration = run_process(connector_python, [str(ROOT / "tests/run_organization_context_connector_example_e2e.py"), "--connector-root", str(connector), "--example-root", str(example)], cwd=ROOT, env=connector_env)
        live_output = temp / "live-preflight.json"
        live_env = dict(os.environ)
        for key in ("OPENAI_API_KEY", "OKCANVAS_AGENT_MODEL", "OKCANVAS_WORKSPACE_STEP007_LIVE_ACCEPTANCE", "OKCANVAS_LOCAL_ENV_SOURCE_NAME", "OKCANVAS_LOCAL_ENV_LOADED_KEYS"):
            live_env.pop(key, None)
        live_preflight = run_process(sys.executable, [str(ROOT / "scripts/run_workspace_step007_live_acceptance.py"), "--example-root", str(example), "--output", str(live_output)], cwd=ROOT, env=live_env)

    after = {"connector": snapshot_files(connector_root), "example": snapshot_files(example_root), "runtime": snapshot_files(runtime_root)}
    parsed = {
        "connector": parse_last_json(connector_acceptance),
        "example": parse_last_json(example_acceptance),
        "connector_example": parse_last_json(integration),
        "live_preflight": parse_last_json(live_preflight),
    }
    catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
    contracts = {item["id"]: item for item in json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]}
    parent = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP006_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    live_parent = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP004R2_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    runtime = json.loads((runtime_root / "docs/evidence/STEP088_DETERMINISTIC_ACCEPTANCE.json").read_text(encoding="utf-8"))
    binding = json.loads((connector_root / "contracts/connector-binding-contract.json").read_text(encoding="utf-8"))
    fixture_manifest = json.loads((example_root / "fixtures/tenant-a/manifest.json").read_text(encoding="utf-8"))
    server = json.loads((runtime_root / "specs/mcp/servers/organization-context-read/server.json").read_text(encoding="utf-8"))
    root_agent = json.loads((runtime_root / "specs/agents/organization-context-session-agent/definition.json").read_text(encoding="utf-8"))
    child_agent = json.loads((runtime_root / "specs/agents/organization-context-read-agent/definition.json").read_text(encoding="utf-8"))
    routing_policy = json.loads((runtime_root / "specs/assistant/routing-policy.json").read_text(encoding="utf-8"))
    runtime_source = "\n".join(path.read_text(encoding="utf-8") for path in (runtime_root / "okcanvas_agent_runtime").rglob("*.py"))

    connector_payload = parsed["connector"] or {}
    example_payload = parsed["example"] or {}
    integration_payload = parsed["connector_example"] or {}
    integration_checks = integration_payload.get("checks", {}) if isinstance(integration_payload, dict) else {}
    live_payload = parsed["live_preflight"] or {}
    projects = {item["project_id"]: item for item in catalog.get("projects", [])}
    remote_contract = contracts["runtime-organization-context-connector"]
    checks = {
        "workspace_root_contract_exact": not errors,
        "workspace_identity_exact": catalog.get("workspace_step") == STEP and catalog.get("workspace_version") == VERSION,
        "step006_windows_parent_retained": parent.get("state") == "PASSED" and parent.get("passed_checks") == 27,
        "step004r2_windows_live_parent_retained": live_parent.get("state") == "PASSED" and live_parent.get("live", {}).get("passed_checks") == 22,
        "runtime_step088_identity_exact": projects.get("agent-runtime", {}).get("baseline") == "STEP088_RUNTIME_ORGANIZATION_CONTEXT_SESSION_DELEGATION_AND_LIVE_OPENAI_E2E_READINESS" and projects.get("agent-runtime", {}).get("version") == "2.68.0",
        "runtime_step088_acceptance_passed": runtime.get("state") == "PASSED" and runtime.get("passed_checks") == 22 and runtime.get("total_checks") == 22,
        "runtime_organization_context_contract_implemented": remote_contract.get("implemented") is True and remote_contract.get("production_source_of_truth") == "DATABASE" and remote_contract.get("write_enabled") is False,
        "dedicated_session_root_exact": root_agent.get("agent_id") == "organization-context-session-agent" and root_agent.get("session_mode") == "sqlite-v1" and root_agent.get("agent_tools") == ["organization-context-read-agent"],
        "stateless_child_mcp_ownership_exact": child_agent.get("session_mode") == "disabled" and child_agent.get("mcp_servers") == ["organization-context-read"] and child_agent.get("output_contract") == "OrganizationContextReadResult",
        "organization_context_remote_mcp_exact": server.get("server_id") == "organization-context-read" and server.get("credential_ref") == "organization-context-read-credential" and len(server.get("allowed_tools", [])) == 3,
        "organization_context_routing_policy_current": routing_policy.get("version") == "1.4.0" and "organization-context-read-v1" in json.dumps(routing_policy),
        "local_step084_catalog_retained": (runtime_root / "specs/organization/manifest.json").is_file() and "local_step084_catalog_replaced" not in runtime_source,
        "connector_acceptance_passed": connector_payload.get("state") == "PASSED" and connector_payload.get("passed_checks") == 10,
        "example_acceptance_passed": example_payload.get("state") == "PASSED" and example_payload.get("passed_checks") == 16,
        "connector_example_integration_passed": integration_payload.get("state") == "PASSED" and integration_payload.get("passed_checks") == 15,
        "unified_employee_resolution_proven": integration_checks.get("employee_context_resolved") is True,
        "same_name_ambiguity_proven": integration_checks.get("same_name_ambiguity_preserved") is True,
        "similar_client_ambiguity_proven": integration_checks.get("similar_client_ambiguity_preserved") is True,
        "entity_relationships_proven": integration_checks.get("entity_relationships_normalized") is True,
        "delegated_identity_and_secret_redaction_proven": integration_checks.get("delegated_identity_forwarded") is True and integration_checks.get("authorization_value_not_captured") is True,
        "live_preflight_fails_closed_without_environment": live_preflight.get("returncode") == 1 and live_payload.get("state") == "FAILED" and live_payload.get("safe_error", {}).get("category") == "LIVE_ENVIRONMENT_NOT_READY",
        "live_harness_uses_actual_boundaries": all(token in (ROOT / "scripts/run_workspace_step007_live_acceptance.py").read_text(encoding="utf-8") for token in ("organization_context_mcp_server", "create_runtime_app", "src/cli.mjs", "organization-context-session-agent", "/api/v1/context/resolve")),
        "live_provider_not_claimed_by_readiness": live_payload.get("limitations") is None or live_payload.get("limitations", {}).get("actual_openai_model_called") is not True,
        "production_database_sot_exact": fixture_manifest.get("production_sot") == "DATABASE" and binding.get("production_source_of_truth") == "DATABASE",
        "connector_is_read_only": binding.get("read_only") is True and binding.get("fake_mode_allowed") is False and all(not name.startswith(("create_", "update_", "delete_")) for name in binding.get("tool_names", [])),
        "connector_example_source_import_absent": "okcanvas-connector-examples" not in "\n".join(path.read_text(encoding="utf-8") for path in (connector_root / "organization_context_mcp_server").rglob("*.py")),
        "workspace_unit_tests_passed": unit.get("returncode") == 0,
        "node_and_project_python_resolved": bool(node) and bool(npm) and bool(connector_python),
        "subproject_acceptance_did_not_mutate_source": before == after,
        "workspace_manifest_exact": drift == {"missing": [], "changed": [], "unexpected": []},
    }
    state = "PASSED" if all(checks.values()) else "FAILED"
    payload = {
        "schema_version": "okcanvas-agent-platform-workspace-step007-acceptance-v1",
        "step": STEP, "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_RUNTIME_ORGANIZATION_CONTEXT_WIRING_AND_LIVE_READINESS",
        "state": state, "started_at": started, "completed_at": now(),
        "execution_platform": "windows" if os.name == "nt" else os.name,
        "checks": checks, "passed_checks": sum(value is True for value in checks.values()), "total_checks": len(checks),
        "parsed": parsed,
        "processes": {"workspace_unit_tests": unit, "connector_acceptance": connector_acceptance, "example_acceptance": example_acceptance, "connector_example_integration": integration, "live_preflight": live_preflight},
        "workspace_manifest_drift": drift,
        "resolved_interpreters": {"node": node, "npm": npm, "organization_context_connector": connector_python, "workspace_bootstrap": sys.executable},
        "limitations": {"runtime_organization_context_wired": True, "local_step084_catalog_replaced": False, "windows_step007_live_executed": False, "real_enterprise_organization_context_called": False, "production_database_executed": False, "openai_model_called": False},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_json_stdout(payload)
    return 0 if state == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
