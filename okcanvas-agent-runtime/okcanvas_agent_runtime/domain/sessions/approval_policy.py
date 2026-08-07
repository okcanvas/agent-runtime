from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.sessions.errors import SessionPolicyError


@dataclass(frozen=True)
class SQLiteSessionApprovalPolicy:
    schema_version: str
    policy_id: str
    version: str
    session_mode: str
    approval_mode: str
    max_tools: int
    hold_turn_lease_while_interrupted: bool
    commit_rejected_turn: bool
    rollback_failed_turn: bool
    workspace_access: str
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, Any]:
        return asdict(self)


_EXPECTED_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "session_mode",
    "approval_mode",
    "max_tools",
    "hold_turn_lease_while_interrupted",
    "commit_rejected_turn",
    "rollback_failed_turn",
    "workspace_access",
}


class SQLiteSessionApprovalPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def resolve(self) -> SQLiteSessionApprovalPolicy:
        root = (self.project_root / "specs" / "runtime").resolve()
        path = (root / "sqlite-session-approval-policy.json").resolve()
        if path.parent != root or path.is_symlink() or not path.is_file():
            raise SessionPolicyError("SQLite Session approval policy is missing or unsafe")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise SessionPolicyError("SQLite Session approval policy is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _EXPECTED_KEYS:
            raise SessionPolicyError("SQLite Session approval policy keys mismatch")
        if payload["schema_version"] != "okcanvas-sqlite-session-approval-policy-v1":
            raise SessionPolicyError("Unsupported SQLite Session approval policy schema")
        if payload["session_mode"] != "sqlite-v1" or payload["approval_mode"] != "ALWAYS":
            raise SessionPolicyError("Session approval policy mode mismatch")
        if payload["max_tools"] != 1:
            raise SessionPolicyError("STEP046 permits exactly one approval Tool")
        if payload["hold_turn_lease_while_interrupted"] is not True:
            raise SessionPolicyError("STEP046 must hold the Session Turn lease while interrupted")
        if payload["commit_rejected_turn"] is not True:
            raise SessionPolicyError("STEP046 commits the rejected conversational Turn")
        if payload["rollback_failed_turn"] is not True:
            raise SessionPolicyError("STEP046 rolls back failed partial Session history")
        if payload["workspace_access"] != "none":
            raise SessionPolicyError("STEP046 is workspace-free")
        return SQLiteSessionApprovalPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            session_mode="sqlite-v1",
            approval_mode="ALWAYS",
            max_tools=1,
            hold_turn_lease_while_interrupted=True,
            commit_rejected_turn=True,
            rollback_failed_turn=True,
            workspace_access="none",
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
