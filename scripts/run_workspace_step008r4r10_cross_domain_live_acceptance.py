from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GROUPWARE_CONNECTOR_ROOT = ROOT / "okcanvas-connectors/groupware-mcp-server"
if str(GROUPWARE_CONNECTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(GROUPWARE_CONNECTOR_ROOT))

import httpx

from groupware_mcp_server.app import create_app as create_groupware_connector_app
from groupware_mcp_server.config import Settings as GroupwareConnectorSettings
from run_workspace_step008_live_acceptance import (
    CLI_ROOT,
    EXAMPLE_ORGANIZATION_CONTEXT_API_TOKEN,
    ENV_LOADED_KEYS,
    ENV_SOURCE_NAME,
    RUNTIME_ROOT,
    LiveASGIServer,
    close_process_pipes,
    collect_runtime_evidence,
    create_connector_app as create_organization_connector_app,
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
    ConnectorSettings as OrganizationConnectorSettings,
)
from current_workspace_baseline import load_current_baseline
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP as EXECUTABLE_RUNTIME_STEP, PROJECT_VERSION as EXECUTABLE_RUNTIME_VERSION

CURRENT = load_current_baseline(ROOT)
STEP = CURRENT.workspace_step
VERSION = CURRENT.workspace_version
RUNTIME_STEP = CURRENT.runtime_step
RUNTIME_VERSION = CURRENT.runtime_version
LIVE_GATE = "OKCANVAS_WORKSPACE_STEP008R4R10_CROSS_DOMAIN_LIVE_ACCEPTANCE"
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP008R4R10_CROSS_DOMAIN_LIVE_ACCEPTANCE.json"
ORG_EXAMPLE_ROOT = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"
GROUPWARE_EXAMPLE_ROOT = ROOT / "okcanvas-connector-examples/groupware/groupware-api-fake"
GROUPWARE_EXAMPLE_API_TOKEN = "example-groupware-api-token"



def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity_provenance() -> tuple[dict[str, object], dict[str, bool]]:
    baseline_path = ROOT / "specs/workspace/current-baseline.json"
    catalog_path = ROOT / "specs/workspace/project-catalog.json"
    pyproject_path = RUNTIME_ROOT / "pyproject.toml"
    runtime_baseline_path = RUNTIME_ROOT / "okcanvas_agent_runtime/core/baseline.py"
    harness_path = Path(__file__).resolve()

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    runtime_record = next(
        (item for item in catalog.get("projects", []) if item.get("project_id") == "agent-runtime"),
        None,
    )
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    pyproject_version = str(dict(pyproject.get("project") or {}).get("version") or "")

    checks = {
        "workspace_catalog_identity_matches_current_baseline": (
            catalog.get("workspace_step") == STEP and catalog.get("workspace_version") == VERSION
        ),
        "workspace_runtime_identity_matches_project_catalog": (
            isinstance(runtime_record, dict)
            and runtime_record.get("baseline") == RUNTIME_STEP
            and runtime_record.get("version") == RUNTIME_VERSION
        ),
        "workspace_runtime_identity_matches_executable_runtime": (
            RUNTIME_STEP == EXECUTABLE_RUNTIME_STEP and RUNTIME_VERSION == EXECUTABLE_RUNTIME_VERSION
        ),
        "workspace_runtime_version_matches_runtime_package_metadata": pyproject_version == RUNTIME_VERSION,
    }
    provenance = {
        "workspace_current_baseline": {
            "workspace_step": STEP,
            "workspace_version": VERSION,
            "runtime_step": RUNTIME_STEP,
            "runtime_version": RUNTIME_VERSION,
            "sha256": _sha256_file(baseline_path),
        },
        "workspace_project_catalog": {
            "workspace_step": catalog.get("workspace_step"),
            "workspace_version": catalog.get("workspace_version"),
            "runtime_step": runtime_record.get("baseline") if isinstance(runtime_record, dict) else None,
            "runtime_version": runtime_record.get("version") if isinstance(runtime_record, dict) else None,
            "sha256": _sha256_file(catalog_path),
        },
        "runtime_executable_baseline": {
            "runtime_step": EXECUTABLE_RUNTIME_STEP,
            "runtime_version": EXECUTABLE_RUNTIME_VERSION,
            "sha256": _sha256_file(runtime_baseline_path),
        },
        "runtime_package_metadata": {
            "runtime_version": pyproject_version,
            "sha256": _sha256_file(pyproject_path),
        },
        "focused_live_harness": {
            "sha256": _sha256_file(harness_path),
        },
        "runtime_service": None,
    }
    return provenance, checks


CASES: tuple[dict[str, object], ...] = (
    {
        "case_id": "establish-employee-focus",
        "prompt": "김선임 연락처",
        "expected_tool": "resolve_organization_context",
        "expected_domain": "ORGANIZATION_CONTEXT",
        "expected_resource": None,
        "expected_record_count": None,
    },
    {
        "case_id": "employee-calendar-cross-domain",
        "prompt": "그 사람 일정은?",
        "expected_tool": "list_calendar_events",
        "expected_domain": "GROUPWARE",
        "expected_resource": "CALENDAR",
        "expected_record_count": 1,
    },
    {
        "case_id": "employee-notice-cross-domain",
        "prompt": "그 사람 관련 공지 알려줘",
        "expected_tool": "search_notices",
        "expected_domain": "GROUPWARE",
        "expected_resource": "NOTICE",
        "expected_record_count": 1,
    },
)


def _route_exact(route: dict[str, object], case: dict[str, object]) -> bool:
    if route.get("status") != "EXECUTABLE" or route.get("selected_agent_definition_id") != "organization-assistant-session-agent":
        return False
    if case["expected_domain"] == "ORGANIZATION_CONTEXT":
        hint = route.get("organization_context_request_hint")
        return (
            route.get("request_class") == "SEARCH_KNOWLEDGE"
            and isinstance(hint, dict)
            and hint.get("pattern_id") == "organization-context-contact-field-short-v1"
            and hint.get("target_expression") == "김선임"
            and hint.get("preferred_operation") == "RESOLVE"
            and route.get("groupware_context_filter") in (None, {})
        )
    hint = route.get("groupware_context_filter")
    return (
        route.get("request_class") == "READ_SYSTEM"
        and route.get("matched_rule_id") == "groupware-read-session-stateless-subagent-v1"
        and isinstance(hint, dict)
        and hint.get("schema_version") == "okcanvas-groupware-context-filter-hint-v1"
        and hint.get("resource_kind") == case["expected_resource"]
        and hint.get("tool_name") == case["expected_tool"]
        and hint.get("entity_type") == "EMPLOYEE"
        and hint.get("entity_id") == "employee-0017"
        and hint.get("max_results") == 20
        and route.get("organization_context_request_hint") in (None, {})
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
    if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict):
        return False, event
    focus_ok = (
        focus.get("domain") == "ORGANIZATION_CONTEXT"
        and focus.get("state") == "RESOLVED"
        and candidates[0].get("entity_type") == "EMPLOYEE"
        and candidates[0].get("entity_id") == "employee-0017"
    )
    if case["expected_domain"] == "ORGANIZATION_CONTEXT":
        return (
            focus_ok
            and event.get("normalization_strategy") == "product-owned-mcp-evidence-normalization-v1"
            and event.get("tool_name") == "resolve_organization_context"
            and event.get("model_output_persisted") is False
            and event.get("tool_result_persisted") is False
        ), event
    return (
        focus_ok
        and event.get("normalization_strategy") == "product-owned-cross-domain-mcp-evidence-normalization-v1"
        and event.get("strategy") == "groupware-cross-domain-stable-context-filter-v1"
        and event.get("tool_name") == case["expected_tool"]
        and event.get("context_entity_type") == "EMPLOYEE"
        and event.get("context_entity_id") == "employee-0017"
        and event.get("context_filter_applied") is True
        and event.get("context_filtered_record_count") == case["expected_record_count"]
        and event.get("model_output_persisted") is False
        and event.get("tool_result_persisted") is False
    ), event


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    value = int(sock.getsockname()[1])
    sock.close()
    return value


def _start_example(*, source: Path, target: Path, npm: str, node: str, environment: dict[str, str], secrets: list[str]) -> tuple[subprocess.Popen[bytes], str]:
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("node_modules", "dist", ".pytest_cache"))
    setup = run_command(npm, ["ci", "--ignore-scripts", "--offline"], cwd=target, env=environment, secrets=secrets)
    if setup["returncode"] != 0:
        raise RuntimeError(f"Node example dependency setup failed: {source.name}")
    build = run_command(npm, ["run", "build"], cwd=target, env=environment, secrets=secrets)
    if build["returncode"] != 0:
        raise RuntimeError(f"Node example build failed: {source.name}")
    port = _free_port()
    child_env = dict(environment)
    child_env.update({"PORT": str(port), "HOST": "127.0.0.1"})
    process = subprocess.Popen(
        [node, "dist/src/main.js"], cwd=target, env=child_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return process, f"http://127.0.0.1:{port}"


async def execute(output: Path) -> dict[str, object]:
    started = now()
    env_source = os.environ.get(ENV_SOURCE_NAME, "")
    loaded_keys = {item for item in os.environ.get(ENV_LOADED_KEYS, "").split(",") if item}
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OKCANVAS_AGENT_MODEL", "").strip()
    identity_provenance, identity_checks = _identity_provenance()
    preflight = {
        "explicit_cross_domain_live_gate": os.environ.get(LIVE_GATE) == "1",
        "environment_file_loaded": env_source in {".env.local", ".env.local.cmd"},
        "openai_key_loaded_from_environment_file": "OPENAI_API_KEY" in loaded_keys and bool(api_key),
        "model_loaded_from_environment_file": "OKCANVAS_AGENT_MODEL" in loaded_keys and bool(model),
        "model_name_safe": bool(model) and len(model) <= 200 and "\r" not in model and "\n" not in model,
        **identity_checks,
    }
    if not all(preflight.values()):
        payload = {
            "schema_version": "okcanvas-workspace-step008r4r10-cross-domain-live-acceptance-v2",
            "step": STEP, "version": VERSION, "runtime_step": RUNTIME_STEP, "runtime_version": RUNTIME_VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_ORGANIZATION_TO_GROUPWARE_STABLE_FOCUS_E2E",
            "state": "FAILED", "started_at": started, "completed_at": now(),
            "checks": preflight, "passed_checks": sum(v is True for v in preflight.values()), "total_checks": len(preflight),
            "safe_error": {
                "category": "LIVE_IDENTITY_PROVENANCE_MISMATCH" if not all(identity_checks.values()) else "LIVE_ENVIRONMENT_NOT_READY",
                "type": "IdentityProvenanceFailure" if not all(identity_checks.values()) else "PreflightFailure",
            },
            "identity_provenance": identity_provenance,
            "environment": {"source_name": env_source or None, "loaded_key_names": sorted(loaded_keys), "openai_api_key_present": bool(api_key), "model": model or None, "secret_values_persisted": False},
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload

    external_token = random_secret("step094-service")
    org_connector_token = random_secret("step094-org-connector")
    groupware_connector_token = random_secret("step094-groupware-connector")
    admin_key = random_secret("step094-admin")
    submitter_key = random_secret("step094-submitter")
    payload_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    session_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    secrets = [api_key, external_token, org_connector_token, groupware_connector_token, EXAMPLE_ORGANIZATION_CONTEXT_API_TOKEN, GROUPWARE_EXAMPLE_API_TOKEN, admin_key, submitter_key, payload_key, session_key]
    node = resolve_executable("node")
    npm = resolve_executable("npm")
    temp = Path(tempfile.mkdtemp(prefix="okcanvas-workspace-step094-cross-domain-live-"))
    org_fake_process: subprocess.Popen[bytes] | None = None
    groupware_fake_process: subprocess.Popen[bytes] | None = None
    org_connector_server: LiveASGIServer | None = None
    groupware_connector_server: LiveASGIServer | None = None
    runtime_server: LiveASGIServer | None = None
    original_factory = mcp_http_factory.strict_remote_http_client_factory
    previous_org_bearer = os.environ.get("OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER")
    previous_groupware_bearer = os.environ.get("OKCANVAS_GROUPWARE_READ_BEARER")
    cleanup_error_types: list[str] = []
    transient_removal_error_types: list[str] = []
    cleanup_completed = False
    execution_stage = "initialize"
    payload: dict[str, object] | None = None
    failure_cli_diagnostic: dict[str, object] | None = None
    failure_runtime_diagnostic: dict[str, object] | None = None
    failure_runtime_diagnostic_error_type: str | None = None

    try:
        environment = dict(os.environ)
        execution_stage = "prepare_examples"
        org_fake_process, org_fake_base = _start_example(
            source=ORG_EXAMPLE_ROOT, target=temp / "organization-context-api-fake",
            npm=npm, node=node, environment=environment, secrets=secrets,
        )
        groupware_fake_process, groupware_fake_base = _start_example(
            source=GROUPWARE_EXAMPLE_ROOT, target=temp / "groupware-api-fake",
            npm=npm, node=node, environment=environment, secrets=secrets,
        )
        await wait_http(org_fake_base, "/healthz")
        await wait_http(groupware_fake_base, "/healthz")

        ca_path, cert_path, key_path = create_loopback_certificates(temp / "tls")
        execution_stage = "start_connectors"
        org_connector_server = LiveASGIServer(
            create_organization_connector_app(OrganizationConnectorSettings(
                connector_bearer=org_connector_token,
                organization_context_base_url=org_fake_base,
                organization_context_api_bearer=EXAMPLE_ORGANIZATION_CONTEXT_API_TOKEN,
                http_timeout_seconds=3, max_retry_attempts=0,
            )),
            ssl_certfile=cert_path, ssl_keyfile=key_path, hostname="localhost",
        )
        org_connector_server.start()
        await wait_http(org_connector_server.base_url, "/healthz", verify=str(ca_path))

        groupware_connector_server = LiveASGIServer(
            create_groupware_connector_app(GroupwareConnectorSettings(
                connector_bearer=groupware_connector_token,
                groupware_base_url=groupware_fake_base,
                groupware_api_bearer=GROUPWARE_EXAMPLE_API_TOKEN,
                http_timeout_seconds=3, max_retry_attempts=0,
            )),
            ssl_certfile=cert_path, ssl_keyfile=key_path, hostname="localhost",
        )
        groupware_connector_server.start()
        await wait_http(groupware_connector_server.base_url, "/healthz", verify=str(ca_path))

        def loopback_trusted_client_factory(headers=None, timeout=None, auth=None):
            kwargs: dict[str, Any] = {"follow_redirects": False, "trust_env": False, "verify": str(ca_path)}
            if headers is not None: kwargs["headers"] = headers
            if timeout is not None: kwargs["timeout"] = timeout
            if auth is not None: kwargs["auth"] = auth
            return httpx.AsyncClient(**kwargs)

        mcp_http_factory.strict_remote_http_client_factory = loopback_trusted_client_factory
        os.environ["OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"] = org_connector_token
        os.environ["OKCANVAS_GROUPWARE_READ_BEARER"] = groupware_connector_token

        runtime_project = temp / "runtime-project"
        shutil.copytree(RUNTIME_ROOT / "specs", runtime_project / "specs")
        shutil.copytree(RUNTIME_ROOT / "reference", runtime_project / "reference")
        org_server_path = runtime_project / "specs/mcp/servers/organization-context-read/server.json"
        org_server = json.loads(org_server_path.read_text(encoding="utf-8"))
        org_server["url_template"] = f"{org_connector_server.base_url}/tenants/{{tenant_id}}/mcp"
        org_server_path.write_text(json.dumps(org_server, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        groupware_server_path = runtime_project / "specs/mcp/servers/groupware-read/server.json"
        groupware_server = json.loads(groupware_server_path.read_text(encoding="utf-8"))
        groupware_server["url_template"] = f"{groupware_connector_server.base_url}/tenants/{{tenant_id}}/mcp"
        groupware_server_path.write_text(json.dumps(groupware_server, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        execution_stage = "start_runtime"
        runtime_server = LiveASGIServer(create_runtime_app(
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
        ))
        runtime_server.start()
        auth_headers = {"Authorization": f"Bearer {external_token}"}
        await wait_http(runtime_server.base_url, "/v1/service/whoami", headers=auth_headers)

        execution_stage = "verify_runtime_identity"
        async with httpx.AsyncClient(base_url=runtime_server.base_url, headers=auth_headers, trust_env=False) as client:
            capabilities_response = await client.get("/v1/service/capabilities")
            capabilities_response.raise_for_status()
            capabilities = capabilities_response.json()
        service_runtime_version = str(capabilities.get("runtime_version") or "")
        identity_provenance["runtime_service"] = {
            "schema_version": capabilities.get("schema_version"),
            "runtime_version": service_runtime_version,
        }
        preflight["runtime_service_version_matches_workspace_baseline"] = service_runtime_version == RUNTIME_VERSION
        if not preflight["runtime_service_version_matches_workspace_baseline"]:
            raise RuntimeError("Runtime Service version differs from Workspace current baseline")

        execution_stage = "create_session"
        async with httpx.AsyncClient(base_url=runtime_server.base_url, headers=auth_headers, trust_env=False) as client:
            response = await client.post("/v1/service/sessions", json={"agent_definition_id": "organization-assistant-session-agent"})
            response.raise_for_status()
            created_session = response.json()
        session_id = str(created_session["session_id"])

        route_summaries: list[dict[str, object]] = []
        run_summaries: list[dict[str, object]] = []
        cli_summaries: list[dict[str, object]] = []
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
            route_summaries.append({"case_id": case["case_id"], "exact": route_ok, "status": route.get("status"), "matched_rule_id": route.get("matched_rule_id"), "organization_context_request_hint": route.get("organization_context_request_hint"), "groupware_context_filter": route.get("groupware_context_filter")})

            prompt_file = temp / f"prompt-{index + 1}.txt"
            prompt_file.write_text(f"{case['prompt']}\n/quit\n", encoding="utf-8")
            cli_env = dict(environment)
            cli_env["PYTHONUTF8"] = "1"
            execution_stage = f"execute_{case['case_id']}"
            cli = run_command(node, [
                "src/cli.mjs", "--base-url", runtime_server.base_url, "--bearer", external_token,
                "--model", model, "--session-id", session_id, "--script", str(prompt_file), "--yes", "--debug",
            ], cwd=CLI_ROOT, env=cli_env, secrets=secrets)
            cli_summary = {
                "case_id": case["case_id"],
                "returncode": cli["returncode"],
                "one_request_completed": "1개 요청 완료" in str(cli["stdout"]),
                "stdout": cli["stdout"],
                "stderr": cli["stderr"],
                "stdout_encoding": cli["stdout_encoding"],
                "stderr_encoding": cli["stderr_encoding"],
                "command": cli["command"],
            }
            cli_summaries.append(cli_summary)
            # Always retain the latest redacted CLI observation before any post-CLI assertion.
            # Node CLI intentionally returns process exit 0 after rendering a per-request CliError,
            # so returncode alone is not proof that a Product request completed.
            failure_cli_diagnostic = dict(cli_summary)

            try:
                evidence = await collect_runtime_evidence(runtime_server.base_url, external_token)
                runs = list(evidence["runs"])
                failure_runtime_diagnostic = {
                    "run_count": len(runs),
                    "runs": [
                        {
                            "run": dict(item.get("run") or {}),
                            "event_types": [str(event.get("event_type")) for event in list(item.get("events") or [])],
                            "tool_names": [str(payload.get("tool_name")) for payload in event_payloads(item, "tool.started")],
                            "run_failed_payloads": event_payloads(item, "run.failed"),
                            "normalization_payloads": event_payloads(item, "agent.tool.output.normalized"),
                        }
                        for item in runs
                    ],
                }
            except BaseException as diagnostic_exc:
                failure_runtime_diagnostic_error_type = type(diagnostic_exc).__name__
                raise

            if cli["returncode"] != 0:
                raise RuntimeError(f"Product CLI process failed for {case['case_id']}")
            if not cli_summary["one_request_completed"]:
                raise RuntimeError(f"Product CLI request did not complete for {case['case_id']}")
            if len(runs) != index + 1:
                raise RuntimeError(f"Unexpected Run count after {case['case_id']}: {len(runs)}")
            run = runs[-1]
            normalization_ok, normalization = _normalization_exact(run, case)
            normalization_checks.append(normalization_ok)
            run_summaries.append({
                "case_id": case["case_id"], "run_id": run.get("run", {}).get("run_id"),
                "run_status": run.get("run", {}).get("status"),
                "tool_names": [str(item.get("tool_name")) for item in event_payloads(run, "tool.started")],
                "normalization_exact": normalization_ok, "normalization": normalization,
            })

        execution_stage = "collect_final_evidence"
        evidence = await collect_runtime_evidence(runtime_server.base_url, external_token)
        runs = list(evidence["runs"])
        async with httpx.AsyncClient(base_url=org_fake_base, trust_env=False) as client:
            org_requests = (await client.get("/_fake/requests")).json().get("requests", [])
        async with httpx.AsyncClient(base_url=groupware_fake_base, trust_env=False) as client:
            groupware_requests = (await client.get("/_fake/requests")).json().get("requests", [])
        groupware_paths = [item.get("path") for item in groupware_requests]
        groupware_bodies = [item.get("body") for item in groupware_requests]
        expected_ref = {"entity_type": "EMPLOYEE", "entity_id": "employee-0017"}
        canonical_bodies = all(
            isinstance(body, dict)
            and body.get("context_ref") == expected_ref
            and body.get("limit") == 20
            and ("query" not in body or body.get("query") == "")
            and "start_at" not in body and "end_at" not in body
            for body in groupware_bodies
        )
        public_surface = json.dumps({"routes": route_summaries, "runs": run_summaries, "org_requests": org_requests, "groupware_requests": groupware_requests}, ensure_ascii=False, default=str)
        checks = {
            **preflight,
            "harness_execution_completed_without_exception": True,
            "dedicated_session_created": created_session.get("agent_definition_id") == "organization-assistant-session-agent" and session_id.startswith("session_"),
            "three_routes_resolved_after_prior_turn_commit": len(route_checks) == 3 and all(route_checks),
            "three_cli_turns_completed": len(cli_summaries) == 3 and all(item["returncode"] == 0 and item["one_request_completed"] for item in cli_summaries),
            "exactly_three_runtime_runs_created": len(runs) == 3,
            "all_runtime_runs_succeeded": len(runs) == 3 and all(item.get("run", {}).get("status") == "SUCCEEDED" for item in runs),
            "expected_mcp_tool_sequence_observed": [item["tool_names"] for item in run_summaries] == [["resolve_organization_context"], ["list_calendar_events"], ["search_notices"]],
            "focus_is_preserved_across_groupware_turns_only_after_evidence": len(normalization_checks) == 3 and all(normalization_checks),
            "organization_connector_called_once": [item.get("path") for item in org_requests] == ["/api/v1/context/resolve"],
            "groupware_paths_exact": groupware_paths == ["/api/v1/calendar/events/list", "/api/v1/notices/search"],
            "groupware_context_ref_and_canonical_arguments_exact": canonical_bodies,
            "groupware_authorization_redacted": all(item.get("authorization_present") is True and item.get("authorization_value_recorded") is False for item in groupware_requests),
            "secrets_absent_from_evidence": all(secret not in public_surface for secret in secrets),
        }
        payload = {
            "schema_version": "okcanvas-workspace-step008r4r10-cross-domain-live-acceptance-v2",
            "step": STEP, "version": VERSION, "runtime_step": RUNTIME_STEP, "runtime_version": RUNTIME_VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_ORGANIZATION_TO_GROUPWARE_STABLE_FOCUS_E2E",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "started_at": started, "completed_at": now(), "checks": checks,
            "passed_checks": sum(v is True for v in checks.values()), "total_checks": len(checks),
            "route_summaries": route_summaries, "run_summaries": run_summaries, "cli_summaries": cli_summaries,
            "connector_examples": {"organization_request_count": len(org_requests), "groupware_request_count": len(groupware_requests), "groupware_paths": groupware_paths},
            "identity_provenance": identity_provenance,
            "environment": {"source_name": env_source, "loaded_key_names": sorted(loaded_keys), "openai_api_key_present": True, "model": model, "secret_values_persisted": False},
            "limitations": {"production_groupware_called": False, "production_database_executed": False, "object_storage_live_executed": False},
        }
    except BaseException as exc:
        payload = {
            "schema_version": "okcanvas-workspace-step008r4r10-cross-domain-live-acceptance-v2",
            "step": STEP, "version": VERSION, "runtime_step": RUNTIME_STEP, "runtime_version": RUNTIME_VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_ORGANIZATION_TO_GROUPWARE_STABLE_FOCUS_E2E",
            "state": "FAILED", "started_at": started, "completed_at": now(),
            "checks": {**preflight, "harness_execution_completed_without_exception": False},
            "passed_checks": sum(v is True for v in preflight.values()), "total_checks": len(preflight) + 1,
            "safe_error": {
                "category": "LIVE_IDENTITY_PROVENANCE_MISMATCH" if execution_stage == "verify_runtime_identity" else safe_failure_category(exc),
                "type": type(exc).__name__,
            },
            "failure_stage": execution_stage,
            "failure_diagnostics": {
                "cli": failure_cli_diagnostic,
                "runtime": failure_runtime_diagnostic,
                "runtime_collection_error_type": failure_runtime_diagnostic_error_type,
            },
            "identity_provenance": identity_provenance,
            "environment": {"source_name": env_source, "loaded_key_names": sorted(loaded_keys), "openai_api_key_present": True, "model": model, "secret_values_persisted": False},
        }
    finally:
        mcp_http_factory.strict_remote_http_client_factory = original_factory
        if previous_org_bearer is None: os.environ.pop("OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER", None)
        else: os.environ["OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"] = previous_org_bearer
        if previous_groupware_bearer is None: os.environ.pop("OKCANVAS_GROUPWARE_READ_BEARER", None)
        else: os.environ["OKCANVAS_GROUPWARE_READ_BEARER"] = previous_groupware_bearer
        for server in (runtime_server, groupware_connector_server, org_connector_server):
            if server is not None:
                try: server.stop()
                except BaseException as exc: cleanup_error_types.append(type(exc).__name__)
        for process in (groupware_fake_process, org_fake_process):
            if process is not None:
                try:
                    if process.poll() is None:
                        process.terminate()
                        try: process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill(); process.wait(timeout=5)
                except BaseException as exc: cleanup_error_types.append(type(exc).__name__)
                finally: close_process_pipes(process)
        removed, removal_errors = remove_temp_tree(temp)
        transient_removal_error_types.extend(removal_errors)
        cleanup_completed = removed and not cleanup_error_types

    assert payload is not None
    checks = dict(payload.get("checks") or {})
    checks["harness_cleanup_completed"] = cleanup_completed
    payload["checks"] = checks
    payload["passed_checks"] = sum(v is True for v in checks.values())
    payload["total_checks"] = len(checks)
    payload["state"] = "PASSED" if payload.get("state") == "PASSED" and all(checks.values()) else "FAILED"
    payload["cleanup"] = {"completed": cleanup_completed, "cleanup_error_types": cleanup_error_types, "transient_removal_error_types": transient_removal_error_types}
    public = redact(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", secrets)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(public, encoding="utf-8")
    return json.loads(public)


def main() -> int:
    parser = argparse.ArgumentParser(description="STEP094 cross-domain stable-focus Windows Live OpenAI acceptance")
    parser.add_argument("--output", default=str(OUTPUT_DEFAULT))
    args = parser.parse_args()
    payload = asyncio.run(execute(Path(args.output).resolve()))
    print(json.dumps({"state": payload.get("state"), "passed_checks": payload.get("passed_checks"), "total_checks": payload.get("total_checks"), "output": str(Path(args.output).resolve())}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("state") == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
