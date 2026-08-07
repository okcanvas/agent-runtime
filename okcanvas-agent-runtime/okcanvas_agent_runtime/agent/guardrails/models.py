from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class GuardrailKind(StrEnum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    TOOL_INPUT = "TOOL_INPUT"
    TOOL_OUTPUT = "TOOL_OUTPUT"


@dataclass(frozen=True)
class GuardrailRuntime:
    schema_version: str
    guardrail_id: str
    version: str
    kind: GuardrailKind
    implementation_id: str
    marker: str | None
    tool_id: str | None
    run_in_parallel: bool
    behavior: str
    definition_sha256: str
    implementation_sha256: str
    directory: Path

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "guardrail_id": self.guardrail_id,
            "version": self.version,
            "kind": self.kind.value,
            "implementation_id": self.implementation_id,
            "marker_sha256": __import__("hashlib").sha256(self.marker.encode("utf-8")).hexdigest() if self.marker else None,
            "tool_id": self.tool_id,
            "run_in_parallel": self.run_in_parallel,
            "behavior": self.behavior,
            "definition_sha256": self.definition_sha256,
            "implementation_sha256": self.implementation_sha256,
        }

    def to_public_dict(self) -> dict[str, object]:
        return {
            "guardrail_id": self.guardrail_id,
            "version": self.version,
            "kind": self.kind.value,
            "tool_id": self.tool_id,
            "run_in_parallel": self.run_in_parallel,
            "behavior": self.behavior,
        }
