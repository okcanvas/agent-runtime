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

from workspace_inventory import excluded_parent_project_path, snapshot_files
from workspace_process import decode_process_output, resolve_executable, run_process, workspace_root_errors, write_json_stdout

STEP = "WORKSPACE_STEP003_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_E2E"
VERSION = "0.3.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP003_ACCEPTANCE.json"


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


def failure(started: str, errors: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "okcanvas-agent-platform-workspace-step003-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_FULL_PROCESS_BOUNDARY",
        "state": "FAILED",
        "started_at": started,
        "completed_at": now(),
        "checks": {"workspace_root_contract_exact": False},
        "passed_checks": 0,
        "total_checks": 1,
        "errors": errors,
        "limitations": {
            "windows_step003_executed": False,
            "live_openai_model_called": False,
            "real_enterprise_groupware_provider_called": False,
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

    try:
        node = resolve_executable("node")
        npm = resolve_executable("npm")
    except FileNotFoundError as exc:
        payload = failure(started, [str(exc)])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_json_stdout(payload)
        return 2

    utf8_text, utf8_encoding = decode_process_output("상태 → PASS".encode("utf-8"), preferred_encoding="cp949")
    cp949_text, cp949_encoding = decode_process_output("상태 통과".encode("cp949"), preferred_encoding="cp949")
    output_encoding_safe = (
        utf8_text == "상태 → PASS" and utf8_encoding == "utf-8"
        and cp949_text == "상태 통과" and cp949_encoding.lower().replace("-", "") == "cp949"
    )

    project_roots = {
        "runtime": ROOT / "okcanvas-agent-runtime",
        "cli": ROOT / "okcanvas-agent-cli",
        "connector": ROOT / "okcanvas-connectors/groupware-mcp-server",
        "example": ROOT / "okcanvas-connector-examples/groupware/groupware-api-fake",
    }
    before = {name: snapshot_files(path) for name, path in project_roots.items()}
    unit = run_process(sys.executable, ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], cwd=ROOT)

    with tempfile.TemporaryDirectory(prefix="okcanvas-workspace-step003-acceptance-") as temp_name:
        temp = Path(temp_name)
        cli = temp / "okcanvas-agent-cli"
        connector = temp / "okcanvas-connectors/groupware-mcp-server"
        example = temp / "okcanvas-connector-examples/groupware/groupware-api-fake"
        copy_project(project_roots["cli"], cli)
        copy_project(project_roots["connector"], connector)
        copy_project(project_roots["example"], example)

        cli_acceptance = run_process(node, ["scripts/run-acceptance.mjs"], cwd=cli)
        connector_env = dict(os.environ)
        connector_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        connector_acceptance = run_process(sys.executable, ["scripts/run_acceptance.py"], cwd=connector, env=connector_env)
        example_acceptance = run_process(npm, ["run", "acceptance"], cwd=example)
        connector_example = run_process(
            sys.executable,
            [str(ROOT / "tests/run_groupware_connector_example_e2e.py"), "--connector-root", str(connector), "--example-root", str(example)],
            cwd=ROOT,
            env=connector_env,
        )
        full_e2e = run_process(
            sys.executable,
            [str(ROOT / "tests/run_main_assistant_groupware_subagent_e2e.py"), "--example-root", str(example), "--output", str(temp / "step003-e2e.json")],
            cwd=ROOT,
        )

    runtime_evidence = json.loads(
        (ROOT / "okcanvas-agent-runtime/docs/evidence/STEP087_DETERMINISTIC_ACCEPTANCE.json").read_text(encoding="utf-8")
    )
    parsed = {
        "runtime": runtime_evidence,
        "cli": parse_last_json(cli_acceptance),
        "connector": parse_last_json(connector_acceptance),
        "example": parse_last_json(example_acceptance),
        "connector_example": parse_last_json(connector_example),
        "full_e2e": parse_last_json(full_e2e),
    }
    catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
    contracts = {item["id"]: item for item in json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]}
    windows_parent = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP002R1_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    e2e_text = json.dumps(parsed["full_e2e"], ensure_ascii=False, sort_keys=True)
    runtime_catalog = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")

    checks = {
        "workspace_root_contract_exact": True,
        "external_node_tools_resolved": Path(node).is_absolute() and Path(npm).is_absolute(),
        "subprocess_output_encoding_safe": output_encoding_safe,
        "workspace_unit_tests_passed": unit["returncode"] == 0,
        "runtime_step087_acceptance_passed": parsed["runtime"] is not None and parsed["runtime"].get("state") == "PASSED"
        and parsed["runtime"].get("passed_checks") == parsed["runtime"].get("total_checks") == 15,
        "product_cli_retained_acceptance_passed": cli_acceptance["returncode"] == 0
        and parsed["cli"] is not None and parsed["cli"].get("state") == "PASSED"
        and parsed["cli"].get("passed_checks") == parsed["cli"].get("total_checks") == 11,
        "connector_retained_acceptance_passed": connector_acceptance["returncode"] == 0
        and parsed["connector"] is not None and parsed["connector"].get("state") == "PASSED"
        and parsed["connector"].get("passed_checks") == parsed["connector"].get("total_checks") == 7,
        "example_retained_acceptance_passed": example_acceptance["returncode"] == 0
        and parsed["example"] is not None and parsed["example"].get("state") == "PASSED"
        and parsed["example"].get("passed_checks") == parsed["example"].get("total_checks") == 6,
        "connector_example_integration_passed": connector_example["returncode"] == 0
        and parsed["connector_example"] is not None and parsed["connector_example"].get("state") == "PASSED"
        and parsed["connector_example"].get("passed_checks") == parsed["connector_example"].get("total_checks") == 7,
        "main_assistant_groupware_full_e2e_passed": full_e2e["returncode"] == 0
        and parsed["full_e2e"] is not None and parsed["full_e2e"].get("state") == "PASSED"
        and parsed["full_e2e"].get("passed_checks") == parsed["full_e2e"].get("total_checks") == 14,
        "workspace_catalog_promoted_exact": catalog.get("workspace_step") == STEP and catalog.get("workspace_version") == VERSION
        and runtime_catalog.get("baseline") == "STEP087_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_DELEGATION"
        and runtime_catalog.get("version") == "2.67.0",
        "integration_contracts_promoted_exact": contracts["service-cli-runtime"].get("implemented") is True
        and contracts["runtime-main-assistant-groupware-subagent"].get("implemented") is True
        and contracts["runtime-main-assistant-groupware-subagent"].get("protocol") == "AGENT_AS_TOOL",
        "step002r1_windows_parent_retained": windows_parent.get("state") == "PASSED"
        and windows_parent.get("passed_checks") == windows_parent.get("total_checks") == 19,
        "current_step003_windows_not_claimed": parsed["runtime"] is not None
        and parsed["runtime"].get("limitations", {}).get("windows_step087_executed") is False,
        "runtime_nested_connector_and_example_absent": not (project_roots["runtime"] / "okcanvas-connectors").exists()
        and not (project_roots["runtime"] / "okcanvas-connector-examples").exists(),
        "workspace_shared_environments_absent": not (ROOT / ".venv").exists() and not (ROOT / "node_modules").exists(),
        "local_environment_excluded_from_identity": excluded_parent_project_path(Path(".env.local")),
        "step003_launcher_present": (ROOT / "sh_run_workspace_step003_acceptance.cmd").is_file(),
        "e2e_command_bearer_redacted": parsed["full_e2e"] is not None
        and "[REDACTED]" in e2e_text and "step003-external-service-bearer-123456" not in e2e_text,
        "e2e_connector_and_groupware_secrets_absent": "step003-connector-bearer-123456" not in e2e_text
        and "example-groupware-api-token" not in e2e_text,
        "live_provider_claims_remain_false": parsed["runtime"] is not None
        and parsed["runtime"].get("limitations", {}).get("live_openai_model_called") is False
        and parsed["runtime"].get("limitations", {}).get("live_groupware_provider_called") is False,
        "subproject_acceptance_did_not_mutate_source": False,
    }
    after = {name: snapshot_files(path) for name, path in project_roots.items()}
    checks["subproject_acceptance_did_not_mutate_source"] = before == after

    payload = {
        "schema_version": "okcanvas-agent-platform-workspace-step003-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_FULL_PROCESS_BOUNDARY",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "resolved_executables": {"python": sys.executable, "node": node, "npm": npm},
        "processes": {
            "workspace_unit_tests": unit,
            "runtime_step087_evidence": {
                "path": "okcanvas-agent-runtime/docs/evidence/STEP087_DETERMINISTIC_ACCEPTANCE.json",
                "state": runtime_evidence.get("state"),
                "passed_checks": runtime_evidence.get("passed_checks"),
                "total_checks": runtime_evidence.get("total_checks"),
            },
            "product_cli": cli_acceptance,
            "connector": connector_acceptance,
            "example": example_acceptance,
            "connector_example": connector_example,
            "main_assistant_groupware_e2e": full_e2e,
        },
        "parsed": parsed,
        "retained_product_source_bytes": before == after,
        "limitations": {
            "windows_step003_executed": False,
            "live_openai_model_called": False,
            "real_enterprise_groupware_provider_called": False,
            "deterministic_openai_agents_boundary_used": True,
            "actual_connector_process_executed": True,
            "actual_node_example_process_executed": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_json_stdout(payload)
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
