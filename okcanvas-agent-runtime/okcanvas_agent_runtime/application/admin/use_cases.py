from __future__ import annotations

import hmac
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.definitions.errors import (
    AgentDefinitionContractError,
    AgentDefinitionIntegrityError,
    AgentDefinitionNotFoundError,
)
from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.organization_context import OrganizationAccessContext
from okcanvas_agent_runtime.application.admin.projections import (
    agent_definition_detail,
    agent_definition_summary,
    evaluation_case_detail,
    evaluation_case_summary,
    evaluation_result_response,
    evaluation_suite_summary,
    event_response,
    run_response,
    task_response,
)
from okcanvas_agent_runtime.application.approvals import (
    ToolApprovalConfirmationError,
    ToolApprovalDecision,
    ToolApprovalError,
    ToolApprovalIntegrityError,
    ToolApprovalNotFound,
    ToolApprovalState,
    ToolApprovalStateError,
    decision_confirmation_challenge,
)
from okcanvas_agent_runtime.application.errors import ControlAPIError
from okcanvas_agent_runtime.application.artifacts import ArtifactService
from okcanvas_agent_runtime.application.events import PollingRunEventSubscription, RunEventSubscription
from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionEnvelope
from okcanvas_agent_runtime.application.execution.coordinator import ScheduledExecution
from okcanvas_agent_runtime.application.submissions import (
    RunSubmissionAuthorityError,
    RunSubmissionConfirmationError,
    RunSubmissionError,
    RunSubmissionIdempotencyConflict,
    RunSubmissionIntegrityError,
    RunSubmissionNotFound,
    RunSubmissionStateError,
    RunSubmissionValidationError,
)
from okcanvas_agent_runtime.application.submissions.protected_payload_errors import ProtectedPayloadError
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.domain.attachments import AttachmentError
from okcanvas_agent_runtime.domain.runs.errors import ArtifactIntegrityError, RecordNotFoundError
from okcanvas_agent_runtime.domain.runs.models import RunStatus, TaskStatus
from okcanvas_agent_runtime.domain.sessions import (
    SessionBusyError,
    SessionConfigurationError,
    SessionIntegrityError,
    SessionNotFound,
    SessionRuntimeError,
    SessionStateError,
)
from okcanvas_agent_runtime.application.evaluation import (
    EvaluationSuiteError,
    EvaluationSuiteErrorCode,
    EvaluationSuiteSubject,
    RecordedRunEvaluationError,
    RecordedRunEvaluationErrorCode,
    compare_results,
)
from okcanvas_agent_runtime.application.scenarios import WalkingSkeletonCatalogError
from okcanvas_agent_protocols.rest.admin import (
    AgentDefinitionDetailResponse,
    AgentDefinitionListResponse,
    AgentInvocationListResponse,
    AssistantRouteRequest,
    AssistantRouteResponse,
    AssistantRunPreflightRequest,
    AssistantRunPreflightResponse,
    AgentInvocationResponse,
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
    WalkingSkeletonScenarioResponse,
)


def _error_status(envelope: GenericExecutionEnvelope) -> int:
    if envelope.error is None:
        return 500
    code = envelope.error.code.value
    if code in {"INVALID_REQUEST"}:
        return 422
    if code in {"LIVE_OPT_IN_REQUIRED", "SESSION_BUSY"}:
        return 409
    if code in {
        "AGENT_DEFINITION_INVALID", "AGENT_POLICY_DENIED", "MODEL_NOT_CONFIGURED",
        "API_KEY_MISSING", "SDK_NOT_INSTALLED", "SDK_VERSION_MISMATCH",
    }:
        return 503
    return 500


def _raise_envelope(envelope: GenericExecutionEnvelope) -> None:
    assert envelope.error is not None
    raise ControlAPIError(
        status_code=_error_status(envelope),
        code=envelope.error.code.value,
        message=envelope.error.message,
        retryable=envelope.error.retryable,
        details={"detail_type": envelope.error.detail_type} if envelope.error.detail_type else {},
    )


def _submission_response(decision) -> RunSubmissionResponse:
    return RunSubmissionResponse(**decision.to_public_dict())


def _raise_commerce_snapshot_error(exc: Exception) -> None:
    error_name = type(exc).__name__
    code = str(getattr(exc, "code", "COMMERCE_SNAPSHOT_INGRESS_FAILED"))
    if error_name == "CommerceSnapshotRequestError":
        raise ControlAPIError(422, code, str(exc)) from exc
    if error_name == "CommerceSnapshotConfigurationError":
        raise ControlAPIError(503, code, str(exc)) from exc
    if error_name == "CommerceSnapshotUnavailableError":
        raise ControlAPIError(503, code, str(exc), retryable=True) from exc
    if error_name == "CommerceSnapshotReplayIntegrityError":
        raise ControlAPIError(409, code, str(exc)) from exc
    if error_name in {"CommerceSnapshotValidationError", "CommerceSnapshotDefinitionError"}:
        raise ControlAPIError(502, code, str(exc)) from exc
    if error_name.endswith("CommerceSnapshotIngressError") or hasattr(exc, "retryable"):
        raise ControlAPIError(502, code, str(exc), retryable=bool(getattr(exc, "retryable", False))) from exc
    _raise_submission_error(exc)


def _raise_submission_error(exc: Exception) -> None:
    if isinstance(exc, RunSubmissionNotFound):
        raise ControlAPIError(404, exc.code, "Run submission was not found") from exc
    if isinstance(exc, RunSubmissionAuthorityError):
        raise ControlAPIError(403, exc.code, "Run submission authority is required") from exc
    if isinstance(exc, RunSubmissionValidationError):
        raise ControlAPIError(422, exc.code, str(exc)) from exc
    if isinstance(exc, RunSubmissionIdempotencyConflict):
        raise ControlAPIError(409, exc.code, str(exc)) from exc
    if isinstance(exc, RunSubmissionConfirmationError):
        raise ControlAPIError(409, exc.code, str(exc)) from exc
    if isinstance(exc, (RunSubmissionStateError, RunSubmissionIntegrityError)):
        raise ControlAPIError(409, exc.code, str(exc)) from exc
    if isinstance(exc, ProtectedPayloadError):
        raise ControlAPIError(409, exc.code, "Protected payload validation failed") from exc
    if isinstance(exc, RunSubmissionError):
        raise ControlAPIError(500, exc.code, "Governed Run submission failed") from exc
    raise exc


def _raise_suite_error(exc: EvaluationSuiteError) -> None:
    statuses = {
        EvaluationSuiteErrorCode.SUITE_NOT_FOUND: 404,
        EvaluationSuiteErrorCode.BASELINE_NOT_FOUND: 404,
        EvaluationSuiteErrorCode.BASELINE_SOURCE_NOT_FOUND: 404,
        EvaluationSuiteErrorCode.SUBJECTS_INVALID: 422,
        EvaluationSuiteErrorCode.BATCH_LIMIT_EXCEEDED: 422,
        EvaluationSuiteErrorCode.RECORDED_RUN_INVALID: 409,
        EvaluationSuiteErrorCode.BASELINE_INCOMPATIBLE: 409,
        EvaluationSuiteErrorCode.BASELINE_SOURCE_NOT_PASSED: 409,
        EvaluationSuiteErrorCode.SUITE_INVALID: 500,
        EvaluationSuiteErrorCode.PERSISTENCE_FAILED: 500,
    }
    raise ControlAPIError(
        statuses[exc.code],
        exc.code.value,
        exc.message,
        details={"detail_type": exc.detail_type} if exc.detail_type else {},
    ) from exc


def _raise_session_error(exc: Exception) -> None:
    if isinstance(exc, SessionNotFound):
        raise ControlAPIError(404, exc.code, str(exc)) from exc
    if isinstance(exc, SessionBusyError):
        raise ControlAPIError(409, exc.code, str(exc), retryable=True) from exc
    if isinstance(exc, (SessionStateError, SessionIntegrityError)):
        raise ControlAPIError(409, exc.code, str(exc)) from exc
    if isinstance(exc, (SessionConfigurationError, SessionRuntimeError)):
        raise ControlAPIError(503, exc.code, str(exc)) from exc
    raise exc


class AdminUseCases:
    def __init__(
        self,
        *,
        operations_service: Any,
        store: Any,
        walking_skeleton_catalog: Any,
        definitions: Any,
        evaluation_catalog: Any,
        evaluation_store: Any,
        recorded_evaluation_service: Any,
        evaluation_suite_catalog: Any,
        evaluation_suite_service: Any,
        session_runtime: Any,
        runtime_bindings: Any,
        run_submission_policy: Any,
        attachment_store: Any,
        governed_boundary: Any,
        commerce_snapshot_ingress: Any,
        submission_store: Any,
        governed_execution: Any,
        tool_approval_service: Any,
        tool_approval_store: Any,
        governed_lifecycle: Any,
        direct_run_submission_enabled: bool,
        coordinator: Any,
        artifact_root: str | Path,
        native_stream_broker: Any,
        organization_catalog_root: str | Path | None = None,
        artifact_service: ArtifactService,
    ) -> None:
        self._operations_service = operations_service
        self._store = store
        self._walking_skeleton_catalog = walking_skeleton_catalog
        self._definitions = definitions
        self._assistant = OrganizationAssistantRoutingService(str(definitions.project_root), organization_catalog_root)
        self._evaluation_catalog = evaluation_catalog
        self._evaluation_store = evaluation_store
        self._recorded_evaluation_service = recorded_evaluation_service
        self._evaluation_suite_catalog = evaluation_suite_catalog
        self._evaluation_suite_service = evaluation_suite_service
        self._session_runtime = session_runtime
        self._runtime_bindings = runtime_bindings
        self._run_submission_policy = run_submission_policy
        self._attachment_store = attachment_store
        self._governed_boundary = governed_boundary
        self._commerce_snapshot_ingress = commerce_snapshot_ingress
        self._submission_store = submission_store
        self._governed_execution = governed_execution
        self._tool_approval_service = tool_approval_service
        self._tool_approval_store = tool_approval_store
        self._governed_lifecycle = governed_lifecycle
        self._direct_run_submission_enabled = direct_run_submission_enabled
        self._coordinator = coordinator
        self._artifact_root = artifact_root
        self._artifact_service = artifact_service
        self._native_stream_broker = native_stream_broker
        self._event_subscription: RunEventSubscription = PollingRunEventSubscription(store)

    def local_attachment_maximum(self) -> int:
        if self._attachment_store is None:
            raise ControlAPIError(503, "LOCAL_ATTACHMENT_NOT_CONFIGURED", "Local attachment ingress is not configured on this server")
        return int(self._attachment_store.policy.max_bytes)

    async def upload_local_attachment(self, *, filename: str, payload: bytes) -> LocalAttachmentUploadResponse:
        maximum = self.local_attachment_maximum()
        if len(payload) > maximum:
            raise ControlAPIError(413, "LOCAL_ATTACHMENT_TOO_LARGE", f"Local attachment exceeds the {maximum}-byte limit")
        try:
            record = self._attachment_store.create_slot(payload, filename)
        except AttachmentError as exc:
            raise ControlAPIError(422, "LOCAL_ATTACHMENT_INVALID", str(exc)) from exc
        return LocalAttachmentUploadResponse(**record.to_public_dict())

    def persisted_event_subscription(self, *, run_id: str) -> RunEventSubscription:
        try:
            self._store.get_run(run_id)
        except RecordNotFoundError as exc:
            raise ControlAPIError(404, "RUN_NOT_FOUND", "Run was not found") from exc
        return self._event_subscription

    async def native_stream_broker(self, *, run_id: str) -> Any:
        try:
            run = self._store.get_run(run_id)
        except RecordNotFoundError as exc:
            raise ControlAPIError(404, "RUN_NOT_FOUND", "Run was not found") from exc
        if run.status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}:
            if not await self._native_stream_broker.has_channel(run_id):
                raise ControlAPIError(409, "NATIVE_SDK_STREAM_UNAVAILABLE", "Native SDK stream is process-local and is no longer available")
        return self._native_stream_broker


    async def operations_summary(self, *, refresh_references: bool=False) -> OperationsSummaryResponse:
        try:
            payload = self._operations_service.snapshot(refresh_references=refresh_references)
        except Exception as exc:
            raise ControlAPIError(500, 'OPERATIONS_SNAPSHOT_FAILED', 'Operations snapshot could not be built') from exc
        payload['recent_runs'] = [run_response(item).model_dump(mode='json') for item in payload['recent_runs']]
        return OperationsSummaryResponse(**payload)

    async def list_tasks(self, *, status_filter: str | None=None, limit: int=50, offset: int=0) -> TaskListResponse:
        status_value = TaskStatus(status_filter) if status_filter else None
        items, total = self._store.list_tasks(status=status_value, limit=limit, offset=offset)
        return TaskListResponse(total=total, limit=limit, offset=offset, tasks=[task_response(item) for item in items])

    async def list_runs(self, *, status_filter: str | None=None, agent_definition_id: str | None=None, limit: int=50, offset: int=0) -> RunListResponse:
        status_value = RunStatus(status_filter) if status_filter else None
        items, total = self._store.list_runs(status=status_value, agent_definition_id=agent_definition_id, limit=limit, offset=offset)
        return RunListResponse(total=total, limit=limit, offset=offset, runs=[run_response(item) for item in items])

    async def list_runtime_scenarios(self) -> WalkingSkeletonScenarioListResponse:
        try:
            scenarios = self._walking_skeleton_catalog.list_scenarios()
            definition_ids = {item.agent_id for item in self._definitions.list_definitions()}
            evaluation_ids = {item.case_id for item in self._evaluation_catalog.list_cases()}
            for scenario in scenarios:
                if scenario.agent_definition_id not in definition_ids:
                    raise WalkingSkeletonCatalogError(f'Scenario Agent is not registered: {scenario.agent_definition_id}')
                if scenario.evaluation_case_id is not None and scenario.evaluation_case_id not in evaluation_ids:
                    raise WalkingSkeletonCatalogError(f'Scenario Evaluation is not registered: {scenario.evaluation_case_id}')
        except (WalkingSkeletonCatalogError, AgentDefinitionContractError, AgentDefinitionIntegrityError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise ControlAPIError(500, 'WALKING_SKELETON_CATALOG_INVALID', 'Walking skeleton scenario catalog is invalid') from exc
        return WalkingSkeletonScenarioListResponse(catalog_id=self._walking_skeleton_catalog.catalog_id, version=self._walking_skeleton_catalog.version, catalog_sha256=self._walking_skeleton_catalog.catalog_sha256, skeleton_state='IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING', scenarios=[WalkingSkeletonScenarioResponse(**scenario.to_public_dict()) for scenario in scenarios])

    async def list_agent_definitions(self) -> AgentDefinitionListResponse:
        try:
            items = self._definitions.list_definitions()
        except (AgentDefinitionContractError, AgentDefinitionIntegrityError, OSError) as exc:
            raise ControlAPIError(500, 'AGENT_DEFINITION_CATALOG_INVALID', 'Agent definition catalog is invalid') from exc
        return AgentDefinitionListResponse(definitions=[agent_definition_summary(item) for item in items])

    async def get_agent_definition(self, *, agent_id: str) -> AgentDefinitionDetailResponse:
        if re.fullmatch('[a-z][a-z0-9-]{1,63}', agent_id) is None:
            raise ControlAPIError(400, 'AGENT_DEFINITION_ID_INVALID', 'Agent definition ID is invalid')
        try:
            return agent_definition_detail(self._definitions.resolve(agent_id))
        except AgentDefinitionNotFoundError as exc:
            raise ControlAPIError(404, 'AGENT_DEFINITION_NOT_FOUND', 'Agent definition was not found') from exc
        except (AgentDefinitionContractError, AgentDefinitionIntegrityError, OSError) as exc:
            raise ControlAPIError(500, 'AGENT_DEFINITION_INVALID', 'Agent definition is invalid') from exc

    async def list_evaluation_cases(self) -> EvaluationCaseListResponse:
        try:
            items = self._evaluation_catalog.list_cases()
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            raise ControlAPIError(500, 'EVALUATION_CATALOG_INVALID', 'Evaluation catalog is invalid') from exc
        return EvaluationCaseListResponse(cases=[evaluation_case_summary(item) for item in items])

    async def get_evaluation_case(self, *, case_id: str) -> EvaluationCaseDetailResponse:
        if not case_id or any((character not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for character in case_id)):
            raise ControlAPIError(400, 'EVALUATION_CASE_ID_INVALID', 'Evaluation case ID is invalid')
        try:
            return evaluation_case_detail(self._evaluation_catalog.resolve(case_id))
        except FileNotFoundError as exc:
            raise ControlAPIError(404, 'EVALUATION_CASE_NOT_FOUND', 'Evaluation case was not found') from exc
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            raise ControlAPIError(500, 'EVALUATION_CASE_INVALID', 'Evaluation case is invalid') from exc

    async def list_evaluations(self, *, case_id: str | None=None, subject_run_id: str | None=None, state: str | None=None, limit: int=100, offset: int=0) -> EvaluationResultListResponse:
        rows, total = self._evaluation_store.list_results(case_id=case_id, subject_run_id=subject_run_id, state=state, limit=limit, offset=offset)
        return EvaluationResultListResponse(total=total, limit=limit, offset=offset, results=[evaluation_result_response(row) for row in rows])

    async def get_evaluation(self, *, evaluation_id: str) -> EvaluationResultResponse:
        try:
            return evaluation_result_response(self._evaluation_store.get(evaluation_id))
        except KeyError as exc:
            raise ControlAPIError(404, 'EVALUATION_NOT_FOUND', 'Evaluation result was not found') from exc

    async def compare_evaluations(self, *, left_evaluation_id: str, right_evaluation_id: str) -> EvaluationComparisonResponse:
        try:
            left = self._evaluation_store.get(left_evaluation_id)
            right = self._evaluation_store.get(right_evaluation_id)
        except KeyError as exc:
            raise ControlAPIError(404, 'EVALUATION_NOT_FOUND', 'Evaluation result was not found') from exc
        return EvaluationComparisonResponse(**compare_results(left, right))

    async def evaluate_recorded_run(self, *, run_id: str, request: EvaluateRecordedRunRequest) -> EvaluationResultResponse:
        try:
            outcome = self._recorded_evaluation_service.evaluate(run_id=run_id, case_id=request.case_id)
        except RecordedRunEvaluationError as exc:
            status_by_code = {RecordedRunEvaluationErrorCode.RUN_NOT_FOUND: 404, RecordedRunEvaluationErrorCode.EVALUATION_CASE_NOT_FOUND: 404, RecordedRunEvaluationErrorCode.RUN_NOT_SUCCEEDED: 409, RecordedRunEvaluationErrorCode.TASK_NOT_SUCCEEDED: 409, RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCOMPLETE: 409, RecordedRunEvaluationErrorCode.RUN_EVIDENCE_INCONSISTENT: 409, RecordedRunEvaluationErrorCode.AGENT_DEFINITION_DRIFT: 409, RecordedRunEvaluationErrorCode.RUNTIME_BINDING_DRIFT: 409, RecordedRunEvaluationErrorCode.EVALUATION_CASE_INVALID: 500, RecordedRunEvaluationErrorCode.FINAL_OUTPUT_ARTIFACT_INVALID: 500, RecordedRunEvaluationErrorCode.FINAL_OUTPUT_CONTRACT_INVALID: 500, RecordedRunEvaluationErrorCode.EVALUATION_PERSISTENCE_FAILED: 500}
            raise ControlAPIError(status_by_code[exc.code], exc.code.value, exc.message, details={'detail_type': exc.detail_type} if exc.detail_type else {}) from exc
        return evaluation_result_response(self._evaluation_store.get(outcome.evaluation.evaluation_id))

    async def list_evaluation_suites(self) -> EvaluationSuiteListResponse:
        try:
            suites = self._evaluation_suite_catalog.list_suites()
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            raise ControlAPIError(500, 'EVALUATION_SUITE_CATALOG_INVALID', 'Evaluation Suite catalog is invalid') from exc
        return EvaluationSuiteListResponse(suites=[evaluation_suite_summary(item) for item in suites])

    async def get_evaluation_suite(self, *, suite_id: str) -> EvaluationSuiteSummaryResponse:
        try:
            return evaluation_suite_summary(self._evaluation_suite_catalog.resolve(suite_id))
        except FileNotFoundError as exc:
            raise ControlAPIError(404, 'EVALUATION_SUITE_NOT_FOUND', 'Evaluation Suite was not found') from exc
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            raise ControlAPIError(500, 'EVALUATION_SUITE_INVALID', 'Evaluation Suite is invalid') from exc

    async def create_evaluation_suite_run(self, *, request: CreateEvaluationSuiteRunRequest) -> EvaluationSuiteRunResponse:
        try:
            row = self._evaluation_suite_service.run_suite(suite_id=request.suite_id, baseline_id=request.baseline_id, subjects=tuple((EvaluationSuiteSubject(item.subject_id, item.slot_id, item.run_id) for item in request.subjects)))
        except EvaluationSuiteError as exc:
            _raise_suite_error(exc)
        return EvaluationSuiteRunResponse(**row)

    async def get_evaluation_suite_run(self, *, suite_run_id: str) -> EvaluationSuiteRunResponse:
        try:
            return EvaluationSuiteRunResponse(**self._evaluation_store.get_suite_run(suite_run_id))
        except KeyError as exc:
            raise ControlAPIError(404, 'EVALUATION_SUITE_RUN_NOT_FOUND', 'Evaluation Suite run was not found') from exc

    async def create_evaluation_baseline(self, *, request: CreateEvaluationBaselineRequest) -> EvaluationBaselineResponse:
        try:
            row = self._evaluation_suite_service.create_baseline(source_suite_run_id=request.source_suite_run_id, label=request.label)
        except EvaluationSuiteError as exc:
            _raise_suite_error(exc)
        return EvaluationBaselineResponse(**row)

    async def get_evaluation_baseline(self, *, baseline_id: str) -> EvaluationBaselineResponse:
        try:
            return EvaluationBaselineResponse(**self._evaluation_store.get_baseline(baseline_id))
        except KeyError as exc:
            raise ControlAPIError(404, 'EVALUATION_BASELINE_NOT_FOUND', 'Evaluation Baseline was not found') from exc

    async def create_product_session(self, *, request: CreateSessionRequest) -> ProductSessionResponse:
        try:
            definition = self._definitions.resolve(request.agent_definition_id)
            binding = self._runtime_bindings.resolve(definition)
            if binding.execution_path not in {'sqlite-session-execution-v1', 'sqlite-session-approval-execution-v1', 'sqlite-session-native-handoff-execution-v1', 'sqlite-session-native-guardrail-execution-v1', 'sqlite-session-native-agent-tool-execution-v1', 'sqlite-session-bounded-cross-domain-read-subagent-execution-v1', 'sqlite-session-stateless-groupware-subagent-execution-v1', 'sqlite-session-stateless-organization-context-subagent-execution-v1', 'sqlite-session-native-mcp-execution-v1'}:
                raise SessionStateError('Agent is not executable through SQLite Session Runtime')
            return ProductSessionResponse(**self._session_runtime.create(definition=definition, runtime_binding_sha256=binding.runtime_binding_sha256).to_public_dict())
        except (AgentDefinitionContractError, AgentDefinitionIntegrityError, AgentDefinitionNotFoundError) as exc:
            raise ControlAPIError(422, 'AGENT_DEFINITION_INVALID', str(exc)) from exc
        except Exception as exc:
            _raise_session_error(exc)
        raise AssertionError('unreachable')

    async def list_product_sessions(self, *, limit: int=100) -> ProductSessionListResponse:
        records = self._session_runtime.list(limit=limit)
        return ProductSessionListResponse(total=len(records), sessions=[ProductSessionResponse(**item.to_public_dict()) for item in records])

    async def get_product_session(self, *, session_id: str) -> ProductSessionResponse:
        try:
            return ProductSessionResponse(**self._session_runtime.get(session_id).to_public_dict())
        except Exception as exc:
            _raise_session_error(exc)
        raise AssertionError('unreachable')

    async def clear_product_session(self, *, session_id: str) -> ProductSessionResponse:
        try:
            return ProductSessionResponse(**(await self._session_runtime.clear(session_id)).to_public_dict())
        except Exception as exc:
            _raise_session_error(exc)
        raise AssertionError('unreachable')

    async def rotate_product_session_history_key(self, *, session_id: str) -> SessionKeyRotationResponse:
        try:
            result = await self._session_runtime.rotate_history_key(session_id)
            return SessionKeyRotationResponse(**result.to_public_dict())
        except Exception as exc:
            _raise_session_error(exc)
        raise AssertionError('unreachable')

    async def create_assistant_session(self) -> ProductSessionResponse:
        return await self.create_product_session(
            request=CreateSessionRequest(
                agent_definition_id=self._assistant.policy.session_agent_id
            )
        )

    def _assistant_session_focus(self, session_id: str | None):
        if session_id is None:
            return None
        try:
            return self._session_runtime.get_context_focus(session_id)
        except SessionNotFound:
            return None
        except SessionRuntimeError as exc:
            _raise_session_error(exc)
        raise AssertionError("unreachable")

    def _assistant_route_decision(self, request: AssistantRouteRequest):
        session_context_focus = self._assistant_session_focus(request.session_id)
        try:
            decision = self._assistant.route(
                request=request.input,
                session_id=request.session_id,
                attachment_id=request.attachment_id,
                project_snapshot_id=request.project_snapshot_id,
                session_context_focus=session_context_focus,
            )
            if request.session_id and decision.executable_now and decision.selected_agent_id is not None:
                session_record = self._session_runtime.get(request.session_id)
                if decision.selected_agent_id != session_record.agent_definition_id:
                    raise ControlAPIError(409, "ASSISTANT_SESSION_BINDING_MISMATCH", "Assistant route selected an Agent outside the bound Session")
            return decision
        except ControlAPIError:
            raise
        except Exception as exc:
            raise ControlAPIError(422, "ASSISTANT_ROUTING_FAILED", str(exc)) from exc

    async def assistant_route(
        self, *, request: AssistantRouteRequest
    ) -> AssistantRouteResponse:
        decision = self._assistant_route_decision(request)
        return AssistantRouteResponse(**decision.to_public_dict())

    async def assistant_preflight(
        self, *, request: AssistantRunPreflightRequest
    ) -> AssistantRunPreflightResponse:
        route_request = AssistantRouteRequest(
            input=request.input,
            session_id=request.session_id,
            attachment_id=request.attachment_id,
            project_snapshot_id=request.project_snapshot_id,
        )
        decision = self._assistant_route_decision(route_request)
        route = AssistantRouteResponse(**decision.to_public_dict())
        if not route.executable_now or route.selected_agent_definition_id is None:
            return AssistantRunPreflightResponse(route=route, submission=None)
        model_input = request.input
        if route.selected_agent_definition_id in {
            self._assistant.policy.default_agent_id,
            self._assistant.policy.session_agent_id,
            self._assistant.groupware.policy.agent_id,
            self._assistant.organization_remote.policy.root_agent_id,
            self._assistant.organization_remote.policy.agent_id,
        }:
            model_input = self._assistant.build_model_request(decision, request.input)
        submission = await self.preflight_governed_run(
            request=GovernedRunPreflightRequest(
                agent_definition_id=route.selected_agent_definition_id,
                input=model_input,
                model=request.model,
                session_id=request.session_id,
                attachment_id=request.attachment_id,
                project_snapshot_id=request.project_snapshot_id,
                idempotency_key=request.idempotency_key,
            )
        )
        return AssistantRunPreflightResponse(route=route, submission=submission)

    def _organization_access(self, request: OrganizationContextQueryRequest) -> OrganizationAccessContext:
        return OrganizationAccessContext(
            tenant_id=request.tenant_id, principal_id=request.principal_id, roles=tuple(request.roles)
        )

    async def resolve_organization_glossary(
        self, *, request: OrganizationContextQueryRequest
    ) -> OrganizationContextQueryResponse:
        return OrganizationContextQueryResponse(**self._assistant.organization_context.glossary(request.query, self._organization_access(request), request.limit).to_public_dict())

    async def search_organization_knowledge(
        self, *, request: OrganizationContextQueryRequest
    ) -> OrganizationContextQueryResponse:
        return OrganizationContextQueryResponse(**self._assistant.organization_context.knowledge(request.query, self._organization_access(request), request.limit).to_public_dict())

    async def search_organization_directory(
        self, *, request: OrganizationContextQueryRequest
    ) -> OrganizationContextQueryResponse:
        return OrganizationContextQueryResponse(**self._assistant.organization_context.directory(request.query, self._organization_access(request), request.limit).to_public_dict())

    async def get_run_submission_policy(self) -> RunSubmissionPolicyResponse:
        payload = self._run_submission_policy.to_public_dict()
        payload.pop('schema_version', None)
        return RunSubmissionPolicyResponse(**payload)

    async def preflight_governed_run(self, *, request: GovernedRunPreflightRequest) -> RunSubmissionResponse:
        if self._governed_boundary is None:
            raise ControlAPIError(503, 'RUN_SUBMISSION_NOT_CONFIGURED', 'Governed Run submission is not configured on this server')
        settings = RuntimeSettings.from_env(model_override=request.model)
        try:
            decision = self._governed_boundary.preflight(
                authority_scope=self._run_submission_policy.authority_scope,
                agent_definition_id=request.agent_definition_id,
                request=request.input,
                model=settings.model,
                idempotency_key=request.idempotency_key,
                session_id=request.session_id,
                attachment_slot_id=request.attachment_id,
                project_snapshot_slot_id=request.project_snapshot_id,
            )
        except Exception as exc:
            _raise_submission_error(exc)
        return _submission_response(decision)

    async def preflight_commerce_snapshot(self, *, request: GovernedCommerceSnapshotPreflightRequest) -> RunSubmissionResponse:
        if self._commerce_snapshot_ingress is None:
            raise ControlAPIError(503, 'RUN_SUBMISSION_NOT_CONFIGURED', 'Governed Run submission is not configured on this server')
        settings = RuntimeSettings.from_env(model_override=request.model)
        try:
            decision = await self._commerce_snapshot_ingress.preflight(authority_scope=self._run_submission_policy.authority_scope, source_adapter_id=request.source_adapter_id, snapshot_key=request.snapshot_key, model=settings.model, idempotency_key=request.idempotency_key)
        except Exception as exc:
            _raise_commerce_snapshot_error(exc)
        return _submission_response(decision)

    async def get_governed_run_submission(self, *, submission_id: str) -> RunSubmissionResponse:
        try:
            return _submission_response(self._submission_store.get(submission_id))
        except Exception as exc:
            _raise_submission_error(exc)
        raise AssertionError('unreachable')

    async def confirm_governed_run_submission(self, *, submission_id: str, request: GovernedRunConfirmRequest) -> GovernedRunSubmissionResponse:
        if self._governed_execution is None:
            raise ControlAPIError(503, 'RUN_SUBMISSION_NOT_CONFIGURED', 'Governed Run submission is not configured on this server')
        decision = self._submission_store.get(submission_id)
        settings = RuntimeSettings.from_env(model_override=decision.model)
        try:
            result = await self._governed_execution.confirm_and_schedule(submission_id=submission_id, confirmation=request.confirmation, settings=settings)
        except Exception as exc:
            _raise_submission_error(exc)
        if isinstance(result, GenericExecutionEnvelope):
            _raise_envelope(result)
        return GovernedRunSubmissionResponse(submission=_submission_response(result.submission), task_id=result.task_id, run_id=result.run_id, scheduled=result.scheduled, replayed=result.replayed)

    async def prepare_local_tool_approval(self, *, submission_id: str) -> ToolApprovalResponse:
        if self._tool_approval_service is None:
            raise ControlAPIError(503, 'TOOL_APPROVAL_NOT_CONFIGURED', 'Local Tool approval is not configured')
        decision = self._submission_store.get(submission_id)
        settings = RuntimeSettings.from_env(model_override=decision.model)
        try:
            result = await self._tool_approval_service.prepare(submission_id=submission_id, settings=settings)
        except Exception as exc:
            if isinstance(exc, ToolApprovalNotFound):
                raise ControlAPIError(404, exc.code, str(exc)) from exc
            if isinstance(exc, (ToolApprovalStateError, ToolApprovalIntegrityError, ToolApprovalError)):
                raise ControlAPIError(409, exc.code, str(exc)) from exc
            _raise_submission_error(exc)
        return ToolApprovalResponse(**result.record.to_public_dict())

    async def list_tool_approvals(self, *, state: ToolApprovalState | None=None, limit: int=100, offset: int=0) -> ToolApprovalListResponse:
        approvals, total = self._tool_approval_store.list(state=state, limit=limit, offset=offset)
        return ToolApprovalListResponse(total=total, limit=limit, offset=offset, approvals=[item.to_inbox_dict() for item in approvals])

    async def get_tool_approval_inbox_item(self, *, approval_id: str) -> ToolApprovalInboxItemResponse:
        try:
            return ToolApprovalInboxItemResponse(**self._tool_approval_store.get(approval_id).to_inbox_dict())
        except ToolApprovalNotFound as exc:
            raise ControlAPIError(404, exc.code, str(exc)) from exc

    async def get_tool_approval(self, *, approval_id: str) -> ToolApprovalResponse:
        try:
            return ToolApprovalResponse(**self._tool_approval_store.get(approval_id).to_public_dict())
        except ToolApprovalNotFound as exc:
            raise ControlAPIError(404, exc.code, str(exc)) from exc

    async def decide_tool_approval(self, *, approval_id: str, request: ToolApprovalDecisionRequest) -> ToolApprovalResumeResponse:
        if self._tool_approval_service is None:
            raise ControlAPIError(503, 'TOOL_APPROVAL_NOT_CONFIGURED', 'Local Tool approval is not configured')
        try:
            record = self._tool_approval_store.get(approval_id)
        except ToolApprovalNotFound as exc:
            raise ControlAPIError(404, exc.code, str(exc)) from exc
        expected_confirmation = decision_confirmation_challenge(approval_id=record.approval_id, run_id=record.run_id, decision=request.decision)
        if not hmac.compare_digest(request.confirmation, expected_confirmation):
            raise ControlAPIError(409, ToolApprovalConfirmationError.code, 'The exact approval decision confirmation is required')
        submission = self._submission_store.get(record.submission_id)
        settings = RuntimeSettings.from_env(model_override=submission.model)
        try:
            result = await self._tool_approval_service.decide(approval_id=approval_id, decision=ToolApprovalDecision(request.decision), settings=settings)
        except ToolApprovalNotFound as exc:
            raise ControlAPIError(404, exc.code, str(exc)) from exc
        except (ToolApprovalStateError, ToolApprovalIntegrityError, ToolApprovalError) as exc:
            raise ControlAPIError(409, exc.code, str(exc)) from exc
        return ToolApprovalResumeResponse(approval=ToolApprovalResponse(**result.record.to_public_dict()), task_id=result.task_id, run_id=result.run_id, state=result.state, artifact_id=result.artifact_id, tool_executed=result.tool_executed, replayed=result.replayed)

    async def recover_stale_governed_submissions(self) -> GovernedRecoveryResponse:
        if self._governed_execution is None:
            raise ControlAPIError(503, 'RUN_SUBMISSION_NOT_CONFIGURED', 'Governed Run submission is not configured on this server')
        result = await self._governed_execution.recover_stale(settings_factory=lambda decision: RuntimeSettings.from_env(model_override=decision.model))
        return GovernedRecoveryResponse(**result.to_public_dict())

    async def reconcile_orphaned_running(self, *, _request: OrphanedRunReconciliationRequest) -> OrphanedRunReconciliationResponse:
        if self._governed_execution is None:
            raise ControlAPIError(503, 'RUN_SUBMISSION_NOT_CONFIGURED', 'Governed Run submission is not configured on this server')
        result = self._governed_execution.reconcile_orphaned_running()
        return OrphanedRunReconciliationResponse(**result.to_public_dict())

    async def reconcile_terminal_outcomes(self, *, _request: TerminalOutcomeReconciliationRequest) -> TerminalOutcomeReconciliationResponse:
        if self._governed_execution is None or self._governed_lifecycle is None:
            raise ControlAPIError(503, 'RUN_SUBMISSION_NOT_CONFIGURED', 'Governed Run submission is not configured on this server')
        result = self._governed_lifecycle.reconcile_terminal_outcomes(current_owner_id=self._governed_execution.owner_id)
        return TerminalOutcomeReconciliationResponse(**result.to_public_dict())

    async def cleanup_expired_protected_payloads(self) -> ProtectedPayloadRetentionResponse:
        if self._governed_lifecycle is None:
            raise ControlAPIError(503, 'RUN_SUBMISSION_NOT_CONFIGURED', 'Protected payload lifecycle is not configured on this server')
        result = self._governed_lifecycle.cleanup_expired()
        return ProtectedPayloadRetentionResponse(**result.to_public_dict())

    async def create_run(self, *, request: CreateRunRequest) -> CreateRunResponse:
        if not self._direct_run_submission_enabled:
            raise ControlAPIError(403, 'DIRECT_RUN_SUBMISSION_DISABLED', 'Direct Run submission is disabled; use the governed submission boundary')
        settings = RuntimeSettings.from_env(model_override=request.model)
        result = await self._coordinator.schedule(agent_definition_id=request.agent_definition_id, request=request.input, settings=settings, live_opt_in=request.confirm_live_call)
        if not isinstance(result, ScheduledExecution):
            _raise_envelope(result)
        task = self._store.get_task(result.task_id)
        run = self._store.get_run(result.run_id)
        return CreateRunResponse(task_id=task.task_id, run_id=run.run_id, task_status=task.status.value, run_status=run.status.value)

    async def get_task(self, *, task_id: str) -> TaskResponse:
        try:
            return task_response(self._store.get_task(task_id))
        except RecordNotFoundError as exc:
            raise ControlAPIError(404, 'TASK_NOT_FOUND', 'Task was not found') from exc

    async def get_run(self, *, run_id: str) -> RunResponse:
        try:
            return run_response(self._store.get_run(run_id))
        except RecordNotFoundError as exc:
            raise ControlAPIError(404, 'RUN_NOT_FOUND', 'Run was not found') from exc

    async def list_run_invocations(self, *, run_id: str) -> AgentInvocationListResponse:
        try:
            self._store.get_run(run_id)
        except RecordNotFoundError as exc:
            raise ControlAPIError(404, 'RUN_NOT_FOUND', 'Run was not found') from exc
        items = self._store.list_agent_invocations(run_id)
        return AgentInvocationListResponse(run_id=run_id, total=len(items), invocations=[AgentInvocationResponse(**item.to_public_dict()) for item in items])

    async def get_run_artifact(self, *, run_id: str) -> RunArtifactResponse:
        try:
            self._store.get_run(run_id)
            events = self._store.list_events(run_id)
        except RecordNotFoundError as exc:
            raise ControlAPIError(404, 'RUN_NOT_FOUND', 'Run was not found') from exc
        artifact_event = next((item for item in reversed(events) if item.event_type == 'artifact.created'), None)
        artifact_id = artifact_event.payload.get('artifact_id') if artifact_event else None
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ControlAPIError(404, 'RUN_ARTIFACT_NOT_FOUND', 'Run Artifact was not found')
        try:
            artifact, content = self._artifact_service.read_json(artifact_id)
        except (RecordNotFoundError, ArtifactIntegrityError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ControlAPIError(409, 'RUN_ARTIFACT_INTEGRITY_FAILED', 'Run Artifact integrity validation failed') from exc
        if artifact.media_type != 'application/json':
            raise ControlAPIError(415, 'RUN_ARTIFACT_MEDIA_TYPE_UNSUPPORTED', 'Run Artifact is not JSON')
        return RunArtifactResponse(artifact_id=artifact.artifact_id, run_id=artifact.run_id, artifact_type=artifact.artifact_type, media_type=artifact.media_type, sha256=artifact.sha256, byte_length=artifact.byte_length, created_at=artifact.created_at, verified_at=artifact.verified_at, content=content)

    async def get_run_outcome(self, *, run_id: str) -> RunResponse:
        try:
            run = self._store.get_run(run_id)
        except RecordNotFoundError as exc:
            raise ControlAPIError(404, 'RUN_NOT_FOUND', 'Run was not found') from exc
        if run.status.value == 'SUCCEEDED':
            return run_response(run)
        if run.status.value == 'FAILED':
            events = self._store.list_events(run_id)
            failure = next((item for item in reversed(events) if item.event_type == 'run.failed'), None)
            code = str(failure.payload.get('code', 'RUN_FAILED')) if failure else 'RUN_FAILED'
            if code == 'SDK_RUN_FAILED':
                status_code = 502
            elif code == 'PROCESS_LOSS_RECONCILED':
                status_code = 500
            elif code in {'API_KEY_MISSING', 'MODEL_NOT_CONFIGURED', 'SDK_NOT_INSTALLED', 'SDK_VERSION_MISMATCH', 'AGENT_POLICY_DENIED'}:
                status_code = 503
            else:
                status_code = 500
            details = {}
            if failure and failure.payload.get('detail_type'):
                details['detail_type'] = str(failure.payload['detail_type'])
            raise ControlAPIError(status_code, code, 'Run execution failed', retryable=bool(failure and failure.payload.get('retryable')), details=details)
        if run.status.value == 'CANCELLED':
            raise ControlAPIError(409, 'RUN_CANCELLED', 'Run was cancelled')
        raise ControlAPIError(409, 'RUN_NOT_TERMINAL', 'Run has not reached a terminal state', True)

    async def list_events(self, *, run_id: str, after: int=0) -> EventListResponse:
        try:
            events = self._store.list_events(run_id, after_sequence=after)
        except RecordNotFoundError as exc:
            raise ControlAPIError(404, 'RUN_NOT_FOUND', 'Run was not found') from exc
        return EventListResponse(run_id=run_id, after_sequence=after, events=[event_response(item) for item in events])

    async def cancel_run(self, *, run_id: str) -> CancelRunResponse:
        try:
            result = await self._coordinator.cancel(run_id)
        except RecordNotFoundError as exc:
            raise ControlAPIError(404, 'RUN_NOT_FOUND', 'Run was not found') from exc
        except RuntimeError as exc:
            raise ControlAPIError(409, str(exc), 'Run is already terminal') from exc
        task = self._store.get_task(result.task_id)
        run = self._store.get_run(result.run_id)
        return CancelRunResponse(task_id=task.task_id, run_id=run.run_id, task_status=task.status.value, run_status=run.status.value)
