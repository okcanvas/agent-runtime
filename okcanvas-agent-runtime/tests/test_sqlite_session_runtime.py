from __future__ import annotations

import asyncio
import base64
import sys
import types
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.domain.sessions import (
    ProductSessionState,
    SessionConfigurationError,
    SessionHistoryKey,
    SQLiteSessionPolicyCatalog,
    SQLiteSessionRuntimeService,
    SessionBusyError,
    SessionIntegrityError,
    SessionStateError,
)

ROOT = Path(__file__).resolve().parents[1]
KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")


class FakeSQLiteSession:
    histories: dict[str, list[dict[str, object]]] = {}

    def __init__(self, session_id: str, db_path: str | Path) -> None:
        self.session_id = session_id
        self.db_path = Path(db_path)
        self.closed = False
        self.session_settings = None
        self.histories.setdefault(session_id, [])

    async def get_items(self, limit: int | None = None):
        items = list(self.histories[self.session_id])
        return items[-limit:] if limit is not None else items

    async def add_items(self, items):
        self.histories[self.session_id].extend(items)

    async def pop_item(self):
        if not self.histories[self.session_id]:
            return None
        return self.histories[self.session_id].pop()

    async def clear_session(self):
        self.histories[self.session_id].clear()

    def close(self) -> None:
        self.closed = True


def _install_fake_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("agents")
    module.SQLiteSession = FakeSQLiteSession
    monkeypatch.setitem(sys.modules, "agents", module)


def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _install_fake_agents(monkeypatch)
    FakeSQLiteSession.histories.clear()
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(
        tmp_path / "sessions", policy, SessionHistoryKey.from_text(KEY_TEXT)
    )
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    return policy, runtime, definition, binding


def test_sqlite_session_policy_is_exact() -> None:
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    assert policy.schema_version == "okcanvas-sqlite-session-policy-v3"
    assert policy.session_mode == "sqlite-v1"
    assert policy.max_active_turns == 1
    assert policy.history_limit is None
    assert policy.compaction_enabled is True
    assert policy.compaction_mode == "INPUT_ONLY"
    assert policy.compaction_model == "gpt-4.1"
    assert policy.compaction_trigger_candidate_items == 10
    assert policy.compaction_max_input_items == 256
    assert policy.compaction_store is False
    assert policy.encryption_enabled is True
    assert policy.encryption_mode == "STRICT_AES_256_GCM_HKDF_SHA256_V1"
    assert policy.legacy_plaintext_mode == "REJECT"
    assert policy.ttl_seconds is None
    assert len(policy.policy_sha256) == 64


def test_session_create_get_and_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    assert record.session_id.startswith("session_")
    assert record.state is ProductSessionState.ACTIVE
    assert record.agent_definition_id == definition.agent_id
    assert record.runtime_binding_sha256 == binding.runtime_binding_sha256
    assert record.history_encryption_key_id == SessionHistoryKey.from_text(KEY_TEXT).key_id
    assert record.active_run_id is None
    assert record.turn_count == 0
    assert record.item_count == 0
    assert runtime.get(record.session_id) == record
    assert runtime.list() == (record,)
    assert runtime.catalog_db.parent == (tmp_path / "sessions").resolve()
    assert runtime.history_db.parent == (tmp_path / "sessions").resolve()


def test_one_active_turn_and_release_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    acquired = runtime.acquire_turn(
        session_id=record.session_id,
        run_id="run_a",
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    assert acquired.active_run_id == "run_a"
    with pytest.raises(SessionBusyError):
        runtime.acquire_turn(
            session_id=record.session_id,
            run_id="run_b",
            definition=definition,
            runtime_binding_sha256=binding.runtime_binding_sha256,
        )
    same = runtime.acquire_turn(
        session_id=record.session_id,
        run_id="run_a",
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    assert same.active_run_id == "run_a"
    released = runtime.release_turn(
        session_id=record.session_id,
        run_id="run_a",
        succeeded=True,
        item_count=2,
    )
    assert released.active_run_id is None
    assert released.turn_count == 1
    assert released.item_count == 2


def test_failed_turn_releases_without_increment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.acquire_turn(
        session_id=record.session_id,
        run_id="run_failed",
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    released = runtime.release_turn(
        session_id=record.session_id,
        run_id="run_failed",
        succeeded=False,
        item_count=1,
    )
    assert released.turn_count == 0
    assert released.item_count == 1
    assert released.active_run_id is None


def test_binding_drift_and_clear_are_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    with pytest.raises(SessionIntegrityError):
        runtime.validate_binding(
            session_id=record.session_id,
            definition=definition,
            runtime_binding_sha256="0" * 64,
        )
    session = runtime.sdk_session(record.session_id)
    asyncio.run(session.add_items([{"role": "user"}, {"role": "assistant"}]))
    raw = FakeSQLiteSession.histories[record.session_id]
    assert len(raw) == 2
    assert all(item.get("__okcanvas_session_encrypted__") == 1 for item in raw)
    assert all("role" not in item for item in raw)
    session.close()
    assert asyncio.run(runtime.count_items(record.session_id)) == 2
    cleared = asyncio.run(runtime.clear(record.session_id))
    assert cleared.state is ProductSessionState.CLEARED
    assert cleared.item_count == 0
    assert cleared.turn_count == 0
    assert cleared.cleared_at is not None
    assert asyncio.run(runtime.count_items(record.session_id)) == 0
    with pytest.raises(SessionStateError):
        runtime.validate_binding(
            session_id=record.session_id,
            definition=definition,
            runtime_binding_sha256=binding.runtime_binding_sha256,
        )


def test_active_session_cannot_be_cleared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.acquire_turn(
        session_id=record.session_id,
        run_id="run_active",
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    with pytest.raises(SessionBusyError):
        asyncio.run(runtime.clear(record.session_id))


def test_session_database_symlink_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runtime, _definition, _binding = _runtime(tmp_path, monkeypatch)
    history_db = runtime.history_db
    original_exists = Path.exists
    original_is_symlink = Path.is_symlink

    def simulated_exists(path: Path) -> bool:
        if path == history_db:
            return True
        return original_exists(path)

    def simulated_is_symlink(path: Path) -> bool:
        if path == history_db:
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "exists", simulated_exists)
    monkeypatch.setattr(Path, "is_symlink", simulated_is_symlink)

    with pytest.raises(SessionIntegrityError, match="Session database path is unsafe"):
        runtime.raw_sdk_session("session_" + "a" * 32)


def test_clear_failure_restores_active_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )

    class FailingSession:
        async def clear_session(self):
            raise RuntimeError("clear failed")

        def close(self):
            pass

    monkeypatch.setattr(runtime, "raw_sdk_session", lambda _session_id: FailingSession())
    with pytest.raises(RuntimeError, match="clear failed"):
        asyncio.run(runtime.clear(record.session_id))
    restored = runtime.get(record.session_id)
    assert restored.state is ProductSessionState.ACTIVE
    assert restored.cleared_at is None


def test_interrupted_turn_item_count_update_and_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(definition=definition, runtime_binding_sha256=binding.runtime_binding_sha256)
    runtime.acquire_turn(
        session_id=record.session_id,
        run_id="run_interrupted",
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    session = runtime.sdk_session(record.session_id)
    asyncio.run(session.add_items([{"sequence": 1}, {"sequence": 2}]))
    session.close()
    updated = runtime.update_active_item_count(
        session_id=record.session_id, run_id="run_interrupted", item_count=2
    )
    assert updated.active_run_id == "run_interrupted"
    assert updated.item_count == 2
    session = runtime.sdk_session(record.session_id)
    asyncio.run(session.add_items([{"sequence": 3}, {"sequence": 4}]))
    session.close()
    assert asyncio.run(runtime.rollback_to_item_count(
        session_id=record.session_id, expected_item_count=2
    )) == 2
    released = runtime.release_turn(
        session_id=record.session_id, run_id="run_interrupted", committed=False, item_count=2
    )
    assert released.turn_count == 0
    assert released.item_count == 2
    assert released.active_run_id is None


def test_session_create_requires_history_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_agents(monkeypatch)
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(tmp_path / "sessions", policy)
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    with pytest.raises(SessionConfigurationError, match="OKCANVAS_SESSION_HISTORY_KEY"):
        runtime.create(
            definition=definition,
            runtime_binding_sha256=binding.runtime_binding_sha256,
        )


def test_plaintext_and_tampered_history_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    FakeSQLiteSession.histories.setdefault(record.session_id, []).append(
        {"role": "user", "content": "legacy plaintext"}
    )
    with pytest.raises(SessionIntegrityError, match="plaintext"):
        asyncio.run(runtime.count_items(record.session_id))

    FakeSQLiteSession.histories[record.session_id].clear()
    session = runtime.sdk_session(record.session_id)
    asyncio.run(session.add_items([{"role": "user", "content": "secret"}]))
    session.close()
    envelope = FakeSQLiteSession.histories[record.session_id][0]
    envelope["ciphertext_b64"] = str(envelope["ciphertext_b64"])[:-2] + "AA"
    with pytest.raises(SessionIntegrityError, match="integrity"):
        asyncio.run(runtime.count_items(record.session_id))


def test_history_key_rotation_fails_existing_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    rotated = SessionHistoryKey.from_text(
        base64.urlsafe_b64encode(bytes(reversed(range(32)))).decode("ascii")
    )
    runtime.history_key = rotated
    with pytest.raises(SessionIntegrityError, match="key ID changed"):
        runtime.validate_binding(
            session_id=record.session_id,
            definition=definition,
            runtime_binding_sha256=binding.runtime_binding_sha256,
        )


def test_pre_encryption_catalog_row_migrates_but_cannot_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_agents(monkeypatch)
    root = tmp_path / "sessions"
    root.mkdir(parents=True)
    catalog = root / "catalog.sqlite3"
    import sqlite3

    conn = sqlite3.connect(catalog)
    conn.executescript(
        """
        CREATE TABLE product_session (
            session_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            agent_definition_id TEXT NOT NULL,
            agent_definition_version TEXT NOT NULL,
            agent_definition_sha256 TEXT NOT NULL,
            runtime_binding_sha256 TEXT NOT NULL,
            active_run_id TEXT,
            turn_count INTEGER NOT NULL DEFAULT 0,
            item_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            cleared_at TEXT
        );
        """
    )
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    conn.execute(
        """INSERT INTO product_session VALUES(?,?,?,?,?,?,NULL,0,0,?,?,NULL)""",
        (
            "session_legacy",
            "ACTIVE",
            definition.agent_id,
            definition.version,
            definition.definition_sha256,
            binding.runtime_binding_sha256,
            "2026-08-01T00:00:00Z",
            "2026-08-01T00:00:00Z",
        ),
    )
    conn.commit()
    conn.close()

    runtime = SQLiteSessionRuntimeService(
        root,
        SQLiteSessionPolicyCatalog(ROOT).resolve(),
        SessionHistoryKey.from_text(KEY_TEXT),
    )
    runtime.initialize()
    record = runtime.get("session_legacy")
    assert record.history_encryption_key_id is None
    with pytest.raises(SessionIntegrityError, match="must be cleared and recreated"):
        runtime.validate_binding(
            session_id=record.session_id,
            definition=definition,
            runtime_binding_sha256=binding.runtime_binding_sha256,
        )
    cleared = asyncio.run(runtime.clear(record.session_id))
    assert cleared.state is ProductSessionState.CLEARED
