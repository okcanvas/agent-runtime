from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel

from okcanvas_agent_runtime.core.contracts import RuntimeErrorCode
from okcanvas_agent_runtime.core.errors import RuntimeFailure


def write_run_evidence(path: Path, envelope: BaseModel) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = envelope.model_dump_json(indent=2)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_name = handle.name
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise RuntimeFailure(
            RuntimeErrorCode.EVIDENCE_WRITE_FAILED,
            "Failed to write run evidence",
            detail_type=type(exc).__name__,
        ) from exc
