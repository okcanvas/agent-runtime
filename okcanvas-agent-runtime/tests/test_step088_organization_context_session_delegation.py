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
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.application.execution.contracts import GenericGatewayRunResult, GatewayLifecycleEvent
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationContextSessionDelegationCatalog,
    requires_organization_context_session_delegation,
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
    OrganizationContextReadCitation,
    OrganizationContextReadResult,
    OrganizationContextReadStatus,
    OrganizationAssistantResult,
    UsageSummary,
)

ROOT = Path(__file__).resolve().parents[1]
ORG_CONTEXT_ENV = "OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"
ADMIN_KEY = "step088-admin-key-1234567890"
SUBMITTER_KEY = "step088-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
USER_TOKEN = "step088-user-service-token-123456"


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
                "token_id": "step088-user",
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
    server_path = project / "specs/mcp/servers/organization-context-read/server.json"
    payload = json.loads(server_path.read_text(encoding="utf-8"))
    payload["url_template"] = "https://connector.example.com/tenants/{tenant_id}/mcp"
    server_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return project


class RecordingOrganizationContextGateway:
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
        assert definition.agent_id == "organization-context-session-agent"
        assert session_id
        assert session_runtime is not None
        assert delegated_mcp_identity is not None
        assert delegated_mcp_identity.tenant_id == "tenant-a"
        assert delegated_mcp_identity.principal_id == "alice"
        assert delegated_mcp_identity.roles == ("agent-user",)
        assert requires_organization_context_session_delegation(request)
        sdk_session = session_runtime.sdk_session(session_id)
        try:
            await sdk_session.add_items(
                [
                    {"role": "user", "content": "플랫폼팀 김민수 선임 정보를 조직 문맥에서 알려줘."},
                    {"role": "assistant", "content": "플랫폼개발팀 김민수 선임을 확인했습니다."},
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
                    "to_agent_id": "organization-context-read-agent",
                    "arguments_persisted": False,
                    "result_persisted": False,
                },
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "tool.started",
                {"server_id": "organization-context-read", "tool_name": "resolve_organization_context", "arguments_persisted": False},
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "tool.completed",
                {"server_id": "organization-context-read", "tool_name": "resolve_organization_context", "result_persisted": False},
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "agent.tool.completed",
                {
                    "from_agent_id": definition.agent_id,
                    "to_agent_id": "organization-context-read-agent",
                    "parent_control_retained": True,
                    "result_persisted": False,
                },
            )
        )
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id}))
        return GenericGatewayRunResult(
            output=OrganizationAssistantResult(
                status=AssistantResultStatus.ANSWERED,
                answer="플랫폼개발팀 김민수 선임을 확인했습니다.",
                request_class=AssistantRequestClass.SEARCH_KNOWLEDGE,
                side_effect=AssistantSideEffect.READ,
                citations=[
                    AssistantCitation(
                        source_type="ORGANIZATION_KNOWLEDGE",
                        label="김민수",
                        reference="employee-0017",
                    )
                ],
                completed_actions=[],
                proposed_actions=[],
                pending_approvals=[],
                unverified=[],
                follow_up_state=None,
            ),
            usage=UsageSummary(requests=2, input_tokens=20, output_tokens=12, total_tokens=32),
            trace_id="trace_step088",
            response_id="resp_step088",
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
    raise AssertionError("STEP088 run did not become terminal")


def test_step088_exact_composition_and_runtime_binding() -> None:
    definitions = AgentDefinitionCatalog(ROOT)
    root = definitions.resolve("organization-context-session-agent")
    child = definitions.resolve("organization-context-read-agent")
    composition = OrganizationContextSessionDelegationCatalog(ROOT).resolve(root)
    assert root.agent_tools == (child.agent_id,)
    assert root.session_mode == "sqlite-v1"
    assert root.output_contract == "OrganizationAssistantResult"
    assert child.session_mode == "disabled"
    assert child.output_contract == "OrganizationContextReadResult"
    assert child.mcp_servers == ("organization-context-read",)
    assert composition.policy.root_session_only is True
    assert composition.policy.delegated_identity_required is True
    assert composition.policy.write_enabled is False
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root)
    assert binding.execution_path == "sqlite-session-stateless-organization-context-subagent-execution-v1"
    assert binding.session_policy["organization_context_session_delegation"]["max_depth"] == 1
    assert binding.agent_tool_policy["child_output_contract"] == "OrganizationContextReadResult"
    assert binding.mcp_servers[0]["owner_agent_id"] == "organization-context-read-agent"
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.main_assistant_organization_context_session_delegation_implemented is True
    assert info.main_assistant_organization_context_live_openai_provider_verified is False
    assert info.step088_windows_deterministic_accepted is False


def test_step088_session_route_selects_root_and_declares_stateless_child(tmp_path: Path, monkeypatch) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    decision = router.route(
        request="플랫폼팀 김민수 선임 정보를 조직 문맥에서 알려줘.",
        session_id="session-001",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    assert decision.status.value == "EXECUTABLE"
    assert decision.selected_agent_id == "organization-context-session-agent"
    assert decision.required_capabilities[0].selected_agent_id == "organization-context-read-agent"
    assert decision.matched_rule_id == "organization-context-read-session-stateless-subagent-v1"
    assert "session-owned-organization-context-root-retained" in decision.reasons
    assert "child-session-persistence-disabled" in decision.reasons
    model_request = router.build_model_request(decision, "플랫폼팀 김민수 선임 정보를 조직 문맥에서 알려줘.")
    assert requires_organization_context_session_delegation(model_request) is True
    assert '"selected_agent_definition_id": "organization-context-session-agent"' in model_request
    assert "connector-secret" not in model_request


def test_step088_service_session_preflight_execution_forwards_delegated_identity(
    tmp_path: Path, monkeypatch
) -> None:
    _install_fake_agents(monkeypatch)
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    gateway = RecordingOrganizationContextGateway()
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
        session_response = client.post("/v1/service/sessions", headers=headers, json={"agent_definition_id": "organization-context-session-agent"})
        assert session_response.status_code == 201, session_response.text
        session_id = session_response.json()["session_id"]
        preflight = client.post(
            "/v1/service/assistant/run-submissions/preflight",
            headers=headers,
            json={
                "input": "플랫폼팀 김민수 선임 정보를 조직 문맥에서 알려줘.",
                "model": "test-model",
                "session_id": session_id,
                "idempotency_key": "step088-session-organization_context-0001",
            },
        )
        assert preflight.status_code == 201, preflight.text
        body = preflight.json()
        assert body["route"]["selected_agent_definition_id"] == "organization-context-session-agent"
        assert body["route"]["required_capabilities"][0]["selected_agent_id"] == "organization-context-read-agent"
        submission = body["submission"]
        assert submission["agent_definition_id"] == "organization-context-session-agent"
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
        assert content["request_class"] == "SEARCH_KNOWLEDGE"
        assert content["side_effect"] == "READ"
        assert content["citations"][0]["reference"] == "employee-0017"
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


def _organization_context_model_request() -> str:
    context = {
        "schema_version": "okcanvas-assistant-routing-context-v2",
        "status": "EXECUTABLE",
        "selected_agent_definition_id": "organization-context-session-agent",
        "required_capabilities": ["organization-context-read-v1"],
        "organization_context_read_policy": {
            "policy_id": "organization-context-read-v1",
            "production_sot": "DATABASE",
            "delegated_identity_required": True,
            "write_enabled": False,
        },
        "organization_context_request_hint": {
            "schema_version": "okcanvas-organization-context-request-hint-v1",
            "pattern_id": "entity-field-lookup-v1",
            "intent": "ENTITY_FIELD_LOOKUP",
            "target_expression": "플랫폼팀 김민수 선임",
            "entity_type_hints": ["EMPLOYEE"],
            "requested_fields": ["DETAIL"],
            "preferred_operation": "RESOLVE",
        },
    }
    return (
        "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True)
        + "\n\nUSER REQUEST:\n플랫폼팀 김민수 선임 정보를 조직 문맥에서 알려줘."
    )


def test_step088_generic_gateway_places_mcp_only_on_stateless_child(monkeypatch) -> None:
    captured: dict[str, object] = {"agents": [], "events": []}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeServer:
        name = "organization-context-read"

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

    child_output = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.ANSWERED,
        answer="플랫폼개발팀 김민수 선임을 확인했습니다.",
        queried_operations=["resolve_organization_context"],
        result_count=1,
        catalog_revision=500,
        citations=[OrganizationContextReadCitation(label="김민수", reference="employee-0017")],
        unverified=[],
    )
    parent_output = OrganizationAssistantResult(
        status=AssistantResultStatus.ANSWERED,
        answer="플랫폼개발팀 김민수 선임을 확인했습니다.",
        request_class=AssistantRequestClass.SEARCH_KNOWLEDGE,
        side_effect=AssistantSideEffect.READ,
        citations=[
            AssistantCitation(
                source_type="ORGANIZATION_KNOWLEDGE",
                label="김민수",
                reference="employee-0017",
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
                new_items = [
                    SimpleNamespace(
                        output=json.dumps(
                            {
                                "result_schema_version": (
                                    "okcanvas-organization-context-unified-resolve-tool-result-v1"
                                ),
                                "tool_name": "resolve_organization_context",
                                "catalog_revision": 500,
                                "resolved": True,
                                "ambiguous": False,
                                "records": [
                                    {
                                        "entity_type": "EMPLOYEE",
                                        "entity_id": "employee-0017",
                                        "display_name": "김민수",
                                        "context": {
                                            "department_name": "플랫폼개발팀",
                                            "positions": ["선임"],
                                        },
                                    }
                                ],
                                "changes": [],
                            },
                            ensure_ascii=False,
                        )
                    )
                ]
                context_wrapper = SimpleNamespace(usage=_usage_summary())

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is OrganizationContextReadResult
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
                tool_call_id="step088-agent-tool-call",
                tool_arguments='{"input":"플랫폼팀 김민수 선임"}',
                usage=_usage_summary(),
            )
            await hooks.on_tool_start(context, agent, tool)
            nested_result = await tool.invoke()
            await hooks.on_tool_end(context, agent, tool, nested_result)

            class Result:
                context_wrapper = SimpleNamespace(usage=_usage_summary(20, 10))
                last_response_id = "resp-step088-gateway"
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
    fake_agents.gen_trace_id = lambda: "trace-step088-gateway"
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
            definition=AgentDefinitionCatalog(ROOT).resolve("organization-context-session-agent"),
            request=_organization_context_model_request(),
            run_id="run-step088-gateway",
            settings=RuntimeSettings(model="test-model", api_key="hidden-key"),
            lifecycle_sink=sink,
            session_id="session-step088",
            session_runtime=session_runtime,
            delegated_mcp_identity=identity,
        )
    )
    agents = captured["agents"]
    assert len(agents) == 2
    child, root = agents
    assert child.output_type is OrganizationContextReadResult
    assert [server.name for server in child.mcp_servers] == ["organization-context-read"]
    assert child.name == "OKCanvas Organization Context Read-only Assistant"
    assert child.model_settings.values["tool_choice"] == "resolve_organization_context"
    assert child.reset_tool_choice is True
    assert root.output_type is OrganizationAssistantResult
    assert root.mcp_servers == []
    assert len(root.tools) == 1
    assert captured["child_session"] is None
    assert captured["child_run_config"]["trace_metadata"]["run_config_inherited"] is False
    assert captured["child_run_config"]["trace_metadata"][
        "organization_context_named_tool_choice"
    ] == "resolve_organization_context"
    assert captured["root_max_turns"] == 2
    assert root.model_settings.values["tool_choice"] == "required"
    assert captured["root_session"] is not None
    assert captured["root_session_closed"] is True
    assert captured["manager_entered"] is True
    assert captured["manager_exited"] is True
    assert result.output.answer == parent_output.answer
    event_types = [event.event_type for event in captured["events"]]
    assert event_types.count("agent.tool.started") == 1
    assert event_types.count("agent.tool.output.normalized") == 1
    assert event_types.count("agent.tool.completed") == 1
    normalized_event = next(
        event for event in captured["events"]
        if event.event_type == "agent.tool.output.normalized"
    )
    assert normalized_event.payload["normalization_strategy"] == (
        "product-owned-mcp-evidence-normalization-v1"
    )
    assert normalized_event.payload["strategy"] == "tool-evidence-provenance-alignment-v1"
    assert normalized_event.payload["tool_name"] == "resolve_organization_context"
    assert normalized_event.payload["model_output_persisted"] is False
    assert normalized_event.payload["tool_result_persisted"] is False
