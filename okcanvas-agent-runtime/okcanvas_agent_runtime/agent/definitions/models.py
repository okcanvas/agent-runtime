from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentDefinition:
    schema_version: str
    agent_id: str
    version: str
    name: str
    instructions: str
    output_contract: str
    output_schema: dict[str, object]
    tools: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    hosted_tools: tuple[str, ...]
    skills: tuple[str, ...]
    handoffs: tuple[str, ...]
    agent_tools: tuple[str, ...]
    orchestration_children: tuple[str, ...]
    guardrails: tuple[str, ...]
    workspace_access: str
    max_turns: int
    workflow_name: str
    session_mode: str
    input_mode: str
    definition_sha256: str
    definition_path: Path
    instructions_path: Path
    output_schema_path: Path
    tool_capabilities: tuple[dict[str, object], ...]
    guardrail_capabilities: tuple[dict[str, object], ...]
    skill_capabilities: tuple[dict[str, object], ...]

    def to_public_dict(self) -> dict[str, object]:
        from okcanvas_agent_runtime.agent.capabilities.topology import AgentCapabilityTopologyCatalog

        project_root = self.definition_path.parents[3]
        capability_topology = AgentCapabilityTopologyCatalog(project_root).resolve(self)
        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "version": self.version,
            "name": self.name,
            "output_contract": self.output_contract,
            "tools": list(self.tools),
            "tool_capabilities": [dict(item) for item in self.tool_capabilities],
            "mcp_servers": list(self.mcp_servers),
            "hosted_tools": list(self.hosted_tools),
            "skills": list(self.skills),
            "skill_capabilities": [dict(item) for item in self.skill_capabilities],
            "handoffs": list(self.handoffs),
            "agent_tools": list(self.agent_tools),
            "orchestration_children": list(self.orchestration_children),
            "guardrails": list(self.guardrails),
            "guardrail_capabilities": [dict(item) for item in self.guardrail_capabilities],
            "workspace_access": self.workspace_access,
            "max_turns": self.max_turns,
            "workflow_name": self.workflow_name,
            "session_mode": self.session_mode,
            "input_mode": self.input_mode,
            "definition_sha256": self.definition_sha256,
            "capability_topology": capability_topology.to_public_dict(),
        }
