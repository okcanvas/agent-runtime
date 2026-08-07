from __future__ import annotations

from okcanvas_agent_runtime.domain.runs.models import RunEventRecord, RunRecord, TaskRecord
from okcanvas_agent_runtime.agent.definitions.models import AgentDefinition
from okcanvas_agent_runtime.application.evaluation.models import EvaluationCase
from okcanvas_agent_runtime.agent.skills import resolve_effective_instructions
from okcanvas_agent_runtime.application.evaluation.suite import EvaluationSuite

from okcanvas_agent_protocols.rest.admin import AgentDefinitionDetailResponse, AgentDefinitionSummaryResponse, EvaluationCaseDetailResponse, EvaluationCaseSummaryResponse, EvaluationResultResponse, EvaluationSuiteSummaryResponse, EventResponse, RunResponse, TaskResponse


def task_response(record: TaskRecord) -> TaskResponse:
    return TaskResponse(
        task_id=record.task_id,
        task_type=record.task_type,
        status=record.status.value,
        input_sha256=record.input_sha256,
        agent_definition_id=record.agent_definition_id,
        agent_definition_version=record.agent_definition_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
    )


def run_response(record: RunRecord) -> RunResponse:
    return RunResponse(
        run_id=record.run_id,
        task_id=record.task_id,
        attempt=record.attempt,
        status=record.status.value,
        agent_definition_id=record.agent_definition_id,
        agent_definition_version=record.agent_definition_version,
        trace_id=record.trace_id,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        total_tokens=record.total_tokens,
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
    )


def event_response(record: RunEventRecord) -> EventResponse:
    return EventResponse(
        run_id=record.run_id,
        sequence=record.sequence,
        event_type=record.event_type,
        source=record.source.value,
        occurred_at=record.occurred_at,
        payload_schema_version=record.payload_schema_version,
        payload_sha256=record.payload_sha256,
        payload=record.payload,
    )


def agent_definition_summary(definition: AgentDefinition) -> AgentDefinitionSummaryResponse:
    payload = definition.to_public_dict()
    payload.pop("schema_version", None)
    return AgentDefinitionSummaryResponse(**payload)


def agent_definition_detail(definition: AgentDefinition) -> AgentDefinitionDetailResponse:
    import hashlib

    payload = definition.to_public_dict()
    payload.pop("schema_version", None)
    effective_instructions = resolve_effective_instructions(definition)
    return AgentDefinitionDetailResponse(
        **payload,
        instructions_sha256=hashlib.sha256(definition.instructions.encode("utf-8")).hexdigest(),
        instructions_byte_length=len(definition.instructions.encode("utf-8")),
        effective_instructions_sha256=hashlib.sha256(effective_instructions.encode("utf-8")).hexdigest(),
        effective_instructions_byte_length=len(effective_instructions.encode("utf-8")),
        output_schema=definition.output_schema,
    )


def evaluation_case_summary(case: EvaluationCase) -> EvaluationCaseSummaryResponse:
    return EvaluationCaseSummaryResponse(
        case_id=case.case_id,
        version=case.version,
        agent_definition_id=case.agent_definition_id,
        required_tools=list(case.required_tools),
        forbidden_tools=list(case.forbidden_tools),
        max_total_tokens=case.max_total_tokens,
        max_duration_ms=case.max_duration_ms,
        manifest_sha256=case.manifest_sha256,
    )


def evaluation_case_detail(case: EvaluationCase) -> EvaluationCaseDetailResponse:
    summary = evaluation_case_summary(case).model_dump()
    summary.pop("schema_version", None)
    return EvaluationCaseDetailResponse(
        **summary,
        required_result=case.required_result,
        forbidden_result=case.forbidden_result,
    )


def evaluation_result_response(row: dict[str, object]) -> EvaluationResultResponse:
    return EvaluationResultResponse(**row)


def evaluation_suite_summary(suite: EvaluationSuite) -> EvaluationSuiteSummaryResponse:
    return EvaluationSuiteSummaryResponse(
        suite_id=suite.suite_id,
        version=suite.version,
        max_subjects=suite.max_subjects,
        slots=[
            {"slot_id": slot.slot_id, "case_id": slot.case_id, "required": slot.required}
            for slot in suite.slots
        ],
        baseline_comparison={
            "max_passed_to_failed": suite.comparison.max_passed_to_failed,
            "max_total_tokens_increase_percent": suite.comparison.max_total_tokens_increase_percent,
            "max_duration_increase_percent": suite.comparison.max_duration_increase_percent,
            "max_tool_call_increase": suite.comparison.max_tool_call_increase,
        },
        manifest_sha256=suite.manifest_sha256,
    )
