from __future__ import annotations

import asyncio
from pathlib import Path

from okcanvas_agent_runtime.transport.admin.sse.stream import persisted_event_stream
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore


def test_sse_emits_heartbeat_for_non_terminal_run(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = SQLiteProductStore(tmp_path / "product.sqlite3")
        store.initialize()
        task = store.create_task(
            task_type="TEST",
            input_sha256="0" * 64,
            agent_definition_id="coding-agent",
            agent_definition_version="1.0.0",
        )
        run = store.create_run(task_id=task.task_id)
        stream = persisted_event_stream(
            store=store,
            run_id=run.run_id,
            after_sequence=1,
            poll_interval_seconds=0.001,
            heartbeat_seconds=0.001,
        )
        value = await anext(stream)
        assert value == ": heartbeat\n\n"
        await stream.aclose()

    asyncio.run(scenario())
