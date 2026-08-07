from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.sessions.errors import SessionPolicyError


@dataclass(frozen=True)
class SQLiteSessionAgentToolPolicy:
    schema_version: str
    policy_id: str
    version: str
    session_mode: str
    agent_tool_policy_id: str
    max_agent_tool_calls_per_turn: int
    max_depth: int
    root_session_only: bool
    child_session_mode: str
    hold_turn_lease_until_parent_completion: bool
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
    "agent_tool_policy_id",
    "max_agent_tool_calls_per_turn",
    "max_depth",
    "root_session_only",
    "child_session_mode",
    "hold_turn_lease_until_parent_completion",
    "commit_completed_turn",
    "rollback_failed_turn",
    "history_copy_to_product",
    "workspace_access",
}


class SQLiteSessionAgentToolPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def resolve(self) -> SQLiteSessionAgentToolPolicy:
        root = (self.project_root / "specs" / "runtime").resolve()
        path = (root / "sqlite-session-agent-tool-policy.json").resolve()
        if path.parent != root or path.is_symlink() or not path.is_file():
            raise SessionPolicyError("SQLite Session Agent-as-Tool policy is missing or unsafe")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise SessionPolicyError("SQLite Session Agent-as-Tool policy is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _EXPECTED_KEYS:
            raise SessionPolicyError("SQLite Session Agent-as-Tool policy keys mismatch")
        if payload["schema_version"] != "okcanvas-sqlite-session-agent-tool-policy-v1":
            raise SessionPolicyError("Unsupported SQLite Session Agent-as-Tool policy schema")
        if payload["session_mode"] != "sqlite-v1":
            raise SessionPolicyError("SQLite Session Agent-as-Tool policy mode mismatch")
        if payload["agent_tool_policy_id"] != "default-agent-as-tool-policy":
            raise SessionPolicyError("STEP049 requires the existing Agent-as-Tool policy")
        if payload["max_agent_tool_calls_per_turn"] != 1 or payload["max_depth"] != 1:
            raise SessionPolicyError("STEP049 permits one terminal Agent-as-Tool call per Turn")
        if payload["root_session_only"] is not True or payload["child_session_mode"] != "disabled":
            raise SessionPolicyError("STEP049 permits Session history on the Root Agent only")
        if payload["hold_turn_lease_until_parent_completion"] is not True:
            raise SessionPolicyError("STEP049 holds the Turn lease through parent completion")
        if payload["commit_completed_turn"] is not True:
            raise SessionPolicyError("STEP049 commits only completed Agent-as-Tool Turns")
        if payload["rollback_failed_turn"] is not True:
            raise SessionPolicyError("STEP049 rolls back failed partial Session history")
        if payload["history_copy_to_product"] is not False:
            raise SessionPolicyError("STEP049 forbids copying raw Session history to Product storage")
        if payload["workspace_access"] != "none":
            raise SessionPolicyError("STEP049 is workspace-free")
        return SQLiteSessionAgentToolPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            session_mode="sqlite-v1",
            agent_tool_policy_id="default-agent-as-tool-policy",
            max_agent_tool_calls_per_turn=1,
            max_depth=1,
            root_session_only=True,
            child_session_mode="disabled",
            hold_turn_lease_until_parent_completion=True,
            commit_completed_turn=True,
            rollback_failed_turn=True,
            history_copy_to_product=False,
            workspace_access="none",
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
