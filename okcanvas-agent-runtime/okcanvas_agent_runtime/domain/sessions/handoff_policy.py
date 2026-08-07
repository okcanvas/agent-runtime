from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.sessions.errors import SessionPolicyError


@dataclass(frozen=True)
class SQLiteSessionHandoffPolicy:
    schema_version: str
    policy_id: str
    version: str
    session_mode: str
    handoff_policy_id: str
    max_handoffs_per_turn: int
    max_depth: int
    require_same_sdk_session: bool
    hold_turn_lease_until_child_completion: bool
    commit_completed_turn: bool
    rollback_failed_turn: bool
    history_copy_to_product: bool
    workspace_access: str
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, Any]:
        return asdict(self)


_EXPECTED_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "session_mode",
    "handoff_policy_id",
    "max_handoffs_per_turn",
    "max_depth",
    "require_same_sdk_session",
    "hold_turn_lease_until_child_completion",
    "commit_completed_turn",
    "rollback_failed_turn",
    "history_copy_to_product",
    "workspace_access",
}


class SQLiteSessionHandoffPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def resolve(self) -> SQLiteSessionHandoffPolicy:
        root = (self.project_root / "specs" / "runtime").resolve()
        path = (root / "sqlite-session-handoff-policy.json").resolve()
        if path.parent != root or path.is_symlink() or not path.is_file():
            raise SessionPolicyError("SQLite Session Handoff policy is missing or unsafe")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise SessionPolicyError("SQLite Session Handoff policy is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _EXPECTED_KEYS:
            raise SessionPolicyError("SQLite Session Handoff policy keys mismatch")
        if payload["schema_version"] != "okcanvas-sqlite-session-handoff-policy-v1":
            raise SessionPolicyError("Unsupported SQLite Session Handoff policy schema")
        if payload["session_mode"] != "sqlite-v1":
            raise SessionPolicyError("SQLite Session Handoff policy mode mismatch")
        if payload["handoff_policy_id"] != "native-handoff-v1":
            raise SessionPolicyError("STEP047 requires the native Handoff policy")
        if payload["max_handoffs_per_turn"] != 1 or payload["max_depth"] != 1:
            raise SessionPolicyError("STEP047 permits one terminal Handoff per Turn")
        if payload["require_same_sdk_session"] is not True:
            raise SessionPolicyError("STEP047 requires one SDK Session across the Handoff")
        if payload["hold_turn_lease_until_child_completion"] is not True:
            raise SessionPolicyError("STEP047 holds the Turn lease through child completion")
        if payload["commit_completed_turn"] is not True:
            raise SessionPolicyError("STEP047 commits only completed Handoff Turns")
        if payload["rollback_failed_turn"] is not True:
            raise SessionPolicyError("STEP047 rolls back failed partial Session history")
        if payload["history_copy_to_product"] is not False:
            raise SessionPolicyError("STEP047 forbids copying raw Session history to Product storage")
        if payload["workspace_access"] != "none":
            raise SessionPolicyError("STEP047 is workspace-free")
        return SQLiteSessionHandoffPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            session_mode="sqlite-v1",
            handoff_policy_id="native-handoff-v1",
            max_handoffs_per_turn=1,
            max_depth=1,
            require_same_sdk_session=True,
            hold_turn_lease_until_child_completion=True,
            commit_completed_turn=True,
            rollback_failed_turn=True,
            history_copy_to_product=False,
            workspace_access="none",
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
