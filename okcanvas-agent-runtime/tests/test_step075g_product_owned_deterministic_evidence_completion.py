from __future__ import annotations

from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, CodingFinding
from okcanvas_agent_runtime.application.execution.sandbox_answer_completeness import (
    assess_sandbox_answer_completeness,
    complete_sandbox_answer_from_evidence,
)
from okcanvas_agent_runtime.agent.tools.function.models import SandboxProjectReadonlyInspectOutput


REQUEST = (
    "Inspect calculate_reorder and report the exact formula, constant value, identifiers, "
    "operators, literals, implementation file, and evidence line range."
)


def _tool_output() -> SandboxProjectReadonlyInspectOutput:
    return SandboxProjectReadonlyInspectOutput.model_validate(
        {
            "workspace_label": "bounded-project",
            "snapshot_sha256": "a" * 64,
            "files_considered": 3,
            "bytes_considered": 128,
            "inspected_files": ["src/inventory.py"],
            "evidence": [
                {
                    "path": "src/inventory.py",
                    "line_start": 1,
                    "line_end": 4,
                    "excerpt": (
                        "SAFETY_STOCK = 12\n\n"
                        "def calculate_reorder(on_hand: int, forecast: int) -> int:\n"
                        "    return max(0, forecast + SAFETY_STOCK - on_hand)"
                    ),
                }
            ],
            "evidence_characters": 128,
            "query_terms_considered": 4,
            "truncated": False,
            "workspace_access": "sandbox-readonly-v1",
            "workspace_materialized": True,
            "docker_call_count": 9,
            "selected_file_hashes_verified": True,
            "cleanup_state": "COMPLETED",
            "orphan_count": 0,
            "image_binding_sha256": "b" * 64,
            "network_mode": "none",
            "shell_enabled": False,
            "apply_patch_enabled": False,
        },
        strict=True,
    )


def _draft(*, findings: int = 1) -> CodingAgentResult:
    existing = [
        CodingFinding.model_validate(
            {
                "severity": "INFO",
                "confidence": "CONFIRMED",
                "title": f"Finding {index}",
                "detail": "The function uses a bounded non-negative calculation.",
                "evidence": ["src/inventory.py lines 1-4"],
            }
        )
        for index in range(findings)
    ]
    return CodingAgentResult(
        status=AgentStatus.PASS,
        summary="The implementation is simple and clear.",
        findings=existing,
        unverified=["src/inventory.py", "Independent integration behavior"],
    )


def test_deterministic_completion_inserts_only_hash_verified_exact_fragments() -> None:
    tool_output = _tool_output()
    draft = _draft()
    assessment = assess_sandbox_answer_completeness(
        request=REQUEST, output=draft, tool_output=tool_output
    )
    completion = complete_sandbox_answer_from_evidence(
        draft=draft, tool_output=tool_output, assessment=assessment
    )
    completed = completion.output
    serialized = completed.model_dump_json()

    assert completion.added_finding is True
    assert completion.removed_unverified_count == 1
    assert completion.required_fragment_count == 3
    assert completion.evidence_reference_count == 1
    assert "calculate_reorder" in serialized
    assert "max(0, forecast + SAFETY_STOCK - on_hand)" in serialized
    assert "SAFETY_STOCK = 12" in serialized
    assert "src/inventory.py lines 1-4" in serialized
    assert completed.unverified == ["Independent integration behavior"]
    assert completed.summary == draft.summary
    assert assess_sandbox_answer_completeness(
        request=REQUEST, output=completed, tool_output=tool_output
    ).complete is True


def test_deterministic_completion_respects_finding_contract_bound() -> None:
    tool_output = _tool_output()
    draft = _draft(findings=100)
    assessment = assess_sandbox_answer_completeness(
        request=REQUEST, output=draft, tool_output=tool_output
    )
    completed = complete_sandbox_answer_from_evidence(
        draft=draft, tool_output=tool_output, assessment=assessment
    ).output

    assert len(completed.findings) == 100
    assert completed.findings[-1].title == "Exact verified evidence"
    assert completed.findings[0].title == "Finding 0"
    assert completed.findings[-2].title == "Finding 98"


def test_completion_fails_closed_when_exact_requirements_cannot_be_derived() -> None:
    tool_output = _tool_output()
    draft = _draft()
    assessment = assess_sandbox_answer_completeness(
        request="Report the exact formula for missing_function.",
        output=draft,
        tool_output=tool_output,
    )
    assert "EXACT_FACT_REQUIREMENTS_NOT_DERIVED" in assessment.issue_codes

    try:
        complete_sandbox_answer_from_evidence(
            draft=draft, tool_output=tool_output, assessment=assessment
        )
    except ValueError as exc:
        assert "could not be derived" in str(exc)
    else:
        raise AssertionError("Expected deterministic completion to fail closed")


def test_complete_output_is_returned_without_mutation() -> None:
    tool_output = _tool_output()
    draft = CodingAgentResult.model_validate(
        {
            "status": "PASS",
            "summary": (
                "src/inventory.py lines 1-4 defines SAFETY_STOCK = 12 and "
                "calculate_reorder returns max(0, forecast + SAFETY_STOCK - on_hand)."
            ),
            "findings": [],
            "unverified": [],
        }
    )
    assessment = assess_sandbox_answer_completeness(
        request=REQUEST, output=draft, tool_output=tool_output
    )
    completion = complete_sandbox_answer_from_evidence(
        draft=draft, tool_output=tool_output, assessment=assessment
    )

    assert completion.output is draft
    assert completion.added_finding is False
    assert completion.removed_unverified_count == 0
