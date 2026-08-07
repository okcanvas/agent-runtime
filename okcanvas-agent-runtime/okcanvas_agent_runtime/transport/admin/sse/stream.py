from __future__ import annotations

import json
from collections.abc import AsyncIterator

from okcanvas_agent_runtime.application.admin.projections import event_response
from okcanvas_agent_runtime.application.events import PollingRunEventSubscription, RunEventSubscription


def encode_event(*, event_id: int, event_type: str, data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"


async def persisted_event_stream(
    *,
    run_id: str,
    after_sequence: int,
    subscription: RunEventSubscription | None = None,
    store: object | None = None,
    poll_interval_seconds: float = 0.1,
    heartbeat_seconds: float = 10.0,
) -> AsyncIterator[str]:
    """Encode an Application RunEventSubscription as persisted SSE.

    The ``store`` argument is retained only for the pre-STEP081 public call surface;
    it is immediately wrapped by the Application subscription and never polled here.
    """
    if subscription is None:
        if store is None:
            raise ValueError("Run Event subscription is required")
        subscription = PollingRunEventSubscription(
            store,  # type: ignore[arg-type]
            poll_interval_seconds=poll_interval_seconds,
            heartbeat_seconds=heartbeat_seconds,
        )
    async for event in subscription.subscribe(
        run_id=run_id, after_sequence=after_sequence
    ):
        if event is None:
            yield ": heartbeat\n\n"
            continue
        yield encode_event(
            event_id=event.sequence,
            event_type=event.event_type,
            data=event_response(event).model_dump(mode="json"),
        )
