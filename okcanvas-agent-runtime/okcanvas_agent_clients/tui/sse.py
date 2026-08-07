from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from okcanvas_agent_clients.tui.config import TUIClientError


@dataclass(frozen=True)
class SSEMessage:
    event_id: str | None
    event_type: str | None
    data: str


def parse_sse_lines(lines: Iterable[str]) -> Iterator[SSEMessage]:
    event_id: str | None = None
    event_type: str | None = None
    data_lines: list[str] = []

    def dispatch() -> SSEMessage | None:
        nonlocal event_id, event_type, data_lines
        if not data_lines:
            event_id = None
            event_type = None
            return None
        message = SSEMessage(
            event_id=event_id,
            event_type=event_type,
            data="\n".join(data_lines),
        )
        event_id = None
        event_type = None
        data_lines = []
        return message

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "":
            message = dispatch()
            if message is not None:
                yield message
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "id":
            event_id = value
        elif field == "event":
            event_type = value
        elif field == "data":
            data_lines.append(value)

    message = dispatch()
    if message is not None:
        yield message


def parse_sse_json(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    for message in parse_sse_lines(lines):
        try:
            payload = json.loads(message.data)
        except json.JSONDecodeError as exc:
            raise TUIClientError(
                "TUI_SSE_DATA_INVALID",
                "Control API persisted SSE returned invalid JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise TUIClientError(
                "TUI_SSE_DATA_INVALID",
                "Control API persisted SSE returned a non-object payload",
            )
        yield payload
