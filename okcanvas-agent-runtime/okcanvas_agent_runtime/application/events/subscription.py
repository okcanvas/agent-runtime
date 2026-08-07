from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Protocol

from okcanvas_agent_runtime.domain.runs.models import RunEventRecord, TERMINAL_RUN_STATUSES
from okcanvas_agent_runtime.domain.runs.ports import ProductStore


class RunEventSubscription(Protocol):
    async def subscribe(
        self, *, run_id: str, after_sequence: int
    ) -> AsyncIterator[RunEventRecord | None]: ...


class PollingRunEventSubscription:
    """Project persisted Run Events through an application-owned replay cursor."""

    def __init__(
        self,
        store: ProductStore,
        *,
        poll_interval_seconds: float = 0.1,
        heartbeat_seconds: float = 10.0,
    ) -> None:
        self._store = store
        self._poll_interval_seconds = poll_interval_seconds
        self._heartbeat_seconds = heartbeat_seconds

    async def subscribe(
        self, *, run_id: str, after_sequence: int
    ) -> AsyncIterator[RunEventRecord | None]:
        cursor = max(after_sequence, 0)
        last_output = time.monotonic()
        while True:
            events = self._store.list_events(run_id, after_sequence=cursor)
            for event in events:
                cursor = event.sequence
                last_output = time.monotonic()
                yield event

            run = self._store.get_run(run_id)
            if run.status in TERMINAL_RUN_STATUSES:
                return

            now = time.monotonic()
            if now - last_output >= self._heartbeat_seconds:
                last_output = now
                yield None
            await asyncio.sleep(self._poll_interval_seconds)
