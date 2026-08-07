from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProductSkillResource:
    path: str
    media_type: str
    sha256: str
    byte_length: int
    text: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
        }


@dataclass(frozen=True)
class ProductSkillPackage:
    schema_version: str
    skill_id: str
    version: str
    name: str
    description: str
    execution_mode: str
    instructions: str
    instructions_sha256: str
    instructions_byte_length: int
    resources: tuple[ProductSkillResource, ...]
    allowed_agent_ids: tuple[str, ...]
    allowed_input_modes: tuple[str, ...]
    allowed_output_contracts: tuple[str, ...]
    required_tools: tuple[str, ...]
    required_mcp_servers: tuple[str, ...]
    required_hosted_tools: tuple[str, ...]
    workspace_access: str
    manifest_sha256: str
    package_sha256: str
    directory: Path
    manifest_path: Path

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "skill_id": self.skill_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "execution_mode": self.execution_mode,
            "resources": [item.to_public_dict() for item in self.resources],
            "allowed_agent_ids": list(self.allowed_agent_ids),
            "allowed_input_modes": list(self.allowed_input_modes),
            "allowed_output_contracts": list(self.allowed_output_contracts),
            "required_tools": list(self.required_tools),
            "required_mcp_servers": list(self.required_mcp_servers),
            "required_hosted_tools": list(self.required_hosted_tools),
            "workspace_access": self.workspace_access,
            "instructions_sha256": self.instructions_sha256,
            "instructions_byte_length": self.instructions_byte_length,
            "manifest_sha256": self.manifest_sha256,
            "package_sha256": self.package_sha256,
            "executable_code_included": False,
            "dynamic_dependency_installation": False,
            "client_side_execution": False,
        }

    def to_binding_dict(self) -> dict[str, object]:
        return self.to_public_dict()
