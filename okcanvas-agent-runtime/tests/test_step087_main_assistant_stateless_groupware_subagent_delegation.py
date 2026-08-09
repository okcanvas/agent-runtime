from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import shutil
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.assistant_routing.cross_domain_session import CrossDomainSessionDelegationCatalog
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.application.execution.contracts import GenericGatewayRunResult, GatewayLifecycleEvent
from okcanvas_agent_runtime.application.groupware_read import (
    requires_groupware_session_delegation,
)
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.core.contracts import (
    AssistantCitation,
    AssistantRequestClass,
    AssistantResultStatus,
    AssistantSideEffect,
    GroupwareReadCitation,
    GroupwareReadResult,
    GroupwareReadStatus,
    OrganizationAssistantResult,
    UsageSummary,
)

ROOT = Path(__file__).resolve().parents[1]
GROUPWARE_ENV = "OKCANVAS_GROUPWARE_READ_BEARER"
ADMIN_KEY = "step087-admin-key-1234567890"
SUBMITTER_KEY = "step087-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
USER_TOKEN = "step087-user-service-token-123456"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class FakeSQLiteSession:
    histories: dict[str, list[dict[str, object]]] = {}

    def __init__(self, session_id: str, db_path: str | Path) -> None:
        self.session_id = session_id
        self.db_path = Path(db_path)
        self.histories.setdefault(session_id, [])

    async def get_items(self, limit: int | None = None):
        items = list(self.histories[self.session_id])
        return items[-limit:] if limit is not None else items

    async def add_items(self, items):
        self.histories[self.session_id].extend(items)

    async def pop_item(self):
        if not self.histories[self.session_id]:
            return None
        return self.histories[self.session_id].pop()

    async def clear_session(self):
        self.histories[self.session_id].clear()

    def close(self) -> None:
        return None


def _install_fake_agents(monkeypatch) -> None:
    module = types.ModuleType("agents")
    module.SQLiteSession = FakeSQLiteSession
    monkeypatch.setitem(sys.modules, "agents", module)
    FakeSQLiteSession.histories.clear()


REGISTRY = json.dumps(
    {
        "schema_version": "okcanvas-service-client-token-registry-v1",
        "tokens": [
            {
                "token_id": "step087-user",
                "token_sha256": _sha(USER_TOKEN),
                "tenant_id": "tenant-a",
                "principal_id": "alice",
                "roles": ["agent-user"],
            }
        ],
    },
    sort_keys=True,
)


def _configured_project(tmp_path: Path) -> Path:
    project = tmp_path / "configured-project"
    shutil.copytree(ROOT / "specs", project / "specs")
    shutil.copytree(ROOT / "reference", project / "reference")
    server_path = project / "specs/mcp/servers/groupware-read/server.json"
    payload = json.loads(server_path.read_text(encoding="utf-8"))
    payload["url_template"] = "https://connector.example.com/tenants/{tenant_id}/mcp"
    server_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return project


class RecordingGroupwareGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

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
    ):
        self.calls.append(
            {
                "definition": definition,
                "request": request,
                "session_id": session_id,
                "session_runtime": session_runtime,
                "delegated_mcp_identity": delegated_mcp_identity,
            }
        )
        assert definition.agent_id == "organization-assistant-session-agent"
        assert session_id
        assert session_runtime is not None
        assert delegated_mcp_identity is not None
        assert delegated_mcp_identity.tenant_id == "tenant-a"
        assert delegated_mcp_identity.principal_id == "alice"
        assert delegated_mcp_identity.roles == ("agent-user",)
        assert requires_groupware_session_delegation(request)
        sdk_session = session_runtime.sdk_session(session_id)
        try:
            await sdk_session.add_items(
                [
                    {"role": "user", "content": "최근 그룹웨어 공지 목록을 보여줘."},
                    {"role": "assistant", "content": "정기 점검 공지 1건을 확인했습니다."},
                ]
            )
        finally:
            sdk_session.close()
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
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
                {"server_id": "groupware-read", "tool_name": "search_notices", "arguments_persisted": False},
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "tool.completed",
                {"server_id": "groupware-read", "tool_name": "search_notices", "result_persisted": False},
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
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id}))
        return GenericGatewayRunResult(
            output=OrganizationAssistantResult(
                status=AssistantResultStatus.ANSWERED,
                answer="정기 점검 공지 1건을 확인했습니다.",
                request_class=AssistantRequestClass.READ_SYSTEM,
                side_effect=AssistantSideEffect.READ,
                citations=[
                    AssistantCitation(
                        source_type="ENTERPRISE_SYSTEM",
                        label="정기 점검 안내",
                        reference="notice-001",
                    )
                ],
                completed_actions=[],
                proposed_actions=[],
                pending_approvals=[],
                unverified=[],
                follow_up_state=None,
            ),
            usage=UsageSummary(requests=2, input_tokens=20, output_tokens=12, total_tokens=32),
            trace_id="trace_step087",
            response_id="resp_step087",
            sdk_version="0.19.0",
        )


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/v1/service/runs/{run_id}", headers={"Authorization": f"Bearer {USER_TOKEN}"})
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("STEP087 run did not become terminal")


def test_step087_exact_composition_and_runtime_binding() -> None:
    definitions = AgentDefinitionCatalog(ROOT)
    root = definitions.resolve("organization-assistant-session-agent")
    child = definitions.resolve("groupware-read-agent")
    composition = CrossDomainSessionDelegationCatalog(ROOT).resolve(root)
    assert root.agent_tools == ("groupware-read-agent", "organization-context-read-agent")
    assert root.session_mode == "sqlite-v1"
    assert root.output_contract == "OrganizationAssistantResult"
    assert child.session_mode == "disabled"
    assert child.output_contract == "GroupwareReadResult"
    assert child.mcp_servers == ("groupware-read",)
    assert composition.policy.delegated_identity_required is True
    assert composition.policy.write_enabled is False
    assert [item.domain for item in composition.targets] == ["GROUPWARE", "ORGANIZATION_CONTEXT"]
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root)
    assert binding.execution_path == "sqlite-session-bounded-cross-domain-read-subagent-execution-v1"
    assert binding.session_policy["cross_domain_session_delegation"]["max_depth"] == 1
    assert [item["domain"] for item in binding.agent_tool_policy["targets"]] == ["GROUPWARE", "ORGANIZATION_CONTEXT"]
    assert {item["owner_agent_id"] for item in binding.mcp_servers} == {"groupware-read-agent", "organization-context-read-agent"}
    info = RuntimeInfo()
    assert info.version == "2.78.2"
    assert info.step == "STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE"
    assert info.main_assistant_groupware_session_delegation_implemented is True
    assert info.main_assistant_groupware_live_openai_provider_verified is False
    assert info.step087_windows_deterministic_accepted is False


def test_step087_session_route_selects_root_and_declares_stateless_child(tmp_path: Path, monkeypatch) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    decision = router.route(
        request="최근 그룹웨어 공지 목록을 보여줘.",
        session_id="session-001",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    assert decision.status.value == "EXECUTABLE"
    assert decision.selected_agent_id == "organization-assistant-session-agent"
    assert decision.required_capabilities[0].selected_agent_id == "groupware-read-agent"
    assert decision.matched_rule_id == "groupware-read-session-stateless-subagent-v1"
    assert "session-owned-main-assistant-retained" in decision.reasons
    assert "child-session-persistence-disabled" in decision.reasons
    model_request = router.build_model_request(decision, "최근 그룹웨어 공지 목록을 보여줘.")
    assert requires_groupware_session_delegation(model_request) is True
    assert '"selected_agent_definition_id": "organization-assistant-session-agent"' in model_request
    assert "connector-secret" not in model_request


def test_step087_service_session_preflight_execution_forwards_delegated_identity(
    tmp_path: Path, monkeypatch
) -> None:
    _install_fake_agents(monkeypatch)
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "connector-secret")
    gateway = RecordingGroupwareGateway()
    app = create_app(
        project_root=project,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=gateway,
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_KEY,
        service_client_token_registry_json=REGISTRY,
    )
    headers = {"Authorization": f"Bearer {USER_TOKEN}"}
    with TestClient(app) as client:
        session_response = client.post("/v1/service/assistant/sessions", headers=headers)
        assert session_response.status_code == 201, session_response.text
        session_id = session_response.json()["session_id"]
        preflight = client.post(
            "/v1/service/assistant/run-submissions/preflight",
            headers=headers,
            json={
                "input": "최근 그룹웨어 공지 목록을 보여줘.",
                "model": "test-model",
                "session_id": session_id,
                "idempotency_key": "step087-session-groupware-0001",
            },
        )
        assert preflight.status_code == 201, preflight.text
        body = preflight.json()
        assert body["route"]["selected_agent_definition_id"] == "organization-assistant-session-agent"
        assert body["route"]["required_capabilities"][0]["selected_agent_id"] == "groupware-read-agent"
        submission = body["submission"]
        assert submission["agent_definition_id"] == "organization-assistant-session-agent"
        confirm = client.post(
            f"/v1/service/run-submissions/{submission['submission_id']}/confirm",
            headers=headers,
            json={"confirmation": submission["confirmation_challenge"]},
        )
        assert confirm.status_code == 202, confirm.text
        run_id = confirm.json()["run_id"]
        terminal = _wait_terminal(client, run_id)
        assert terminal["status"] == "SUCCEEDED", terminal
        artifacts = client.get(f"/v1/service/runs/{run_id}/artifacts", headers=headers)
        assert artifacts.status_code == 200, artifacts.text
        final_artifact = next(
            item for item in artifacts.json()["artifacts"] if item["artifact_type"] == "agent.final-output"
        )
        artifact = client.get(
            f"/v1/service/runs/{run_id}/artifacts/{final_artifact['artifact_id']}", headers=headers
        )
        assert artifact.status_code == 200, artifact.text
        content = artifact.json()["content"]
        assert content["request_class"] == "READ_SYSTEM"
        assert content["side_effect"] == "READ"
        assert content["citations"][0]["reference"] == "notice-001"
    assert len(gateway.calls) == 1



def _usage_summary(input_tokens: int = 10, output_tokens: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        requests=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )


def _groupware_model_request() -> str:
    context = {
        "schema_version": "okcanvas-assistant-routing-context-v2",
        "status": "EXECUTABLE",
        "selected_agent_definition_id": "organization-assistant-session-agent",
        "required_capabilities": ["groupware-read-v1"],
        "groupware_read_policy": {
            "policy_id": "groupware-read-v1",
            "delegated_identity_required": True,
            "write_enabled": False,
        },
    }
    return (
        "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True)
        + "\n\nUSER REQUEST:\n최근 그룹웨어 공지 목록을 보여줘."
    )


def test_step087_generic_gateway_places_mcp_only_on_stateless_child(monkeypatch) -> None:
    captured: dict[str, object] = {"agents": [], "events": []}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeServer:
        name = "groupware-read"

    class FakeManager:
        active_servers = [FakeServer()]

        async def __aenter__(self):
            captured["manager_entered"] = True
            return self

        async def __aexit__(self, exc_type, exc, tb):
            captured["manager_exited"] = True
            return False

    monkeypatch.setattr(
        gateway_module,
        "create_openai_mcp_runtime",
        lambda *args, **kwargs: SimpleNamespace(manager=FakeManager()),
    )

    child_output = GroupwareReadResult(
        status=GroupwareReadStatus.ANSWERED,
        answer="정기 점검 공지 1건을 확인했습니다.",
        queried_operations=["search_notices"],
        result_count=1,
        citations=[GroupwareReadCitation(label="정기 점검 안내", reference="notice-001")],
        unverified=[],
    )
    parent_output = OrganizationAssistantResult(
        status=AssistantResultStatus.ANSWERED,
        answer="정기 점검 공지 1건을 확인했습니다.",
        request_class=AssistantRequestClass.READ_SYSTEM,
        side_effect=AssistantSideEffect.READ,
        citations=[
            AssistantCitation(
                source_type="ENTERPRISE_SYSTEM",
                label="정기 점검 안내",
                reference="notice-001",
            )
        ],
        completed_actions=[],
        proposed_actions=[],
        pending_approvals=[],
        unverified=[],
        follow_up_state=None,
    )

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    class FakeAgentTool:
        def __init__(self, child, **kwargs):
            self.child = child
            self.name = kwargs["tool_name"]
            self._kwargs = kwargs
            self._tool_origin = SimpleNamespace(
                type=SimpleNamespace(value="agent_as_tool"),
                agent_name=child.name,
                agent_tool_name=self.name,
            )

        async def invoke(self):
            class NestedResult:
                final_output = child_output
                new_items = []
                context_wrapper = SimpleNamespace(usage=_usage_summary())

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is GroupwareReadResult
                    assert raise_if_incorrect_type is True
                    return child_output

            return await self._kwargs["custom_output_extractor"](NestedResult())

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            captured["agents"].append(self)

        def as_tool(self, **kwargs):
            captured["child_session"] = kwargs["session"]
            captured["child_run_config"] = kwargs["run_config"].values
            return FakeAgentTool(self, **kwargs)

    class FakeRunner:
        @classmethod
        async def run(
            cls,
            agent,
            request,
            *,
            max_turns,
            hooks,
            run_config,
            error_handlers=None,
            session,
            **kwargs,
        ):
            captured["root_agent"] = agent
            captured["root_session"] = session
            captured["root_max_turns"] = max_turns
            tool = agent.tools[0]
            context = SimpleNamespace(
                tool_name=tool.name,
                tool_call_id="step087-agent-tool-call",
                tool_arguments='{"input":"최근 공지"}',
                usage=_usage_summary(),
            )
            await hooks.on_tool_start(context, agent, tool)
            nested_result = await tool.invoke()
            await hooks.on_tool_end(context, agent, tool, nested_result)

            class Result:
                context_wrapper = SimpleNamespace(usage=_usage_summary(20, 10))
                last_response_id = "resp-step087-gateway"
                new_items = []

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is OrganizationAssistantResult
                    assert raise_if_incorrect_type is True
                    return parent_output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace-step087-gateway"
    fake_agents.set_default_openai_key = lambda value: captured.setdefault("api_key", value)

    class FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.retry_policies = SimpleNamespace(never=lambda: (lambda _context: False))
    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")

    class FakeSession:
        def close(self) -> None:
            captured["root_session_closed"] = True

    session_runtime = SimpleNamespace(sdk_session=lambda session_id: FakeSession())
    identity = DelegatedMCPIdentity.create(
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )

    async def sink(event):
        captured["events"].append(event)

    result = asyncio.run(
        OpenAIGenericAgentGateway().run(
            definition=AgentDefinitionCatalog(ROOT).resolve("organization-assistant-session-agent"),
            request=_groupware_model_request(),
            run_id="run-step087-gateway",
            settings=RuntimeSettings(model="test-model", api_key="hidden-key"),
            lifecycle_sink=sink,
            session_id="session-step087",
            session_runtime=session_runtime,
            delegated_mcp_identity=identity,
        )
    )
    agents = captured["agents"]
    assert len(agents) == 2
    child, root = agents
    assert child.output_type is GroupwareReadResult
    assert [server.name for server in child.mcp_servers] == ["groupware-read"]
    assert child.name == "OKCanvas Groupware Read-only Assistant"
    assert child.model_settings.values["tool_choice"] == "required"
    assert child.reset_tool_choice is True
    assert root.output_type is OrganizationAssistantResult
    assert root.mcp_servers == []
    assert len(root.tools) == 1
    assert captured["child_session"] is None
    assert captured["child_run_config"]["trace_metadata"]["run_config_inherited"] is False
    assert captured["root_max_turns"] == 2
    assert root.model_settings.values["tool_choice"] == "required"
    assert captured["root_session"] is not None
    assert captured["root_session_closed"] is True
    assert captured["manager_entered"] is True
    assert captured["manager_exited"] is True
    assert result.output.answer == parent_output.answer
    event_types = [event.event_type for event in captured["events"]]
    assert event_types.count("agent.tool.started") == 1
    assert event_types.count("agent.tool.completed") == 1
