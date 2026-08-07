from __future__ import annotations

import json
from collections.abc import AsyncIterator

from okcanvas_agent_runtime.adapters.streaming.broker import InMemoryNativeSDKStreamBroker


async def native_sdk_event_stream(
    *,
    broker: InMemoryNativeSDKStreamBroker,
    run_id: str,
    after_sequence: int = 0,
) -> AsyncIterator[str]:
    yield ": ephemeral-native-sdk-stream\n\n"
    async for event in broker.subscribe(run_id=run_id, after_sequence=after_sequence):
        payload = event.model_dump(mode="json")
        yield (
            f"id: {event.sequence}\n"
            f"event: {event.event_type}\n"
            f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
        )
