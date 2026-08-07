from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.sessions.errors import SessionPolicyError

_EXPECTED_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "sdk_version",
    "sdk_sqlite_session_source_sha256",
    "sessions_table",
    "messages_table",
    "message_data_column",
    "mode",
    "automatic_rotation",
    "resume_incomplete_rotation",
    "source_key_environment",
    "target_key_environment",
    "max_history_items",
    "plaintext_mode",
    "mixed_key_envelope_mode",
    "raw_history_in_events",
    "clear_incomplete_rotation_without_decrypt",
}


@dataclass(frozen=True)
class SQLiteSessionKeyRotationPolicy:
    schema_version: str
    policy_id: str
    version: str
    sdk_version: str
    sdk_sqlite_session_source_sha256: str
    sessions_table: str
    messages_table: str
    message_data_column: str
    mode: str
    automatic_rotation: bool
    resume_incomplete_rotation: bool
    source_key_environment: str
    target_key_environment: str
    max_history_items: int
    plaintext_mode: str
    mixed_key_envelope_mode: str
    raw_history_in_events: bool
    clear_incomplete_rotation_without_decrypt: bool
    policy_sha256: str

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self)


class SQLiteSessionKeyRotationPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def resolve(self) -> SQLiteSessionKeyRotationPolicy:
        path = (
            self.project_root
            / "specs"
            / "runtime"
            / "sqlite-session-key-rotation-policy.json"
        ).resolve()
        expected_parent = (self.project_root / "specs" / "runtime").resolve()
        if path.parent != expected_parent or path.is_symlink() or not path.is_file():
            raise SessionPolicyError("SQLite Session key rotation policy is missing or unsafe")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise SessionPolicyError("SQLite Session key rotation policy is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _EXPECTED_KEYS:
            raise SessionPolicyError("SQLite Session key rotation policy keys mismatch")
        exact = {
            "schema_version": "okcanvas-sqlite-session-key-rotation-policy-v1",
            "policy_id": "local-explicit-single-session-key-rotation-v1",
            "version": "1.0.0",
            "sdk_version": "0.19.0",
            "sdk_sqlite_session_source_sha256": (
                "55e998777c4d15e667b819965b1bd5d66c7391969e4cd270fdd1a6498dccbf16"
            ),
            "sessions_table": "agent_sessions",
            "messages_table": "agent_messages",
            "message_data_column": "message_data",
            "mode": "EXPLICIT_SINGLE_SESSION",
            "automatic_rotation": False,
            "resume_incomplete_rotation": True,
            "source_key_environment": "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY",
            "target_key_environment": "OKCANVAS_SESSION_HISTORY_KEY",
            "max_history_items": 256,
            "plaintext_mode": "REJECT",
            "mixed_key_envelope_mode": "REJECT",
            "raw_history_in_events": False,
            "clear_incomplete_rotation_without_decrypt": True,
        }
        if any(payload.get(key) != value for key, value in exact.items()):
            raise SessionPolicyError("SQLite Session key rotation policy mismatch")
        sdk_source = (
            self.project_root
            / "reference"
            / "upstream"
            / "openai-agents-python-0.19.0"
            / "src"
            / "agents"
            / "memory"
            / "sqlite_session.py"
        ).resolve()
        expected_sdk_parent = (
            self.project_root
            / "reference"
            / "upstream"
            / "openai-agents-python-0.19.0"
            / "src"
            / "agents"
            / "memory"
        ).resolve()
        if (
            sdk_source.parent != expected_sdk_parent
            or sdk_source.is_symlink()
            or not sdk_source.is_file()
            or hashlib.sha256(sdk_source.read_bytes()).hexdigest()
            != exact["sdk_sqlite_session_source_sha256"]
        ):
            raise SessionPolicyError("Pinned SDK SQLiteSession source integrity mismatch")
        return SQLiteSessionKeyRotationPolicy(
            **exact,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
