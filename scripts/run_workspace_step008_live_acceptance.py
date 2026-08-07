from __future__ import annotations

import argparse
import asyncio
import base64
import gc
import hashlib
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "okcanvas-agent-runtime"
CONNECTOR_ROOT = ROOT / "okcanvas-connectors/organization-context-mcp-server"
EXAMPLE_ROOT = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"
CLI_ROOT = ROOT / "okcanvas-agent-cli"
SCRIPTS = ROOT / "scripts"
for path in (RUNTIME_ROOT, CONNECTOR_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import httpx
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from organization_context_mcp_server.app import create_app as create_connector_app
from organization_context_mcp_server.config import Settings as ConnectorSettings
from okcanvas_agent_runtime.adapters.mcp.clients import openai_factory as mcp_http_factory
from okcanvas_agent_runtime.control_api import create_app as create_runtime_app
from current_workspace_baseline import load_current_baseline
from workspace_process import decode_process_output, prepare_invocation, resolve_executable, write_json_stdout

CURRENT = load_current_baseline(ROOT)
STEP = CURRENT.workspace_step
VERSION = CURRENT.workspace_version
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP008_LIVE_ACCEPTANCE.json"
LIVE_GATE = "OKCANVAS_WORKSPACE_STEP008_LIVE_ACCEPTANCE"
EXAMPLE_ORGANIZATION_CONTEXT_API_TOKEN = "example-organization-context-api-token"
ENV_SOURCE_NAME = "OKCANVAS_LOCAL_ENV_SOURCE_NAME"
ENV_LOADED_KEYS = "OKCANVAS_LOCAL_ENV_LOADED_KEYS"

SHORT_EXPRESSION_CASES: tuple[dict[str, object], ...] = (
    {
        "case_id": "same-name-detail",
        "prompt": "김민수 정보",
        "pattern_id": "organization-context-entity-detail-short-v1",
        "intent": "ENTITY_DETAIL_LOOKUP",
        "target_expression": "김민수",
        "entity_type_hints": [],
        "requested_fields": ["DETAIL"],
        "preferred_operation": "RESOLVE",
        "tool_name": "resolve_organization_context",
        "connector_path": "/api/v1/context/resolve",
        "expected_output": "AMBIGUOUS",
    },
    {
        "case_id": "alias-contact",
        "prompt": "김선임 연락처",
        "pattern_id": "organization-context-contact-field-short-v1",
        "intent": "ENTITY_FIELD_LOOKUP",
        "target_expression": "김선임",
        "entity_type_hints": [],
        "requested_fields": ["CONTACT"],
        "preferred_operation": "RESOLVE",
        "tool_name": "resolve_organization_context",
        "connector_path": "/api/v1/context/resolve",
        "expected_output": "EMPLOYEE_0017_CONTACT",
    },
    {
        "case_id": "same-name-position",
        "prompt": "김민수 직책",
        "pattern_id": "organization-context-position-field-short-v1",
        "intent": "ENTITY_FIELD_LOOKUP",
        "target_expression": "김민수",
        "entity_type_hints": [],
        "requested_fields": ["POSITION"],
        "preferred_operation": "RESOLVE",
        "tool_name": "resolve_organization_context",
        "connector_path": "/api/v1/context/resolve",
        "expected_output": "AMBIGUOUS",
    },
    {
        "case_id": "position-member-list-empty",
        "prompt": "과장들 목록",
        "pattern_id": "organization-context-position-members-short-v1",
        "intent": "ENTITY_LIST_BY_POSITION",
        "target_expression": "과장",
        "entity_type_hints": ["POSITION", "EMPLOYEE"],
        "requested_fields": ["MEMBERS"],
        "preferred_operation": "SEARCH",
        "tool_name": "search_organization_context",
        "connector_path": "/api/v1/context/search",
        "expected_output": "NO_MATCH",
    },
)


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def registry_json(external_token: str) -> str:
    return json.dumps(
        {
            "schema_version": "okcanvas-service-client-token-registry-v1",
            "tokens": [
                {
                    "token_id": "step007-live-user",
                    "token_sha256": sha256_text(external_token),
                    "tenant_id": "tenant-a",
                    "principal_id": "user-001",
                    "roles": ["agent-user"],
                }
            ],
        },
        sort_keys=True,
    )


def redact(text: str, secrets: list[str]) -> str:
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


def safe_failure_category(exc: BaseException) -> str:
    name = type(exc).__name__.casefold()
    module = type(exc).__module__.casefold()
    if isinstance(exc, PermissionError):
        return "HARNESS_FILESYSTEM_PERMISSION"
    if ("openai" in module or "agents" in module) and ("authentication" in name or "permission" in name):
        return "OPENAI_AUTHENTICATION_OR_PERMISSION"
    if "ratelimit" in name or "rate_limit" in name:
        return "OPENAI_RATE_LIMIT"
    if "quota" in name:
        return "OPENAI_QUOTA"
    if "timeout" in name:
        return "TIMEOUT"
    if "connect" in name or "network" in name:
        return "NETWORK_OR_CONNECTIVITY"
    if "maxturn" in name:
        return "AGENT_MAX_TURNS"
    if "mcp" in name or "ssl" in name or "certificate" in name:
        return "MCP_OR_TLS"
    if "validation" in name or "output" in name:
        return "MODEL_OUTPUT_CONTRACT"
    return "LIVE_EXECUTION_FAILED"


def random_secret(prefix: str) -> str:
    return prefix + "-" + os.urandom(24).hex()


def run_command(
    executable: str,
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    secrets: list[str],
) -> dict[str, object]:
    invocation, shell = prepare_invocation(executable, args)
    completed = subprocess.run(
        invocation,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=shell,
    )
    stdout_text, stdout_encoding = decode_process_output(completed.stdout)
    stderr_text, stderr_encoding = decode_process_output(completed.stderr)
    stdout = redact(stdout_text, secrets)
    stderr = redact(stderr_text, secrets)
    public_command = [str(part) for part in invocation] if not isinstance(invocation, str) else [invocation]
    for index, value in enumerate(public_command[:-1]):
        if value == "--bearer":
            public_command[index + 1] = "[REDACTED]"
    return {
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_encoding": stdout_encoding,
        "stderr_encoding": stderr_encoding,
        "command": public_command,
    }


class LiveASGIServer:
    def __init__(
        self,
        app: object,
        *,
        ssl_certfile: Path | None = None,
        ssl_keyfile: Path | None = None,
        hostname: str = "127.0.0.1",
    ) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(2048)
        self.port = int(self.socket.getsockname()[1])
        scheme = "https" if ssl_certfile is not None else "http"
        self.base_url = f"{scheme}://{hostname}:{self.port}"
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
            access_log=False,
            lifespan="on",
            ssl_certfile=str(ssl_certfile) if ssl_certfile else None,
            ssl_keyfile=str(ssl_keyfile) if ssl_keyfile else None,
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [self.socket]},
            name=f"uvicorn-step008-{self.port}",
            daemon=True,
        )

    def start(self) -> None:
        self.thread.start()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.server.started:
                return
            if not self.thread.is_alive():
                break
            time.sleep(0.02)
        raise RuntimeError(f"ASGI server failed to start on {self.base_url}")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            self.server.force_exit = True
            self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError(f"ASGI server did not stop on {self.base_url}")
        try:
            self.socket.close()
        except OSError:
            pass


def create_loopback_certificates(target: Path) -> tuple[Path, Path, Path]:
    target.mkdir(parents=True, exist_ok=True)
    now_value = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OKCanvas STEP008 Loopback CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now_value - timedelta(minutes=1))
        .not_valid_after(now_value + timedelta(hours=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                key_cert_sign=True,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_name)
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now_value - timedelta(minutes=1))
        .not_valid_after(now_value + timedelta(hours=2))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_path = target / "ca.pem"
    cert_path = target / "server.pem"
    key_path = target / "server-key.pem"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return ca_path, cert_path, key_path


async def wait_http(
    base_url: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    verify: bool | str = True,
) -> None:
    deadline = time.monotonic() + 15
    async with httpx.AsyncClient(base_url=base_url, trust_env=False, verify=verify) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(path, headers=headers, timeout=0.7)
                if response.status_code < 500:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.05)
    raise RuntimeError(f"HTTP endpoint did not become ready: {base_url}{path}")


async def collect_runtime_evidence(runtime_base_url: str, external_token: str) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {external_token}"}
    async with httpx.AsyncClient(base_url=runtime_base_url, headers=headers, trust_env=False) as client:
        sessions_response = await client.get("/v1/service/sessions?limit=100")
        sessions_response.raise_for_status()
        sessions = sessions_response.json()["sessions"]
        runs_response = await client.get("/v1/service/runs?limit=100")
        runs_response.raise_for_status()
        runs = runs_response.json()["runs"]
        runs = sorted(runs, key=lambda item: (item.get("created_at", ""), item["run_id"]))
        detailed: list[dict[str, object]] = []
        for run in runs:
            run_id = run["run_id"]
            events = (await client.get(f"/v1/service/runs/{run_id}/events")).json()["events"]
            invocations = (await client.get(f"/v1/service/runs/{run_id}/invocations")).json()["invocations"]
            artifacts = (await client.get(f"/v1/service/runs/{run_id}/artifacts")).json()["artifacts"]
            final_meta = next((item for item in artifacts if item["artifact_type"] == "agent.final-output"), None)
            artifact = (
                (await client.get(f"/v1/service/runs/{run_id}/artifacts/{final_meta['artifact_id']}")).json()
                if final_meta is not None
                else {"artifact_type": None, "content": {}}
            )
            detailed.append({"run": run, "events": events, "invocations": invocations, "artifact": artifact})
    return {"sessions": sessions, "runs": detailed}


def event_types(run: dict[str, object]) -> list[str]:
    return [str(item["event_type"]) for item in run["events"]]  # type: ignore[index]


def event_payloads(run: dict[str, object], event_type: str) -> list[dict[str, object]]:
    return [
        dict(item.get("payload") or {})
        for item in run["events"]  # type: ignore[index]
        if item.get("event_type") == event_type
    ]


def empty_search_result_observed(
    *,
    content: dict[str, object],
    citation_refs: list[str],
    unverified: list[str],
    normalizations: list[dict[str, object]],
    expected_tool_name: str,
) -> bool:
    if len(normalizations) != 1:
        return False
    normalization = normalizations[0]
    return (
        content.get("status") == "ANSWERED"
        and not citation_refs
        and not unverified
        and normalization.get("strategy") == "tool-evidence-provenance-alignment-v1"
        and normalization.get("tool_name") == expected_tool_name
        and int(normalization.get("candidate_count") or 0) == 0
        and normalization.get("clarification_applied") is False
        and normalization.get("model_calls_added") == 0
        and normalization.get("tool_reexecuted") is False
    )


def committed_session_turns_observed(
    *,
    session: dict[str, object],
    session_id: str,
    completed_payloads: list[dict[str, object]],
    expected_turn_count: int,
) -> bool:
    return (
        session.get("turn_count") == expected_turn_count
        and len(completed_payloads) == expected_turn_count
        and [payload.get("turn_count") for payload in completed_payloads]
        == list(range(1, expected_turn_count + 1))
        and all(payload.get("session_id") == session_id for payload in completed_payloads)
        and all(int(payload.get("item_count") or 0) > 0 for payload in completed_payloads)
        and all(
            payload.get("history_persisted_in_product_events") is False
            and payload.get("history_persisted_in_product_db") is False
            for payload in completed_payloads
        )
    )


def close_process_pipes(process: subprocess.Popen[bytes]) -> None:
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def remove_temp_tree(path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for attempt in range(6):
        try:
            shutil.rmtree(path)
            return True, errors
        except FileNotFoundError:
            return True, errors
        except OSError as exc:
            errors.append(type(exc).__name__)
            gc.collect()
            time.sleep(0.1 * (attempt + 1))
    return False, errors


async def execute(example_root: Path, output: Path) -> dict[str, object]:
    started = now()
    env_source = os.environ.get(ENV_SOURCE_NAME, "")
    loaded_keys = {item for item in os.environ.get(ENV_LOADED_KEYS, "").split(",") if item}
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OKCANVAS_AGENT_MODEL", "").strip()
    preflight = {
        "explicit_live_gate": os.environ.get(LIVE_GATE) == "1",
        "environment_file_loaded": env_source in {".env.local", ".env.local.cmd"},
        "openai_key_loaded_from_environment_file": "OPENAI_API_KEY" in loaded_keys and bool(api_key),
        "model_loaded_from_environment_file": "OKCANVAS_AGENT_MODEL" in loaded_keys and bool(model),
        "model_name_safe": bool(model) and len(model) <= 200 and "\r" not in model and "\n" not in model,
    }
    if not all(preflight.values()):
        payload = {
            "schema_version": "okcanvas-agent-platform-workspace-step008-live-acceptance-v3",
            "step": STEP,
            "version": VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_ORGANIZATION_CONTEXT_FULL_PROCESS_E2E",
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

    external_token = random_secret("step008-service")
    connector_token = random_secret("step008-connector")
    product_token = EXAMPLE_ORGANIZATION_CONTEXT_API_TOKEN
    admin_key = random_secret("step008-admin")
    submitter_key = random_secret("step008-submitter")
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

    temp = Path(tempfile.mkdtemp(prefix="okcanvas-workspace-step008-live-"))
    execution_stage = "initialize"
    payload: dict[str, object] | None = None
    execution_exception: BaseException | None = None
    cleanup_error_types: list[str] = []
    transient_removal_error_types: list[str] = []
    cleanup_completed = False
    actual_model_call_observed = False
    safe_tool_failures: list[dict[str, object]] = []
    try:
        execution_stage = "prepare_workspace"
        example = temp / "organization-context-api-fake"
        shutil.copytree(example_root, example, ignore=shutil.ignore_patterns("node_modules", "dist", ".pytest_cache"))
        environment = dict(os.environ)
        execution_stage = "prepare_node_example"
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
            if headers is not None: kwargs["headers"] = headers
            if timeout is not None: kwargs["timeout"] = timeout
            if auth is not None: kwargs["auth"] = auth
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

        execution_stage = "preflight_short_expression_routes"
        route_preflight: list[dict[str, object]] = []
        async with httpx.AsyncClient(
            base_url=runtime_server.base_url, headers=auth_headers, trust_env=False
        ) as client:
            for case in SHORT_EXPRESSION_CASES:
                route_response = await client.post(
                    "/v1/service/assistant/routes",
                    json={"input": case["prompt"], "session_id": session_id},
                )
                route_response.raise_for_status()
                route_preflight.append(route_response.json())

        prompts = temp / "prompts.txt"
        prompts.write_text(
            "\n".join(str(case["prompt"]) for case in SHORT_EXPRESSION_CASES)
            + "\n/quit\n",
            encoding="utf-8",
        )
        cli_env = dict(environment)
        cli_env["PYTHONUTF8"] = "1"
        execution_stage = "run_product_cli"
        cli = run_command(node, [
            "src/cli.mjs", "--base-url", runtime_server.base_url, "--bearer", external_token,
            "--model", model, "--session-id", session_id, "--script", str(prompts), "--yes", "--debug",
        ], cwd=CLI_ROOT, env=cli_env, secrets=secrets)

        execution_stage = "collect_runtime_evidence"
        evidence = await collect_runtime_evidence(runtime_server.base_url, external_token)
        execution_stage = "collect_node_example_evidence"
        async with httpx.AsyncClient(base_url=fake_base_url, trust_env=False) as fake:
            fake_requests = (await fake.get("/_fake/requests")).json()
            fake_state = (await fake.get("/_fake/state")).json()

        execution_stage = "validate_live_evidence"
        runs = list(evidence["runs"])
        fake_items = list(fake_requests.get("requests", []))
        captured_paths = [item.get("path") for item in fake_items]
        route_preflight_exact = len(route_preflight) == len(SHORT_EXPRESSION_CASES)
        route_summaries: list[dict[str, object]] = []
        for case, route in zip(SHORT_EXPRESSION_CASES, route_preflight):
            hint = dict(route.get("organization_context_request_hint") or {})
            exact = (
                route.get("status") == "EXECUTABLE"
                and route.get("request_class") == "SEARCH_KNOWLEDGE"
                and route.get("selected_agent_definition_id")
                == "organization-context-session-agent"
                and route.get("matched_rule_id")
                == "organization-context-short-read-session-stateless-subagent-v1"
                and hint.get("pattern_id") == case["pattern_id"]
                and hint.get("intent") == case["intent"]
                and hint.get("target_expression") == case["target_expression"]
                and list(hint.get("entity_type_hints") or [])
                == list(case["entity_type_hints"])
                and list(hint.get("requested_fields") or [])
                == list(case["requested_fields"])
                and hint.get("preferred_operation") == case["preferred_operation"]
            )
            route_preflight_exact = route_preflight_exact and exact
            route_summaries.append({
                "case_id": case["case_id"],
                "exact": exact,
                "status": route.get("status"),
                "selected_agent_definition_id": route.get("selected_agent_definition_id"),
                "matched_rule_id": route.get("matched_rule_id"),
                "request_hint": hint,
            })

        public_surface = json.dumps(
            {
                "cli": cli,
                "routes": route_summaries,
                "fake_requests": fake_requests,
                "fake_state": fake_state,
            },
            ensure_ascii=False,
            default=str,
        )
        all_model_started: list[dict[str, object]] = []
        all_model_completed: list[dict[str, object]] = []
        turn_summaries: list[dict[str, object]] = []
        safe_tool_failures = []
        safe_agent_failures: list[dict[str, object]] = []
        all_runs_succeeded = len(runs) == len(SHORT_EXPRESSION_CASES)
        model_events_each_turn = len(runs) == len(SHORT_EXPRESSION_CASES)
        root_agent_tool_once_each_turn = len(runs) == len(SHORT_EXPRESSION_CASES)
        child_mcp_once_each_turn = len(runs) == len(SHORT_EXPRESSION_CASES)
        expected_tool_sequence_observed = len(runs) == len(SHORT_EXPRESSION_CASES)
        output_contracts_observed = len(runs) == len(SHORT_EXPRESSION_CASES)
        normalization_event_each_turn = len(runs) == len(SHORT_EXPRESSION_CASES)
        ambiguous_result_normalized = len(runs) == len(SHORT_EXPRESSION_CASES)
        structured_output_diagnostics_bounded = True
        session_turn_completed_payloads: list[dict[str, object]] = []
        session_turn_completed_events_exact = len(runs) == len(SHORT_EXPRESSION_CASES)

        allowed_tool_failure_keys = {
            "payload_schema_version", "failure_stage", "failure_category", "server_id",
            "tool_name", "observed_chars", "max_result_chars", "tool_arguments_persisted",
            "tool_result_persisted", "raw_error_persisted", "retryable",
        }
        allowed_agent_failure_keys = {"code", "detail_type", "retryable"}

        for index, case in enumerate(SHORT_EXPRESSION_CASES):
            if index >= len(runs):
                all_runs_succeeded = False
                model_events_each_turn = False
                root_agent_tool_once_each_turn = False
                child_mcp_once_each_turn = False
                expected_tool_sequence_observed = False
                output_contracts_observed = False
                normalization_event_each_turn = False
                ambiguous_result_normalized = False
                turn_summaries.append({
                    "case_id": case["case_id"],
                    "prompt": case["prompt"],
                    "run_present": False,
                })
                continue

            item = runs[index]
            types = event_types(item)
            model_started = event_payloads(item, "model.started")
            model_completed = event_payloads(item, "model.completed")
            all_model_started.extend(model_started)
            all_model_completed.extend(model_completed)
            tool_started = event_payloads(item, "tool.started")
            tool_completed = event_payloads(item, "tool.completed")
            tool_failures = event_payloads(item, "tool.failed")
            agent_failures = event_payloads(item, "agent.failed")
            run_failures = event_payloads(item, "run.failed")
            normalizations = event_payloads(item, "agent.tool.output.normalized")
            output_validation_failures = event_payloads(
                item, "agent.output.validation.failed"
            )
            normalization_failures = event_payloads(
                item, "agent.tool.output.normalization.failed"
            )
            turn_completed = event_payloads(item, "session.turn.completed")
            session_turn_completed_payloads.extend(turn_completed)
            session_turn_completed_events_exact = (
                session_turn_completed_events_exact
                and len(turn_completed) == 1
                and turn_completed[0].get("session_id") == session_id
                and turn_completed[0].get("turn_count") == index + 1
                and int(turn_completed[0].get("item_count") or 0) > 0
                and turn_completed[0].get("history_persisted_in_product_events") is False
                and turn_completed[0].get("history_persisted_in_product_db") is False
            )
            safe_tool_failures.extend(
                {key: value for key, value in failure.items() if key in allowed_tool_failure_keys}
                for failure in tool_failures
            )
            safe_agent_failures.extend(
                {key: value for key, value in failure.items() if key in allowed_agent_failure_keys}
                for failure in [*agent_failures, *run_failures]
            )
            allowed_structured_diagnostic_keys = {
                "payload_schema_version", "failure_stage", "failure_category",
                "agent_id", "output_contract", "detail_type",
                "validation_error_count", "validation_errors",
                "normalization_error_category", "invocation_id",
                "model_output_persisted", "tool_arguments_persisted",
                "tool_result_persisted", "raw_error_persisted",
            }
            for diagnostic in [*output_validation_failures, *normalization_failures]:
                structured_output_diagnostics_bounded = (
                    structured_output_diagnostics_bounded
                    and set(diagnostic).issubset(allowed_structured_diagnostic_keys)
                    and diagnostic.get("model_output_persisted") is False
                    and diagnostic.get("tool_arguments_persisted") is False
                    and diagnostic.get("tool_result_persisted") is False
                    and diagnostic.get("raw_error_persisted") is False
                    and all(
                        set(value).issubset({"location", "type"})
                        for value in diagnostic.get("validation_errors", [])
                        if isinstance(value, dict)
                    )
                )
            content = dict(item.get("artifact", {}).get("content") or {})
            citations = [dict(value) for value in content.get("citations", []) if isinstance(value, dict)]
            citation_refs = [str(value.get("reference")) for value in citations if value.get("reference")]
            answer = str(content.get("answer") or "")
            unverified = [str(value) for value in content.get("unverified", [])]
            run_status = item.get("run", {}).get("status")
            tool_names = [str(value.get("tool_name")) for value in tool_started]

            all_runs_succeeded = all_runs_succeeded and run_status == "SUCCEEDED"
            model_events_each_turn = model_events_each_turn and (
                len(model_started) >= 2 and len(model_completed) >= 2
            )
            root_agent_tool_once_each_turn = root_agent_tool_once_each_turn and (
                types.count("agent.tool.started") == 1
                and types.count("agent.tool.completed") == 1
            )
            child_mcp_once_each_turn = child_mcp_once_each_turn and (
                len(tool_started) == 1 and len(tool_completed) == 1
            )
            expected_tool_sequence_observed = expected_tool_sequence_observed and (
                tool_names == [case["tool_name"]]
            )
            normalization_event_each_turn = normalization_event_each_turn and (
                len(normalizations) == 1
                and normalizations[0].get("normalization_strategy")
                == "product-owned-mcp-evidence-normalization-v1"
                and normalizations[0].get("tool_name") == case["tool_name"]
                and normalizations[0].get("model_calls_added") == 0
                and normalizations[0].get("tool_reexecuted") is False
                and normalizations[0].get("model_output_persisted") is False
                and normalizations[0].get("tool_result_persisted") is False
            )

            expected_output = case["expected_output"]
            if expected_output == "AMBIGUOUS":
                ambiguous_normalization_ok = (
                    len(normalizations) == 1
                    and normalizations[0].get("strategy")
                    == "deterministic-ambiguous-tool-evidence-v1"
                    and normalizations[0].get("ambiguous") is True
                    and int(normalizations[0].get("candidate_count") or 0) >= 2
                    and normalizations[0].get("clarification_applied") is True
                    and normalizations[0].get("model_calls_added") == 0
                    and normalizations[0].get("tool_reexecuted") is False
                )
                ambiguous_result_normalized = (
                    ambiguous_result_normalized and ambiguous_normalization_ok
                )
                output_ok = (
                    ambiguous_normalization_ok
                    and content.get("status") == "NEEDS_CLARIFICATION"
                    and bool(unverified)
                    and len(citation_refs) >= 2
                    and all("employee-" in value for value in citation_refs)
                    and (
                        "동명" in answer
                        or "부서" in answer
                        or "직책" in answer
                        or any("employee-" in value for value in unverified)
                    )
                )
            elif expected_output == "EMPLOYEE_0017_CONTACT":
                output_ok = (
                    content.get("status") == "ANSWERED"
                    and "employee-0017" in citation_refs
                    and (
                        "user0017@tenant-a.example" in answer
                        or "연락처" in answer
                        or "이메일" in answer
                    )
                )
            else:
                output_ok = empty_search_result_observed(
                    content=content,
                    citation_refs=citation_refs,
                    unverified=unverified,
                    normalizations=normalizations,
                    expected_tool_name=str(case["tool_name"]),
                )
            output_contracts_observed = output_contracts_observed and output_ok

            turn_summaries.append({
                "case_id": case["case_id"],
                "prompt": case["prompt"],
                "run_present": True,
                "run_id": item.get("run", {}).get("run_id"),
                "run_status": run_status,
                "model_started_count": len(model_started),
                "model_completed_count": len(model_completed),
                "agent_tool_started_count": types.count("agent.tool.started"),
                "agent_tool_completed_count": types.count("agent.tool.completed"),
                "tool_names": tool_names,
                "final_status": content.get("status"),
                "citation_references": citation_refs,
                "unverified_count": len(unverified),
                "session_turn_completed": [
                    {
                        key: value
                        for key, value in payload.items()
                        if key in {
                            "session_id", "turn_count", "item_count",
                            "history_persisted_in_product_events",
                            "history_persisted_in_product_db",
                        }
                    }
                    for payload in turn_completed
                ],
                "answer_length": len(answer),
                "answer_sha256": sha256_text(answer) if answer else None,
                "output_contract_observed": output_ok,
                "normalization_events": normalizations,
                "structured_output_diagnostics": [
                    *output_validation_failures, *normalization_failures
                ],
                "safe_agent_failures": [
                    {key: value for key, value in failure.items() if key in allowed_agent_failure_keys}
                    for failure in [*agent_failures, *run_failures]
                ],
            })

        actual_model_call_observed = bool(all_model_started)
        session = next(
            (item for item in evidence["sessions"] if item.get("session_id") == session_id),
            {},
        )
        session_item_count = int(session.get("item_count") or 0)
        expected_paths = [str(case["connector_path"]) for case in SHORT_EXPRESSION_CASES]
        checks = {
            **preflight,
            "short_expression_route_preflight_exact": route_preflight_exact,
            "cli_completed_four_prompts": (
                cli["returncode"] == 0 and "4개 요청 완료" in str(cli["stdout"])
            ),
            "dedicated_organization_context_session_created": (
                created_session.get("agent_definition_id")
                == "organization-context-session-agent"
                and session_id.startswith("session_")
            ),
            "exactly_four_runtime_runs_created": len(runs) == 4,
            "all_runtime_runs_succeeded": all_runs_succeeded,
            "actual_openai_model_events_observed_each_turn": model_events_each_turn,
            "configured_model_used": bool(all_model_started)
            and all(item.get("model") == model for item in all_model_started),
            "root_agent_tool_called_once_each_turn": root_agent_tool_once_each_turn,
            "child_mcp_called_once_each_turn": child_mcp_once_each_turn,
            "expected_mcp_tool_sequence_observed": expected_tool_sequence_observed,
            "normalization_event_observed_once_each_turn": normalization_event_each_turn,
            "ambiguous_result_normalized_each_ambiguous_turn": ambiguous_result_normalized,
            "structured_output_diagnostics_bounded": structured_output_diagnostics_bounded,
            "actual_connector_and_node_example_reached": (
                len(fake_items) == 4 and captured_paths == expected_paths
            ),
            "delegated_identity_forwarded": all(
                item.get("tenant_id") == "tenant-a"
                and item.get("principal_id") == "user-001"
                and item.get("roles") == ["agent-user"]
                and bool(item.get("delegation_id"))
                for item in fake_items
            ),
            "organization_context_api_bearer_redacted": all(
                item.get("authorization_present") is True
                and item.get("authorization_value_recorded") is False
                for item in fake_items
            ),
            "short_expression_output_contracts_observed": output_contracts_observed,
            "root_session_continuity_committed": (
                session_turn_completed_events_exact
                and committed_session_turns_observed(
                    session=session,
                    session_id=session_id,
                    completed_payloads=session_turn_completed_payloads,
                    expected_turn_count=len(SHORT_EXPRESSION_CASES),
                )
            ),
            "catalog_revision_observed": int(fake_state.get("catalog_revision") or 0) > 0,
            "provider_identifiers_not_persisted": bool(all_model_started)
            and all(
                item.get("provider_response_id_persisted") is False
                and item.get("provider_request_id_persisted") is False
                for item in all_model_started
            ),
            "response_storage_and_trace_export_remain_disabled": bool(all_model_started)
            and all(item.get("response_store_requested") is False for item in all_model_started),
            "secrets_absent_from_evidence": all(secret not in public_surface for secret in secrets),
            "command_bearer_redacted": (
                "[REDACTED]" in cli["command"] and external_token not in cli["command"]
            ),
        }
        payload = {
            "schema_version": "okcanvas-agent-platform-workspace-step008-live-acceptance-v3",
            "step": STEP,
            "version": VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_ORGANIZATION_CONTEXT_SHORT_EXPRESSION_E2E",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "started_at": started,
            "completed_at": now(),
            "execution_platform": "windows" if os.name == "nt" else os.name,
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
            "cli": cli,
            "runtime": {
                "run_ids": [item.get("run", {}).get("run_id") for item in runs],
                "session_id": session_id,
                "route_preflight": route_summaries,
                "turns": turn_summaries,
                "safe_tool_failures": safe_tool_failures,
                "safe_agent_failures": safe_agent_failures,
                "raw_tool_arguments_persisted": False,
                "raw_tool_results_persisted": False,
                "raw_error_persisted": False,
            },
            "connector_example": {
                "request_count": len(fake_items),
                "captured_paths": captured_paths,
                "catalog_revision": fake_state.get("catalog_revision"),
                "authorization_value_recorded": any(
                    item.get("authorization_value_recorded") for item in fake_items
                ),
            },
            "limitations": {
                "actual_openai_model_called": actual_model_call_observed,
                "actual_connector_process_executed": True,
                "actual_node_example_process_executed": True,
                "production_database_executed": False,
                "real_enterprise_organization_context_called": False,
            },
        }
    except BaseException as exc:
        execution_exception = exc
        payload = {
            "schema_version": "okcanvas-agent-platform-workspace-step008-live-acceptance-v3",
            "step": STEP, "version": VERSION,
            "validation_mode": "WINDOWS_LIVE_OPENAI_ORGANIZATION_CONTEXT_FULL_PROCESS_E2E",
            "state": "FAILED", "started_at": started, "completed_at": now(),
            "execution_platform": "windows" if os.name == "nt" else os.name,
            "checks": preflight, "passed_checks": sum(value is True for value in preflight.values()), "total_checks": len(preflight),
            "safe_error": {"category": safe_failure_category(exc), "type": type(exc).__name__},
            "failure_stage": execution_stage,
            "environment": {"source_name": env_source, "loaded_key_names": sorted(loaded_keys), "openai_api_key_present": True, "model": model, "secret_values_persisted": False},
            "limitations": {"actual_openai_model_called": actual_model_call_observed, "production_database_executed": False, "real_enterprise_organization_context_called": False, "raw_provider_error_persisted": False},
        }
    finally:
        mcp_http_factory.strict_remote_http_client_factory = original_factory
        if previous_connector_bearer is None:
            os.environ.pop("OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER", None)
        else:
            os.environ["OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"] = previous_connector_bearer
        for server in (runtime_server, connector_server):
            if server is not None:
                try: server.stop()
                except BaseException as exc: cleanup_error_types.append(type(exc).__name__)
        if fake_process is not None:
            try:
                if fake_process.poll() is None:
                    fake_process.terminate()
                    try: fake_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        fake_process.kill(); fake_process.wait(timeout=5)
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
    payload["harness_cleanup"] = {"completed": cleanup_completed, "error_types": sorted(set(cleanup_error_types)), "transient_removal_error_types": sorted(set(transient_removal_error_types)), "processes_stopped_before_temp_removal": True}
    if not cleanup_completed:
        payload["state"] = "FAILED"
        if execution_exception is None:
            payload["safe_error"] = {"category": "HARNESS_CLEANUP_FAILED", "type": "CleanupFailure"}
            payload["failure_stage"] = "cleanup"
    payload["completed_at"] = now()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--example-root", type=Path, default=EXAMPLE_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    payload = asyncio.run(execute(args.example_root.resolve(), args.output.resolve()))
    write_json_stdout(payload)
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
