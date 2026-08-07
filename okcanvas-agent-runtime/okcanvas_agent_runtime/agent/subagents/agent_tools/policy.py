from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.subagents.agent_tools.errors import AgentToolPolicyError
from okcanvas_agent_runtime.agent.subagents.agent_tools.models import AgentToolPolicy

_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "max_agent_tool_calls_per_run",
    "max_depth",
    "input_mode",
    "output_mode",
    "max_result_bytes",
    "nested_stream_enabled",
    "inherit_parent_run_config",
    "require_same_output_contract",
    "required_workspace_access",
}
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class AgentToolPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = (
            self.project_root / "specs" / "runtime" / "agent-as-tool-policy.json"
        ).resolve()

    def resolve(self) -> AgentToolPolicy:
        expected_parent = (self.project_root / "specs" / "runtime").resolve()
        if self.path.is_symlink() or self.path.parent != expected_parent or not self.path.is_file():
            raise AgentToolPolicyError("Agent-as-Tool policy is missing or unsafe")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AgentToolPolicyError("Agent-as-Tool policy is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _KEYS:
            raise AgentToolPolicyError("Agent-as-Tool policy keys do not match the contract")
        if payload["schema_version"] != "okcanvas-agent-as-tool-policy-v1":
            raise AgentToolPolicyError("Unsupported Agent-as-Tool policy schema")
        policy_id = self._string(payload, "policy_id")
        version = self._string(payload, "version")
        if not _ID_RE.fullmatch(policy_id) or not _VERSION_RE.fullmatch(version):
            raise AgentToolPolicyError("Agent-as-Tool policy identity is invalid")
        if self._integer(payload, "max_agent_tool_calls_per_run", 1, 8) != 1:
            raise AgentToolPolicyError("STEP042 permits exactly one Agent-as-Tool call per Run")
        if self._integer(payload, "max_depth", 1, 4) != 1:
            raise AgentToolPolicyError("STEP042 permits Agent-as-Tool depth exactly one")
        if payload["input_mode"] != "MODEL_GENERATED_TEXT":
            raise AgentToolPolicyError("STEP042 requires MODEL_GENERATED_TEXT input")
        if payload["output_mode"] != "BOUNDED_STRUCTURED_JSON":
            raise AgentToolPolicyError("STEP042 requires BOUNDED_STRUCTURED_JSON output")
        max_result_bytes = self._integer(payload, "max_result_bytes", 256, 65536)
        for key, expected in (
            ("nested_stream_enabled", True),
            ("inherit_parent_run_config", False),
            ("require_same_output_contract", True),
        ):
            if payload[key] is not expected:
                raise AgentToolPolicyError(f"Unsupported Agent-as-Tool policy value: {key}")
        if payload["required_workspace_access"] != "none":
            raise AgentToolPolicyError("STEP042 requires workspace_access=none")
        return AgentToolPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=policy_id,
            version=version,
            max_agent_tool_calls_per_run=1,
            max_depth=1,
            input_mode="MODEL_GENERATED_TEXT",
            output_mode="BOUNDED_STRUCTURED_JSON",
            max_result_bytes=max_result_bytes,
            nested_stream_enabled=True,
            inherit_parent_run_config=False,
            require_same_output_contract=True,
            required_workspace_access="none",
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise AgentToolPolicyError(f"{key} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _integer(payload: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
        value = payload[key]
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise AgentToolPolicyError(f"{key} must be an integer from {minimum} to {maximum}")
        return value
