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
from okcanvas_agent_runtime.core.baseline import (
    CURRENT_STEP as EXECUTABLE_RUNTIME_STEP,
    PROJECT_VERSION as EXECUTABLE_RUNTIME_VERSION,
)

CURRENT = load_current_baseline(ROOT)
STEP = CURRENT.workspace_step
VERSION = CURRENT.workspace_version
RUNTIME_STEP = CURRENT.runtime_step
RUNTIME_VERSION = CURRENT.runtime_version
LIVE_GATE = "OKCANVAS_WORKSPACE_STEP008R4R12R3_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE"
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP008R4R12R3_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE.json"
ORG_EXAMPLE_ROOT = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"
GROUPWARE_EXAMPLE_ROOT = ROOT / "okcanvas-connector-examples/groupware/groupware-api-fake"
GROUPWARE_EXAMPLE_API_TOKEN = "example-groupware-api-token"
ROOT_AGENT_ID = "organization-assistant-session-agent"
ORG_CHILD_ID = "organization-context-read-agent"
GROUPWARE_CHILD_ID = "groupware-read-agent"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _redacted_json_text(payload: dict[str, object], secrets: list[str]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return redact(serialized, secrets)


def _identity_provenance() -> tuple[dict[str, object], dict[str, bool]]:
    baseline_path = ROOT / "specs/workspace/current-baseline.json"
    catalog_path = ROOT / "specs/workspace/project-catalog.json"
    pyproject_path = RUNTIME_ROOT / "pyproject.toml"
    runtime_baseline_path = RUNTIME_ROOT / "okcanvas_agent_runtime/core/baseline.py"
    harness_path = Path(__file__).resolve()
    entrypoint_path = ROOT / "scripts/run_workspace_step008r4r12r3_grounded_structured_delegation_live_entrypoint.py"
    launcher_path = ROOT / "sh_run_workspace_step008r4r12r3_grounded_structured_delegation_live_acceptance.cmd"

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
        "focused_live_entrypoint_present": entrypoint_path.is_file(),
        "focused_live_launcher_present": launcher_path.is_file(),
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
        "focused_live_harness": {"sha256": _sha256_file(harness_path)},
        "focused_live_entrypoint": {"sha256": _sha256_file(entrypoint_path)} if entrypoint_path.is_file() else None,
        "focused_live_launcher": {"sha256": _sha256_file(launcher_path)} if launcher_path.is_file() else None,
        "runtime_service": None,
    }
    return provenance, checks


# Eight acceptance scenarios. The cross-domain scenario has one fixture turn that is not itself counted
# as a scenario; it exists only to create one server-evidenced stable employee focus.
SCENARIOS: tuple[dict[str, object], ...] = (
    {
        "case_id": "short-contact-natural-variation",
        "prompt": "김민수 연락처 알려줘",
        "expected_mode": "ORG_AMBIGUOUS",
        "expected_target_surface": "김민수",
    },
    {
        "case_id": "short-phone-natural-variation",
        "prompt": "김민수 전화번호 좀 알려줘",
        "expected_mode": "ORG_AMBIGUOUS",
        "expected_target_surface": "김민수",
    },
    {
        "case_id": "hanbit-account-manager-grounded-ambiguity",
        "prompt": "한빛 담당자",
        "expected_mode": "ORG_AMBIGUOUS",
        "expected_target_surface": "한빛",
    },
    {
        "case_id": "stable-focus-calendar-cross-domain",
        "prompt": "그 사람 일정 알려줘",
        "expected_mode": "GROUPWARE_FOCUS_CALENDAR",
        "fixture_prompt": "플랫폼팀 김민수 선임 연락처 알려줘",
    },
    {
        "case_id": "code-overroute-no-specialist",
        "prompt": "제품 코드 리뷰해줘",
        "expected_mode": "DIRECT_NO_SPECIALIST",
    },
    {
        "case_id": "web-overroute-no-specialist",
        "prompt": "OpenAI 정책 최신 내용 검색해줘",
        "expected_mode": "DIRECT_NO_SPECIALIST",
    },
    {
        "case_id": "write-shaped-calendar-delete-no-read-child",
        "prompt": "그 사람 일정 삭제해줘",
        "expected_mode": "DIRECT_NO_SPECIALIST",
        "fixture_prompt": "플랫폼팀 김민수 선임 연락처 알려줘",
    },
    {
        "case_id": "greeting-no-specialist",
        "prompt": "안녕하세요",
        "expected_mode": "DIRECT_NO_SPECIALIST",
    },
)


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    value = int(sock.getsockname()[1])
    sock.close()
    return value


def _start_example(
    *, source: Path, target: Path, npm: str, node: str,
    environment: dict[str, str], secrets: list[str],
) -> tuple[subprocess.Popen[bytes], str]:
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


def _route_grounded_shadow_exact(route: dict[str, object]) -> bool:
    shadow = route.get("grounded_interpretation_shadow")
    return (
        route.get("selected_agent_definition_id") == ROOT_AGENT_ID
        and isinstance(shadow, dict)
        and shadow.get("schema_version") == "okcanvas-assistant-route-v3"
        and shadow.get("interpretation_mode") == "LLM_GROUNDED"
        and shadow.get("authoritative") is False
        and shadow.get("selected_agent_definition_id") == ROOT_AGENT_ID
    )


def _agent_tool_events(run: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    return {
        "requested": event_payloads(run, "agent.tool.requested"),
        "admitted": event_payloads(run, "agent.tool.admitted"),
        "denied": event_payloads(run, "agent.tool.admission.denied"),
        "started": event_payloads(run, "agent.tool.started"),
        "normalized": event_payloads(run, "agent.tool.output.normalized"),
        "mcp_started": event_payloads(run, "tool.started"),
        "run_failed": event_payloads(run, "run.failed"),
    }


def _one_child_exact(run: dict[str, object], *, child_id: str, mcp_tool: str) -> tuple[bool, dict[str, object]]:
    events = _agent_tool_events(run)
    requested = events["requested"]
    admitted = events["admitted"]
    started = events["started"]
    mcp_started = events["mcp_started"]
    exact = (
        len(requested) == len(admitted) == len(started) == 1
        and not events["denied"]
        and not events["run_failed"]
        and requested[0].get("from_agent_id") == ROOT_AGENT_ID
        and requested[0].get("to_agent_id") == child_id
        and requested[0].get("arguments_persisted") is False
        and admitted[0].get("from_agent_id") == ROOT_AGENT_ID
        and admitted[0].get("to_agent_id") == child_id
        and admitted[0].get("side_effect") == "READ"
        and admitted[0].get("stable_ids_from_model_accepted") is False
        and admitted[0].get("selected_child_mcp_connected") is True
        and started[0].get("from_agent_id") == ROOT_AGENT_ID
        and started[0].get("to_agent_id") == child_id
        and started[0].get("input_mode") == "STRUCTURED_MODEL_INTERPRETATION"
        and len(mcp_started) == 1
        and mcp_started[0].get("tool_name") == mcp_tool
    )
    return exact, events


def _direct_no_specialist_exact(run: dict[str, object]) -> tuple[bool, dict[str, object]]:
    events = _agent_tool_events(run)
    exact = (
        not events["requested"]
        and not events["admitted"]
        and not events["denied"]
        and not events["started"]
        and not events["mcp_started"]
        and not events["normalized"]
        and not events["run_failed"]
    )
    return exact, events


def _artifact_content(run: dict[str, object]) -> dict[str, object]:
    artifact = run.get("artifact")
    if not isinstance(artifact, dict):
        return {}
    content = artifact.get("content")
    return dict(content) if isinstance(content, dict) else {}


def _ambiguous_normalization_exact(run: dict[str, object], *, entity_type: str, minimum_candidates: int) -> bool:
    normalizations = event_payloads(run, "agent.tool.output.normalized")
    if len(normalizations) != 1:
        return False
    item = normalizations[0]
    focus = item.get("session_context_focus")
    if not isinstance(focus, dict) or focus.get("state") != "AMBIGUOUS":
        return False
    candidates = focus.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < minimum_candidates:
        return False
    return (
        item.get("tool_name") == "resolve_organization_context"
        and item.get("ambiguous") is True
        and item.get("clarification_applied") is True
        and item.get("model_output_persisted") is False
        and item.get("tool_result_persisted") is False
        and all(isinstance(candidate, dict) and candidate.get("entity_type") == entity_type for candidate in candidates)
    )


def _resolved_employee_focus_exact(run: dict[str, object]) -> bool:
    normalizations = event_payloads(run, "agent.tool.output.normalized")
    if len(normalizations) != 1:
        return False
    focus = normalizations[0].get("session_context_focus")
    if not isinstance(focus, dict) or focus.get("state") != "RESOLVED":
        return False
    candidates = focus.get("candidates")
    return (
        isinstance(candidates, list)
        and len(candidates) == 1
        and isinstance(candidates[0], dict)
        and candidates[0].get("entity_type") == "EMPLOYEE"
        and candidates[0].get("entity_id") == "employee-0017"
    )


def _calendar_focus_normalization_exact(run: dict[str, object]) -> bool:
    normalizations = event_payloads(run, "agent.tool.output.normalized")
    if len(normalizations) != 1:
        return False
    item = normalizations[0]
    return (
        item.get("strategy") == "groupware-cross-domain-stable-context-filter-v1"
        and item.get("tool_name") == "list_calendar_events"
        and item.get("context_entity_type") == "EMPLOYEE"
        and item.get("context_entity_id") == "employee-0017"
        and item.get("context_filter_applied") is True
        and item.get("model_output_persisted") is False
        and item.get("tool_result_persisted") is False
    )


def _hint_requests_exact(requests: list[dict[str, object]], prompt: str) -> bool:
    expected_paths = ["/api/v1/context/search", "/api/v1/glossary/search"]
    hints = [item for item in requests if item.get("path") in set(expected_paths)]
    if [item.get("path") for item in hints[:2]] != expected_paths:
        # Server request ordering follows Context then Glossary in the Product provider.
        return False
    if len(hints) != 2:
        return False
    for item in hints:
        body = item.get("body")
        if not isinstance(body, dict) or body.get("query") != prompt:
            return False
        if item.get("authorization_present") is not True or item.get("authorization_value_recorded") is not False:
            return False
    return True


def _org_execution_request(requests: list[dict[str, object]]) -> dict[str, object] | None:
    matches = [item for item in requests if item.get("path") == "/api/v1/context/resolve"]
    return dict(matches[0]) if len(matches) == 1 else None


def _safe_case_summary(case: dict[str, object], route: dict[str, object], run: dict[str, object], exact: bool) -> dict[str, object]:
    events = _agent_tool_events(run)
    return {
        "case_id": case["case_id"],
        "prompt": case["prompt"],
        "expected_mode": case["expected_mode"],
        "exact": exact,
        "route": {
            "status": route.get("status"),
            "request_class": route.get("request_class"),
            "side_effect": route.get("side_effect"),
            "matched_rule_id": route.get("matched_rule_id"),
            "selected_agent_definition_id": route.get("selected_agent_definition_id"),
            "grounded_interpretation_shadow": route.get("grounded_interpretation_shadow"),
        },
        "run_id": (run.get("run") or {}).get("run_id") if isinstance(run.get("run"), dict) else None,
        "run_status": (run.get("run") or {}).get("status") if isinstance(run.get("run"), dict) else None,
        "agent_tool_requested_to": [item.get("to_agent_id") for item in events["requested"]],
        "agent_tool_admitted_to": [item.get("to_agent_id") for item in events["admitted"]],
        "agent_tool_denied_to": [item.get("to_agent_id") for item in events["denied"]],
        "mcp_tool_names": [item.get("tool_name") for item in events["mcp_started"]],
        "normalization_strategies": [item.get("strategy") or item.get("normalization_strategy") for item in events["normalized"]],
        "final_output": _artifact_content(run),
    }


async def execute(output: Path) -> dict[str, object]:
    started = now()
    env_source = os.environ.get(ENV_SOURCE_NAME, "")
    loaded_keys = {item for item in os.environ.get(ENV_LOADED_KEYS, "").split(",") if item}
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OKCANVAS_AGENT_MODEL", "").strip()
    identity_provenance, identity_checks = _identity_provenance()
    preflight = {
        "explicit_grounded_structured_delegation_live_gate": os.environ.get(LIVE_GATE) == "1",
        "environment_file_loaded": env_source in {".env.local", ".env.local.cmd"},
        "openai_key_loaded_from_environment_file": "OPENAI_API_KEY" in loaded_keys and bool(api_key),
        "model_loaded_from_environment_file": "OKCANVAS_AGENT_MODEL" in loaded_keys and bool(model),
        "model_name_safe": bool(model) and len(model) <= 200 and "\r" not in model and "\n" not in model,
        **identity_checks,
    }
    if not all(preflight.values()):
        payload = {
            "schema_version": "okcanvas-workspace-step008r4r12r3-grounded-structured-delegation-live-acceptance-v1",
            "step": STEP,
            "version": VERSION,
            "runtime_step": RUNTIME_STEP,
            "runtime_version": RUNTIME_VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_GROUNDED_HINT_STRUCTURED_DELEGATION_ADMISSION_E2E",
            "state": "FAILED",
            "started_at": started,
            "completed_at": now(),
            "checks": preflight,
            "passed_checks": sum(v is True for v in preflight.values()),
            "total_checks": len(preflight),
            "safe_error": {
                "category": "LIVE_IDENTITY_PROVENANCE_MISMATCH" if not all(identity_checks.values()) else "LIVE_ENVIRONMENT_NOT_READY",
                "type": "IdentityProvenanceFailure" if not all(identity_checks.values()) else "PreflightFailure",
            },
            "identity_provenance": identity_provenance,
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

    external_token = random_secret("step096br1-service")
    org_connector_token = random_secret("step096br1-org-connector")
    groupware_connector_token = random_secret("step096br1-groupware-connector")
    admin_key = random_secret("step096br1-admin")
    submitter_key = random_secret("step096br1-submitter")
    payload_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    session_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    secrets = [
        api_key, external_token, org_connector_token, groupware_connector_token,
        EXAMPLE_ORGANIZATION_CONTEXT_API_TOKEN, GROUPWARE_EXAMPLE_API_TOKEN,
        admin_key, submitter_key, payload_key, session_key,
    ]
    node = resolve_executable("node")
    npm = resolve_executable("npm")
    temp = Path(tempfile.mkdtemp(prefix="okcanvas-workspace-step096br1-live-"))
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

    async def fake_requests(base_url: str) -> list[dict[str, object]]:
        async with httpx.AsyncClient(base_url=base_url, trust_env=False) as client:
            response = await client.get("/_fake/requests")
            response.raise_for_status()
            raw = response.json().get("requests", [])
            return [dict(item) for item in raw if isinstance(item, dict)]

    async def create_session(auth_headers: dict[str, str]) -> tuple[str, dict[str, object]]:
        assert runtime_server is not None
        async with httpx.AsyncClient(base_url=runtime_server.base_url, headers=auth_headers, trust_env=False) as client:
            response = await client.post("/v1/service/sessions", json={"agent_definition_id": ROOT_AGENT_ID})
            response.raise_for_status()
            created = response.json()
        return str(created["session_id"]), created

    async def execute_turn(
        *, prompt: str, session_id: str, auth_headers: dict[str, str], environment: dict[str, str],
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
        assert runtime_server is not None
        org_before = len(await fake_requests(org_fake_base))
        groupware_before = len(await fake_requests(groupware_fake_base))
        evidence_before = await collect_runtime_evidence(runtime_server.base_url, external_token)
        run_count_before = len(list(evidence_before["runs"]))
        async with httpx.AsyncClient(base_url=runtime_server.base_url, headers=auth_headers, trust_env=False) as client:
            route_response = await client.post("/v1/service/assistant/routes", json={"input": prompt, "session_id": session_id})
            route_response.raise_for_status()
            route = route_response.json()
        prompt_file = temp / f"prompt-{session_id[-8:]}-{run_count_before + 1}.txt"
        prompt_file.write_text(f"{prompt}\n/quit\n", encoding="utf-8")
        cli_env = dict(environment)
        cli_env["PYTHONUTF8"] = "1"
        cli = run_command(node, [
            "src/cli.mjs", "--base-url", runtime_server.base_url, "--bearer", external_token,
            "--model", model, "--session-id", session_id, "--script", str(prompt_file), "--yes", "--debug",
        ], cwd=CLI_ROOT, env=cli_env, secrets=secrets)
        nonlocal failure_cli_diagnostic, failure_runtime_diagnostic
        failure_cli_diagnostic = {
            "returncode": cli["returncode"],
            "one_request_completed": "1개 요청 완료" in str(cli["stdout"]),
            "stdout": cli["stdout"],
            "stderr": cli["stderr"],
            "command": cli["command"],
        }
        evidence_after = await collect_runtime_evidence(runtime_server.base_url, external_token)
        runs = list(evidence_after["runs"])
        failure_runtime_diagnostic = {
            "run_count": len(runs),
            "runs": [
                {
                    "run": dict(item.get("run") or {}),
                    "event_types": [str(event.get("event_type")) for event in list(item.get("events") or [])],
                    "agent_tool_requested": event_payloads(item, "agent.tool.requested"),
                    "agent_tool_admitted": event_payloads(item, "agent.tool.admitted"),
                    "agent_tool_denied": event_payloads(item, "agent.tool.admission.denied"),
                    "mcp_tool_names": [str(x.get("tool_name")) for x in event_payloads(item, "tool.started")],
                    "run_failed": event_payloads(item, "run.failed"),
                }
                for item in runs
            ],
        }
        if cli["returncode"] != 0:
            raise RuntimeError("Product CLI process failed")
        if not failure_cli_diagnostic["one_request_completed"]:
            raise RuntimeError("Product CLI request did not complete")
        if len(runs) != run_count_before + 1:
            raise RuntimeError(f"Expected exactly one new Runtime Run, before={run_count_before}, after={len(runs)}")
        run = runs[-1]
        if (run.get("run") or {}).get("status") != "SUCCEEDED":
            raise RuntimeError("Runtime Run did not succeed")
        org_after = await fake_requests(org_fake_base)
        groupware_after = await fake_requests(groupware_fake_base)
        org_delta = org_after[org_before:]
        groupware_delta = groupware_after[groupware_before:]
        return route, run, failure_cli_diagnostic, org_delta, groupware_delta

    try:
        environment = dict(os.environ)
        execution_stage = "prepare_examples"
        org_fake_process, org_fake_base = _start_example(
            source=ORG_EXAMPLE_ROOT,
            target=temp / "organization-context-api-fake",
            npm=npm,
            node=node,
            environment=environment,
            secrets=secrets,
        )
        groupware_fake_process, groupware_fake_base = _start_example(
            source=GROUPWARE_EXAMPLE_ROOT,
            target=temp / "groupware-api-fake",
            npm=npm,
            node=node,
            environment=environment,
            secrets=secrets,
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
                http_timeout_seconds=3,
                max_retry_attempts=0,
            )),
            ssl_certfile=cert_path,
            ssl_keyfile=key_path,
            hostname="localhost",
        )
        org_connector_server.start()
        await wait_http(org_connector_server.base_url, "/healthz", verify=str(ca_path))

        groupware_connector_server = LiveASGIServer(
            create_groupware_connector_app(GroupwareConnectorSettings(
                connector_bearer=groupware_connector_token,
                groupware_base_url=groupware_fake_base,
                groupware_api_bearer=GROUPWARE_EXAMPLE_API_TOKEN,
                http_timeout_seconds=3,
                max_retry_attempts=0,
            )),
            ssl_certfile=cert_path,
            ssl_keyfile=key_path,
            hostname="localhost",
        )
        groupware_connector_server.start()
        await wait_http(groupware_connector_server.base_url, "/healthz", verify=str(ca_path))

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
        os.environ["OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"] = org_connector_token
        os.environ["OKCANVAS_GROUPWARE_READ_BEARER"] = groupware_connector_token

        runtime_project = temp / "runtime-project"
        shutil.copytree(RUNTIME_ROOT / "specs", runtime_project / "specs")
        shutil.copytree(RUNTIME_ROOT / "reference", runtime_project / "reference")
        org_url = f"{org_connector_server.base_url}/tenants/{{tenant_id}}/mcp"
        for relative in (
            "specs/mcp/servers/organization-context-read/server.json",
            "specs/mcp/servers/organization-context-interpretation-hints/server.json",
        ):
            path = runtime_project / relative
            data = json.loads(path.read_text(encoding="utf-8"))
            data["url_template"] = org_url
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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

        case_summaries: list[dict[str, object]] = []
        case_checks: list[bool] = []
        total_turn_count = 0
        dedicated_sessions: list[dict[str, object]] = []

        for case in SCENARIOS:
            execution_stage = f"session_{case['case_id']}"
            session_id, created = await create_session(auth_headers)
            dedicated_sessions.append(created)

            fixture_prompt = case.get("fixture_prompt")
            fixture_summary: dict[str, object] | None = None
            if isinstance(fixture_prompt, str):
                execution_stage = f"fixture_{case['case_id']}"
                route, run, cli, org_delta, groupware_delta = await execute_turn(
                    prompt=fixture_prompt,
                    session_id=session_id,
                    auth_headers=auth_headers,
                    environment=environment,
                )
                total_turn_count += 1
                child_exact, child_events = _one_child_exact(
                    run, child_id=ORG_CHILD_ID, mcp_tool="resolve_organization_context"
                )
                fixture_exact = (
                    _route_grounded_shadow_exact(route)
                    and child_exact
                    and _resolved_employee_focus_exact(run)
                    and _hint_requests_exact(org_delta, fixture_prompt)
                    and not groupware_delta
                )
                fixture_summary = {
                    "prompt": fixture_prompt,
                    "exact": fixture_exact,
                    "route": {
                        "status": route.get("status"),
                        "matched_rule_id": route.get("matched_rule_id"),
                        "grounded_interpretation_shadow": route.get("grounded_interpretation_shadow"),
                    },
                    "agent_tool_requested_to": [item.get("to_agent_id") for item in child_events["requested"]],
                    "mcp_tool_names": [item.get("tool_name") for item in child_events["mcp_started"]],
                }
                if not fixture_exact:
                    raise RuntimeError(f"Stable-focus fixture failed for {case['case_id']}")

            execution_stage = f"case_{case['case_id']}"
            route, run, cli, org_delta, groupware_delta = await execute_turn(
                prompt=str(case["prompt"]),
                session_id=session_id,
                auth_headers=auth_headers,
                environment=environment,
            )
            total_turn_count += 1
            route_exact = _route_grounded_shadow_exact(route)
            hints_exact = _hint_requests_exact(org_delta, str(case["prompt"]))
            mode = str(case["expected_mode"])
            case_exact = False

            if mode == "ORG_AMBIGUOUS":
                child_exact, _events = _one_child_exact(
                    run, child_id=ORG_CHILD_ID, mcp_tool="resolve_organization_context"
                )
                expected_type = "CLIENT" if case["case_id"] == "hanbit-account-manager-grounded-ambiguity" else "EMPLOYEE"
                minimum_candidates = 4 if expected_type == "CLIENT" else 2
                execution_request = _org_execution_request(org_delta)
                body = execution_request.get("body") if isinstance(execution_request, dict) else None
                expected_surface = str(case.get("expected_target_surface") or "")
                execution_surface_exact = (
                    isinstance(body, dict)
                    and body.get("query") == expected_surface
                    and expected_type in list(body.get("entity_types") or [])
                    and not str(body.get("query") or "").startswith(("employee-", "client-"))
                )
                case_exact = (
                    route_exact
                    and hints_exact
                    and child_exact
                    and execution_surface_exact
                    and _ambiguous_normalization_exact(
                        run, entity_type=expected_type, minimum_candidates=minimum_candidates
                    )
                    and not groupware_delta
                )
            elif mode == "GROUPWARE_FOCUS_CALENDAR":
                child_exact, _events = _one_child_exact(
                    run, child_id=GROUPWARE_CHILD_ID, mcp_tool="list_calendar_events"
                )
                body = groupware_delta[0].get("body") if len(groupware_delta) == 1 else None
                case_exact = (
                    route_exact
                    and hints_exact
                    and child_exact
                    and _calendar_focus_normalization_exact(run)
                    and len(groupware_delta) == 1
                    and groupware_delta[0].get("path") == "/api/v1/calendar/events/list"
                    and isinstance(body, dict)
                    and body.get("context_ref") == {"entity_type": "EMPLOYEE", "entity_id": "employee-0017"}
                    and body.get("limit") == 20
                )
            elif mode == "DIRECT_NO_SPECIALIST":
                direct_exact, _events = _direct_no_specialist_exact(run)
                # Hint-plane traffic is allowed and required; execution-specialist traffic is forbidden.
                execution_org_paths = [
                    item.get("path") for item in org_delta
                    if item.get("path") not in {"/api/v1/context/search", "/api/v1/glossary/search"}
                ]
                content = _artifact_content(run)
                delete_semantics_exact = True
                if case["case_id"] == "write-shaped-calendar-delete-no-read-child":
                    delete_semantics_exact = (
                        content.get("side_effect") != "READ"
                        and content.get("status") in {"ACTION_PROPOSED", "NEEDS_CAPABILITY", "NEEDS_CLARIFICATION", "REFUSED"}
                    )
                case_exact = (
                    route_exact
                    and hints_exact
                    and direct_exact
                    and not execution_org_paths
                    and not groupware_delta
                    and delete_semantics_exact
                )
            else:
                raise RuntimeError(f"Unknown case mode: {mode}")

            case_checks.append(case_exact)
            summary = _safe_case_summary(case, route, run, case_exact)
            summary["fixture"] = fixture_summary
            summary["hint_requests_exact"] = hints_exact
            summary["organization_api_paths"] = [item.get("path") for item in org_delta]
            summary["groupware_api_paths"] = [item.get("path") for item in groupware_delta]
            case_summaries.append(summary)

        execution_stage = "collect_final_evidence"
        evidence = await collect_runtime_evidence(runtime_server.base_url, external_token)
        runs = list(evidence["runs"])
        public_surface = json.dumps(
            {"cases": case_summaries, "runtime_run_count": len(runs)},
            ensure_ascii=False,
            default=str,
        )
        checks = {
            **preflight,
            "harness_execution_completed_without_exception": True,
            "eight_dedicated_scenario_sessions_created": (
                len(dedicated_sessions) == len(SCENARIOS)
                and all(item.get("agent_definition_id") == ROOT_AGENT_ID for item in dedicated_sessions)
            ),
            "ten_runtime_turns_created_for_eight_scenarios_plus_two_focus_fixtures": len(runs) == total_turn_count == 10,
            "all_runtime_runs_succeeded": len(runs) == total_turn_count and all((item.get("run") or {}).get("status") == "SUCCEEDED" for item in runs),
            "all_eight_grounded_scenarios_exact": len(case_checks) == 8 and all(case_checks),
            "natural_language_variations_select_organization_child": all(
                next(item for item in case_summaries if item["case_id"] == case_id)["exact"] is True
                for case_id in ("short-contact-natural-variation", "short-phone-natural-variation")
            ),
            "hanbit_account_manager_preserves_client_ambiguity": next(
                item for item in case_summaries if item["case_id"] == "hanbit-account-manager-grounded-ambiguity"
            )["exact"] is True,
            "stable_focus_cross_domain_calendar_uses_runtime_context_ref": next(
                item for item in case_summaries if item["case_id"] == "stable-focus-calendar-cross-domain"
            )["exact"] is True,
            "legacy_overroute_phrases_do_not_invoke_specialists": all(
                next(item for item in case_summaries if item["case_id"] == case_id)["exact"] is True
                for case_id in ("code-overroute-no-specialist", "web-overroute-no-specialist")
            ),
            "write_shaped_delete_is_not_downgraded_to_read_child": next(
                item for item in case_summaries if item["case_id"] == "write-shaped-calendar-delete-no-read-child"
            )["exact"] is True,
            "greeting_does_not_invoke_specialist": next(
                item for item in case_summaries if item["case_id"] == "greeting-no-specialist"
            )["exact"] is True,
            "secrets_absent_from_evidence": all(secret not in public_surface for secret in secrets),
        }
        payload = {
            "schema_version": "okcanvas-workspace-step008r4r12r3-grounded-structured-delegation-live-acceptance-v1",
            "step": STEP,
            "version": VERSION,
            "runtime_step": RUNTIME_STEP,
            "runtime_version": RUNTIME_VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_GROUNDED_HINT_STRUCTURED_DELEGATION_ADMISSION_E2E",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "started_at": started,
            "completed_at": now(),
            "checks": checks,
            "passed_checks": sum(v is True for v in checks.values()),
            "total_checks": len(checks),
            "scenario_count": len(SCENARIOS),
            "runtime_turn_count": total_turn_count,
            "case_summaries": case_summaries,
            "identity_provenance": identity_provenance,
            "environment": {
                "source_name": env_source,
                "loaded_key_names": sorted(loaded_keys),
                "openai_api_key_present": True,
                "model": model,
                "secret_values_persisted": False,
            },
            "limitations": {
                "production_organization_database_called": False,
                "production_groupware_called": False,
                "object_storage_live_executed": False,
                "write_capability_executed": False,
                "compound_multi_child_executed": False,
            },
        }
    except BaseException as exc:
        payload = {
            "schema_version": "okcanvas-workspace-step008r4r12r3-grounded-structured-delegation-live-acceptance-v1",
            "step": STEP,
            "version": VERSION,
            "runtime_step": RUNTIME_STEP,
            "runtime_version": RUNTIME_VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_GROUNDED_HINT_STRUCTURED_DELEGATION_ADMISSION_E2E",
            "state": "FAILED",
            "started_at": started,
            "completed_at": now(),
            "checks": {**preflight, "harness_execution_completed_without_exception": False},
            "passed_checks": sum(v is True for v in preflight.values()),
            "total_checks": len(preflight) + 1,
            "safe_error": {
                "category": "LIVE_IDENTITY_PROVENANCE_MISMATCH" if execution_stage == "verify_runtime_identity" else safe_failure_category(exc),
                "type": type(exc).__name__,
            },
            "failure_stage": execution_stage,
            "failure_diagnostics": {
                "cli": failure_cli_diagnostic,
                "runtime": failure_runtime_diagnostic,
            },
            "identity_provenance": identity_provenance,
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
        if previous_org_bearer is None:
            os.environ.pop("OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER", None)
        else:
            os.environ["OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"] = previous_org_bearer
        if previous_groupware_bearer is None:
            os.environ.pop("OKCANVAS_GROUPWARE_READ_BEARER", None)
        else:
            os.environ["OKCANVAS_GROUPWARE_READ_BEARER"] = previous_groupware_bearer
        for server in (runtime_server, groupware_connector_server, org_connector_server):
            if server is not None:
                try:
                    server.stop()
                except Exception as exc:
                    cleanup_error_types.append(type(exc).__name__)
        for process in (groupware_fake_process, org_fake_process):
            if process is not None:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except Exception as exc:
                    cleanup_error_types.append(type(exc).__name__)
                    try:
                        process.kill()
                    except Exception:
                        pass
                close_process_pipes(process)
        try:
            remove_temp_tree(temp, retry_error_types=transient_removal_error_types)
        except Exception as exc:
            cleanup_error_types.append(type(exc).__name__)
        cleanup_completed = not cleanup_error_types

    assert payload is not None
    checks = dict(payload.get("checks") or {})
    checks["harness_cleanup_completed"] = cleanup_completed
    payload["checks"] = checks
    payload["passed_checks"] = sum(v is True for v in checks.values())
    payload["total_checks"] = len(checks)
    payload["state"] = "PASSED" if payload.get("state") == "PASSED" and all(checks.values()) else "FAILED"
    payload["cleanup"] = {
        "completed": cleanup_completed,
        "error_types": cleanup_error_types,
        "transient_removal_error_types": transient_removal_error_types,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        _redacted_json_text(payload, secrets) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run STEP096BR1 focused grounded structured-delegation Windows/OpenAI Live acceptance")
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    payload = asyncio.run(execute(args.output.resolve()))
    print(json.dumps({
        "state": payload.get("state"),
        "passed_checks": payload.get("passed_checks"),
        "total_checks": payload.get("total_checks"),
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("state") == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
