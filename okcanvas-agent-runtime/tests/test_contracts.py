import pytest
from pydantic import ValidationError

from okcanvas_agent_runtime.core.contracts import (
    AgentStatus,
    CodingAgentResult,
    CodingFinding,
    FindingConfidence,
    FindingSeverity,
)


def test_coding_agent_result_is_strict() -> None:
    result = CodingAgentResult(
        status=AgentStatus.PARTIAL,
        summary="The request contains no executable evidence.",
        findings=[
            CodingFinding(
                severity=FindingSeverity.WARNING,
                confidence=FindingConfidence.CONFIRMED,
                title="No tool access",
                detail="STEP001 has no tools or workspace access.",
                evidence=["STEP001 runtime contract"],
            )
        ],
        unverified=["Repository state"],
    )
    assert result.status == AgentStatus.PARTIAL

    with pytest.raises(ValidationError):
        CodingAgentResult.model_validate(
            {
                "status": "PASS",
                "summary": "x",
                "findings": [],
                "unverified": [],
                "unexpected": True,
            }
        )
