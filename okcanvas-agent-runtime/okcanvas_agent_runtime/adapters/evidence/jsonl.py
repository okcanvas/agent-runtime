from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_EVENT_BYTES = 1_000_000


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    if hasattr(value, "as_dict"):
        return _json_safe(value.as_dict())
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    if dataclasses.is_dataclass(value):
        return _json_safe(dataclasses.asdict(value))
    return str(value)


class JsonlEventJournal:
    def __init__(self, path: Path):
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sequence = 0
        self._thread_id: str | None = None
        self._event_types: set[str] = set()
        self._item_types: set[str] = set()
        self.path.write_text("", encoding="utf-8")

    @property
    def count(self) -> int:
        return self._sequence

    @property
    def thread_id(self) -> str | None:
        return self._thread_id

    @property
    def event_types(self) -> frozenset[str]:
        return frozenset(self._event_types)

    @property
    def item_types(self) -> frozenset[str]:
        return frozenset(self._item_types)

    async def record_codex_payload(self, payload: Any) -> None:
        event = getattr(payload, "event", payload)
        raw = _json_safe(event)
        event_type = raw.get("type", "unknown") if isinstance(raw, dict) else "unknown"
        thread_id = None
        if isinstance(raw, dict):
            candidate = raw.get("thread_id")
            if isinstance(candidate, str) and candidate.strip():
                thread_id = candidate.strip()
                self._thread_id = thread_id
        self.append(
            event_type=str(event_type),
            payload=raw,
            thread_id=thread_id or self._thread_id,
        )

    def append(self, *, event_type: str, payload: Any, thread_id: str | None = None) -> None:
        self._sequence += 1
        self._event_types.add(event_type)
        safe_payload = _json_safe(payload)
        if isinstance(safe_payload, dict):
            item = safe_payload.get("item")
            if isinstance(item, dict):
                item_type = item.get("type")
                if isinstance(item_type, str) and item_type:
                    self._item_types.add(item_type)
        record = {
            "sequence": self._sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "thread_id": thread_id,
            "payload": safe_payload,
        }
        encoded = json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
        if len(encoded) > MAX_EVENT_BYTES:
            record["payload"] = {
                "truncated": True,
                "original_sha256": hashlib.sha256(encoded).hexdigest(),
                "original_bytes": len(encoded),
            }
            encoded = json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
        with self.path.open("ab") as handle:
            handle.write(encoded)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()
