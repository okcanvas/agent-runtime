from __future__ import annotations

from tests.artifact_test_support import artifact_service
from tests.artifact_test_support import read_json_artifact

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import asyncio
import json
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import (
    AgentStatus,
    CodingAgentResult,
    UsageSummary,
)
from okcanvas_agent_runtime.application.execution import (
    GatewayLifecycleEvent,
    GenericAgentExecutionService,
    GenericExecutionErrorCode,
    GenericGatewayRunResult,
)
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import InvocationKind, InvocationState, RunStatus, TaskStatus

ROOT = Path(__file__).resolve().parents[1]


class SuccessfulGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        assert definition.agent_id == "coding-agent"
        assert definition.tools == ()
        assert definition.handoffs == ()
        assert request == "Inspect only this supplied text"
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_test"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PARTIAL,
                summary="Only supplied text was analyzed.",
                findings=[],
                unverified=["Repository state"],
            ),
            usage=UsageSummary(
                requests=1,
                input_tokens=40,
                output_tokens=20,
                total_tokens=60,
                cached_input_tokens=10,
                reasoning_tokens=2,
            ),
            trace_id="trace_generic",
            response_id="resp_test",
            sdk_version="0.19.0",
        )


class FailingGateway:
    async def run(self, **kwargs):
        raise GenericExecutionFailure(
            GenericExecutionErrorCode.SDK_RUN_FAILED,
            "SDK failed",
            retryable=True,
        )


def _service(tmp_path: Path, gateway) -> tuple[GenericAgentExecutionService, SQLiteProductStore]:
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    service = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=store,
        gateway=gateway,
        artifact_root=tmp_path / "artifacts",
        artifact_service=artifact_service(store, tmp_path / "artifacts"),
    )
    return service, store


def test_success_links_task_run_events_usage_and_artifact(tmp_path: Path) -> None:
    service, store = _service(tmp_path, SuccessfulGateway())
    envelope = asyncio.run(
        service.run(
            agent_definition_id="coding-agent",
            request=" Inspect only this supplied text ",
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.state == "SUCCEEDED"
    assert envelope.task_id and envelope.run_id and envelope.artifact_id
    task = store.get_task(envelope.task_id)
    run = store.get_run(envelope.run_id)
    assert task.status is TaskStatus.SUCCEEDED
    assert run.status is RunStatus.SUCCEEDED
    assert run.trace_id == "trace_generic"
    assert (run.input_tokens, run.output_tokens, run.total_tokens) == (40, 20, 60)
    invocations = store.list_agent_invocations(run.run_id)
    assert len(invocations) == 1
    assert invocations[0].invocation_kind is InvocationKind.ROOT
    assert invocations[0].state is InvocationState.SUCCEEDED
    assert (invocations[0].input_tokens, invocations[0].output_tokens, invocations[0].total_tokens) == (40, 20, 60)
    assert invocations[0].workspace_access.value == "none"
    events = store.list_events(run.run_id)
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    event_types = [event.event_type for event in events]
    assert event_types == [
        "run.created",
        "run.started",
        "agent.definition.resolved",
        "agent.started",
        "model.started",
        "model.completed",
        "agent.completed",
        "artifact.created",
        "run.completed",
    ]
    artifact = store.verify_artifact(envelope.artifact_id)
    payload = read_json_artifact(store, tmp_path / "artifacts", envelope.artifact_id)
    assert payload["summary"] == "Only supplied text was analyzed."
    database_bytes = (tmp_path / "product.sqlite3").read_bytes()
    assert b"Inspect only this supplied text" not in database_bytes
    assert b"Inspect only the information actually provided" not in database_bytes
    assert b"secret" not in database_bytes


def test_gateway_failure_transitions_product_state_to_failed(tmp_path: Path) -> None:
    service, store = _service(tmp_path, FailingGateway())
    envelope = asyncio.run(
        service.run(
            agent_definition_id="coding-agent",
            request="do work",
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error and envelope.error.code is GenericExecutionErrorCode.SDK_RUN_FAILED
    assert envelope.task_id and envelope.run_id
    assert store.get_task(envelope.task_id).status is TaskStatus.FAILED
    assert store.get_run(envelope.run_id).status is RunStatus.FAILED
    invocations = store.list_agent_invocations(envelope.run_id)
    assert len(invocations) == 1 and invocations[0].state is InvocationState.FAILED
    assert [item.event_type for item in store.list_events(envelope.run_id)][-2:] == [
        "agent.failed",
        "run.failed",
    ]


def test_unconfirmed_run_creates_no_product_records(tmp_path: Path) -> None:
    service, store = _service(tmp_path, SuccessfulGateway())
    envelope = asyncio.run(
        service.run(
            agent_definition_id="coding-agent",
            request="do work",
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=False,
        )
    )
    assert envelope.error and envelope.error.code is GenericExecutionErrorCode.LIVE_OPT_IN_REQUIRED
    with store._connection() as connection:  # acceptance of no persistence before opt-in
        assert connection.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 0


def test_lifecycle_persistence_failure_is_not_misclassified_as_sdk_failure(tmp_path: Path) -> None:
    class EventFailingStore(SQLiteProductStore):
        def append_event(self, run_id, *, event_type, source, payload=None, payload_schema_version="okcanvas-event-payload-v1"):
            if event_type == "agent.started":
                raise OSError("forced event failure")
            return super().append_event(
                run_id,
                event_type=event_type,
                source=source,
                payload=payload,
                payload_schema_version=payload_schema_version,
            )

    store = EventFailingStore(tmp_path / "product.sqlite3")
    store.initialize()
    service = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=store,
        gateway=SuccessfulGateway(),
        artifact_root=tmp_path / "artifacts",
            artifact_service=artifact_service(store, tmp_path / "artifacts"),
    )
    envelope = asyncio.run(
        service.run(
            agent_definition_id="coding-agent",
            request="Inspect only this supplied text",
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.error and envelope.error.code is GenericExecutionErrorCode.PRODUCT_STATE_FAILED
    assert envelope.run_id
    assert store.get_run(envelope.run_id).status is RunStatus.FAILED
