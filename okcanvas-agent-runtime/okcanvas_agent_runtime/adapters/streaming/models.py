from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NativeSDKStreamEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["okcanvas-native-sdk-stream-event-v1"] = (
        "okcanvas-native-sdk-stream-event-v1"
    )
    run_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=1)
    event_type: Literal[
        "sdk.stream.started",
        "model.text.delta",
        "run.item",
        "agent.updated",
        "sdk.stream.completed",
        "sdk.stream.failed",
        "agent.tool.stream.started",
        "agent.tool.agent.updated",
        "agent.tool.model.text.delta",
        "agent.tool.run.item",
        "agent.tool.stream.completed",
    ]
    payload: dict[str, Any]
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        sequence: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> "NativeSDKStreamEvent":
        return cls(
            run_id=run_id,
            sequence=sequence,
            event_type=event_type,
            payload=payload,
            created_at=datetime.now(timezone.utc),
        )
