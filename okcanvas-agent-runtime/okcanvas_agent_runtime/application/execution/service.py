from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Callable
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinition, AgentDefinitionCatalog, AgentDefinitionError
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.agent.mcp.definitions import MCPDefinitionError, MCPServerCatalog
from okcanvas_agent_runtime.agent.tools.function import FunctionToolApprovalMode, FunctionToolDefinitionContractError, FunctionToolDefinitionIntegrityError, FunctionToolDefinitionNotFoundError, FunctionToolRuntimeCatalog
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from okcanvas_agent_runtime.domain.invocations import InvocationPolicyCatalog, InvocationState
from okcanvas_agent_runtime.application.invocations.service import InvocationScopeService
from okcanvas_agent_runtime.domain.runs.ports import ProductStore
from okcanvas_agent_runtime.domain.attachments import LocalAttachmentPolicyCatalog, MultimodalModelPolicyCatalog
from okcanvas_agent_runtime.domain.attachments.models import PreparedLocalAttachment
from okcanvas_agent_runtime.domain.project_snapshots.models import PreparedProjectSnapshot
from okcanvas_agent_runtime.domain.sessions import (
    SessionBusyError, SessionIntegrityError, SessionRuntimeError, SessionContextFocusObservation,
)
from okcanvas_agent_runtime.application.ports import SessionRuntimePort
from okcanvas_agent_runtime.application.artifacts import ArtifactService

from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionEnvelope, GenericExecutionError, GenericExecutionErrorCode, GatewayLifecycleEvent
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.application.execution.gateway import GenericAgentGateway
from okcanvas_agent_runtime.application.execution.output_registry import serialize_output, validate_output_schema
from okcanvas_agent_runtime.agent.runtime import RuntimeBindingResolver
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity

MAX_REQUEST_CHARS = 100_000


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


@dataclass(frozen=True)
class PreparedGenericExecution:
    task_id: str
    run_id: str
    definition: AgentDefinition
    request: str
    runtime_binding_sha256: str
    attachment: PreparedLocalAttachment | None = None
    project_snapshot: PreparedProjectSnapshot | None = None
    session_id: str | None = None
    start_execution: Callable[[], bool] | None = None
    continue_execution: Callable[[], bool] | None = None
    delegated_mcp_identity: DelegatedMCPIdentity | None = None


class GenericAgentExecutionService:
    def __init__(
        self,
        *,
        definitions: AgentDefinitionCatalog,
        store: ProductStore,
        gateway: GenericAgentGateway,
        runtime_bindings: RuntimeBindingResolver,
        artifact_root: str | Path,
        session_runtime: SessionRuntimePort | None = None,
        artifact_service: ArtifactService,
    ) -> None:
        self._definitions = definitions
        self._store = store
        self._gateway = gateway
        self._artifact_root = Path(artifact_root).expanduser().resolve()
        self._artifact_service = artifact_service
        self._runtime_bindings = runtime_bindings
        self._sessions = session_runtime
        self._invocations = InvocationScopeService(
            definitions=definitions,
            store=store,
            policy=InvocationPolicyCatalog(definitions.project_root).resolve(),
        )

    def validate_request(
        self,
        *,
        agent_definition_id: str,
        request: str,
        settings: RuntimeSettings,
        live_opt_in: bool,
        session_id: str | None = None,
        attachment: PreparedLocalAttachment | None = None,
        project_snapshot: PreparedProjectSnapshot | None = None,
    ) -> tuple[AgentDefinition, str] | GenericExecutionEnvelope:
        normalized = request.strip()
        if not normalized or len(normalized) > MAX_REQUEST_CHARS:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.INVALID_REQUEST,
                    "Request must contain 1..100000 characters",
                ),
            )
        if not live_opt_in:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.LIVE_OPT_IN_REQUIRED,
                    "Live model execution requires explicit confirmation",
                ),
            )
        try:
            definition = self._definitions.resolve(agent_definition_id)
        except AgentDefinitionError as exc:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_DEFINITION_INVALID,
                    "Agent definition could not be resolved",
                    detail_type=type(exc).__name__,
                ),
            )
        try:
            validate_output_schema(definition.output_contract, definition.output_schema)
        except GenericExecutionFailure as failure:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                failure,
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        if definition.input_mode == "local-attachment-v1":
            if attachment is None:
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.INVALID_REQUEST,
                        "Local attachment Agent requires exactly one validated attachment",
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
            try:
                attachment_policy = LocalAttachmentPolicyCatalog(self._definitions.project_root).resolve()
                model_policy = MultimodalModelPolicyCatalog(self._definitions.project_root).resolve()
                model_policy.validate_model(settings.model)
                if attachment.metadata.media_type not in attachment_policy.allowed_media_types:
                    raise ValueError("Attachment media type is outside policy")
            except Exception as exc:
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Local attachment policy or model capability could not be validated",
                        detail_type=type(exc).__name__,
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
        elif attachment is not None:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Text-only Agent cannot receive a local attachment",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        if project_snapshot is not None and definition.workspace_access != "sandbox-readonly-v1":
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Project snapshot is valid only for a sandbox-readonly Agent",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )

        if definition.session_mode == "sqlite-v1":
            if self._sessions is None or not session_id:
                return self._preflight_failure(
                    agent_definition_id, settings,
                    GenericExecutionFailure(GenericExecutionErrorCode.AGENT_POLICY_DENIED, "SQLite Session ID is required"),
                    definition_version=definition.version, definition_sha256=definition.definition_sha256,
                )
            try:
                binding = self._runtime_bindings.resolve(definition)
                if binding.execution_path not in {
                    "sqlite-session-execution-v1",
                    "sqlite-session-native-handoff-execution-v1",
                    "sqlite-session-native-guardrail-execution-v1",
                    "sqlite-session-native-agent-tool-execution-v1",
                    "sqlite-session-bounded-cross-domain-read-subagent-execution-v1",
                    "sqlite-session-stateless-groupware-subagent-execution-v1",
                    "sqlite-session-stateless-organization-context-subagent-execution-v1",
                    "sqlite-session-native-mcp-execution-v1",
                }:
                    raise SessionIntegrityError("Session Agent Runtime is not executable")
                self._sessions.validate_binding(
                    session_id=session_id, definition=definition,
                    runtime_binding_sha256=binding.runtime_binding_sha256,
                )
            except SessionRuntimeError as exc:
                return self._preflight_failure(
                    agent_definition_id, settings,
                    GenericExecutionFailure(GenericExecutionErrorCode.AGENT_POLICY_DENIED, str(exc), detail_type=type(exc).__name__),
                    definition_version=definition.version, definition_sha256=definition.definition_sha256,
                )
        elif definition.session_mode != "disabled":
            return self._preflight_failure(
                agent_definition_id, settings,
                GenericExecutionFailure(GenericExecutionErrorCode.AGENT_POLICY_DENIED, "Unsupported SDK Session mode"),
                definition_version=definition.version, definition_sha256=definition.definition_sha256,
            )
        elif session_id is not None:
            return self._preflight_failure(
                agent_definition_id, settings,
                GenericExecutionFailure(GenericExecutionErrorCode.AGENT_POLICY_DENIED, "Session ID is valid only for a Session-enabled Agent"),
                definition_version=definition.version, definition_sha256=definition.definition_sha256,
            )
        if definition.guardrails:
            try:
                binding = self._runtime_bindings.resolve(definition)
            except Exception as exc:
                return self._preflight_failure(
                    agent_definition_id, settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Native Guardrail Runtime contract could not be resolved",
                        detail_type=type(exc).__name__,
                    ),
                    definition_version=definition.version, definition_sha256=definition.definition_sha256,
                )
            expected_guardrail_paths = {"native-guardrail-execution-v1"}
            if definition.session_mode == "sqlite-v1":
                expected_guardrail_paths.add("sqlite-session-native-guardrail-execution-v1")
            if binding.execution_path not in expected_guardrail_paths:
                return self._preflight_failure(
                    agent_definition_id, settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Agent Guardrail graph is not executable as STEP044 or STEP048 Native Guardrail Runtime",
                    ),
                    definition_version=definition.version, definition_sha256=definition.definition_sha256,
                )
        if definition.handoffs:
            try:
                binding = self._runtime_bindings.resolve(definition)
            except Exception as exc:
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Native Handoff Runtime contract could not be resolved",
                        detail_type=type(exc).__name__,
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
            expected_handoff_paths = {"native-handoff-execution-v1"}
            if definition.session_mode == "sqlite-v1":
                expected_handoff_paths.add("sqlite-session-native-handoff-execution-v1")
            if binding.execution_path not in expected_handoff_paths:
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Agent child graph is not executable as native Handoff or STEP047 Session Handoff",
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
        if definition.agent_tools:
            try:
                binding = self._runtime_bindings.resolve(definition)
            except Exception as exc:
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Agent-as-Tool Runtime contract could not be resolved",
                        detail_type=type(exc).__name__,
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
            expected_agent_tool_paths = {"agent-as-tool-execution-v1"}
            if definition.session_mode == "sqlite-v1":
                expected_agent_tool_paths.add("sqlite-session-native-agent-tool-execution-v1")
                expected_agent_tool_paths.add("sqlite-session-bounded-cross-domain-read-subagent-execution-v1")
                expected_agent_tool_paths.add("sqlite-session-stateless-groupware-subagent-execution-v1")
                expected_agent_tool_paths.add("sqlite-session-stateless-organization-context-subagent-execution-v1")
            if binding.execution_path not in expected_agent_tool_paths:
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Agent child graph is not executable as STEP042 or STEP049 Agent-as-Tool",
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
        if definition.hosted_tools:
            try:
                binding = self._runtime_bindings.resolve(definition)
            except Exception as exc:
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.HOSTED_SEARCH_POLICY_VIOLATION,
                        "Hosted Web Search Runtime contract could not be resolved",
                        detail_type=type(exc).__name__,
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
            if binding.execution_path != "hosted-web-search-execution-v1":
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.HOSTED_SEARCH_POLICY_VIOLATION,
                        "Agent is not executable as STEP067 Hosted Web Search",
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
        if definition.orchestration_children:
            try:
                binding = self._runtime_bindings.resolve(definition)
            except Exception as exc:
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Bounded orchestration Runtime contract could not be resolved",
                        detail_type=type(exc).__name__,
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
            if binding.execution_path != "bounded-multi-agent-orchestration-v1":
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Agent graph is not executable as STEP062 bounded orchestration",
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
        try:
            function_tool_runtimes = FunctionToolRuntimeCatalog(
                self._definitions.project_root
            ).resolve_many(definition.tools)
        except (
            FunctionToolDefinitionContractError,
            FunctionToolDefinitionIntegrityError,
            FunctionToolDefinitionNotFoundError,
        ) as exc:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.FUNCTION_TOOL_CONFIGURATION_INVALID,
                    "Agent Function Tool configuration could not be resolved",
                    detail_type=type(exc).__name__,
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        if any(
            item.approval_mode is FunctionToolApprovalMode.ALWAYS
            for item in function_tool_runtimes
        ):
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Approval-required Function Tools must use the governed approval path",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        if definition.workspace_access == "sandbox-readonly-v1":
            try:
                sandbox_binding = self._runtime_bindings.resolve(definition)
            except Exception as exc:
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Read-only Sandbox Runtime contract could not be resolved",
                        detail_type=type(exc).__name__,
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
            if (
                sandbox_binding.execution_path != "product-owned-readonly-sandbox-agent-execution-v1"
                or len(function_tool_runtimes) != 1
                or function_tool_runtimes[0].factory_id != "sandbox_project_readonly_inspect_v1"
            ):
                return self._preflight_failure(
                    agent_definition_id,
                    settings,
                    GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Agent is not executable as the STEP075 read-only Sandbox Agent",
                    ),
                    definition_version=definition.version,
                    definition_sha256=definition.definition_sha256,
                )
        if len(function_tool_runtimes) > 1:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "P0 generic Function Tool execution permits exactly one Tool",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        try:
            mcp_definitions = MCPServerCatalog(self._definitions.project_root).resolve_many(
                definition.mcp_servers
            )
        except MCPDefinitionError as exc:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.MCP_CONFIGURATION_INVALID,
                    "Agent MCP server configuration could not be resolved",
                    detail_type=type(exc).__name__,
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        if definition.handoffs and (
            definition.agent_tools or function_tool_runtimes or mcp_definitions
        ):
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "STEP041 does not mix Handoff with Agent-as-Tool, MCP, or local Function Tools",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        if definition.agent_tools and (
            definition.handoffs or function_tool_runtimes or mcp_definitions
        ):
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "STEP042 does not mix Agent-as-Tool with Handoff, MCP, or local Function Tools",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        if function_tool_runtimes and mcp_definitions:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "P0 Runtime does not mix MCP and local Function Tools",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        if any(not item.read_only for item in mcp_definitions):
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Governed generic execution permits only read-only MCP servers",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        return definition, normalized

    def prepare(
        self,
        *,
        agent_definition_id: str,
        request: str,
        settings: RuntimeSettings,
        live_opt_in: bool,
        session_id: str | None = None,
        attachment: PreparedLocalAttachment | None = None,
        project_snapshot: PreparedProjectSnapshot | None = None,
        delegated_mcp_identity: DelegatedMCPIdentity | None = None,
    ) -> PreparedGenericExecution | GenericExecutionEnvelope:
        validated = self.validate_request(
            agent_definition_id=agent_definition_id,
            request=request,
            settings=settings,
            live_opt_in=live_opt_in,
            session_id=session_id,
            attachment=attachment,
            project_snapshot=project_snapshot,
        )
        if isinstance(validated, GenericExecutionEnvelope):
            return validated
        definition, normalized = validated
        try:
            task = self._store.create_task(
                task_type="GENERIC_AGENT_EXECUTION",
                input_sha256=_sha256_text(normalized),
                agent_definition_id=definition.agent_id,
                agent_definition_version=definition.version,
            )
            run = self._store.create_run(task_id=task.task_id)
        except Exception as exc:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                    "Generic Agent execution product state could not be prepared",
                    detail_type=type(exc).__name__,
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        runtime_binding = self._runtime_bindings.resolve(definition)
        return PreparedGenericExecution(
            task_id=task.task_id,
            run_id=run.run_id,
            definition=definition,
            request=normalized,
            runtime_binding_sha256=runtime_binding.runtime_binding_sha256,
            attachment=attachment,
            project_snapshot=project_snapshot,
            session_id=session_id,
            delegated_mcp_identity=delegated_mcp_identity,
        )

    def prepare_existing(
        self,
        *,
        task_id: str,
        run_id: str,
        agent_definition_id: str,
        expected_definition_version: str,
        expected_definition_sha256: str,
        expected_runtime_binding_sha256: str,
        expected_input_sha256: str,
        expected_payload_ref: str,
        request: str,
        settings: RuntimeSettings,
        session_id: str | None = None,
        attachment: PreparedLocalAttachment | None = None,
        project_snapshot: PreparedProjectSnapshot | None = None,
        delegated_mcp_identity: DelegatedMCPIdentity | None = None,
    ) -> PreparedGenericExecution | GenericExecutionEnvelope:
        validated = self.validate_request(
            agent_definition_id=agent_definition_id,
            request=request,
            settings=settings,
            live_opt_in=True,
            session_id=session_id,
            attachment=attachment,
            project_snapshot=project_snapshot,
        )
        if isinstance(validated, GenericExecutionEnvelope):
            return validated
        definition, normalized = validated
        runtime_binding = self._runtime_bindings.resolve(definition)
        if (
            definition.version != expected_definition_version
            or definition.definition_sha256 != expected_definition_sha256
            or runtime_binding.runtime_binding_sha256 != expected_runtime_binding_sha256
            or _sha256_text(normalized) != expected_input_sha256
        ):
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_DEFINITION_INVALID,
                    "Governed submission identity changed before execution",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        try:
            task = self._store.get_task(task_id)
            run = self._store.get_run(run_id)
        except Exception as exc:
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                    "Governed Product Task/Run binding could not be loaded",
                    detail_type=type(exc).__name__,
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        if (
            task.status is not TaskStatus.READY
            or run.status is not RunStatus.CREATED
            or run.task_id != task.task_id
            or task.input_sha256 != expected_input_sha256
            or task.protected_payload_ref != expected_payload_ref
            or task.agent_definition_id != definition.agent_id
            or task.agent_definition_version != definition.version
            or run.agent_definition_id != definition.agent_id
            or run.agent_definition_version != definition.version
        ):
            return self._preflight_failure(
                agent_definition_id,
                settings,
                GenericExecutionFailure(
                    GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                    "Governed Product Task/Run binding does not match the submission",
                ),
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
            )
        return PreparedGenericExecution(
            task_id=task.task_id,
            run_id=run.run_id,
            definition=definition,
            request=normalized,
            runtime_binding_sha256=runtime_binding.runtime_binding_sha256,
            attachment=attachment,
            project_snapshot=project_snapshot,
            session_id=session_id,
            delegated_mcp_identity=delegated_mcp_identity,
        )

    async def run(
        self,
        *,
        agent_definition_id: str,
        request: str,
        settings: RuntimeSettings,
        live_opt_in: bool,
        session_id: str | None = None,
        attachment: PreparedLocalAttachment | None = None,
        project_snapshot: PreparedProjectSnapshot | None = None,
    ) -> GenericExecutionEnvelope:
        prepared = self.prepare(
            agent_definition_id=agent_definition_id,
            request=request,
            settings=settings,
            live_opt_in=live_opt_in,
            session_id=session_id,
            attachment=attachment,
            project_snapshot=project_snapshot,
        )
        if isinstance(prepared, GenericExecutionEnvelope):
            return prepared
        return await self.execute_prepared(prepared=prepared, settings=settings)

    @staticmethod
    def _require_execution_fence(prepared: PreparedGenericExecution) -> None:
        if prepared.continue_execution is not None and not prepared.continue_execution():
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.EXECUTION_CLAIM_LOST,
                "Governed execution claim is no longer active",
                retryable=False,
            )

    async def execute_prepared(
        self,
        *,
        prepared: PreparedGenericExecution,
        settings: RuntimeSettings,
    ) -> GenericExecutionEnvelope:
        definition = prepared.definition
        task_id = prepared.task_id
        run_id = prepared.run_id
        session_acquired = False
        session_item_count_before = 0
        session_context_focus: SessionContextFocusObservation | None = None
        rollback_failed_session_turn = bool(
            definition.session_mode == "sqlite-v1"
            and (definition.handoffs or definition.guardrails or definition.agent_tools or definition.mcp_servers)
        )

        async def session_compaction_sink(event_type: str, payload: dict[str, object]) -> None:
            self._store.append_event(
                run_id,
                event_type=event_type,
                source=EventSource.RUNTIME,
                payload=payload,
                payload_schema_version="okcanvas-session-compaction-lifecycle-v1",
                require_active_run=True,
            )

        async def release_failed_session_turn() -> None:
            nonlocal session_acquired
            if not session_acquired or prepared.session_id is None or self._sessions is None:
                return
            try:
                if rollback_failed_session_turn:
                    item_count = await self._sessions.rollback_to_item_count(
                        session_id=prepared.session_id,
                        expected_item_count=session_item_count_before,
                    )
                else:
                    item_count = await self._sessions.count_items(prepared.session_id)
                self._sessions.release_turn(
                    session_id=prepared.session_id,
                    run_id=run_id,
                    succeeded=False,
                    item_count=item_count,
                )
                session_acquired = False
            except Exception:
                pass

        try:
            await asyncio.sleep(0)
            if prepared.start_execution is not None:
                if not prepared.start_execution():
                    return self._preflight_failure(
                        definition.agent_id,
                        settings,
                        GenericExecutionFailure(
                            GenericExecutionErrorCode.EXECUTION_CLAIM_LOST,
                            "Governed execution claim is no longer active",
                            retryable=True,
                        ),
                        definition_version=definition.version,
                        definition_sha256=definition.definition_sha256,
                    )
            else:
                self._store.transition_task(task_id, TaskStatus.RUNNING)
                self._store.transition_run(
                    run_id,
                    RunStatus.RUNNING,
                    event_type="run.started",
                    payload={
                        "agent_definition_id": definition.agent_id,
                        "agent_definition_version": definition.version,
                    },
                    payload_schema_version="okcanvas-generic-run-started-v1",
                )
            self._require_execution_fence(prepared)
            root_invocation = self._invocations.ensure_root(
                run_id=run_id,
                agent_definition_id=definition.agent_id,
                runtime_binding_sha256=prepared.runtime_binding_sha256,
            )
            if prepared.session_id is not None:
                if self._sessions is None:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.SESSION_INTEGRITY_ERROR,
                        "SQLite Session Runtime is not configured",
                    )
                try:
                    session_record = self._sessions.acquire_turn(
                        session_id=prepared.session_id,
                        run_id=run_id,
                        definition=definition,
                        runtime_binding_sha256=prepared.runtime_binding_sha256,
                    )
                    session_acquired = True
                    session_item_count_before = session_record.item_count
                except SessionBusyError as exc:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.SESSION_BUSY,
                        "Session already has an active Turn",
                        detail_type=type(exc).__name__,
                    ) from exc
                except SessionRuntimeError as exc:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.SESSION_INTEGRITY_ERROR,
                        "Session identity or Runtime binding is invalid",
                        detail_type=type(exc).__name__,
                    ) from exc
                self._store.append_event(
                    run_id,
                    event_type="session.turn.started",
                    source=EventSource.RUNTIME,
                    payload={
                        "session_id": prepared.session_id,
                        "turn_ordinal": session_record.turn_count + 1,
                        "history_persisted_in_product_events": False,
                        "history_persisted_in_product_db": False,
                        "workspace_access": "none",
                    },
                    payload_schema_version="okcanvas-session-turn-started-v1",
                    require_active_run=True,
                )
            self._store.append_event(
                run_id,
                event_type="agent.definition.resolved",
                source=EventSource.RUNTIME,
                payload={
                    "agent_definition_id": definition.agent_id,
                    "agent_definition_version": definition.version,
                    "agent_definition_sha256": definition.definition_sha256,
                    "runtime_binding_sha256": prepared.runtime_binding_sha256,
                    "output_contract": definition.output_contract,
                    "local_tool_count": len(definition.tools),
                    "local_tool_names": list(definition.tools),
                    "mcp_server_ids": list(definition.mcp_servers),
                    "mcp_server_count": len(definition.mcp_servers),
                    "handoff_count": len(definition.handoffs),
                    "agent_tool_count": len(definition.agent_tools),
                    "orchestration_child_count": len(definition.orchestration_children),
                    "orchestration_child_ids": list(definition.orchestration_children),
                    "guardrail_count": len(definition.guardrails),
                    "guardrail_ids": list(definition.guardrails),
                    "root_invocation_id": root_invocation.invocation_id,
                    "workspace_access": root_invocation.workspace_access.value,
                    "session_mode": definition.session_mode,
                    "session_id_present": prepared.session_id is not None,
                },
                payload_schema_version="okcanvas-agent-definition-resolved-v1",
                require_active_run=True,
            )

            invocation_by_agent_id = {definition.agent_id: root_invocation.invocation_id}
            handoff_child_invocation_id: str | None = None
            handoff_parent_usage = UsageSummary()
            agent_tool_child_invocation_id: str | None = None
            agent_tool_usage_before = UsageSummary()
            agent_tool_child_usage = UsageSummary()
            orchestration_invocation_by_ordinal: dict[int, str] = {}
            orchestration_agent_by_ordinal: dict[int, str] = {}
            orchestration_terminal_ordinals: set[int] = set()
            if definition.orchestration_children:
                child_bindings = tuple(
                    (child_id, self._runtime_bindings.resolve(self._definitions.resolve(child_id)).runtime_binding_sha256)
                    for child_id in definition.orchestration_children
                )
                planned_children = self._invocations.plan_orchestration_children(
                    parent_invocation_id=root_invocation.invocation_id,
                    child_runtime_bindings=child_bindings,
                )
                for ordinal, planned in enumerate(planned_children, start=1):
                    orchestration_invocation_by_ordinal[ordinal] = planned.invocation_id
                    orchestration_agent_by_ordinal[ordinal] = planned.agent_definition_id
                    invocation_by_agent_id[planned.agent_definition_id] = planned.invocation_id
                self._store.append_event(
                    run_id,
                    event_type="orchestration.plan.bound",
                    source=EventSource.RUNTIME,
                    payload={
                        "root_invocation_id": root_invocation.invocation_id,
                        "child_invocation_ids": [item.invocation_id for item in planned_children],
                        "child_agent_ids": [item.agent_definition_id for item in planned_children],
                        "child_ordinals": [1, 2],
                        "depth": 1,
                        "workspace_access": "none",
                    },
                    payload_schema_version="okcanvas-bounded-orchestration-plan-bound-v1",
                    require_active_run=True,
                )

            async def lifecycle_sink(event: GatewayLifecycleEvent) -> None:
                nonlocal handoff_child_invocation_id, handoff_parent_usage
                nonlocal agent_tool_child_invocation_id, agent_tool_usage_before
                nonlocal agent_tool_child_usage, session_context_focus
                try:
                    self._require_execution_fence(prepared)
                    payload = dict(event.payload)
                    if event.event_type == "agent.tool.output.normalized":
                        focus_payload = payload.get("session_context_focus")
                        if isinstance(focus_payload, dict):
                            observed_focus = SessionContextFocusObservation.from_mapping(focus_payload)
                            if session_context_focus is not None and session_context_focus != observed_focus:
                                raise GenericExecutionFailure(
                                    GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                                    "One Session Turn observed conflicting context-focus evidence",
                                )
                            session_context_focus = observed_focus
                    if event.event_type.startswith("orchestration.child."):
                        ordinal = int(payload.get("ordinal", 0) or 0)
                        agent_id_value = str(payload.get("agent_id", ""))
                        invocation_id = orchestration_invocation_by_ordinal.get(ordinal)
                        if (
                            invocation_id is None
                            or orchestration_agent_by_ordinal.get(ordinal) != agent_id_value
                        ):
                            raise GenericExecutionFailure(
                                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                                "Observed orchestration child does not match the immutable plan",
                            )
                        if event.event_type == "orchestration.child.started":
                            if ordinal in orchestration_terminal_ordinals:
                                raise GenericExecutionFailure(
                                    GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                                    "Terminal orchestration child cannot restart",
                                )
                            child_record = self._invocations.begin_orchestration_child(invocation_id)
                        elif event.event_type == "orchestration.child.completed":
                            if ordinal in orchestration_terminal_ordinals:
                                raise GenericExecutionFailure(
                                    GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                                    "Orchestration child completed more than once",
                                )
                            usage = UsageSummary.model_validate(payload.get("usage", {}))
                            child_record = self._invocations.complete_invocation(
                                invocation_id=invocation_id,
                                state=InvocationState.SUCCEEDED,
                                input_tokens=usage.input_tokens,
                                output_tokens=usage.output_tokens,
                                total_tokens=usage.total_tokens,
                            )
                            orchestration_terminal_ordinals.add(ordinal)
                        elif event.event_type == "orchestration.child.failed":
                            if ordinal in orchestration_terminal_ordinals:
                                raise GenericExecutionFailure(
                                    GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                                    "Orchestration child failed after terminal state",
                                )
                            usage = UsageSummary.model_validate(payload.get("usage", {}))
                            child_record = self._invocations.complete_invocation(
                                invocation_id=invocation_id,
                                state=InvocationState.FAILED,
                                input_tokens=usage.input_tokens,
                                output_tokens=usage.output_tokens,
                                total_tokens=usage.total_tokens,
                            )
                            orchestration_terminal_ordinals.add(ordinal)
                        elif event.event_type == "orchestration.child.cancelled":
                            if ordinal in orchestration_terminal_ordinals:
                                raise GenericExecutionFailure(
                                    GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                                    "Orchestration child cancelled after terminal state",
                                )
                            usage = UsageSummary.model_validate(payload.get("usage", {}))
                            child_record = self._invocations.cancel_invocation(
                                invocation_id=invocation_id,
                                input_tokens=usage.input_tokens,
                                output_tokens=usage.output_tokens,
                                total_tokens=usage.total_tokens,
                            )
                            orchestration_terminal_ordinals.add(ordinal)
                        else:
                            child_record = self._store.get_agent_invocation(invocation_id)
                        payload.update(
                            {
                                "root_invocation_id": root_invocation.invocation_id,
                                "invocation_id": child_record.invocation_id,
                                "parent_invocation_id": child_record.parent_invocation_id,
                                "invocation_kind": child_record.invocation_kind.value,
                                "workspace_access": child_record.workspace_access.value,
                            }
                        )
                    elif event.event_type == "agent.tool.started":
                        from_agent_id = str(payload.get("from_agent_id", ""))
                        to_agent_id = str(payload.get("to_agent_id", ""))
                        if (
                            agent_tool_child_invocation_id is not None
                            or from_agent_id != definition.agent_id
                            or to_agent_id not in definition.agent_tools
                        ):
                            raise GenericExecutionFailure(
                                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                                "Observed Agent-as-Tool call does not match the immutable graph",
                            )
                        usage_payload = payload.pop("parent_usage_before", {})
                        agent_tool_usage_before = UsageSummary.model_validate(usage_payload)
                        child_definition = self._definitions.resolve(to_agent_id)
                        child_binding = self._runtime_bindings.resolve(child_definition)
                        child = self._invocations.begin_agent_tool(
                            parent_invocation_id=root_invocation.invocation_id,
                            child_agent_definition_id=to_agent_id,
                            child_runtime_binding_sha256=child_binding.runtime_binding_sha256,
                        )
                        agent_tool_child_invocation_id = child.invocation_id
                        invocation_by_agent_id[to_agent_id] = child.invocation_id
                        payload.update(
                            {
                                "from_invocation_id": root_invocation.invocation_id,
                                "to_invocation_id": child.invocation_id,
                                "child_agent_definition_version": child_definition.version,
                                "child_agent_definition_sha256": child_definition.definition_sha256,
                                "child_runtime_binding_sha256": child_binding.runtime_binding_sha256,
                                "workspace_access": child.workspace_access.value,
                                "workspace_materialized": False,
                                "run_config_inherited": False,
                            }
                        )
                    elif event.event_type == "agent.tool.completed":
                        from_agent_id = str(payload.get("from_agent_id", ""))
                        to_agent_id = str(payload.get("to_agent_id", ""))
                        if (
                            agent_tool_child_invocation_id is None
                            or from_agent_id != definition.agent_id
                            or to_agent_id not in definition.agent_tools
                        ):
                            raise GenericExecutionFailure(
                                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                                "Observed Agent-as-Tool completion does not match the active child",
                            )
                        usage_after = UsageSummary.model_validate(payload.pop("usage_after", {}))
                        child_input = usage_after.input_tokens - agent_tool_usage_before.input_tokens
                        child_output = usage_after.output_tokens - agent_tool_usage_before.output_tokens
                        child_total = usage_after.total_tokens - agent_tool_usage_before.total_tokens
                        if min(child_input, child_output, child_total) < 0:
                            raise GenericExecutionFailure(
                                GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                                "Agent-as-Tool child usage could not be partitioned",
                            )
                        agent_tool_child_usage = UsageSummary(
                            input_tokens=child_input,
                            output_tokens=child_output,
                            total_tokens=child_total,
                        )
                        child = self._invocations.complete_invocation(
                            invocation_id=agent_tool_child_invocation_id,
                            state=InvocationState.SUCCEEDED,
                            input_tokens=child_input,
                            output_tokens=child_output,
                            total_tokens=child_total,
                        )
                        payload.update(
                            {
                                "from_invocation_id": root_invocation.invocation_id,
                                "to_invocation_id": child.invocation_id,
                                "child_usage": agent_tool_child_usage.model_dump(mode="json"),
                                "workspace_access": child.workspace_access.value,
                                "workspace_materialized": False,
                            }
                        )
                    elif event.event_type == "agent.handoff":
                        from_agent_id = str(payload.get("from_agent_id", ""))
                        to_agent_id = str(payload.get("to_agent_id", ""))
                        if (
                            handoff_child_invocation_id is not None
                            or from_agent_id != definition.agent_id
                            or to_agent_id not in definition.handoffs
                        ):
                            raise GenericExecutionFailure(
                                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                                "Observed Handoff does not match the immutable Agent graph",
                            )
                        usage_payload = payload.pop("parent_usage", {})
                        handoff_parent_usage = UsageSummary.model_validate(usage_payload)
                        child_definition = self._definitions.resolve(to_agent_id)
                        child_binding = self._runtime_bindings.resolve(child_definition)
                        child = self._invocations.begin_handoff(
                            parent_invocation_id=root_invocation.invocation_id,
                            child_agent_definition_id=to_agent_id,
                            child_runtime_binding_sha256=child_binding.runtime_binding_sha256,
                            parent_input_tokens=handoff_parent_usage.input_tokens,
                            parent_output_tokens=handoff_parent_usage.output_tokens,
                            parent_total_tokens=handoff_parent_usage.total_tokens,
                        )
                        handoff_child_invocation_id = child.invocation_id
                        invocation_by_agent_id[to_agent_id] = child.invocation_id
                        payload.update(
                            {
                                "from_invocation_id": root_invocation.invocation_id,
                                "to_invocation_id": child.invocation_id,
                                "child_agent_definition_version": child_definition.version,
                                "child_agent_definition_sha256": child_definition.definition_sha256,
                                "child_runtime_binding_sha256": child_binding.runtime_binding_sha256,
                                "workspace_access": child.workspace_access.value,
                                "workspace_materialized": False,
                            }
                        )
                    agent_id = payload.get("agent_id")
                    if isinstance(agent_id, str) and agent_id in invocation_by_agent_id:
                        payload["invocation_id"] = invocation_by_agent_id[agent_id]
                    self._store.append_event(
                        run_id,
                        event_type=event.event_type,
                        source=event.source,
                        payload=payload,
                        payload_schema_version=event.payload_schema_version,
                        require_active_run=True,
                    )
                except GenericExecutionFailure:
                    raise
                except Exception as exc:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                        "SDK lifecycle Event could not be persisted",
                        detail_type=type(exc).__name__,
                    ) from exc

            gateway_kwargs = {
                "definition": definition,
                "request": prepared.request,
                "run_id": run_id,
                "settings": settings,
                "lifecycle_sink": lifecycle_sink,
            }
            if prepared.attachment is not None:
                gateway_kwargs["attachment"] = prepared.attachment
            if prepared.project_snapshot is not None:
                gateway_kwargs["project_snapshot"] = prepared.project_snapshot
            if prepared.delegated_mcp_identity is not None:
                gateway_kwargs["delegated_mcp_identity"] = prepared.delegated_mcp_identity
            if prepared.session_id is not None:
                gateway_kwargs["session_id"] = prepared.session_id
                gateway_kwargs["session_runtime"] = self._sessions
            gateway_result = await self._gateway.run(**gateway_kwargs)
            await asyncio.sleep(0)
            self._require_execution_fence(prepared)
            if handoff_child_invocation_id is not None:
                child_input = gateway_result.usage.input_tokens - handoff_parent_usage.input_tokens
                child_output = gateway_result.usage.output_tokens - handoff_parent_usage.output_tokens
                child_total = gateway_result.usage.total_tokens - handoff_parent_usage.total_tokens
                if min(child_input, child_output, child_total) < 0:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                        "Native Handoff invocation usage could not be partitioned",
                    )
                self._invocations.complete_invocation(
                    invocation_id=handoff_child_invocation_id,
                    state=InvocationState.SUCCEEDED,
                    input_tokens=child_input,
                    output_tokens=child_output,
                    total_tokens=child_total,
                )
            if agent_tool_child_invocation_id is not None:
                parent_input = gateway_result.usage.input_tokens - agent_tool_child_usage.input_tokens
                parent_output = gateway_result.usage.output_tokens - agent_tool_child_usage.output_tokens
                parent_total = gateway_result.usage.total_tokens - agent_tool_child_usage.total_tokens
                if min(parent_input, parent_output, parent_total) < 0:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                        "Agent-as-Tool parent usage could not be partitioned",
                    )
                self._invocations.complete_root(
                    run_id=run_id,
                    state=InvocationState.SUCCEEDED,
                    input_tokens=parent_input,
                    output_tokens=parent_output,
                    total_tokens=parent_total,
                )
            if definition.orchestration_children:
                if orchestration_terminal_ordinals != {1, 2}:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                        "Bounded orchestration completed without two terminal child invocations",
                    )
                self._invocations.complete_root(
                    run_id=run_id,
                    state=InvocationState.SUCCEEDED,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                )
            self._store.update_run_execution_metadata(
                run_id,
                trace_id=gateway_result.trace_id,
                input_tokens=gateway_result.usage.input_tokens,
                output_tokens=gateway_result.usage.output_tokens,
                total_tokens=gateway_result.usage.total_tokens,
            )
            if prepared.project_snapshot is not None:
                try:
                    self._require_execution_fence(prepared)
                    snapshot_artifact = self._artifact_service.create_json(
                        run_id=run_id,
                        artifact_type="agent.project-snapshot-evidence",
                        payload=prepared.project_snapshot.to_evidence_dict(),
                    )
                except GenericExecutionFailure:
                    raise
                except Exception as exc:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.ARTIFACT_WRITE_FAILED,
                        "Project snapshot evidence Artifact could not be persisted",
                        detail_type=type(exc).__name__,
                    ) from exc
                self._store.append_event(
                    run_id,
                    event_type="artifact.created",
                    source=EventSource.RUNTIME,
                    payload={
                        "artifact_id": snapshot_artifact.artifact_id,
                        "artifact_type": snapshot_artifact.artifact_type,
                        "sha256": snapshot_artifact.sha256,
                        "byte_length": snapshot_artifact.byte_length,
                        "media_type": snapshot_artifact.media_type,
                        "snapshot_sha256": prepared.project_snapshot.metadata.snapshot_sha256,
                        "raw_archive_persisted": False,
                        "host_path_persisted": False,
                    },
                    payload_schema_version="okcanvas-project-snapshot-artifact-created-v1",
                    require_active_run=True,
                )
            if prepared.attachment is not None:
                try:
                    self._require_execution_fence(prepared)
                    attachment_artifact = self._artifact_service.create_json(
                        run_id=run_id,
                        artifact_type="agent.local-attachment-evidence",
                        payload=prepared.attachment.to_evidence_dict(),
                    )
                except GenericExecutionFailure:
                    raise
                except Exception as exc:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.ARTIFACT_WRITE_FAILED,
                        "Local attachment evidence Artifact could not be persisted",
                        detail_type=type(exc).__name__,
                    ) from exc
                self._store.append_event(
                    run_id,
                    event_type="artifact.created",
                    source=EventSource.RUNTIME,
                    payload={
                        "artifact_id": attachment_artifact.artifact_id,
                        "artifact_type": attachment_artifact.artifact_type,
                        "sha256": attachment_artifact.sha256,
                        "byte_length": attachment_artifact.byte_length,
                        "media_type": attachment_artifact.media_type,
                        "attachment_content_sha256": prepared.attachment.metadata.content_sha256,
                        "attachment_media_type": prepared.attachment.metadata.media_type,
                        "attachment_byte_length": prepared.attachment.metadata.byte_length,
                        "raw_attachment_persisted": False,
                    },
                    payload_schema_version="okcanvas-local-attachment-artifact-created-v1",
                    require_active_run=True,
                )
            hosted_search_artifact = None
            if gateway_result.hosted_search_evidence is not None:
                try:
                    evidence_payload = gateway_result.hosted_search_evidence.to_artifact_dict()
                    self._require_execution_fence(prepared)
                    hosted_search_artifact = self._artifact_service.create_json(
                        run_id=run_id,
                        artifact_type="agent.hosted-search-evidence",
                        payload=evidence_payload,
                    )
                except GenericExecutionFailure:
                    raise
                except Exception as exc:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.ARTIFACT_WRITE_FAILED,
                        "Hosted Search evidence Artifact could not be persisted",
                        detail_type=type(exc).__name__,
                    ) from exc
                self._store.append_event(
                    run_id,
                    event_type="artifact.created",
                    source=EventSource.RUNTIME,
                    payload={
                        "artifact_id": hosted_search_artifact.artifact_id,
                        "artifact_type": hosted_search_artifact.artifact_type,
                        "sha256": hosted_search_artifact.sha256,
                        "byte_length": hosted_search_artifact.byte_length,
                        "media_type": hosted_search_artifact.media_type,
                        "raw_query_persisted": False,
                        "raw_content_persisted": False,
                        "provider_call_id_persisted": False,
                    },
                    payload_schema_version="okcanvas-hosted-search-artifact-created-v1",
                    require_active_run=True,
                )
            try:
                artifact_payload = serialize_output(
                    definition.output_contract, gateway_result.output
                )
                self._require_execution_fence(prepared)
                artifact = self._artifact_service.create_json(
                    run_id=run_id,
                    artifact_type="agent.final-output",
                    payload=artifact_payload,
                )
            except GenericExecutionFailure:
                raise
            except Exception as exc:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.ARTIFACT_WRITE_FAILED,
                    "Final output Artifact could not be persisted",
                    detail_type=type(exc).__name__,
                ) from exc
            self._store.append_event(
                run_id,
                event_type="artifact.created",
                source=EventSource.RUNTIME,
                payload={
                    "artifact_id": artifact.artifact_id,
                    "artifact_type": artifact.artifact_type,
                    "sha256": artifact.sha256,
                    "byte_length": artifact.byte_length,
                    "media_type": artifact.media_type,
                },
                payload_schema_version="okcanvas-artifact-created-v1",
                require_active_run=True,
            )
            if session_acquired and prepared.session_id is not None and self._sessions is not None:
                item_count = await self._sessions.count_items(prepared.session_id)
                session_record = self._sessions.release_turn(
                    session_id=prepared.session_id,
                    run_id=run_id,
                    succeeded=True,
                    item_count=item_count,
                    context_focus=session_context_focus,
                )
                session_acquired = False
                self._store.append_event(
                    run_id,
                    event_type="session.turn.completed",
                    source=EventSource.RUNTIME,
                    payload={
                        "session_id": prepared.session_id,
                        "turn_count": session_record.turn_count,
                        "item_count": session_record.item_count,
                        "history_persisted_in_product_events": False,
                        "history_persisted_in_product_db": False,
                        "context_focus_updated": session_context_focus is not None,
                        "context_focus_state": (
                            session_context_focus.state.value if session_context_focus is not None else None
                        ),
                        "context_focus_raw_tool_result_persisted": False,
                    },
                    payload_schema_version="okcanvas-session-turn-completed-v1",
                    require_active_run=True,
                )
                await self._sessions.compact_after_committed_turn(
                    session_id=prepared.session_id,
                    run_id=run_id,
                    compaction_api_key=settings.api_key,
                    compaction_event_sink=session_compaction_sink,
                )
            self._store.transition_run(
                run_id,
                RunStatus.SUCCEEDED,
                event_type="run.completed",
                source=EventSource.RUNTIME,
                payload={
                    "artifact_id": artifact.artifact_id,
                    "hosted_search_evidence_artifact_id": (
                        hosted_search_artifact.artifact_id if hosted_search_artifact else None
                    ),
                    "trace_id": gateway_result.trace_id,
                    "response_id": gateway_result.response_id,
                    "sdk_version": gateway_result.sdk_version,
                    "usage": gateway_result.usage.model_dump(mode="json"),
                },
                payload_schema_version="okcanvas-generic-run-completed-v1",
            )
            self._store.transition_task(task_id, TaskStatus.SUCCEEDED)
            self._invocations.synchronize_root_with_run(run_id)
            return GenericExecutionEnvelope(
                state="SUCCEEDED",
                task_id=task_id,
                run_id=run_id,
                agent_definition_id=definition.agent_id,
                agent_definition_version=definition.version,
                agent_definition_sha256=definition.definition_sha256,
                model=settings.model,
                live_call=True,
                trace_id=gateway_result.trace_id,
                response_id=gateway_result.response_id,
                artifact_id=artifact.artifact_id,
                artifact_sha256=artifact.sha256,
                usage=gateway_result.usage,
                result=artifact_payload,
            )
        except asyncio.CancelledError:
            await release_failed_session_turn()
            raise
        except GenericExecutionFailure as failure:
            await release_failed_session_turn()
            return self._persisted_failure(
                failure,
                settings=settings,
                definition_id=definition.agent_id,
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
                task_id=task_id,
                run_id=run_id,
            )
        except Exception as exc:
            await release_failed_session_turn()
            return self._persisted_failure(
                GenericExecutionFailure(
                    GenericExecutionErrorCode.PRODUCT_STATE_FAILED,
                    "Generic Agent execution product state failed",
                    detail_type=type(exc).__name__,
                ),
                settings=settings,
                definition_id=definition.agent_id,
                definition_version=definition.version,
                definition_sha256=definition.definition_sha256,
                task_id=task_id,
                run_id=run_id,
            )

    def _persisted_failure(
        self,
        failure: GenericExecutionFailure,
        *,
        settings: RuntimeSettings,
        definition_id: str,
        definition_version: str,
        definition_sha256: str,
        task_id: str | None,
        run_id: str | None,
    ) -> GenericExecutionEnvelope:
        if run_id is not None and failure.usage is not None:
            try:
                self._store.update_run_execution_metadata(
                    run_id,
                    trace_id=failure.trace_id,
                    input_tokens=failure.usage.input_tokens,
                    output_tokens=failure.usage.output_tokens,
                    total_tokens=failure.usage.total_tokens,
                )
            except Exception:
                pass
        if run_id is not None:
            try:
                current = self._store.get_run(run_id)
                if current.status is RunStatus.RUNNING:
                    self._store.append_event(
                        run_id,
                        event_type="agent.failed",
                        source=EventSource.RUNTIME,
                        payload={
                            "code": failure.code.value,
                            "retryable": failure.retryable,
                            "detail_type": failure.detail_type,
                            **(failure.diagnostic or {}),
                        },
                        payload_schema_version="okcanvas-agent-failed-v1",
                    )
                    self._store.transition_run(
                        run_id,
                        RunStatus.FAILED,
                        event_type="run.failed",
                        payload={
                            "code": failure.code.value,
                            "retryable": failure.retryable,
                            "detail_type": failure.detail_type,
                            **(failure.diagnostic or {}),
                        },
                        payload_schema_version="okcanvas-generic-run-failed-v1",
                    )
            except Exception:
                pass
        if task_id is not None:
            try:
                current_task = self._store.get_task(task_id)
                if current_task.status is TaskStatus.RUNNING:
                    self._store.transition_task(task_id, TaskStatus.FAILED)
            except Exception:
                pass
        if run_id is not None:
            try:
                self._invocations.synchronize_root_with_run(run_id)
            except Exception:
                pass
        return GenericExecutionEnvelope(
            state="FAILED",
            task_id=task_id,
            run_id=run_id,
            agent_definition_id=definition_id,
            agent_definition_version=definition_version,
            agent_definition_sha256=definition_sha256,
            model=settings.model,
            live_call=failure.code
            in {
                GenericExecutionErrorCode.SDK_RUN_FAILED,
                GenericExecutionErrorCode.OUTPUT_CONTRACT_INVALID,
                GenericExecutionErrorCode.ARTIFACT_WRITE_FAILED,
                GenericExecutionErrorCode.INPUT_GUARDRAIL_TRIPPED,
                GenericExecutionErrorCode.OUTPUT_GUARDRAIL_TRIPPED,
                GenericExecutionErrorCode.TOOL_INPUT_GUARDRAIL_TRIPPED,
                GenericExecutionErrorCode.TOOL_OUTPUT_GUARDRAIL_TRIPPED,
            },
            trace_id=failure.trace_id,
            usage=failure.usage or UsageSummary(),
            error=GenericExecutionError(
                code=failure.code,
                message=failure.public_message,
                retryable=failure.retryable,
                detail_type=failure.detail_type,
            ),
        )

    @staticmethod
    def _preflight_failure(
        agent_definition_id: str,
        settings: RuntimeSettings,
        failure: GenericExecutionFailure,
        *,
        definition_version: str | None = None,
        definition_sha256: str | None = None,
    ) -> GenericExecutionEnvelope:
        return GenericExecutionEnvelope(
            state="FAILED",
            agent_definition_id=agent_definition_id,
            agent_definition_version=definition_version,
            agent_definition_sha256=definition_sha256,
            model=settings.model,
            live_call=False,
            error=GenericExecutionError(
                code=failure.code,
                message=failure.public_message,
                retryable=failure.retryable,
                detail_type=failure.detail_type,
            ),
        )
