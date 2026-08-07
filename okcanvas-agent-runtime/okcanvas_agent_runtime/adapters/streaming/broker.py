from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from okcanvas_agent_runtime.adapters.streaming.models import NativeSDKStreamEvent

_SENTINEL = object()


@dataclass
class _Channel:
    events: deque[NativeSDKStreamEvent]
    subscribers: set[asyncio.Queue[NativeSDKStreamEvent | object]] = field(default_factory=set)
    next_sequence: int = 1
    completed: bool = False


class InMemoryNativeSDKStreamBroker:
    """Bounded, process-local streaming broker.

    This broker is intentionally not durable. Product/canonical Events remain in SQLite.
    Subscriber disconnect only removes that subscriber and never cancels Product execution.
    """

    def __init__(self, *, max_runs: int = 128, max_events_per_run: int = 512) -> None:
        if max_runs < 1 or max_events_per_run < 1:
            raise ValueError("Native stream broker limits must be positive")
        self._max_runs = max_runs
        self._max_events_per_run = max_events_per_run
        self._channels: OrderedDict[str, _Channel] = OrderedDict()
        self._lock = asyncio.Lock()

    async def register(self, run_id: str) -> None:
        async with self._lock:
            self._channel_locked(run_id)

    async def has_channel(self, run_id: str) -> bool:
        async with self._lock:
            return run_id in self._channels

    async def publish(
        self,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> NativeSDKStreamEvent:
        async with self._lock:
            channel = self._channel_locked(run_id)
            if channel.completed:
                raise RuntimeError("NATIVE_SDK_STREAM_ALREADY_COMPLETED")
            event = NativeSDKStreamEvent.create(
                run_id=run_id,
                sequence=channel.next_sequence,
                event_type=event_type,
                payload=dict(payload),
            )
            channel.next_sequence += 1
            channel.events.append(event)
            subscribers = tuple(channel.subscribers)
        for queue in subscribers:
            queue.put_nowait(event)
        return event

    async def complete(
        self,
        *,
        run_id: str,
        state: str,
        detail_type: str | None = None,
    ) -> None:
        event_type = "sdk.stream.completed" if state == "SUCCEEDED" else "sdk.stream.failed"
        payload: dict[str, object] = {"state": state, "detail_type": detail_type}
        async with self._lock:
            channel = self._channel_locked(run_id)
            if channel.completed:
                return
            event = NativeSDKStreamEvent.create(
                run_id=run_id,
                sequence=channel.next_sequence,
                event_type=event_type,
                payload=payload,
            )
            channel.next_sequence += 1
            channel.events.append(event)
            channel.completed = True
            subscribers = tuple(channel.subscribers)
        for queue in subscribers:
            queue.put_nowait(event)
            queue.put_nowait(_SENTINEL)

    async def subscribe(
        self,
        *,
        run_id: str,
        after_sequence: int = 0,
    ) -> AsyncIterator[NativeSDKStreamEvent]:
        queue: asyncio.Queue[NativeSDKStreamEvent | object] = asyncio.Queue()
        async with self._lock:
            channel = self._channel_locked(run_id)
            replay = [item for item in channel.events if item.sequence > after_sequence]
            completed = channel.completed
            channel.subscribers.add(queue)
        for event in replay:
            queue.put_nowait(event)
        if completed:
            queue.put_nowait(_SENTINEL)
        try:
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    break
                assert isinstance(item, NativeSDKStreamEvent)
                yield item
        finally:
            async with self._lock:
                channel = self._channels.get(run_id)
                if channel is not None:
                    channel.subscribers.discard(queue)

    async def snapshot(self, run_id: str) -> list[NativeSDKStreamEvent]:
        async with self._lock:
            channel = self._channels.get(run_id)
            return list(channel.events) if channel else []

    def _channel_locked(self, run_id: str) -> _Channel:
        channel = self._channels.get(run_id)
        if channel is None:
            channel = _Channel(events=deque(maxlen=self._max_events_per_run))
            self._channels[run_id] = channel
        else:
            self._channels.move_to_end(run_id)
        self._evict_locked()
        return channel

    def _evict_locked(self) -> None:
        while len(self._channels) > self._max_runs:
            removable = next(
                (
                    key
                    for key, channel in self._channels.items()
                    if channel.completed and not channel.subscribers
                ),
                None,
            )
            if removable is None:
                break
            self._channels.pop(removable, None)
