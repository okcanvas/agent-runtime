from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NativeHandoffPolicy:
    schema_version: str
    policy_id: str
    version: str
    max_handoffs_per_run: int
    max_depth: int
    input_filter_mode: str
    nest_handoff_history: bool
    handoff_input_payload_enabled: bool
    require_same_output_contract: bool
    required_workspace_access: str
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "max_handoffs_per_run": self.max_handoffs_per_run,
            "max_depth": self.max_depth,
            "input_filter_mode": self.input_filter_mode,
            "nest_handoff_history": self.nest_handoff_history,
            "handoff_input_payload_enabled": self.handoff_input_payload_enabled,
            "require_same_output_contract": self.require_same_output_contract,
            "required_workspace_access": self.required_workspace_access,
            "policy_sha256": self.policy_sha256,
        }
