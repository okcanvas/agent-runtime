from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from okcanvas_agent_runtime.application.admin.use_cases import AdminUseCases
from okcanvas_agent_runtime.application.approvals import ToolApprovalState
from okcanvas_agent_runtime.application.errors import ControlAPIError
from okcanvas_agent_runtime.transport.admin.sse.native import native_sdk_event_stream
from okcanvas_agent_runtime.transport.admin.sse.stream import persisted_event_stream
from okcanvas_agent_protocols.rest.admin import (
    AgentDefinitionDetailResponse,
    AgentDefinitionListResponse,
    AgentInvocationListResponse,
    AssistantRouteRequest,
    AssistantRouteResponse,
    AssistantRunPreflightRequest,
    AssistantRunPreflightResponse,
    CancelRunResponse,
    CreateEvaluationBaselineRequest,
    CreateEvaluationSuiteRunRequest,
    CreateRunRequest,
    CreateRunResponse,
    CreateSessionRequest,
    EvaluationBaselineResponse,
    EvaluationCaseDetailResponse,
    EvaluationCaseListResponse,
    EvaluationComparisonResponse,
    EvaluationResultListResponse,
    EvaluationResultResponse,
    EvaluationSuiteListResponse,
    EvaluationSuiteRunResponse,
    EvaluationSuiteSummaryResponse,
    EvaluateRecordedRunRequest,
    EventListResponse,
    GovernedCommerceSnapshotPreflightRequest,
    GovernedRecoveryResponse,
    GovernedRunConfirmRequest,
    GovernedRunPreflightRequest,
    GovernedRunSubmissionResponse,
    LocalAttachmentUploadResponse,
    OrganizationContextQueryRequest,
    OrganizationContextQueryResponse,
    OperationsSummaryResponse,
    OrphanedRunReconciliationRequest,
    OrphanedRunReconciliationResponse,
    ProductSessionListResponse,
    ProductSessionResponse,
    ProtectedPayloadRetentionResponse,
    RunArtifactResponse,
    RunListResponse,
    RunResponse,
    RunSubmissionPolicyResponse,
    RunSubmissionResponse,
    SessionKeyRotationResponse,
    TaskListResponse,
    TaskResponse,
    TerminalOutcomeReconciliationRequest,
    TerminalOutcomeReconciliationResponse,
    ToolApprovalDecisionRequest,
    ToolApprovalInboxItemResponse,
    ToolApprovalListResponse,
    ToolApprovalResponse,
    ToolApprovalResumeResponse,
    WalkingSkeletonScenarioListResponse,
)


@dataclass(frozen=True)
class AdminRouteContext:
    auth: Any
    submitter_auth: Any
    use_cases: AdminUseCases



def build_admin_router(*, context: AdminRouteContext) -> APIRouter:
    router = APIRouter()
    auth = context.auth
    submitter_auth = context.submitter_auth
    use_cases = context.use_cases


    @router.get('/v1/operations/summary', response_model=OperationsSummaryResponse, dependencies=[Depends(auth.require)])
    async def operations_summary(refresh_references: bool=Query(default=False)) -> OperationsSummaryResponse:
        return await use_cases.operations_summary(refresh_references=refresh_references)

    @router.get('/v1/tasks', response_model=TaskListResponse, dependencies=[Depends(auth.require)])
    async def list_tasks(status_filter: str | None=Query(default=None, alias='status', pattern='^(READY|RUNNING|WAITING_APPROVAL|SUCCEEDED|FAILED|CANCELLED)$'), limit: int=Query(default=50, ge=1, le=200), offset: int=Query(default=0, ge=0)) -> TaskListResponse:
        return await use_cases.list_tasks(status_filter=status_filter, limit=limit, offset=offset)

    @router.get('/v1/runs', response_model=RunListResponse, dependencies=[Depends(auth.require)])
    async def list_runs(status_filter: str | None=Query(default=None, alias='status', pattern='^(CREATED|RUNNING|INTERRUPTED|SUCCEEDED|FAILED|CANCELLED)$'), agent_definition_id: str | None=Query(default=None, min_length=1, max_length=128), limit: int=Query(default=50, ge=1, le=200), offset: int=Query(default=0, ge=0)) -> RunListResponse:
        return await use_cases.list_runs(status_filter=status_filter, agent_definition_id=agent_definition_id, limit=limit, offset=offset)

    @router.get('/v1/runtime-scenarios', response_model=WalkingSkeletonScenarioListResponse, dependencies=[Depends(auth.require)])
    async def list_runtime_scenarios() -> WalkingSkeletonScenarioListResponse:
        return await use_cases.list_runtime_scenarios()

    @router.get('/v1/agent-definitions', response_model=AgentDefinitionListResponse, dependencies=[Depends(auth.require)])
    async def list_agent_definitions() -> AgentDefinitionListResponse:
        return await use_cases.list_agent_definitions()

    @router.get('/v1/agent-definitions/{agent_id}', response_model=AgentDefinitionDetailResponse, dependencies=[Depends(auth.require)])
    async def get_agent_definition(agent_id: str) -> AgentDefinitionDetailResponse:
        return await use_cases.get_agent_definition(agent_id=agent_id)

    @router.get('/v1/evaluation-cases', response_model=EvaluationCaseListResponse, dependencies=[Depends(auth.require)])
    async def list_evaluation_cases() -> EvaluationCaseListResponse:
        return await use_cases.list_evaluation_cases()

    @router.get('/v1/evaluation-cases/{case_id}', response_model=EvaluationCaseDetailResponse, dependencies=[Depends(auth.require)])
    async def get_evaluation_case(case_id: str) -> EvaluationCaseDetailResponse:
        return await use_cases.get_evaluation_case(case_id=case_id)

    @router.get('/v1/evaluations', response_model=EvaluationResultListResponse, dependencies=[Depends(auth.require)])
    async def list_evaluations(case_id: str | None=Query(default=None, min_length=1, max_length=128), subject_run_id: str | None=Query(default=None, min_length=1, max_length=128), state: str | None=Query(default=None, pattern='^(PASSED|FAILED)$'), limit: int=Query(default=100, ge=1, le=200), offset: int=Query(default=0, ge=0)) -> EvaluationResultListResponse:
        return await use_cases.list_evaluations(case_id=case_id, subject_run_id=subject_run_id, state=state, limit=limit, offset=offset)

    @router.get('/v1/evaluations/{evaluation_id}', response_model=EvaluationResultResponse, dependencies=[Depends(auth.require)])
    async def get_evaluation(evaluation_id: str) -> EvaluationResultResponse:
        return await use_cases.get_evaluation(evaluation_id=evaluation_id)

    @router.get('/v1/evaluation-comparisons', response_model=EvaluationComparisonResponse, dependencies=[Depends(auth.require)])
    async def compare_evaluations(left_evaluation_id: str=Query(min_length=1, max_length=128), right_evaluation_id: str=Query(min_length=1, max_length=128)) -> EvaluationComparisonResponse:
        return await use_cases.compare_evaluations(left_evaluation_id=left_evaluation_id, right_evaluation_id=right_evaluation_id)

    @router.post('/v1/runs/{run_id}/evaluations', response_model=EvaluationResultResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth.require)])
    async def evaluate_recorded_run(run_id: str, request: EvaluateRecordedRunRequest) -> EvaluationResultResponse:
        return await use_cases.evaluate_recorded_run(run_id=run_id, request=request)

    @router.get('/v1/evaluation-suites', response_model=EvaluationSuiteListResponse, dependencies=[Depends(auth.require)])
    async def list_evaluation_suites() -> EvaluationSuiteListResponse:
        return await use_cases.list_evaluation_suites()

    @router.get('/v1/evaluation-suites/{suite_id}', response_model=EvaluationSuiteSummaryResponse, dependencies=[Depends(auth.require)])
    async def get_evaluation_suite(suite_id: str) -> EvaluationSuiteSummaryResponse:
        return await use_cases.get_evaluation_suite(suite_id=suite_id)

    @router.post('/v1/evaluation-suite-runs', response_model=EvaluationSuiteRunResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth.require)])
    async def create_evaluation_suite_run(request: CreateEvaluationSuiteRunRequest) -> EvaluationSuiteRunResponse:
        return await use_cases.create_evaluation_suite_run(request=request)

    @router.get('/v1/evaluation-suite-runs/{suite_run_id}', response_model=EvaluationSuiteRunResponse, dependencies=[Depends(auth.require)])
    async def get_evaluation_suite_run(suite_run_id: str) -> EvaluationSuiteRunResponse:
        return await use_cases.get_evaluation_suite_run(suite_run_id=suite_run_id)

    @router.post('/v1/evaluation-baselines', response_model=EvaluationBaselineResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth.require)])
    async def create_evaluation_baseline(request: CreateEvaluationBaselineRequest) -> EvaluationBaselineResponse:
        return await use_cases.create_evaluation_baseline(request=request)

    @router.get('/v1/evaluation-baselines/{baseline_id}', response_model=EvaluationBaselineResponse, dependencies=[Depends(auth.require)])
    async def get_evaluation_baseline(baseline_id: str) -> EvaluationBaselineResponse:
        return await use_cases.get_evaluation_baseline(baseline_id=baseline_id)

    @router.post('/v1/sessions', response_model=ProductSessionResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def create_product_session(request: CreateSessionRequest) -> ProductSessionResponse:
        return await use_cases.create_product_session(request=request)

    @router.get('/v1/sessions', response_model=ProductSessionListResponse, dependencies=[Depends(auth.require)])
    async def list_product_sessions(limit: int=Query(default=100, ge=1, le=200)) -> ProductSessionListResponse:
        return await use_cases.list_product_sessions(limit=limit)

    @router.get('/v1/sessions/{session_id}', response_model=ProductSessionResponse, dependencies=[Depends(auth.require)])
    async def get_product_session(session_id: str) -> ProductSessionResponse:
        return await use_cases.get_product_session(session_id=session_id)

    @router.post('/v1/sessions/{session_id}/clear', response_model=ProductSessionResponse, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def clear_product_session(session_id: str) -> ProductSessionResponse:
        return await use_cases.clear_product_session(session_id=session_id)

    @router.post('/v1/sessions/{session_id}/rotate-history-key', response_model=SessionKeyRotationResponse, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def rotate_product_session_history_key(session_id: str) -> SessionKeyRotationResponse:
        return await use_cases.rotate_product_session_history_key(session_id=session_id)

    @router.post(
        '/v1/assistant/sessions',
        response_model=ProductSessionResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(auth.require), Depends(submitter_auth.require)],
    )
    async def create_assistant_session() -> ProductSessionResponse:
        return await use_cases.create_assistant_session()

    @router.post(
        '/v1/assistant/routes',
        response_model=AssistantRouteResponse,
        dependencies=[Depends(auth.require)],
    )
    async def assistant_route(request: AssistantRouteRequest) -> AssistantRouteResponse:
        return await use_cases.assistant_route(request=request)

    @router.post(
        '/v1/assistant/run-submissions/preflight',
        response_model=AssistantRunPreflightResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(auth.require), Depends(submitter_auth.require)],
    )
    async def assistant_preflight(
        request: AssistantRunPreflightRequest,
    ) -> AssistantRunPreflightResponse:
        return await use_cases.assistant_preflight(request=request)

    @router.post('/v1/organization/glossary/resolve', response_model=OrganizationContextQueryResponse, dependencies=[Depends(auth.require)])
    async def resolve_organization_glossary(request: OrganizationContextQueryRequest) -> OrganizationContextQueryResponse:
        return await use_cases.resolve_organization_glossary(request=request)

    @router.post('/v1/organization/knowledge/search', response_model=OrganizationContextQueryResponse, dependencies=[Depends(auth.require)])
    async def search_organization_knowledge(request: OrganizationContextQueryRequest) -> OrganizationContextQueryResponse:
        return await use_cases.search_organization_knowledge(request=request)

    @router.post('/v1/organization/directory/search', response_model=OrganizationContextQueryResponse, dependencies=[Depends(auth.require)])
    async def search_organization_directory(request: OrganizationContextQueryRequest) -> OrganizationContextQueryResponse:
        return await use_cases.search_organization_directory(request=request)

    @router.get('/v1/run-submission-policy', response_model=RunSubmissionPolicyResponse, dependencies=[Depends(auth.require)])
    async def get_run_submission_policy() -> RunSubmissionPolicyResponse:
        return await use_cases.get_run_submission_policy()

    @router.post('/v1/local-attachments', response_model=LocalAttachmentUploadResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def upload_local_attachment(request: Request, x_okcanvas_attachment_filename: str=Header(alias='X-OKCanvas-Attachment-Filename', min_length=1, max_length=255)) -> LocalAttachmentUploadResponse:
        maximum = use_cases.local_attachment_maximum()
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > maximum:
                    raise ControlAPIError(413, "LOCAL_ATTACHMENT_TOO_LARGE", f"Local attachment exceeds the {maximum}-byte limit")
            except ValueError as exc:
                raise ControlAPIError(400, "INVALID_CONTENT_LENGTH", "Content-Length is invalid") from exc
        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > maximum:
                raise ControlAPIError(413, "LOCAL_ATTACHMENT_TOO_LARGE", f"Local attachment exceeds the {maximum}-byte limit")
            chunks.append(chunk)
        return await use_cases.upload_local_attachment(filename=x_okcanvas_attachment_filename, payload=b"".join(chunks))

    @router.post('/v1/run-submissions/preflight', response_model=RunSubmissionResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def preflight_governed_run(request: GovernedRunPreflightRequest) -> RunSubmissionResponse:
        return await use_cases.preflight_governed_run(request=request)

    @router.post('/v1/commerce-snapshot-ingress/preflight', response_model=RunSubmissionResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def preflight_commerce_snapshot(request: GovernedCommerceSnapshotPreflightRequest) -> RunSubmissionResponse:
        return await use_cases.preflight_commerce_snapshot(request=request)

    @router.get('/v1/run-submissions/{submission_id}', response_model=RunSubmissionResponse, dependencies=[Depends(auth.require)])
    async def get_governed_run_submission(submission_id: str) -> RunSubmissionResponse:
        return await use_cases.get_governed_run_submission(submission_id=submission_id)

    @router.post('/v1/run-submissions/{submission_id}/confirm', response_model=GovernedRunSubmissionResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def confirm_governed_run_submission(submission_id: str, request: GovernedRunConfirmRequest) -> GovernedRunSubmissionResponse:
        return await use_cases.confirm_governed_run_submission(submission_id=submission_id, request=request)

    @router.post('/v1/run-submissions/{submission_id}/prepare-approval', response_model=ToolApprovalResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def prepare_local_tool_approval(submission_id: str) -> ToolApprovalResponse:
        return await use_cases.prepare_local_tool_approval(submission_id=submission_id)

    @router.get('/v1/tool-approvals', response_model=ToolApprovalListResponse, dependencies=[Depends(auth.require)])
    async def list_tool_approvals(state: ToolApprovalState | None=Query(default=None), limit: int=Query(default=100, ge=1, le=200), offset: int=Query(default=0, ge=0)) -> ToolApprovalListResponse:
        return await use_cases.list_tool_approvals(state=state, limit=limit, offset=offset)

    @router.get('/v1/tool-approvals/{approval_id}/inbox', response_model=ToolApprovalInboxItemResponse, dependencies=[Depends(auth.require)])
    async def get_tool_approval_inbox_item(approval_id: str) -> ToolApprovalInboxItemResponse:
        return await use_cases.get_tool_approval_inbox_item(approval_id=approval_id)

    @router.get('/v1/tool-approvals/{approval_id}', response_model=ToolApprovalResponse, dependencies=[Depends(auth.require)])
    async def get_tool_approval(approval_id: str) -> ToolApprovalResponse:
        return await use_cases.get_tool_approval(approval_id=approval_id)

    @router.post('/v1/tool-approvals/{approval_id}/decision', response_model=ToolApprovalResumeResponse, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def decide_tool_approval(approval_id: str, request: ToolApprovalDecisionRequest) -> ToolApprovalResumeResponse:
        return await use_cases.decide_tool_approval(approval_id=approval_id, request=request)

    @router.post('/v1/run-submissions/recover-stale', response_model=GovernedRecoveryResponse, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def recover_stale_governed_submissions() -> GovernedRecoveryResponse:
        return await use_cases.recover_stale_governed_submissions()

    @router.post('/v1/run-submissions/reconcile-orphaned-running', response_model=OrphanedRunReconciliationResponse, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def reconcile_orphaned_running(_request: OrphanedRunReconciliationRequest) -> OrphanedRunReconciliationResponse:
        return await use_cases.reconcile_orphaned_running(_request=_request)

    @router.post('/v1/run-submissions/reconcile-terminal-outcomes', response_model=TerminalOutcomeReconciliationResponse, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def reconcile_terminal_outcomes(_request: TerminalOutcomeReconciliationRequest) -> TerminalOutcomeReconciliationResponse:
        return await use_cases.reconcile_terminal_outcomes(_request=_request)

    @router.post('/v1/protected-payloads/cleanup-expired', response_model=ProtectedPayloadRetentionResponse, dependencies=[Depends(auth.require), Depends(submitter_auth.require)])
    async def cleanup_expired_protected_payloads() -> ProtectedPayloadRetentionResponse:
        return await use_cases.cleanup_expired_protected_payloads()

    @router.post('/v1/runs', response_model=CreateRunResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(auth.require)])
    async def create_run(request: CreateRunRequest) -> CreateRunResponse:
        return await use_cases.create_run(request=request)

    @router.get('/v1/tasks/{task_id}', response_model=TaskResponse, dependencies=[Depends(auth.require)])
    async def get_task(task_id: str) -> TaskResponse:
        return await use_cases.get_task(task_id=task_id)

    @router.get('/v1/runs/{run_id}', response_model=RunResponse, dependencies=[Depends(auth.require)])
    async def get_run(run_id: str) -> RunResponse:
        return await use_cases.get_run(run_id=run_id)

    @router.get('/v1/runs/{run_id}/invocations', response_model=AgentInvocationListResponse, dependencies=[Depends(auth.require)])
    async def list_run_invocations(run_id: str) -> AgentInvocationListResponse:
        return await use_cases.list_run_invocations(run_id=run_id)

    @router.get('/v1/runs/{run_id}/artifact', response_model=RunArtifactResponse, dependencies=[Depends(auth.require)])
    async def get_run_artifact(run_id: str) -> RunArtifactResponse:
        return await use_cases.get_run_artifact(run_id=run_id)

    @router.get('/v1/runs/{run_id}/outcome', response_model=RunResponse, dependencies=[Depends(auth.require)])
    async def get_run_outcome(run_id: str) -> RunResponse:
        return await use_cases.get_run_outcome(run_id=run_id)

    @router.get('/v1/runs/{run_id}/events', response_model=EventListResponse, dependencies=[Depends(auth.require)])
    async def list_events(run_id: str, after: int=Query(default=0, ge=0)) -> EventListResponse:
        return await use_cases.list_events(run_id=run_id, after=after)

    @router.get('/v1/runs/{run_id}/events/stream', dependencies=[Depends(auth.require)])
    async def stream_events(run_id: str, cursor: int=Query(default=0, ge=0), last_event_id: str | None=Header(default=None, alias='Last-Event-ID')) -> StreamingResponse:
        if last_event_id is not None:
            try:
                cursor = max(cursor, int(last_event_id))
            except ValueError as exc:
                raise ControlAPIError(400, "INVALID_LAST_EVENT_ID", "Last-Event-ID must be an integer") from exc
        subscription = use_cases.persisted_event_subscription(run_id=run_id)
        return StreamingResponse(
            persisted_event_stream(subscription=subscription, run_id=run_id, after_sequence=cursor),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    @router.get('/v1/runs/{run_id}/sdk-stream', dependencies=[Depends(auth.require)])
    async def stream_native_sdk_events(run_id: str, cursor: int=Query(default=0, ge=0), last_event_id: str | None=Header(default=None, alias='Last-Event-ID')) -> StreamingResponse:
        if last_event_id is not None:
            try:
                cursor = max(cursor, int(last_event_id))
            except ValueError as exc:
                raise ControlAPIError(400, "INVALID_LAST_EVENT_ID", "Last-Event-ID must be an integer") from exc
        broker = await use_cases.native_stream_broker(run_id=run_id)
        return StreamingResponse(
            native_sdk_event_stream(broker=broker, run_id=run_id, after_sequence=cursor),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-store, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive", "X-OKCanvas-Stream-Durability": "ephemeral"},
        )

    @router.post('/v1/runs/{run_id}/cancel', response_model=CancelRunResponse, dependencies=[Depends(auth.require)])
    async def cancel_run(run_id: str) -> CancelRunResponse:
        return await use_cases.cancel_run(run_id=run_id)

    return router
