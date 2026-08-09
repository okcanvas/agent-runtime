from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from tests.artifact_test_support import artifact_service, local_blob_path
from okcanvas_agent_runtime.domain.runs import (
    ArtifactIntegrityError,
    EventSource,
    IntegrityContractError,
    InvalidStateTransitionError,
    RunStatus,
    TaskStatus,
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def store(tmp_path: Path) -> SQLiteProductStore:
    product_store = SQLiteProductStore(tmp_path / "product-state.sqlite3")
    product_store.initialize()
    return product_store


def create_task_and_run(store: SQLiteProductStore) -> tuple[str, str]:
    task = store.create_task(
        task_type="TEST",
        input_sha256=digest("input"),
        agent_definition_id="coding-agent",
        agent_definition_version="v1",
    )
    run = store.create_run(task_id=task.task_id)
    return task.task_id, run.run_id


def test_schema_migration_is_idempotent(store: SQLiteProductStore) -> None:
    assert store.schema_versions() == [1]
    store.initialize()
    assert store.schema_versions() == [1]


def test_task_and_run_survive_store_restart(tmp_path: Path) -> None:
    path = tmp_path / "restart.sqlite3"
    first = SQLiteProductStore(path)
    first.initialize()
    task_id, run_id = create_task_and_run(first)
    first.transition_task(task_id, TaskStatus.RUNNING)
    first.transition_run(run_id, RunStatus.RUNNING, event_type="run.started")

    second = SQLiteProductStore(path)
    second.initialize()
    assert second.get_task(task_id).status is TaskStatus.RUNNING
    assert second.get_run(run_id).status is RunStatus.RUNNING
    assert [event.sequence for event in second.list_events(run_id)] == [1, 2]


def test_task_transition_contract_is_enforced(store: SQLiteProductStore) -> None:
    task = store.create_task(
        task_type="TEST",
        input_sha256=digest("task"),
        agent_definition_id="agent",
        agent_definition_version="v1",
    )
    with pytest.raises(InvalidStateTransitionError):
        store.transition_task(task.task_id, TaskStatus.SUCCEEDED)

    assert store.transition_task(task.task_id, TaskStatus.RUNNING).status is TaskStatus.RUNNING
    assert store.transition_task(task.task_id, TaskStatus.SUCCEEDED).status is TaskStatus.SUCCEEDED
    with pytest.raises(InvalidStateTransitionError):
        store.transition_task(task.task_id, TaskStatus.RUNNING)


def test_terminal_task_rejects_new_run(store: SQLiteProductStore) -> None:
    task = store.create_task(
        task_type="TEST",
        input_sha256=digest("task"),
        agent_definition_id="agent",
        agent_definition_version="v1",
    )
    store.transition_task(task.task_id, TaskStatus.CANCELLED)
    with pytest.raises(IntegrityContractError):
        store.create_run(task_id=task.task_id)


def test_run_transition_and_terminal_event_are_atomic(
    store: SQLiteProductStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_id = create_task_and_run(store)

    def fail_event(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("event write failed")

    monkeypatch.setattr(store, "_insert_event", fail_event)
    with pytest.raises(RuntimeError, match="event write failed"):
        store.transition_run(run_id, RunStatus.RUNNING, event_type="run.started")

    assert store.get_run(run_id).status is RunStatus.CREATED
    assert [event.event_type for event in store.list_events(run_id)] == ["run.created"]


def test_run_terminal_transition_appends_event_in_same_operation(store: SQLiteProductStore) -> None:
    _, run_id = create_task_and_run(store)
    store.transition_run(run_id, RunStatus.RUNNING, event_type="run.started")
    completed = store.transition_run(
        run_id,
        RunStatus.SUCCEEDED,
        event_type="run.completed",
        payload={"result": "ok"},
    )
    assert completed.status is RunStatus.SUCCEEDED
    assert completed.completed_at is not None
    events = store.list_events(run_id)
    assert [event.event_type for event in events] == [
        "run.created",
        "run.started",
        "run.completed",
    ]
    assert events[-1].payload["result"] == "ok"
    assert events[-1].payload["from_status"] == "RUNNING"
    assert events[-1].payload["to_status"] == "SUCCEEDED"


def test_event_sequence_is_append_only_under_concurrency(store: SQLiteProductStore) -> None:
    _, run_id = create_task_and_run(store)

    def append(index: int) -> int:
        return store.append_event(
            run_id,
            event_type="test.concurrent",
            source=EventSource.RUNTIME,
            payload={"index": index},
        ).sequence

    with ThreadPoolExecutor(max_workers=8) as executor:
        sequences = list(executor.map(append, range(24)))

    assert sorted(sequences) == list(range(2, 26))
    events = store.list_events(run_id)
    assert [event.sequence for event in events] == list(range(1, 26))


def test_event_payload_is_canonical_and_hash_verified(store: SQLiteProductStore) -> None:
    _, run_id = create_task_and_run(store)
    event = store.append_event(
        run_id,
        event_type="test.payload",
        source=EventSource.OPERATOR,
        payload={"b": 2, "a": 1},
    )
    expected = hashlib.sha256(b'{"a":1,"b":2}').hexdigest()
    assert event.payload_sha256 == expected
    assert event.payload == {"a": 1, "b": 2}


def test_artifact_metadata_registration_and_blob_verification(store: SQLiteProductStore, tmp_path: Path) -> None:
    _, run_id = create_task_and_run(store)
    service = artifact_service(store, tmp_path / "artifacts")
    artifact = service.create_bytes(
        run_id=run_id,
        artifact_type="result",
        media_type="application/json",
        data=b'{"ok":true}',
    )
    assert artifact.byte_length == len(b'{"ok":true}')
    assert artifact.sha256 == hashlib.sha256(b'{"ok":true}').hexdigest()
    assert service.verify(artifact.artifact_id).verified_at is not None


def test_artifact_blob_missing_and_mismatch_are_detected(store: SQLiteProductStore, tmp_path: Path) -> None:
    _, run_id = create_task_and_run(store)
    root = tmp_path / "artifacts"
    service = artifact_service(store, root)
    artifact = service.create_bytes(
        run_id=run_id,
        artifact_type="patch",
        media_type="text/x-diff",
        data=b"before",
    )
    path = local_blob_path(root, artifact.storage_path)

    path.write_bytes(b"after")
    with pytest.raises(ArtifactIntegrityError) as mismatch:
        service.verify(artifact.artifact_id)
    assert mismatch.value.details["reason"] == "mismatch"

    path.unlink()
    with pytest.raises(ArtifactIntegrityError) as missing:
        service.verify(artifact.artifact_id)
    assert missing.value.details["reason"] == "missing"


def test_raw_input_and_api_key_are_not_store_inputs(store: SQLiteProductStore) -> None:
    sentinel = "openai-test-key-never-persist-this-secret"
    task = store.create_task(
        task_type="TEST",
        input_sha256=digest(sentinel),
        agent_definition_id="agent",
        agent_definition_version="v1",
        protected_payload_ref="vault://task/input/1",
    )
    assert task.input_sha256 == digest(sentinel)
    database_bytes = store.database_path.read_bytes()
    assert sentinel.encode("utf-8") not in database_bytes


def test_invalid_sha_is_rejected_before_database_write(store: SQLiteProductStore) -> None:
    with pytest.raises(IntegrityContractError):
        store.create_task(
            task_type="TEST",
            input_sha256="not-a-sha",
            agent_definition_id="agent",
            agent_definition_version="v1",
        )


def test_database_foreign_keys_are_enabled(store: SQLiteProductStore, tmp_path: Path) -> None:
    with pytest.raises(Exception):
        store.register_artifact(
            run_id="run_missing",
            artifact_type="result",
            storage_ref="local-artifact-v1://run_missing/orphan.blob",
            sha256=hashlib.sha256(b"orphan").hexdigest(),
            byte_length=6,
            media_type="text/plain",
        )

    with sqlite3.connect(store.database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]
    assert count == 0
