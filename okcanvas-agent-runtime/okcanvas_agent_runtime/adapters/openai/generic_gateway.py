from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.metadata
import json
from typing import Any

from pydantic import ValidationError

from okcanvas_agent_runtime.agent.definitions import AgentDefinition, AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import EXPECTED_OPENAI_AGENTS_VERSION, RuntimeSettings
from okcanvas_agent_runtime.core.contracts import CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.adapters.mcp.clients import RemoteMCPResultLimitError, create_openai_mcp_runtime
from okcanvas_agent_runtime.adapters.mcp.organization_interpretation_hints import (
    GroundedInterpretationHintContractError,
    OrganizationGroundedInterpretationContextProvider,
)
from okcanvas_agent_runtime.application.assistant_interpretation import (
    GroundedDelegationAdmission,
    GroundedDelegationContractError,
    GroupwareReadDelegationInput,
    OrganizationReadDelegationInput,
    extract_grounded_routing_context,
    extract_grounded_session_utterance,
    grounded_structured_delegation_requested,
)
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity, MCPAccessCatalog, MCPPassiveHealthRegistry
from okcanvas_agent_runtime.agent.mcp.definitions import MCPDefinitionError, MCPServerCatalog
from okcanvas_agent_runtime.agent.model.retry import ModelRetryPolicyCatalog, ModelRetryPolicyError, build_sdk_model_retry_settings
from okcanvas_agent_runtime.agent.model.routing import ModelRoutingError, ModelRoutingPolicyCatalog, PinnedOpenAIResponsesProvider
from okcanvas_agent_runtime.agent.model.reasoning_evidence import ReasoningEvidencePolicyCatalog, ReasoningEvidencePolicyError, build_sdk_reasoning_model_settings_kwargs, count_reasoning_items
from okcanvas_agent_runtime.agent.model.response_storage import ResponseStoragePolicyCatalog, ResponseStoragePolicyError, build_sdk_response_storage_model_settings_kwargs
from okcanvas_agent_runtime.agent.model.provider_identity import ProviderIdentifierPolicyCatalog, ProviderIdentifierPolicyError, minimize_provider_identifier, provider_identifier_presence
from okcanvas_agent_runtime.agent.tools.function import FunctionToolApprovalMode, FunctionToolDefinitionContractError, FunctionToolDefinitionIntegrityError, FunctionToolDefinitionNotFoundError, FunctionToolRuntimeCatalog, build_sdk_function_tool, invocation_prompt
from okcanvas_agent_runtime.adapters.workspace.tool_inspection import project_readonly_inspect, sandbox_project_readonly_inspect
from okcanvas_agent_runtime.agent.tools.function.models import SandboxProjectReadonlyInspectOutput
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.agent.guardrails import GuardrailKind, GuardrailRuntimeCatalog, attach_sdk_tool_guardrails, build_sdk_agent_guardrails
from okcanvas_agent_runtime.agent.subagents.handoffs import NativeHandoffContractError, NativeHandoffPolicyCatalog, build_sdk_native_handoff, validate_native_handoff_definitions, validate_sqlite_session_handoff_definitions
from okcanvas_agent_runtime.agent.subagents.agent_tools import AgentToolContractError, AgentToolPolicyCatalog, agent_tool_name, bounded_structured_child_result, build_sdk_agent_tool, validate_agent_tool_definitions, validate_sqlite_session_agent_tool_definitions
from okcanvas_agent_runtime.adapters.openai.runtime.sdk_readiness import inspect_sdk
from okcanvas_agent_runtime.adapters.sandbox.docker.errors import SandboxDockerError
from okcanvas_agent_runtime.application.ports import SessionRuntimePort
from okcanvas_agent_runtime.domain.attachments.models import PreparedLocalAttachment
from okcanvas_agent_runtime.domain.project_snapshots import materialize_project_snapshot
from okcanvas_agent_runtime.domain.project_snapshots.models import PreparedProjectSnapshot
from okcanvas_agent_runtime.domain.attachments.model_policy import MultimodalModelPolicyCatalog
from okcanvas_agent_runtime.application.orchestration import BoundedOrchestrationPolicyCatalog
from okcanvas_agent_runtime.application.assistant_routing.cross_domain_session import (
    CrossDomainSessionContractError,
    CrossDomainSessionDelegationCatalog,
)
from okcanvas_agent_runtime.application.groupware_read import (
    groupware_named_tool_choice,
)
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationContextSessionDelegationCatalog,
    organization_context_named_tool_choice,
    requires_organization_context_session_delegation,
)
from okcanvas_agent_runtime.agent.tools.hosted_search import HostedWebSearchEvidenceError, HostedWebSearchPolicyError, HostedWebSearchPolicyCatalog, build_sdk_web_search_tool, extract_hosted_web_search_evidence, hosted_web_search_model_settings_kwargs
from okcanvas_agent_runtime.application.orchestration.openai_runtime import run_openai_bounded_orchestration
from okcanvas_agent_runtime.agent.skills import resolve_effective_instructions
from okcanvas_agent_runtime.agent.model.trace_export import TraceExportPolicyCatalog, TraceExportPolicyError, build_sdk_trace_run_config_kwargs
from okcanvas_agent_runtime.adapters.streaming import InMemoryNativeSDKStreamBroker, adapt_sdk_stream_event

from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionErrorCode, GenericGatewayRunResult, GatewayLifecycleEvent
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.application.execution.gateway import LifecycleSink
from okcanvas_agent_runtime.application.execution.output_registry import normalize_output, resolve_output_contract
from okcanvas_agent_runtime.application.execution.sandbox_answer_completeness import assess_sandbox_answer_completeness, complete_sandbox_answer_from_evidence, find_sandbox_tool_output


def _nested_int(value: Any, attribute: str) -> int:
    nested = getattr(value, attribute, None)
    return int(nested or 0)


def _usage_summary(usage: Any) -> UsageSummary:
    return UsageSummary(
        requests=int(getattr(usage, "requests", 0) or 0),
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        cached_input_tokens=_nested_int(
            getattr(usage, "input_tokens_details", None), "cached_tokens"
        ),
        reasoning_tokens=_nested_int(
            getattr(usage, "output_tokens_details", None), "reasoning_tokens"
        ),
    )


def _add_usage(left: UsageSummary, right: UsageSummary) -> UsageSummary:
    return UsageSummary(
        requests=left.requests + right.requests,
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        total_tokens=left.total_tokens + right.total_tokens,
        cached_input_tokens=left.cached_input_tokens + right.cached_input_tokens,
        reasoning_tokens=left.reasoning_tokens + right.reasoning_tokens,
    )


def _tool_identity(tool: Any, context: Any) -> tuple[str, str | None, bool]:
    name = str(getattr(context, "tool_name", None) or getattr(tool, "name", "unknown"))
    origin = getattr(tool, "_tool_origin", None)
    server_name = getattr(origin, "mcp_server_name", None)
    call_id_present = bool(getattr(context, "tool_call_id", None))
    return name, str(server_name) if server_name else None, call_id_present


def _tool_origin_type(tool: Any) -> str:
    origin = getattr(tool, "_tool_origin", None)
    value = getattr(origin, "type", None)
    return str(getattr(value, "value", value) or "")


def _safe_model_output_shape(response: Any) -> dict[str, int]:
    """Return content-free provider output item counts for Live diagnostics."""

    counts = {"message": 0, "function_call": 0, "reasoning": 0, "other": 0}
    for item in tuple(getattr(response, "output", ()) or ()):
        kind = str(getattr(item, "type", "") or "").strip().lower()
        if kind == "message":
            counts["message"] += 1
        elif kind == "function_call":
            counts["function_call"] += 1
        elif kind == "reasoning":
            counts["reasoning"] += 1
        else:
            counts["other"] += 1
    return counts


def _safe_model_behavior_failure_diagnostic(exc: Exception) -> dict[str, object] | None:
    """Classify SDK model-behavior failures without persisting model/tool payload text."""

    if type(exc).__name__ != "ModelBehaviorError":
        return None
    message = str(exc)
    if message.startswith("Invalid JSON input for tool "):
        category = (
            "TOOL_ARGUMENT_SCHEMA_INVALID"
            if "validation error" in message.lower()
            else "TOOL_ARGUMENT_JSON_INVALID"
        )
    elif message.startswith("Failed to serialize structured tool input for "):
        category = "TOOL_ARGUMENT_SERIALIZATION_FAILED"
    elif message == "Agent tool called with invalid input":
        category = "TOOL_INPUT_BUILDER_INVALID"
    elif message.startswith("Tool ") and " not found in agent " in message:
        category = "UNKNOWN_TOOL_CALL"
    elif message.startswith("Invalid JSON when parsing "):
        category = "STRUCTURED_FINAL_OUTPUT_INVALID"
    elif message == "Model returned no final output for the structured output type.":
        category = "STRUCTURED_FINAL_OUTPUT_MISSING"
    elif message == "Model did not produce a final response!":
        category = "MODEL_FINAL_RESPONSE_MISSING"
    else:
        category = "MODEL_BEHAVIOR_OTHER"
    return {
        "detail_type": "ModelBehaviorError",
        "model_behavior_category": category,
        "raw_model_output_persisted": False,
        "raw_tool_arguments_persisted": False,
        "raw_error_message_persisted": False,
    }


def _exception_chain(exc: BaseException) -> tuple[BaseException, ...]:
    pending: list[BaseException] = [exc]
    ordered: list[BaseException] = []
    seen: set[int] = set()
    while pending:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        ordered.append(current)
        nested = getattr(current, "exceptions", None)
        if isinstance(nested, (list, tuple)):
            pending.extend(item for item in nested if isinstance(item, BaseException))
        cause = getattr(current, "__cause__", None)
        context = getattr(current, "__context__", None)
        if isinstance(cause, BaseException):
            pending.append(cause)
        if isinstance(context, BaseException):
            pending.append(context)
    return tuple(ordered)


def _safe_mcp_failure_diagnostic(
    exc: BaseException, active_mcp_tool: dict[str, object] | None
) -> tuple[dict[str, object] | None, bool, str]:
    chain = _exception_chain(exc)
    limit_error = next((item for item in chain if isinstance(item, RemoteMCPResultLimitError)), None)
    if isinstance(limit_error, RemoteMCPResultLimitError):
        return ({
            "failure_stage": "mcp_tool_call",
            "failure_category": "MCP_RESULT_LIMIT_EXCEEDED",
            "server_id": limit_error.server_id,
            "tool_name": str((active_mcp_tool or {}).get("tool_name") or "unknown"),
            "observed_chars": limit_error.observed_chars,
            "max_result_chars": limit_error.max_result_chars,
            "tool_arguments_persisted": False,
            "tool_result_persisted": False,
            "raw_error_persisted": False,
        }, False, type(limit_error).__name__)
    if active_mcp_tool is None:
        return None, True, type(exc).__name__
    inner = next((item for item in chain if type(item).__name__ != "AgentsException"), exc)
    return ({
        "failure_stage": "mcp_tool_call",
        "failure_category": "MCP_TOOL_EXECUTION_FAILED",
        "server_id": str(active_mcp_tool.get("server_id") or "unknown"),
        "tool_name": str(active_mcp_tool.get("tool_name") or "unknown"),
        "detail_type": type(inner).__name__,
        "tool_arguments_persisted": False,
        "tool_result_persisted": False,
        "raw_error_persisted": False,
    }, True, type(inner).__name__)


def _safe_structured_output_failure_diagnostic(
    exc: BaseException, *, output_contract: str, agent_id: str
) -> dict[str, object]:
    chain = _exception_chain(exc)
    validation = next((item for item in chain if isinstance(item, ValidationError)), None)
    validation_errors: list[dict[str, object]] = []
    if isinstance(validation, ValidationError):
        for item in validation.errors(
            include_url=False, include_context=False, include_input=False
        )[:20]:
            location = item.get("loc", ())
            validation_errors.append({
                "location": [str(part) for part in location],
                "type": str(item.get("type") or "unknown"),
            })
        category = "PYDANTIC_OUTPUT_VALIDATION_FAILED"
    elif any(type(item).__name__ == "ModelBehaviorError" for item in chain):
        category = "SDK_MODEL_BEHAVIOR_ERROR"
    else:
        category = "NESTED_OUTPUT_NORMALIZATION_FAILED"
    detail = next(
        (item for item in chain if type(item).__name__ not in {"AgentsException", "ExceptionGroup"}),
        exc,
    )
    normalization_error_category = next(
        (
            str(value)
            for item in chain
            if isinstance((value := getattr(item, "safe_category", None)), str) and value
        ),
        None,
    )
    return {
        "failure_stage": "child_structured_output",
        "failure_category": category,
        "agent_id": agent_id,
        "output_contract": output_contract,
        "detail_type": type(detail).__name__,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
        "normalization_error_category": normalization_error_category,
        "model_output_persisted": False,
        "tool_arguments_persisted": False,
        "tool_result_persisted": False,
        "raw_error_persisted": False,
    }


def _inject_grounded_interpretation_context(model_data: Any, context_text: str) -> Any:
    """Add turn-local grounded context to the model payload without persisting it to Session history.

    The hint payload is deliberately a user-role data item rather than system instructions. Database/SOT
    strings are model context data and must never gain instruction authority. The SDK persists the original
    caller input, not call_model_input_filter additions, so this item remains turn-local.
    """

    context_item = {
        "role": "user",
        "content": [{"type": "input_text", "text": context_text}],
    }
    items = list(model_data.input)
    insertion_index = 0
    for index in range(len(items) - 1, -1, -1):
        item = items[index]
        if isinstance(item, dict) and item.get("role") == "user":
            insertion_index = index
            break
    items.insert(insertion_index, context_item)
    return type(model_data)(input=items, instructions=model_data.instructions)


class OpenAIGenericAgentGateway:
    def __init__(
        self,
        *,
        native_stream_broker: InMemoryNativeSDKStreamBroker | None = None,
        readonly_workspace_root: str | None = None,
        sandbox_readonly_image: str | None = None,
        sandbox_temporary_parent: str | None = None,
    ) -> None:
        self._native_stream_broker = native_stream_broker
        self._readonly_workspace_root = readonly_workspace_root
        self._sandbox_readonly_image = sandbox_readonly_image
        self._sandbox_temporary_parent = sandbox_temporary_parent

    async def run(
        self,
        *,
        definition: AgentDefinition,
        request: str,
        run_id: str,
        settings: RuntimeSettings,
        lifecycle_sink: LifecycleSink,
        session_id: str | None = None,
        session_runtime: SessionRuntimePort | None = None,
        attachment: PreparedLocalAttachment | None = None,
        project_snapshot: PreparedProjectSnapshot | None = None,
        delegated_mcp_identity: DelegatedMCPIdentity | None = None,
    ) -> GenericGatewayRunResult:
        readiness = inspect_sdk(settings)
        if not readiness.ready:
            issue = readiness.issues[0]
            mapping = {
                "SDK_NOT_INSTALLED": GenericExecutionErrorCode.SDK_NOT_INSTALLED,
                "SDK_VERSION_MISMATCH": GenericExecutionErrorCode.SDK_VERSION_MISMATCH,
                "API_KEY_MISSING": GenericExecutionErrorCode.API_KEY_MISSING,
                "MODEL_NOT_CONFIGURED": GenericExecutionErrorCode.MODEL_NOT_CONFIGURED,
            }
            raise GenericExecutionFailure(mapping[issue.code.value], issue.message)
        if definition.input_mode == "local-attachment-v1":
            if attachment is None:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.INVALID_REQUEST,
                    "Local attachment Agent requires one validated attachment",
                )
            try:
                MultimodalModelPolicyCatalog(definition.definition_path.parents[3]).resolve().validate_model(settings.model)
            except Exception as exc:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.MODEL_ROUTE_DENIED,
                    "Selected model is not allowed for local PDF/image input",
                    detail_type=type(exc).__name__,
                ) from exc
        elif attachment is not None:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Text-only Agent cannot receive a local attachment",
            )
        if project_snapshot is not None and definition.workspace_access != "sandbox-readonly-v1":
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Project snapshot is valid only for a sandbox-readonly Agent",
            )

        if definition.orchestration_children:
            if session_id is not None or session_runtime is not None:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Bounded orchestration cannot use an SDK Session",
                )
            try:
                orchestration_policy = BoundedOrchestrationPolicyCatalog(
                    definition.definition_path.parents[3]
                ).resolve()
            except Exception as exc:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Bounded orchestration policy could not be resolved",
                    detail_type=type(exc).__name__,
                ) from exc
            return await run_openai_bounded_orchestration(
                root_definition=definition,
                request=request,
                run_id=run_id,
                settings=settings,
                lifecycle_sink=lifecycle_sink,
                policy=orchestration_policy,
            )

        if definition.session_mode == "sqlite-v1":
            if session_id is None or session_runtime is None:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.SESSION_INTEGRITY_ERROR,
                    "SQLite Session identity and Runtime are required",
                )
            session_handoff_mode = (
                len(definition.handoffs) == 1
                and not definition.tools
                and not definition.mcp_servers
                and not definition.agent_tools
                and not definition.guardrails
                and definition.workspace_access == "none"
            )
            session_guardrail_mode = (
                bool(definition.guardrails)
                and not definition.tools
                and not definition.handoffs
                and not definition.mcp_servers
                and not definition.agent_tools
                and definition.workspace_access == "none"
            )
            session_mcp_mode = (
                len(definition.mcp_servers) == 1
                and not definition.tools
                and not definition.handoffs
                and not definition.agent_tools
                and not definition.guardrails
                and definition.workspace_access == "none"
            )
            session_agent_tool_mode = (
                len(definition.agent_tools) == 1
                and not definition.tools
                and not definition.handoffs
                and not definition.mcp_servers
                and not definition.guardrails
                and definition.workspace_access == "none"
            )
            session_cross_domain_agent_tool_mode = (
                definition.agent_id == "organization-assistant-session-agent"
                and definition.agent_tools == ("groupware-read-agent", "organization-context-read-agent")
                and not definition.tools
                and not definition.handoffs
                and not definition.mcp_servers
                and not definition.guardrails
                and definition.workspace_access == "none"
            )
            if definition.tools or (definition.mcp_servers and not session_mcp_mode) or (
                definition.agent_tools and not (session_agent_tool_mode or session_cross_domain_agent_tool_mode)
            ) or (definition.handoffs and not session_handoff_mode) or (
                definition.guardrails and not session_guardrail_mode
            ):
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "SQLite Session composition is outside the STEP043, STEP046, STEP047, STEP048, STEP049, or STEP050 boundary",
                )
        elif definition.session_mode != "disabled" or session_id is not None:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Session identity does not match the Agent Session mode",
            )

        assert settings.model is not None
        assert settings.api_key is not None
        class _UnusedInputGuardrailTripwireTriggered(Exception):
            pass

        class _UnusedOutputGuardrailTripwireTriggered(Exception):
            pass

        class _UnusedToolInputGuardrailTripwireTriggered(Exception):
            pass

        class _UnusedToolOutputGuardrailTripwireTriggered(Exception):
            pass

        InputGuardrailTripwireTriggered = _UnusedInputGuardrailTripwireTriggered
        OutputGuardrailTripwireTriggered = _UnusedOutputGuardrailTripwireTriggered
        ToolInputGuardrailTripwireTriggered = _UnusedToolInputGuardrailTripwireTriggered
        ToolOutputGuardrailTripwireTriggered = _UnusedToolOutputGuardrailTripwireTriggered
        try:
            from agents import Agent, ModelSettings, RunConfig, RunHooks, Runner, gen_trace_id, set_default_openai_key
        except (ImportError, ModuleNotFoundError) as exc:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.SDK_NOT_INSTALLED,
                f"openai-agents=={EXPECTED_OPENAI_AGENTS_VERSION} is not installed",
                detail_type=type(exc).__name__,
            ) from exc

        project_root = definition.definition_path.parents[3]
        groupware_session_binding = None
        organization_context_session_binding = None
        cross_domain_session_binding = None
        cross_domain_target = None
        delegated_route_required = False
        if definition.agent_id == "organization-assistant-session-agent":
            try:
                cross_domain_session_binding = CrossDomainSessionDelegationCatalog(project_root).resolve(
                    definition
                )
                cross_domain_target = cross_domain_session_binding.target_for_request(request)
                delegated_route_required = cross_domain_target is not None
                if cross_domain_target is not None:
                    if cross_domain_target.domain == "GROUPWARE":
                        groupware_session_binding = cross_domain_target
                    elif cross_domain_target.domain == "ORGANIZATION_CONTEXT":
                        organization_context_session_binding = cross_domain_target
                    else:
                        raise CrossDomainSessionContractError("Unsupported selected cross-domain target")
            except Exception as exc:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Cross-domain Session delegation contract is invalid",
                    detail_type=type(exc).__name__,
                ) from exc
        elif definition.agent_id == "organization-context-session-agent":
            try:
                organization_context_session_binding = (
                    OrganizationContextSessionDelegationCatalog(project_root).resolve(definition)
                )
                delegated_route_required = requires_organization_context_session_delegation(request)
            except Exception as exc:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Organization Context Session delegation contract is invalid",
                    detail_type=type(exc).__name__,
                ) from exc
        delegated_session_binding = (
            groupware_session_binding or organization_context_session_binding
        )
        if delegated_route_required and delegated_mcp_identity is None:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Delegated read Session requires a protected delegated identity",
            )
        grounded_interpretation_context_text: str | None = None
        grounded_interpretation_utterance: str | None = None
        grounded_session_focus = None
        grounded_structured_delegation_enabled = False
        if definition.agent_id == "organization-assistant-session-agent":
            routing_context = extract_grounded_routing_context(request)
            utterance = extract_grounded_session_utterance(request)
            structured_delegation_requested = grounded_structured_delegation_requested(routing_context)
            if utterance is not None and session_runtime is not None and session_id is not None:
                try:
                    grounded_session_focus = session_runtime.get_context_focus(session_id)
                    provider = OrganizationGroundedInterpretationContextProvider(project_root)
                    grounded_context = await provider.build(
                        utterance=utterance,
                        delegated_identity=delegated_mcp_identity,
                        session_focus=grounded_session_focus,
                    )
                    grounded_interpretation_utterance = utterance
                    grounded_structured_delegation_enabled = (
                        structured_delegation_requested and cross_domain_session_binding is not None
                    )
                    grounded_interpretation_context_text = grounded_context.to_model_context_text()
                    await lifecycle_sink(
                        GatewayLifecycleEvent(
                            "interpretation.context.prepared",
                            {
                                "schema_version": "okcanvas-grounded-interpretation-context-v1",
                                "hint_state": grounded_context.organization_hints.state.value,
                                "hint_diagnostic_code": grounded_context.organization_hints.diagnostic_code,
                                "delegated_identity_present": delegated_mcp_identity is not None,
                                "capability_availability": {
                                    item.capability_id: item.available
                                    for item in grounded_context.capabilities
                                },
                                "entity_hint_state": grounded_context.organization_hints.entity_state.value,
                                "term_hint_state": grounded_context.organization_hints.term_state.value,
                                "entity_hint_count": len(grounded_context.organization_hints.entities),
                                "term_hint_count": len(grounded_context.organization_hints.terms),
                                "catalog_revision_consistent": (
                                    grounded_context.organization_hints.catalog_revision_consistent
                                ),
                                "hint_content_persisted": False,
                                "stable_entity_ids_exposed_to_model": False,
                                "raw_tool_results_persisted": False,
                                "authoritative_for_execution": False,
                            },
                            payload_schema_version="okcanvas-grounded-interpretation-context-prepared-v1",
                            source=EventSource.RUNTIME,
                        )
                    )
                except GroundedInterpretationHintContractError as exc:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Grounded interpretation hint contract is invalid",
                        detail_type=type(exc).__name__,
                    ) from exc
        try:
            model_route = ModelRoutingPolicyCatalog(project_root).resolve_model(settings.model)
        except ModelRoutingError as exc:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.MODEL_ROUTE_DENIED,
                "Selected model is outside the immutable Runtime route",
                detail_type=type(exc).__name__,
            ) from exc
        try:
            model_retry_policy = ModelRetryPolicyCatalog(project_root).resolve()
            model_retry_settings = build_sdk_model_retry_settings(model_retry_policy)
            reasoning_evidence_policy = ReasoningEvidencePolicyCatalog(project_root).resolve()
            reasoning_settings = build_sdk_reasoning_model_settings_kwargs(
                reasoning_evidence_policy
            )
            response_storage_policy = ResponseStoragePolicyCatalog(project_root).resolve()
            response_storage_settings = build_sdk_response_storage_model_settings_kwargs(
                response_storage_policy
            )
            provider_identifier_policy = ProviderIdentifierPolicyCatalog(project_root).resolve()
            trace_export_policy = TraceExportPolicyCatalog(project_root).resolve()
            trace_run_config_settings = build_sdk_trace_run_config_kwargs(trace_export_policy)
            hosted_search_policy = (
                HostedWebSearchPolicyCatalog(project_root).resolve()
                if definition.hosted_tools
                else None
            )
        except (
            ModelRetryPolicyError,
            ReasoningEvidencePolicyError,
            ResponseStoragePolicyError,
            ProviderIdentifierPolicyError,
            TraceExportPolicyError,
            HostedWebSearchPolicyError,
        ) as exc:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.MODEL_ROUTE_DENIED,
                "Model request policy is outside the immutable Runtime route",
                detail_type=type(exc).__name__,
            ) from exc
        model_provider = PinnedOpenAIResponsesProvider(
            route=model_route,
            retry_policy=model_retry_policy,
            api_key=settings.api_key,
        )
        handoff_policy = None
        child_definition = None
        if definition.handoffs:
            try:
                handoff_policy = NativeHandoffPolicyCatalog(project_root).resolve()
                if len(definition.handoffs) != 1:
                    raise NativeHandoffContractError(
                        "STEP041 permits exactly one declared Handoff target"
                    )
                child_definition = AgentDefinitionCatalog(project_root).resolve(
                    definition.handoffs[0]
                )
                if definition.session_mode == "sqlite-v1":
                    validate_sqlite_session_handoff_definitions(
                        parent=definition, child=child_definition, policy=handoff_policy
                    )
                else:
                    validate_native_handoff_definitions(
                        parent=definition, child=child_definition, policy=handoff_policy
                    )
            except Exception as exc:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Native Handoff definition or policy is invalid",
                    detail_type=type(exc).__name__,
                ) from exc
        agent_tool_policy = None
        agent_tool_child_definition = None
        grounded_agent_tool_bindings = ()
        if definition.agent_tools:
            try:
                if grounded_structured_delegation_enabled:
                    if cross_domain_session_binding is None:
                        raise AgentToolContractError("Grounded structured delegation has no cross-domain binding")
                    grounded_agent_tool_bindings = cross_domain_session_binding.targets
                elif delegated_session_binding is not None:
                    agent_tool_policy = delegated_session_binding.policy
                    agent_tool_child_definition = delegated_session_binding.child
                elif cross_domain_session_binding is not None:
                    # A cross-domain Session Root exposes no child Tool on legacy language-only Turns.
                    agent_tool_policy = None
                    agent_tool_child_definition = None
                else:
                    agent_tool_policy = AgentToolPolicyCatalog(project_root).resolve()
                    if len(definition.agent_tools) != 1:
                        raise AgentToolContractError(
                            "STEP042 permits exactly one declared Agent-as-Tool target"
                        )
                    agent_tool_child_definition = AgentDefinitionCatalog(project_root).resolve(
                        definition.agent_tools[0]
                    )
                    if definition.session_mode == "sqlite-v1":
                        validate_sqlite_session_agent_tool_definitions(
                            parent=definition,
                            child=agent_tool_child_definition,
                            policy=agent_tool_policy,
                        )
                    else:
                        validate_agent_tool_definitions(
                            parent=definition,
                            child=agent_tool_child_definition,
                            policy=agent_tool_policy,
                        )
            except Exception as exc:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Agent-as-Tool definition or policy is invalid",
                    detail_type=type(exc).__name__,
                ) from exc
        try:
            mcp_catalog = MCPServerCatalog(project_root)
            mcp_definitions = mcp_catalog.resolve_many(definition.mcp_servers)
            agent_tool_mcp_definitions = (
                mcp_catalog.resolve_many(agent_tool_child_definition.mcp_servers)
                if (not grounded_structured_delegation_enabled)
                and delegated_session_binding is not None and delegated_route_required
                and agent_tool_child_definition is not None
                else ()
            )
            grounded_agent_tool_mcp_definitions = (
                tuple(mcp_catalog.resolve(binding.mcp_server_id) for binding in grounded_agent_tool_bindings)
                if grounded_agent_tool_bindings
                else ()
            )
        except MCPDefinitionError as exc:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.MCP_CONFIGURATION_INVALID,
                "Agent MCP configuration could not be resolved",
                detail_type=type(exc).__name__,
            ) from exc
        try:
            function_tool_runtimes = FunctionToolRuntimeCatalog(project_root).resolve_many(
                definition.tools
            )
        except (
            FunctionToolDefinitionContractError,
            FunctionToolDefinitionIntegrityError,
            FunctionToolDefinitionNotFoundError,
        ) as exc:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.FUNCTION_TOOL_CONFIGURATION_INVALID,
                "Agent Function Tool configuration could not be resolved",
                detail_type=type(exc).__name__,
            ) from exc
        try:
            guardrail_runtimes = GuardrailRuntimeCatalog(project_root).resolve_many(
                definition.guardrails
            )
        except Exception as exc:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Agent Guardrail configuration could not be resolved",
                detail_type=type(exc).__name__,
            ) from exc
        if guardrail_runtimes:
            try:
                from agents import InputGuardrailTripwireTriggered as _InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered as _OutputGuardrailTripwireTriggered, ToolInputGuardrailTripwireTriggered as _ToolInputGuardrailTripwireTriggered, ToolOutputGuardrailTripwireTriggered as _ToolOutputGuardrailTripwireTriggered
            except (ImportError, ModuleNotFoundError) as exc:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.SDK_NOT_INSTALLED,
                    f"openai-agents=={EXPECTED_OPENAI_AGENTS_VERSION} Guardrail API is unavailable",
                    detail_type=type(exc).__name__,
                ) from exc
            InputGuardrailTripwireTriggered = _InputGuardrailTripwireTriggered
            OutputGuardrailTripwireTriggered = _OutputGuardrailTripwireTriggered
            ToolInputGuardrailTripwireTriggered = _ToolInputGuardrailTripwireTriggered
            ToolOutputGuardrailTripwireTriggered = _ToolOutputGuardrailTripwireTriggered

        session_guardrail_mode = bool(
            guardrail_runtimes
            and definition.session_mode == "sqlite-v1"
            and not definition.handoffs
            and not definition.agent_tools
            and not mcp_definitions
            and not function_tool_runtimes
            and all(item.kind in {GuardrailKind.INPUT, GuardrailKind.OUTPUT} for item in guardrail_runtimes)
        )
        if guardrail_runtimes and (
            definition.handoffs
            or definition.agent_tools
            or mcp_definitions
            or (definition.session_mode != "disabled" and not session_guardrail_mode)
        ):
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Guardrails may use only the STEP044 isolated path or STEP048 SQLite Session language path",
            )
        tool_guardrails_by_tool: dict[str, list[Any]] = {}
        for guardrail_runtime in guardrail_runtimes:
            if guardrail_runtime.kind in {GuardrailKind.TOOL_INPUT, GuardrailKind.TOOL_OUTPUT}:
                if not guardrail_runtime.tool_id:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Tool Guardrail has no immutable Tool target",
                    )
                tool_guardrails_by_tool.setdefault(guardrail_runtime.tool_id, []).append(
                    guardrail_runtime
                )
        if set(tool_guardrails_by_tool) - {item.tool_id for item in function_tool_runtimes}:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Tool Guardrail target is not present in the Agent Tool graph",
            )
        if definition.handoffs and (
            definition.agent_tools or function_tool_runtimes or mcp_definitions
        ):
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "STEP041 does not mix Handoff with Agent-as-Tool, MCP, or local Function Tools",
            )
        if definition.agent_tools and (
            definition.handoffs or function_tool_runtimes or mcp_definitions
        ):
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "STEP042 does not mix Agent-as-Tool with Handoff, MCP, or local Function Tools",
            )
        if function_tool_runtimes and mcp_definitions:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "P0 Runtime does not mix MCP and local Function Tools",
            )
        if any(
            item.approval_mode is FunctionToolApprovalMode.ALWAYS
            for item in function_tool_runtimes
        ):
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Approval-required Function Tools must use the governed approval path",
            )
        if len(function_tool_runtimes) > 1:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "P0 generic Function Tool execution permits exactly one Tool",
            )
        if definition.hosted_tools:
            if (
                hosted_search_policy is None
                or definition.hosted_tools != (hosted_search_policy.tool_id,)
                or definition.session_mode != "disabled"
                or definition.max_turns != hosted_search_policy.max_turns
                or definition.output_contract != "HostedWebSearchResult"
                or function_tool_runtimes
                or mcp_definitions
                or definition.handoffs
                or definition.agent_tools
                or definition.orchestration_children
                or guardrail_runtimes
                or definition.workspace_access != "none"
            ):
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.HOSTED_SEARCH_POLICY_VIOLATION,
                    "Hosted Web Search Agent is outside the isolated STEP067 policy",
                )

        output_contract = resolve_output_contract(definition.output_contract)
        output_type = output_contract.output_type
        agent_tool_output_contract = (
            resolve_output_contract(agent_tool_child_definition.output_contract)
            if agent_tool_child_definition is not None
            else None
        )
        agent_tool_output_type = (
            agent_tool_output_contract.output_type
            if agent_tool_output_contract is not None
            else None
        )
        grounded_output_contracts = {
            binding.child.agent_id: resolve_output_contract(binding.child.output_contract)
            for binding in grounded_agent_tool_bindings
        }
        trace_id = gen_trace_id()
        set_default_openai_key(settings.api_key)
        allowed_server_ids = frozenset(
            (
                *definition.mcp_servers,
                *(item.server_id for item in agent_tool_mcp_definitions),
                *(item.server_id for item in grounded_agent_tool_mcp_definitions),
            )
        )
        local_tools = {item.tool_id: item for item in function_tool_runtimes}
        selected_model_settings: dict[str, object] = {
            **reasoning_settings,
            **response_storage_settings,
        }
        if hosted_search_policy is not None:
            selected_model_settings.update(
                hosted_web_search_model_settings_kwargs(hosted_search_policy)
            )

        sdk_definition_by_object: dict[int, AgentDefinition] = {}
        handoff_count = 0
        agent_tool_count = 0
        grounded_agent_tool_request_count = 0
        active_mcp_tool: dict[str, object] | None = None
        agent_tool_completed = False
        admitted_agent_tool_definition = None
        expected_agent_tool_name = (
            agent_tool_name(agent_tool_child_definition)
            if agent_tool_child_definition is not None
            else None
        )
        grounded_agent_tool_by_name = {
            agent_tool_name(binding.child): binding for binding in grounded_agent_tool_bindings
        }
        grounded_mcp_definition_by_agent = {
            binding.child.agent_id: mcp_definition
            for binding, mcp_definition in zip(
                grounded_agent_tool_bindings, grounded_agent_tool_mcp_definitions, strict=True
            )
        }
        grounded_admission_lock = asyncio.Lock()
        grounded_admitted_request_by_agent: dict[str, str] = {}
        grounded_connected_servers: dict[str, Any] = {}

        def definition_for_sdk_agent(agent: Any) -> AgentDefinition:
            resolved = sdk_definition_by_object.get(id(agent))
            if resolved is None:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "SDK emitted an Agent outside the immutable Runtime graph",
                )
            return resolved

        guardrail_by_id = {item.guardrail_id: item for item in guardrail_runtimes}

        async def raise_guardrail_failure(exc: BaseException) -> None:
            if isinstance(exc, InputGuardrailTripwireTriggered):
                kind = GuardrailKind.INPUT
                guardrail_id = exc.guardrail_result.guardrail.get_name()
                code = GenericExecutionErrorCode.INPUT_GUARDRAIL_TRIPPED
            elif isinstance(exc, OutputGuardrailTripwireTriggered):
                kind = GuardrailKind.OUTPUT
                guardrail_id = exc.guardrail_result.guardrail.get_name()
                code = GenericExecutionErrorCode.OUTPUT_GUARDRAIL_TRIPPED
            elif isinstance(exc, ToolInputGuardrailTripwireTriggered):
                kind = GuardrailKind.TOOL_INPUT
                guardrail_id = exc.guardrail.get_name()
                code = GenericExecutionErrorCode.TOOL_INPUT_GUARDRAIL_TRIPPED
            elif isinstance(exc, ToolOutputGuardrailTripwireTriggered):
                kind = GuardrailKind.TOOL_OUTPUT
                guardrail_id = exc.guardrail.get_name()
                code = GenericExecutionErrorCode.TOOL_OUTPUT_GUARDRAIL_TRIPPED
            else:
                raise exc
            runtime = guardrail_by_id.get(guardrail_id)
            if runtime is None or runtime.kind is not kind:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "SDK Guardrail tripwire did not match the immutable Guardrail graph",
                ) from exc
            run_data = getattr(exc, "run_data", None)
            usage = _usage_summary(
                getattr(getattr(run_data, "context_wrapper", None), "usage", None)
            )
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "guardrail.tripped",
                    {
                        "guardrail_id": runtime.guardrail_id,
                        "guardrail_kind": runtime.kind.value,
                        "tool_id": runtime.tool_id,
                        "behavior": runtime.behavior,
                        "tripwire_triggered": True,
                        "guarded_content_persisted": False,
                        "output_info_persisted": False,
                        "raw_sdk_error_persisted": False,
                    },
                    payload_schema_version="okcanvas-native-guardrail-tripwire-v1",
                )
            )
            raise GenericExecutionFailure(
                code,
                f"Native SDK {runtime.kind.value.lower()} Guardrail tripwire triggered",
                retryable=False,
                detail_type=type(exc).__name__,
                usage=usage,
                trace_id=trace_id,
            ) from exc

        class ProductRunHooks(RunHooks):
            async def on_agent_start(self, context, agent) -> None:  # type: ignore[no-untyped-def]
                active = definition_for_sdk_agent(agent)
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "agent.started",
                        {"agent_id": active.agent_id, "agent_name": active.name},
                    )
                )

            async def on_llm_start(  # type: ignore[no-untyped-def]
                self, context, agent, system_prompt, input_items
            ) -> None:
                active = definition_for_sdk_agent(agent)
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "model.started",
                        {
                            "agent_id": active.agent_id,
                            **model_route.to_safe_event_dict(),
                            "model_retry_policy_id": model_retry_policy.policy_id,
                            "model_retry_policy_sha256": model_retry_policy.policy_sha256,
                            "runner_managed_max_retries": (
                                model_retry_policy.runner_managed_max_retries
                            ),
                            "provider_managed_max_retries": (
                                model_retry_policy.provider_managed_max_retries
                            ),
                            "reasoning_evidence_policy_id": (
                                reasoning_evidence_policy.policy_id
                            ),
                            "reasoning_evidence_policy_sha256": (
                                reasoning_evidence_policy.policy_sha256
                            ),
                            "reasoning_summary_requested": (
                                reasoning_evidence_policy.reasoning_summary_requested
                            ),
                            "reasoning_response_include_count": len(
                                reasoning_evidence_policy.response_include
                            ),
                            "hosted_search_response_include_count": (
                                len(hosted_search_policy.response_include)
                                if hosted_search_policy
                                else 0
                            ),
                            "reasoning_content_persisted": False,
                            "reasoning_token_count_persisted": (
                                reasoning_evidence_policy.persist_reasoning_token_count
                            ),
                            "response_storage_policy_id": response_storage_policy.policy_id,
                            "response_storage_policy_sha256": (
                                response_storage_policy.policy_sha256
                            ),
                            "response_store_requested": (
                                response_storage_policy.response_store_requested
                            ),
                            "provider_identifier_policy_id": (
                                provider_identifier_policy.policy_id
                            ),
                            "provider_identifier_policy_sha256": (
                                provider_identifier_policy.policy_sha256
                            ),
                            "provider_response_id_persisted": False,
                            "provider_request_id_persisted": False,
                            "provider_identifier_presence_persisted": True,
                            "input_item_count": len(input_items),
                        },
                    )
                )

            async def on_llm_end(self, context, agent, response) -> None:  # type: ignore[no-untyped-def]
                active = definition_for_sdk_agent(agent)
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "model.completed",
                        {
                            "agent_id": active.agent_id,
                            "response_id_present": provider_identifier_presence(
                                getattr(response, "response_id", None),
                                provider_identifier_policy,
                            ),
                            "request_id_present": provider_identifier_presence(
                                getattr(response, "request_id", None),
                                provider_identifier_policy,
                            ),
                            "provider_response_id_persisted": False,
                            "provider_request_id_persisted": False,
                            "output_item_count": len(getattr(response, "output", ()) or ()),
                            "output_item_type_counts": _safe_model_output_shape(response),
                            "output_item_content_persisted": False,
                            "reasoning_item_count": count_reasoning_items(response),
                            "reasoning_content_persisted": False,
                            "reasoning_summary_persisted": False,
                            "reasoning_item_ids_persisted": False,
                            "reasoning_provider_data_persisted": False,
                        },
                    )
                )

            async def on_agent_end(self, context, agent, output) -> None:  # type: ignore[no-untyped-def]
                active = definition_for_sdk_agent(agent)
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "agent.completed",
                        {
                            "agent_id": active.agent_id,
                            "output_contract": active.output_contract,
                        },
                    )
                )

            async def on_tool_start(self, context, agent, tool) -> None:  # type: ignore[no-untyped-def]
                nonlocal agent_tool_count, grounded_agent_tool_request_count, active_mcp_tool
                tool_name, server_id, call_id_present = _tool_identity(tool, context)
                if _tool_origin_type(tool) == "agent_as_tool":
                    if grounded_structured_delegation_enabled:
                        binding = grounded_agent_tool_by_name.get(tool_name)
                        if (
                            binding is None
                            or agent_tool_count != 0
                            or grounded_agent_tool_request_count != 0
                        ):
                            raise GenericExecutionFailure(
                                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                                "Grounded Agent-as-Tool request is outside the bounded one-request read graph",
                            )
                        grounded_agent_tool_request_count = 1
                        await lifecycle_sink(
                            GatewayLifecycleEvent(
                                "agent.tool.requested",
                                {
                                    "from_agent_id": definition.agent_id,
                                    "to_agent_id": binding.child.agent_id,
                                    "tool_name": tool_name,
                                    "tool_call_id_present": call_id_present,
                                    "arguments_persisted": False,
                                    "admitted": False,
                                },
                                payload_schema_version="okcanvas-grounded-agent-tool-requested-v1",
                                source=EventSource.AGENT_SDK,
                            )
                        )
                        return
                    if (
                        agent_tool_policy is None
                        or agent_tool_child_definition is None
                        or expected_agent_tool_name is None
                        or tool_name != expected_agent_tool_name
                        or agent_tool_count != 0
                    ):
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                            "SDK Agent-as-Tool call did not match the immutable one-edge graph",
                        )
                    agent_tool_count = 1
                    usage = _usage_summary(getattr(context, "usage", None))
                    await lifecycle_sink(
                        GatewayLifecycleEvent(
                            "agent.tool.started",
                            {
                                "from_agent_id": definition.agent_id,
                                "to_agent_id": agent_tool_child_definition.agent_id,
                                "tool_name": tool_name,
                                "tool_call_id_present": call_id_present,
                                "arguments_persisted": False,
                                "result_persisted": False,
                                "input_mode": agent_tool_policy.input_mode,
                                "output_mode": agent_tool_policy.output_mode,
                                "parent_usage_before": usage.model_dump(mode="json"),
                            },
                            payload_schema_version="okcanvas-agent-as-tool-started-v1",
                        )
                    )
                    return
                if server_id:
                    if server_id not in allowed_server_ids:
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.MCP_TOOL_POLICY_VIOLATION,
                            "A non-allowlisted MCP Tool invocation was attempted",
                        )
                    active_mcp_tool = {"server_id": server_id, "tool_name": tool_name}
                    payload = {
                        "server_id": server_id,
                        "tool_name": tool_name,
                        "tool_call_id_present": call_id_present,
                        "arguments_persisted": False,
                    }
                    schema = "okcanvas-mcp-tool-started-v1"
                    source = EventSource.MCP
                else:
                    runtime = local_tools.get(tool_name)
                    if runtime is None:
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.FUNCTION_TOOL_POLICY_VIOLATION,
                            "A non-allowlisted local Function Tool invocation was attempted",
                        )
                    payload = {
                        "tool_id": runtime.tool_id,
                        "tool_name": runtime.tool_id,
                        "runtime_version": runtime.runtime_version,
                        "approval_required": False,
                        "tool_call_id_present": call_id_present,
                        "arguments_persisted": False,
                    }
                    schema = "okcanvas-function-tool-started-v1"
                    source = EventSource.AGENT_SDK
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "tool.started", payload, payload_schema_version=schema, source=source
                    )
                )

            async def on_tool_end(self, context, agent, tool, result) -> None:  # type: ignore[no-untyped-def]
                nonlocal active_mcp_tool, agent_tool_completed
                tool_name, server_id, call_id_present = _tool_identity(tool, context)
                if _tool_origin_type(tool) == "agent_as_tool":
                    if grounded_structured_delegation_enabled:
                        binding = grounded_agent_tool_by_name.get(tool_name)
                        if (
                            binding is None
                            or admitted_agent_tool_definition is None
                            or admitted_agent_tool_definition.agent_id != binding.child.agent_id
                            or agent_tool_count != 1
                        ):
                            raise GenericExecutionFailure(
                                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                                "Grounded Agent-as-Tool completion was not admitted",
                            )
                        agent_tool_completed = True
                        usage = _usage_summary(getattr(context, "usage", None))
                        await lifecycle_sink(
                            GatewayLifecycleEvent(
                                "agent.tool.completed",
                                {
                                    "from_agent_id": definition.agent_id,
                                    "to_agent_id": binding.child.agent_id,
                                    "tool_name": tool_name,
                                    "tool_call_id_present": call_id_present,
                                    "arguments_persisted": False,
                                    "result_present": result is not None,
                                    "result_persisted": False,
                                    "parent_control_retained": True,
                                    "usage_after": usage.model_dump(mode="json"),
                                },
                                payload_schema_version="okcanvas-agent-as-tool-completed-v1",
                            )
                        )
                        return
                    if (
                        agent_tool_policy is None
                        or agent_tool_child_definition is None
                        or expected_agent_tool_name is None
                        or tool_name != expected_agent_tool_name
                        or agent_tool_count != 1
                    ):
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                            "SDK Agent-as-Tool completion did not match the immutable one-edge graph",
                        )
                    agent_tool_completed = True
                    usage = _usage_summary(getattr(context, "usage", None))
                    await lifecycle_sink(
                        GatewayLifecycleEvent(
                            "agent.tool.completed",
                            {
                                "from_agent_id": definition.agent_id,
                                "to_agent_id": agent_tool_child_definition.agent_id,
                                "tool_name": tool_name,
                                "tool_call_id_present": call_id_present,
                                "arguments_persisted": False,
                                "result_present": result is not None,
                                "result_persisted": False,
                                "parent_control_retained": True,
                                "usage_after": usage.model_dump(mode="json"),
                            },
                            payload_schema_version="okcanvas-agent-as-tool-completed-v1",
                        )
                    )
                    return
                if server_id:
                    if server_id not in allowed_server_ids:
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.MCP_TOOL_POLICY_VIOLATION,
                            "A non-allowlisted MCP Tool completion was observed",
                        )
                    payload = {
                        "server_id": server_id,
                        "tool_name": tool_name,
                        "tool_call_id_present": call_id_present,
                        "result_present": result is not None,
                        "result_persisted": False,
                    }
                    schema = "okcanvas-mcp-tool-completed-v1"
                    source = EventSource.MCP
                else:
                    runtime = local_tools.get(tool_name)
                    if runtime is None:
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.FUNCTION_TOOL_POLICY_VIOLATION,
                            "A non-allowlisted local Function Tool completion was observed",
                        )
                    payload = {
                        "tool_id": runtime.tool_id,
                        "tool_name": runtime.tool_id,
                        "runtime_version": runtime.runtime_version,
                        "approval_required": False,
                        "tool_call_id_present": call_id_present,
                        "result_present": result is not None,
                        "result_persisted": False,
                    }
                    if isinstance(result, SandboxProjectReadonlyInspectOutput):
                        payload.update({
                            "workspace_access": result.workspace_access,
                            "workspace_materialized": result.workspace_materialized,
                            "snapshot_sha256": result.snapshot_sha256,
                            "files_considered": result.files_considered,
                            "inspected_file_count": len(result.inspected_files),
                            "docker_call_count": result.docker_call_count,
                            "selected_file_hashes_verified": result.selected_file_hashes_verified,
                            "cleanup_state": result.cleanup_state,
                            "orphan_count": result.orphan_count,
                            "image_binding_sha256": result.image_binding_sha256,
                            "network_mode": result.network_mode,
                            "shell_enabled": result.shell_enabled,
                            "apply_patch_enabled": result.apply_patch_enabled,
                            "raw_workspace_content_persisted": False,
                            "raw_tool_result_persisted": False,
                        })
                        schema = "okcanvas-sandbox-readonly-tool-completed-v1"
                    else:
                        schema = "okcanvas-function-tool-completed-v1"
                    source = EventSource.AGENT_SDK
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "tool.completed", payload, payload_schema_version=schema, source=source
                    )
                )
                if server_id:
                    active_mcp_tool = None

            async def on_handoff(self, context, from_agent, to_agent) -> None:  # type: ignore[no-untyped-def]
                nonlocal handoff_count
                if handoff_policy is None or child_definition is None:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "A Handoff occurred in a zero-Handoff Agent",
                    )
                source_definition = definition_for_sdk_agent(from_agent)
                target_definition = definition_for_sdk_agent(to_agent)
                if (
                    handoff_count != 0
                    or source_definition.agent_id != definition.agent_id
                    or target_definition.agent_id != child_definition.agent_id
                ):
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "SDK Handoff did not match the immutable one-edge graph",
                    )
                handoff_count = 1
                usage = _usage_summary(getattr(context, "usage", None))
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "agent.handoff",
                        {
                            "from_agent_id": source_definition.agent_id,
                            "to_agent_id": target_definition.agent_id,
                            "input_filter_mode": handoff_policy.input_filter_mode,
                            "nest_handoff_history": handoff_policy.nest_handoff_history,
                            "handoff_input_payload_enabled": False,
                            "history_persisted": False,
                            "sdk_session_history_active": definition.session_mode == "sqlite-v1",
                            "session_id_present": session_id is not None,
                            "handoff_arguments_persisted": False,
                            "parent_usage": usage.model_dump(mode="json"),
                        },
                        payload_schema_version="okcanvas-native-agent-handoff-v1",
                    )
                )

        output_recovered = False

        def invalid_final_output_handler(_data: Any) -> Any:
            nonlocal output_recovered
            output_recovered = True
            return output_contract.recover_invalid_final_output(request)

        async def execute(active_mcp_servers: list[Any]) -> Any:
            root_active_mcp_servers = (
                [] if delegated_session_binding is not None else active_mcp_servers
            )
            child_active_mcp_servers = (
                active_mcp_servers if delegated_session_binding is not None else []
            )
            execution_id = "execution_" + hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:32]
            sdk_tools: list[Any] = []
            for runtime in function_tool_runtimes:
                if runtime.factory_id == "sandbox_project_readonly_inspect_v1":
                    if not self._sandbox_readonly_image:
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.FUNCTION_TOOL_CONFIGURATION_INVALID,
                            "Read-only Sandbox local image is required",
                        )
                    if project_snapshot is None and not self._readonly_workspace_root:
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.FUNCTION_TOOL_CONFIGURATION_INVALID,
                            "Read-only Sandbox requires a bound project snapshot or development workspace root",
                        )

                    def inspect_bound_snapshot() -> Any:
                        if project_snapshot is not None:
                            with materialize_project_snapshot(
                                project_snapshot,
                                temporary_parent=self._sandbox_temporary_parent,
                            ) as workspace_root:
                                return sandbox_project_readonly_inspect(
                                    str(workspace_root),
                                    request,
                                    image_reference=self._sandbox_readonly_image,
                                    temporary_parent=self._sandbox_temporary_parent,
                                )
                        return sandbox_project_readonly_inspect(
                            self._readonly_workspace_root or "",
                            request,
                            image_reference=self._sandbox_readonly_image,
                            temporary_parent=self._sandbox_temporary_parent,
                        )

                    async def sandbox_executor() -> Any:
                        try:
                            return await asyncio.to_thread(inspect_bound_snapshot)
                        except SandboxDockerError as exc:
                            await lifecycle_sink(
                                GatewayLifecycleEvent(
                                    "tool.failed",
                                    {
                                        "tool_id": runtime.tool_id,
                                        "tool_name": runtime.tool_id,
                                        "runtime_version": runtime.runtime_version,
                                        "code": exc.code,
                                        "detail_type": type(exc).__name__,
                                        "operation": exc.operation,
                                        "return_code": exc.return_code,
                                        "stderr_category": exc.stderr_category,
                                        "output_truncated": exc.output_truncated,
                                        "cleanup_attempted": exc.cleanup_attempted,
                                        "cleanup_completed": exc.cleanup_completed,
                                        "orphan_count": exc.orphan_count,
                                        "arguments_persisted": False,
                                        "result_persisted": False,
                                        "raw_arguments_persisted": False,
                                        "raw_output_persisted": False,
                                        "raw_message_persisted": False,
                                    },
                                    payload_schema_version="okcanvas-function-tool-failed-v1",
                                    source=EventSource.AGENT_SDK,
                                )
                            )
                            raise GenericExecutionFailure(
                                GenericExecutionErrorCode.FUNCTION_TOOL_POLICY_VIOLATION,
                                "Read-only Sandbox Tool failed safely",
                                detail_type=f"SandboxDockerError:{exc.code}",
                            ) from exc

                    sdk_tool = build_sdk_function_tool(
                        runtime,
                        execution_id=execution_id,
                        executor=sandbox_executor,
                    )
                elif runtime.factory_id == "project_readonly_inspect_v1":
                    if self._readonly_workspace_root is None:
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.FUNCTION_TOOL_POLICY_VIOLATION,
                            "Read-only project root is not configured",
                        )

                    async def project_executor() -> Any:
                        return await asyncio.to_thread(
                            project_readonly_inspect,
                            self._readonly_workspace_root,
                            request,
                        )

                    sdk_tool = build_sdk_function_tool(
                        runtime, execution_id=execution_id, executor=project_executor
                    )
                else:
                    sdk_tool = build_sdk_function_tool(
                        runtime,
                        execution_id=execution_id,
                        protected_text=request,
                    )
                selected_tool_guardrails = tuple(
                    tool_guardrails_by_tool.get(runtime.tool_id, ())
                )
                if selected_tool_guardrails:
                    attach_sdk_tool_guardrails(sdk_tool, selected_tool_guardrails)
                sdk_tools.append(sdk_tool)
            if hosted_search_policy is not None:
                sdk_tools.append(build_sdk_web_search_tool(hosted_search_policy))
            if guardrail_runtimes:
                input_guardrails, output_guardrails = build_sdk_agent_guardrails(
                    tuple(
                        item
                        for item in guardrail_runtimes
                        if item.kind in {GuardrailKind.INPUT, GuardrailKind.OUTPUT}
                    )
                )
            else:
                input_guardrails, output_guardrails = [], []
            sdk_handoffs: list[Any] = []
            if grounded_agent_tool_bindings:
                if grounded_interpretation_utterance is None:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                        "Grounded structured delegation has no user utterance",
                    )
                admission = GroundedDelegationAdmission(str(project_root))

                async def add_grounded_child_tool(binding: Any) -> None:
                    nonlocal agent_tool_count, admitted_agent_tool_definition
                    child_definition_local = binding.child
                    output_contract_local = grounded_output_contracts[child_definition_local.agent_id]
                    output_type_local = output_contract_local.output_type
                    child_agent_kwargs: dict[str, Any] = {
                        "name": child_definition_local.name,
                        "instructions": resolve_effective_instructions(child_definition_local),
                        "model": settings.model,
                        "tools": [],
                        "mcp_servers": [],
                        "handoffs": [],
                        "output_type": output_type_local,
                        "model_settings": ModelSettings(
                            tool_choice="required",
                            **reasoning_settings,
                            **response_storage_settings,
                        ),
                        "reset_tool_choice": True,
                    }
                    child_agent_local = Agent(**child_agent_kwargs)
                    sdk_definition_by_object[id(child_agent_local)] = child_definition_local
                    child_run_config_local = RunConfig(
                        model=settings.model,
                        model_provider=model_provider,
                        model_settings=ModelSettings(
                            retry=model_retry_settings,
                            **reasoning_settings,
                            **response_storage_settings,
                        ),
                        workflow_name=child_definition_local.workflow_name,
                        trace_id=trace_id,
                        group_id=run_id,
                        **trace_run_config_settings,
                        trace_metadata={
                            "run_id": run_id,
                            "model_route_id": model_route.policy.route_id,
                            "model_routing_policy_sha256": model_route.policy.policy_sha256,
                            "model_retry_policy_id": model_retry_policy.policy_id,
                            "model_retry_policy_sha256": model_retry_policy.policy_sha256,
                            "reasoning_evidence_policy_id": reasoning_evidence_policy.policy_id,
                            "reasoning_evidence_policy_sha256": reasoning_evidence_policy.policy_sha256,
                            "response_storage_policy_id": response_storage_policy.policy_id,
                            "response_storage_policy_sha256": response_storage_policy.policy_sha256,
                            "provider_identifier_policy_id": provider_identifier_policy.policy_id,
                            "provider_identifier_policy_sha256": provider_identifier_policy.policy_sha256,
                            "trace_export_policy_id": trace_export_policy.policy_id,
                            "trace_export_policy_sha256": trace_export_policy.policy_sha256,
                            "agent_definition_id": child_definition_local.agent_id,
                            "agent_definition_version": child_definition_local.version,
                            "agent_definition_sha256": child_definition_local.definition_sha256,
                            "invocation_kind": "GROUNDED_STRUCTURED_AGENT_AS_TOOL",
                            "run_config_inherited": False,
                        },
                    )
                    nested_stream_started_local = False

                    async def on_grounded_nested_stream(envelope: Any) -> None:
                        nonlocal nested_stream_started_local
                        if self._native_stream_broker is None:
                            return
                        if not nested_stream_started_local:
                            nested_stream_started_local = True
                            await self._native_stream_broker.publish(
                                run_id=run_id,
                                event_type="agent.tool.stream.started",
                                payload={
                                    "agent_id": child_definition_local.agent_id,
                                    "persisted": False,
                                },
                            )
                        sdk_event = envelope.get("event") if isinstance(envelope, dict) else None
                        adapted = adapt_sdk_stream_event(sdk_event)
                        if adapted is None:
                            return
                        nested_type, nested_payload = adapted
                        if nested_type == "agent.updated":
                            nested_payload = {
                                **nested_payload,
                                "agent_id": child_definition_local.agent_id,
                            }
                        await self._native_stream_broker.publish(
                            run_id=run_id,
                            event_type=f"agent.tool.{nested_type}",
                            payload={**nested_payload, "nested": True},
                        )

                    async def grounded_input_builder(options: dict[str, Any]) -> str:
                        nonlocal agent_tool_count, admitted_agent_tool_definition
                        raw = options.get("params")
                        if not isinstance(raw, dict):
                            raise GroundedDelegationContractError(
                                "Structured delegation parameters are not an object"
                            )
                        async with grounded_admission_lock:
                            if agent_tool_count != 0 or admitted_agent_tool_definition is not None:
                                raise GroundedDelegationContractError(
                                    "At most one grounded specialist may be admitted per Turn"
                                )
                            try:
                                if binding.domain == "ORGANIZATION_CONTEXT":
                                    child_request = admission.admit_organization(
                                        raw=raw,
                                        user_utterance=grounded_interpretation_utterance,
                                        delegated_identity=delegated_mcp_identity,
                                        session_focus=grounded_session_focus,
                                        parent_side_effect=str((routing_context or {}).get("side_effect") or ""),
                                    )
                                    admitted_tool_choice = (
                                        organization_context_named_tool_choice(child_request)
                                    )
                                elif binding.domain == "GROUPWARE":
                                    child_request = admission.admit_groupware(
                                        raw=raw,
                                        user_utterance=grounded_interpretation_utterance,
                                        delegated_identity=delegated_mcp_identity,
                                        session_focus=grounded_session_focus,
                                        parent_side_effect=str((routing_context or {}).get("side_effect") or ""),
                                    )
                                    admitted_tool_choice = groupware_named_tool_choice(child_request)
                                else:
                                    raise GroundedDelegationContractError(
                                        "Unsupported grounded delegation domain"
                                    )
                                if not admitted_tool_choice:
                                    raise GroundedDelegationContractError(
                                        "Admitted child request did not resolve one exact MCP Tool"
                                    )
                                mcp_definition = grounded_mcp_definition_by_agent[
                                    child_definition_local.agent_id
                                ]
                                access_bindings = MCPAccessCatalog(project_root).bind_many(
                                    (mcp_definition,), delegated_mcp_identity
                                )
                                lazy_runtime = create_openai_mcp_runtime(
                                    (mcp_definition,),
                                    project_root=project_root,
                                    access_bindings=access_bindings,
                                    health_registry=MCPPassiveHealthRegistry(),
                                )
                                server = lazy_runtime.servers[0]
                                await server.connect()
                            except Exception as exc:
                                await lifecycle_sink(
                                    GatewayLifecycleEvent(
                                        "agent.tool.admission.denied",
                                        {
                                            "from_agent_id": definition.agent_id,
                                            "to_agent_id": child_definition_local.agent_id,
                                            "arguments_persisted": False,
                                            "stable_ids_from_model_accepted": False,
                                            "detail_type": type(exc).__name__,
                                        },
                                        payload_schema_version=(
                                            "okcanvas-grounded-agent-tool-admission-denied-v1"
                                        ),
                                        source=EventSource.RUNTIME,
                                    )
                                )
                                raise
                            child_agent_local.mcp_servers = [server]
                            child_agent_local.model_settings = ModelSettings(
                                tool_choice=admitted_tool_choice,
                                **reasoning_settings,
                                **response_storage_settings,
                            )
                            grounded_connected_servers[child_definition_local.agent_id] = server
                            grounded_admitted_request_by_agent[child_definition_local.agent_id] = (
                                child_request
                            )
                            admitted_agent_tool_definition = child_definition_local
                            agent_tool_count = 1
                            await lifecycle_sink(
                                GatewayLifecycleEvent(
                                    "agent.tool.admitted",
                                    {
                                        "from_agent_id": definition.agent_id,
                                        "to_agent_id": child_definition_local.agent_id,
                                        "capability_id": (
                                            "organization-context-read-v1"
                                            if binding.domain == "ORGANIZATION_CONTEXT"
                                            else "groupware-read-v1"
                                        ),
                                        "side_effect": "READ",
                                        "arguments_persisted": False,
                                        "stable_ids_from_model_accepted": False,
                                        "selected_child_mcp_connected": True,
                                    },
                                    payload_schema_version="okcanvas-grounded-agent-tool-admitted-v1",
                                    source=EventSource.RUNTIME,
                                )
                            )
                            await lifecycle_sink(
                                GatewayLifecycleEvent(
                                    "agent.tool.started",
                                    {
                                        "from_agent_id": definition.agent_id,
                                        "to_agent_id": child_definition_local.agent_id,
                                        "tool_name": agent_tool_name(child_definition_local),
                                        "arguments_persisted": False,
                                        "result_persisted": False,
                                        "input_mode": "STRUCTURED_MODEL_INTERPRETATION",
                                        "output_mode": binding.policy.output_mode,
                                    },
                                    payload_schema_version="okcanvas-agent-as-tool-started-v1",
                                    source=EventSource.RUNTIME,
                                )
                            )
                            return child_request

                    async def extract_grounded_nested_output(result: Any) -> str:
                        child_request = grounded_admitted_request_by_agent.get(
                            child_definition_local.agent_id
                        )
                        if child_request is None:
                            raise AgentToolContractError(
                                "Grounded child output has no admitted request"
                            )
                        try:
                            draft = result.final_output_as(
                                output_type_local, raise_if_incorrect_type=True
                            )
                            normalization = output_contract_local.normalize_nested_result(
                                result=result, output=draft, request=child_request
                            )
                            payload = normalization.output.model_dump(
                                mode="json", round_trip=True
                            )
                            serialized = json.dumps(
                                payload, ensure_ascii=False, separators=(",", ":")
                            )
                        except Exception as exc:
                            diagnostic = _safe_structured_output_failure_diagnostic(
                                exc,
                                output_contract=child_definition_local.output_contract,
                                agent_id=child_definition_local.agent_id,
                            )
                            await lifecycle_sink(
                                GatewayLifecycleEvent(
                                    "agent.tool.output.normalization.failed",
                                    diagnostic,
                                    payload_schema_version=(
                                        "okcanvas-agent-tool-output-normalization-failed-v1"
                                    ),
                                    source=EventSource.AGENT_SDK,
                                )
                            )
                            raise AgentToolContractError(
                                "Nested Agent output could not be normalized"
                            ) from exc
                        if len(serialized.encode("utf-8")) > binding.policy.max_result_bytes:
                            raise AgentToolContractError(
                                "Nested Agent structured result exceeds the configured bound"
                            )
                        await lifecycle_sink(
                            GatewayLifecycleEvent(
                                "agent.tool.output.normalized",
                                {
                                    "agent_id": child_definition_local.agent_id,
                                    "output_contract": child_definition_local.output_contract,
                                    "normalization_strategy": (
                                        output_contract_local.nested_normalization_strategy
                                    ),
                                    **normalization.metadata,
                                },
                                payload_schema_version="okcanvas-agent-tool-output-normalized-v1",
                                source=EventSource.AGENT_SDK,
                            )
                        )
                        return serialized

                    if binding.domain == "ORGANIZATION_CONTEXT":
                        parameters = OrganizationReadDelegationInput
                        description = (
                            "Use for exactly one grounded, read-only Organization Context request. "
                            "Interpret natural language using the turn-local grounded context. "
                            "Never supply a stable entity ID; use context_reference_mode=SESSION_FOCUS "
                            "only when the current grounded focus is the intended entity."
                        )
                    elif binding.domain == "GROUPWARE":
                        parameters = GroupwareReadDelegationInput
                        description = (
                            "Use for exactly one grounded, read-only Groupware resource: notice, mail, "
                            "or calendar. Use context_reference_mode=SESSION_FOCUS only when the user "
                            "clearly refers to the current grounded entity."
                        )
                    else:
                        raise GenericExecutionFailure(
                            GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                            "Unsupported grounded child binding",
                        )
                    sdk_tools.append(
                        build_sdk_agent_tool(
                            child_sdk_agent=child_agent_local,
                            child_definition=child_definition_local,
                            policy=binding.policy,
                            run_config=child_run_config_local,
                            hooks=ProductRunHooks(),
                            on_stream=on_grounded_nested_stream,
                            custom_output_extractor=extract_grounded_nested_output,
                            parameters=parameters,
                            input_builder=grounded_input_builder,
                            tool_description=description,
                        )
                    )

                for grounded_binding in grounded_agent_tool_bindings:
                    await add_grounded_child_tool(grounded_binding)

            if (
                agent_tool_child_definition is not None
                and agent_tool_policy is not None
                and (delegated_session_binding is None or delegated_route_required)
            ):
                child_agent_kwargs: dict[str, Any] = {
                    "name": agent_tool_child_definition.name,
                    "instructions": resolve_effective_instructions(agent_tool_child_definition),
                    "model": settings.model,
                    "tools": [],
                    "mcp_servers": child_active_mcp_servers,
                    "handoffs": [],
                    "output_type": agent_tool_output_type,
                }
                if delegated_session_binding is not None:
                    child_tool_choice = (
                        organization_context_named_tool_choice(request)
                        if organization_context_session_binding is not None
                        else groupware_named_tool_choice(request)
                        if groupware_session_binding is not None
                        else None
                    ) or "required"
                    child_agent_kwargs["model_settings"] = ModelSettings(
                        tool_choice=child_tool_choice,
                        **reasoning_settings,
                        **response_storage_settings,
                    )
                    child_agent_kwargs["reset_tool_choice"] = True
                child_agent = Agent(**child_agent_kwargs)
                sdk_definition_by_object[id(child_agent)] = agent_tool_child_definition
                child_run_config = RunConfig(
                    model=settings.model,
                    model_provider=model_provider,
                    model_settings=ModelSettings(retry=model_retry_settings, **reasoning_settings, **response_storage_settings),
                    workflow_name=agent_tool_child_definition.workflow_name,
                    trace_id=trace_id,
                    group_id=run_id,
                    **trace_run_config_settings,
                    trace_metadata={
                        "run_id": run_id,
                        "model_route_id": model_route.policy.route_id,
                        "model_routing_policy_sha256": model_route.policy.policy_sha256,
                        "model_retry_policy_id": model_retry_policy.policy_id,
                        "model_retry_policy_sha256": model_retry_policy.policy_sha256,
                        "reasoning_evidence_policy_id": reasoning_evidence_policy.policy_id,
                        "reasoning_evidence_policy_sha256": (
                            reasoning_evidence_policy.policy_sha256
                        ),
                        "reasoning_summary_requested": (
                            reasoning_evidence_policy.reasoning_summary_requested
                        ),
                        "reasoning_content_persisted": False,
                        "response_storage_policy_id": response_storage_policy.policy_id,
                        "response_storage_policy_sha256": response_storage_policy.policy_sha256,
                        "response_store_requested": response_storage_policy.response_store_requested,
                        "provider_identifier_policy_id": provider_identifier_policy.policy_id,
                        "provider_identifier_policy_sha256": provider_identifier_policy.policy_sha256,
                        "provider_response_id_persisted": False,
                        "provider_request_id_persisted": False,
                        "trace_export_policy_id": trace_export_policy.policy_id,
                        "trace_export_policy_sha256": trace_export_policy.policy_sha256,
                        "provider_trace_export_enabled": False,
                        "provider_id": model_route.policy.provider_id,
                        "model": model_route.model_id,
                        "parent_agent_definition_id": definition.agent_id,
                        "agent_definition_id": agent_tool_child_definition.agent_id,
                        "agent_definition_version": agent_tool_child_definition.version,
                        "agent_definition_sha256": agent_tool_child_definition.definition_sha256,
                        "invocation_kind": "AGENT_AS_TOOL",
                        "run_config_inherited": False,
                        "organization_context_named_tool_choice": (
                            child_tool_choice
                            if organization_context_session_binding is not None
                            else None
                        ),
                        "groupware_named_tool_choice": (
                            child_tool_choice if groupware_session_binding is not None else None
                        ),
                    },
                )
                nested_stream_started = False

                async def on_nested_stream(envelope: Any) -> None:
                    nonlocal nested_stream_started
                    if self._native_stream_broker is None:
                        return
                    if not nested_stream_started:
                        nested_stream_started = True
                        await self._native_stream_broker.publish(
                            run_id=run_id,
                            event_type="agent.tool.stream.started",
                            payload={
                                "agent_id": agent_tool_child_definition.agent_id,
                                "persisted": False,
                            },
                        )
                    sdk_event = envelope.get("event") if isinstance(envelope, dict) else None
                    adapted = adapt_sdk_stream_event(sdk_event)
                    if adapted is None:
                        return
                    nested_type, nested_payload = adapted
                    if nested_type == "agent.updated":
                        nested_payload = {
                            **nested_payload,
                            "agent_id": agent_tool_child_definition.agent_id,
                        }
                    await self._native_stream_broker.publish(
                        run_id=run_id,
                        event_type=f"agent.tool.{nested_type}",
                        payload={**nested_payload, "nested": True},
                    )

                async def extract_nested_output(result: Any) -> str:
                    if agent_tool_output_contract is None or agent_tool_output_type is None:
                        raise AgentToolContractError("Nested output contract is unavailable")
                    try:
                        draft = result.final_output_as(
                            agent_tool_output_type, raise_if_incorrect_type=True
                        )
                        normalization = agent_tool_output_contract.normalize_nested_result(
                            result=result, output=draft, request=request
                        )
                        payload = normalization.output.model_dump(mode="json", round_trip=True)
                        serialized = json.dumps(
                            payload, ensure_ascii=False, separators=(",", ":")
                        )
                    except Exception as exc:
                        diagnostic = _safe_structured_output_failure_diagnostic(
                            exc,
                            output_contract=agent_tool_child_definition.output_contract,
                            agent_id=agent_tool_child_definition.agent_id,
                        )
                        await lifecycle_sink(
                            GatewayLifecycleEvent(
                                "agent.tool.output.normalization.failed",
                                diagnostic,
                                payload_schema_version=(
                                    "okcanvas-agent-tool-output-normalization-failed-v1"
                                ),
                                source=EventSource.AGENT_SDK,
                            )
                        )
                        raise AgentToolContractError(
                            "Nested Agent output could not be normalized"
                        ) from exc
                    if len(serialized.encode("utf-8")) > agent_tool_policy.max_result_bytes:
                        raise AgentToolContractError(
                            "Nested Agent structured result exceeds the configured bound"
                        )
                    await lifecycle_sink(
                        GatewayLifecycleEvent(
                            "agent.tool.output.normalized",
                            {
                                "agent_id": agent_tool_child_definition.agent_id,
                                "output_contract": agent_tool_child_definition.output_contract,
                                "normalization_strategy": (
                                    agent_tool_output_contract.nested_normalization_strategy
                                ),
                                **normalization.metadata,
                            },
                            payload_schema_version="okcanvas-agent-tool-output-normalized-v1",
                            source=EventSource.AGENT_SDK,
                        )
                    )
                    if self._native_stream_broker is not None:
                        await self._native_stream_broker.publish(
                            run_id=run_id,
                            event_type="agent.tool.stream.completed",
                            payload={
                                "agent_id": agent_tool_child_definition.agent_id,
                                "result_byte_length": len(serialized.encode("utf-8")),
                                "result_persisted": False,
                                "persisted": False,
                            },
                        )
                    return serialized

                sdk_tools.append(
                    build_sdk_agent_tool(
                        child_sdk_agent=child_agent,
                        child_definition=agent_tool_child_definition,
                        policy=agent_tool_policy,
                        run_config=child_run_config,
                        hooks=ProductRunHooks(),
                        on_stream=on_nested_stream,
                        custom_output_extractor=extract_nested_output,
                    )
                )
            if child_definition is not None and handoff_policy is not None:
                child_agent = Agent(
                    name=child_definition.name,
                    instructions=resolve_effective_instructions(child_definition),
                    model=settings.model,
                    tools=[],
                    mcp_servers=[],
                    handoffs=[],
                    output_type=output_type,
                    handoff_description=(
                        "Declared language-only specialist for the governed request."
                    ),
                )
                sdk_definition_by_object[id(child_agent)] = child_definition
                sdk_handoffs.append(
                    build_sdk_native_handoff(
                        child_sdk_agent=child_agent,
                        child_definition=child_definition,
                        policy=handoff_policy,
                    )
                )
            root_instructions = resolve_effective_instructions(definition)
            agent_kwargs: dict[str, Any] = {
                "name": definition.name,
                "instructions": root_instructions,
                "model": settings.model,
                "tools": sdk_tools,
                "mcp_servers": root_active_mcp_servers,
                "mcp_config": {"include_server_in_tool_names": False},
                "handoffs": sdk_handoffs,
                "input_guardrails": input_guardrails,
                "output_guardrails": output_guardrails,
                "output_type": output_type,
            }
            if hosted_search_policy is not None:
                agent_kwargs["model_settings"] = ModelSettings(**selected_model_settings)
                agent_kwargs["reset_tool_choice"] = True
            elif sdk_tools:
                if (
                    not grounded_structured_delegation_enabled
                    and (delegated_session_binding is None or delegated_route_required)
                ):
                    agent_kwargs["model_settings"] = ModelSettings(
                        tool_choice="required", **reasoning_settings, **response_storage_settings
                    )
            agent = Agent(**agent_kwargs)
            sdk_definition_by_object[id(agent)] = definition

            def grounded_model_input_filter(data: Any) -> Any:
                if grounded_interpretation_context_text is None:
                    return data.model_data
                return _inject_grounded_interpretation_context(
                    data.model_data, grounded_interpretation_context_text
                )

            run_config = RunConfig(
                model=settings.model,
                model_provider=model_provider,
                model_settings=ModelSettings(retry=model_retry_settings, **selected_model_settings),
                workflow_name=definition.workflow_name,
                trace_id=trace_id,
                group_id=run_id,
                call_model_input_filter=(
                    grounded_model_input_filter
                    if grounded_interpretation_context_text is not None
                    else None
                ),
                **trace_run_config_settings,
                trace_metadata={
                    "run_id": run_id,
                    "model_route_id": model_route.policy.route_id,
                    "model_routing_policy_sha256": model_route.policy.policy_sha256,
                    "model_retry_policy_id": model_retry_policy.policy_id,
                    "model_retry_policy_sha256": model_retry_policy.policy_sha256,
                    "reasoning_evidence_policy_id": reasoning_evidence_policy.policy_id,
                    "reasoning_evidence_policy_sha256": (
                        reasoning_evidence_policy.policy_sha256
                    ),
                    "reasoning_summary_requested": (
                        reasoning_evidence_policy.reasoning_summary_requested
                    ),
                    "reasoning_content_persisted": False,
                    "response_storage_policy_id": response_storage_policy.policy_id,
                    "response_storage_policy_sha256": response_storage_policy.policy_sha256,
                    "response_store_requested": response_storage_policy.response_store_requested,
                    "provider_identifier_policy_id": provider_identifier_policy.policy_id,
                    "provider_identifier_policy_sha256": provider_identifier_policy.policy_sha256,
                    "provider_response_id_persisted": False,
                    "provider_request_id_persisted": False,
                    "trace_export_policy_id": trace_export_policy.policy_id,
                    "trace_export_policy_sha256": trace_export_policy.policy_sha256,
                    "provider_trace_export_enabled": False,
                    "provider_id": model_route.policy.provider_id,
                    "model": model_route.model_id,
                    "agent_definition_id": definition.agent_id,
                    "agent_definition_version": definition.version,
                    "agent_definition_sha256": definition.definition_sha256,
                    "mcp_server_ids": list(definition.mcp_servers),
                    "function_tool_ids": list(definition.tools),
                    "hosted_tool_ids": list(definition.hosted_tools),
                    "skill_ids": list(definition.skills),
                    "hosted_web_search_policy_id": (
                        hosted_search_policy.policy_id if hosted_search_policy else None
                    ),
                    "hosted_web_search_policy_sha256": (
                        hosted_search_policy.policy_sha256 if hosted_search_policy else None
                    ),
                    "hosted_search_query_persisted": False,
                    "hosted_search_content_persisted": False,
                    "handoff_agent_ids": list(definition.handoffs),
                    "handoff_policy_id": handoff_policy.policy_id if handoff_policy else None,
                    "agent_tool_ids": list(definition.agent_tools),
                    "agent_tool_policy_id": agent_tool_policy.policy_id if agent_tool_policy else None,
                    "session_mode": definition.session_mode,
                    "session_id_present": session_id is not None,
                    "guardrail_ids": list(definition.guardrails),
                    "input_mode": definition.input_mode,
                    "local_attachment_present": attachment is not None,
                    "local_attachment_raw_persisted": False,
                },
            )
            error_handlers = (
                {"invalid_final_output": invalid_final_output_handler}
                if output_contract.supports_invalid_final_output_recovery
                else None
            )
            if attachment is not None:
                encoded = base64.b64encode(attachment.data).decode("ascii")
                if attachment.metadata.input_kind == "input_file":
                    media_item = {
                        "type": "input_file",
                        "file_data": f"data:{attachment.metadata.media_type};base64,{encoded}",
                        "filename": attachment.metadata.filename,
                    }
                else:
                    media_item = {
                        "type": "input_image",
                        "detail": "auto",
                        "image_url": f"data:{attachment.metadata.media_type};base64,{encoded}",
                    }
                runner_input = [
                    {"role": "user", "content": [media_item]},
                    {"role": "user", "content": request},
                ]
            else:
                runner_input = (
                    invocation_prompt(function_tool_runtimes[0], execution_id)
                    if function_tool_runtimes
                    else request
                )
            sdk_session = (
                session_runtime.sdk_session(session_id)
                if definition.session_mode == "sqlite-v1" and session_runtime is not None and session_id is not None
                else None
            )
            run_kwargs: dict[str, Any] = {
                "max_turns": definition.max_turns,
                "hooks": ProductRunHooks(),
                "run_config": run_config,
                "error_handlers": error_handlers,
                "session": sdk_session,
            }
            if function_tool_runtimes:
                run_kwargs["context"] = {"execution_id": execution_id}
            try:
                if self._native_stream_broker is None:
                    return await Runner.run(agent, runner_input, **run_kwargs)

                await self._native_stream_broker.register(run_id)
                await self._native_stream_broker.publish(
                    run_id=run_id,
                    event_type="sdk.stream.started",
                    payload={
                        "agent_id": definition.agent_id,
                        "native_sdk_stream": True,
                        "persisted": False,
                    },
                )
                try:
                    result = Runner.run_streamed(agent, runner_input, **run_kwargs)
                    async for sdk_event in result.stream_events():
                        adapted = adapt_sdk_stream_event(sdk_event)
                        if adapted is None:
                            continue
                        event_type, payload = adapted
                        if event_type == "agent.updated":
                            updated_agent = getattr(sdk_event, "new_agent", None)
                            active_definition = sdk_definition_by_object.get(id(updated_agent))
                            if active_definition is None:
                                raise GenericExecutionFailure(
                                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                                    "Native stream exposed an undeclared Agent",
                                )
                            payload = {**payload, "agent_id": active_definition.agent_id}
                        await self._native_stream_broker.publish(
                            run_id=run_id, event_type=event_type, payload=payload
                        )
                    await self._native_stream_broker.complete(run_id=run_id, state="SUCCEEDED")
                    return result
                except BaseException as exc:
                    await self._native_stream_broker.complete(
                        run_id=run_id, state="FAILED", detail_type=type(exc).__name__
                    )
                    raise
            except (
                InputGuardrailTripwireTriggered,
                OutputGuardrailTripwireTriggered,
                ToolInputGuardrailTripwireTriggered,
                ToolOutputGuardrailTripwireTriggered,
            ) as exc:
                await raise_guardrail_failure(exc)
                raise AssertionError("unreachable")
            finally:
                for server in tuple(grounded_connected_servers.values()):
                    try:
                        await server.cleanup()
                    except Exception:
                        pass
                grounded_connected_servers.clear()
                if sdk_session is not None:
                    close = getattr(sdk_session, "close", None)
                    if callable(close):
                        close()
        try:
            try:
                active_mcp_definitions = (*mcp_definitions, *agent_tool_mcp_definitions)
                if active_mcp_definitions:
                    access_bindings = MCPAccessCatalog(project_root).bind_many(active_mcp_definitions, delegated_mcp_identity)
                    runtime = create_openai_mcp_runtime(
                        active_mcp_definitions, project_root=project_root, access_bindings=access_bindings,
                        health_registry=MCPPassiveHealthRegistry(),
                    )
                    entered = False
                    try:
                        async with runtime.manager as manager:
                            entered = True
                            if len(manager.active_servers) != len(active_mcp_definitions):
                                raise GenericExecutionFailure(
                                    GenericExecutionErrorCode.MCP_CONNECTION_FAILED,
                                    "Not all allowlisted MCP servers connected",
                                    retryable=True,
                                )
                            result = await execute(manager.active_servers)
                    except GenericExecutionFailure:
                        raise
                    except Exception as exc:
                        code = (
                            GenericExecutionErrorCode.SDK_RUN_FAILED
                            if entered
                            else GenericExecutionErrorCode.MCP_CONNECTION_FAILED
                        )
                        message = (
                            "OpenAI Agents SDK run failed"
                            if entered
                            else "MCP server connection failed"
                        )
                        diagnostic: dict[str, object] | None
                        retryable: bool
                        detail_type: str
                        if (
                            entered
                            and agent_tool_child_definition is not None
                            and agent_tool_count == 1
                            and not agent_tool_completed
                            and active_mcp_tool is None
                        ):
                            diagnostic = _safe_structured_output_failure_diagnostic(
                                exc,
                                output_contract=agent_tool_child_definition.output_contract,
                                agent_id=agent_tool_child_definition.agent_id,
                            )
                            retryable = True
                            detail_type = str(diagnostic["detail_type"])
                            await lifecycle_sink(
                                GatewayLifecycleEvent(
                                    "agent.output.validation.failed",
                                    diagnostic,
                                    payload_schema_version=(
                                        "okcanvas-agent-output-validation-failed-v1"
                                    ),
                                    source=EventSource.AGENT_SDK,
                                )
                            )
                        else:
                            diagnostic, retryable, detail_type = _safe_mcp_failure_diagnostic(
                                exc, active_mcp_tool if entered else None
                            )
                            if diagnostic is not None:
                                await lifecycle_sink(GatewayLifecycleEvent(
                                    "tool.failed",
                                    diagnostic,
                                    payload_schema_version="okcanvas-mcp-tool-failed-v1",
                                    source=EventSource.MCP,
                                ))
                        raise GenericExecutionFailure(
                            code,
                            message,
                            retryable=retryable,
                            detail_type=detail_type,
                            diagnostic=diagnostic,
                        ) from exc
                else:
                    result = await execute([])
            except GenericExecutionFailure:
                raise
            except Exception as exc:
                diagnostic = _safe_model_behavior_failure_diagnostic(exc)
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.SDK_RUN_FAILED,
                    "OpenAI Agents SDK run failed",
                    retryable=True,
                    detail_type=type(exc).__name__,
                    diagnostic=diagnostic,
                ) from exc
        finally:
            await model_provider.aclose()

        if child_definition is not None and handoff_count != 1:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Native Handoff Agent completed without the required single Handoff",
            )

        agent_tool_invocation_required = bool(
            not grounded_structured_delegation_enabled
            and agent_tool_child_definition is not None
            and (delegated_session_binding is None or delegated_route_required)
        )
        if grounded_structured_delegation_enabled:
            if agent_tool_count not in {0, 1}:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Grounded Session Root exceeded the one-child-per-Turn bound",
                )
            if agent_tool_count == 1 and not agent_tool_completed:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                    "Grounded Session child invocation did not complete",
                )
        elif agent_tool_invocation_required and agent_tool_count != 1:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Agent-as-Tool parent completed without the required single child invocation",
            )
        elif not agent_tool_invocation_required and agent_tool_count != 0:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.AGENT_POLICY_DENIED,
                "Agent-as-Tool invocation was not authorized by the Product routing context",
            )

        hosted_search_evidence = None
        if hosted_search_policy is not None:
            try:
                hosted_search_evidence = extract_hosted_web_search_evidence(
                    tuple(getattr(result, "new_items", ()) or ()),
                    hosted_search_policy,
                )
            except HostedWebSearchEvidenceError as exc:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.HOSTED_SEARCH_POLICY_VIOLATION,
                    "Hosted Web Search source evidence did not satisfy Product policy",
                    detail_type=type(exc).__name__,
                ) from exc
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "hosted.web_search.completed",
                    {
                        "policy_id": hosted_search_evidence.policy_id,
                        "policy_sha256": hosted_search_evidence.policy_sha256,
                        "search_call_count": hosted_search_evidence.search_call_count,
                        "retrieved_source_count": hosted_search_evidence.retrieved_source_count,
                        "citation_count": hosted_search_evidence.citation_count,
                        "raw_query_persisted": False,
                        "raw_content_persisted": False,
                        "provider_call_id_persisted": False,
                    },
                    payload_schema_version="okcanvas-hosted-web-search-completed-v1",
                    source=EventSource.AGENT_SDK,
                )
            )

        if output_recovered:
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "agent.output.recovered",
                    {
                        "agent_id": definition.agent_id,
                        "output_contract": definition.output_contract,
                        "strategy": output_contract.recovery_strategy,
                        "model_output_persisted": False,
                    },
                    payload_schema_version="okcanvas-agent-output-recovered-v1",
                )
            )

        try:
            output = result.final_output_as(output_type, raise_if_incorrect_type=True)
            output = normalize_output(definition.output_contract, output)
        except (TypeError, ValidationError, ValueError) as exc:
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.OUTPUT_CONTRACT_INVALID,
                f"Agent output did not match {definition.output_contract}",
                detail_type=type(exc).__name__,
            ) from exc

        total_usage = _usage_summary(result.context_wrapper.usage)
        final_response_id = result.last_response_id
        if definition.agent_id == "sandbox-readonly-coding-agent":
            if not isinstance(output, CodingAgentResult):
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.OUTPUT_CONTRACT_INVALID,
                    "Read-only Sandbox Agent returned the wrong output type",
                )
            tool_output = find_sandbox_tool_output(tuple(getattr(result, "new_items", ()) or ()))
            if tool_output is None:
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.ANSWER_COMPLETENESS_FAILED,
                    "Read-only Sandbox answer completeness evidence is unavailable",
                    detail_type="SandboxToolEvidenceMissing",
                    usage=total_usage,
                    trace_id=trace_id,
                )
            assessment = assess_sandbox_answer_completeness(
                request=request, output=output, tool_output=tool_output
            )
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "agent.output.completeness.checked",
                    {
                        "agent_id": definition.agent_id,
                        "exactness_requested": assessment.exactness_requested,
                        "complete": assessment.complete,
                        "issue_count": len(assessment.issue_codes),
                        "required_fragment_count": len(assessment.required_fragments),
                        "evidence_path_count": len(assessment.evidence_paths),
                        "raw_request_persisted": False,
                        "raw_evidence_persisted": False,
                        "raw_draft_persisted": False,
                    },
                    payload_schema_version="okcanvas-sandbox-answer-completeness-v1",
                )
            )
            if assessment.repair_required:
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "agent.output.completion.started",
                        {
                            "agent_id": definition.agent_id,
                            "strategy": "product-owned-deterministic-evidence-v1",
                            "model_calls_added": 0,
                            "tool_reexecution_allowed": False,
                            "raw_request_persisted": False,
                            "raw_evidence_persisted": False,
                            "raw_draft_persisted": False,
                        },
                        payload_schema_version="okcanvas-sandbox-answer-completion-v1",
                    )
                )
                try:
                    completion = complete_sandbox_answer_from_evidence(
                        draft=output,
                        tool_output=tool_output,
                        assessment=assessment,
                    )
                except ValueError as exc:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.ANSWER_COMPLETENESS_FAILED,
                        "Read-only Sandbox deterministic evidence completion failed",
                        retryable=False,
                        detail_type=type(exc).__name__,
                        usage=total_usage,
                        trace_id=trace_id,
                    ) from exc
                completed_assessment = assess_sandbox_answer_completeness(
                    request=request, output=completion.output, tool_output=tool_output
                )
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "agent.output.completion.completed",
                        {
                            "agent_id": definition.agent_id,
                            "strategy": "product-owned-deterministic-evidence-v1",
                            "complete": completed_assessment.complete,
                            "issue_count": len(completed_assessment.issue_codes),
                            "required_fragment_count": completion.required_fragment_count,
                            "evidence_reference_count": completion.evidence_reference_count,
                            "added_finding": completion.added_finding,
                            "removed_unverified_count": completion.removed_unverified_count,
                            "model_calls_added": 0,
                            "tool_reexecuted": False,
                            "raw_request_persisted": False,
                            "raw_evidence_persisted": False,
                            "raw_draft_persisted": False,
                        },
                        payload_schema_version="okcanvas-sandbox-answer-completion-v1",
                    )
                )
                if not completed_assessment.complete:
                    raise GenericExecutionFailure(
                        GenericExecutionErrorCode.ANSWER_COMPLETENESS_FAILED,
                        "Read-only Sandbox answer remained incomplete after deterministic evidence completion",
                        retryable=False,
                        detail_type="SandboxAnswerCompletenessError",
                        usage=total_usage,
                        trace_id=trace_id,
                    )
                output = completion.output

        return GenericGatewayRunResult(
            output=output,
            usage=total_usage,
            trace_id=trace_id,
            response_id=minimize_provider_identifier(
                final_response_id, provider_identifier_policy
            ),
            sdk_version=importlib.metadata.version("openai-agents"),
            hosted_search_evidence=hosted_search_evidence,
        )
