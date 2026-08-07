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
import threading
import time
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "okcanvas-agent-runtime"
CONNECTOR_ROOT = ROOT / "okcanvas-connectors/groupware-mcp-server"
CLI_ROOT = ROOT / "okcanvas-agent-cli"
SCRIPTS = ROOT / "scripts"
for path in (RUNTIME_ROOT, CONNECTOR_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import httpx
import uvicorn

from workspace_process import prepare_invocation, resolve_executable, write_json_stdout
from groupware_mcp_server.app import create_app as create_connector_app
from groupware_mcp_server.config import Settings as ConnectorSettings
from okcanvas_agent_runtime.application.execution.contracts import (
    GenericGatewayRunResult,
    GatewayLifecycleEvent,
)
from okcanvas_agent_runtime.application.groupware_read import (
    parse_product_routing_context,
    requires_groupware_session_delegation,
)
from okcanvas_agent_runtime.control_api import create_app as create_runtime_app
from okcanvas_agent_runtime.core.contracts import (
    AssistantCitation,
    AssistantRequestClass,
    AssistantResultStatus,
    AssistantSideEffect,
    OrganizationAssistantResult,
    UsageSummary,
)

STEP = "WORKSPACE_STEP003_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_E2E"
VERSION = "0.3.0"
EXTERNAL_TOKEN = "step003-external-service-bearer-123456"
CONNECTOR_TOKEN = "step003-connector-bearer-123456"
GROUPWARE_TOKEN = "example-groupware-api-token"
ADMIN_KEY = "step003-admin-key-1234567890"
SUBMITTER_KEY = "step003-submitter-key-1234567890"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")


class FakeSQLiteSession:
    histories: dict[str, list[dict[str, object]]] = {}
    lock = threading.Lock()

    def __init__(self, session_id: str, db_path: str | Path) -> None:
        self.session_id = session_id
        self.db_path = Path(db_path)
        with self.lock:
            self.histories.setdefault(session_id, [])

    async def get_items(self, limit: int | None = None):
        with self.lock:
            items = list(self.histories[self.session_id])
        return items[-limit:] if limit is not None else items

    async def add_items(self, items):
        with self.lock:
            self.histories[self.session_id].extend(items)

    async def pop_item(self):
        with self.lock:
            if not self.histories[self.session_id]:
                return None
            return self.histories[self.session_id].pop()

    async def clear_session(self):
        with self.lock:
            self.histories[self.session_id].clear()

    def close(self) -> None:
        return None


def install_deterministic_session_sdk() -> None:
    module = types.ModuleType("agents")
    module.SQLiteSession = FakeSQLiteSession
    sys.modules["agents"] = module
    FakeSQLiteSession.histories.clear()


class LiveASGIServer:
    def __init__(self, app: object) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(2048)
        self.port = int(self.socket.getsockname()[1])
        self.base_url = f"http://127.0.0.1:{self.port}"
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
            access_log=False,
            lifespan="on",
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [self.socket]},
            name=f"uvicorn-{self.port}",
            daemon=True,
        )

    def start(self) -> None:
        self.thread.start()
        deadline = time.monotonic() + 10
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
        try:
            self.socket.close()
        except OSError:
            pass


class DeterministicGroupwareSessionGateway:
    def __init__(self, connector_base_url: str) -> None:
        self.connector_base_url = connector_base_url.rstrip("/")
        self.calls: list[dict[str, object]] = []

    @staticmethod
    def _user_request(request: str) -> str:
        separator = "\n\nUSER REQUEST:\n"
        return request.split(separator, 1)[1] if separator in request else request

    async def _append_session(self, session_runtime, session_id: str, user: str, answer: str) -> None:
        sdk_session = session_runtime.sdk_session(session_id)
        try:
            await sdk_session.add_items(
                [
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": answer},
                ]
            )
        finally:
            sdk_session.close()

    async def _call_connector(self, *, run_id: str, identity) -> dict[str, object]:
        headers = {
            "Authorization": f"Bearer {CONNECTOR_TOKEN}",
            "X-OKCanvas-Tenant-ID": identity.tenant_id,
            "X-OKCanvas-Principal-ID": identity.principal_id,
            "X-OKCanvas-Roles": ",".join(identity.roles),
            "X-OKCanvas-Delegation-ID": identity.delegation_id,
            "Accept": "application/json, text/event-stream",
        }
        payload = {
            "jsonrpc": "2.0",
            "id": f"{run_id}-call-001",
            "method": "tools/call",
            "params": {
                "name": "search_notices",
                "arguments": {"query": "maintenance", "limit": 5},
                "_meta": {"request_id": f"{run_id}-tool-001"},
            },
        }
        async with httpx.AsyncClient(base_url=self.connector_base_url, trust_env=False) as client:
            response = await client.post(
                f"/tenants/{identity.tenant_id}/mcp",
                headers=headers,
                json=payload,
                timeout=5,
            )
        response.raise_for_status()
        body = response.json()
        structured = body["result"]["structuredContent"]
        if body["result"]["isError"] is not False or structured["mutated"] is not False:
            raise RuntimeError("Connector returned a failed or mutating Groupware result")
        return structured

    async def run(
        self,
        *,
        definition,
        request,
        run_id,
        settings,
        lifecycle_sink,
        session_id=None,
        session_runtime=None,
        delegated_mcp_identity=None,
        **_kwargs,
    ) -> GenericGatewayRunResult:
        del settings
        if definition.agent_id != "organization-assistant-session-agent":
            raise RuntimeError("STEP003 gateway accepts only the Main Assistant Session root")
        if not session_id or session_runtime is None:
            raise RuntimeError("STEP003 requires the Runtime-owned SQLite Session")
        route = parse_product_routing_context(request)
        if route is None:
            raise RuntimeError("STEP003 requires immutable Product routing context")
        user_request = self._user_request(request)
        groupware_turn = requires_groupware_session_delegation(request)
        self.calls.append(
            {
                "run_id": run_id,
                "session_id": session_id,
                "groupware_turn": groupware_turn,
                "route": route,
                "delegated_identity_present": delegated_mcp_identity is not None,
            }
        )
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        if groupware_turn:
            if delegated_mcp_identity is None:
                raise RuntimeError("Groupware turn is missing delegated identity")
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "agent.tool.started",
                    {
                        "from_agent_id": definition.agent_id,
                        "to_agent_id": "groupware-read-agent",
                        "arguments_persisted": False,
                        "result_persisted": False,
                    },
                )
            )
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "tool.started",
                    {
                        "server_id": "groupware-read",
                        "tool_name": "search_notices",
                        "arguments_persisted": False,
                    },
                )
            )
            structured = await self._call_connector(
                run_id=run_id, identity=delegated_mcp_identity
            )
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "tool.completed",
                    {
                        "server_id": "groupware-read",
                        "tool_name": "search_notices",
                        "result_persisted": False,
                    },
                )
            )
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "agent.tool.completed",
                    {
                        "from_agent_id": definition.agent_id,
                        "to_agent_id": "groupware-read-agent",
                        "parent_control_retained": True,
                        "result_persisted": False,
                    },
                )
            )
            record = structured["records"][0]
            title = str(record["title"])
            answer = f"그룹웨어 공지 1건을 확인했습니다: {title}"
            result = OrganizationAssistantResult(
                status=AssistantResultStatus.ANSWERED,
                answer=answer,
                request_class=AssistantRequestClass.READ_SYSTEM,
                side_effect=AssistantSideEffect.READ,
                citations=[
                    AssistantCitation(
                        source_type="ENTERPRISE_SYSTEM",
                        label=title,
                        reference=str(record["record_id"]),
                    )
                ],
                completed_actions=[],
                proposed_actions=[],
                pending_approvals=[],
                unverified=[],
                follow_up_state="groupware-notice-title-confirmed",
            )
            usage = UsageSummary(requests=2, input_tokens=24, output_tokens=14, total_tokens=38)
        else:
            if delegated_mcp_identity is not None:
                raise RuntimeError("Language-only continuation must not receive delegated MCP identity")
            sdk_session = session_runtime.sdk_session(session_id)
            try:
                prior_items = await sdk_session.get_items()
            finally:
                sdk_session.close()
            prior_text = json.dumps(prior_items, ensure_ascii=False)
            if "Maintenance notice" not in prior_text:
                raise RuntimeError("Second turn could not observe the committed Root Session history")
            answer = "앞선 답변에서 확인한 공지 제목은 Maintenance notice입니다."
            result = OrganizationAssistantResult(
                status=AssistantResultStatus.ANSWERED,
                answer=answer,
                request_class=AssistantRequestClass.ANSWER,
                side_effect=AssistantSideEffect.NONE,
                citations=[],
                completed_actions=[],
                proposed_actions=[],
                pending_approvals=[],
                unverified=[],
                follow_up_state=None,
            )
            usage = UsageSummary(requests=1, input_tokens=16, output_tokens=9, total_tokens=25)
        await self._append_session(session_runtime, session_id, user_request, result.answer)
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id}))
        return GenericGatewayRunResult(
            output=result,
            usage=usage,
            trace_id=f"trace_{run_id}",
            response_id=f"response_{run_id}",
            sdk_version="deterministic-step003-harness",
        )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def registry_json() -> str:
    return json.dumps(
        {
            "schema_version": "okcanvas-service-client-token-registry-v1",
            "tokens": [
                {
                    "token_id": "step003-user",
                    "token_sha256": sha256_text(EXTERNAL_TOKEN),
                    "tenant_id": "tenant-a",
                    "principal_id": "user-001",
                    "roles": ["agent-user"],
                }
            ],
        },
        sort_keys=True,
    )


def run_command(executable: str, args: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, object]:
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
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    public_command = (
        [str(part) for part in invocation]
        if not isinstance(invocation, str)
        else [invocation]
    )
    for index, value in enumerate(public_command[:-1]):
        if value == "--bearer":
            public_command[index + 1] = "[REDACTED]"
    return {
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "command": public_command,
    }


async def wait_http(base_url: str, path: str, *, headers: dict[str, str] | None = None) -> None:
    deadline = time.monotonic() + 10
    async with httpx.AsyncClient(base_url=base_url, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(path, headers=headers, timeout=0.5)
                if response.status_code < 500:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.05)
    raise RuntimeError(f"HTTP endpoint did not become ready: {base_url}{path}")


async def collect_runtime_evidence(
    runtime_base_url: str,
    gateway: DeterministicGroupwareSessionGateway,
) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {EXTERNAL_TOKEN}"}
    async with httpx.AsyncClient(base_url=runtime_base_url, headers=headers, trust_env=False) as client:
        sessions = (await client.get("/v1/service/sessions?limit=100")).json()["sessions"]
        session = sessions[0]
        runs: list[dict[str, object]] = []
        for call in gateway.calls:
            run_id = str(call["run_id"])
            run = (await client.get(f"/v1/service/runs/{run_id}")).json()
            events = (await client.get(f"/v1/service/runs/{run_id}/events")).json()["events"]
            invocations = (await client.get(f"/v1/service/runs/{run_id}/invocations")).json()["invocations"]
            artifacts = (await client.get(f"/v1/service/runs/{run_id}/artifacts")).json()["artifacts"]
            final_meta = next(
                (item for item in artifacts if item["artifact_type"] == "agent.final-output"),
                None,
            )
            artifact = (
                (
                    await client.get(
                        f"/v1/service/runs/{run_id}/artifacts/{final_meta['artifact_id']}"
                    )
                ).json()
                if final_meta is not None
                else {"artifact_type": None, "content": {}}
            )
            runs.append(
                {
                    "run": run,
                    "events": events,
                    "invocations": invocations,
                    "artifact": artifact,
                }
            )
    return {"session": session, "runs": runs}


async def execute(example_root: Path) -> dict[str, object]:
    install_deterministic_session_sdk()
    node = resolve_executable("node")
    npm = resolve_executable("npm")
    with tempfile.TemporaryDirectory(prefix="okcanvas-workspace-step003-") as temp_name:
        temp = Path(temp_name)
        example = temp / "groupware-api-fake"
        shutil.copytree(
            example_root,
            example,
            ignore=shutil.ignore_patterns("node_modules", "dist", ".pytest_cache"),
        )
        environment = dict(os.environ)
        setup = run_command(npm, ["ci", "--ignore-scripts", "--offline"], cwd=example, env=environment)
        if setup["returncode"] != 0:
            raise RuntimeError(str(setup["stdout"]) + str(setup["stderr"]))
        build = run_command(npm, ["run", "build"], cwd=example, env=environment)
        if build["returncode"] != 0:
            raise RuntimeError(str(build["stdout"]) + str(build["stderr"]))

        fake_port_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fake_port_socket.bind(("127.0.0.1", 0))
        fake_port = int(fake_port_socket.getsockname()[1])
        fake_port_socket.close()
        fake_env = dict(environment)
        fake_env.update({"PORT": str(fake_port), "HOST": "127.0.0.1"})
        fake_process = subprocess.Popen(
            [node, "dist/src/main.js"],
            cwd=example,
            env=fake_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        fake_base_url = f"http://127.0.0.1:{fake_port}"
        connector_server: LiveASGIServer | None = None
        runtime_server: LiveASGIServer | None = None
        previous_env = {name: os.environ.get(name) for name in (
            "OKCANVAS_GROUPWARE_READ_BEARER",
            "OPENAI_API_KEY",
            "OKCANVAS_DEFAULT_MODEL",
        )}
        try:
            await wait_http(fake_base_url, "/healthz")
            connector_app = create_connector_app(
                ConnectorSettings(
                    connector_bearer=CONNECTOR_TOKEN,
                    groupware_base_url=fake_base_url,
                    groupware_api_bearer=GROUPWARE_TOKEN,
                    http_timeout_seconds=2,
                    max_retry_attempts=0,
                )
            )
            connector_server = LiveASGIServer(connector_app)
            connector_server.start()
            await wait_http(connector_server.base_url, "/healthz")

            os.environ["OKCANVAS_GROUPWARE_READ_BEARER"] = CONNECTOR_TOKEN
            os.environ["OPENAI_API_KEY"] = "step003-deterministic-model-key"
            os.environ["OKCANVAS_DEFAULT_MODEL"] = "test-model"
            runtime_project = temp / "runtime-project"
            shutil.copytree(RUNTIME_ROOT / "specs", runtime_project / "specs")
            shutil.copytree(RUNTIME_ROOT / "reference", runtime_project / "reference")
            groupware_server_path = runtime_project / "specs/mcp/servers/groupware-read/server.json"
            groupware_server = json.loads(groupware_server_path.read_text(encoding="utf-8"))
            groupware_server["url_template"] = (
                "https://connector.example.com/tenants/{tenant_id}/mcp"
            )
            groupware_server_path.write_text(
                json.dumps(groupware_server, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            gateway = DeterministicGroupwareSessionGateway(connector_server.base_url)
            runtime_app = create_runtime_app(
                project_root=runtime_project,
                product_db=temp / "runtime" / "product.sqlite3",
                artifact_root=temp / "runtime" / "artifacts",
                admin_key=ADMIN_KEY,
                gateway=gateway,
                run_submitter_key=SUBMITTER_KEY,
                protected_payload_root=temp / "runtime" / "protected-payloads",
                protected_payload_key=PAYLOAD_KEY,
                session_root=temp / "runtime" / "sessions",
                session_history_key=SESSION_KEY,
                service_client_token_registry_json=registry_json(),
            )
            runtime_server = LiveASGIServer(runtime_app)
            runtime_server.start()
            auth_headers = {"Authorization": f"Bearer {EXTERNAL_TOKEN}"}
            await wait_http(runtime_server.base_url, "/v1/service/whoami", headers=auth_headers)

            prompts = temp / "prompts.txt"
            prompts.write_text(
                "최근 그룹웨어 공지 목록을 보여줘.\n"
                "앞선 답변의 제목을 그대로 다시 말해줘.\n"
                "/quit\n",
                encoding="utf-8",
            )
            cli_env = dict(environment)
            cli_env["PYTHONUTF8"] = "1"
            cli = run_command(
                node,
                [
                    "src/cli.mjs",
                    "--base-url",
                    runtime_server.base_url,
                    "--bearer",
                    EXTERNAL_TOKEN,
                    "--model",
                    "test-model",
                    "--script",
                    str(prompts),
                    "--yes",
                    "--debug",
                ],
                cwd=CLI_ROOT,
                env=cli_env,
            )
            evidence = await collect_runtime_evidence(runtime_server.base_url, gateway)
            async with httpx.AsyncClient(base_url=fake_base_url, trust_env=False) as fake:
                fake_requests = (await fake.get("/_fake/requests")).json()

            stdout = str(cli["stdout"])
            stderr = str(cli["stderr"])
            if len(gateway.calls) != 2:
                raise RuntimeError(
                    "CLI did not execute two Runtime calls\nSTDOUT:\n" + stdout + "\nSTDERR:\n" + stderr
                )
            first = evidence["runs"][0]
            second = evidence["runs"][1]
            if first["run"]["status"] != "SUCCEEDED" or second["run"]["status"] != "SUCCEEDED":
                raise RuntimeError(
                    "Runtime E2E run failed\nSTDOUT:\n"
                    + stdout
                    + "\nSTDERR:\n"
                    + stderr
                    + "\nEVIDENCE:\n"
                    + json.dumps(evidence, ensure_ascii=False, indent=2)
                )
            first_event_types = [item["event_type"] for item in first["events"]]
            second_event_types = [item["event_type"] for item in second["events"]]
            captured = fake_requests["requests"][0]
            secret_surface = stdout + stderr + json.dumps(evidence, ensure_ascii=False)
            checks = {
                "product_cli_completed_two_prompts": cli["returncode"] == 0
                and "종료 · 2개 요청 완료" in stdout,
                "main_assistant_session_owned_both_turns": len(gateway.calls) == 2
                and gateway.calls[0]["session_id"] == gateway.calls[1]["session_id"]
                and all(
                    call["route"]["selected_agent_definition_id"]
                    == "organization-assistant-session-agent"
                    for call in gateway.calls
                ),
                "groupware_subagent_selected_only_first_turn": gateway.calls[0]["groupware_turn"] is True
                and gateway.calls[0]["route"]["required_capabilities"] == ["groupware-read-v1"]
                and gateway.calls[1]["groupware_turn"] is False,
                "delegated_identity_scoped_only_to_groupware_turn": gateway.calls[0]["delegated_identity_present"] is True
                and gateway.calls[1]["delegated_identity_present"] is False,
                "runtime_connector_mcp_http_crossed": first_event_types.count("agent.tool.started") == 1
                and first_event_types.count("tool.started") == 1
                and first_event_types.count("tool.completed") == 1
                and first_event_types.count("agent.tool.completed") == 1,
                "stateless_child_not_reused_for_continuation": "agent.tool.started" not in second_event_types
                and len(second["invocations"]) == 1,
                "connector_example_rest_reached": len(fake_requests["requests"]) == 1
                and captured["path"] == "/api/v1/notices/search",
                "delegated_identity_forwarded_to_example": captured["tenant_id"] == "tenant-a"
                and captured["principal_id"] == "user-001"
                and captured["roles"] == ["agent-user"]
                and bool(captured["delegation_id"]),
                "groupware_api_bearer_redacted_by_example": captured["authorization_present"] is True
                and captured["authorization_value_recorded"] is False,
                "enterprise_citation_persisted": first["artifact"]["content"]["request_class"] == "READ_SYSTEM"
                and first["artifact"]["content"]["side_effect"] == "READ"
                and first["artifact"]["content"]["citations"][0]["reference"] == "notice-001",
                "root_session_continuity_committed": evidence["session"]["turn_count"] == 2
                and evidence["session"]["item_count"] == 4
                and "Maintenance notice" in second["artifact"]["content"]["answer"],
                "persisted_sse_and_terminal_artifacts_observed": all(
                    run["run"]["status"] == "SUCCEEDED"
                    and any(event["event_type"] == "run.completed" for event in run["events"])
                    and run["artifact"]["artifact_type"] == "agent.final-output"
                    for run in evidence["runs"]
                ),
                "external_and_connector_secrets_not_exposed": EXTERNAL_TOKEN not in secret_surface
                and CONNECTOR_TOKEN not in secret_surface
                and GROUPWARE_TOKEN not in secret_surface,
                "cli_rendered_groupware_and_follow_up_answers": "Maintenance notice" in stdout
                and "앞선 답변에서 확인한 공지 제목" in stdout,
            }
            return {
                "schema_version": "okcanvas-agent-platform-workspace-step003-e2e-v1",
                "step": STEP,
                "version": VERSION,
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "passed_checks": sum(value is True for value in checks.values()),
                "total_checks": len(checks),
                "runtime_run_ids": [call["run_id"] for call in gateway.calls],
                "session_id": gateway.calls[0]["session_id"] if gateway.calls else None,
                "cli": cli,
                "fake_request_count": len(fake_requests["requests"]),
                "retained_boundaries": {
                    "runtime": "STEP087R2_SESSION_REFERENTIAL_RESTATEMENT_ROUTING_CLOSURE",
                    "cli": "CLI_STEP001R1_WINDOWS_NODE_TEST_RUNNER_PATH_SPACE_CLOSURE",
                    "connector": "CONNECTOR_STEP001R1_ASYNC_TEST_RUNNER_DEPENDENCY_CLOSURE",
                    "example": "EXAMPLE_STEP001R1_TYPESCRIPT_BUILD_DEPENDENCY_CLOSURE",
                },
            }
        finally:
            if runtime_server is not None:
                runtime_server.stop()
            if connector_server is not None:
                connector_server.stop()
            fake_process.terminate()
            try:
                fake_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                fake_process.kill()
                fake_process.wait(timeout=5)
            for name, value in previous_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--example-root",
        type=Path,
        default=ROOT / "okcanvas-connector-examples/groupware/groupware-api-fake",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = asyncio.run(execute(args.example_root.resolve()))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    write_json_stdout(payload)
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
