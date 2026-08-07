from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from okcanvas_agent_runtime.core.contracts import CodingAgentResult, CodingFinding, FindingConfidence, FindingSeverity
from okcanvas_agent_runtime.agent.tools.function.models import SandboxProjectReadonlyInspectOutput


_EXACTNESS_TERMS = (
    "exact",
    "formula",
    "signature",
    "constant value",
    "assignment",
    "literal",
    "operator",
    "정확",
    "수식",
    "시그니처",
    "상수 값",
)
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_FUNCTION_DEF = re.compile(
    r"^\s*def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<params>[^)]*)\)\s*(?:->\s*[^:]+)?\s*:\s*$"
)
_ASSIGNMENT = re.compile(
    r"^\s*(?P<name>[A-Z][A-Z0-9_]*)\s*=\s*(?P<value>[^#\n]+?)\s*$"
)
_RETURN = re.compile(r"^\s*return\s+(?P<expression>.+?)\s*$")


@dataclass(frozen=True)
class SandboxAnswerCompletenessAssessment:
    exactness_requested: bool
    complete: bool
    issue_codes: tuple[str, ...]
    required_fragments: tuple[str, ...]
    evidence_paths: tuple[str, ...]

    @property
    def repair_required(self) -> bool:
        return not self.complete


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _serialized_output(output: CodingAgentResult) -> str:
    return json.dumps(output.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def _requested_function_names(request: str, evidence_text: str) -> tuple[str, ...]:
    request_identifiers = set(_IDENTIFIER.findall(request))
    names: list[str] = []
    for line in evidence_text.splitlines():
        match = _FUNCTION_DEF.match(line)
        if match and match.group("name") in request_identifiers:
            names.append(match.group("name"))
    return tuple(dict.fromkeys(names))


def _required_fragments_for_function(
    function_name: str,
    evidence_text: str,
    *,
    include_signature: bool,
) -> tuple[str, ...]:
    lines = evidence_text.splitlines()
    signature: str | None = None
    expression: str | None = None
    for index, line in enumerate(lines):
        match = _FUNCTION_DEF.match(line)
        if not match or match.group("name") != function_name:
            continue
        signature = line.strip()
        signature_indent = len(line) - len(line.lstrip())
        for candidate in lines[index + 1 :]:
            if not candidate.strip():
                continue
            candidate_indent = len(candidate) - len(candidate.lstrip())
            if candidate_indent <= signature_indent:
                break
            returned = _RETURN.match(candidate)
            if returned:
                expression = returned.group("expression").strip()
                break
        break

    fragments: list[str] = [function_name]
    if signature and include_signature:
        fragments.append(signature)
    if expression:
        fragments.append(expression)
        referenced_constants = {
            token
            for token in _IDENTIFIER.findall(expression)
            if token.isupper() and ("_" in token or len(token) > 1)
        }
        for line in lines:
            assignment = _ASSIGNMENT.match(line)
            if assignment and assignment.group("name") in referenced_constants:
                fragments.append(
                    f"{assignment.group('name')} = {assignment.group('value').strip()}"
                )
    return tuple(dict.fromkeys(fragments))


def assess_sandbox_answer_completeness(
    *,
    request: str,
    output: CodingAgentResult,
    tool_output: SandboxProjectReadonlyInspectOutput,
) -> SandboxAnswerCompletenessAssessment:
    exactness_requested = any(term in request.casefold() for term in _EXACTNESS_TERMS)
    evidence_text = "\n".join(item.excerpt for item in tool_output.evidence)
    evidence_paths = tuple(dict.fromkeys(tool_output.inspected_files))
    required_fragments: list[str] = []
    for function_name in _requested_function_names(request, evidence_text):
        required_fragments.extend(
            _required_fragments_for_function(
                function_name,
                evidence_text,
                include_signature="signature" in request.casefold() or "시그니처" in request,
            )
        )
    required = tuple(dict.fromkeys(required_fragments))

    serialized = _serialized_output(output)
    compact_output = _compact(serialized)
    issues: list[str] = []

    if exactness_requested:
        if not required:
            issues.append("EXACT_FACT_REQUIREMENTS_NOT_DERIVED")
        for fragment in required:
            if _compact(fragment) not in compact_output:
                issues.append("EXACT_EVIDENCE_FRAGMENT_MISSING")
                break
        if not any(path in serialized for path in evidence_paths):
            issues.append("EVIDENCE_PATH_MISSING")
    unverified_casefold = [item.casefold() for item in output.unverified]
    if any(
        path.casefold() in unresolved
        for path in evidence_paths
        for unresolved in unverified_casefold
    ):
        issues.append("EVIDENCE_BACKED_PATH_MARKED_UNVERIFIED")

    return SandboxAnswerCompletenessAssessment(
        exactness_requested=exactness_requested,
        complete=not issues,
        issue_codes=tuple(dict.fromkeys(issues)),
        required_fragments=required,
        evidence_paths=evidence_paths,
    )



@dataclass(frozen=True)
class SandboxAnswerDeterministicCompletion:
    output: CodingAgentResult
    added_finding: bool
    removed_unverified_count: int
    required_fragment_count: int
    evidence_reference_count: int


def complete_sandbox_answer_from_evidence(
    *,
    draft: CodingAgentResult,
    tool_output: SandboxProjectReadonlyInspectOutput,
    assessment: SandboxAnswerCompletenessAssessment,
) -> SandboxAnswerDeterministicCompletion:
    """Complete exact evidence requirements without another model or Tool call.

    Only fragments already derived from the single immutable, hash-verified Tool output are
    inserted. The original model findings are preserved up to the output contract bound,
    and evidence-backed paths are removed from ``unverified``.
    """

    if assessment.complete:
        return SandboxAnswerDeterministicCompletion(
            output=draft,
            added_finding=False,
            removed_unverified_count=0,
            required_fragment_count=len(assessment.required_fragments),
            evidence_reference_count=0,
        )
    if "EXACT_FACT_REQUIREMENTS_NOT_DERIVED" in assessment.issue_codes:
        raise ValueError("Exact evidence requirements could not be derived")
    if len(assessment.required_fragments) > 20:
        raise ValueError("Exact evidence fragment count exceeds the Product bound")

    evidence_references = tuple(
        dict.fromkeys(
            f"{item.path} lines {item.line_start}-{item.line_end}"
            for item in tool_output.evidence
            if item.path in assessment.evidence_paths
        )
    )
    if len(evidence_references) > 20:
        raise ValueError("Exact evidence reference count exceeds the Product bound")

    exact_lines = [
        "Exact verified evidence requested by the user:",
        *(f"- {fragment}" for fragment in assessment.required_fragments),
    ]
    detail = "\n".join(exact_lines)
    if len(detail) > 4000:
        raise ValueError("Exact evidence completion exceeds the output contract bound")

    findings = list(draft.findings)
    added_finding = bool(assessment.required_fragments or evidence_references)
    if added_finding:
        if len(findings) >= 100:
            findings = findings[:99]
        findings.append(
            CodingFinding(
                severity=FindingSeverity.INFO,
                confidence=FindingConfidence.CONFIRMED,
                title="Exact verified evidence",
                detail=detail,
                evidence=list(evidence_references),
            )
        )

    evidence_paths_casefold = tuple(path.casefold() for path in assessment.evidence_paths)
    cleaned_unverified = [
        item
        for item in draft.unverified
        if not any(path in item.casefold() for path in evidence_paths_casefold)
    ]
    completed_output = CodingAgentResult(
        status=draft.status,
        summary=draft.summary,
        findings=findings,
        unverified=cleaned_unverified,
    )
    return SandboxAnswerDeterministicCompletion(
        output=completed_output,
        added_finding=added_finding,
        removed_unverified_count=len(draft.unverified) - len(cleaned_unverified),
        required_fragment_count=len(assessment.required_fragments),
        evidence_reference_count=len(evidence_references),
    )

def build_sandbox_answer_repair_prompt(
    *,
    request: str,
    draft: CodingAgentResult,
    tool_output: SandboxProjectReadonlyInspectOutput,
    assessment: SandboxAnswerCompletenessAssessment,
) -> str:
    evidence = [
        {
            "path": item.path,
            "line_start": item.line_start,
            "line_end": item.line_end,
            "excerpt": item.excerpt,
        }
        for item in tool_output.evidence
    ]
    payload = {
        "original_request": request,
        "draft": draft.model_dump(mode="json"),
        "evidence": evidence,
        "required_exact_fragments": list(assessment.required_fragments),
        "issue_codes": list(assessment.issue_codes),
    }
    return (
        "Repair the structured coding answer using only the bounded evidence below. "
        "Do not call tools. Preserve exact identifiers, operators, literals, function signatures, "
        "constant assignments, and complete expressions requested by the user; never replace them "
        "with ellipsis or a generic paraphrase. Cite repository-relative paths and line ranges. "
        "Do not place an evidence-backed path in unverified. Return only CodingAgentResult.\n\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def find_sandbox_tool_output(items: Iterable[object]) -> SandboxProjectReadonlyInspectOutput | None:
    matches: list[SandboxProjectReadonlyInspectOutput] = []
    for item in items:
        output = getattr(item, "output", None)
        if isinstance(output, SandboxProjectReadonlyInspectOutput):
            matches.append(output)
            continue
        if isinstance(output, dict):
            try:
                matches.append(SandboxProjectReadonlyInspectOutput.model_validate(output, strict=True))
            except Exception:
                continue
        if isinstance(output, str):
            try:
                matches.append(
                    SandboxProjectReadonlyInspectOutput.model_validate_json(output, strict=True)
                )
            except Exception:
                continue
    return matches[0] if len(matches) == 1 else None
