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
from workspace_process import (
    resolve_executable,
    resolve_project_python,
    run_process,
    workspace_root_errors,
    write_json_stdout,
)

STEP = "WORKSPACE_STEP005R1_GROUPWARE_ACCEPTANCE_PATTERN_ALIGNMENT"
VERSION = "0.5.1"
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP005R1_ACCEPTANCE.json"


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
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            ".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
            ".ruff_cache", "dist", "build", "*.egg-info"
        ),
    )


def manifest_drift() -> dict[str, list[str]]:
    manifest = json.loads((ROOT / "WORKSPACE_MANIFEST.json").read_text(encoding="utf-8"))
    expected = {
        str(item["path"]): (str(item["sha256"]), int(item["size"]))
        for item in manifest["files"]
    }
    actual = snapshot_files(ROOT, workspace=True)
    return {
        "missing": sorted(set(expected) - set(actual)),
        "changed": sorted(path for path in set(expected) & set(actual) if expected[path] != actual[path]),
        "unexpected": sorted(set(actual) - set(expected)),
    }


def failure(started: str, errors: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "okcanvas-agent-platform-workspace-step005r1-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_CONNECTOR_AND_EXAMPLE_FOUNDATION",
        "state": "FAILED",
        "started_at": started,
        "completed_at": now(),
        "execution_platform": "windows" if os.name == "nt" else os.name,
        "checks": {"workspace_root_contract_exact": False},
        "passed_checks": 0,
        "total_checks": 1,
        "errors": errors,
        "limitations": {
            "runtime_organization_context_wired": False,
            "real_enterprise_organization_context_called": False,
            "openai_model_called": False,
        },
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
        connector_python = resolve_project_python(
            connector_root,
            required_modules=("pytest", "fastapi", "httpx", "pydantic"),
            fallback_executable=sys.executable,
            allow_fallback=os.name != "nt",
        )
    except FileNotFoundError as exc:
        payload = failure(started, [str(exc)])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_json_stdout(payload)
        return 2

    drift = manifest_drift()
    before = {
        "connector": snapshot_files(connector_root),
        "example": snapshot_files(example_root),
        "runtime": snapshot_files(ROOT / "okcanvas-agent-runtime"),
    }
    unit = run_process(sys.executable, ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], cwd=ROOT)

    with tempfile.TemporaryDirectory(prefix="s5r1-") as temp_name:
        temp = Path(temp_name)
        # The Windows-live accepted Groupware E2E owns short execution copies rather than
        # reproducing long repository paths inside the temp tree. This keeps compileall
        # below legacy Windows path limits even when PYTHONPYCACHEPREFIX is active.
        connector = temp / "c"
        example = temp / "e"
        copy_project(connector_root, connector)
        copy_project(example_root, example)
        connector_env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        connector_acceptance = run_process(connector_python, ["scripts/run_acceptance.py"], cwd=connector, env=connector_env)
        example_acceptance = run_process(npm, ["run", "acceptance"], cwd=example)
        integration = run_process(
            connector_python,
            [
                str(ROOT / "tests/run_organization_context_connector_example_e2e.py"),
                "--connector-root", str(connector),
                "--example-root", str(example),
            ],
            cwd=ROOT,
            env=connector_env,
        )

    after = {
        "connector": snapshot_files(connector_root),
        "example": snapshot_files(example_root),
        "runtime": snapshot_files(ROOT / "okcanvas-agent-runtime"),
    }
    parsed = {
        "connector": parse_last_json(connector_acceptance),
        "example": parse_last_json(example_acceptance),
        "connector_example": parse_last_json(integration),
    }
    catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
    contracts = {
        item["id"]: item
        for item in json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]
    }
    windows_parent = json.loads(
        (ROOT / "docs/evidence/WORKSPACE_STEP004R2_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8")
    )
    connector_binding = json.loads((connector_root / "contracts/connector-binding-contract.json").read_text(encoding="utf-8"))
    example_source = (example_root / "src/server.ts").read_text(encoding="utf-8")
    connector_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (connector_root / "organization_context_mcp_server").rglob("*.py")
    )
    setup_source = (ROOT / "sh_setup_workspace.cmd").read_text(encoding="utf-8")

    connector_payload = parsed["connector"] or {}
    example_payload = parsed["example"] or {}
    integration_payload = parsed["connector_example"] or {}
    integration_checks = integration_payload.get("checks", {}) if isinstance(integration_payload, dict) else {}

    checks = {
        "workspace_root_contract_exact": not errors,
        "workspace_identity_exact": catalog.get("workspace_step") == STEP and catalog.get("workspace_version") == VERSION,
        "official_step004r2_windows_live_parent_retained": windows_parent.get("state") == "PASSED"
        and windows_parent.get("deterministic", {}).get("passed_checks") == 34
        and windows_parent.get("live", {}).get("passed_checks") == 22,
        "organization_context_connector_cataloged": any(
            item.get("project_id") == "organization-context-mcp-connector"
            and item.get("baseline") == "CONNECTOR_ORGANIZATION_CONTEXT_STEP001R1_GROUPWARE_ACCEPTANCE_PATTERN_ALIGNMENT"
            for item in catalog.get("projects", [])
        ),
        "organization_context_example_cataloged": any(
            item.get("project_id") == "organization-context-api-fake-example"
            and item.get("baseline") == "EXAMPLE_ORGANIZATION_CONTEXT_STEP001R1_GROUPWARE_CONSTRUCTION_GUIDE_PATTERN_ALIGNMENT"
            and item.get("version") == "0.1.1"
            and item.get("production") is False
            for item in catalog.get("projects", [])
        ),
        "runtime_wiring_explicitly_deferred": contracts["runtime-organization-context-connector"]["implemented"] is False
        and contracts["runtime-organization-context-connector"]["status"] == "DEFERRED_TO_RUNTIME_WIRING_STEP",
        "connector_product_api_contract_implemented": contracts["connector-organization-context-api"]["implemented"] is True,
        "example_construction_guide_contract_implemented": contracts["connector-example-organization-context-api"]["construction_guide"] is True,
        "connector_acceptance_passed": connector_payload.get("state") == "PASSED" and connector_payload.get("passed_checks") == 8,
        "example_acceptance_passed": example_payload.get("state") == "PASSED" and example_payload.get("passed_checks") == 9,
        "connector_example_integration_passed": integration_payload.get("state") == "PASSED" and integration_payload.get("passed_checks") == 10,
        "department_scope_and_ambiguity_proven": integration_checks.get("department_scoped_resolution_normalized") is True
        and integration_checks.get("ambiguity_preserved_without_guessing") is True,
        "mutable_change_visible_through_read_only_connector": integration_checks.get("mutable_product_change_visible_through_read_only_connector") is True,
        "delegated_identity_and_secret_redaction_proven": integration_checks.get("delegated_identity_forwarded") is True
        and integration_checks.get("authorization_value_not_captured") is True,
        "connector_is_read_only": connector_binding.get("read_only") is True
        and connector_binding.get("fake_mode_allowed") is False
        and all(not name.startswith(("create_", "update_", "delete_")) for name in connector_binding.get("tool_names", [])),
        "example_is_not_mcp": "@modelcontextprotocol" not in example_source and "/tenants/" not in example_source,
        "frequent_crud_contract_present": all(
            token in example_source
            for token in ("catalog-state", "glossary/changes", "row_version_conflict", 'term.status = "RETIRED"')
        ),
        "connector_example_source_import_absent": "organization-context-api-fake" not in connector_source and "FAKE_MODE" not in connector_source,
        "independent_project_environments_declared": "organization-context-mcp-server\\.venv" in setup_source
        and "organization-context\\organization-context-api-fake" in setup_source,
        "workspace_unit_tests_passed": unit.get("returncode") == 0,
        "subproject_acceptance_did_not_mutate_source": before == after,
        "workspace_manifest_exact": all(not values for values in drift.values()),
        "node_and_project_python_resolved": bool(node) and bool(npm) and Path(connector_python).is_file(),
        "groupware_workspace_e2e_pattern_reused": (ROOT / "tests/run_organization_context_connector_example_e2e.py").is_file()
        and "from workspace_process import prepare_invocation, resolve_executable" in (ROOT / "tests/run_organization_context_connector_example_e2e.py").read_text(encoding="utf-8"),
        "short_windows_execution_copy_paths_used": 'connector = temp / "c"' in Path(__file__).read_text(encoding="utf-8")
        and 'example = temp / "e"' in Path(__file__).read_text(encoding="utf-8"),
        "bespoke_compiler_gate_absent": not (connector_root / "scripts/compile_source_tree.py").exists()
        and '"compileall": [sys.executable, "-m", "compileall"' in (connector_root / "scripts/run_acceptance.py").read_text(encoding="utf-8"),
        "example_groupware_project_skeleton_aligned": (example_root / "scripts/package-source.mjs").is_file()
        and json.loads((example_root / "package.json").read_text(encoding="utf-8"))["scripts"].get("package:source") == "node scripts/package-source.mjs",
    }
    state = "PASSED" if all(checks.values()) else "FAILED"
    payload = {
        "schema_version": "okcanvas-agent-platform-workspace-step005r1-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_CONNECTOR_AND_EXAMPLE_FOUNDATION",
        "state": state,
        "started_at": started,
        "completed_at": now(),
        "execution_platform": "windows" if os.name == "nt" else os.name,
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "workspace_manifest_drift": drift,
        "resolved_interpreters": {
            "workspace_bootstrap": sys.executable,
            "organization_context_connector": connector_python,
            "node": node,
            "npm": npm,
        },
        "parsed": parsed,
        "processes": {
            "workspace_unit_tests": unit,
            "connector_acceptance": connector_acceptance,
            "example_acceptance": example_acceptance,
            "connector_example_integration": integration,
        },
        "limitations": {
            "runtime_organization_context_wired": False,
            "real_enterprise_organization_context_called": False,
            "openai_model_called": False,
            "local_step084_catalog_replaced": False,
        },
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
