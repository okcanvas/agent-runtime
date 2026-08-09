from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.domain.sessions import (
    SessionConfigurationError,
    SessionHistoryKey,
    SessionIntegrityError,
    SQLiteSessionPolicyCatalog,
    SQLiteSessionRuntimeService,
    StrictEncryptedSession,
    generate_session_history_key,
)

ROOT = Path(__file__).resolve().parents[1]
KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ROTATED_KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")


class MemorySession:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []
        self.session_settings = None

    async def get_items(self, limit: int | None = None):
        values = list(self.items)
        return values[-limit:] if limit is not None else values

    async def add_items(self, items):
        self.items.extend(items)

    async def pop_item(self):
        return self.items.pop() if self.items else None

    async def clear_session(self):
        self.items.clear()


class FakeSQLiteSession(MemorySession):
    histories: dict[str, list[dict[str, object]]] = {}

    def __init__(self, session_id: str, db_path: str | Path) -> None:
        super().__init__()
        self.session_id = session_id
        self.db_path = Path(db_path)
        self.items = self.histories.setdefault(session_id, [])

    def close(self) -> None:
        pass


def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = types.ModuleType("agents")
    module.SQLiteSession = FakeSQLiteSession
    monkeypatch.setitem(sys.modules, "agents", module)
    FakeSQLiteSession.histories.clear()
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(
        tmp_path / "sessions", policy, SessionHistoryKey.from_text(KEY_TEXT)
    )
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    return runtime, definition, binding


def test_step063_runtime_info_and_policy_are_exact() -> None:
    info = RuntimeInfo()
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.strict_encrypted_sqlite_session_history_implemented is True
    assert info.strict_encrypted_sqlite_session_history_policy_id == "local-strict-encrypted-sqlite-session-v1"
    assert info.strict_encrypted_sqlite_session_history_envelope_version == 1
    assert info.strict_encrypted_sqlite_session_history_key_derivation == "PER_SESSION_HKDF_SHA256_V1"
    assert info.strict_encrypted_sqlite_session_history_legacy_plaintext_mode == "REJECT"
    assert info.strict_encrypted_sqlite_session_history_clear_without_decrypt is True
    assert info.strict_encrypted_sqlite_session_history_deterministic_accepted is True
    assert info.strict_encrypted_sqlite_session_history_windows_live_accepted is True
    assert policy.encryption_enabled is True
    assert policy.compaction_enabled is True
    assert policy.ttl_seconds is None


def test_session_history_key_accepts_exact_formats_and_generator() -> None:
    hex_key = bytes(range(32)).hex()
    assert SessionHistoryKey.from_text(hex_key).key_id == SessionHistoryKey.from_text(KEY_TEXT).key_id
    generated = generate_session_history_key()
    assert len(base64.urlsafe_b64decode(generated)) == 32
    with pytest.raises(SessionConfigurationError):
        SessionHistoryKey.from_text("too-short")


def test_strict_wrapper_encrypts_every_item_and_round_trips_without_plaintext() -> None:
    backend = MemorySession()
    session = StrictEncryptedSession(
        session_id="session_test", underlying_session=backend, key=SessionHistoryKey.from_text(KEY_TEXT)
    )
    item = {"role": "user", "content": "NEVER_PERSIST_PLAINTEXT"}
    asyncio.run(session.add_items([item]))
    raw = backend.items[0]
    assert set(raw) == {
        "__okcanvas_session_encrypted__", "version", "key_id", "nonce_b64", "ciphertext_b64"
    }
    assert "role" not in raw and "content" not in raw
    assert "NEVER_PERSIST_PLAINTEXT" not in json.dumps(raw)
    assert asyncio.run(session.get_items()) == [item]


def test_plaintext_tamper_and_wrong_key_are_rejected() -> None:
    backend = MemorySession()
    session = StrictEncryptedSession(
        session_id="session_test", underlying_session=backend, key=SessionHistoryKey.from_text(KEY_TEXT)
    )
    backend.items.append({"role": "user", "content": "plaintext"})
    with pytest.raises(SessionIntegrityError, match="plaintext"):
        asyncio.run(session.get_items())
    backend.items.clear()
    asyncio.run(session.add_items([{"role": "user", "content": "secret"}]))
    backend.items[0]["ciphertext_b64"] = str(backend.items[0]["ciphertext_b64"])[:-2] + "AA"
    with pytest.raises(SessionIntegrityError):
        asyncio.run(session.get_items())
    wrong = StrictEncryptedSession(
        session_id="session_test", underlying_session=backend,
        key=SessionHistoryKey.from_text(ROTATED_KEY_TEXT),
    )
    with pytest.raises(SessionIntegrityError, match="key ID"):
        asyncio.run(wrong.get_items())


def test_rotated_key_fails_assert_update_and_release_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(definition=definition, runtime_binding_sha256=binding.runtime_binding_sha256)
    runtime.acquire_turn(
        session_id=record.session_id, run_id="run_a", definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.history_key = SessionHistoryKey.from_text(ROTATED_KEY_TEXT)
    with pytest.raises(SessionIntegrityError, match="key ID changed"):
        runtime.assert_active_turn(session_id=record.session_id, run_id="run_a")
    with pytest.raises(SessionIntegrityError, match="key ID changed"):
        runtime.update_active_item_count(session_id=record.session_id, run_id="run_a", item_count=1)
    with pytest.raises(SessionIntegrityError, match="key ID changed"):
        runtime.release_turn(session_id=record.session_id, run_id="run_a", succeeded=False, item_count=0)


def test_pre_encryption_session_can_be_cleared_without_decryption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, definition, binding = _runtime(tmp_path, monkeypatch)
    record = runtime.create(definition=definition, runtime_binding_sha256=binding.runtime_binding_sha256)
    with sqlite3.connect(runtime.catalog_db) as conn:
        conn.execute(
            "UPDATE product_session SET history_encryption_key_id=NULL WHERE session_id=?",
            (record.session_id,),
        )
    FakeSQLiteSession.histories.setdefault(record.session_id, []).append({"role": "user", "content": "legacy"})
    with pytest.raises(SessionIntegrityError, match="cleared and recreated"):
        runtime.sdk_session(record.session_id)
    cleared = asyncio.run(runtime.clear(record.session_id))
    assert cleared.state.value == "CLEARED"
    assert FakeSQLiteSession.histories[record.session_id] == []


def test_control_api_rejects_reused_protected_payload_key(tmp_path: Path) -> None:
    with pytest.raises(SessionConfigurationError, match="must be distinct"):
        create_app(
            project_root=ROOT,
            product_db=tmp_path / "product.sqlite3",
            artifact_root=tmp_path / "artifacts",
            evaluation_db=tmp_path / "evaluation.sqlite3",
            admin_key="step063-admin-key-123456",
            run_submitter_key="step063-submitter-key-123456",
            protected_payload_root=tmp_path / "payloads",
            protected_payload_key=KEY_TEXT,
            session_root=tmp_path / "sessions",
            session_history_key=KEY_TEXT,
        )


def test_runtime_binding_binds_policy_and_encryption_source() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.session_policy is not None
    assert binding.session_policy["policy_id"] == "local-strict-encrypted-compacted-sqlite-session-v1"
    assert binding.session_policy["encryption_enabled"] is True
    assert binding.session_runtime_sha256 is not None and len(binding.session_runtime_sha256) == 64
    source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text(encoding="utf-8")
    assert '"okcanvas_agent_runtime.adapters.storage.session_history"' in source
