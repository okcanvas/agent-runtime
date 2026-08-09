from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from run_workspace_step008_live_acceptance import (
    CLI_ROOT,
    CONNECTOR_ROOT,
    EXAMPLE_ORGANIZATION_CONTEXT_API_TOKEN,
    EXAMPLE_ROOT,
    ENV_LOADED_KEYS,
    ENV_SOURCE_NAME,
    RUNTIME_ROOT,
    LiveASGIServer,
    close_process_pipes,
    collect_runtime_evidence,
    create_connector_app,
    create_loopback_certificates,
    create_runtime_app,
    event_payloads,
    mcp_http_factory,
    now,
    random_secret,
    redact,
    registry_json,
    remove_temp_tree,
    resolve_executable,
    run_command,
    safe_failure_category,
    wait_http,
    ConnectorSettings,
)
from current_workspace_baseline import load_current_baseline

ROOT = Path(__file__).resolve().parents[1]
CURRENT = load_current_baseline(ROOT)
STEP = CURRENT.workspace_step
VERSION = CURRENT.workspace_version
RUNTIME_STEP = CURRENT.runtime_step
RUNTIME_VERSION = CURRENT.runtime_version
LIVE_GATE = "OKCANVAS_WORKSPACE_STEP008R4R9_RELATION_LIVE_ACCEPTANCE"
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP008R4R9_RELATION_LIVE_ACCEPTANCE.json"

CASES: tuple[dict[str, object], ...] = (
    {
        "case_id": "establish-employee-focus",
        "prompt": "김선임 연락처",
        "expected_tool": "resolve_organization_context",
        "expected_connector_path": "/api/v1/context/resolve",
        "expected_relation": None,
        "expected_focus_state": "RESOLVED",
        "expected_focus_ids": ["employee-0017"],
    },
    {
        "case_id": "employee-managed-products",
        "prompt": "그 사람이 담당하는 제품은?",
        "expected_tool": "get_organization_entity",
        "expected_connector_path": "/api/v1/context/entities/EMPLOYEE/employee-0017",
        "expected_relation": {
            "source_entity_type": "EMPLOYEE",
            "source_entity_id": "employee-0017",
            "relation_type": "EMPLOYEE_MANAGES_PRODUCT",
            "direction": "OUTBOUND",
            "result_entity_types": ["PRODUCT"],
        },
        "expected_focus_state": "MULTIPLE",
        "expected_focus_ids": ["product-016", "product-064", "product-112"],
    },
    {
        "case_id": "ordinal-product-clients",
        "prompt": "첫 번째 제품 고객사는?",
        "expected_tool": "get_organization_entity",
        "expected_connector_path": "/api/v1/context/entities/PRODUCT/product-016",
        "expected_relation": {
            "source_entity_type": "PRODUCT",
            "source_entity_id": "product-016",
            "relation_type": "CLIENT_USES_PRODUCT",
            "direction": "INBOUND",
            "result_entity_types": ["CLIENT"],
        },
        "expected_focus_state": "MULTIPLE",
        "expected_focus_ids": ["client-0015", "client-0118"],
    },
)


def _route_exact(route: dict[str, object], case: dict[str, object]) -> bool:
    if (
        route.get("status") != "EXECUTABLE"
        or route.get("request_class") != "SEARCH_KNOWLEDGE"
        or route.get("selected_agent_definition_id") != "organization-context-session-agent"
        or route.get("matched_rule_id") != "organization-context-short-read-session-stateless-subagent-v1"
    ):
        return False
    hint = route.get("organization_context_request_hint")
    if not isinstance(hint, dict):
        return False
    expected_relation = case["expected_relation"]
    if expected_relation is None:
        return (
            hint.get("pattern_id") == "organization-context-contact-field-short-v1"
            and hint.get("intent") == "ENTITY_FIELD_LOOKUP"
            and hint.get("target_expression") == "김선임"
            and hint.get("preferred_operation") == "RESOLVE"
            and hint.get("relation_traversal") in (None, {})
        )
    relation = hint.get("relation_traversal")
    return (
        hint.get("preferred_operation") == "GET"
        and hint.get("target_expression") == expected_relation["source_entity_id"]
        and isinstance(relation, dict)
        and relation.get("source_entity_type") == expected_relation["source_entity_type"]
        and relation.get("source_entity_id") == expected_relation["source_entity_id"]
        and relation.get("relation_type") == expected_relation["relation_type"]
        and relation.get("direction") == expected_relation["direction"]
        and list(relation.get("result_entity_types") or []) == expected_relation["result_entity_types"]
        and relation.get("max_results") == 20
    )


def _normalization_exact(run: dict[str, object], case: dict[str, object]) -> tuple[bool, dict[str, object]]:
    events = event_payloads(run, "agent.tool.output.normalized")
    if len(events) != 1:
        return False, {"event_count": len(events)}
    event = dict(events[0])
    focus = event.get("session_context_focus")
    if not isinstance(focus, dict):
        return False, event
    candidates = focus.get("candidates")
    if not isinstance(candidates, list):
        return False, event
    candidate_ids = [str(item.get("entity_id")) for item in candidates if isinstance(item, dict)]
    expected_ids = list(case["expected_focus_ids"])
    base = (
        event.get("normalization_strategy") == "product-owned-mcp-evidence-normalization-v1"
        and event.get("tool_name") == case["expected_tool"]
        and event.get("model_calls_added") == 0
        and event.get("tool_reexecuted") is False
        and event.get("model_output_persisted") is False
        and event.get("tool_result_persisted") is False
        and focus.get("state") == case["expected_focus_state"]
        and candidate_ids == expected_ids
    )
    expected_relation = case["expected_relation"]
    if expected_relation is None:
        return base, event
    relation_ok = (
        event.get("strategy") == "tool-evidence-relation-projection-v1"
        and event.get("relation_type") == expected_relation["relation_type"]
        and event.get("relation_direction") == expected_relation["direction"]
        and event.get("relation_source_entity_id") == expected_relation["source_entity_id"]
        and event.get("relation_projected_count") == len(expected_ids)
    )
    return base and relation_ok, event


async def execute(example_root: Path, output: Path) -> dict[str, object]:
    started = now()
    env_source = os.environ.get(ENV_SOURCE_NAME, "")
    loaded_keys = {item for item in os.environ.get(ENV_LOADED_KEYS, "").split(",") if item}
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OKCANVAS_AGENT_MODEL", "").strip()
    preflight = {
        "explicit_relation_live_gate": os.environ.get(LIVE_GATE) == "1",
        "environment_file_loaded": env_source in {".env.local", ".env.local.cmd"},
        "openai_key_loaded_from_environment_file": "OPENAI_API_KEY" in loaded_keys and bool(api_key),
        "model_loaded_from_environment_file": "OKCANVAS_AGENT_MODEL" in loaded_keys and bool(model),
        "model_name_safe": bool(model) and len(model) <= 200 and "\r" not in model and "\n" not in model,
    }
    if not all(preflight.values()):
        payload = {
            "schema_version": "okcanvas-workspace-step008r4r9-relation-live-acceptance-v1",
            "step": STEP,
            "version": VERSION,
            "runtime_step": RUNTIME_STEP,
            "runtime_version": RUNTIME_VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_ORGANIZATION_CONTEXT_RELATION_CHAIN_E2E",
            "state": "FAILED",
            "started_at": started,
            "completed_at": now(),
            "checks": preflight,
            "passed_checks": sum(value is True for value in preflight.values()),
            "total_checks": len(preflight),
            "safe_error": {"category": "LIVE_ENVIRONMENT_NOT_READY", "type": "PreflightFailure"},
            "environment": {
                "source_name": env_source or None,
                "loaded_key_names": sorted(loaded_keys),
                "openai_api_key_present": bool(api_key),
                "model": model or None,
                "secret_values_persisted": False,
            },
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload

    external_token = random_secret("step093-service")
    connector_token = random_secret("step093-connector")
    product_token = EXAMPLE_ORGANIZATION_CONTEXT_API_TOKEN
    admin_key = random_secret("step093-admin")
    submitter_key = random_secret("step093-submitter")
    payload_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    session_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    secrets = [api_key, external_token, connector_token, product_token, admin_key, submitter_key, payload_key, session_key]
    node = resolve_executable("node")
    npm = resolve_executable("npm")
    connector_server: LiveASGIServer | None = None
    runtime_server: LiveASGIServer | None = None
    fake_process: subprocess.Popen[bytes] | None = None
    original_factory = mcp_http_factory.strict_remote_http_client_factory
    previous_connector_bearer = os.environ.get("OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER")
    temp = Path(tempfile.mkdtemp(prefix="okcanvas-workspace-step093-relation-live-"))
    execution_stage = "initialize"
    payload: dict[str, object] | None = None
    cleanup_error_types: list[str] = []
    transient_removal_error_types: list[str] = []
    cleanup_completed = False

    try:
        execution_stage = "prepare_node_example"
        example = temp / "organization-context-api-fake"
        shutil.copytree(example_root, example, ignore=shutil.ignore_patterns("node_modules", "dist", ".pytest_cache"))
        environment = dict(os.environ)
        setup = run_command(npm, ["ci", "--ignore-scripts", "--offline"], cwd=example, env=environment, secrets=secrets)
        if setup["returncode"] != 0:
            raise RuntimeError("Node Organization Context example dependency setup failed")
        build = run_command(npm, ["run", "build"], cwd=example, env=environment, secrets=secrets)
        if build["returncode"] != 0:
            raise RuntimeError("Node Organization Context example build failed")

        fake_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fake_socket.bind(("127.0.0.1", 0))
        fake_port = int(fake_socket.getsockname()[1])
        fake_socket.close()
        fake_env = dict(environment)
        fake_env.update({"PORT": str(fake_port), "HOST": "127.0.0.1"})
        execution_stage = "start_node_example"
        fake_process = subprocess.Popen([node, "dist/src/main.js"], cwd=example, env=fake_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        fake_base_url = f"http://127.0.0.1:{fake_port}"
        await wait_http(fake_base_url, "/healthz")

        ca_path, cert_path, key_path = create_loopback_certificates(temp / "tls")
        execution_stage = "start_connector"
        connector_app = create_connector_app(ConnectorSettings(
            connector_bearer=connector_token,
            organization_context_base_url=fake_base_url,
            organization_context_api_bearer=product_token,
            http_timeout_seconds=3,
            max_retry_attempts=0,
        ))
        connector_server = LiveASGIServer(connector_app, ssl_certfile=cert_path, ssl_keyfile=key_path, hostname="localhost")
        connector_server.start()
        await wait_http(connector_server.base_url, "/healthz", verify=str(ca_path))

        def loopback_trusted_client_factory(headers=None, timeout=None, auth=None):
            kwargs: dict[str, Any] = {"follow_redirects": False, "trust_env": False, "verify": str(ca_path)}
            if headers is not None:
                kwargs["headers"] = headers
            if timeout is not None:
                kwargs["timeout"] = timeout
            if auth is not None:
                kwargs["auth"] = auth
            return httpx.AsyncClient(**kwargs)

        mcp_http_factory.strict_remote_http_client_factory = loopback_trusted_client_factory
        os.environ["OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"] = connector_token

        runtime_project = temp / "runtime-project"
        shutil.copytree(RUNTIME_ROOT / "specs", runtime_project / "specs")
        shutil.copytree(RUNTIME_ROOT / "reference", runtime_project / "reference")
        server_path = runtime_project / "specs/mcp/servers/organization-context-read/server.json"
        server_payload = json.loads(server_path.read_text(encoding="utf-8"))
        server_payload["url_template"] = f"{connector_server.base_url}/tenants/{{tenant_id}}/mcp"
        server_path.write_text(json.dumps(server_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        execution_stage = "start_runtime"
        runtime_app = create_runtime_app(
            project_root=runtime_project,
            product_db=temp / "runtime/product.sqlite3",
            artifact_root=temp / "runtime/artifacts",
            admin_key=admin_key,
            run_submitter_key=submitter_key,
            protected_payload_root=temp / "runtime/protected-payloads",
            protected_payload_key=payload_key,
            session_root=temp / "runtime/sessions",
            session_history_key=session_key,
            service_client_token_registry_json=registry_json(external_token),
        )
        runtime_server = LiveASGIServer(runtime_app)
        runtime_server.start()
        auth_headers = {"Authorization": f"Bearer {external_token}"}
        await wait_http(runtime_server.base_url, "/v1/service/whoami", headers=auth_headers)

        execution_stage = "create_organization_context_session"
        async with httpx.AsyncClient(base_url=runtime_server.base_url, headers=auth_headers, trust_env=False) as client:
            response = await client.post("/v1/service/sessions", json={"agent_definition_id": "organization-context-session-agent"})
            response.raise_for_status()
            created_session = response.json()
        session_id = str(created_session["session_id"])

        route_summaries: list[dict[str, object]] = []
        cli_summaries: list[dict[str, object]] = []
        run_summaries: list[dict[str, object]] = []
        route_checks: list[bool] = []
        normalization_checks: list[bool] = []

        for index, case in enumerate(CASES):
            execution_stage = f"route_{case['case_id']}"
            async with httpx.AsyncClient(base_url=runtime_server.base_url, headers=auth_headers, trust_env=False) as client:
                route_response = await client.post("/v1/service/assistant/routes", json={"input": case["prompt"], "session_id": session_id})
                route_response.raise_for_status()
                route = route_response.json()
            route_ok = _route_exact(route, case)
            route_checks.append(route_ok)
            route_summaries.append({
                "case_id": case["case_id"],
                "exact": route_ok,
                "status": route.get("status"),
                "matched_rule_id": route.get("matched_rule_id"),
                "request_hint": route.get("organization_context_request_hint"),
            })

            prompt_file = temp / f"prompt-{index + 1}.txt"
            prompt_file.write_text(f"{case['prompt']}\n/quit\n", encoding="utf-8")
            cli_env = dict(environment)
            cli_env["PYTHONUTF8"] = "1"
            execution_stage = f"execute_{case['case_id']}"
            cli = run_command(node, [
                "src/cli.mjs", "--base-url", runtime_server.base_url, "--bearer", external_token,
                "--model", model, "--session-id", session_id, "--script", str(prompt_file), "--yes", "--debug",
            ], cwd=CLI_ROOT, env=cli_env, secrets=secrets)
            cli_summaries.append({
                "case_id": case["case_id"],
                "returncode": cli["returncode"],
                "one_request_completed": "1개 요청 완료" in str(cli["stdout"]),
                "command": cli["command"],
                "stderr": cli["stderr"],
            })
            if cli["returncode"] != 0:
                raise RuntimeError(f"Product CLI failed for {case['case_id']}")

            evidence = await collect_runtime_evidence(runtime_server.base_url, external_token)
            runs = list(evidence["runs"])
            if len(runs) != index + 1:
                raise RuntimeError(f"Unexpected Run count after {case['case_id']}: {len(runs)}")
            run = runs[-1]
            normalization_ok, normalization = _normalization_exact(run, case)
            normalization_checks.append(normalization_ok)
            run_summaries.append({
                "case_id": case["case_id"],
                "run_id": run.get("run", {}).get("run_id"),
                "run_status": run.get("run", {}).get("status"),
                "tool_names": [str(item.get("tool_name")) for item in event_payloads(run, "tool.started")],
                "normalization_exact": normalization_ok,
                "normalization": normalization,
            })

        execution_stage = "collect_final_evidence"
        evidence = await collect_runtime_evidence(runtime_server.base_url, external_token)
        runs = list(evidence["runs"])
        async with httpx.AsyncClient(base_url=fake_base_url, trust_env=False) as fake:
            fake_requests = (await fake.get("/_fake/requests")).json()
        fake_items = list(fake_requests.get("requests", []))
        captured_paths = [item.get("path") for item in fake_items]
        expected_paths = [case["expected_connector_path"] for case in CASES]
        public_surface = json.dumps({"routes": route_summaries, "runs": run_summaries, "fake_requests": fake_requests}, ensure_ascii=False, default=str)

        checks = {
            **preflight,
            "harness_execution_completed_without_exception": True,
            "dedicated_organization_context_session_created": created_session.get("agent_definition_id") == "organization-context-session-agent" and session_id.startswith("session_"),
            "three_routes_resolved_sequentially_after_prior_turn_commit": len(route_checks) == 3 and all(route_checks),
            "three_cli_turns_completed": len(cli_summaries) == 3 and all(item["returncode"] == 0 and item["one_request_completed"] for item in cli_summaries),
            "exactly_three_runtime_runs_created": len(runs) == 3,
            "all_runtime_runs_succeeded": len(runs) == 3 and all(item.get("run", {}).get("status") == "SUCCEEDED" for item in runs),
            "expected_mcp_tool_sequence_observed": [item["tool_names"] for item in run_summaries] == [["resolve_organization_context"], ["get_organization_entity"], ["get_organization_entity"]],
            "relation_projection_focus_chain_exact": len(normalization_checks) == 3 and all(normalization_checks),
            "employee_relation_projects_three_products": run_summaries[1]["normalization"].get("relation_projected_count") == 3,
            "ordinal_product_relation_projects_two_clients": run_summaries[2]["normalization"].get("relation_projected_count") == 2,
            "actual_connector_example_paths_exact": captured_paths == expected_paths,
            "connector_authorization_redacted": all(item.get("authorization_present") is True and item.get("authorization_value_recorded") is False for item in fake_items),
            "secrets_absent_from_evidence": all(secret not in public_surface for secret in secrets),
        }
        payload = {
            "schema_version": "okcanvas-workspace-step008r4r9-relation-live-acceptance-v1",
            "step": STEP,
            "version": VERSION,
            "runtime_step": RUNTIME_STEP,
            "runtime_version": RUNTIME_VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_ORGANIZATION_CONTEXT_RELATION_CHAIN_E2E",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "started_at": started,
            "completed_at": now(),
            "checks": checks,
            "passed_checks": sum(value is True for value in checks.values()),
            "total_checks": len(checks),
            "environment": {
                "source_name": env_source,
                "loaded_key_names": sorted(loaded_keys),
                "openai_api_key_present": True,
                "model": model,
                "secret_values_persisted": False,
            },
            "route_summaries": route_summaries,
            "run_summaries": run_summaries,
            "cli_summaries": cli_summaries,
            "connector_example": {"captured_paths": captured_paths, "request_count": len(fake_items)},
            "limitations": {
                "production_database_executed": False,
                "object_storage_live_executed": False,
                "real_enterprise_organization_context_called": False,
            },
        }
    except BaseException as exc:
        payload = {
            "schema_version": "okcanvas-workspace-step008r4r9-relation-live-acceptance-v1",
            "step": STEP,
            "version": VERSION,
            "runtime_step": RUNTIME_STEP,
            "runtime_version": RUNTIME_VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_ORGANIZATION_CONTEXT_RELATION_CHAIN_E2E",
            "state": "FAILED",
            "started_at": started,
            "completed_at": now(),
            "checks": {
                **preflight,
                "harness_execution_completed_without_exception": False,
            },
            "passed_checks": sum(value is True for value in preflight.values()),
            "total_checks": len(preflight) + 1,
            "safe_error": {"category": safe_failure_category(exc), "type": type(exc).__name__},
            "failure_stage": execution_stage,
            "environment": {
                "source_name": env_source,
                "loaded_key_names": sorted(loaded_keys),
                "openai_api_key_present": True,
                "model": model,
                "secret_values_persisted": False,
            },
        }
    finally:
        mcp_http_factory.strict_remote_http_client_factory = original_factory
        if previous_connector_bearer is None:
            os.environ.pop("OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER", None)
        else:
            os.environ["OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"] = previous_connector_bearer
        for server in (runtime_server, connector_server):
            if server is not None:
                try:
                    server.stop()
                except BaseException as exc:
                    cleanup_error_types.append(type(exc).__name__)
        if fake_process is not None:
            try:
                if fake_process.poll() is None:
                    fake_process.terminate()
                    try:
                        fake_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        fake_process.kill()
                        fake_process.wait(timeout=5)
            except BaseException as exc:
                cleanup_error_types.append(type(exc).__name__)
            finally:
                close_process_pipes(fake_process)
        removed, removal_errors = remove_temp_tree(temp)
        transient_removal_error_types.extend(removal_errors)
        cleanup_completed = removed and not cleanup_error_types

    assert payload is not None
    checks = dict(payload.get("checks") or {})
    checks["harness_cleanup_completed"] = cleanup_completed
    payload["checks"] = checks
    payload["passed_checks"] = sum(value is True for value in checks.values())
    payload["total_checks"] = len(checks)
    payload["state"] = (
        "PASSED"
        if payload.get("state") == "PASSED" and all(checks.values())
        else "FAILED"
    )
    payload["cleanup"] = {
        "completed": cleanup_completed,
        "cleanup_error_types": cleanup_error_types,
        "transient_removal_error_types": transient_removal_error_types,
    }
    public = redact(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", secrets)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(public, encoding="utf-8")
    return json.loads(public)


def main() -> int:
    parser = argparse.ArgumentParser(description="STEP093 relation-aware Windows Live OpenAI acceptance")
    parser.add_argument("--example-root", default=str(EXAMPLE_ROOT))
    parser.add_argument("--output", default=str(OUTPUT_DEFAULT))
    args = parser.parse_args()
    payload = asyncio.run(execute(Path(args.example_root).resolve(), Path(args.output).resolve()))
    print(json.dumps({
        "state": payload.get("state"),
        "passed_checks": payload.get("passed_checks"),
        "total_checks": payload.get("total_checks"),
        "output": str(Path(args.output).resolve()),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("state") == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
