from __future__ import annotations

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

STEP = "WORKSPACE_STEP002R1_PRODUCT_SERVICE_CLI_WINDOWS_NODE_PATH_SPACE_CLOSURE"
VERSION = "0.2.1"
OUTPUT = ROOT / "docs/evidence/WORKSPACE_STEP002R1_ACCEPTANCE.json"


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_last_json(process: dict[str, Any]) -> dict[str, Any] | None:
    text = str(process.get("stdout", "")).strip()
    if not text:
        return None
    starts = [index for index, char in enumerate(text) if char == "{"]
    for index in reversed(starts):
        try:
            return json.loads(text[index:])
        except json.JSONDecodeError:
            continue
    return None


def copy_project(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(".venv", "node_modules", "__pycache__", ".pytest_cache", "dist"),
    )


def failure_payload(started: str, errors: list[str]) -> dict[str, Any]:
    checks = {
        "workspace_root_contract_exact": False,
        "external_node_tools_resolved": False,
        "subprocess_output_encoding_safe": False,
    }
    return {
        "schema_version": "okcanvas-agent-platform-workspace-step002r1-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "FAILED",
        "started_at": started,
        "completed_at": now(),
        "checks": checks,
        "passed_checks": 0,
        "total_checks": len(checks),
        "errors": errors,
    }


def main() -> int:
    started = now()
    root_errors = workspace_root_errors(ROOT)
    if root_errors:
        payload = failure_payload(started, root_errors)
        write_json_stdout(payload)
        return 2

    resolution_errors: list[str] = []
    try:
        node = resolve_executable("node")
    except FileNotFoundError as exc:
        node = "node"
        resolution_errors.append(str(exc))
    try:
        npm = resolve_executable("npm")
    except FileNotFoundError as exc:
        npm = "npm"
        resolution_errors.append(str(exc))
    if resolution_errors:
        payload = failure_payload(started, resolution_errors)
        payload["checks"]["workspace_root_contract_exact"] = True
        payload["passed_checks"] = 1
        write_json_stdout(payload)
        return 2

    utf8_probe, utf8_probe_encoding = decode_process_output(
        "상태 → PASS".encode("utf-8"), preferred_encoding="cp949"
    )
    cp949_probe, cp949_probe_encoding = decode_process_output(
        "상태 통과".encode("cp949"), preferred_encoding="cp949"
    )
    output_encoding_safe = (
        utf8_probe == "상태 → PASS"
        and utf8_probe_encoding == "utf-8"
        and cp949_probe == "상태 통과"
        and cp949_probe_encoding.lower().replace("-", "") == "cp949"
    )

    runtime = ROOT / "okcanvas-agent-runtime"
    project_roots = [
        runtime,
        ROOT / "okcanvas-agent-cli",
        ROOT / "okcanvas-connectors/groupware-mcp-server",
        ROOT / "okcanvas-connector-examples/groupware/groupware-api-fake",
    ]
    before_source = {str(path.relative_to(ROOT)): snapshot_files(path) for path in project_roots}
    unit = run_process(
        sys.executable,
        ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
        cwd=ROOT,
    )

    with tempfile.TemporaryDirectory(prefix="okcanvas-workspace-step001r1-") as temp_name:
        temp = Path(temp_name)
        cli = temp / "okcanvas-agent-cli"
        connector = temp / "okcanvas-connectors/groupware-mcp-server"
        example = temp / "okcanvas-connector-examples/groupware/groupware-api-fake"
        copy_project(ROOT / "okcanvas-agent-cli", cli)
        copy_project(ROOT / "okcanvas-connectors/groupware-mcp-server", connector)
        copy_project(ROOT / "okcanvas-connector-examples/groupware/groupware-api-fake", example)

        cli_acceptance = run_process(node, ["scripts/run-acceptance.mjs"], cwd=cli)
        connector_env = dict(os.environ)
        connector_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        connector_acceptance = run_process(
            sys.executable, ["scripts/run_acceptance.py"], cwd=connector, env=connector_env
        )
        example_acceptance = run_process(npm, ["run", "acceptance"], cwd=example)
        connector_example = run_process(
            sys.executable,
            [
                str(ROOT / "tests/run_groupware_connector_example_e2e.py"),
                "--connector-root",
                str(connector),
                "--example-root",
                str(example),
            ],
            cwd=ROOT,
            env=connector_env,
        )

    cli_payload = parse_last_json(cli_acceptance)
    connector_payload = parse_last_json(connector_acceptance)
    example_payload = parse_last_json(example_acceptance)
    integration_payload = parse_last_json(connector_example)
    parent_runtime = json.loads(
        (ROOT / "docs/evidence/STEP086R2_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8")
    )

    checks = {
        "workspace_root_contract_exact": True,
        "external_node_tools_resolved": Path(node).is_absolute() and Path(npm).is_absolute(),
        "subprocess_output_encoding_safe": output_encoding_safe,
        "workspace_unit_tests_passed": unit["returncode"] == 0,
        "product_cli_interactive_acceptance_passed": cli_acceptance["returncode"] == 0
        and cli_payload is not None
        and cli_payload.get("state") == "PASSED"
        and cli_payload.get("step") == "CLI_STEP001R1_WINDOWS_NODE_TEST_RUNNER_PATH_SPACE_CLOSURE"
        and cli_payload.get("version") == "0.2.1"
        and cli_payload.get("passed_checks") == cli_payload.get("total_checks") == 11,
        "connector_retained_acceptance_passed": connector_acceptance["returncode"] == 0
        and connector_payload is not None
        and connector_payload.get("state") == "PASSED"
        and connector_payload.get("passed_checks") == connector_payload.get("total_checks") == 7,
        "example_retained_acceptance_passed": example_acceptance["returncode"] == 0
        and example_payload is not None
        and example_payload.get("state") == "PASSED"
        and example_payload.get("passed_checks") == example_payload.get("total_checks") == 6,
        "connector_to_example_integration_passed": connector_example["returncode"] == 0
        and integration_payload is not None
        and integration_payload.get("state") == "PASSED"
        and integration_payload.get("passed_checks") == integration_payload.get("total_checks") == 7
        and integration_payload.get("example_step") == "EXAMPLE_STEP001R1_TYPESCRIPT_BUILD_DEPENDENCY_CLOSURE",
        "runtime_windows_parent_evidence_retained": parent_runtime.get("state") == "PASSED"
        and parent_runtime.get("step") == "STEP086R2_DELEGATED_ROLE_HEADER_AND_EXTERNAL_CONNECTOR_CONTRACT_CLOSURE"
        and parent_runtime.get("version") == "2.66.2"
        and parent_runtime.get("passed_checks") == parent_runtime.get("total_checks") == 15,
        "runtime_nested_connector_absent": not (runtime / "okcanvas-connectors").exists(),
        "runtime_nested_example_absent": not (runtime / "okcanvas-connector-examples").exists(),
        "workspace_shared_python_environment_absent": not (ROOT / ".venv").exists(),
        "workspace_shared_node_environment_absent": not (ROOT / "node_modules").exists(),
        "local_environment_excluded_from_identity": excluded_parent_project_path(Path(".env.local")),
        "product_cli_workspace_launcher_present": (ROOT / "sh_run_agent_cli.cmd").is_file(),
        "product_cli_product_ready_contract": (ROOT / "okcanvas-agent-cli/specs/service-cli-boundary.json").is_file()
        and json.loads((ROOT / "okcanvas-agent-cli/specs/service-cli-boundary.json").read_text(encoding="utf-8")).get("implementation_state") == "PRODUCT_READY",
        "product_cli_windows_node_path_space_closed": cli_payload is not None
        and cli_payload.get("checks", {}).get("windows_node_test_runner_path_space_safe") is True,
        "workspace_test_import_root_exact": unit["returncode"] == 0,
        "subproject_acceptance_did_not_mutate_source": False,
    }
    post_identity = run_process(
        sys.executable,
        [
            "-m",
            "unittest",
            "tests.test_workspace_structure.WorkspaceStructureTest.test_parent_project_files_are_byte_identical",
            "-v",
        ],
        cwd=ROOT,
    )
    after_source = {str(path.relative_to(ROOT)): snapshot_files(path) for path in project_roots}
    checks["subproject_acceptance_did_not_mutate_source"] = (
        before_source == after_source and post_identity["returncode"] == 0
    )

    payload = {
        "schema_version": "okcanvas-agent-platform-workspace-step002r1-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "resolved_executables": {"node": node, "npm": npm, "python": sys.executable},
        "processes": {
            "workspace_unit_tests": unit,
            "post_acceptance_parent_identity": post_identity,
            "product_cli": cli_acceptance,
            "connector": connector_acceptance,
            "example": example_acceptance,
            "connector_example_integration": connector_example,
        },
        "parsed": {
            "product_cli": cli_payload,
            "connector": connector_payload,
            "example": example_payload,
            "connector_example_integration": integration_payload,
        },
        "retained_product_source_bytes": True,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_json_stdout(payload)
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
