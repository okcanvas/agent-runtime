from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

from okcanvas_agent_runtime.application.evaluation.application import PreparedRecordedRunEvaluation, RecordedRunEvaluationError, RecordedRunEvaluationService
from okcanvas_agent_runtime.application.evaluation.models import EvaluationCase
from okcanvas_agent_runtime.application.ports import EvaluationStorePort

_VALID_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_")
_GLOBAL_MAX_SUBJECTS = 20


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _valid_identifier(value: str) -> bool:
    return bool(value) and len(value) <= 128 and all(character in _VALID_ID_CHARS for character in value)


@dataclass(frozen=True)
class EvaluationSuiteSlot:
    slot_id: str
    case_id: str
    required: bool


@dataclass(frozen=True)
class BaselineComparisonPolicy:
    max_passed_to_failed: int
    max_total_tokens_increase_percent: int
    max_duration_increase_percent: int
    max_tool_call_increase: int


@dataclass(frozen=True)
class EvaluationSuite:
    suite_id: str
    version: str
    slots: tuple[EvaluationSuiteSlot, ...]
    max_subjects: int
    comparison: BaselineComparisonPolicy
    manifest_sha256: str


@dataclass(frozen=True)
class EvaluationSuiteSubject:
    subject_id: str
    slot_id: str
    run_id: str


class EvaluationSuiteErrorCode(StrEnum):
    SUITE_NOT_FOUND = "SUITE_NOT_FOUND"
    SUITE_INVALID = "SUITE_INVALID"
    SUBJECTS_INVALID = "SUBJECTS_INVALID"
    BATCH_LIMIT_EXCEEDED = "BATCH_LIMIT_EXCEEDED"
    RECORDED_RUN_INVALID = "RECORDED_RUN_INVALID"
    BASELINE_NOT_FOUND = "BASELINE_NOT_FOUND"
    BASELINE_INCOMPATIBLE = "BASELINE_INCOMPATIBLE"
    BASELINE_SOURCE_NOT_FOUND = "BASELINE_SOURCE_NOT_FOUND"
    BASELINE_SOURCE_NOT_PASSED = "BASELINE_SOURCE_NOT_PASSED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class EvaluationSuiteError(RuntimeError):
    def __init__(
        self,
        code: EvaluationSuiteErrorCode,
        message: str,
        *,
        detail_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail_type = detail_type


class EvaluationSuiteCatalog:
    _ALLOWED_KEYS = {
        "schema_version",
        "suite_id",
        "version",
        "slots",
        "max_subjects",
        "baseline_comparison",
    }
    _COMPARISON_KEYS = {
        "max_passed_to_failed",
        "max_total_tokens_increase_percent",
        "max_duration_increase_percent",
        "max_tool_call_increase",
    }

    def __init__(self, project_root: str | Path) -> None:
        self.root = Path(project_root).expanduser().resolve()
        self.spec_root = self.root / "specs" / "evaluation-suites"

    def list_suites(self) -> tuple[EvaluationSuite, ...]:
        if not self.spec_root.is_dir():
            return ()
        suites: list[EvaluationSuite] = []
        for entry in sorted(self.spec_root.iterdir(), key=lambda item: item.name):
            if entry.is_symlink():
                raise ValueError(f"symbolic evaluation suite directories are forbidden: {entry.name}")
            if not entry.is_dir():
                continue
            if not _valid_identifier(entry.name):
                raise ValueError(f"invalid evaluation suite directory: {entry.name}")
            suites.append(self.resolve(entry.name))
        return tuple(suites)

    def resolve(self, suite_id: str) -> EvaluationSuite:
        if not _valid_identifier(suite_id):
            raise ValueError("invalid suite_id")
        directory = self.spec_root / suite_id
        if directory.is_symlink():
            raise ValueError("symbolic evaluation suite directories are forbidden")
        path = directory / "suite.json"
        if path.is_symlink():
            raise ValueError("symbolic evaluation suite files are forbidden")
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"evaluation suite not found: {suite_id}") from exc
        if self.spec_root.resolve() not in resolved.parents:
            raise ValueError("evaluation suite path escapes spec root")
        raw = resolved.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("evaluation suite must be an object")
        unknown = set(data) - self._ALLOWED_KEYS
        missing = self._ALLOWED_KEYS - set(data)
        if unknown or missing:
            raise ValueError(
                f"evaluation suite fields mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        if data.get("schema_version") != "okcanvas-evaluation-suite-v1":
            raise ValueError("unsupported evaluation suite schema")
        if data.get("suite_id") != suite_id:
            raise ValueError("evaluation suite ID does not match its directory")
        version = data.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError("evaluation suite version must be a non-empty string")
        raw_slots = data.get("slots")
        if not isinstance(raw_slots, list) or not raw_slots:
            raise ValueError("evaluation suite slots must be a non-empty list")
        slots: list[EvaluationSuiteSlot] = []
        seen_slots: set[str] = set()
        for raw_slot in raw_slots:
            if not isinstance(raw_slot, dict) or set(raw_slot) != {"slot_id", "case_id", "required"}:
                raise ValueError("evaluation suite slot fields are invalid")
            slot_id = raw_slot.get("slot_id")
            case_id = raw_slot.get("case_id")
            required = raw_slot.get("required")
            if not isinstance(slot_id, str) or not _valid_identifier(slot_id):
                raise ValueError("evaluation suite slot_id is invalid")
            if not isinstance(case_id, str) or not _valid_identifier(case_id):
                raise ValueError("evaluation suite case_id is invalid")
            if not isinstance(required, bool):
                raise ValueError("evaluation suite slot required must be boolean")
            if slot_id in seen_slots:
                raise ValueError("evaluation suite slot IDs must be unique")
            seen_slots.add(slot_id)
            slots.append(EvaluationSuiteSlot(slot_id=slot_id, case_id=case_id, required=required))
        max_subjects = data.get("max_subjects")
        if isinstance(max_subjects, bool) or not isinstance(max_subjects, int):
            raise ValueError("evaluation suite max_subjects must be an integer")
        if not 1 <= max_subjects <= _GLOBAL_MAX_SUBJECTS:
            raise ValueError(f"evaluation suite max_subjects must be 1..{_GLOBAL_MAX_SUBJECTS}")
        comparison_data = data.get("baseline_comparison")
        if not isinstance(comparison_data, dict) or set(comparison_data) != self._COMPARISON_KEYS:
            raise ValueError("evaluation suite baseline comparison fields are invalid")
        values: dict[str, int] = {}
        for key in self._COMPARISON_KEYS:
            value = comparison_data.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"evaluation suite {key} must be a non-negative integer")
            values[key] = value
        return EvaluationSuite(
            suite_id=suite_id,
            version=version,
            slots=tuple(slots),
            max_subjects=max_subjects,
            comparison=BaselineComparisonPolicy(**values),
            manifest_sha256=hashlib.sha256(raw).hexdigest(),
        )


def _aggregate(prepared: Iterable[tuple[EvaluationSuiteSubject, PreparedRecordedRunEvaluation]]) -> dict[str, int]:
    items = list(prepared)
    passed = sum(item.outcome.evaluation.state == "PASSED" for _subject, item in items)
    total_tokens = sum(int(item.outcome.evaluation.metrics["total_tokens"]) for _subject, item in items)
    duration_ms = sum(int(item.outcome.evaluation.metrics["duration_ms"]) for _subject, item in items)
    tool_calls = sum(int(item.outcome.evaluation.metrics["tool_calls"]) for _subject, item in items)
    requests = sum(int(item.outcome.evaluation.metrics["requests"]) for _subject, item in items)
    count = len(items)
    return {
        "evaluation_count": count,
        "passed": passed,
        "failed": count - passed,
        "pass_rate_basis_points": (passed * 10_000 // count) if count else 0,
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
        "tool_calls": tool_calls,
        "requests": requests,
    }


def _percent_increase(current: int, baseline: int) -> int:
    if current <= baseline:
        return 0
    if baseline == 0:
        return 100 if current > 0 else 0
    return ((current - baseline) * 100 + baseline - 1) // baseline


class EvaluationSuiteService:
    def __init__(
        self,
        *,
        project_root: str | Path,
        recorded_run_service: RecordedRunEvaluationService,
        evaluation_store: EvaluationStorePort,
    ) -> None:
        self._catalog = EvaluationSuiteCatalog(project_root)
        self._recorded = recorded_run_service
        self._store = evaluation_store

    def run_suite(
        self,
        *,
        suite_id: str,
        subjects: Iterable[EvaluationSuiteSubject],
        baseline_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            suite = self._catalog.resolve(suite_id)
        except FileNotFoundError as exc:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.SUITE_NOT_FOUND, "Evaluation Suite was not found"
            ) from exc
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.SUITE_INVALID,
                "Evaluation Suite is invalid",
                detail_type=type(exc).__name__,
            ) from exc

        requested = tuple(subjects)
        if not requested:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.SUBJECTS_INVALID,
                "At least one explicit Suite subject is required",
            )
        if len(requested) > suite.max_subjects or len(requested) > _GLOBAL_MAX_SUBJECTS:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.BATCH_LIMIT_EXCEEDED,
                "Evaluation Suite subject batch exceeds its configured limit",
            )
        slot_map = {slot.slot_id: slot for slot in suite.slots}
        subject_ids: set[str] = set()
        represented_slots: set[str] = set()
        for subject in requested:
            if not _valid_identifier(subject.subject_id):
                raise EvaluationSuiteError(
                    EvaluationSuiteErrorCode.SUBJECTS_INVALID, "Suite subject_id is invalid"
                )
            if subject.subject_id in subject_ids:
                raise EvaluationSuiteError(
                    EvaluationSuiteErrorCode.SUBJECTS_INVALID,
                    "Suite subject IDs must be unique",
                )
            if subject.slot_id not in slot_map:
                raise EvaluationSuiteError(
                    EvaluationSuiteErrorCode.SUBJECTS_INVALID,
                    "Suite subject references an unknown slot",
                )
            if not subject.run_id or len(subject.run_id) > 128:
                raise EvaluationSuiteError(
                    EvaluationSuiteErrorCode.SUBJECTS_INVALID, "Suite subject run_id is invalid"
                )
            subject_ids.add(subject.subject_id)
            represented_slots.add(subject.slot_id)
        missing_required = sorted(
            slot.slot_id for slot in suite.slots if slot.required and slot.slot_id not in represented_slots
        )
        if missing_required:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.SUBJECTS_INVALID,
                f"Required Suite slots are missing: {', '.join(missing_required)}",
            )

        baseline: dict[str, Any] | None = None
        if baseline_id is not None:
            try:
                baseline = self._store.get_baseline(baseline_id)
            except KeyError as exc:
                raise EvaluationSuiteError(
                    EvaluationSuiteErrorCode.BASELINE_NOT_FOUND,
                    "Evaluation Baseline was not found",
                ) from exc
            if (
                baseline["suite_id"] != suite.suite_id
                or baseline["suite_version"] != suite.version
                or baseline["suite_manifest_sha256"] != suite.manifest_sha256
            ):
                raise EvaluationSuiteError(
                    EvaluationSuiteErrorCode.BASELINE_INCOMPATIBLE,
                    "Evaluation Baseline does not match the Suite identity",
                )

        prepared_items: list[tuple[EvaluationSuiteSubject, PreparedRecordedRunEvaluation]] = []
        try:
            for subject in requested:
                slot = slot_map[subject.slot_id]
                prepared_items.append(
                    (
                        subject,
                        self._recorded.prepare(run_id=subject.run_id, case_id=slot.case_id),
                    )
                )
        except RecordedRunEvaluationError as exc:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.RECORDED_RUN_INVALID,
                "One or more recorded Runs could not be evaluated",
                detail_type=exc.code.value,
            ) from exc

        aggregate = _aggregate(prepared_items)
        current_members = [
            {
                "subject_id": subject.subject_id,
                "slot_id": subject.slot_id,
                "case_id": prepared.case.case_id,
                "subject_run_id": subject.run_id,
                "evaluation_id": prepared.outcome.evaluation.evaluation_id,
                "state": prepared.outcome.evaluation.state,
                "metrics": dict(prepared.outcome.evaluation.metrics),
            }
            for subject, prepared in prepared_items
        ]
        regressions: list[dict[str, Any]] = []
        comparison_state = "NOT_COMPARED"
        if baseline is not None:
            baseline_members = {
                (item["subject_id"], item["slot_id"], item["case_id"]): item
                for item in baseline["members"]
            }
            current_members_by_key = {
                (item["subject_id"], item["slot_id"], item["case_id"]): item
                for item in current_members
            }
            if set(baseline_members) != set(current_members_by_key):
                raise EvaluationSuiteError(
                    EvaluationSuiteErrorCode.BASELINE_INCOMPATIBLE,
                    "Evaluation Baseline subject shape does not match this Suite execution",
                )
            passed_to_failed = sum(
                baseline_members[key]["state"] == "PASSED"
                and current_members_by_key[key]["state"] == "FAILED"
                for key in baseline_members
            )
            if passed_to_failed > suite.comparison.max_passed_to_failed:
                regressions.append(
                    {
                        "metric": "passed_to_failed",
                        "actual": passed_to_failed,
                        "allowed": suite.comparison.max_passed_to_failed,
                    }
                )
            baseline_aggregate = baseline["aggregate"]
            token_increase = _percent_increase(
                aggregate["total_tokens"], int(baseline_aggregate["total_tokens"])
            )
            if token_increase > suite.comparison.max_total_tokens_increase_percent:
                regressions.append(
                    {
                        "metric": "total_tokens_increase_percent",
                        "actual": token_increase,
                        "allowed": suite.comparison.max_total_tokens_increase_percent,
                    }
                )
            duration_increase = _percent_increase(
                aggregate["duration_ms"], int(baseline_aggregate["duration_ms"])
            )
            if duration_increase > suite.comparison.max_duration_increase_percent:
                regressions.append(
                    {
                        "metric": "duration_increase_percent",
                        "actual": duration_increase,
                        "allowed": suite.comparison.max_duration_increase_percent,
                    }
                )
            tool_call_increase = aggregate["tool_calls"] - int(baseline_aggregate["tool_calls"])
            if tool_call_increase > suite.comparison.max_tool_call_increase:
                regressions.append(
                    {
                        "metric": "tool_call_increase",
                        "actual": tool_call_increase,
                        "allowed": suite.comparison.max_tool_call_increase,
                    }
                )
            comparison_state = "REGRESSED" if regressions else "MATCHED"

        created_at = _now()
        suite_run = {
            "suite_run_id": f"suite_run_{uuid.uuid4().hex}",
            "suite_id": suite.suite_id,
            "suite_version": suite.version,
            "suite_manifest_sha256": suite.manifest_sha256,
            "state": "PASSED" if aggregate["failed"] == 0 else "FAILED",
            "comparison_state": comparison_state,
            "baseline_id": baseline_id,
            "subject_count": len(requested),
            "evaluation_count": len(prepared_items),
            "aggregate": aggregate,
            "regressions": regressions,
            "created_at": created_at,
        }
        evaluations: list[tuple[EvaluationCase, dict[str, Any], Any]] = [
            (prepared.case, prepared.envelope, prepared.outcome.evaluation)
            for _subject, prepared in prepared_items
        ]
        try:
            self._store.save_suite_bundle(
                evaluations=evaluations, suite_run=suite_run, members=current_members
            )
        except Exception as exc:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.PERSISTENCE_FAILED,
                "Evaluation Suite result could not be persisted",
                detail_type=type(exc).__name__,
            ) from exc
        return self._store.get_suite_run(suite_run["suite_run_id"])

    def create_baseline(self, *, source_suite_run_id: str, label: str) -> dict[str, Any]:
        normalized_label = label.strip()
        if not normalized_label or len(normalized_label) > 100:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.SUBJECTS_INVALID,
                "Evaluation Baseline label must be 1..100 characters",
            )
        try:
            source = self._store.get_suite_run(source_suite_run_id)
        except KeyError as exc:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.BASELINE_SOURCE_NOT_FOUND,
                "Source Evaluation Suite run was not found",
            ) from exc
        if source["state"] != "PASSED":
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.BASELINE_SOURCE_NOT_PASSED,
                "Only a passed Evaluation Suite run can become a Baseline",
            )
        baseline = {
            "baseline_id": f"baseline_{uuid.uuid4().hex}",
            "suite_id": source["suite_id"],
            "suite_version": source["suite_version"],
            "suite_manifest_sha256": source["suite_manifest_sha256"],
            "source_suite_run_id": source_suite_run_id,
            "label": normalized_label,
            "aggregate": source["aggregate"],
            "members": [
                {
                    "subject_id": item["subject_id"],
                    "slot_id": item["slot_id"],
                    "case_id": item["case_id"],
                    "state": item["state"],
                    "metrics": item["metrics"],
                }
                for item in source["members"]
            ],
            "created_at": _now(),
        }
        try:
            self._store.create_baseline(baseline)
        except Exception as exc:
            raise EvaluationSuiteError(
                EvaluationSuiteErrorCode.PERSISTENCE_FAILED,
                "Evaluation Baseline could not be persisted",
                detail_type=type(exc).__name__,
            ) from exc
        return self._store.get_baseline(baseline["baseline_id"])
