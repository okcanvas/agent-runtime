from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import IntegrityContractError


def test_updates_trace_and_usage_without_changing_status(tmp_path: Path) -> None:
    store = SQLiteProductStore(tmp_path / "store.sqlite3")
    store.initialize()
    task = store.create_task(
        task_type="TEST",
        input_sha256=hashlib.sha256(b"input").hexdigest(),
        agent_definition_id="coding-agent",
        agent_definition_version="1.0.0",
    )
    run = store.create_run(task_id=task.task_id)
    updated = store.update_run_execution_metadata(
        run.run_id,
        trace_id="trace_123",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    )
    assert updated.status == run.status
    assert updated.trace_id == "trace_123"
    assert updated.total_tokens == 15


def test_rejects_negative_usage(tmp_path: Path) -> None:
    store = SQLiteProductStore(tmp_path / "store.sqlite3")
    store.initialize()
    task = store.create_task(
        task_type="TEST",
        input_sha256=hashlib.sha256(b"input").hexdigest(),
        agent_definition_id="coding-agent",
        agent_definition_version="1.0.0",
    )
    run = store.create_run(task_id=task.task_id)
    with pytest.raises(IntegrityContractError):
        store.update_run_execution_metadata(
            run.run_id,
            trace_id=None,
            input_tokens=-1,
            output_tokens=0,
            total_tokens=0,
        )
