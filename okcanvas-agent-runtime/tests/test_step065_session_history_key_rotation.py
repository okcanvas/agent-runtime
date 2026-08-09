from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.domain.sessions import (
    SQLiteSessionHistoryRotator,
    SQLiteSessionKeyRotationPolicyCatalog,
    SQLiteSessionPolicyCatalog,
    SQLiteSessionRuntimeService,
    SessionBusyError,
    SessionConfigurationError,
    SessionHistoryKey,
    SessionIntegrityError,
    StrictEncryptedSession,
)
from okcanvas_agent_runtime.adapters.persistence.sessions.rotation import inspect_session_envelope_key_id
from scripts.windows_entrypoint import LocalEnvironmentError, validate_control_api_environment

ROOT = Path(__file__).resolve().parents[1]
OLD_KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
NEW_KEY_TEXT = base64.urlsafe_b64encode(bytes(reversed(range(32)))).decode("ascii")
THIRD_KEY_TEXT = base64.urlsafe_b64encode(bytes([17]) * 32).decode("ascii")
ADMIN = "step065-admin-key-123456"
SUBMITTER = "step065-submitter-key-123456"
PROTECTED = base64.urlsafe_b64encode(bytes([99]) * 32).decode("ascii")
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER,
}


def _runtime(
    root: Path,
    *,
    current: str,
    previous: str | None,
) -> SQLiteSessionRuntimeService:
    runtime = SQLiteSessionRuntimeService(
        root,
        SQLiteSessionPolicyCatalog(ROOT).resolve(),
        history_key=SessionHistoryKey.from_text(current),
        previous_history_key=(SessionHistoryKey.from_text(previous) if previous else None),
        key_rotation_policy=SQLiteSessionKeyRotationPolicyCatalog(ROOT).resolve(),
    )
    runtime.initialize()
    return runtime


def _definition_and_binding():
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    return definition, binding


def _create_session(runtime: SQLiteSessionRuntimeService):
    definition, binding = _definition_and_binding()
    return runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )


def _init_history_schema(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_sessions (
            session_id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS agent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            message_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_agent_messages_session_id
        ON agent_messages(session_id, id);
        """
    )
    conn.commit()
    conn.close()


def _codec(session_id: str, key_text: str) -> StrictEncryptedSession:
    return StrictEncryptedSession(
        session_id=session_id,
        underlying_session=object(),
        key=SessionHistoryKey.from_text(key_text),
    )


def _seed_items(
    runtime: SQLiteSessionRuntimeService,
    session_id: str,
    key_text: str,
    items: list[dict[str, object]],
) -> None:
    _init_history_schema(runtime.history_db)
    codec = _codec(session_id, key_text)
    conn = sqlite3.connect(runtime.history_db)
    conn.execute("INSERT OR IGNORE INTO agent_sessions(session_id) VALUES(?)", (session_id,))
    for item in items:
        envelope = codec._encrypt(item)
        conn.execute(
            "INSERT INTO agent_messages(session_id,message_data) VALUES(?,?)",
            (
                session_id,
                json.dumps(envelope, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
            ),
        )
    conn.commit()
    conn.close()
    with runtime._connection() as catalog:
        catalog.execute(
            "UPDATE product_session SET item_count=? WHERE session_id=?",
            (len(items), session_id),
        )


def _raw_envelopes(path: Path, session_id: str) -> list[dict[str, object]]:
    if not path.exists():
        return []
    conn = sqlite3.connect(path)
    rows = conn.execute(
        "SELECT message_data FROM agent_messages WHERE session_id=? ORDER BY id", (session_id,)
    ).fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]


def test_step065_runtime_info_is_exact() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.bounded_encrypted_sqlite_session_compaction_windows_live_accepted is True
    assert info.step064_focused_tests_windows_live_accepted is True
    assert info.sqlite_session_key_rotation_implemented is True
    assert info.sqlite_session_key_rotation_mode == "explicit-single-session"
    assert info.sqlite_session_key_rotation_automatic is False
    assert info.sqlite_session_key_rotation_max_history_items == 256
    assert info.sqlite_session_key_rotation_resume_incomplete is True
    assert info.sqlite_session_key_rotation_windows_live_accepted is False


def test_step065_rotation_policy_is_exact() -> None:
    policy = SQLiteSessionKeyRotationPolicyCatalog(ROOT).resolve()
    assert policy.policy_id == "local-explicit-single-session-key-rotation-v1"
    assert policy.mode == "EXPLICIT_SINGLE_SESSION"
    assert policy.automatic_rotation is False
    assert policy.resume_incomplete_rotation is True
    assert policy.max_history_items == 256
    assert policy.raw_history_in_events is False
    assert len(policy.policy_sha256) == 64


def test_rotation_reencrypts_all_items_and_updates_catalog(tmp_path: Path) -> None:
    old_runtime = _runtime(tmp_path / "sessions", current=OLD_KEY_TEXT, previous=None)
    record = _create_session(old_runtime)
    items = [
        {"role": "user", "content": "private question"},
        {"role": "assistant", "content": "private answer"},
    ]
    _seed_items(old_runtime, record.session_id, OLD_KEY_TEXT, items)

    runtime = _runtime(tmp_path / "sessions", current=NEW_KEY_TEXT, previous=OLD_KEY_TEXT)
    result = asyncio.run(runtime.rotate_history_key(record.session_id))
    assert result.source_key_id == SessionHistoryKey.from_text(OLD_KEY_TEXT).key_id
    assert result.target_key_id == SessionHistoryKey.from_text(NEW_KEY_TEXT).key_id
    assert result.item_count == 2
    assert result.resumed is False
    assert result.already_current is False

    updated = runtime.get(record.session_id)
    assert updated.history_encryption_key_id == result.target_key_id
    assert updated.active_run_id is None
    envelopes = _raw_envelopes(runtime.history_db, record.session_id)
    assert {inspect_session_envelope_key_id(item) for item in envelopes} == {
        result.target_key_id
    }
    raw_text = runtime.history_db.read_text(errors="ignore")
    assert "private question" not in raw_text
    decoded = [_codec(record.session_id, NEW_KEY_TEXT)._decrypt(item) for item in envelopes]
    assert decoded == items
    with runtime._connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM product_session_key_rotation WHERE session_id=?",
            (record.session_id,),
        ).fetchone()[0] == 0


def test_rotation_requires_previous_key_before_creating_lease(tmp_path: Path) -> None:
    old_runtime = _runtime(tmp_path / "sessions", current=OLD_KEY_TEXT, previous=None)
    record = _create_session(old_runtime)
    _seed_items(old_runtime, record.session_id, OLD_KEY_TEXT, [{"role": "user", "content": "x"}])
    runtime = _runtime(tmp_path / "sessions", current=NEW_KEY_TEXT, previous=None)
    with pytest.raises(SessionConfigurationError, match="PREVIOUS_KEY"):
        asyncio.run(runtime.rotate_history_key(record.session_id))
    assert runtime.get(record.session_id).active_run_id is None


def test_rotation_is_blocked_by_active_turn(tmp_path: Path) -> None:
    old_runtime = _runtime(tmp_path / "sessions", current=OLD_KEY_TEXT, previous=None)
    record = _create_session(old_runtime)
    definition, binding = _definition_and_binding()
    old_runtime.acquire_turn(
        session_id=record.session_id,
        run_id="run_active",
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime = _runtime(tmp_path / "sessions", current=NEW_KEY_TEXT, previous=OLD_KEY_TEXT)
    with pytest.raises(SessionBusyError, match="active Turn"):
        asyncio.run(runtime.rotate_history_key(record.session_id))


def test_rotation_resumes_after_history_commit_before_catalog_finalize(tmp_path: Path) -> None:
    old_runtime = _runtime(tmp_path / "sessions", current=OLD_KEY_TEXT, previous=None)
    record = _create_session(old_runtime)
    _seed_items(old_runtime, record.session_id, OLD_KEY_TEXT, [{"role": "user", "content": "resume"}])
    runtime = _runtime(tmp_path / "sessions", current=NEW_KEY_TEXT, previous=OLD_KEY_TEXT)
    operation_id, source_id, target_id, resumed, already = runtime._prepare_key_rotation(
        record.session_id
    )
    assert operation_id and not resumed and not already
    SQLiteSessionHistoryRotator(
        history_db=runtime.history_db,
        policy=runtime.key_rotation_policy,
    ).rotate(
        session_id=record.session_id,
        source_key_id=source_id,
        source_key=runtime.previous_history_key,
        target_key=runtime.history_key,
    )

    restarted = _runtime(tmp_path / "sessions", current=NEW_KEY_TEXT, previous=None)
    result = asyncio.run(restarted.rotate_history_key(record.session_id))
    assert result.operation_id == operation_id
    assert result.resumed is True
    assert restarted.get(record.session_id).active_run_id is None
    assert restarted.get(record.session_id).history_encryption_key_id == target_id


def test_mixed_key_history_fails_closed_and_explicit_clear_recovers(tmp_path: Path) -> None:
    old_runtime = _runtime(tmp_path / "sessions", current=OLD_KEY_TEXT, previous=None)
    record = _create_session(old_runtime)
    _seed_items(old_runtime, record.session_id, OLD_KEY_TEXT, [{"role": "user", "content": "old"}])
    _seed_items(old_runtime, record.session_id, NEW_KEY_TEXT, [{"role": "assistant", "content": "new"}])
    runtime = _runtime(tmp_path / "sessions", current=NEW_KEY_TEXT, previous=OLD_KEY_TEXT)
    with pytest.raises(SessionIntegrityError, match="mixed or unexpected"):
        asyncio.run(runtime.rotate_history_key(record.session_id))
    assert str(runtime.get(record.session_id).active_run_id).startswith("session_rotation_")
    cleared = asyncio.run(runtime.clear(record.session_id))
    assert cleared.state.value == "CLEARED"
    assert cleared.active_run_id is None
    assert _raw_envelopes(runtime.history_db, record.session_id) == []


def test_empty_and_already_current_sessions_are_idempotent(tmp_path: Path) -> None:
    old_runtime = _runtime(tmp_path / "sessions", current=OLD_KEY_TEXT, previous=None)
    record = _create_session(old_runtime)
    runtime = _runtime(tmp_path / "sessions", current=NEW_KEY_TEXT, previous=OLD_KEY_TEXT)
    rotated = asyncio.run(runtime.rotate_history_key(record.session_id))
    assert rotated.item_count == 0
    assert rotated.already_current is False
    again = asyncio.run(runtime.rotate_history_key(record.session_id))
    assert again.operation_id is None
    assert again.already_current is True


def test_rotation_rejects_invalid_json_and_bounded_overflow(tmp_path: Path) -> None:
    old_runtime = _runtime(tmp_path / "sessions", current=OLD_KEY_TEXT, previous=None)
    record = _create_session(old_runtime)
    _init_history_schema(old_runtime.history_db)
    conn = sqlite3.connect(old_runtime.history_db)
    conn.execute("INSERT INTO agent_sessions(session_id) VALUES(?)", (record.session_id,))
    conn.execute(
        "INSERT INTO agent_messages(session_id,message_data) VALUES(?,?)",
        (record.session_id, "not-json"),
    )
    conn.commit()
    conn.close()
    runtime = _runtime(tmp_path / "sessions", current=NEW_KEY_TEXT, previous=OLD_KEY_TEXT)
    with pytest.raises(SessionIntegrityError, match="invalid JSON"):
        asyncio.run(runtime.rotate_history_key(record.session_id))

    other = _create_session(old_runtime)
    _seed_items(
        old_runtime,
        other.session_id,
        OLD_KEY_TEXT,
        [{"role": "user", "content": str(index)} for index in range(257)],
    )
    with pytest.raises(SessionIntegrityError, match="bounded key rotation"):
        asyncio.run(runtime.rotate_history_key(other.session_id))


def test_control_api_rotation_returns_only_non_secret_metadata(tmp_path: Path) -> None:
    session_root = tmp_path / "sessions"
    old_runtime = _runtime(session_root, current=OLD_KEY_TEXT, previous=None)
    record = _create_session(old_runtime)
    _seed_items(old_runtime, record.session_id, OLD_KEY_TEXT, [{"role": "user", "content": "api secret"}])
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key=ADMIN,
        run_submitter_key=SUBMITTER,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key=PROTECTED,
        session_root=session_root,
        session_history_key=NEW_KEY_TEXT,
        session_history_previous_key=OLD_KEY_TEXT,
    )
    with TestClient(app) as client:
        assert client.post(
            f"/v1/sessions/{record.session_id}/rotate-history-key",
            headers={"X-OKCanvas-Admin-Key": ADMIN},
        ).status_code == 403
        response = client.post(
            f"/v1/sessions/{record.session_id}/rotate-history-key", headers=HEADERS
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["schema_version"] == "okcanvas-session-key-rotation-result-v1"
    assert payload["state"] == "COMPLETED"
    serialized = json.dumps(payload)
    assert OLD_KEY_TEXT not in serialized
    assert NEW_KEY_TEXT not in serialized
    assert "api secret" not in serialized


def test_environment_requires_three_distinct_keys() -> None:
    base = {
        "OKCANVAS_CONTROL_ADMIN_KEY": ADMIN,
        "OKCANVAS_RUN_SUBMITTER_KEY": SUBMITTER,
        "OKCANVAS_PROTECTED_PAYLOAD_KEY": PROTECTED,
        "OKCANVAS_SESSION_HISTORY_KEY": NEW_KEY_TEXT,
        "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY": OLD_KEY_TEXT,
    }
    validate_control_api_environment(base)
    with pytest.raises(LocalEnvironmentError, match="must be distinct"):
        validate_control_api_environment(
            {**base, "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY": NEW_KEY_TEXT}
        )
    with pytest.raises(LocalEnvironmentError, match="must be distinct"):
        validate_control_api_environment(
            {**base, "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY": PROTECTED}
        )
    with pytest.raises(LocalEnvironmentError, match="SESSION_HISTORY_KEY is required"):
        validate_control_api_environment(
            {**base, "OKCANVAS_SESSION_HISTORY_KEY": ""}
        )
