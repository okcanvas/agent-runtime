from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    version: str
    agent_definition_id: str
    required_result: dict[str, Any]
    forbidden_result: dict[str, Any]
    required_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    max_total_tokens: int | None
    max_duration_ms: int | None
    manifest_sha256: str


@dataclass(frozen=True)
class EvaluationResult:
    evaluation_id: str
    case_id: str
    case_version: str
    subject_run_id: str
    state: str
    checks: dict[str, bool]
    metrics: dict[str, int]
    failures: tuple[str, ...]
    created_at: str
