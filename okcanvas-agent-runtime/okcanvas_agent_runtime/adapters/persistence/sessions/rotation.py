from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.adapters.storage.session_history import SessionHistoryKey, StrictEncryptedSession
from okcanvas_agent_runtime.domain.sessions.errors import SessionConfigurationError, SessionIntegrityError
from okcanvas_agent_runtime.domain.sessions.rotation_policy import SQLiteSessionKeyRotationPolicy

_ENVELOPE_MARKER = "__okcanvas_session_encrypted__"
_ENVELOPE_VERSION = 1
_ENVELOPE_KEYS = {
    _ENVELOPE_MARKER,
    "version",
    "key_id",
    "nonce_b64",
    "ciphertext_b64",
}


def inspect_session_envelope_key_id(envelope: Any) -> str:
    if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_KEYS:
        raise SessionIntegrityError(
            "Session history contains plaintext or an unsupported encryption envelope"
        )
    if envelope.get(_ENVELOPE_MARKER) != 1 or envelope.get("version") != _ENVELOPE_VERSION:
        raise SessionIntegrityError("Session history encryption envelope version is unsupported")
    key_id = envelope.get("key_id")
    if not isinstance(key_id, str) or re.fullmatch(r"[0-9a-f]{16}", key_id) is None:
        raise SessionIntegrityError("Session history encryption key ID is malformed")
    return key_id


@dataclass(frozen=True)
class SessionKeyRotationResult:
    session_id: str
    operation_id: str | None
    source_key_id: str
    target_key_id: str
    item_count: int
    resumed: bool
    already_current: bool
    state: str = "COMPLETED"

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = "okcanvas-session-key-rotation-result-v1"
        return payload


@dataclass(frozen=True)
class HistoryRotationOutcome:
    item_count: int
    observed_mode: str


class SQLiteSessionHistoryRotator:
    """Atomically re-encrypt one Session inside the pinned SDK SQLite history database."""

    def __init__(
        self,
        *,
        history_db: str | Path,
        policy: SQLiteSessionKeyRotationPolicy,
    ) -> None:
        self.history_db = Path(history_db).expanduser().resolve()
        self.policy = policy

    def _validate_path(self) -> None:
        parent = self.history_db.parent
        if parent.is_symlink() or not parent.is_dir():
            raise SessionIntegrityError("Session root must be a real directory")
        if self.history_db.exists() and (
            self.history_db.is_symlink() or not self.history_db.is_file()
        ):
            raise SessionIntegrityError("Session database path is unsafe")

    @staticmethod
    def _codec(session_id: str, key: SessionHistoryKey) -> StrictEncryptedSession:
        return StrictEncryptedSession(
            session_id=session_id,
            underlying_session=object(),
            key=key,
        )

    @staticmethod
    def _parse_message_data(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, str):
            raise SessionIntegrityError("Session history message_data is not text")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SessionIntegrityError("Session history contains invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SessionIntegrityError("Session history envelope must be an object")
        return payload

    def _verify_schema(self, conn: sqlite3.Connection) -> None:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if (
            self.policy.messages_table not in tables
            or self.policy.sessions_table not in tables
        ):
            raise SessionIntegrityError("Installed SDK SQLite Session schema is missing")
        columns = {
            str(row[1])
            for row in conn.execute(
                f"PRAGMA table_info({self.policy.messages_table})"
            ).fetchall()
        }
        if not {"id", "session_id", self.policy.message_data_column}.issubset(columns):
            raise SessionIntegrityError("Installed SDK SQLite Session message schema changed")

    def clear_session(self, session_id: str) -> None:
        self._validate_path()
        if not self.history_db.exists():
            return
        conn = sqlite3.connect(
            self.history_db, timeout=15, isolation_level=None, check_same_thread=False
        )
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            self._verify_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                f"DELETE FROM {self.policy.messages_table} WHERE session_id=?",
                (session_id,),
            )
            conn.execute(
                f"DELETE FROM {self.policy.sessions_table} WHERE session_id=?",
                (session_id,),
            )
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def rotate(
        self,
        *,
        session_id: str,
        source_key_id: str,
        source_key: SessionHistoryKey | None,
        target_key: SessionHistoryKey,
    ) -> HistoryRotationOutcome:
        self._validate_path()
        if not self.history_db.exists():
            return HistoryRotationOutcome(item_count=0, observed_mode="EMPTY")

        conn = sqlite3.connect(
            self.history_db,
            timeout=15,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            self._verify_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                f"SELECT id, {self.policy.message_data_column} "
                f"FROM {self.policy.messages_table} "
                "WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            if len(rows) > self.policy.max_history_items:
                raise SessionIntegrityError(
                    "Session history exceeds the bounded key rotation item limit"
                )
            if not rows:
                conn.commit()
                return HistoryRotationOutcome(item_count=0, observed_mode="EMPTY")

            envelopes: list[tuple[int, dict[str, Any]]] = []
            observed_key_ids: set[str] = set()
            for row in rows:
                envelope = self._parse_message_data(row[self.policy.message_data_column])
                observed_key_ids.add(inspect_session_envelope_key_id(envelope))
                envelopes.append((int(row["id"]), envelope))

            if observed_key_ids == {target_key.key_id}:
                conn.commit()
                return HistoryRotationOutcome(
                    item_count=len(envelopes), observed_mode="ALREADY_TARGET"
                )
            if observed_key_ids != {source_key_id}:
                raise SessionIntegrityError(
                    "Session history contains mixed or unexpected encryption key IDs"
                )
            if source_key is None or source_key.key_id != source_key_id:
                raise SessionConfigurationError(
                    "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY is required to resume key rotation"
                )

            source_codec = self._codec(session_id, source_key)
            target_codec = self._codec(session_id, target_key)
            rewritten: list[tuple[str, int, str]] = []
            for message_id, envelope in envelopes:
                plaintext = source_codec._decrypt(envelope)
                target_envelope = target_codec._encrypt(plaintext)
                rewritten.append(
                    (
                        json.dumps(
                            target_envelope,
                            ensure_ascii=True,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        message_id,
                        session_id,
                    )
                )
            conn.executemany(
                f"UPDATE {self.policy.messages_table} "
                f"SET {self.policy.message_data_column}=? "
                "WHERE id=? AND session_id=?",
                rewritten,
            )
            verification = conn.execute(
                f"SELECT {self.policy.message_data_column} "
                f"FROM {self.policy.messages_table} "
                "WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            if len(verification) != len(rewritten):
                raise SessionIntegrityError("Session history key rotation row count changed")
            for row in verification:
                envelope = self._parse_message_data(row[self.policy.message_data_column])
                if inspect_session_envelope_key_id(envelope) != target_key.key_id:
                    raise SessionIntegrityError("Session history key rotation verification failed")
                target_codec._decrypt(envelope)
            conn.commit()
            return HistoryRotationOutcome(
                item_count=len(rewritten), observed_mode="REENCRYPTED"
            )
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
