from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.definitions.errors import AgentDefinitionContractError, AgentDefinitionIntegrityError, AgentDefinitionNotFoundError
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.application.artifacts import ArtifactService
from okcanvas_agent_runtime.agent.runtime import RuntimeBindingResolver
from okcanvas_agent_runtime.application.execution.output_registry import validate_output_schema
from okcanvas_agent_runtime.domain.runs import RunStatus, TaskStatus
from okcanvas_agent_runtime.domain.runs.errors import ArtifactIntegrityError, RecordNotFoundError
from okcanvas_agent_runtime.domain.runs.ports import ProductStore

from okcanvas_agent_runtime.application.evaluation.models import EvaluationCase, EvaluationResult
from okcanvas_agent_runtime.application.evaluation.service import DeterministicEvaluator, EvaluationCatalog
from okcanvas_agent_runtime.application.ports import EvaluationStorePort

_MAX_FINAL_OUTPUT_BYTES = 1_048_576


class RecordedRunEvaluationErrorCode(StrEnum):
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    RUN_NOT_SUCCEEDED = "RUN_NOT_SUCCEEDED"
    TASK_NOT_SUCCEEDED = "TASK_NOT_SUCCEEDED"
    EVALUATION_CASE_NOT_FOUND = "EVALUATION_CASE_NOT_FOUND"
    EVALUATION_CASE_INVALID = "EVALUATION_CASE_INVALID"
    RUN_EVIDENCE_INCOMPLETE = "RUN_EVIDENCE_INCOMPLETE"
    RUN_EVIDENCE_INCONSISTENT = "RUN_EVIDENCE_INCONSISTENT"
    AGENT_DEFINITION_DRIFT = "AGENT_DEFINITION_DRIFT"
    RUNTIME_BINDING_DRIFT = "RUNTIME_BINDING_DRIFT"
    FINAL_OUTPUT_ARTIFACT_INVALID = "FINAL_OUTPUT_ARTIFACT_INVALID"
    FINAL_OUTPUT_CONTRACT_INVALID = "FINAL_OUTPUT_CONTRACT_INVALID"
    EVALUATION_PERSISTENCE_FAILED = "EVALUATION_PERSISTENCE_FAILED"


class RecordedRunEvaluationError(RuntimeError):
    def __init__(
        self,
        code: RecordedRunEvaluationErrorCode,
        message: str,
        *,
        detail_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail_type = detail_type


@dataclass(frozen=True)
class PreparedRecordedRunEvaluation:
    case: EvaluationCase
    envelope: dict[str, Any]
    outcome: "RecordedRunEvaluationOutcome"


@dataclass(frozen=True)
class RecordedRunEvaluationOutcome:
    evaluation: EvaluationResult
    artifact_id: str
    artifact_sha256: str
    duration_ms: int
    event_count: int
    model: str


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _single_event(events: list[Any], event_type: str) -> Any:
    matches = [event for event in events if event.event_type == event_type]
    if len(matches) != 1:
        raise RecordedRunEvaluationError(
            RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCOMPLETE,
            f"Recorded Run must contain exactly one {event_type} Event",
        )
    return matches[0]


def _safe_non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RecordedRunEvaluationError(
            RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCONSISTENT,
            f"Recorded Run contains invalid {field}",
        )
    return value


class RecordedRunEvaluationService:
    """Evaluate only product-owned, completed Run evidence.

    The service never invokes an Agent, model, MCP server, or SDK Runner. It reconstructs the
    evaluator input from the durable Product Run, canonical Events, and a verified final-output
    Artifact. SDK RunResult objects and raw prompts are intentionally outside this boundary.
    """

    def __init__(
        self,
        *,
        project_root: str | Path,
        product_store: ProductStore,
        evaluation_store: EvaluationStorePort,
        artifact_root: str | Path,
        runtime_bindings: RuntimeBindingResolver,
        evaluator: DeterministicEvaluator | None = None,
        artifact_service: ArtifactService,
    ) -> None:
        self._project_root = Path(project_root).expanduser().resolve()
        self._product_store = product_store
        self._evaluation_store = evaluation_store
        self._artifact_root = Path(artifact_root).expanduser().resolve()
        self._artifact_service = artifact_service
        self._definitions = AgentDefinitionCatalog(self._project_root)
        self._runtime_bindings = runtime_bindings
        self._cases = EvaluationCatalog(self._project_root)
        self._evaluator = evaluator or DeterministicEvaluator()

    def prepare(self, *, run_id: str, case_id: str) -> PreparedRecordedRunEvaluation:
        try:
            run = self._product_store.get_run(run_id)
        except RecordNotFoundError as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_NOT_FOUND,
                "Recorded Run was not found",
                detail_type=type(exc).__name__,
            ) from exc
        if run.status is not RunStatus.SUCCEEDED:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_NOT_SUCCEEDED,
                "Only a successfully completed Run can be evaluated",
            )
        try:
            task = self._product_store.get_task(run.task_id)
        except RecordNotFoundError as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCONSISTENT,
                "Recorded Run references a missing Task",
                detail_type=type(exc).__name__,
            ) from exc
        if task.status is not TaskStatus.SUCCEEDED:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.TASK_NOT_SUCCEEDED,
                "Only a Run whose Task succeeded can be evaluated",
            )
        if (
            task.agent_definition_id != run.agent_definition_id
            or task.agent_definition_version != run.agent_definition_version
        ):
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCONSISTENT,
                "Task and Run Agent definition identities do not match",
            )

        try:
            case = self._cases.resolve(case_id)
        except FileNotFoundError as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.EVALUATION_CASE_NOT_FOUND,
                "Evaluation Case was not found",
                detail_type=type(exc).__name__,
            ) from exc
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.EVALUATION_CASE_INVALID,
                "Evaluation Case is invalid",
                detail_type=type(exc).__name__,
            ) from exc

        events = self._product_store.list_events(run_id)
        definition_event = _single_event(events, "agent.definition.resolved")
        artifact_event = _single_event(events, "artifact.created")
        completed_event = _single_event(events, "run.completed")

        try:
            definition = self._definitions.resolve(run.agent_definition_id)
        except (
            AgentDefinitionNotFoundError,
            AgentDefinitionContractError,
            AgentDefinitionIntegrityError,
            OSError,
        ) as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.AGENT_DEFINITION_DRIFT,
                "Recorded Run Agent definition can no longer be verified",
                detail_type=type(exc).__name__,
            ) from exc
        definition_payload = definition_event.payload
        if (
            definition.version != run.agent_definition_version
            or definition_payload.get("agent_definition_id") != run.agent_definition_id
            or definition_payload.get("agent_definition_version") != run.agent_definition_version
            or definition_payload.get("agent_definition_sha256") != definition.definition_sha256
        ):
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.AGENT_DEFINITION_DRIFT,
                "Recorded Run Agent definition differs from the immutable definition catalog",
            )
        try:
            runtime_binding = self._runtime_bindings.resolve(definition)
        except Exception as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUNTIME_BINDING_DRIFT,
                "Recorded Run Runtime binding can no longer be verified",
                detail_type=type(exc).__name__,
            ) from exc
        recorded_runtime_binding_sha256 = definition_payload.get("runtime_binding_sha256")
        if (
            not isinstance(recorded_runtime_binding_sha256, str)
            or len(recorded_runtime_binding_sha256) != 64
            or recorded_runtime_binding_sha256 != runtime_binding.runtime_binding_sha256
            or definition_payload.get("output_contract") != definition.output_contract
            or definition_payload.get("mcp_server_ids") != list(definition.mcp_servers)
            or definition_payload.get("mcp_server_count") != len(definition.mcp_servers)
            or definition_payload.get("local_tool_count") != len(definition.tools)
            or definition_payload.get("handoff_count") != len(definition.handoffs)
            or definition_payload.get("session_mode") != definition.session_mode
        ):
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUNTIME_BINDING_DRIFT,
                "Recorded Run Runtime binding differs from the current executable Runtime catalog",
            )

        artifact_payload = artifact_event.payload
        artifact_id = artifact_payload.get("artifact_id")
        if (
            not isinstance(artifact_id, str)
            or not artifact_id
            or artifact_payload.get("artifact_type") != "agent.final-output"
            or completed_event.payload.get("artifact_id") != artifact_id
        ):
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCONSISTENT,
                "Recorded Run final-output Artifact identity is inconsistent",
            )
        try:
            artifact = self._product_store.get_artifact(artifact_id)
        except RecordNotFoundError as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.FINAL_OUTPUT_ARTIFACT_INVALID,
                "Recorded Run final-output Artifact metadata was not found",
                detail_type=type(exc).__name__,
            ) from exc
        if (
            artifact.run_id != run_id
            or artifact.artifact_type != "agent.final-output"
            or artifact.media_type != "application/json"
            or artifact.sha256 != artifact_payload.get("sha256")
            or artifact.byte_length != artifact_payload.get("byte_length")
            or artifact.byte_length > _MAX_FINAL_OUTPUT_BYTES
        ):
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.FINAL_OUTPUT_ARTIFACT_INVALID,
                "Recorded Run final-output Artifact metadata is invalid",
            )

        try:
            artifact, raw_output = self._artifact_service.read_bytes(artifact_id)
        except (
            ValueError,
            ArtifactIntegrityError,
            RecordNotFoundError,
            OSError,
        ) as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.FINAL_OUTPUT_ARTIFACT_INVALID,
                "Recorded Run final-output Artifact failed integrity verification",
                detail_type=type(exc).__name__,
            ) from exc
        try:
            parsed_output = json.loads(raw_output.decode("utf-8"))
            if not isinstance(parsed_output, dict):
                raise ValueError("final-output Artifact must contain a JSON object")
            output_type = validate_output_schema(
                definition.output_contract, definition.output_schema
            )
            validated_output = output_type.model_validate(parsed_output).model_dump(mode="json")
        except (
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
            GenericExecutionFailure,
        ) as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.FINAL_OUTPUT_CONTRACT_INVALID,
                "Recorded Run final-output Artifact does not satisfy its output contract",
                detail_type=type(exc).__name__,
            ) from exc

        if run.started_at is None or run.completed_at is None:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCOMPLETE,
                "Recorded Run is missing execution timestamps",
            )
        try:
            duration_ms = int(
                (_parse_timestamp(run.completed_at) - _parse_timestamp(run.started_at)).total_seconds()
                * 1000
            )
        except (TypeError, ValueError) as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCONSISTENT,
                "Recorded Run contains invalid execution timestamps",
                detail_type=type(exc).__name__,
            ) from exc
        if duration_ms < 0:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCONSISTENT,
                "Recorded Run completion time precedes its start time",
            )

        model_values = {
            event.payload.get("model")
            for event in events
            if event.event_type == "model.started"
            and isinstance(event.payload.get("model"), str)
            and event.payload.get("model")
        }
        if len(model_values) != 1:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCONSISTENT,
                "Recorded Run must identify exactly one model",
            )
        model = next(iter(model_values))

        completed_usage = completed_event.payload.get("usage")
        if not isinstance(completed_usage, dict):
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCOMPLETE,
                "Recorded Run completion Event is missing Usage evidence",
            )
        for field, stored in (
            ("input_tokens", run.input_tokens),
            ("output_tokens", run.output_tokens),
            ("total_tokens", run.total_tokens),
        ):
            event_value = _safe_non_negative_int(completed_usage.get(field), field=field)
            if event_value != stored:
                raise RecordedRunEvaluationError(
                    RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCONSISTENT,
                    f"Recorded Run {field} does not match its completion Event",
                )
        usage = {
            "requests": _safe_non_negative_int(completed_usage.get("requests", 0), field="requests"),
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "total_tokens": run.total_tokens,
            "cached_input_tokens": _safe_non_negative_int(
                completed_usage.get("cached_input_tokens", 0), field="cached_input_tokens"
            ),
            "reasoning_tokens": _safe_non_negative_int(
                completed_usage.get("reasoning_tokens", 0), field="reasoning_tokens"
            ),
        }
        envelope: dict[str, Any] = {
            "schema_version": "okcanvas-generic-agent-execution-v1",
            "state": "SUCCEEDED",
            "task_id": task.task_id,
            "run_id": run.run_id,
            "agent_definition_id": run.agent_definition_id,
            "agent_definition_version": run.agent_definition_version,
            "agent_definition_sha256": definition.definition_sha256,
            "runtime_binding_sha256": runtime_binding.runtime_binding_sha256,
            "model": model,
            "live_call": True,
            "trace_id": run.trace_id,
            "artifact_id": artifact.artifact_id,
            "artifact_sha256": artifact.sha256,
            "usage": usage,
            "result": validated_output,
        }
        evaluator_events = [
            {
                "sequence": event.sequence,
                "event_type": event.event_type,
                "source": event.source.value,
                "payload": event.payload,
            }
            for event in events
        ]
        result = self._evaluator.evaluate(
            case=case,
            envelope=envelope,
            events=evaluator_events,
            duration_ms=duration_ms,
        )
        outcome = RecordedRunEvaluationOutcome(
            evaluation=result,
            artifact_id=artifact.artifact_id,
            artifact_sha256=artifact.sha256,
            duration_ms=duration_ms,
            event_count=len(events),
            model=model,
        )
        return PreparedRecordedRunEvaluation(case=case, envelope=envelope, outcome=outcome)

    def persist(self, prepared: PreparedRecordedRunEvaluation) -> RecordedRunEvaluationOutcome:
        try:
            self._evaluation_store.save(
                case=prepared.case,
                envelope=prepared.envelope,
                result=prepared.outcome.evaluation,
            )
        except Exception as exc:
            raise RecordedRunEvaluationError(
                RecordedRunEvaluationErrorCode.EVALUATION_PERSISTENCE_FAILED,
                "Recorded Run evaluation result could not be persisted",
                detail_type=type(exc).__name__,
            ) from exc
        return prepared.outcome

    def evaluate(self, *, run_id: str, case_id: str) -> RecordedRunEvaluationOutcome:
        return self.persist(self.prepare(run_id=run_id, case_id=case_id))
