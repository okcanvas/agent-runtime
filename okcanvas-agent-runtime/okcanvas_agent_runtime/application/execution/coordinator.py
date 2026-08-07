from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass

from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.application.execution.service import GenericAgentExecutionService, PreparedGenericExecution
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from okcanvas_agent_runtime.domain.runs.models import TERMINAL_RUN_STATUSES
from okcanvas_agent_runtime.domain.runs.ports import ProductStore


@dataclass(frozen=True)
class ScheduledExecution:
    task_id: str
    run_id: str


class LocalExecutionCoordinator:
    """Single-process coordinator. Durable distributed leasing is intentionally deferred."""

    def __init__(
        self,
        *,
        service: GenericAgentExecutionService,
        store: ProductStore,
        completion_observer: Callable[[str, object | None], object] | None = None,
    ) -> None:
        self._service = service
        self._store = store
        self._completion_observer = completion_observer
        self._tasks: dict[str, asyncio.Task[object]] = {}
        self._lock = asyncio.Lock()

    def set_completion_observer(
        self, observer: Callable[[str, object | None], object] | None
    ) -> None:
        self._completion_observer = observer

    async def schedule(
        self,
        *,
        agent_definition_id: str,
        request: str,
        settings: RuntimeSettings,
        live_opt_in: bool,
    ) -> ScheduledExecution | object:
        prepared = self._service.prepare(
            agent_definition_id=agent_definition_id,
            request=request,
            settings=settings,
            live_opt_in=live_opt_in,
        )
        if not isinstance(prepared, PreparedGenericExecution):
            return prepared

        async with self._lock:
            task = asyncio.create_task(self._execute(prepared, settings))
            self._tasks[prepared.run_id] = task
        return ScheduledExecution(task_id=prepared.task_id, run_id=prepared.run_id)

    async def schedule_prepared(
        self,
        *,
        prepared: PreparedGenericExecution,
        settings: RuntimeSettings,
    ) -> ScheduledExecution:
        async with self._lock:
            existing = self._tasks.get(prepared.run_id)
            if existing is not None:
                return ScheduledExecution(task_id=prepared.task_id, run_id=prepared.run_id)
            task = asyncio.create_task(self._execute(prepared, settings))
            self._tasks[prepared.run_id] = task
        return ScheduledExecution(task_id=prepared.task_id, run_id=prepared.run_id)

    async def _execute(
        self,
        prepared: PreparedGenericExecution,
        settings: RuntimeSettings,
    ) -> object:
        result: object | None = None
        try:
            result = await self._service.execute_prepared(prepared=prepared, settings=settings)
            return result
        finally:
            observer = self._completion_observer
            if observer is not None:
                observed = observer(prepared.run_id, result)
                if inspect.isawaitable(observed):
                    await observed
            async with self._lock:
                self._tasks.pop(prepared.run_id, None)

    async def cancel(self, run_id: str) -> ScheduledExecution:
        run = self._store.get_run(run_id)
        if run.status in TERMINAL_RUN_STATUSES:
            raise RuntimeError("RUN_ALREADY_TERMINAL")

        async with self._lock:
            task = self._tasks.get(run_id)
            if task is not None:
                task.cancel()

        current = self._store.get_run(run_id)
        if current.status not in TERMINAL_RUN_STATUSES:
            self._store.transition_run(
                run_id,
                RunStatus.CANCELLED,
                event_type="run.cancelled",
                source=EventSource.OPERATOR,
                payload={"reason": "local_admin_request"},
                payload_schema_version="okcanvas-run-cancelled-v1",
            )
        task_record = self._store.get_task(run.task_id)
        if task_record.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            self._store.transition_task(run.task_id, TaskStatus.CANCELLED)
        observer = self._completion_observer
        if observer is not None:
            observed = observer(run_id, None)
            if inspect.isawaitable(observed):
                await observed
        return ScheduledExecution(task_id=run.task_id, run_id=run_id)
