from __future__ import annotations

from tests.artifact_test_support import artifact_service
from tests.artifact_test_support import read_json_artifact

import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.application.execution import (
    GatewayLifecycleEvent,
    GenericAgentExecutionService,
    GenericExecutionErrorCode,
    GenericGatewayRunResult,
    OpenAIGenericAgentGateway,
)
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.application.orchestration import (
    BoundedOrchestrationPolicyCatalog,
    BoundedOrchestrationResult,
    aggregate_child_results,
)
from okcanvas_agent_runtime.application.orchestration import openai_runtime as orchestration_module
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import InvocationKind, InvocationState, RunStatus, TaskStatus
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness

ROOT = Path(__file__).resolve().parents[1]
ROOT_AGENT = "bounded-orchestration-manager-agent"
ARCH_AGENT = "bounded-orchestration-architecture-agent"
RISK_AGENT = "bounded-orchestration-risk-agent"


def _usage(input_tokens: int, output_tokens: int, *, cached: int = 0, reasoning: int = 0):
    return SimpleNamespace(
        requests=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=cached),
        output_tokens_details=SimpleNamespace(reasoning_tokens=reasoning),
    )


def _coding_result(status: AgentStatus, summary: str) -> CodingAgentResult:
    return CodingAgentResult(status=status, summary=summary, findings=[], unverified=[])


def _install_concurrent_fake_agents(monkeypatch, captured: dict[str, object]) -> None:
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"
    both_entered = asyncio.Event()
    risk_completed = asyncio.Event()
    active = 0

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.setdefault("agent_names", []).append(kwargs["name"])
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs
            captured.setdefault("run_configs", []).append(kwargs)

    class FakeRunHooks:
        pass

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class FakeRunner:
        @classmethod
        async def run(cls, agent, request, *, max_turns, hooks, run_config, session):
            nonlocal active
            captured["run_calls"] = int(captured.get("run_calls", 0)) + 1
            captured.setdefault("requests", []).append(request)
            captured.setdefault("sessions", []).append(session)
            captured.setdefault("max_turns", []).append(max_turns)
            active += 1
            captured["max_active"] = max(int(captured.get("max_active", 0)), active)
            if active == 2:
                both_entered.set()
            await both_entered.wait()
            await hooks.on_agent_start(SimpleNamespace(usage=_usage(0, 0)), agent)
            await hooks.on_llm_start(
                SimpleNamespace(usage=_usage(0, 0)), agent, agent.instructions, [{"role": "user"}]
            )
            if "Architecture" in agent.name:
                await risk_completed.wait()
                usage = _usage(11, 4, cached=2, reasoning=1)
                output = _coding_result(AgentStatus.PASS, "Architecture complete.")
            else:
                usage = _usage(13, 6, cached=3, reasoning=2)
                output = _coding_result(AgentStatus.PARTIAL, "Risk review complete.")
                risk_completed.set()
            response = SimpleNamespace(
                response_id=f"response-{agent.name}",
                request_id=f"request-{agent.name}",
                output=[SimpleNamespace(type="reasoning")],
            )
            await hooks.on_llm_end(SimpleNamespace(usage=usage), agent, response)
            await hooks.on_agent_end(SimpleNamespace(usage=usage), agent, output)
            active -= 1

            class Result:
                context_wrapper = SimpleNamespace(usage=usage)

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is CodingAgentResult
                    assert raise_if_incorrect_type is True
                    return output

            return Result()

        @classmethod
        def run_streamed(cls, *args, **kwargs):
            raise AssertionError("STEP062 must use two direct Runner.run calls")

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.retry_policies = types.SimpleNamespace(never=lambda: (lambda _context: False))
    fake_agents.gen_trace_id = lambda: "trace-step062"
    fake_agents.set_default_openai_key = lambda value: captured.setdefault("api_key", value)

    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(orchestration_module.importlib.metadata, "version", lambda name: "0.19.0")


def test_policy_definition_and_runtime_binding_are_closed() -> None:
    definitions = AgentDefinitionCatalog(ROOT)
    root = definitions.resolve(ROOT_AGENT)
    children = tuple(definitions.resolve(item) for item in root.orchestration_children)
    policy = BoundedOrchestrationPolicyCatalog(ROOT).resolve()
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root)

    assert root.orchestration_children == (ARCH_AGENT, RISK_AGENT)
    assert root.output_contract == "BoundedOrchestrationResult"
    assert not root.tools and not root.mcp_servers and not root.handoffs and not root.agent_tools
    assert root.session_mode == "disabled" and root.workspace_access == "none"
    assert [item.output_contract for item in children] == ["CodingAgentResult", "CodingAgentResult"]
    assert all(
        not item.tools
        and not item.mcp_servers
        and not item.handoffs
        and not item.agent_tools
        and not item.orchestration_children
        and item.session_mode == "disabled"
        and item.workspace_access == "none"
        for item in children
    )
    assert policy.child_count == 2 and policy.max_parallelism == 2 and policy.max_depth == 1
    assert policy.failure_mode == "ALL_REQUIRED_FAIL_FAST"
    assert policy.cancellation_mode == "CANCEL_PENDING_SIBLINGS"
    assert policy.aggregation_mode == "DECLARATION_ORDER_STRUCTURED"
    assert binding.execution_path == "bounded-multi-agent-orchestration-v1"
    assert binding.orchestration_policy is not None
    assert len(binding.orchestration_runtime_sha256 or "") == 64
    assert [item["ordinal"] for item in binding.child_agents] == [1, 2]
    assert [item["child_agent_id"] for item in binding.child_agents] == [ARCH_AGENT, RISK_AGENT]
    assert all(len(str(item["child_runtime_binding_sha256"])) == 64 for item in binding.child_agents)


def test_gateway_executes_two_siblings_concurrently_and_aggregates_declared_order(monkeypatch) -> None:
    captured: dict[str, object] = {"events": []}
    _install_concurrent_fake_agents(monkeypatch, captured)

    async def sink(event):
        captured["events"].append(event)

    result = asyncio.run(
        OpenAIGenericAgentGateway().run(
            definition=AgentDefinitionCatalog(ROOT).resolve(ROOT_AGENT),
            request="Review this bounded request.",
            run_id="run-step062-unit",
            settings=RuntimeSettings(model="test-model", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
    )

    assert captured["api_key"] == "hidden-key"
    assert captured["run_calls"] == 2
    assert captured["max_active"] == 2
    assert captured["sessions"] == [None, None]
    assert len(captured["agent_names"]) == 2
    assert all(config["group_id"] == "run-step062-unit" for config in captured["run_configs"])
    assert all(config["trace_id"] == "trace-step062" for config in captured["run_configs"])
    assert [config["trace_metadata"]["orchestration_ordinal"] for config in captured["run_configs"]] == [1, 2]
    assert result.response_id is None
    assert result.trace_id == "trace-step062"
    assert result.sdk_version == "0.19.0"
    assert result.usage == UsageSummary(
        requests=2,
        input_tokens=24,
        output_tokens=10,
        total_tokens=34,
        cached_input_tokens=5,
        reasoning_tokens=3,
    )
    assert isinstance(result.output, BoundedOrchestrationResult)
    assert result.output.status is AgentStatus.PARTIAL
    assert [item.ordinal for item in result.output.children] == [1, 2]
    assert [item.agent_definition_id for item in result.output.children] == [ARCH_AGENT, RISK_AGENT]
    events = captured["events"]
    starts = [event.payload["ordinal"] for event in events if event.event_type == "orchestration.child.started"]
    completions = [event.payload["ordinal"] for event in events if event.event_type == "orchestration.child.completed"]
    assert starts == [1, 2]
    assert completions == [2, 1]
    assert [event.event_type for event in events].count("orchestration.completed") == 1


class SuccessfulOrchestrationGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink, **kwargs):
        definitions = AgentDefinitionCatalog(ROOT)
        policy = BoundedOrchestrationPolicyCatalog(ROOT).resolve()
        child1 = definitions.resolve(ARCH_AGENT)
        child2 = definitions.resolve(RISK_AGENT)
        usage1 = UsageSummary(requests=1, input_tokens=10, output_tokens=4, total_tokens=14)
        usage2 = UsageSummary(requests=1, input_tokens=12, output_tokens=5, total_tokens=17)
        result1 = _coding_result(AgentStatus.PASS, "Architecture complete.")
        result2 = _coding_result(AgentStatus.PARTIAL, "Risk review complete.")
        await lifecycle_sink(GatewayLifecycleEvent("orchestration.started", {"root_agent_id": definition.agent_id}))
        for ordinal, child in enumerate((child1, child2), start=1):
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "orchestration.child.started",
                    {"ordinal": ordinal, "agent_id": child.agent_id},
                )
            )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "orchestration.child.completed",
                {"ordinal": 2, "agent_id": child2.agent_id, "usage": usage2.model_dump(mode="json")},
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "orchestration.child.completed",
                {"ordinal": 1, "agent_id": child1.agent_id, "usage": usage1.model_dump(mode="json")},
            )
        )
        aggregate = aggregate_child_results(
            children=((1, child1, result1, usage1), (2, child2, result2, usage2)),
            policy=policy,
        )
        total = UsageSummary(requests=2, input_tokens=22, output_tokens=9, total_tokens=31)
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "orchestration.completed",
                {"root_agent_id": definition.agent_id, "usage": total.model_dump(mode="json")},
            )
        )
        return GenericGatewayRunResult(
            output=aggregate,
            usage=total,
            trace_id="trace-step062-service",
            response_id=None,
            sdk_version="0.19.0",
        )


class FailingOrchestrationGateway:
    async def run(self, *, definition, lifecycle_sink, **kwargs):
        usage = UsageSummary(requests=1, input_tokens=7, output_tokens=0, total_tokens=7)
        await lifecycle_sink(GatewayLifecycleEvent("orchestration.started", {"root_agent_id": definition.agent_id}))
        await lifecycle_sink(
            GatewayLifecycleEvent("orchestration.child.started", {"ordinal": 1, "agent_id": ARCH_AGENT})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent("orchestration.child.started", {"ordinal": 2, "agent_id": RISK_AGENT})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "orchestration.child.failed",
                {"ordinal": 1, "agent_id": ARCH_AGENT, "usage": usage.model_dump(mode="json")},
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "orchestration.child.cancelled",
                {"ordinal": 2, "agent_id": RISK_AGENT, "usage": UsageSummary().model_dump(mode="json")},
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent("orchestration.failed", {"failed_ordinal": 1, "artifact_created": False})
        )
        raise GenericExecutionFailure(
            GenericExecutionErrorCode.SDK_RUN_FAILED,
            "Bounded orchestration child SDK run failed",
            retryable=True,
            usage=usage,
            trace_id="trace-step062-failure",
        )


def _service(tmp_path: Path, gateway) -> tuple[GenericAgentExecutionService, SQLiteProductStore]:
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    return (
        GenericAgentExecutionService(
            runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
            definitions=AgentDefinitionCatalog(ROOT),
            store=store,
            gateway=gateway,
            artifact_root=tmp_path / "artifacts",
            artifact_service=artifact_service(store, tmp_path / "artifacts"),
        ),
        store,
    )


def test_product_run_records_root_and_two_child_invocations_and_one_artifact(tmp_path: Path) -> None:
    service, store = _service(tmp_path, SuccessfulOrchestrationGateway())
    envelope = asyncio.run(
        service.run(
            agent_definition_id=ROOT_AGENT,
            request="Review this bounded request.",
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.state == "SUCCEEDED"
    assert envelope.run_id and envelope.task_id and envelope.artifact_id
    assert envelope.response_id is None
    assert store.get_task(envelope.task_id).status is TaskStatus.SUCCEEDED
    assert store.get_run(envelope.run_id).status is RunStatus.SUCCEEDED
    invocations = store.list_agent_invocations(envelope.run_id)
    assert len(invocations) == 3
    root = next(item for item in invocations if item.invocation_kind is InvocationKind.ROOT)
    children = [item for item in invocations if item.invocation_kind is InvocationKind.ORCHESTRATION_CHILD]
    assert root.state is InvocationState.SUCCEEDED
    assert (root.input_tokens, root.output_tokens, root.total_tokens) == (0, 0, 0)
    assert [item.agent_definition_id for item in children] == [ARCH_AGENT, RISK_AGENT]
    assert [item.state for item in children] == [InvocationState.SUCCEEDED, InvocationState.SUCCEEDED]
    assert [(item.input_tokens, item.output_tokens, item.total_tokens) for item in children] == [
        (10, 4, 14),
        (12, 5, 17),
    ]
    artifact = store.verify_artifact(envelope.artifact_id)
    payload = read_json_artifact(store, tmp_path / "artifacts", envelope.artifact_id)
    assert payload["schema_version"] == "okcanvas-bounded-orchestration-result-v1"
    assert [item["ordinal"] for item in payload["children"]] == [1, 2]
    assert [item["agent_definition_id"] for item in payload["children"]] == [ARCH_AGENT, RISK_AGENT]
    event_types = [event.event_type for event in store.list_events(envelope.run_id)]
    assert event_types.count("orchestration.plan.bound") == 1
    assert event_types.count("orchestration.child.started") == 2
    assert event_types.count("orchestration.child.completed") == 2
    assert event_types.count("artifact.created") == 1


def test_child_failure_cancels_sibling_and_creates_no_artifact(tmp_path: Path) -> None:
    service, store = _service(tmp_path, FailingOrchestrationGateway())
    envelope = asyncio.run(
        service.run(
            agent_definition_id=ROOT_AGENT,
            request="Review this bounded request.",
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error and envelope.error.code is GenericExecutionErrorCode.SDK_RUN_FAILED
    assert envelope.run_id and envelope.task_id and envelope.artifact_id is None
    assert store.get_task(envelope.task_id).status is TaskStatus.FAILED
    assert store.get_run(envelope.run_id).status is RunStatus.FAILED
    invocations = store.list_agent_invocations(envelope.run_id)
    root = next(item for item in invocations if item.invocation_kind is InvocationKind.ROOT)
    children = [item for item in invocations if item.invocation_kind is InvocationKind.ORCHESTRATION_CHILD]
    assert root.state is InvocationState.FAILED
    assert (root.input_tokens, root.output_tokens, root.total_tokens) == (0, 0, 0)
    assert [item.state for item in children] == [InvocationState.FAILED, InvocationState.CANCELLED]
    with store._connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM artifact").fetchone()[0] == 0
    event_types = [event.event_type for event in store.list_events(envelope.run_id)]
    assert "orchestration.failed" in event_types
    assert event_types[-2:] == ["agent.failed", "run.failed"]
