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

STEP = "WORKSPACE_STEP006_ORGANIZATION_CONTEXT_JSON_REFERENCE_DATASET_AND_UNIFIED_RESOLUTION_FOUNDATION"
VERSION = "0.6.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP006_ACCEPTANCE.json"


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
        "schema_version": "okcanvas-agent-platform-workspace-step006-acceptance-v1",
        "step": STEP, "version": VERSION, "state": "FAILED", "started_at": started, "completed_at": now(),
        "execution_platform": "windows" if os.name == "nt" else os.name,
        "checks": {"workspace_root_contract_exact": False}, "passed_checks": 0, "total_checks": 1, "errors": errors,
        "limitations": {"runtime_organization_context_wired": False, "real_enterprise_organization_context_called": False, "openai_model_called": False, "production_database_executed": False},
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
    before = {"connector": snapshot_files(connector_root), "example": snapshot_files(example_root), "runtime": snapshot_files(ROOT / "okcanvas-agent-runtime")}
    unit = run_process(sys.executable, ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], cwd=ROOT)

    with tempfile.TemporaryDirectory(prefix="s006-") as temp_name:
        temp = Path(temp_name)
        connector = temp / "c"
        example = temp / "e"
        copy_project(connector_root, connector)
        copy_project(example_root, example)
        connector_env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        connector_acceptance = run_process(connector_python, ["scripts/run_acceptance.py"], cwd=connector, env=connector_env)
        example_acceptance = run_process(npm, ["run", "acceptance"], cwd=example)
        integration = run_process(connector_python, [str(ROOT / "tests/run_organization_context_connector_example_e2e.py"), "--connector-root", str(connector), "--example-root", str(example)], cwd=ROOT, env=connector_env)

    after = {"connector": snapshot_files(connector_root), "example": snapshot_files(example_root), "runtime": snapshot_files(ROOT / "okcanvas-agent-runtime")}
    parsed = {"connector": parse_last_json(connector_acceptance), "example": parse_last_json(example_acceptance), "connector_example": parse_last_json(integration)}
    catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
    contracts = {item["id"]: item for item in json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]}
    parent = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP005R1_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    live_parent = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP004R2_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    binding = json.loads((connector_root / "contracts/connector-binding-contract.json").read_text(encoding="utf-8"))
    fixture_manifest = json.loads((example_root / "fixtures/tenant-a/manifest.json").read_text(encoding="utf-8"))
    example_source = "\n".join(path.read_text(encoding="utf-8") for path in (example_root / "src").rglob("*.ts"))
    connector_source = "\n".join(path.read_text(encoding="utf-8") for path in (connector_root / "organization_context_mcp_server").rglob("*.py"))

    connector_payload = parsed["connector"] or {}
    example_payload = parsed["example"] or {}
    integration_payload = parsed["connector_example"] or {}
    integration_checks = integration_payload.get("checks", {}) if isinstance(integration_payload, dict) else {}
    dataset_counts = example_payload.get("dataset_counts", {}) if isinstance(example_payload, dict) else {}
    expected_counts = {"departments": 13, "positions": 12, "employees": 48, "products": 120, "clients": 120, "glossary": 80, "projects": 24, "systems": 10, "capabilities": 30, "relations": 893}

    projects = {item["project_id"]: item for item in catalog.get("projects", [])}
    checks = {
        "workspace_root_contract_exact": not errors,
        "workspace_identity_exact": catalog.get("workspace_step") == STEP and catalog.get("workspace_version") == VERSION,
        "step005r1_windows_parent_retained": parent.get("state") == "PASSED" and parent.get("passed_checks") == 27,
        "step004r2_windows_live_parent_retained": live_parent.get("state") == "PASSED" and live_parent.get("live", {}).get("passed_checks") == 22,
        "organization_context_connector_cataloged": projects.get("organization-context-mcp-connector", {}).get("baseline") == "CONNECTOR_ORGANIZATION_CONTEXT_STEP002_UNIFIED_REFERENCE_ENTITY_READ_TOOLS" and projects.get("organization-context-mcp-connector", {}).get("version") == "0.2.0",
        "organization_context_example_cataloged": projects.get("organization-context-api-fake-example", {}).get("baseline") == "EXAMPLE_ORGANIZATION_CONTEXT_STEP002_JSON_REFERENCE_DATASET_AND_UNIFIED_RESOLUTION" and projects.get("organization-context-api-fake-example", {}).get("version") == "0.2.0",
        "runtime_wiring_explicitly_deferred": contracts["runtime-organization-context-connector"]["implemented"] is False and contracts["runtime-organization-context-connector"]["status"] == "DEFERRED_TO_RUNTIME_WIRING_STEP",
        "production_database_sot_exact": contracts["connector-organization-context-api"].get("production_source_of_truth") == "DATABASE" and fixture_manifest.get("production_sot") == "DATABASE" and binding.get("production_source_of_truth") == "DATABASE",
        "example_json_sot_exact": fixture_manifest.get("example_sot") == "COMMITTED_JSON_FIXTURES" and contracts["connector-example-organization-context-api"].get("example_source_of_truth") == "COMMITTED_JSON_FIXTURES",
        "reference_dataset_counts_exact": dataset_counts == expected_counts and fixture_manifest.get("expected_counts", {}).get("relations_minimum") == 200,
        "connector_acceptance_passed": connector_payload.get("state") == "PASSED" and connector_payload.get("passed_checks") == 10,
        "example_acceptance_passed": example_payload.get("state") == "PASSED" and example_payload.get("passed_checks") == 16,
        "connector_example_integration_passed": integration_payload.get("state") == "PASSED" and integration_payload.get("passed_checks") == 15,
        "unified_employee_resolution_proven": integration_checks.get("employee_context_resolved") is True,
        "same_name_ambiguity_proven": integration_checks.get("same_name_ambiguity_preserved") is True,
        "similar_client_ambiguity_proven": integration_checks.get("similar_client_ambiguity_preserved") is True,
        "entity_relationships_proven": integration_checks.get("entity_relationships_normalized") is True,
        "glossary_compatibility_retained": integration_checks.get("glossary_compatibility_retained") is True,
        "mutable_change_visible_through_read_only_connector": integration_checks.get("mutable_product_change_visible_through_read_only_connector") is True,
        "delegated_identity_and_secret_redaction_proven": integration_checks.get("delegated_identity_forwarded") is True and integration_checks.get("authorization_value_not_captured") is True,
        "connector_is_read_only": binding.get("read_only") is True and binding.get("fake_mode_allowed") is False and len(binding.get("tool_names", [])) == 8 and all(not name.startswith(("create_", "update_", "delete_")) for name in binding.get("tool_names", [])),
        "fixture_loader_replaces_hardcoded_seed": "loadReferenceDatasets" in example_source and "function seedTerms" not in example_source,
        "connector_example_source_import_absent": "okcanvas-connector-examples" not in connector_source and "organization-context-api-fake" not in connector_source,
        "workspace_unit_tests_passed": unit.get("returncode") == 0,
        "node_and_project_python_resolved": bool(node) and bool(npm) and bool(connector_python),
        "subproject_acceptance_did_not_mutate_source": before == after,
        "workspace_manifest_exact": drift == {"missing": [], "changed": [], "unexpected": []},
    }
    state = "PASSED" if all(checks.values()) else "FAILED"
    payload = {
        "schema_version": "okcanvas-agent-platform-workspace-step006-acceptance-v1",
        "step": STEP, "version": VERSION, "validation_mode": "LOCAL_DETERMINISTIC_JSON_REFERENCE_DATASET_AND_CONNECTOR_E2E",
        "state": state, "started_at": started, "completed_at": now(), "execution_platform": "windows" if os.name == "nt" else os.name,
        "checks": checks, "passed_checks": sum(value is True for value in checks.values()), "total_checks": len(checks),
        "parsed": parsed, "processes": {"workspace_unit_tests": unit, "connector_acceptance": connector_acceptance, "example_acceptance": example_acceptance, "connector_example_integration": integration},
        "dataset_counts": dataset_counts, "workspace_manifest_drift": drift,
        "resolved_interpreters": {"node": node, "npm": npm, "organization_context_connector": connector_python, "workspace_bootstrap": sys.executable},
        "limitations": {"runtime_organization_context_wired": False, "local_step084_catalog_replaced": False, "real_enterprise_organization_context_called": False, "production_database_executed": False, "openai_model_called": False},
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
