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
    "max_mcp_servers_per_turn",
    "read_only_required",
    "local_stdio_only",
    "manager_scope",
    "hold_turn_lease_until_manager_cleanup",
    "commit_completed_turn",
    "rollback_failed_turn",
    "history_copy_to_product",
    "mcp_content_copy_to_product",
    "workspace_access",
}


@dataclass(frozen=True)
class SQLiteSessionMCPPolicy:
    schema_version: str
    policy_id: str
    version: str
    max_mcp_servers_per_turn: int
    read_only_required: bool
    local_stdio_only: bool
    manager_scope: str
    hold_turn_lease_until_manager_cleanup: bool
    commit_completed_turn: bool
    rollback_failed_turn: bool
    history_copy_to_product: bool
    mcp_content_copy_to_product: bool
    workspace_access: str
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, Any]:
        return asdict(self)


class SQLiteSessionMCPPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def resolve(self) -> SQLiteSessionMCPPolicy:
        path = (self.project_root / "specs" / "runtime" / "sqlite-session-mcp-policy.json").resolve()
        expected_parent = (self.project_root / "specs" / "runtime").resolve()
        if path.parent != expected_parent or path.is_symlink() or not path.is_file():
            raise SessionPolicyError("SQLite Session MCP policy is missing or unsafe")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise SessionPolicyError("SQLite Session MCP policy is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _EXPECTED_KEYS:
            raise SessionPolicyError("SQLite Session MCP policy keys mismatch")
        if payload["schema_version"] != "okcanvas-sqlite-session-mcp-policy-v1":
            raise SessionPolicyError("Unsupported SQLite Session MCP policy schema")
        if payload["max_mcp_servers_per_turn"] != 1:
            raise SessionPolicyError("STEP050 permits exactly one MCP server per Turn")
        if payload["read_only_required"] is not True:
            raise SessionPolicyError("STEP050 requires a read-only MCP server")
        if payload["local_stdio_only"] is not True:
            raise SessionPolicyError("STEP050 permits local stdio MCP only")
        if payload["manager_scope"] != "per-turn":
            raise SessionPolicyError("STEP050 requires one MCP manager lifecycle per Turn")
        if payload["hold_turn_lease_until_manager_cleanup"] is not True:
            raise SessionPolicyError("STEP050 must hold the Turn lease through MCP cleanup")
        if payload["commit_completed_turn"] is not True or payload["rollback_failed_turn"] is not True:
            raise SessionPolicyError("STEP050 requires commit on success and rollback on failure")
        if payload["history_copy_to_product"] is not False or payload["mcp_content_copy_to_product"] is not False:
            raise SessionPolicyError("STEP050 forbids copying Session or MCP content to Product state")
        if payload["workspace_access"] != "none":
            raise SessionPolicyError("STEP050 is workspace-free")
        return SQLiteSessionMCPPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            max_mcp_servers_per_turn=1,
            read_only_required=True,
            local_stdio_only=True,
            manager_scope="per-turn",
            hold_turn_lease_until_manager_cleanup=True,
            commit_completed_turn=True,
            rollback_failed_turn=True,
            history_copy_to_product=False,
            mcp_content_copy_to_product=False,
            workspace_access="none",
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
