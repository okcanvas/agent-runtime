from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.application.submissions.errors import RunSubmissionPolicyError
from okcanvas_agent_runtime.application.submissions.models import RunSubmissionExecutionMode, RunSubmissionPolicy

_POLICY_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "authority_scope",
    "idempotency_required",
    "idempotency_key_min_length",
    "idempotency_key_max_length",
    "input_max_chars",
    "confirmation_mode",
    "read_only_execution_mode",
    "local_tool_execution_mode",
    "write_mcp_execution_mode",
    "handoff_or_session_execution_mode",
    "protected_payload_mode",
    "direct_run_api_default_enabled",
    "console_mutation_enabled",
}
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class RunSubmissionPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = (
            self.project_root / "specs" / "submissions" / "local-run-submission-policy.json"
        ).resolve()

    def resolve(self) -> RunSubmissionPolicy:
        expected_parent = (self.project_root / "specs" / "submissions").resolve()
        if self.path.is_symlink() or self.path.parent != expected_parent or not self.path.is_file():
            raise RunSubmissionPolicyError("Run submission policy is missing or unsafe")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunSubmissionPolicyError("Run submission policy is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _POLICY_KEYS:
            raise RunSubmissionPolicyError("Run submission policy keys do not match the contract")
        if payload["schema_version"] != "okcanvas-run-submission-policy-v1":
            raise RunSubmissionPolicyError("Unsupported run submission policy schema")
        policy_id = self._string(payload, "policy_id")
        if not _ID_RE.fullmatch(policy_id):
            raise RunSubmissionPolicyError("Invalid run submission policy ID")
        version = self._string(payload, "version")
        if not _VERSION_RE.fullmatch(version):
            raise RunSubmissionPolicyError("Run submission policy version must be semantic")
        if payload["authority_scope"] != "LOCAL_RUN_SUBMITTER":
            raise RunSubmissionPolicyError("Unsupported run submission authority scope")
        if payload["idempotency_required"] is not True:
            raise RunSubmissionPolicyError("Idempotency must be mandatory")
        minimum = self._integer(payload, "idempotency_key_min_length", 16, 64)
        maximum = self._integer(payload, "idempotency_key_max_length", minimum, 256)
        input_max = self._integer(payload, "input_max_chars", 1, 100_000)
        if payload["confirmation_mode"] != "fingerprint-challenge":
            raise RunSubmissionPolicyError("Unsupported confirmation mode")
        protected = self._string(payload, "protected_payload_mode")
        if protected != "AES_256_GCM_FILE_V1":
            raise RunSubmissionPolicyError("STEP018 requires the AES-256-GCM protected payload mode")
        if payload["direct_run_api_default_enabled"] is not False:
            raise RunSubmissionPolicyError("Direct Run API must be disabled by default")
        if payload["console_mutation_enabled"] is not False:
            raise RunSubmissionPolicyError("Console mutation must remain disabled in STEP018")
        return RunSubmissionPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=policy_id,
            version=version,
            authority_scope="LOCAL_RUN_SUBMITTER",
            idempotency_required=True,
            idempotency_key_min_length=minimum,
            idempotency_key_max_length=maximum,
            input_max_chars=input_max,
            confirmation_mode="fingerprint-challenge",
            read_only_execution_mode=self._mode(payload, "read_only_execution_mode"),
            local_tool_execution_mode=self._mode(payload, "local_tool_execution_mode"),
            write_mcp_execution_mode=self._mode(payload, "write_mcp_execution_mode"),
            handoff_or_session_execution_mode=self._mode(
                payload, "handoff_or_session_execution_mode"
            ),
            protected_payload_mode=protected,
            direct_run_api_default_enabled=False,
            console_mutation_enabled=False,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise RunSubmissionPolicyError(f"{key} must be a non-empty string")
        return value.strip()

    @classmethod
    def _mode(cls, payload: dict[str, Any], key: str) -> RunSubmissionExecutionMode:
        try:
            return RunSubmissionExecutionMode(cls._string(payload, key))
        except ValueError as exc:
            raise RunSubmissionPolicyError(f"Unsupported execution mode for {key}") from exc

    @staticmethod
    def _integer(payload: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
        value = payload[key]
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise RunSubmissionPolicyError(f"{key} must be an integer from {minimum} to {maximum}")
        return value
