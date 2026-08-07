from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.subagents.handoffs.errors import NativeHandoffPolicyError
from okcanvas_agent_runtime.agent.subagents.handoffs.models import NativeHandoffPolicy

_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "max_handoffs_per_run",
    "max_depth",
    "input_filter_mode",
    "nest_handoff_history",
    "handoff_input_payload_enabled",
    "require_same_output_contract",
    "required_workspace_access",
}
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class NativeHandoffPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = (self.project_root / "specs" / "runtime" / "native-handoff-policy.json").resolve()

    def resolve(self) -> NativeHandoffPolicy:
        expected_parent = (self.project_root / "specs" / "runtime").resolve()
        if self.path.is_symlink() or self.path.parent != expected_parent or not self.path.is_file():
            raise NativeHandoffPolicyError("Native Handoff policy is missing or unsafe")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NativeHandoffPolicyError("Native Handoff policy is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _KEYS:
            raise NativeHandoffPolicyError("Native Handoff policy keys do not match the contract")
        if payload["schema_version"] != "okcanvas-native-handoff-policy-v1":
            raise NativeHandoffPolicyError("Unsupported Native Handoff policy schema")
        policy_id = self._string(payload, "policy_id")
        version = self._string(payload, "version")
        if not _ID_RE.fullmatch(policy_id) or not _VERSION_RE.fullmatch(version):
            raise NativeHandoffPolicyError("Native Handoff policy identity is invalid")
        if self._integer(payload, "max_handoffs_per_run", 1, 4) != 1:
            raise NativeHandoffPolicyError("STEP041 permits exactly one Handoff per Run")
        if self._integer(payload, "max_depth", 1, 4) != 1:
            raise NativeHandoffPolicyError("STEP041 permits Handoff depth exactly one")
        if payload["input_filter_mode"] != "REMOVE_ALL_TOOLS":
            raise NativeHandoffPolicyError("STEP041 requires REMOVE_ALL_TOOLS input filtering")
        for key, expected in (
            ("nest_handoff_history", False),
            ("handoff_input_payload_enabled", False),
            ("require_same_output_contract", True),
        ):
            if payload[key] is not expected:
                raise NativeHandoffPolicyError(f"Unsupported Native Handoff policy value: {key}")
        if payload["required_workspace_access"] != "none":
            raise NativeHandoffPolicyError("STEP041 requires workspace_access=none")
        return NativeHandoffPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=policy_id,
            version=version,
            max_handoffs_per_run=1,
            max_depth=1,
            input_filter_mode="REMOVE_ALL_TOOLS",
            nest_handoff_history=False,
            handoff_input_payload_enabled=False,
            require_same_output_contract=True,
            required_workspace_access="none",
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise NativeHandoffPolicyError(f"{key} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _integer(payload: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
        value = payload[key]
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise NativeHandoffPolicyError(f"{key} must be an integer from {minimum} to {maximum}")
        return value
