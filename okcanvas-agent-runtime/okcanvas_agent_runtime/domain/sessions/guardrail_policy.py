from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.sessions.errors import SessionPolicyError


@dataclass(frozen=True)
class SQLiteSessionGuardrailPolicy:
    schema_version: str
    policy_id: str
    version: str
    session_mode: str
    allowed_guardrail_kinds: tuple[str, ...]
    max_per_kind: int
    commit_successful_turn: bool
    rollback_tripped_turn: bool
    history_copy_to_product: bool
    workspace_access: str
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["allowed_guardrail_kinds"] = list(self.allowed_guardrail_kinds)
        return payload


_EXPECTED_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "session_mode",
    "allowed_guardrail_kinds",
    "max_per_kind",
    "commit_successful_turn",
    "rollback_tripped_turn",
    "history_copy_to_product",
    "workspace_access",
}


class SQLiteSessionGuardrailPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def resolve(self) -> SQLiteSessionGuardrailPolicy:
        policy_root = (self.project_root / "specs" / "runtime").resolve()
        path = (policy_root / "sqlite-session-guardrail-policy.json").resolve()
        if path.parent != policy_root or path.is_symlink() or not path.is_file():
            raise SessionPolicyError("SQLite Session Guardrail policy is missing or unsafe")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise SessionPolicyError("SQLite Session Guardrail policy is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _EXPECTED_KEYS:
            raise SessionPolicyError("SQLite Session Guardrail policy keys mismatch")
        if payload["schema_version"] != "okcanvas-sqlite-session-guardrail-policy-v1":
            raise SessionPolicyError("Unsupported SQLite Session Guardrail policy schema")
        if payload["session_mode"] != "sqlite-v1":
            raise SessionPolicyError("SQLite Session Guardrail policy mode mismatch")
        if payload["allowed_guardrail_kinds"] != ["INPUT", "OUTPUT"]:
            raise SessionPolicyError("STEP048 permits Agent input/output Guardrails only")
        if payload["max_per_kind"] != 1:
            raise SessionPolicyError("STEP048 permits at most one Guardrail per allowed kind")
        if payload["commit_successful_turn"] is not True:
            raise SessionPolicyError("STEP048 commits successful Session Turns")
        if payload["rollback_tripped_turn"] is not True:
            raise SessionPolicyError("STEP048 rolls back tripwire partial Session history")
        if payload["history_copy_to_product"] is not False:
            raise SessionPolicyError("STEP048 forbids copying raw Session history to Product storage")
        if payload["workspace_access"] != "none":
            raise SessionPolicyError("STEP048 is workspace-free")
        return SQLiteSessionGuardrailPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            session_mode="sqlite-v1",
            allowed_guardrail_kinds=("INPUT", "OUTPUT"),
            max_per_kind=1,
            commit_successful_turn=True,
            rollback_tripped_turn=True,
            history_copy_to_product=False,
            workspace_access="none",
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
