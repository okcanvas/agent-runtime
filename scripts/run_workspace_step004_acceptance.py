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

from workspace_inventory import excluded_package_path, excluded_workspace_path, snapshot_files
from workspace_process import (
    decode_process_output,
    render_json_for_console,
    resolve_executable,
    resolve_project_python,
    run_process,
    workspace_root_errors,
    write_json_stdout,
)

STEP = "WORKSPACE_STEP004R2_LIVE_GROUPWARE_FAKE_CREDENTIAL_SESSION_CONTINUATION_AND_JSON_STDOUT_CLOSURE"
VERSION = "0.4.2"
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP004R2_ACCEPTANCE.json"


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
        "changed": sorted(
            path for path in set(expected) & set(actual) if expected[path] != actual[path]
        ),
        "unexpected": sorted(set(actual) - set(expected)),
    }


def failure(started: str, errors: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "okcanvas-agent-platform-workspace-step004r2-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_LIVE_READINESS",
        "state": "FAILED",
        "started_at": started,
        "completed_at": now(),
        "execution_platform": "windows" if os.name == "nt" else os.name,
        "checks": {"workspace_root_contract_exact": False},
        "passed_checks": 0,
        "total_checks": 1,
        "errors": errors,
        "limitations": {
            "live_openai_model_called": False,
            "real_enterprise_groupware_provider_called": False,
            "windows_step004r2_live_executed": False,
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

    roots = {
        "runtime": ROOT / "okcanvas-agent-runtime",
        "cli": ROOT / "okcanvas-agent-cli",
        "connector": ROOT / "okcanvas-connectors/groupware-mcp-server",
        "example": ROOT / "okcanvas-connector-examples/groupware/groupware-api-fake",
    }
    try:
        node = resolve_executable("node")
        npm = resolve_executable("npm")
        connector_python = resolve_project_python(
            roots["connector"],
            required_modules=("pytest", "fastapi", "httpx", "pydantic"),
            fallback_executable=sys.executable,
            allow_fallback=os.name != "nt",
        )
        runtime_python = resolve_project_python(
            roots["runtime"],
            required_modules=("fastapi", "uvicorn", "httpx", "pydantic", "cryptography"),
            fallback_executable=sys.executable,
            allow_fallback=os.name != "nt",
        )
    except FileNotFoundError as exc:
        payload = failure(started, [str(exc)])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_json_stdout(payload)
        return 2

    utf8_text, utf8_encoding = decode_process_output("상태 → PASS".encode("utf-8"), preferred_encoding="cp949")
    cp949_text, cp949_encoding = decode_process_output("상태 통과".encode("cp949"), preferred_encoding="cp949")
    console_probe = {"korean": "상태", "symbol": "✔", "arrow": "→", "emoji": "🧪"}
    cp949_console_text, cp949_console_encoding, cp949_console_escaped = render_json_for_console(
        console_probe, encoding="cp949"
    )
    encoding_safe = (
        utf8_text == "상태 → PASS" and utf8_encoding == "utf-8"
        and cp949_text == "상태 통과" and cp949_encoding.lower().replace("-", "") == "cp949"
        and cp949_console_escaped and cp949_console_encoding == "ascii-json-escape"
        and json.loads(cp949_console_text) == console_probe
    )

    drift = manifest_drift()
    before = {name: snapshot_files(path) for name, path in roots.items()}
    unit = run_process(sys.executable, ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], cwd=ROOT)

    with tempfile.TemporaryDirectory(prefix="okcanvas-workspace-step004-acceptance-") as temp_name:
        temp = Path(temp_name)
        cli = temp / "okcanvas-agent-cli"
        connector = temp / "okcanvas-connectors/groupware-mcp-server"
        example = temp / "okcanvas-connector-examples/groupware/groupware-api-fake"
        copy_project(roots["cli"], cli)
        copy_project(roots["connector"], connector)
        copy_project(roots["example"], example)

        cli_acceptance = run_process(node, ["scripts/run-acceptance.mjs"], cwd=cli)
        connector_env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        connector_acceptance = run_process(connector_python, ["scripts/run_acceptance.py"], cwd=connector, env=connector_env)
        example_acceptance = run_process(npm, ["run", "acceptance"], cwd=example)
        connector_example = run_process(
            connector_python,
            [
                str(ROOT / "tests/run_groupware_connector_example_e2e.py"),
                "--connector-root", str(connector),
                "--example-root", str(example),
            ],
            cwd=ROOT,
            env=connector_env,
        )
        full_e2e = run_process(
            runtime_python,
            [
                str(ROOT / "tests/run_main_assistant_groupware_subagent_e2e.py"),
                "--example-root", str(example),
                "--output", str(temp / "step003-e2e.json"),
            ],
            cwd=ROOT,
        )
        live_preflight_env = dict(os.environ)
        for name in (
            "OKCANVAS_WORKSPACE_STEP004_LIVE_ACCEPTANCE",
            "OKCANVAS_LOCAL_ENV_SOURCE_NAME",
            "OKCANVAS_LOCAL_ENV_LOADED_KEYS",
            "OPENAI_API_KEY",
            "OKCANVAS_AGENT_MODEL",
        ):
            live_preflight_env.pop(name, None)
        live_preflight = run_process(
            runtime_python,
            [
                str(ROOT / "scripts/run_workspace_step004r2_live_acceptance.py"),
                "--output", str(temp / "step004-live-preflight.json"),
            ],
            cwd=ROOT,
            env=live_preflight_env,
        )

    runtime_evidence = json.loads(
        (roots["runtime"] / "docs/evidence/STEP087R2_DETERMINISTIC_ACCEPTANCE.json").read_text(encoding="utf-8")
    )
    parsed = {
        "runtime": runtime_evidence,
        "cli": parse_last_json(cli_acceptance),
        "connector": parse_last_json(connector_acceptance),
        "example": parse_last_json(example_acceptance),
        "connector_example": parse_last_json(connector_example),
        "full_e2e": parse_last_json(full_e2e),
        "live_preflight": parse_last_json(live_preflight),
    }
    after = {name: snapshot_files(path) for name, path in roots.items()}
    catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
    contracts = {
        item["id"]: item
        for item in json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]
    }
    windows_parent = json.loads(
        (ROOT / "docs/evidence/WORKSPACE_STEP003R2_WINDOWS_DETERMINISTIC_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8")
    )
    root_definition = json.loads(
        (roots["runtime"] / "specs/agents/organization-assistant-session-agent/definition.json").read_text(encoding="utf-8")
    )
    child_definition = json.loads(
        (roots["runtime"] / "specs/agents/groupware-read-agent/definition.json").read_text(encoding="utf-8")
    )
    live_source = (ROOT / "scripts/run_workspace_step004r2_live_acceptance.py").read_text(encoding="utf-8")
    isolation_source = (ROOT / "scripts/workspace_python_bytecode_isolation.py").read_text(encoding="utf-8")
    entrypoint_source = (roots["runtime"] / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    gateway_source = (
        roots["runtime"] / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py"
    ).read_text(encoding="utf-8")
    routing_source = (
        roots["runtime"] / "okcanvas_agent_runtime/application/assistant_routing/service.py"
    ).read_text(encoding="utf-8")
    routing_policy = json.loads(
        (roots["runtime"] / "specs/assistant/routing-policy.json").read_text(encoding="utf-8")
    )

    checks = {
        "workspace_root_contract_exact": not errors,
        "workspace_identity_exact": catalog.get("workspace_step") == STEP
        and catalog.get("workspace_version") == VERSION,
        "runtime_step087r2_identity_exact": next(
            item for item in catalog["projects"] if item["project_id"] == "agent-runtime"
        ).get("baseline") == "STEP087R2_SESSION_REFERENTIAL_RESTATEMENT_ROUTING_CLOSURE"
        and next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime").get("version") == "2.67.2",
        "step003r2_windows_parent_retained": windows_parent.get("state") == "PASSED"
        and windows_parent.get("passed_checks") == windows_parent.get("total_checks") == 27
        and windows_parent.get("windows_step003r2_accepted") is True,
        "runtime_step087r2_acceptance_passed": parsed["runtime"] is not None
        and parsed["runtime"].get("state") == "PASSED"
        and parsed["runtime"].get("passed_checks") == parsed["runtime"].get("total_checks"),
        "workspace_unit_tests_passed": unit.get("returncode") == 0,
        "product_cli_retained_acceptance_passed": parsed["cli"] is not None and parsed["cli"].get("state") == "PASSED",
        "connector_retained_acceptance_passed": parsed["connector"] is not None and parsed["connector"].get("state") == "PASSED",
        "example_retained_acceptance_passed": parsed["example"] is not None and parsed["example"].get("state") == "PASSED",
        "connector_example_integration_passed": parsed["connector_example"] is not None and parsed["connector_example"].get("state") == "PASSED",
        "deterministic_main_assistant_e2e_retained": parsed["full_e2e"] is not None
        and parsed["full_e2e"].get("state") == "PASSED"
        and parsed["full_e2e"].get("passed_checks") == parsed["full_e2e"].get("total_checks") == 14,
        "live_preflight_fails_closed_without_environment": live_preflight.get("returncode") == 1
        and parsed["live_preflight"] is not None
        and parsed["live_preflight"].get("state") == "FAILED"
        and parsed["live_preflight"].get("safe_error", {}).get("category") == "LIVE_ENVIRONMENT_NOT_READY",
        "live_environment_loader_contract_exact": 'OKCANVAS_LOCAL_ENV_SOURCE_NAME' in entrypoint_source
        and 'OKCANVAS_LOCAL_ENV_LOADED_KEYS' in entrypoint_source
        and 'workspace-step004-live-acceptance' in entrypoint_source,
        "live_openai_inputs_declared_exact": "OPENAI_API_KEY" in entrypoint_source
        and "OKCANVAS_AGENT_MODEL" in entrypoint_source
        and '"OPENAI_API_KEY" in loaded_keys' in live_source
        and '"OKCANVAS_AGENT_MODEL" in loaded_keys' in live_source,
        "live_full_process_harness_uses_actual_boundaries": "create_runtime_app(" in live_source
        and "create_connector_app(" in live_source
        and "OpenAIGenericAgentGateway" not in live_source
        and "DeterministicGroupwareSessionGateway" not in live_source
        and "dist/src/main.js" in live_source,
        "loopback_tls_trust_is_harness_scoped": "create_loopback_certificates" in live_source
        and '"verify": str(ca_path)' in live_source
        and "strict_remote_http_client_factory = original_factory" in live_source,
        "root_and_child_live_turn_budgets_exact": root_definition.get("max_turns") == 2
        and child_definition.get("max_turns") == 2,
        "child_tool_choice_required_for_live_mcp": 'child_agent_kwargs["model_settings"] = ModelSettings(' in gateway_source
        and 'tool_choice="required"' in gateway_source
        and 'child_agent_kwargs["reset_tool_choice"] = True' in gateway_source,
        "live_secret_values_never_declared_as_evidence": '"secret_values_persisted": False' in live_source
        and '"raw_provider_error_persisted": False' in live_source
        and "safe_failure_category" in live_source,
        "live_example_product_credential_exact": 'EXAMPLE_GROUPWARE_API_TOKEN = "example-groupware-api-token"' in live_source
        and 'groupware_token = EXAMPLE_GROUPWARE_API_TOKEN' in live_source
        and 'random_secret("step004-groupware")' not in live_source,
        "session_referential_restatement_routing_exact": "session-referential-restatement-v1" in routing_source
        and routing_policy.get("version") == "1.3.0"
        and set(("session_reference", "session_restatement", "external_refresh")).issubset(
            set(routing_policy.get("lexicons", {}))
        ),
        "live_session_item_count_contract_is_sdk_tolerant": "session_item_count >= 4" in live_source
        and "session_item_count % 2 == 0" in live_source
        and 'session.get("item_count") == 4' not in live_source,
        "live_stdout_remains_single_json_document": "file=sys.stderr" in entrypoint_source
        and "Loaded local environment" in entrypoint_source,
        "live_and_deterministic_launchers_present": (ROOT / "sh_run_workspace_step004r2_acceptance.cmd").is_file()
        and (ROOT / "sh_run_workspace_step004r2_live_acceptance.cmd").is_file()
        and "step004r2" in (ROOT / "sh_run_workspace_step004_acceptance.cmd").read_text(encoding="utf-8").casefold()
        and "step004r2" in (ROOT / "sh_run_workspace_step004_live_acceptance.cmd").read_text(encoding="utf-8").casefold(),
        "local_environment_and_live_evidence_excluded": excluded_workspace_path(Path("okcanvas-agent-runtime/.env.local"))
        and excluded_package_path(Path("okcanvas-agent-runtime/.env.local.cmd"))
        and excluded_package_path(Path("docs/evidence/WORKSPACE_STEP004_LIVE_ACCEPTANCE.json")),
        "workspace_python_bytecode_isolation_active": "PYTHONPYCACHEPREFIX" in isolation_source
        and "okcanvas-workspace-pycache-" in isolation_source
        and "workspace_python_bytecode_isolation.py" in (ROOT / "sh_run_workspace_step004r2_acceptance.cmd").read_text(encoding="utf-8")
        and "workspace_python_bytecode_isolation.py" in (ROOT / "sh_run_workspace_step004r2_live_acceptance.cmd").read_text(encoding="utf-8"),
        "project_python_environments_resolved": Path(runtime_python).is_file() and Path(connector_python).is_file(),
        "external_node_tools_resolved": bool(node) and bool(npm),
        "integration_contracts_retained": contracts["service-cli-runtime"]["implemented"] is True
        and contracts["runtime-main-assistant-groupware-subagent"]["implemented"] is True
        and contracts["runtime-groupware-connector"]["implemented"] is True
        and contracts["connector-groupware-api"]["implemented"] is True,
        "subproject_acceptance_did_not_mutate_source": before == after,
        "workspace_manifest_exact": all(not values for values in drift.values()),
        "subprocess_and_parent_json_encoding_safe": encoding_safe,
        "live_provider_not_claimed_by_readiness": parsed["runtime"] is not None
        and parsed["runtime"].get("limitations", {}).get("live_openai_model_called") is False
        and parsed["live_preflight"].get("environment", {}).get("secret_values_persisted") is False,
        "real_enterprise_provider_not_claimed": parsed["live_preflight"].get("limitations", {}).get(
            "real_enterprise_groupware_provider_called", False
        ) is False,
    }
    state = "PASSED" if all(checks.values()) else "FAILED"
    payload = {
        "schema_version": "okcanvas-agent-platform-workspace-step004r2-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_LIVE_READINESS",
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
            "runtime": runtime_python,
            "connector": connector_python,
            "node": node,
            "npm": npm,
        },
        "parsed": parsed,
        "processes": {
            "workspace_unit_tests": unit,
            "runtime_step087r2_evidence": {
                "path": "okcanvas-agent-runtime/docs/evidence/STEP087R2_DETERMINISTIC_ACCEPTANCE.json",
                "state": runtime_evidence.get("state"),
                "passed_checks": runtime_evidence.get("passed_checks"),
                "total_checks": runtime_evidence.get("total_checks"),
            },
            "product_cli": cli_acceptance,
            "connector": connector_acceptance,
            "example": example_acceptance,
            "connector_example": connector_example,
            "deterministic_full_e2e": full_e2e,
            "live_preflight": live_preflight,
        },
        "limitations": {
            "live_openai_model_called": False,
            "real_enterprise_groupware_provider_called": False,
            "windows_step004r2_live_executed": False,
            "windows_step004r2_live_accepted": False,
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
