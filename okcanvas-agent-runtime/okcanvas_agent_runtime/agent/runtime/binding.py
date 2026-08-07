from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from okcanvas_agent_runtime.agent.definitions import AgentDefinition


@dataclass(frozen=True)
class AgentRuntimeBinding:
    schema_version: str
    agent_definition_id: str
    agent_definition_version: str
    agent_definition_sha256: str
    execution_path: str
    sdk_package: str
    sdk_version: str
    capability_topology: dict[str, object]
    capability_topology_runtime_sha256: str
    sdk_example_inventory_sha256: str
    architecture_constitution: dict[str, object]
    architecture_constitution_runtime_sha256: str
    model_routing_policy: dict[str, object]
    model_provider_runtime_sha256: str
    model_retry_policy: dict[str, object]
    model_retry_runtime_sha256: str
    reasoning_evidence_policy: dict[str, object]
    reasoning_evidence_runtime_sha256: str
    response_storage_policy: dict[str, object]
    response_storage_runtime_sha256: str
    provider_identifier_policy: dict[str, object]
    provider_identifier_runtime_sha256: str
    trace_export_policy: dict[str, object]
    trace_export_runtime_sha256: str
    sandbox_runtime_foundation: dict[str, object]
    sandbox_runtime_sha256: str
    output_contract: str
    output_contract_runtime_sha256: str
    input_mode: str
    attachment_policy: dict[str, object] | None
    multimodal_model_policy: dict[str, object] | None
    attachment_runtime_sha256: str | None
    mcp_servers: tuple[dict[str, str], ...]
    hosted_tools: tuple[dict[str, object], ...]
    hosted_tool_runtime_sha256: str | None
    skills: tuple[dict[str, object], ...]
    skill_runtime_sha256: str | None
    local_tools: tuple[dict[str, str], ...]
    child_agents: tuple[dict[str, object], ...]
    invocation_policy: dict[str, object]
    invocation_scope_runtime_sha256: str
    handoff_policy: dict[str, object] | None
    handoff_runtime_sha256: str | None
    agent_tool_policy: dict[str, object] | None
    agent_tool_runtime_sha256: str | None
    orchestration_policy: dict[str, object] | None
    orchestration_runtime_sha256: str | None
    session_policy: dict[str, object] | None
    session_runtime_sha256: str | None
    guardrails: tuple[dict[str, object], ...]
    guardrail_runtime_sha256: str | None
    execution_engine_sha256: str
    runtime_binding_sha256: str

    def to_fingerprint_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "execution_path": self.execution_path,
            "sdk_package": self.sdk_package,
            "sdk_version": self.sdk_version,
            "capability_topology": dict(self.capability_topology),
            "capability_topology_runtime_sha256": self.capability_topology_runtime_sha256,
            "sdk_example_inventory_sha256": self.sdk_example_inventory_sha256,
            "architecture_constitution": dict(self.architecture_constitution),
            "architecture_constitution_runtime_sha256": self.architecture_constitution_runtime_sha256,
            "model_routing_policy": dict(self.model_routing_policy),
            "model_provider_runtime_sha256": self.model_provider_runtime_sha256,
            "model_retry_policy": dict(self.model_retry_policy),
            "model_retry_runtime_sha256": self.model_retry_runtime_sha256,
            "reasoning_evidence_policy": dict(self.reasoning_evidence_policy),
            "reasoning_evidence_runtime_sha256": self.reasoning_evidence_runtime_sha256,
            "response_storage_policy": dict(self.response_storage_policy),
            "response_storage_runtime_sha256": self.response_storage_runtime_sha256,
            "provider_identifier_policy": dict(self.provider_identifier_policy),
            "provider_identifier_runtime_sha256": self.provider_identifier_runtime_sha256,
            "trace_export_policy": dict(self.trace_export_policy),
            "trace_export_runtime_sha256": self.trace_export_runtime_sha256,
            "sandbox_runtime_foundation": dict(self.sandbox_runtime_foundation),
            "sandbox_runtime_sha256": self.sandbox_runtime_sha256,
            "output_contract": self.output_contract,
            "output_contract_runtime_sha256": self.output_contract_runtime_sha256,
            "input_mode": self.input_mode,
            "attachment_policy": dict(self.attachment_policy) if self.attachment_policy else None,
            "multimodal_model_policy": dict(self.multimodal_model_policy) if self.multimodal_model_policy else None,
            "attachment_runtime_sha256": self.attachment_runtime_sha256,
            "mcp_servers": [dict(item) for item in self.mcp_servers],
            "hosted_tools": [dict(item) for item in self.hosted_tools],
            "hosted_tool_runtime_sha256": self.hosted_tool_runtime_sha256,
            "skills": [dict(item) for item in self.skills],
            "skill_runtime_sha256": self.skill_runtime_sha256,
            "local_tools": [dict(item) for item in self.local_tools],
            "child_agents": [dict(item) for item in self.child_agents],
            "invocation_policy": dict(self.invocation_policy),
            "invocation_scope_runtime_sha256": self.invocation_scope_runtime_sha256,
            "handoff_policy": dict(self.handoff_policy) if self.handoff_policy else None,
            "handoff_runtime_sha256": self.handoff_runtime_sha256,
            "agent_tool_policy": dict(self.agent_tool_policy) if self.agent_tool_policy else None,
            "agent_tool_runtime_sha256": self.agent_tool_runtime_sha256,
            "orchestration_policy": (
                dict(self.orchestration_policy) if self.orchestration_policy else None
            ),
            "orchestration_runtime_sha256": self.orchestration_runtime_sha256,
            "session_policy": dict(self.session_policy) if self.session_policy else None,
            "session_runtime_sha256": self.session_runtime_sha256,
            "guardrails": [dict(item) for item in self.guardrails],
            "guardrail_runtime_sha256": self.guardrail_runtime_sha256,
            "execution_engine_sha256": self.execution_engine_sha256,
            "runtime_binding_sha256": self.runtime_binding_sha256,
        }


class RuntimeBindingResolver(Protocol):
    def resolve(self, definition: AgentDefinition) -> AgentRuntimeBinding: ...
