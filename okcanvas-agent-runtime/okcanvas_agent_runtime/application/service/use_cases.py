from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from okcanvas_agent_protocols.rest.admin import (
    AgentDefinitionDetailResponse, AgentDefinitionListResponse, AgentInvocationListResponse,
    AgentInvocationResponse, AssistantRouteRequest, AssistantRouteResponse,
    AssistantRunPreflightRequest, AssistantRunPreflightResponse, CancelRunResponse,
    OrganizationContextQueryRequest, OrganizationContextQueryResponse,
    CreateSessionRequest, EventListResponse, GovernedRunConfirmRequest,
    GovernedRunPreflightRequest, GovernedRunSubmissionResponse, LocalAttachmentUploadResponse,
    ProductSessionListResponse, ProductSessionResponse, RunArtifactResponse, RunListResponse,
    RunResponse, RunSubmissionResponse, ToolApprovalDecisionRequest,
    ToolApprovalInboxItemResponse, ToolApprovalListResponse, ToolApprovalResponse,
    ToolApprovalResumeResponse,
)
from okcanvas_agent_protocols.rest.service import (
    ProjectSnapshotUploadResponse, ServiceArtifactListResponse, ServiceArtifactSummaryResponse,
    ServiceCapabilitiesResponse, ServiceErrorContractResponse, ServiceSandboxRuntimeResponse,
    ServiceSkillListResponse, ServiceSkillResponse, ServiceSubmissionListResponse,
    ServiceWhoAmIResponse,
)
from okcanvas_agent_runtime.agent.capabilities.topology import CapabilityFoundationCatalog
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.definitions.errors import (
    AgentDefinitionContractError, AgentDefinitionIntegrityError, AgentDefinitionNotFoundError,
)
from okcanvas_agent_runtime.agent.runtime import RuntimeBindingResolver
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity, MCPAccessCatalog
from okcanvas_agent_runtime.application.artifacts import ArtifactService
from okcanvas_agent_runtime.application.ports import (
    AttachmentStorePort,
    ProjectSnapshotStorePort,
    RunSubmissionStorePort,
    ServiceResourceOwnershipStorePort,
    SessionRuntimePort,
    ToolApprovalStorePort,
)
from okcanvas_agent_runtime.domain.runs.ports import ProductStore
from okcanvas_agent_runtime.agent.skills import (
    ProductSkillCatalog, ProductSkillContractError, ProductSkillIntegrityError,
    ProductSkillNotFoundError,
)
from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.organization_context import OrganizationAccessContext
from okcanvas_agent_runtime.application.admin.projections import (
    agent_definition_detail, agent_definition_summary, event_response, run_response,
)
from okcanvas_agent_runtime.application.approvals import (
    ToolApprovalConfirmationError, ToolApprovalDecision, ToolApprovalError,
    ToolApprovalIntegrityError, ToolApprovalNotFound, ToolApprovalState,
    ToolApprovalStateError, decision_confirmation_challenge,
)
from okcanvas_agent_runtime.application.errors import ControlAPIError
from okcanvas_agent_runtime.application.events import PollingRunEventSubscription
from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionEnvelope
from okcanvas_agent_runtime.application.submissions import (
    RunExecutionOwnershipTransition, RunSubmissionAuthorityError,
    RunSubmissionConfirmationError, RunSubmissionError, RunSubmissionIdempotencyConflict,
    RunSubmissionIntegrityError, RunSubmissionNotFound, RunSubmissionOwnershipTransition,
    RunSubmissionStateError, RunSubmissionValidationError,
)
from okcanvas_agent_runtime.application.submissions.protected_payload_errors import ProtectedPayloadError
from okcanvas_agent_runtime.core.baseline import PROJECT_VERSION
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.governance import resolve_architecture_constitution
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.core.service_identity import ServicePrincipal
from okcanvas_agent_runtime.domain.attachments import AttachmentError
from okcanvas_agent_runtime.domain.project_snapshots.errors import ProjectSnapshotError
from okcanvas_agent_runtime.domain.runs.errors import ArtifactIntegrityError, RecordNotFoundError
from okcanvas_agent_runtime.domain.runs.models import RunStatus
from okcanvas_agent_runtime.domain.sessions import (
    SessionBusyError, SessionConfigurationError, SessionIntegrityError, SessionNotFound,
    SessionRuntimeError, SessionStateError,
)


def _submission_response(decision: Any) -> RunSubmissionResponse:
    return RunSubmissionResponse(**decision.to_public_dict())


def _skill_response(package: Any) -> ServiceSkillResponse:
    payload = package.to_public_dict()
    payload.pop("schema_version", None)
    return ServiceSkillResponse(**payload)


def _raise_submission_error(exc: Exception) -> None:
    if isinstance(exc, RunSubmissionNotFound):
        raise ControlAPIError(404, exc.code, "Run submission was not found") from exc
    if isinstance(exc, RunSubmissionAuthorityError):
        raise ControlAPIError(403, exc.code, "Run submission authority is required") from exc
    if isinstance(exc, RunSubmissionValidationError):
        raise ControlAPIError(422, exc.code, str(exc)) from exc
    if isinstance(exc, (
        RunSubmissionIdempotencyConflict, RunSubmissionConfirmationError,
        RunSubmissionStateError, RunSubmissionIntegrityError, ProtectedPayloadError,
    )):
        raise ControlAPIError(409, exc.code, str(exc)) from exc
    if isinstance(exc, RunSubmissionError):
        raise ControlAPIError(500, exc.code, "Governed Run submission failed") from exc
    raise exc


def _raise_session_error(exc: Exception) -> None:
    if isinstance(exc, SessionNotFound):
        raise ControlAPIError(404, exc.code, str(exc)) from exc
    if isinstance(exc, SessionBusyError):
        raise ControlAPIError(409, exc.code, str(exc)) from exc
    if isinstance(exc, (SessionStateError, SessionIntegrityError)):
        raise ControlAPIError(409, exc.code, str(exc)) from exc
    if isinstance(exc, SessionConfigurationError):
        raise ControlAPIError(503, exc.code, str(exc)) from exc
    if isinstance(exc, SessionRuntimeError):
        raise ControlAPIError(500, exc.code, str(exc)) from exc
    raise exc


def _namespace_idempotency(principal: ServicePrincipal, client_key: str) -> str:
    digest = hashlib.sha256(
        f"{principal.tenant_id}\x00{principal.principal_id}\x00{client_key}".encode("utf-8")
    ).hexdigest()
    return f"service-{digest}"


class ServiceUseCases:
    """Service-client application commands and queries behind REST/SSE transports."""

    def __init__(
        self,
        *,
        ownership: ServiceResourceOwnershipStorePort,
        definitions: AgentDefinitionCatalog,
        runtime_bindings: RuntimeBindingResolver,
        session_runtime: SessionRuntimePort,
        attachment_store: AttachmentStorePort | None,
        project_snapshot_store: ProjectSnapshotStorePort | None,
        governed_boundary: Any,
        governed_execution: Any,
        submission_store: RunSubmissionStorePort,
        run_submission_policy: Any,
        tool_approval_service: Any,
        tool_approval_store: ToolApprovalStorePort,
        product_store: ProductStore,
        coordinator: Any,
        artifact_root: str | Path,
        sandbox_catalog: Any,
        organization_catalog_root: str | Path | None = None,
        artifact_service: ArtifactService,
    ) -> None:
        self._ownership = ownership
        self._definitions = definitions
        self._runtime_bindings = runtime_bindings
        self._sessions = session_runtime
        self._attachments = attachment_store
        self._snapshots = project_snapshot_store
        self._governed_boundary = governed_boundary
        self._governed_execution = governed_execution
        self._submissions = submission_store
        self._run_submission_policy = run_submission_policy
        self._tool_approval_service = tool_approval_service
        self._tool_approvals = tool_approval_store
        self._products = product_store
        self._coordinator = coordinator
        self._artifact_root = Path(artifact_root).expanduser().resolve()
        self._artifact_service = artifact_service
        self._skills = ProductSkillCatalog(definitions.project_root)
        self._sandbox = sandbox_catalog
        self._capability_foundation = CapabilityFoundationCatalog(definitions.project_root).resolve()
        self._assistant = OrganizationAssistantRoutingService(str(definitions.project_root), organization_catalog_root)
        self._mcp_catalog = MCPServerCatalog(definitions.project_root)
        self._mcp_access = MCPAccessCatalog(definitions.project_root)
        self._constitution = resolve_architecture_constitution()
        self._events = PollingRunEventSubscription(product_store)

    @property
    def event_subscription(self) -> PollingRunEventSubscription:
        return self._events

    @property
    def attachment_max_bytes(self) -> int:
        if self._attachments is None:
            raise ControlAPIError(503, "LOCAL_ATTACHMENT_NOT_CONFIGURED", "Local attachment ingress is not configured")
        return int(self._attachments.policy.max_bytes)

    @property
    def project_snapshot_max_bytes(self) -> int:
        if self._snapshots is None:
            raise ControlAPIError(503, "PROJECT_SNAPSHOT_NOT_CONFIGURED", "Project snapshot ingress is not configured")
        return int(self._snapshots.policy.max_archive_bytes)

    def _reconcile_expired_ingress_slots(self) -> dict[str, tuple[str, ...]]:
        expired_attachments: tuple[str, ...] = ()
        expired_snapshots: tuple[str, ...] = ()
        if self._attachments is not None:
            expired_attachments = self._attachments.cleanup_expired_slot_refs()
            for resource_id in expired_attachments:
                self._ownership.release_if_exists(resource_type="attachment-slot", resource_id=resource_id)
        if self._snapshots is not None:
            expired_snapshots = self._snapshots.cleanup_expired_slot_refs()
            for resource_id in expired_snapshots:
                self._ownership.release_if_exists(resource_type="project-snapshot-slot", resource_id=resource_id)
        return {"attachment-slot": expired_attachments, "project-snapshot-slot": expired_snapshots}

    def _release_missing_ingress_ownership(
        self, *, principal: ServicePrincipal, attachment_id: str | None,
        project_snapshot_id: str | None,
    ) -> None:
        if attachment_id is not None and self._attachments is not None and not self._attachments.slot_exists(attachment_id):
            self._ownership.release_if_owned(principal=principal, resource_type="attachment-slot", resource_id=attachment_id)
        if project_snapshot_id is not None and self._snapshots is not None and not self._snapshots.slot_exists(project_snapshot_id):
            self._ownership.release_if_owned(principal=principal, resource_type="project-snapshot-slot", resource_id=project_snapshot_id)

    def capabilities(self, principal: ServicePrincipal | None = None) -> ServiceCapabilitiesResponse:
        attachment_limits = {}
        if self._attachments is not None:
            policy = self._attachments.policy
            attachment_limits = {
                "max_attachments": policy.max_attachments, "max_bytes": policy.max_bytes,
                "allowed_media_types": list(policy.allowed_media_types), "max_pdf_pages": policy.max_pdf_pages,
                "max_image_width": policy.max_image_width, "max_image_height": policy.max_image_height,
                "max_image_pixels": policy.max_image_pixels, "slot_ttl_seconds": policy.slot_ttl_seconds,
            }
        snapshot_limits = {}
        if self._snapshots is not None:
            policy = self._snapshots.policy
            snapshot_limits = {
                "max_archive_bytes": policy.max_archive_bytes, "max_files": policy.max_files,
                "max_total_bytes": policy.max_total_bytes, "max_file_bytes": policy.max_file_bytes,
                "max_path_chars": policy.max_path_chars, "slot_ttl_seconds": policy.slot_ttl_seconds,
                "allowed_compression_methods": list(policy.allowed_compression_methods),
            }
        foundation = self._capability_foundation
        constitution = self._constitution
        delegated_identity = (
            DelegatedMCPIdentity.create(
                tenant_id=principal.tenant_id,
                principal_id=principal.principal_id,
                roles=tuple(role.value for role in principal.roles),
            )
            if principal is not None
            else None
        )
        groupware_readiness = self._assistant.groupware.readiness(delegated_identity)
        organization_context_readiness = self._assistant.organization_remote.readiness(
            delegated_identity
        )
        return ServiceCapabilitiesResponse(
            runtime_version=PROJECT_VERSION,
            supported_clients=["agent-cli", "agent-web", "agent-desktop"],
            development_harnesses=["/runner", "/console", "clients/cli"],
            service_resources=[
                "agent-definition", "session", "attachment-slot", "project-snapshot-slot",
                "binary-ingress-slot-delete", "binary-ingress-expiry-reconciliation",
                "atomic-service-submission-ownership-transfer", "atomic-task-run-ownership-transfer",
                "submission", "run", "persisted-event-stream", "invocation", "artifact",
                "tool-approval", "skill", "sandbox-runtime-metadata", "agent-capability-topology",
                "capability-discovery-policy", "sdk-example-inventory",
                "organization-assistant-route", "organization-assistant-preflight",
                "organization-assistant-session",
            ],
            run_submission_configured=self._governed_boundary is not None and self._governed_execution is not None,
            local_attachment_ingress_configured=self._attachments is not None,
            local_attachment_limits=attachment_limits,
            project_snapshot_ingress_configured=self._snapshots is not None,
            project_snapshot_limits=snapshot_limits,
            project_snapshot_api="/v1/service/project-snapshots" if self._snapshots is not None else None,
            skills_available=True, skill_catalog_api="/v1/service/skills",
            skill_foundation_step="STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1", next_skill_step=None,
            sandbox_runtime_foundation_available=True, sandbox_execution_enabled=True,
            sandbox_provider_lifecycle_enabled=True, sandbox_runtime_api="/v1/service/sandbox-runtime",
            sandbox_foundation_step="STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES",
            capability_topology_available=True, capability_foundation_schema=foundation.schema_version,
            capability_topology_schema="okcanvas-agent-capability-topology-v1",
            capability_agent_topology_count=foundation.agent_topology_count,
            capability_binding_count=foundation.binding_count,
            capability_families=[key for key, _ in foundation.family_counts],
            capability_discovery_policy_id=foundation.discovery_policy.policy_id,
            capability_discovery_policy_version=foundation.discovery_policy.version,
            capability_discovery_policy_sha256=foundation.discovery_policy.policy_sha256,
            capability_tool_search_structure_ready=True,
            capability_tool_search_runtime_enabled=foundation.discovery_policy.tool_search_runtime_enabled,
            capability_programmatic_tool_calling_structure_ready=True,
            capability_programmatic_tool_calling_runtime_enabled=foundation.discovery_policy.programmatic_tool_calling_runtime_enabled,
            capability_sdk_example_inventory_version=f"{foundation.sdk_example_inventory.sdk_package}-python-{foundation.sdk_example_inventory.sdk_version}",
            capability_sdk_example_inventory_count=len(foundation.sdk_example_inventory.records),
            capability_sdk_example_inventory_sha256=foundation.sdk_example_inventory.inventory_sha256,
            capability_topology_root_sha256=foundation.topology_root_sha256,
            architecture_constitution_integrated=True,
            architecture_constitution_id=constitution.constitution_id,
            architecture_constitution_version=constitution.constitution_version,
            architecture_constitution_authority_state=constitution.authority_state,
            architecture_constitution_sha256=constitution.constitution_sha256,
            architecture_constitution_clause_count=constitution.clause_count,
            architecture_constitution_required_gate_count=constitution.required_gate_count,
            architecture_constitution_source_movement_allowed=False,
            architecture_step_compliance_gate_implemented=True,
            organization_assistant_routing_available=True,
            organization_assistant_route_api="/v1/service/assistant/routes",
            organization_assistant_preflight_api="/v1/service/assistant/run-submissions/preflight",
            organization_assistant_session_api="/v1/service/assistant/sessions",
            organization_assistant_policy_id=self._assistant.policy.policy_id,
            organization_assistant_policy_version=self._assistant.policy.version,
            organization_assistant_policy_sha256=self._assistant.policy.policy_sha256,
            organization_assistant_default_agent_id=self._assistant.policy.default_agent_id,
            organization_assistant_session_agent_id=self._assistant.policy.session_agent_id,
            organization_assistant_unconfigured_capabilities=sorted(
                {
                    item.capability_id
                    for item in self._assistant.policy.capabilities.values()
                    if item.availability.value != "AVAILABLE"
                    and item.capability_id not in {
                        self._assistant.groupware.policy.capability_id,
                        self._assistant.organization_remote.policy.capability_id,
                    }
                }
                | ({"organization-knowledge-read-v1"} if self._assistant.organization_context.catalog.state.value == "EMPTY" else set())
                | ({self._assistant.groupware.policy.capability_id} if not groupware_readiness.executable_now else set())
                | ({self._assistant.organization_remote.policy.capability_id} if not organization_context_readiness.executable_now else set())
            ),
            organization_context_remote_read_state=organization_context_readiness.state.value,
            organization_context_remote_endpoint_configured=organization_context_readiness.endpoint_configured,
            organization_context_remote_credential_reference_configured=organization_context_readiness.credential_reference_configured,
            organization_context_remote_credential_value_configured=organization_context_readiness.credential_value_configured,
            organization_context_remote_identity_bound=organization_context_readiness.identity_bound,
            organization_context_remote_role_allowed=organization_context_readiness.role_allowed,
            organization_context_remote_executable_now=organization_context_readiness.executable_now,
            organization_context_foundation_available=True,
            organization_context_catalog_id=self._assistant.organization_context.catalog.catalog_id,
            organization_context_catalog_version=self._assistant.organization_context.catalog.version,
            organization_context_catalog_state=self._assistant.organization_context.catalog.state.value,
            organization_context_effective_at=self._assistant.organization_context.catalog.effective_at,
            organization_context_record_count=self._assistant.organization_context.catalog.record_count,
            organization_glossary_record_count=len(self._assistant.organization_context.catalog.glossary_records),
            organization_knowledge_record_count=len(self._assistant.organization_context.catalog.knowledge_records),
            organization_directory_record_count=len(self._assistant.organization_context.catalog.directory_records),
            organization_glossary_api="/v1/service/organization/glossary/resolve",
            organization_knowledge_api="/v1/service/organization/knowledge/search",
            organization_directory_api="/v1/service/organization/directory/search",
            multi_mcp_foundation_available=True,
            multi_mcp_max_remote_servers=self._mcp_access.policy.max_remote_servers_per_agent,
            delegated_mcp_identity_foundation_available=True,
            mcp_access_policy_id=self._mcp_access.policy.policy_id,
            mcp_access_policy_version=self._mcp_access.policy.version,
            mcp_access_policy_sha256=self._mcp_access.policy.policy_sha256,
            mcp_credential_reference_count=len(self._mcp_access.secret_references),
            mcp_active_remote_server_count=sum(
                1 for item in self._mcp_catalog.list_servers() if item.is_remote_streamable_http
            ),
            mcp_active_delegated_server_count=sum(
                1 for item in self._mcp_catalog.list_servers() if item.requires_delegated_identity
            ),
            mcp_health_mode=self._mcp_access.policy.health_mode,
            mcp_circuit_breaker_scope=self._mcp_access.policy.circuit_breaker_state_scope,
            mcp_write_enabled=False,
            groupware_read_foundation_available=True,
            groupware_read_policy_id=self._assistant.groupware.policy.policy_id,
            groupware_read_policy_version=self._assistant.groupware.policy.version,
            groupware_read_policy_sha256=self._assistant.groupware.policy.policy_sha256,
            groupware_read_agent_id=self._assistant.groupware.policy.agent_id,
            groupware_read_server_id=self._assistant.groupware.policy.server_id,
            groupware_read_allowed_tools=list(self._assistant.groupware.policy.allowed_tools),
            groupware_read_state=groupware_readiness.state.value,
            groupware_read_endpoint_configured=groupware_readiness.endpoint_configured,
            groupware_read_credential_reference_configured=groupware_readiness.credential_reference_configured,
            groupware_read_credential_value_configured=groupware_readiness.credential_value_configured,
            groupware_read_identity_bound=groupware_readiness.identity_bound,
            groupware_read_role_allowed=groupware_readiness.role_allowed,
            groupware_read_executable_now=groupware_readiness.executable_now,
            groupware_write_enabled=False,
            next_selected_step=RuntimeInfo().next_selected_step,
        )

    def sandbox_runtime(self) -> ServiceSandboxRuntimeResponse:
        try:
            foundation = self._sandbox.resolve()
        except Exception as exc:
            raise ControlAPIError(500, "PRODUCT_SANDBOX_RUNTIME_INVALID", "Product Sandbox Runtime contract is invalid") from exc
        return ServiceSandboxRuntimeResponse(**foundation.to_public_dict())

    @staticmethod
    def error_contract() -> ServiceErrorContractResponse:
        return ServiceErrorContractResponse(notes=[
            "Cross-principal and cross-tenant resources are returned as not found.",
            "Persisted SSE is the reconnectable service-client stream.",
            "Native SDK stream is a process-local development surface and is not exposed here.",
        ])

    @staticmethod
    def whoami(principal: ServicePrincipal) -> ServiceWhoAmIResponse:
        return ServiceWhoAmIResponse(**principal.to_public_dict())

    def list_skills(self) -> ServiceSkillListResponse:
        try: items = self._skills.list_packages()
        except (ProductSkillContractError, ProductSkillIntegrityError, OSError) as exc:
            raise ControlAPIError(500, "PRODUCT_SKILL_CATALOG_INVALID", "Product Skill catalog is invalid") from exc
        return ServiceSkillListResponse(total=len(items), skills=[_skill_response(item) for item in items])

    def get_skill(self, skill_id: str) -> ServiceSkillResponse:
        try: return _skill_response(self._skills.resolve(skill_id))
        except ProductSkillNotFoundError as exc:
            raise ControlAPIError(404, "PRODUCT_SKILL_NOT_FOUND", "Product Skill was not found") from exc
        except (ProductSkillContractError, ProductSkillIntegrityError, OSError) as exc:
            raise ControlAPIError(500, "PRODUCT_SKILL_INVALID", "Product Skill is invalid") from exc

    def list_agents(self) -> AgentDefinitionListResponse:
        try: items = self._definitions.list_definitions()
        except (AgentDefinitionContractError, AgentDefinitionIntegrityError, OSError) as exc:
            raise ControlAPIError(500, "AGENT_DEFINITION_CATALOG_INVALID", "Agent definition catalog is invalid") from exc
        return AgentDefinitionListResponse(definitions=[agent_definition_summary(item) for item in items])

    def get_agent(self, agent_id: str) -> AgentDefinitionDetailResponse:
        try: return agent_definition_detail(self._definitions.resolve(agent_id))
        except AgentDefinitionNotFoundError as exc:
            raise ControlAPIError(404, "AGENT_DEFINITION_NOT_FOUND", "Agent definition was not found") from exc
        except (AgentDefinitionContractError, AgentDefinitionIntegrityError, OSError) as exc:
            raise ControlAPIError(500, "AGENT_DEFINITION_INVALID", "Agent definition is invalid") from exc

    def create_session(self, request: Any, principal: ServicePrincipal) -> ProductSessionResponse:
        try:
            definition = self._definitions.resolve(request.agent_definition_id)
            binding = self._runtime_bindings.resolve(definition)
            if binding.execution_path not in {
                "sqlite-session-execution-v1", "sqlite-session-approval-execution-v1",
                "sqlite-session-native-handoff-execution-v1", "sqlite-session-native-guardrail-execution-v1",
                "sqlite-session-native-agent-tool-execution-v1",
                "sqlite-session-stateless-groupware-subagent-execution-v1", "sqlite-session-stateless-organization-context-subagent-execution-v1", "sqlite-session-native-mcp-execution-v1",
            }:
                raise SessionStateError("Agent is not executable through SQLite Session Runtime")
            record = self._sessions.create(definition=definition, runtime_binding_sha256=binding.runtime_binding_sha256)
            self._ownership.register(principal=principal, resource_type="session", resource_id=record.session_id)
            return ProductSessionResponse(**record.to_public_dict())
        except (AgentDefinitionContractError, AgentDefinitionIntegrityError, AgentDefinitionNotFoundError) as exc:
            raise ControlAPIError(422, "AGENT_DEFINITION_INVALID", str(exc)) from exc
        except Exception as exc: _raise_session_error(exc)
        raise AssertionError("unreachable")

    def list_sessions(self, limit: int, principal: ServicePrincipal) -> ProductSessionListResponse:
        ids = self._ownership.list_ids(principal=principal, resource_type="session", limit=limit)
        records = [self._sessions.get(item) for item in ids]
        return ProductSessionListResponse(total=len(records), sessions=[ProductSessionResponse(**item.to_public_dict()) for item in records])

    def get_session(self, session_id: str, principal: ServicePrincipal) -> ProductSessionResponse:
        self._ownership.require_principal(principal=principal, resource_type="session", resource_id=session_id)
        try: return ProductSessionResponse(**self._sessions.get(session_id).to_public_dict())
        except Exception as exc: _raise_session_error(exc)
        raise AssertionError("unreachable")

    async def clear_session(self, session_id: str, principal: ServicePrincipal) -> ProductSessionResponse:
        self._ownership.require_principal(principal=principal, resource_type="session", resource_id=session_id)
        try: return ProductSessionResponse(**(await self._sessions.clear(session_id)).to_public_dict())
        except Exception as exc: _raise_session_error(exc)
        raise AssertionError("unreachable")

    def upload_attachment(self, content: bytes, filename: str, principal: ServicePrincipal) -> LocalAttachmentUploadResponse:
        self._reconcile_expired_ingress_slots()
        if self._attachments is None:
            raise ControlAPIError(503, "LOCAL_ATTACHMENT_NOT_CONFIGURED", "Local attachment ingress is not configured")
        try: record = self._attachments.create_slot(content, filename)
        except AttachmentError as exc: raise ControlAPIError(422, "LOCAL_ATTACHMENT_INVALID", str(exc)) from exc
        try: self._ownership.register(principal=principal, resource_type="attachment-slot", resource_id=record.record_ref)
        except Exception:
            self._attachments.delete(record.record_ref)
            raise
        return LocalAttachmentUploadResponse(**record.to_public_dict())

    def delete_attachment(self, attachment_id: str, principal: ServicePrincipal) -> None:
        if self._attachments is None:
            raise ControlAPIError(503, "LOCAL_ATTACHMENT_NOT_CONFIGURED", "Local attachment ingress is not configured")
        self._ownership.require_principal(principal=principal, resource_type="attachment-slot", resource_id=attachment_id)
        self._attachments.delete(attachment_id)
        self._ownership.release(principal=principal, resource_type="attachment-slot", resource_id=attachment_id)

    def upload_project_snapshot(self, content: bytes, filename: str, principal: ServicePrincipal) -> ProjectSnapshotUploadResponse:
        self._reconcile_expired_ingress_slots()
        if self._snapshots is None:
            raise ControlAPIError(503, "PROJECT_SNAPSHOT_NOT_CONFIGURED", "Project snapshot ingress is not configured")
        try: record = self._snapshots.create_slot(content, filename)
        except ProjectSnapshotError as exc: raise ControlAPIError(422, "PROJECT_SNAPSHOT_INVALID", str(exc)) from exc
        try: self._ownership.register(principal=principal, resource_type="project-snapshot-slot", resource_id=record.record_ref)
        except Exception:
            self._snapshots.delete(record.record_ref)
            raise
        return ProjectSnapshotUploadResponse(**record.to_public_dict())

    def delete_project_snapshot(self, project_snapshot_id: str, principal: ServicePrincipal) -> None:
        if self._snapshots is None:
            raise ControlAPIError(503, "PROJECT_SNAPSHOT_NOT_CONFIGURED", "Project snapshot ingress is not configured")
        self._ownership.require_principal(principal=principal, resource_type="project-snapshot-slot", resource_id=project_snapshot_id)
        self._snapshots.delete(project_snapshot_id)
        self._ownership.release(principal=principal, resource_type="project-snapshot-slot", resource_id=project_snapshot_id)

    def preflight(self, request: GovernedRunPreflightRequest, principal: ServicePrincipal) -> RunSubmissionResponse:
        self._reconcile_expired_ingress_slots()
        if self._governed_boundary is None:
            raise ControlAPIError(503, "RUN_SUBMISSION_NOT_CONFIGURED", "Governed Run submission is not configured")
        if request.session_id: self._ownership.require_principal(principal=principal, resource_type="session", resource_id=request.session_id)
        if request.attachment_id: self._ownership.require_principal(principal=principal, resource_type="attachment-slot", resource_id=request.attachment_id)
        if request.project_snapshot_id: self._ownership.require_principal(principal=principal, resource_type="project-snapshot-slot", resource_id=request.project_snapshot_id)
        consumed = tuple(
            (kind, value) for kind, value in (
                ("attachment-slot", request.attachment_id),
                ("project-snapshot-slot", request.project_snapshot_id),
            ) if value
        )
        transition = RunSubmissionOwnershipTransition(
            tenant_id=principal.tenant_id, principal_id=principal.principal_id,
            roles=tuple(sorted(role.value for role in principal.roles)), consumed_resources=consumed,
        )
        settings = RuntimeSettings.from_env(model_override=request.model)
        try:
            decision = self._governed_boundary.preflight(
                authority_scope=self._run_submission_policy.authority_scope,
                agent_definition_id=request.agent_definition_id, request=request.input,
                model=settings.model, idempotency_key=_namespace_idempotency(principal, request.idempotency_key),
                session_id=request.session_id, attachment_slot_id=request.attachment_id,
                project_snapshot_slot_id=request.project_snapshot_id, ownership_transition=transition,
            )
        except Exception as exc:
            self._release_missing_ingress_ownership(
                principal=principal, attachment_id=request.attachment_id,
                project_snapshot_id=request.project_snapshot_id,
            )
            _raise_submission_error(exc)
        return _submission_response(decision)

    def create_assistant_session(self, principal: ServicePrincipal) -> ProductSessionResponse:
        return self.create_session(
            CreateSessionRequest(agent_definition_id=self._assistant.policy.session_agent_id),
            principal,
        )

    def assistant_route(
        self, request: AssistantRouteRequest, principal: ServicePrincipal
    ) -> AssistantRouteResponse:
        self._reconcile_expired_ingress_slots()
        if request.session_id:
            self._ownership.require_principal(
                principal=principal, resource_type="session", resource_id=request.session_id
            )
        if request.attachment_id:
            self._ownership.require_principal(
                principal=principal, resource_type="attachment-slot", resource_id=request.attachment_id
            )
        if request.project_snapshot_id:
            self._ownership.require_principal(
                principal=principal,
                resource_type="project-snapshot-slot",
                resource_id=request.project_snapshot_id,
            )
        try:
            decision = self._assistant.route(
                request=request.input,
                session_id=request.session_id,
                attachment_id=request.attachment_id,
                project_snapshot_id=request.project_snapshot_id,
                tenant_id=principal.tenant_id,
                principal_id=principal.principal_id,
                roles=tuple(role.value for role in principal.roles),
            )
        except Exception as exc:
            raise ControlAPIError(422, "ASSISTANT_ROUTING_FAILED", str(exc)) from exc
        return AssistantRouteResponse(**decision.to_public_dict())

    def assistant_preflight(
        self, request: AssistantRunPreflightRequest, principal: ServicePrincipal
    ) -> AssistantRunPreflightResponse:
        route_request = AssistantRouteRequest(
            input=request.input,
            session_id=request.session_id,
            attachment_id=request.attachment_id,
            project_snapshot_id=request.project_snapshot_id,
        )
        route = self.assistant_route(route_request, principal)
        if not route.executable_now or route.selected_agent_definition_id is None:
            return AssistantRunPreflightResponse(route=route, submission=None)
        decision = self._assistant.route(
            request=request.input,
            session_id=request.session_id,
            attachment_id=request.attachment_id,
            project_snapshot_id=request.project_snapshot_id,
            tenant_id=principal.tenant_id,
            principal_id=principal.principal_id,
            roles=tuple(role.value for role in principal.roles),
        )
        model_input = request.input
        if route.selected_agent_definition_id in {
            self._assistant.policy.default_agent_id,
            self._assistant.policy.session_agent_id,
            self._assistant.groupware.policy.agent_id,
            self._assistant.organization_remote.policy.root_agent_id,
            self._assistant.organization_remote.policy.agent_id,
        }:
            model_input = self._assistant.build_model_request(decision, request.input)
        submission = self.preflight(
            GovernedRunPreflightRequest(
                agent_definition_id=route.selected_agent_definition_id,
                input=model_input,
                model=request.model,
                session_id=request.session_id,
                attachment_id=request.attachment_id,
                project_snapshot_id=request.project_snapshot_id,
                idempotency_key=request.idempotency_key,
            ),
            principal,
        )
        return AssistantRunPreflightResponse(route=route, submission=submission)

    def resolve_organization_glossary(
        self, request: OrganizationContextQueryRequest, principal: ServicePrincipal
    ) -> OrganizationContextQueryResponse:
        access = OrganizationAccessContext(
            tenant_id=principal.tenant_id, principal_id=principal.principal_id,
            roles=tuple(role.value for role in principal.roles),
        )
        return OrganizationContextQueryResponse(**self._assistant.organization_context.glossary(request.query, access, request.limit).to_public_dict())

    def search_organization_knowledge(
        self, request: OrganizationContextQueryRequest, principal: ServicePrincipal
    ) -> OrganizationContextQueryResponse:
        access = OrganizationAccessContext(
            tenant_id=principal.tenant_id, principal_id=principal.principal_id,
            roles=tuple(role.value for role in principal.roles),
        )
        return OrganizationContextQueryResponse(**self._assistant.organization_context.knowledge(request.query, access, request.limit).to_public_dict())

    def search_organization_directory(
        self, request: OrganizationContextQueryRequest, principal: ServicePrincipal
    ) -> OrganizationContextQueryResponse:
        access = OrganizationAccessContext(
            tenant_id=principal.tenant_id, principal_id=principal.principal_id,
            roles=tuple(role.value for role in principal.roles),
        )
        return OrganizationContextQueryResponse(**self._assistant.organization_context.directory(request.query, access, request.limit).to_public_dict())

    def list_submissions(self, limit: int, principal: ServicePrincipal) -> ServiceSubmissionListResponse:
        ids = self._ownership.list_ids(principal=principal, resource_type="submission", limit=limit)
        items = [_submission_response(self._submissions.get(item)).model_dump(mode="json") for item in ids]
        return ServiceSubmissionListResponse(total=len(items), submissions=items)

    def get_submission(self, submission_id: str, principal: ServicePrincipal) -> RunSubmissionResponse:
        self._ownership.require_principal(principal=principal, resource_type="submission", resource_id=submission_id)
        try: return _submission_response(self._submissions.get(submission_id))
        except RunSubmissionNotFound as exc: raise ControlAPIError(404, exc.code, "Run submission was not found") from exc

    async def confirm_submission(self, submission_id: str, request: GovernedRunConfirmRequest, principal: ServicePrincipal) -> GovernedRunSubmissionResponse:
        self._ownership.require_principal(principal=principal, resource_type="submission", resource_id=submission_id)
        if self._governed_execution is None:
            raise ControlAPIError(503, "RUN_SUBMISSION_NOT_CONFIGURED", "Governed Run submission is not configured")
        decision = self._submissions.get(submission_id)
        try:
            result = await self._governed_execution.confirm_and_schedule(
                submission_id=submission_id, confirmation=request.confirmation,
                settings=RuntimeSettings.from_env(model_override=decision.model),
                ownership_transition=RunExecutionOwnershipTransition(
                    tenant_id=principal.tenant_id, principal_id=principal.principal_id,
                    roles=tuple(sorted(role.value for role in principal.roles)),
                ),
            )
        except Exception as exc: _raise_submission_error(exc)
        assert result is not None
        if isinstance(result, GenericExecutionEnvelope):
            if result.error is None: raise ControlAPIError(500, "RUN_EXECUTION_FAILED", "Run execution failed")
            raise ControlAPIError(500, result.error.code.value, result.error.message, result.error.retryable)
        return GovernedRunSubmissionResponse(
            submission=_submission_response(result.submission), task_id=result.task_id,
            run_id=result.run_id, scheduled=result.scheduled, replayed=result.replayed,
        )

    async def prepare_approval(self, submission_id: str, principal: ServicePrincipal) -> ToolApprovalResponse:
        self._ownership.require_principal(principal=principal, resource_type="submission", resource_id=submission_id)
        if self._tool_approval_service is None:
            raise ControlAPIError(503, "TOOL_APPROVAL_NOT_CONFIGURED", "Local Tool approval is not configured")
        decision = self._submissions.get(submission_id)
        result = await self._tool_approval_service.prepare(
            submission_id=submission_id, settings=RuntimeSettings.from_env(model_override=decision.model),
        )
        self._ownership.register(principal=principal, resource_type="task", resource_id=result.record.task_id)
        self._ownership.register(principal=principal, resource_type="run", resource_id=result.record.run_id)
        self._ownership.register(principal=principal, resource_type="approval", resource_id=result.record.approval_id)
        return ToolApprovalResponse(**result.record.to_public_dict())

    def list_approvals(self, state: ToolApprovalState | None, limit: int, principal: ServicePrincipal) -> ToolApprovalListResponse:
        ids = self._ownership.list_ids(principal=principal, resource_type="approval", tenant_wide=True, limit=limit)
        records = [self._tool_approvals.get(item) for item in ids]
        if state is not None: records = [item for item in records if item.state is state]
        return ToolApprovalListResponse(total=len(records), limit=limit, offset=0, approvals=[item.to_inbox_dict() for item in records])

    def approval_inbox(self, approval_id: str, principal: ServicePrincipal) -> ToolApprovalInboxItemResponse:
        self._ownership.require_tenant(principal=principal, resource_type="approval", resource_id=approval_id)
        try: return ToolApprovalInboxItemResponse(**self._tool_approvals.get(approval_id).to_inbox_dict())
        except ToolApprovalNotFound as exc: raise ControlAPIError(404, exc.code, str(exc)) from exc

    async def decide_approval(self, approval_id: str, request: ToolApprovalDecisionRequest, principal: ServicePrincipal) -> ToolApprovalResumeResponse:
        self._ownership.require_tenant(principal=principal, resource_type="approval", resource_id=approval_id)
        if self._tool_approval_service is None:
            raise ControlAPIError(503, "TOOL_APPROVAL_NOT_CONFIGURED", "Local Tool approval is not configured")
        record = self._tool_approvals.get(approval_id)
        expected = decision_confirmation_challenge(approval_id=record.approval_id, run_id=record.run_id, decision=request.decision)
        if not hmac.compare_digest(request.confirmation, expected):
            raise ControlAPIError(409, ToolApprovalConfirmationError.code, "The exact approval decision confirmation is required")
        submission = self._submissions.get(record.submission_id)
        try:
            result = await self._tool_approval_service.decide(
                approval_id=approval_id, decision=ToolApprovalDecision(request.decision),
                settings=RuntimeSettings.from_env(model_override=submission.model),
            )
        except ToolApprovalNotFound as exc: raise ControlAPIError(404, exc.code, str(exc)) from exc
        except (ToolApprovalStateError, ToolApprovalIntegrityError, ToolApprovalError) as exc:
            raise ControlAPIError(409, exc.code, str(exc)) from exc
        return ToolApprovalResumeResponse(
            approval=ToolApprovalResponse(**result.record.to_public_dict()), task_id=result.task_id,
            run_id=result.run_id, state=result.state, artifact_id=result.artifact_id,
            tool_executed=result.tool_executed, replayed=result.replayed,
        )

    def list_runs(self, limit: int, principal: ServicePrincipal) -> RunListResponse:
        ids = self._ownership.list_ids(principal=principal, resource_type="run", limit=limit)
        runs = [self._products.get_run(item) for item in ids]
        return RunListResponse(total=len(runs), limit=limit, offset=0, runs=[run_response(item) for item in runs])

    def get_run(self, run_id: str, principal: ServicePrincipal) -> RunResponse:
        self._ownership.require_principal(principal=principal, resource_type="run", resource_id=run_id)
        return run_response(self._products.get_run(run_id))

    def invocations(self, run_id: str, principal: ServicePrincipal) -> AgentInvocationListResponse:
        self._ownership.require_principal(principal=principal, resource_type="run", resource_id=run_id)
        items = self._products.list_agent_invocations(run_id)
        return AgentInvocationListResponse(run_id=run_id, total=len(items), invocations=[AgentInvocationResponse(**item.to_public_dict()) for item in items])

    def artifacts(self, run_id: str, principal: ServicePrincipal) -> ServiceArtifactListResponse:
        self._ownership.require_principal(principal=principal, resource_type="run", resource_id=run_id)
        items = self._products.list_artifacts(run_id)
        return ServiceArtifactListResponse(
            run_id=run_id, total=len(items), artifacts=[ServiceArtifactSummaryResponse(
                artifact_id=item.artifact_id, run_id=item.run_id, artifact_type=item.artifact_type,
                media_type=item.media_type, sha256=item.sha256, byte_length=item.byte_length,
                created_at=item.created_at, verified_at=item.verified_at,
            ) for item in items],
        )

    def artifact(self, run_id: str, artifact_id: str, principal: ServicePrincipal) -> RunArtifactResponse:
        self._ownership.require_principal(principal=principal, resource_type="run", resource_id=run_id)
        try:
            artifact, content = self._artifact_service.read_json(artifact_id)
        except (RecordNotFoundError, ArtifactIntegrityError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ControlAPIError(409, "RUN_ARTIFACT_INTEGRITY_FAILED", "Run Artifact integrity validation failed") from exc
        if artifact.media_type != "application/json":
            raise ControlAPIError(409, "RUN_ARTIFACT_INTEGRITY_FAILED", "Run Artifact storage contract is invalid")
        response = RunArtifactResponse(
            artifact_id=artifact.artifact_id, run_id=artifact.run_id, artifact_type=artifact.artifact_type,
            media_type=artifact.media_type, sha256=artifact.sha256, byte_length=artifact.byte_length,
            created_at=artifact.created_at, verified_at=artifact.verified_at, content=content,
        )
        if response.run_id != run_id: raise ControlAPIError(404, "RUN_ARTIFACT_NOT_FOUND", "Run Artifact was not found")
        return response

    def events(self, run_id: str, after: int, principal: ServicePrincipal) -> EventListResponse:
        self._ownership.require_principal(principal=principal, resource_type="run", resource_id=run_id)
        items = self._products.list_events(run_id, after_sequence=after)
        return EventListResponse(run_id=run_id, after_sequence=after, events=[event_response(item) for item in items])

    def require_run(self, run_id: str, principal: ServicePrincipal) -> None:
        self._ownership.require_principal(principal=principal, resource_type="run", resource_id=run_id)

    def outcome(self, run_id: str, principal: ServicePrincipal) -> RunResponse:
        self.require_run(run_id, principal)
        run = self._products.get_run(run_id)
        if run.status is RunStatus.SUCCEEDED: return run_response(run)
        if run.status is RunStatus.CANCELLED: raise ControlAPIError(409, "RUN_CANCELLED", "Run was cancelled")
        if run.status is RunStatus.FAILED: raise ControlAPIError(500, "RUN_FAILED", "Run execution failed")
        raise ControlAPIError(409, "RUN_NOT_TERMINAL", "Run has not reached a terminal state", True)

    async def cancel(self, run_id: str, principal: ServicePrincipal) -> CancelRunResponse:
        self.require_run(run_id, principal)
        try: result = await self._coordinator.cancel(run_id)
        except RecordNotFoundError as exc: raise ControlAPIError(404, "RUN_NOT_FOUND", "Run was not found") from exc
        except RuntimeError as exc: raise ControlAPIError(409, str(exc), "Run is already terminal") from exc
        task = self._products.get_task(result.task_id)
        run = self._products.get_run(result.run_id)
        return CancelRunResponse(task_id=task.task_id, run_id=run.run_id, task_status=task.status.value, run_status=run.status.value)
