from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScenarioActionMode(str, Enum):
    RUN = "RUN"
    RUN_AND_EVALUATE = "RUN_AND_EVALUATE"
    PREPARE_APPROVAL = "PREPARE_APPROVAL"
    SESSION_TWO_TURN = "SESSION_TWO_TURN"
    EXPECTED_FAILURE = "EXPECTED_FAILURE"


@dataclass(frozen=True)
class WalkingSkeletonScenario:
    scenario_id: str
    title: str
    summary: str
    agent_definition_id: str
    action_mode: ScenarioActionMode
    request_templates: tuple[str, ...]
    evaluation_case_id: str | None
    expected_terminal_state: str
    expected_error_code: str | None
    requires_session: bool
    requires_approval_operator: bool
    capabilities: tuple[str, ...]
    invocation_kinds: tuple[str, ...]
    workspace_access: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "summary": self.summary,
            "agent_definition_id": self.agent_definition_id,
            "action_mode": self.action_mode.value,
            "request_templates": list(self.request_templates),
            "evaluation_case_id": self.evaluation_case_id,
            "expected_terminal_state": self.expected_terminal_state,
            "expected_error_code": self.expected_error_code,
            "requires_session": self.requires_session,
            "requires_approval_operator": self.requires_approval_operator,
            "capabilities": list(self.capabilities),
            "invocation_kinds": list(self.invocation_kinds),
            "workspace_access": self.workspace_access,
        }
