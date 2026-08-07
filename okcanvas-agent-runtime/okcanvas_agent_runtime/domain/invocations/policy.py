from __future__ import annotations

import hashlib
import json
from pathlib import Path

from okcanvas_agent_runtime.domain.invocations.errors import InvocationPolicyError
from okcanvas_agent_runtime.domain.invocations.models import InvocationPolicy, WorkspaceAccess


class InvocationPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.policy_path = (
            self.project_root / "specs" / "runtime" / "sub-agent-invocation-policy.json"
        ).resolve()

    def resolve(self) -> InvocationPolicy:
        if self.policy_path.is_symlink() or not self.policy_path.is_file():
            raise InvocationPolicyError("Sub-Agent invocation policy is missing or unsafe")
        if self.policy_path.parent != (self.project_root / "specs" / "runtime").resolve():
            raise InvocationPolicyError("Sub-Agent invocation policy escaped its specification root")
        raw = self.policy_path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvocationPolicyError("Sub-Agent invocation policy is not valid UTF-8 JSON") from exc
        expected = {
            "schema_version",
            "policy_id",
            "version",
            "max_depth",
            "max_handoffs_per_run",
            "max_agent_tools_per_run",
            "default_workspace_access",
            "physical_workspace_enabled",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise InvocationPolicyError("Sub-Agent invocation policy keys do not match the contract")
        if payload["schema_version"] != "okcanvas-sub-agent-invocation-policy-v1":
            raise InvocationPolicyError("Unsupported Sub-Agent invocation policy schema")
        if payload["policy_id"] != "default-sub-agent-invocation-policy":
            raise InvocationPolicyError("Unexpected Sub-Agent invocation policy ID")
        if payload["version"] != "1.0.0":
            raise InvocationPolicyError("Unexpected Sub-Agent invocation policy version")
        for key, maximum in (
            ("max_depth", 16),
            ("max_handoffs_per_run", 64),
            ("max_agent_tools_per_run", 64),
        ):
            value = payload[key]
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
                raise InvocationPolicyError(f"{key} is outside the allowed range")
        try:
            workspace_access = WorkspaceAccess(str(payload["default_workspace_access"]))
        except ValueError as exc:
            raise InvocationPolicyError("Unknown default workspace access") from exc
        if workspace_access is not WorkspaceAccess.NONE:
            raise InvocationPolicyError("P0 default workspace access must be none")
        if payload["physical_workspace_enabled"] is not False:
            raise InvocationPolicyError("STEP040 cannot enable physical workspace materialization")
        return InvocationPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            max_depth=int(payload["max_depth"]),
            max_handoffs_per_run=int(payload["max_handoffs_per_run"]),
            max_agent_tools_per_run=int(payload["max_agent_tools_per_run"]),
            default_workspace_access=workspace_access,
            physical_workspace_enabled=False,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
