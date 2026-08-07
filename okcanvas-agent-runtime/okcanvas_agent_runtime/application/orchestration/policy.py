from __future__ import annotations

import hashlib
import json
from pathlib import Path

from okcanvas_agent_runtime.application.orchestration.errors import BoundedOrchestrationPolicyError
from okcanvas_agent_runtime.application.orchestration.models import BoundedOrchestrationPolicy


class BoundedOrchestrationPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.policy_path = (
            self.project_root / "specs" / "runtime" / "bounded-orchestration-policy.json"
        ).resolve()

    def resolve(self) -> BoundedOrchestrationPolicy:
        if self.policy_path.is_symlink() or not self.policy_path.is_file():
            raise BoundedOrchestrationPolicyError(
                "Bounded orchestration policy is missing or unsafe"
            )
        if self.policy_path.parent != (self.project_root / "specs" / "runtime").resolve():
            raise BoundedOrchestrationPolicyError(
                "Bounded orchestration policy escaped its specification root"
            )
        raw = self.policy_path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BoundedOrchestrationPolicyError(
                "Bounded orchestration policy is not valid UTF-8 JSON"
            ) from exc
        expected = {
            "schema_version",
            "policy_id",
            "version",
            "child_count",
            "max_parallelism",
            "max_depth",
            "failure_mode",
            "cancellation_mode",
            "aggregation_mode",
            "child_output_contract",
            "root_output_contract",
            "child_session_mode",
            "read_only_language_only",
            "native_child_streaming",
            "workspace_access",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise BoundedOrchestrationPolicyError(
                "Bounded orchestration policy keys do not match the contract"
            )
        exact = {
            "schema_version": "okcanvas-bounded-orchestration-policy-v1",
            "policy_id": "default-bounded-multi-agent-orchestration",
            "version": "1.0.0",
            "child_count": 2,
            "max_parallelism": 2,
            "max_depth": 1,
            "failure_mode": "ALL_REQUIRED_FAIL_FAST",
            "cancellation_mode": "CANCEL_PENDING_SIBLINGS",
            "aggregation_mode": "DECLARATION_ORDER_STRUCTURED",
            "child_output_contract": "CodingAgentResult",
            "root_output_contract": "BoundedOrchestrationResult",
            "child_session_mode": "disabled",
            "read_only_language_only": True,
            "native_child_streaming": False,
            "workspace_access": "none",
        }
        if payload != exact:
            raise BoundedOrchestrationPolicyError(
                "Bounded orchestration policy does not match the STEP062 V1 contract"
            )
        return BoundedOrchestrationPolicy(
            **payload,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
