from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from okcanvas_agent_protocols.rest.admin import (
    AgentDefinitionDetailResponse, AgentDefinitionListResponse, AgentInvocationListResponse,
    AssistantRouteRequest, AssistantRouteResponse, AssistantRunPreflightRequest,
    AssistantRunPreflightResponse, CancelRunResponse, CreateSessionRequest, EventListResponse,
    GovernedRunConfirmRequest,
    GovernedRunPreflightRequest, GovernedRunSubmissionResponse, LocalAttachmentUploadResponse,
    OrganizationContextQueryRequest, OrganizationContextQueryResponse,
    ProductSessionListResponse, ProductSessionResponse, RunArtifactResponse, RunListResponse,
    RunResponse, RunSubmissionResponse, ToolApprovalDecisionRequest,
    ToolApprovalInboxItemResponse, ToolApprovalListResponse, ToolApprovalResponse,
    ToolApprovalResumeResponse,
)
from okcanvas_agent_protocols.rest.service import (
    ProjectSnapshotUploadResponse, ServiceArtifactListResponse, ServiceCapabilitiesResponse,
    ServiceErrorContractResponse, ServiceSandboxRuntimeResponse, ServiceSkillListResponse,
    ServiceSkillResponse, ServiceSubmissionListResponse, ServiceWhoAmIResponse,
)
from okcanvas_agent_runtime.application.approvals import ToolApprovalState
from okcanvas_agent_runtime.application.errors import ControlAPIError
from okcanvas_agent_runtime.application.service import ServiceUseCases
from okcanvas_agent_runtime.core.service_identity import ServiceClientRole, ServicePrincipal
from okcanvas_agent_runtime.transport.admin.sse.stream import persisted_event_stream
from okcanvas_agent_runtime.transport.service.rest.auth import ServiceClientAuthenticator


async def _read_bounded_body(request: Request, maximum: int, *, code: str, label: str) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > maximum:
            raise ControlAPIError(413, code, f"{label} exceeds the {maximum}-byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


def build_service_client_router(
    *, authenticator: ServiceClientAuthenticator, use_cases: ServiceUseCases
) -> APIRouter:
    router = APIRouter(prefix="/v1/service", tags=["service-client-v1"])

    async def principal_dependency(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> ServicePrincipal:
        return await authenticator.require(authorization)

    async def agent_user(principal: ServicePrincipal = Depends(principal_dependency)) -> ServicePrincipal:
        return authenticator.require_role(principal, ServiceClientRole.AGENT_USER)

    async def approval_operator(principal: ServicePrincipal = Depends(principal_dependency)) -> ServicePrincipal:
        return authenticator.require_role(principal, ServiceClientRole.APPROVAL_OPERATOR)

    @router.get("/capabilities", response_model=ServiceCapabilitiesResponse)
    async def capabilities(principal: ServicePrincipal = Depends(principal_dependency)) -> ServiceCapabilitiesResponse:
        return use_cases.capabilities(principal)

    @router.get("/sandbox-runtime", response_model=ServiceSandboxRuntimeResponse)
    async def sandbox_runtime(_: ServicePrincipal = Depends(principal_dependency)) -> ServiceSandboxRuntimeResponse:
        return use_cases.sandbox_runtime()

    @router.get("/error-contract", response_model=ServiceErrorContractResponse)
    async def error_contract(_: ServicePrincipal = Depends(principal_dependency)) -> ServiceErrorContractResponse:
        return use_cases.error_contract()

    @router.get("/whoami", response_model=ServiceWhoAmIResponse)
    async def whoami(principal: ServicePrincipal = Depends(principal_dependency)) -> ServiceWhoAmIResponse:
        return use_cases.whoami(principal)

    @router.post(
        "/assistant/sessions",
        response_model=ProductSessionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_assistant_session(
        principal: ServicePrincipal = Depends(agent_user),
    ) -> ProductSessionResponse:
        return use_cases.create_assistant_session(principal)

    @router.post("/assistant/routes", response_model=AssistantRouteResponse)
    async def assistant_route(
        request: AssistantRouteRequest,
        principal: ServicePrincipal = Depends(agent_user),
    ) -> AssistantRouteResponse:
        return use_cases.assistant_route(request, principal)

    @router.post(
        "/assistant/run-submissions/preflight",
        response_model=AssistantRunPreflightResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def assistant_preflight(
        request: AssistantRunPreflightRequest,
        principal: ServicePrincipal = Depends(agent_user),
    ) -> AssistantRunPreflightResponse:
        return use_cases.assistant_preflight(request, principal)

    @router.post("/organization/glossary/resolve", response_model=OrganizationContextQueryResponse)
    async def resolve_organization_glossary(
        request: OrganizationContextQueryRequest,
        principal: ServicePrincipal = Depends(principal_dependency),
    ) -> OrganizationContextQueryResponse:
        return use_cases.resolve_organization_glossary(request, principal)

    @router.post("/organization/knowledge/search", response_model=OrganizationContextQueryResponse)
    async def search_organization_knowledge(
        request: OrganizationContextQueryRequest,
        principal: ServicePrincipal = Depends(principal_dependency),
    ) -> OrganizationContextQueryResponse:
        return use_cases.search_organization_knowledge(request, principal)

    @router.post("/organization/directory/search", response_model=OrganizationContextQueryResponse)
    async def search_organization_directory(
        request: OrganizationContextQueryRequest,
        principal: ServicePrincipal = Depends(principal_dependency),
    ) -> OrganizationContextQueryResponse:
        return use_cases.search_organization_directory(request, principal)

    @router.get("/skills", response_model=ServiceSkillListResponse)
    async def list_skills(_: ServicePrincipal = Depends(principal_dependency)) -> ServiceSkillListResponse:
        return use_cases.list_skills()

    @router.get("/skills/{skill_id}", response_model=ServiceSkillResponse)
    async def get_skill(skill_id: str, _: ServicePrincipal = Depends(principal_dependency)) -> ServiceSkillResponse:
        return use_cases.get_skill(skill_id)

    @router.get("/agent-definitions", response_model=AgentDefinitionListResponse)
    async def list_agents(_: ServicePrincipal = Depends(principal_dependency)) -> AgentDefinitionListResponse:
        return use_cases.list_agents()

    @router.get("/agent-definitions/{agent_id}", response_model=AgentDefinitionDetailResponse)
    async def get_agent(agent_id: str, _: ServicePrincipal = Depends(principal_dependency)) -> AgentDefinitionDetailResponse:
        return use_cases.get_agent(agent_id)

    @router.post("/sessions", response_model=ProductSessionResponse, status_code=status.HTTP_201_CREATED)
    async def create_session(request: CreateSessionRequest, principal: ServicePrincipal = Depends(agent_user)) -> ProductSessionResponse:
        return use_cases.create_session(request, principal)

    @router.get("/sessions", response_model=ProductSessionListResponse)
    async def list_sessions(limit: int = Query(default=100, ge=1, le=200), principal: ServicePrincipal = Depends(agent_user)) -> ProductSessionListResponse:
        return use_cases.list_sessions(limit, principal)

    @router.get("/sessions/{session_id}", response_model=ProductSessionResponse)
    async def get_session(session_id: str, principal: ServicePrincipal = Depends(agent_user)) -> ProductSessionResponse:
        return use_cases.get_session(session_id, principal)

    @router.post("/sessions/{session_id}/clear", response_model=ProductSessionResponse)
    async def clear_session(session_id: str, principal: ServicePrincipal = Depends(agent_user)) -> ProductSessionResponse:
        return await use_cases.clear_session(session_id, principal)

    @router.post("/local-attachments", response_model=LocalAttachmentUploadResponse, status_code=status.HTTP_201_CREATED)
    async def upload_attachment(
        request: Request,
        filename: str = Header(alias="X-OKCanvas-Attachment-Filename", min_length=1, max_length=255),
        principal: ServicePrincipal = Depends(agent_user),
    ) -> LocalAttachmentUploadResponse:
        content = await _read_bounded_body(request, use_cases.attachment_max_bytes, code="LOCAL_ATTACHMENT_TOO_LARGE", label="Local attachment")
        return use_cases.upload_attachment(content, filename, principal)

    @router.delete("/local-attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_attachment_slot(attachment_id: str, principal: ServicePrincipal = Depends(agent_user)) -> Response:
        use_cases.delete_attachment(attachment_id, principal)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/project-snapshots", response_model=ProjectSnapshotUploadResponse, status_code=status.HTTP_201_CREATED)
    async def upload_project_snapshot(
        request: Request,
        filename: str = Header(alias="X-OKCanvas-Project-Snapshot-Filename", min_length=1, max_length=120),
        principal: ServicePrincipal = Depends(agent_user),
    ) -> ProjectSnapshotUploadResponse:
        content = await _read_bounded_body(request, use_cases.project_snapshot_max_bytes, code="PROJECT_SNAPSHOT_TOO_LARGE", label="Project snapshot")
        return use_cases.upload_project_snapshot(content, filename, principal)

    @router.delete("/project-snapshots/{project_snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_project_snapshot_slot(project_snapshot_id: str, principal: ServicePrincipal = Depends(agent_user)) -> Response:
        use_cases.delete_project_snapshot(project_snapshot_id, principal)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/run-submissions/preflight", response_model=RunSubmissionResponse, status_code=status.HTTP_201_CREATED)
    async def preflight(request: GovernedRunPreflightRequest, principal: ServicePrincipal = Depends(agent_user)) -> RunSubmissionResponse:
        return use_cases.preflight(request, principal)

    @router.get("/run-submissions", response_model=ServiceSubmissionListResponse)
    async def list_submissions(limit: int = Query(default=100, ge=1, le=200), principal: ServicePrincipal = Depends(agent_user)) -> ServiceSubmissionListResponse:
        return use_cases.list_submissions(limit, principal)

    @router.get("/run-submissions/{submission_id}", response_model=RunSubmissionResponse)
    async def get_submission(submission_id: str, principal: ServicePrincipal = Depends(agent_user)) -> RunSubmissionResponse:
        return use_cases.get_submission(submission_id, principal)

    @router.post("/run-submissions/{submission_id}/confirm", response_model=GovernedRunSubmissionResponse, status_code=status.HTTP_202_ACCEPTED)
    async def confirm_submission(submission_id: str, request: GovernedRunConfirmRequest, principal: ServicePrincipal = Depends(agent_user)) -> GovernedRunSubmissionResponse:
        return await use_cases.confirm_submission(submission_id, request, principal)

    @router.post("/run-submissions/{submission_id}/prepare-approval", response_model=ToolApprovalResponse, status_code=status.HTTP_202_ACCEPTED)
    async def prepare_approval(submission_id: str, principal: ServicePrincipal = Depends(agent_user)) -> ToolApprovalResponse:
        return await use_cases.prepare_approval(submission_id, principal)

    @router.get("/tool-approvals", response_model=ToolApprovalListResponse)
    async def list_approvals(
        state: ToolApprovalState | None = Query(default=None), limit: int = Query(default=100, ge=1, le=200),
        principal: ServicePrincipal = Depends(approval_operator),
    ) -> ToolApprovalListResponse:
        return use_cases.list_approvals(state, limit, principal)

    @router.get("/tool-approvals/{approval_id}/inbox", response_model=ToolApprovalInboxItemResponse)
    async def approval_inbox(approval_id: str, principal: ServicePrincipal = Depends(approval_operator)) -> ToolApprovalInboxItemResponse:
        return use_cases.approval_inbox(approval_id, principal)

    @router.post("/tool-approvals/{approval_id}/decision", response_model=ToolApprovalResumeResponse)
    async def decide_approval(approval_id: str, request: ToolApprovalDecisionRequest, principal: ServicePrincipal = Depends(approval_operator)) -> ToolApprovalResumeResponse:
        return await use_cases.decide_approval(approval_id, request, principal)

    @router.get("/runs", response_model=RunListResponse)
    async def list_runs(limit: int = Query(default=100, ge=1, le=200), principal: ServicePrincipal = Depends(agent_user)) -> RunListResponse:
        return use_cases.list_runs(limit, principal)

    @router.get("/runs/{run_id}", response_model=RunResponse)
    async def get_run(run_id: str, principal: ServicePrincipal = Depends(agent_user)) -> RunResponse:
        return use_cases.get_run(run_id, principal)

    @router.get("/runs/{run_id}/invocations", response_model=AgentInvocationListResponse)
    async def invocations(run_id: str, principal: ServicePrincipal = Depends(agent_user)) -> AgentInvocationListResponse:
        return use_cases.invocations(run_id, principal)

    @router.get("/runs/{run_id}/artifacts", response_model=ServiceArtifactListResponse)
    async def artifacts(run_id: str, principal: ServicePrincipal = Depends(agent_user)) -> ServiceArtifactListResponse:
        return use_cases.artifacts(run_id, principal)

    @router.get("/runs/{run_id}/artifacts/{artifact_id}", response_model=RunArtifactResponse)
    async def artifact(run_id: str, artifact_id: str, principal: ServicePrincipal = Depends(agent_user)) -> RunArtifactResponse:
        return use_cases.artifact(run_id, artifact_id, principal)

    @router.get("/runs/{run_id}/events", response_model=EventListResponse)
    async def events(run_id: str, after: int = Query(default=0, ge=0), principal: ServicePrincipal = Depends(agent_user)) -> EventListResponse:
        return use_cases.events(run_id, after, principal)

    @router.get("/runs/{run_id}/events/stream")
    async def event_stream(
        run_id: str, cursor: int = Query(default=0, ge=0),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
        principal: ServicePrincipal = Depends(agent_user),
    ) -> StreamingResponse:
        use_cases.require_run(run_id, principal)
        if last_event_id is not None:
            try: cursor = max(cursor, int(last_event_id))
            except ValueError as exc: raise ControlAPIError(400, "INVALID_LAST_EVENT_ID", "Last-Event-ID must be an integer") from exc
        return StreamingResponse(
            persisted_event_stream(subscription=use_cases.event_subscription, run_id=run_id, after_sequence=cursor),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    @router.get("/runs/{run_id}/outcome", response_model=RunResponse)
    async def outcome(run_id: str, principal: ServicePrincipal = Depends(agent_user)) -> RunResponse:
        return use_cases.outcome(run_id, principal)

    @router.post("/runs/{run_id}/cancel", response_model=CancelRunResponse)
    async def cancel(run_id: str, principal: ServicePrincipal = Depends(agent_user)) -> CancelRunResponse:
        return await use_cases.cancel(run_id, principal)

    return router
