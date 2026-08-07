from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentToolPolicy:
    schema_version: str
    policy_id: str
    version: str
    max_agent_tool_calls_per_run: int
    max_depth: int
    input_mode: str
    output_mode: str
    max_result_bytes: int
    nested_stream_enabled: bool
    inherit_parent_run_config: bool
    require_same_output_contract: bool
    required_workspace_access: str
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "max_agent_tool_calls_per_run": self.max_agent_tool_calls_per_run,
            "max_depth": self.max_depth,
            "input_mode": self.input_mode,
            "output_mode": self.output_mode,
            "max_result_bytes": self.max_result_bytes,
            "nested_stream_enabled": self.nested_stream_enabled,
            "inherit_parent_run_config": self.inherit_parent_run_config,
            "require_same_output_contract": self.require_same_output_contract,
            "required_workspace_access": self.required_workspace_access,
            "policy_sha256": self.policy_sha256,
        }
