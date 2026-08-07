from __future__ import annotations

import hashlib
import json
from pathlib import Path

from okcanvas_agent_runtime.domain.sessions.errors import SessionPolicyError
from okcanvas_agent_runtime.domain.sessions.models import SQLiteSessionPolicy

_EXPECTED_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "session_mode",
    "max_active_turns",
    "history_limit",
    "compaction_enabled",
    "compaction_mode",
    "compaction_provider",
    "compaction_api",
    "compaction_model",
    "compaction_trigger_candidate_items",
    "compaction_max_input_items",
    "compaction_store",
    "compaction_previous_response_id_allowed",
    "compaction_automatic",
    "compaction_restore_previous_on_failure",
    "compaction_raw_history_in_events",
    "encryption_enabled",
    "encryption_mode",
    "encryption_envelope_version",
    "key_derivation",
    "legacy_plaintext_mode",
    "ttl_seconds",
}


class SQLiteSessionPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def resolve(self) -> SQLiteSessionPolicy:
        path = (self.project_root / "specs" / "runtime" / "sqlite-session-policy.json").resolve()
        expected_parent = (self.project_root / "specs" / "runtime").resolve()
        if path.parent != expected_parent or path.is_symlink() or not path.is_file():
            raise SessionPolicyError("SQLite Session policy is missing or unsafe")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise SessionPolicyError("SQLite Session policy is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _EXPECTED_KEYS:
            raise SessionPolicyError("SQLite Session policy keys mismatch")
        if payload["schema_version"] != "okcanvas-sqlite-session-policy-v3":
            raise SessionPolicyError("Unsupported SQLite Session policy schema")
        if payload["policy_id"] != "local-strict-encrypted-compacted-sqlite-session-v1":
            raise SessionPolicyError("Unexpected SQLite Session policy ID")
        if payload["version"] != "3.0.0":
            raise SessionPolicyError("Unexpected SQLite Session policy version")
        if payload["session_mode"] != "sqlite-v1":
            raise SessionPolicyError("SQLite Session policy mode must be sqlite-v1")
        if payload["max_active_turns"] != 1:
            raise SessionPolicyError("SQLite Session requires exactly one active Turn")
        if payload["history_limit"] is not None:
            raise SessionPolicyError("STEP064 does not truncate Session history by item limit")
        exact_compaction = {
            "compaction_enabled": True,
            "compaction_mode": "INPUT_ONLY",
            "compaction_provider": "openai",
            "compaction_api": "responses.compact",
            "compaction_model": "gpt-4.1",
            "compaction_trigger_candidate_items": 10,
            "compaction_max_input_items": 256,
            "compaction_store": False,
            "compaction_previous_response_id_allowed": False,
            "compaction_automatic": True,
            "compaction_restore_previous_on_failure": True,
            "compaction_raw_history_in_events": False,
        }
        if any(payload[key] != value for key, value in exact_compaction.items()):
            raise SessionPolicyError("STEP064 Session compaction policy mismatch")
        if payload["encryption_enabled"] is not True:
            raise SessionPolicyError("STEP064 requires Session history encryption")
        if payload["encryption_mode"] != "STRICT_AES_256_GCM_HKDF_SHA256_V1":
            raise SessionPolicyError("Unexpected Session history encryption mode")
        if payload["encryption_envelope_version"] != 1:
            raise SessionPolicyError("Unexpected Session history envelope version")
        if payload["key_derivation"] != "PER_SESSION_HKDF_SHA256_V1":
            raise SessionPolicyError("Unexpected Session history key derivation")
        if payload["legacy_plaintext_mode"] != "REJECT":
            raise SessionPolicyError("Legacy plaintext Session history must fail closed")
        if payload["ttl_seconds"] is not None:
            raise SessionPolicyError("STEP064 does not silently expire Session history")
        return SQLiteSessionPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            session_mode=str(payload["session_mode"]),
            max_active_turns=int(payload["max_active_turns"]),
            history_limit=None,
            compaction_enabled=True,
            compaction_mode=str(payload["compaction_mode"]),
            compaction_provider=str(payload["compaction_provider"]),
            compaction_api=str(payload["compaction_api"]),
            compaction_model=str(payload["compaction_model"]),
            compaction_trigger_candidate_items=int(payload["compaction_trigger_candidate_items"]),
            compaction_max_input_items=int(payload["compaction_max_input_items"]),
            compaction_store=False,
            compaction_previous_response_id_allowed=False,
            compaction_automatic=True,
            compaction_restore_previous_on_failure=True,
            compaction_raw_history_in_events=False,
            encryption_enabled=True,
            encryption_mode=str(payload["encryption_mode"]),
            encryption_envelope_version=int(payload["encryption_envelope_version"]),
            key_derivation=str(payload["key_derivation"]),
            legacy_plaintext_mode=str(payload["legacy_plaintext_mode"]),
            ttl_seconds=None,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
