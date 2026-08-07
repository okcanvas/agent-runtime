from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyErrorCode
from okcanvas_agent_runtime.agent.tools.codex.readonly_errors import CodexReadOnlyFailure


class CodexThreadState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "okcanvas-codex-thread-v1"
    thread_id: str = Field(min_length=1)
    workspace: str = Field(min_length=1)
    workspace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    updated_at: datetime


def load_thread_state(path: Path | None) -> CodexThreadState | None:
    if path is None or not path.exists():
        return None
    try:
        return CodexThreadState.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        raise CodexReadOnlyFailure(
            CodexReadOnlyErrorCode.THREAD_STATE_INVALID,
            "Codex thread state is invalid",
            detail_type=type(exc).__name__,
        ) from exc


def write_thread_state(
    path: Path, *, thread_id: str, workspace: str, workspace_sha256: str
) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = CodexThreadState(
        thread_id=thread_id,
        workspace=workspace,
        workspace_sha256=workspace_sha256,
        updated_at=datetime.now(timezone.utc),
    ).model_dump_json(indent=2)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_name = handle.name
        os.replace(temporary_name, target)
    except OSError as exc:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise CodexReadOnlyFailure(
            CodexReadOnlyErrorCode.EVIDENCE_WRITE_FAILED,
            "Failed to write Codex thread state",
            detail_type=type(exc).__name__,
        ) from exc
