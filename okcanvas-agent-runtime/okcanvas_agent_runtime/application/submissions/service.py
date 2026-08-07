from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.domain.attachments.errors import AttachmentError
from okcanvas_agent_runtime.domain.attachments.model_policy import MultimodalModelPolicyCatalog
from okcanvas_agent_runtime.agent.runtime import RuntimeBindingResolver
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.agent.model.routing import ModelRouteDeniedError, ModelRoutingPolicyCatalog, ModelRoutingPolicyError
from okcanvas_agent_runtime.agent.tools.function import FunctionToolApprovalMode, FunctionToolRuntimeCatalog
from okcanvas_agent_runtime.domain.sessions import SessionRuntimeError
from okcanvas_agent_runtime.domain.project_snapshots.errors import ProjectSnapshotError
from okcanvas_agent_runtime.application.submissions.protected_payload import ProtectedPayloadContent
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity, MCPAccessCatalog, MCPAccessContractError
from okcanvas_agent_runtime.application.groupware_read import (
    GroupwareSessionDelegationCatalog,
    GroupwareSessionDelegationContractError,
    requires_groupware_session_delegation,
)
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationContextSessionDelegationCatalog,
    OrganizationContextSessionDelegationContractError,
    requires_organization_context_session_delegation,
)
from okcanvas_agent_runtime.application.ports import AttachmentStorePort, ProjectSnapshotStorePort, ProtectedPayloadStorePort, RunSubmissionStorePort, SessionRuntimePort

from okcanvas_agent_runtime.application.submissions.errors import RunSubmissionAuthorityError, RunSubmissionIdempotencyConflict, RunSubmissionValidationError
from okcanvas_agent_runtime.application.submissions.models import RunSubmissionDecision, RunSubmissionExecutionMode, RunSubmissionOwnershipTransition, RunSubmissionRecordState, ProtectedPayloadRetentionState, RunSubmissionSourceBinding
from okcanvas_agent_runtime.application.submissions.policy import RunSubmissionPolicyCatalog
from okcanvas_agent_runtime.application.submissions.lifecycle import GovernedLifecyclePolicy, GovernedLifecyclePolicyCatalog

_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class RunSubmissionBoundaryService:
    """Classify, fingerprint, encrypt, and persist a governed submission preflight."""

    def __init__(
        self,
        *,
        project_root: str,
        store: RunSubmissionStorePort,
        protected_payload_store: ProtectedPayloadStorePort,
        runtime_bindings: RuntimeBindingResolver,
        lifecycle_policy: GovernedLifecyclePolicy | None = None,
        session_runtime: SessionRuntimePort | None = None,
        attachment_store: AttachmentStorePort | None = None,
        project_snapshot_store: ProjectSnapshotStorePort | None = None,
    ) -> None:
        self._policy = RunSubmissionPolicyCatalog(project_root).resolve()
        self._lifecycle = lifecycle_policy or GovernedLifecyclePolicyCatalog(project_root).resolve()
        self._agents = AgentDefinitionCatalog(project_root)
        self._mcp = MCPServerCatalog(project_root)
        self._mcp_access = MCPAccessCatalog(project_root)
        self._model_routing = ModelRoutingPolicyCatalog(project_root)
        self._function_tools = FunctionToolRuntimeCatalog(project_root)
        self._runtime_bindings = runtime_bindings
        self._store = store
        self._payloads = protected_payload_store
        self._sessions = session_runtime
        self._attachments = attachment_store
        self._project_snapshots = project_snapshot_store
        self._multimodal_models = MultimodalModelPolicyCatalog(project_root)
        self._project_root = project_root

    @property
    def policy(self):
        return self._policy

    def preflight(
        self,
        *,
        authority_scope: str,
        agent_definition_id: str,
        request: str,
        model: str | None,
        idempotency_key: str,
        source_binding: RunSubmissionSourceBinding | None = None,
        session_id: str | None = None,
        attachment_slot_id: str | None = None,
        project_snapshot_slot_id: str | None = None,
        ownership_transition: RunSubmissionOwnershipTransition | None = None,
    ) -> RunSubmissionDecision:
        if authority_scope != self._policy.authority_scope:
            raise RunSubmissionAuthorityError(
                "Local operations read authority does not grant Run submission authority"
            )
        normalized = request.strip()
        if not normalized or len(normalized) > self._policy.input_max_chars or "\x00" in normalized:
            raise RunSubmissionValidationError(
                f"Run input must contain 1..{self._policy.input_max_chars} non-NUL characters"
            )
        if not (
            self._policy.idempotency_key_min_length
            <= len(idempotency_key)
            <= self._policy.idempotency_key_max_length
        ) or not _IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise RunSubmissionValidationError(
                "Idempotency key has invalid length or characters"
            )
        normalized_model = model.strip() if model and model.strip() else None
        definition = self._agents.resolve(agent_definition_id)
        mcp_server_ids = list(definition.mcp_servers)
        if definition.agent_id == "organization-assistant-session-agent":
            try:
                groupware_binding = GroupwareSessionDelegationCatalog(self._project_root).resolve(definition)
            except GroupwareSessionDelegationContractError as exc:
                raise RunSubmissionValidationError(str(exc)) from exc
            if requires_groupware_session_delegation(normalized):
                mcp_server_ids.append(groupware_binding.mcp_server_id)
        elif definition.agent_id == "organization-context-session-agent":
            try:
                context_binding = OrganizationContextSessionDelegationCatalog(self._project_root).resolve(definition)
            except OrganizationContextSessionDelegationContractError as exc:
                raise RunSubmissionValidationError(str(exc)) from exc
            if requires_organization_context_session_delegation(normalized):
                mcp_server_ids.append(context_binding.mcp_server_id)
        mcp_servers = self._mcp.resolve_many(tuple(mcp_server_ids))
        delegated_identity = None
        if any(item.requires_delegated_identity for item in mcp_servers):
            if ownership_transition is None:
                raise RunSubmissionAuthorityError(
                    "Delegated Remote MCP requires an authenticated service principal"
                )
            delegated_identity = DelegatedMCPIdentity.create(
                tenant_id=ownership_transition.tenant_id,
                principal_id=ownership_transition.principal_id,
                roles=ownership_transition.roles,
            )
            try:
                self._mcp_access.bind_many(mcp_servers, delegated_identity)
            except MCPAccessContractError as exc:
                raise RunSubmissionAuthorityError(str(exc)) from exc
        function_tools = self._function_tools.resolve_many(definition.tools)
        runtime_binding = self._runtime_bindings.resolve(definition)
        approval_modes = {item.approval_mode for item in function_tools}
        attachment_slot = None
        if definition.input_mode == "local-attachment-v1":
            if self._attachments is None or not attachment_slot_id:
                raise RunSubmissionValidationError(
                    "Local attachment Agent requires one uploaded attachment slot"
                )
            try:
                attachment_slot = self._attachments.inspect_slot(attachment_slot_id)
                self._multimodal_models.resolve().validate_model(normalized_model)
            except AttachmentError as exc:
                raise RunSubmissionValidationError(str(exc)) from exc
        elif attachment_slot_id is not None:
            raise RunSubmissionValidationError(
                "Attachment slot is valid only for a local-attachment Agent"
            )
        project_snapshot_slot = None
        if definition.workspace_access == "sandbox-readonly-v1":
            if self._project_snapshots is None or not project_snapshot_slot_id:
                raise RunSubmissionValidationError(
                    "Sandbox read-only Agent requires one uploaded project snapshot slot"
                )
            try:
                project_snapshot_slot = self._project_snapshots.inspect_slot(
                    project_snapshot_slot_id
                )
            except ProjectSnapshotError as exc:
                raise RunSubmissionValidationError(str(exc)) from exc
        elif project_snapshot_slot_id is not None:
            raise RunSubmissionValidationError(
                "Project snapshot slot is valid only for a sandbox-readonly Agent"
            )
        if definition.session_mode == "sqlite-v1":
            if self._sessions is None or not session_id:
                raise RunSubmissionValidationError("SQLite Session ID is required")
            if runtime_binding.execution_path not in {
                "sqlite-session-execution-v1",
                "sqlite-session-approval-execution-v1",
                "sqlite-session-native-handoff-execution-v1",
                "sqlite-session-native-guardrail-execution-v1",
                "sqlite-session-native-agent-tool-execution-v1",
                "sqlite-session-stateless-groupware-subagent-execution-v1",
                "sqlite-session-stateless-organization-context-subagent-execution-v1",
                "sqlite-session-native-mcp-execution-v1",
            }:
                raise RunSubmissionValidationError("Session Agent Runtime is not executable")
            try:
                self._sessions.validate_binding(
                    session_id=session_id,
                    definition=definition,
                    runtime_binding_sha256=runtime_binding.runtime_binding_sha256,
                )
            except SessionRuntimeError as exc:
                raise RunSubmissionValidationError(str(exc)) from exc
            if runtime_binding.execution_path == "sqlite-session-approval-execution-v1":
                mode = self._policy.local_tool_execution_mode
                reasons = ("sqlite-session-function-tool-requires-sdk-runstate-approval",)
            elif runtime_binding.execution_path == "sqlite-session-native-handoff-execution-v1":
                mode = self._policy.read_only_execution_mode
                reasons = ("sqlite-session-native-handoff-turn",)
            elif runtime_binding.execution_path == "sqlite-session-native-guardrail-execution-v1":
                mode = self._policy.read_only_execution_mode
                reasons = ("sqlite-session-native-guardrail-turn",)
            elif runtime_binding.execution_path == "sqlite-session-native-agent-tool-execution-v1":
                mode = self._policy.read_only_execution_mode
                reasons = ("sqlite-session-native-agent-tool-turn",)
            elif runtime_binding.execution_path == "sqlite-session-stateless-groupware-subagent-execution-v1":
                mode = self._policy.read_only_execution_mode
                reasons = ("sqlite-session-stateless-groupware-subagent-turn",)
            elif runtime_binding.execution_path == "sqlite-session-stateless-organization-context-subagent-execution-v1":
                mode = self._policy.read_only_execution_mode
                reasons = ("sqlite-session-stateless-organization-context-subagent-turn",)
            elif runtime_binding.execution_path == "sqlite-session-native-mcp-execution-v1":
                mode = self._policy.read_only_execution_mode
                reasons = ("sqlite-session-native-mcp-turn",)
            else:
                mode = self._policy.read_only_execution_mode
                reasons = ("local-sqlite-session-turn",)
        elif definition.session_mode != "disabled":
            mode = self._policy.handoff_or_session_execution_mode
            reasons = ("session-mode-not-executable",)
        elif session_id is not None:
            raise RunSubmissionValidationError("Session ID is valid only for a Session-enabled Agent")
        elif definition.input_mode == "local-attachment-v1":
            if runtime_binding.execution_path != "bounded-local-pdf-image-input-execution-v1":
                raise RunSubmissionValidationError("Local attachment Runtime is not executable")
            mode = self._policy.read_only_execution_mode
            reasons = ("bounded-local-pdf-image-input",)
        elif definition.orchestration_children:
            if runtime_binding.execution_path != "bounded-multi-agent-orchestration-v1":
                mode = self._policy.handoff_or_session_execution_mode
                reasons = ("orchestration-graph-is-not-step062-executable",)
            else:
                mode = self._policy.read_only_execution_mode
                reasons = ("fixed-bounded-orchestration-is-language-only",)
        elif definition.agent_tools:
            if runtime_binding.execution_path != "agent-as-tool-execution-v1":
                mode = self._policy.handoff_or_session_execution_mode
                reasons = ("agent-tool-graph-is-not-step042-executable",)
            else:
                mode = self._policy.read_only_execution_mode
                reasons = ("declared-agent-tool-is-language-only",)
        elif definition.handoffs:
            if runtime_binding.execution_path != "native-handoff-execution-v1":
                mode = self._policy.handoff_or_session_execution_mode
                reasons = ("handoff-graph-is-not-step041-executable",)
            else:
                mode = self._policy.read_only_execution_mode
                reasons = ("declared-native-handoff-is-language-only",)
        elif function_tools and mcp_servers:
            raise RunSubmissionValidationError(
                "P0 Runtime does not mix MCP and local Function Tools in one Agent"
            )
        elif len(approval_modes) > 1:
            raise RunSubmissionValidationError(
                "P0 Runtime does not mix approval modes in one Agent"
            )
        elif any(not item.read_only for item in mcp_servers):
            mode = self._policy.write_mcp_execution_mode
            reasons = ("write-mcp-is-proposal-only",)
        elif function_tools and approval_modes == {FunctionToolApprovalMode.ALWAYS}:
            if len(function_tools) != 1:
                raise RunSubmissionValidationError(
                    "P0 approval Runtime permits exactly one Function Tool"
                )
            mode = self._policy.local_tool_execution_mode
            reasons = ("function-tool-requires-sdk-runstate-approval",)
        elif function_tools:
            mode = self._policy.read_only_execution_mode
            reasons = ("registered-function-tools-are-read-only",)
        else:
            mode = self._policy.read_only_execution_mode
            reasons = ("agent-capabilities-are-read-only",)
        approval_tool_executable = bool(
            function_tools and approval_modes == {FunctionToolApprovalMode.ALWAYS}
        )
        if (
            mode is RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION
            or (
                mode is RunSubmissionExecutionMode.APPROVAL_INTERRUPTED
                and approval_tool_executable
            )
        ) and not normalized_model:
            raise RunSubmissionValidationError(
                "A concrete model must be selected before an executable Run can be fingerprinted"
            )
        if normalized_model is not None:
            try:
                self._model_routing.resolve_model(normalized_model)
            except (ModelRouteDeniedError, ModelRoutingPolicyError) as exc:
                raise RunSubmissionValidationError(str(exc)) from exc
        input_sha = _sha256_text(normalized)
        if source_binding is not None and source_binding.source_snapshot_sha256 != input_sha:
            raise RunSubmissionValidationError(
                "Source snapshot hash does not match the canonical governed request"
            )
        canonical = {
            "policy_sha256": self._policy.policy_sha256,
            "authority_scope": authority_scope,
            "agent_definition_id": definition.agent_id,
            "agent_definition_version": definition.version,
            "agent_definition_sha256": definition.definition_sha256,
            "runtime_binding_sha256": runtime_binding.runtime_binding_sha256,
            "session_id": session_id,
            "model": normalized_model,
            "input_sha256": input_sha,
            "execution_mode": mode.value,
            "source_binding": (
                source_binding.to_fingerprint_dict() if source_binding is not None else None
            ),
            "attachment": (attachment_slot.metadata.to_dict() if attachment_slot is not None else None),
            "project_snapshot": (
                {
                    "snapshot_sha256": project_snapshot_slot.metadata.snapshot_sha256,
                    "archive_sha256": project_snapshot_slot.metadata.archive_sha256,
                    "archive_byte_length": project_snapshot_slot.metadata.archive_byte_length,
                    "file_count": project_snapshot_slot.metadata.file_count,
                    "total_bytes": project_snapshot_slot.metadata.total_bytes,
                }
                if project_snapshot_slot is not None
                else None
            ),
        }
        fingerprint = _sha256_text(
            json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
        idempotency_sha = _sha256_text(idempotency_key)
        existing = self._store.find_by_idempotency_hash(idempotency_sha)
        if existing is not None:
            if existing.request_fingerprint_sha256 != fingerprint:
                raise RunSubmissionIdempotencyConflict(
                    "Idempotency key was already used for a different submission fingerprint"
                )
            if (
                (mode is RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION or (mode is RunSubmissionExecutionMode.APPROVAL_INTERRUPTED and approval_tool_executable))
                and not existing.protected_payload_persisted
            ):
                return self._attach_payload(
                    existing,
                    normalized,
                    attachment_slot_id=attachment_slot_id,
                    project_snapshot_slot_id=project_snapshot_slot_id,
                    ownership_transition=ownership_transition,
                )
            if attachment_slot_id is not None and self._attachments is not None:
                self._attachments.delete(attachment_slot_id)
            if project_snapshot_slot_id is not None and self._project_snapshots is not None:
                self._project_snapshots.delete(project_snapshot_slot_id)
            if ownership_transition is not None:
                existing = self._store.apply_ownership_transition(
                    existing.submission_id, ownership_transition
                )
            return existing

        if mode is RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION:
            state = RunSubmissionRecordState.READY_FOR_CONFIRMATION
            challenge = f"RUN {definition.agent_id}@{definition.version} {fingerprint[:12]}"
            executable_now = True
            approval_required = False
        elif mode is RunSubmissionExecutionMode.APPROVAL_INTERRUPTED:
            state = RunSubmissionRecordState.APPROVAL_PATH_REQUIRED
            challenge = None
            executable_now = False
            approval_required = True
        else:
            state = RunSubmissionRecordState.PROPOSAL_ONLY
            challenge = None
            executable_now = False
            approval_required = False
        created_at = _utc_now()
        submission_id = f"submission_{uuid.uuid4().hex}"
        payload_record = None
        attachment_binding = None
        bound_attachment_ref = None
        if attachment_slot_id is not None:
            assert self._attachments is not None
            try:
                bound_record, attachment_binding = self._attachments.bind_slot(attachment_slot_id, submission_id)
                bound_attachment_ref = bound_record.record_ref
            except AttachmentError as exc:
                raise RunSubmissionValidationError(str(exc)) from exc
        project_snapshot_binding = None
        bound_project_snapshot_ref = None
        if project_snapshot_slot_id is not None:
            assert self._project_snapshots is not None
            try:
                bound_snapshot, project_snapshot_binding = self._project_snapshots.bind_slot(
                    project_snapshot_slot_id, submission_id
                )
                bound_project_snapshot_ref = bound_snapshot.record_ref
            except ProjectSnapshotError as exc:
                if bound_attachment_ref is not None and self._attachments is not None:
                    self._attachments.delete(bound_attachment_ref)
                raise RunSubmissionValidationError(str(exc)) from exc
        if mode is RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION or (mode is RunSubmissionExecutionMode.APPROVAL_INTERRUPTED and approval_tool_executable):
            assert normalized_model is not None
            payload_record = self._payloads.write(
                ProtectedPayloadContent(
                    submission_id=submission_id,
                    agent_definition_id=definition.agent_id,
                    agent_definition_version=definition.version,
                    agent_definition_sha256=definition.definition_sha256,
                    runtime_binding_sha256=runtime_binding.runtime_binding_sha256,
                    session_id=session_id,
                    model=normalized_model,
                    request=normalized,
                    input_sha256=input_sha,
                    request_fingerprint_sha256=fingerprint,
                    created_at=created_at,
                    attachment=attachment_binding,
                    project_snapshot=project_snapshot_binding,
                    delegated_mcp_identity=delegated_identity,
                )
            )
        decision = RunSubmissionDecision(
            submission_id=submission_id,
            state=state,
            execution_mode=mode,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            policy_sha256=self._policy.policy_sha256,
            authority_scope=authority_scope,
            agent_definition_id=definition.agent_id,
            agent_definition_version=definition.version,
            agent_definition_sha256=definition.definition_sha256,
            runtime_binding_sha256=runtime_binding.runtime_binding_sha256,
            session_id=session_id,
            model=normalized_model,
            input_sha256=input_sha,
            request_fingerprint_sha256=fingerprint,
            idempotency_key_sha256=idempotency_sha,
            source_adapter_id=(source_binding.adapter_id if source_binding else None),
            source_adapter_version=(source_binding.adapter_version if source_binding else None),
            source_adapter_definition_sha256=(
                source_binding.adapter_definition_sha256 if source_binding else None
            ),
            source_request_sha256=(
                source_binding.source_request_sha256 if source_binding else None
            ),
            source_snapshot_sha256=(
                source_binding.source_snapshot_sha256 if source_binding else None
            ),
            source_acquired_at=(source_binding.acquired_at if source_binding else None),
            project_snapshot_sha256=(
                project_snapshot_slot.metadata.snapshot_sha256
                if project_snapshot_slot is not None else None
            ),
            project_snapshot_archive_sha256=(
                project_snapshot_slot.metadata.archive_sha256
                if project_snapshot_slot is not None else None
            ),
            project_snapshot_file_count=(
                project_snapshot_slot.metadata.file_count
                if project_snapshot_slot is not None else None
            ),
            project_snapshot_total_bytes=(
                project_snapshot_slot.metadata.total_bytes
                if project_snapshot_slot is not None else None
            ),
            confirmation_challenge=challenge,
            approval_required=approval_required,
            executable_now=executable_now,
            protected_payload_persisted=payload_record is not None,
            protected_payload_ref=payload_record.payload_ref if payload_record else None,
            protected_payload_sha256=payload_record.file_sha256 if payload_record else None,
            protected_payload_key_id=payload_record.key_id if payload_record else None,
            protected_payload_byte_length=payload_record.byte_length if payload_record else None,
            task_id=None,
            run_id=None,
            confirmed_at=None,
            payload_consumed_at=None,
            scheduled_at=None,
            claim_owner_id=None,
            claim_acquired_at=None,
            claim_expires_at=None,
            claim_attempts=0,
            recovery_count=0,
            last_recovered_at=None,
            execution_started_at=None,
            execution_completed_at=None,
            payload_retention_state=ProtectedPayloadRetentionState.ACTIVE,
            payload_delete_after=(
                (datetime.now(UTC) + timedelta(hours=self._lifecycle.unconfirmed_payload_ttl_hours)).isoformat().replace("+00:00", "Z")
                if payload_record is not None
                else None
            ),
            payload_deleted_at=None,
            payload_retention_reason=(
                "unconfirmed-preflight-ttl" if payload_record is not None else None
            ),
            reasons=reasons,
            created_at=created_at,
        )
        try:
            registered = self._store.register(
                decision, ownership_transition=ownership_transition
            )
        except Exception:
            if payload_record is not None:
                self._payloads.delete(payload_record.payload_ref)
            if bound_attachment_ref is not None and self._attachments is not None:
                self._attachments.delete(bound_attachment_ref)
            if bound_project_snapshot_ref is not None and self._project_snapshots is not None:
                self._project_snapshots.delete(bound_project_snapshot_ref)
            raise
        if registered.submission_id != decision.submission_id:
            if payload_record is not None:
                self._payloads.delete(payload_record.payload_ref)
            if bound_attachment_ref is not None and self._attachments is not None:
                self._attachments.delete(bound_attachment_ref)
            if bound_project_snapshot_ref is not None and self._project_snapshots is not None:
                self._project_snapshots.delete(bound_project_snapshot_ref)
            if attachment_binding is not None or project_snapshot_binding is not None:
                raise RunSubmissionIdempotencyConflict(
                    "Concurrent binary ingress preflight must be retried with a new upload slot"
                )
            if (
                (mode is RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION or (mode is RunSubmissionExecutionMode.APPROVAL_INTERRUPTED and approval_tool_executable))
                and not registered.protected_payload_persisted
            ):
                return self._attach_payload(
                    registered,
                    normalized,
                    attachment_slot_id=None,
                    project_snapshot_slot_id=None,
                )
        return registered

    def _attach_payload(
        self,
        decision: RunSubmissionDecision,
        normalized_request: str,
        attachment_slot_id: str | None = None,
        project_snapshot_slot_id: str | None = None,
        ownership_transition: RunSubmissionOwnershipTransition | None = None,
    ) -> RunSubmissionDecision:
        if decision.model is None:
            raise RunSubmissionValidationError(
                "Existing executable submission has no bound model"
            )
        attachment_binding = None
        bound_attachment_ref = None
        if attachment_slot_id is not None:
            if self._attachments is None:
                raise RunSubmissionValidationError("Attachment store is not configured")
            try:
                bound_record, attachment_binding = self._attachments.bind_slot(
                    attachment_slot_id, decision.submission_id
                )
                bound_attachment_ref = bound_record.record_ref
            except AttachmentError as exc:
                raise RunSubmissionValidationError(str(exc)) from exc
        project_snapshot_binding = None
        bound_project_snapshot_ref = None
        if project_snapshot_slot_id is not None:
            if self._project_snapshots is None:
                raise RunSubmissionValidationError("Project snapshot store is not configured")
            try:
                bound_snapshot, project_snapshot_binding = self._project_snapshots.bind_slot(
                    project_snapshot_slot_id, decision.submission_id
                )
                bound_project_snapshot_ref = bound_snapshot.record_ref
            except ProjectSnapshotError as exc:
                if bound_attachment_ref is not None and self._attachments is not None:
                    self._attachments.delete(bound_attachment_ref)
                raise RunSubmissionValidationError(str(exc)) from exc
        record = self._payloads.write(
            ProtectedPayloadContent(
                submission_id=decision.submission_id,
                agent_definition_id=decision.agent_definition_id,
                agent_definition_version=decision.agent_definition_version,
                agent_definition_sha256=decision.agent_definition_sha256,
                runtime_binding_sha256=decision.runtime_binding_sha256,
                session_id=decision.session_id,
                model=decision.model,
                request=normalized_request,
                input_sha256=decision.input_sha256,
                request_fingerprint_sha256=decision.request_fingerprint_sha256,
                created_at=decision.created_at,
                attachment=attachment_binding,
                project_snapshot=project_snapshot_binding,
            )
        )
        try:
            attached = self._store.attach_payload(
                decision.submission_id,
                payload_ref=record.payload_ref,
                file_sha256=record.file_sha256,
                key_id=record.key_id,
                byte_length=record.byte_length,
                delete_after=(
                    datetime.fromisoformat(decision.created_at.replace("Z", "+00:00"))
                    + timedelta(hours=self._lifecycle.unconfirmed_payload_ttl_hours)
                ).isoformat().replace("+00:00", "Z"),
                ownership_transition=ownership_transition,
            )
        except Exception:
            self._payloads.delete(record.payload_ref)
            if bound_attachment_ref is not None and self._attachments is not None:
                self._attachments.delete(bound_attachment_ref)
            if bound_project_snapshot_ref is not None and self._project_snapshots is not None:
                self._project_snapshots.delete(bound_project_snapshot_ref)
            raise
        if attached.protected_payload_ref != record.payload_ref:
            self._payloads.delete(record.payload_ref)
            if bound_attachment_ref is not None and self._attachments is not None:
                self._attachments.delete(bound_attachment_ref)
            if bound_project_snapshot_ref is not None and self._project_snapshots is not None:
                self._project_snapshots.delete(bound_project_snapshot_ref)
        return attached

    @staticmethod
    def confirmation_matches(decision: RunSubmissionDecision, supplied: str) -> bool:
        return bool(
            decision.execution_mode is RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION
            and decision.confirmation_challenge
            and supplied == decision.confirmation_challenge
        )
