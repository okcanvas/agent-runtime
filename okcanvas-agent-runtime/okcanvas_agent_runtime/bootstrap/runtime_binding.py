from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.runtime.binding import AgentRuntimeBinding

from okcanvas_agent_runtime.agent.definitions import AgentDefinition, AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.capabilities.topology import AgentCapabilityTopologyCatalog, SDKExampleCatalog
from okcanvas_agent_runtime.core.config import EXPECTED_OPENAI_AGENTS_VERSION
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.agent.model.routing import ModelRoutingPolicyCatalog
from okcanvas_agent_runtime.agent.model.retry import ModelRetryPolicyCatalog
from okcanvas_agent_runtime.agent.model.reasoning_evidence import ReasoningEvidencePolicyCatalog
from okcanvas_agent_runtime.agent.model.response_storage import ResponseStoragePolicyCatalog
from okcanvas_agent_runtime.agent.model.provider_identity import ProviderIdentifierPolicyCatalog
from okcanvas_agent_runtime.agent.model.trace_export import TraceExportPolicyCatalog
from okcanvas_agent_runtime.adapters.sandbox.docker import SandboxRuntimeCatalog
from okcanvas_agent_runtime.domain.invocations import ChildAgentGraphResolver, InvocationPolicyCatalog
from okcanvas_agent_runtime.domain.attachments import LocalAttachmentPolicyCatalog, MultimodalModelPolicyCatalog
from okcanvas_agent_runtime.agent.skills import ProductSkillCatalog
from okcanvas_agent_runtime.agent.tools.hosted_search import HostedWebSearchPolicyCatalog, SDK_RESPONSES_SOURCE_SHA256, SDK_TOOL_SOURCE_SHA256, SDK_TURN_RESOLUTION_SOURCE_SHA256
from okcanvas_agent_runtime.agent.subagents.handoffs import NativeHandoffPolicyCatalog, validate_native_handoff_definitions, validate_sqlite_session_handoff_definitions
from okcanvas_agent_runtime.agent.subagents.agent_tools import AgentToolPolicyCatalog, validate_agent_tool_definitions, validate_sqlite_session_agent_tool_definitions
from okcanvas_agent_runtime.domain.sessions import SQLiteSessionApprovalPolicyCatalog, SQLiteSessionAgentToolPolicyCatalog, SQLiteSessionHandoffPolicyCatalog, SQLiteSessionGuardrailPolicyCatalog, SQLiteSessionMCPPolicyCatalog, SQLiteSessionPolicyCatalog
from okcanvas_agent_runtime.agent.guardrails import GuardrailRuntimeCatalog
from okcanvas_agent_runtime.core.governance import resolve_architecture_constitution
from okcanvas_agent_runtime.application.orchestration import BoundedOrchestrationPolicyCatalog, validate_bounded_orchestration_definitions
from okcanvas_agent_runtime.application.assistant_routing.cross_domain_session import CrossDomainSessionDelegationCatalog
from okcanvas_agent_runtime.application.organization_context import OrganizationContextSessionDelegationCatalog
from okcanvas_agent_runtime.agent.tools.function import FunctionToolApprovalMode, FunctionToolRuntimeCatalog

from okcanvas_agent_runtime.application.execution.output_registry import resolve_output_contract


def _canonical_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"Runtime implementation file is missing or unsafe: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _combined_source_sha(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        resolved = path.resolve()
        digest.update(resolved.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(resolved.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _module_file(module_name: str) -> Path:
    module = importlib.import_module(module_name)
    raw = getattr(module, "__file__", None)
    if not raw:
        raise RuntimeError(f"Runtime module has no source file: {module_name}")
    path = Path(raw).resolve()
    if path.suffix == ".pyc" and path.with_suffix(".py").is_file():
        path = path.with_suffix(".py")
    return path






class AgentRuntimeBindingCatalog:
    """Resolve the executable Runtime behavior bound to one immutable Agent definition.

    The resulting SHA is intentionally conservative. Any change to the selected output-contract
    runtime, MCP declaration/module, controlled local-Tool policy/implementation, SDK version, or
    execution engine requires a new preflight and exact confirmation.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self._mcp = MCPServerCatalog(self.project_root)
        self._capabilities = AgentCapabilityTopologyCatalog(self.project_root)
        self._sdk_examples = SDKExampleCatalog(self.project_root)
        self._hosted_web_search = HostedWebSearchPolicyCatalog(self.project_root)
        self._skills = ProductSkillCatalog(self.project_root)
        self._attachment_policy = LocalAttachmentPolicyCatalog(self.project_root)
        self._multimodal_model_policy = MultimodalModelPolicyCatalog(self.project_root)
        self._model_routing = ModelRoutingPolicyCatalog(self.project_root)
        self._model_retry = ModelRetryPolicyCatalog(self.project_root)
        self._reasoning_evidence = ReasoningEvidencePolicyCatalog(self.project_root)
        self._response_storage = ResponseStoragePolicyCatalog(self.project_root)
        self._provider_identifier = ProviderIdentifierPolicyCatalog(self.project_root)
        self._trace_export = TraceExportPolicyCatalog(self.project_root)
        self._sandbox_runtime = SandboxRuntimeCatalog(self.project_root)
        self._tools = FunctionToolRuntimeCatalog(self.project_root)
        self._guardrails = GuardrailRuntimeCatalog(self.project_root)
        self._orchestration = BoundedOrchestrationPolicyCatalog(self.project_root)
        self._invocation_policy = InvocationPolicyCatalog(self.project_root).resolve()

    def resolve(self, definition: AgentDefinition) -> AgentRuntimeBinding:
        output_runtime = resolve_output_contract(definition.output_contract)
        capability_topology = self._capabilities.resolve(definition)
        sdk_example_inventory = self._sdk_examples.resolve(require_sources=False)
        architecture_constitution = resolve_architecture_constitution()
        architecture_constitution_runtime_sha = _combined_source_sha(
            (
                _module_file("okcanvas_agent_runtime.core.governance.architecture_constitution"),
                _module_file("okcanvas_agent_runtime.core.governance.step_compliance"),
            )
        )
        capability_topology_modules = (
            "okcanvas_agent_runtime.agent.capabilities.topology.models",
            "okcanvas_agent_runtime.agent.capabilities.topology.policy",
            "okcanvas_agent_runtime.agent.capabilities.topology.catalog",
            "okcanvas_agent_runtime.agent.capabilities.topology.examples",
        )
        capability_topology_runtime_sha = _combined_source_sha(
            tuple(_module_file(name) for name in capability_topology_modules)
        )
        model_policy = self._model_routing.resolve()
        model_retry_policy = self._model_retry.resolve()
        reasoning_evidence_policy = self._reasoning_evidence.resolve()
        response_storage_policy = self._response_storage.resolve()
        provider_identifier_policy = self._provider_identifier.resolve()
        trace_export_policy = self._trace_export.resolve()
        sandbox_runtime_foundation = self._sandbox_runtime.resolve()
        self._sandbox_runtime.validate_agent_workspace_access(definition.workspace_access)
        model_provider_modules = (
            "okcanvas_agent_runtime.agent.model.routing.models",
            "okcanvas_agent_runtime.agent.model.routing.catalog",
            "okcanvas_agent_runtime.agent.model.routing.provider",
        )
        model_provider_runtime_sha = _combined_source_sha(
            tuple(_module_file(name) for name in model_provider_modules)
        )
        model_retry_modules = (
            "okcanvas_agent_runtime.agent.model.retry.models",
            "okcanvas_agent_runtime.agent.model.retry.catalog",
            "okcanvas_agent_runtime.agent.model.retry.runtime",
        )
        model_retry_runtime_sha = _combined_source_sha(
            tuple(_module_file(name) for name in model_retry_modules)
        )
        reasoning_evidence_modules = (
            "okcanvas_agent_runtime.agent.model.reasoning_evidence.models",
            "okcanvas_agent_runtime.agent.model.reasoning_evidence.catalog",
            "okcanvas_agent_runtime.agent.model.reasoning_evidence.runtime",
        )
        reasoning_evidence_runtime_sha = _combined_source_sha(
            tuple(_module_file(name) for name in reasoning_evidence_modules)
        )
        response_storage_modules = (
            "okcanvas_agent_runtime.agent.model.response_storage.models",
            "okcanvas_agent_runtime.agent.model.response_storage.catalog",
            "okcanvas_agent_runtime.agent.model.response_storage.runtime",
        )
        response_storage_runtime_sha = _combined_source_sha(
            tuple(_module_file(name) for name in response_storage_modules)
        )
        provider_identifier_modules = (
            "okcanvas_agent_runtime.agent.model.provider_identity.models",
            "okcanvas_agent_runtime.agent.model.provider_identity.catalog",
            "okcanvas_agent_runtime.agent.model.provider_identity.runtime",
        )
        provider_identifier_runtime_sha = _combined_source_sha(
            tuple(_module_file(name) for name in provider_identifier_modules)
        )
        trace_export_modules = (
            "okcanvas_agent_runtime.agent.model.trace_export.models",
            "okcanvas_agent_runtime.agent.model.trace_export.catalog",
            "okcanvas_agent_runtime.agent.model.trace_export.runtime",
        )
        trace_export_runtime_sha = _combined_source_sha(
            tuple(_module_file(name) for name in trace_export_modules)
        )
        sandbox_runtime_modules = (
            "okcanvas_agent_runtime.adapters.sandbox.docker.models",
            "okcanvas_agent_runtime.adapters.sandbox.docker.catalog",
            "okcanvas_agent_runtime.adapters.sandbox.docker.service",
            "okcanvas_agent_runtime.adapters.sandbox.docker.docker_cli",
            "okcanvas_agent_runtime.adapters.sandbox.docker.read_only_workspace",
        )
        sandbox_runtime_sha = _combined_source_sha(
            tuple(_module_file(name) for name in sandbox_runtime_modules)
        )
        skill_packages = self._skills.resolve_many(definition.skills)
        skill_entries = [item.to_binding_dict() for item in skill_packages]
        skill_modules = (
            "okcanvas_agent_runtime.agent.skills.models",
            "okcanvas_agent_runtime.agent.skills.catalog",
            "okcanvas_agent_runtime.agent.skills.runtime",
        )
        skill_runtime_sha = (
            _combined_source_sha(tuple(_module_file(name) for name in skill_modules))
            if skill_packages
            else None
        )

        hosted_tool_entries: list[dict[str, object]] = []
        hosted_tool_runtime_sha: str | None = None
        if definition.hosted_tools:
            if definition.hosted_tools != ("web-search-v1",):
                raise RuntimeError("STEP067 permits exactly one hosted Web Search Tool")
            hosted_policy = self._hosted_web_search.resolve()
            hosted_entry = hosted_policy.to_binding_dict()
            hosted_entry.update(
                {
                    "sdk_tool_source_sha256": SDK_TOOL_SOURCE_SHA256,
                    "sdk_responses_source_sha256": SDK_RESPONSES_SOURCE_SHA256,
                    "sdk_turn_resolution_source_sha256": SDK_TURN_RESOLUTION_SOURCE_SHA256,
                }
            )
            hosted_tool_entries.append(hosted_entry)
            hosted_tool_runtime_sha = _combined_source_sha(
                tuple(
                    _module_file(name)
                    for name in (
                        "okcanvas_agent_runtime.agent.tools.hosted_search.models",
                        "okcanvas_agent_runtime.agent.tools.hosted_search.catalog",
                        "okcanvas_agent_runtime.agent.tools.hosted_search.runtime",
                    )
                )
            )
        groupware_session_binding = None
        organization_context_session_binding = None
        cross_domain_session_binding = None
        if definition.agent_id == "organization-assistant-session-agent":
            cross_domain_session_binding = CrossDomainSessionDelegationCatalog(
                self.project_root
            ).resolve(definition)
        elif definition.agent_id == "organization-context-session-agent":
            organization_context_session_binding = OrganizationContextSessionDelegationCatalog(
                self.project_root
            ).resolve(definition)
        delegated_session_binding = (
            groupware_session_binding or organization_context_session_binding
        )
        mcp_server_ids = list(definition.mcp_servers)
        if cross_domain_session_binding is not None:
            mcp_server_ids.extend(item.mcp_server_id for item in cross_domain_session_binding.targets)
        elif delegated_session_binding is not None:
            mcp_server_ids.append(delegated_session_binding.mcp_server_id)
        mcp_definitions = self._mcp.resolve_many(tuple(mcp_server_ids))
        mcp_entries: list[dict[str, str]] = []
        mcp_factory_sha = _file_sha(
            _module_file("okcanvas_agent_runtime.adapters.mcp.clients.openai_factory")
        )
        for server in mcp_definitions:
            entry = {
                "server_id": server.server_id,
                "version": server.version,
                "kind": server.kind,
                "definition_sha256": server.definition_sha256,
                "factory_sha256": mcp_factory_sha,
            }
            if cross_domain_session_binding is not None:
                owner = next(
                    (item.child.agent_id for item in cross_domain_session_binding.targets if item.mcp_server_id == server.server_id),
                    None,
                )
                if owner is None:
                    raise RuntimeError("Cross-domain MCP server has no declared child owner")
                entry["owner_agent_id"] = owner
            elif delegated_session_binding is not None:
                entry["owner_agent_id"] = delegated_session_binding.child.agent_id
            if server.is_local_stdio:
                if not server.module:
                    raise RuntimeError("builtin-stdio MCP definition has no module")
                module_path = _module_file(server.module)
                entry.update(
                    {
                        "module": server.module,
                        "module_sha256": _file_sha(module_path),
                    }
                )
            elif server.is_remote_streamable_http:
                if not server.url and not server.url_template:
                    raise RuntimeError("remote Streamable HTTP MCP definition has no endpoint")
                entry.update(
                    {
                        "endpoint_mode": server.endpoint_mode,
                        "url": server.url or "",
                        "url_template": server.url_template or "",
                        "authorization_mode": server.authorization_mode,
                        "authorization_env": server.authorization_env or "",
                        "credential_ref": server.credential_ref or "",
                        "required_roles": ",".join(server.required_roles),
                        "health_mode": server.health_mode,
                        "circuit_breaker_failure_threshold": str(server.circuit_breaker_failure_threshold),
                        "circuit_breaker_reset_seconds": str(server.circuit_breaker_reset_seconds),
                        "tls_required": "true",
                        "redirects_enabled": "false",
                        "proxy_environment_enabled": "false",
                    }
                )
            else:
                raise RuntimeError("Unsupported MCP transport in Runtime binding")
            mcp_entries.append(entry)

        tool_runtimes = self._tools.resolve_many(definition.tools)
        guardrail_runtimes = self._guardrails.resolve_many(definition.guardrails)
        guardrail_entries = [item.to_binding_dict() for item in guardrail_runtimes]
        child_edges = ChildAgentGraphResolver(
            AgentDefinitionCatalog(self.project_root), self._invocation_policy
        ).resolve(definition)
        child_entries = [item.to_binding_dict() for item in child_edges]
        tool_entries = [item.to_binding_dict() for item in tool_runtimes]
        if tool_runtimes and definition.mcp_servers:
            raise RuntimeError("P0 Runtime does not mix MCP and local Function Tools")
        if definition.hosted_tools and (
            tool_runtimes
            or definition.mcp_servers
            or definition.handoffs
            or definition.agent_tools
            or definition.orchestration_children
            or definition.guardrails
            or definition.session_mode != "disabled"
        ):
            raise RuntimeError("STEP067 Hosted Web Search Runtime must be isolated")
        approval_modes = {item.approval_mode for item in tool_runtimes}
        if len(approval_modes) > 1:
            raise RuntimeError("P0 Runtime does not mix approval modes in one Agent")

        attachment_policy_payload: dict[str, object] | None = None
        multimodal_model_policy_payload: dict[str, object] | None = None
        attachment_runtime_sha: str | None = None
        handoff_policy_payload: dict[str, object] | None = None
        handoff_runtime_sha: str | None = None
        agent_tool_policy_payload: dict[str, object] | None = None
        agent_tool_runtime_sha: str | None = None
        orchestration_policy_payload: dict[str, object] | None = None
        orchestration_runtime_sha: str | None = None
        session_policy_payload: dict[str, object] | None = None
        session_runtime_sha: str | None = None
        guardrail_runtime_sha: str | None = None
        sandbox_readonly_agent = bool(
            definition.workspace_access == "sandbox-readonly-v1"
            and definition.tools == ("sandbox_project_readonly_inspect",)
            and len(tool_runtimes) == 1
            and tool_runtimes[0].factory_id == "sandbox_project_readonly_inspect_v1"
            and definition.session_mode == "disabled"
            and not definition.mcp_servers
            and not definition.hosted_tools
            and not definition.handoffs
            and not definition.agent_tools
            and not definition.orchestration_children
            and not definition.guardrails
            and not definition.skills
        )
        bounded_orchestration = bool(definition.orchestration_children)
        native_handoff = bool(
            len(definition.handoffs) == 1
            and not definition.agent_tools
            and not definition.tools
            and not definition.mcp_servers
            and definition.session_mode == "disabled"
        )
        sqlite_session_approval = bool(
            definition.session_mode == "sqlite-v1"
            and not definition.handoffs
            and not definition.agent_tools
            and len(tool_runtimes) == 1
            and approval_modes == {FunctionToolApprovalMode.ALWAYS}
            and not definition.mcp_servers
            and definition.workspace_access == "none"
        )
        sqlite_session_handoff = bool(
            definition.session_mode == "sqlite-v1"
            and len(definition.handoffs) == 1
            and not definition.agent_tools
            and not definition.tools
            and not definition.mcp_servers
            and not definition.guardrails
            and definition.workspace_access == "none"
        )
        sqlite_session_guardrail = bool(
            definition.session_mode == "sqlite-v1"
            and not definition.handoffs
            and not definition.agent_tools
            and not definition.tools
            and not definition.mcp_servers
            and bool(guardrail_runtimes)
            and all(item.kind.value in {"INPUT", "OUTPUT"} for item in guardrail_runtimes)
            and definition.workspace_access == "none"
        )
        sqlite_session_mcp = bool(
            definition.session_mode == "sqlite-v1"
            and len(definition.mcp_servers) == 1
            and not definition.handoffs
            and not definition.agent_tools
            and not definition.tools
            and not definition.guardrails
            and definition.workspace_access == "none"
        )
        sqlite_session_cross_domain_delegation = cross_domain_session_binding is not None
        sqlite_session_groupware_delegation = groupware_session_binding is not None
        sqlite_session_organization_context_delegation = (
            organization_context_session_binding is not None
        )
        sqlite_session_agent_tool = bool(
            definition.session_mode == "sqlite-v1"
            and len(definition.agent_tools) == 1
            and not definition.handoffs
            and not definition.tools
            and not definition.mcp_servers
            and not definition.guardrails
            and definition.workspace_access == "none"
        )
        sqlite_session = bool(
            definition.session_mode == "sqlite-v1"
            and not definition.handoffs
            and not definition.agent_tools
            and not definition.tools
            and not definition.mcp_servers
            and not definition.guardrails
            and definition.workspace_access == "none"
        )
        if sandbox_readonly_agent:
            if not sandbox_runtime_foundation.policy.agent_execution_enabled:
                raise RuntimeError("STEP075 Sandbox Agent execution is disabled")
            execution_path = "product-owned-readonly-sandbox-agent-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.application.execution.sandbox_answer_completeness",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.agent.tools.function.catalog",
                "okcanvas_agent_runtime.agent.tools.function.factories",
                "okcanvas_agent_runtime.agent.tools.function.implementations",
                "okcanvas_agent_runtime.adapters.workspace.tool_inspection",
                "okcanvas_agent_runtime.adapters.sandbox.docker.models",
                "okcanvas_agent_runtime.adapters.sandbox.docker.catalog",
                "okcanvas_agent_runtime.adapters.sandbox.docker.docker_cli",
                "okcanvas_agent_runtime.adapters.sandbox.docker.read_only_workspace",
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif definition.input_mode == "local-attachment-v1":
            if any((definition.tools, definition.mcp_servers, definition.hosted_tools, definition.handoffs, definition.agent_tools, definition.orchestration_children, definition.guardrails)) or definition.session_mode != "disabled":
                raise RuntimeError("STEP068 local attachment Runtime must be isolated")
            attachment_policy = self._attachment_policy.resolve()
            multimodal_model_policy = self._multimodal_model_policy.resolve()
            attachment_policy_payload = attachment_policy.to_binding_dict()
            multimodal_model_policy_payload = multimodal_model_policy.to_binding_dict()
            attachment_modules = (
                "okcanvas_agent_runtime.domain.attachments.models",
                "okcanvas_agent_runtime.domain.attachments.policy",
                "okcanvas_agent_runtime.domain.attachments.model_policy",
                "okcanvas_agent_runtime.domain.attachments.validation",
                "okcanvas_agent_runtime.adapters.storage.attachments",
            )
            attachment_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in attachment_modules)
            )
            execution_path = "bounded-local-pdf-image-input-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.submissions.lifecycle",
                "okcanvas_agent_runtime.application.submissions.protected_payload",
                "okcanvas_agent_runtime.adapters.storage.protected_payload.store",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                *attachment_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif bounded_orchestration:
            orchestration_policy = self._orchestration.resolve()
            children = tuple(
                AgentDefinitionCatalog(self.project_root).resolve(child_id)
                for child_id in definition.orchestration_children
            )
            validate_bounded_orchestration_definitions(
                root=definition, children=children, policy=orchestration_policy
            )
            orchestration_modules = (
                "okcanvas_agent_runtime.application.orchestration.models",
                "okcanvas_agent_runtime.application.orchestration.policy",
                "okcanvas_agent_runtime.application.orchestration.runtime",
                "okcanvas_agent_runtime.application.orchestration.openai_runtime",
            )
            orchestration_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in orchestration_modules)
            )
            orchestration_policy_payload = orchestration_policy.to_binding_dict()
            enriched_children: list[dict[str, object]] = []
            for ordinal, child in enumerate(children, start=1):
                child_binding = self.resolve(child)
                enriched_children.append(
                    {
                        "parent_agent_id": definition.agent_id,
                        "child_agent_id": child.agent_id,
                        "kind": "ORCHESTRATION_CHILD",
                        "depth": 1,
                        "ordinal": ordinal,
                        "child_definition_version": child.version,
                        "child_definition_sha256": child.definition_sha256,
                        "child_runtime_binding_sha256": child_binding.runtime_binding_sha256,
                        "workspace_access": child.workspace_access,
                    }
                )
            child_entries = enriched_children
            execution_path = "bounded-multi-agent-orchestration-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                *orchestration_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif sqlite_session_mcp:
            session_policy = SQLiteSessionPolicyCatalog(self.project_root).resolve()
            composition_policy = SQLiteSessionMCPPolicyCatalog(self.project_root).resolve()
            servers = mcp_definitions
            if len(servers) != 1 or not servers[0].read_only or servers[0].kind != "builtin-stdio":
                raise RuntimeError("STEP050 requires exactly one read-only builtin-stdio MCP server")
            session_modules = (
                "okcanvas_agent_runtime.domain.sessions.models",
                "okcanvas_agent_runtime.domain.sessions.policy",
                "okcanvas_agent_runtime.adapters.storage.session_history",
                "okcanvas_agent_runtime.domain.sessions.compaction",
                "okcanvas_agent_runtime.domain.sessions.mcp_policy",
                "okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service",
            )
            mcp_modules = (
                "okcanvas_agent_runtime.agent.mcp.definitions.models",
                "okcanvas_agent_runtime.agent.mcp.definitions.catalog",
                "okcanvas_agent_runtime.adapters.mcp.clients.openai_factory",
                servers[0].module,
            )
            session_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in session_modules)
            )
            session_policy_payload = {
                "sqlite_session": session_policy.to_binding_dict(),
                "mcp_composition": composition_policy.to_binding_dict(),
            }
            execution_path = "sqlite-session-native-mcp-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                *session_modules,
                *mcp_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif sqlite_session_guardrail:
            session_policy = SQLiteSessionPolicyCatalog(self.project_root).resolve()
            composition_policy = SQLiteSessionGuardrailPolicyCatalog(self.project_root).resolve()
            session_modules = (
                "okcanvas_agent_runtime.domain.sessions.models",
                "okcanvas_agent_runtime.domain.sessions.policy",
                "okcanvas_agent_runtime.adapters.storage.session_history",
                "okcanvas_agent_runtime.domain.sessions.compaction",
                "okcanvas_agent_runtime.domain.sessions.guardrail_policy",
                "okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service",
            )
            guardrail_modules = (
                "okcanvas_agent_runtime.agent.guardrails.models",
                "okcanvas_agent_runtime.agent.guardrails.catalog",
                "okcanvas_agent_runtime.agent.guardrails.runtime",
            )
            session_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in session_modules)
            )
            guardrail_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in guardrail_modules)
            )
            session_policy_payload = {
                "sqlite_session": session_policy.to_binding_dict(),
                "guardrail_composition": composition_policy.to_binding_dict(),
            }
            execution_path = "sqlite-session-native-guardrail-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                *session_modules,
                *guardrail_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif guardrail_runtimes:
            if definition.handoffs or definition.agent_tools or definition.mcp_servers or definition.session_mode != "disabled":
                raise RuntimeError("STEP044 Guardrail Runtime is Session-disabled, child-free and MCP-free")
            guardrail_modules = (
                "okcanvas_agent_runtime.agent.guardrails.models",
                "okcanvas_agent_runtime.agent.guardrails.catalog",
                "okcanvas_agent_runtime.agent.guardrails.runtime",
            )
            guardrail_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in guardrail_modules)
            )
            execution_path = "native-guardrail-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.agent.tools.function.catalog",
                "okcanvas_agent_runtime.agent.tools.function.factories",
                "okcanvas_agent_runtime.agent.tools.function.implementations",
                "okcanvas_agent_runtime.adapters.workspace.tool_inspection",
                *guardrail_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif sqlite_session_approval:
            session_policy = SQLiteSessionPolicyCatalog(self.project_root).resolve()
            composition_policy = SQLiteSessionApprovalPolicyCatalog(self.project_root).resolve()
            session_modules = (
                "okcanvas_agent_runtime.domain.sessions.models",
                "okcanvas_agent_runtime.domain.sessions.policy",
                "okcanvas_agent_runtime.adapters.storage.session_history",
                "okcanvas_agent_runtime.domain.sessions.compaction",
                "okcanvas_agent_runtime.domain.sessions.approval_policy",
                "okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service",
            )
            session_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in session_modules)
            )
            session_policy_payload = {
                "sqlite_session": session_policy.to_binding_dict(),
                "approval_composition": composition_policy.to_binding_dict(),
            }
            execution_path = "sqlite-session-approval-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.agent.tools.function.catalog",
                "okcanvas_agent_runtime.agent.tools.function.factories",
                "okcanvas_agent_runtime.agent.tools.function.implementations",
                "okcanvas_agent_runtime.adapters.workspace.tool_inspection",
                "okcanvas_agent_runtime.application.approvals.gateway",
                "okcanvas_agent_runtime.application.approvals.service",
                "okcanvas_agent_runtime.adapters.persistence.tool_approval",
                *session_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif sqlite_session_handoff:
            session_policy = SQLiteSessionPolicyCatalog(self.project_root).resolve()
            composition_policy = SQLiteSessionHandoffPolicyCatalog(self.project_root).resolve()
            handoff_policy = NativeHandoffPolicyCatalog(self.project_root).resolve()
            child = AgentDefinitionCatalog(self.project_root).resolve(definition.handoffs[0])
            validate_sqlite_session_handoff_definitions(
                parent=definition, child=child, policy=handoff_policy
            )
            if composition_policy.handoff_policy_id != handoff_policy.policy_id:
                raise RuntimeError("STEP047 Session Handoff policy identity mismatch")
            session_modules = (
                "okcanvas_agent_runtime.domain.sessions.models",
                "okcanvas_agent_runtime.domain.sessions.policy",
                "okcanvas_agent_runtime.adapters.storage.session_history",
                "okcanvas_agent_runtime.domain.sessions.compaction",
                "okcanvas_agent_runtime.domain.sessions.handoff_policy",
                "okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service",
            )
            handoff_modules = (
                "okcanvas_agent_runtime.agent.subagents.handoffs.models",
                "okcanvas_agent_runtime.agent.subagents.handoffs.policy",
                "okcanvas_agent_runtime.agent.subagents.handoffs.runtime",
            )
            session_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in session_modules)
            )
            handoff_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in handoff_modules)
            )
            session_policy_payload = {
                "sqlite_session": session_policy.to_binding_dict(),
                "handoff_composition": composition_policy.to_binding_dict(),
            }
            handoff_policy_payload = handoff_policy.to_binding_dict()
            execution_path = "sqlite-session-native-handoff-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                *session_modules,
                *handoff_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif sqlite_session_cross_domain_delegation:
            assert cross_domain_session_binding is not None
            session_policy = SQLiteSessionPolicyCatalog(self.project_root).resolve()
            composition_policy = cross_domain_session_binding.policy
            session_modules = (
                "okcanvas_agent_runtime.domain.sessions.models",
                "okcanvas_agent_runtime.domain.sessions.policy",
                "okcanvas_agent_runtime.adapters.storage.session_history",
                "okcanvas_agent_runtime.domain.sessions.compaction",
                "okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service",
            )
            cross_domain_modules = (
                "okcanvas_agent_runtime.application.assistant_routing.cross_domain_session",
                "okcanvas_agent_runtime.application.groupware_read.models",
                "okcanvas_agent_runtime.application.groupware_read.catalog",
                "okcanvas_agent_runtime.application.groupware_read.request_execution",
                "okcanvas_agent_runtime.application.organization_context.remote_models",
                "okcanvas_agent_runtime.application.organization_context.remote_catalog",
                "okcanvas_agent_runtime.application.organization_context.request_execution",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.runtime",
                "okcanvas_agent_runtime.adapters.mcp.clients.openai_factory",
                "okcanvas_agent_runtime.application.mcp_access.catalog",
            )
            session_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in session_modules)
            )
            agent_tool_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in cross_domain_modules)
            )
            session_policy_payload = {
                "sqlite_session": session_policy.to_binding_dict(),
                "cross_domain_session_delegation": composition_policy.to_binding_dict(),
            }
            agent_tool_policy_payload = composition_policy.to_binding_dict()
            execution_path = "sqlite-session-bounded-cross-domain-read-subagent-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.application.invocations.service",
                *session_modules,
                *cross_domain_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif sqlite_session_organization_context_delegation:
            assert organization_context_session_binding is not None
            session_policy = SQLiteSessionPolicyCatalog(self.project_root).resolve()
            composition_policy = organization_context_session_binding.policy
            session_modules = (
                "okcanvas_agent_runtime.domain.sessions.models",
                "okcanvas_agent_runtime.domain.sessions.policy",
                "okcanvas_agent_runtime.adapters.storage.session_history",
                "okcanvas_agent_runtime.domain.sessions.compaction",
                "okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service",
            )
            organization_context_modules = (
                "okcanvas_agent_runtime.application.organization_context.remote_models",
                "okcanvas_agent_runtime.application.organization_context.remote_catalog",
                "okcanvas_agent_runtime.application.organization_context.remote_session_delegation",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.runtime",
                "okcanvas_agent_runtime.adapters.mcp.clients.openai_factory",
                "okcanvas_agent_runtime.application.mcp_access.catalog",
            )
            session_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in session_modules)
            )
            agent_tool_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in organization_context_modules)
            )
            session_policy_payload = {
                "sqlite_session": session_policy.to_binding_dict(),
                "organization_context_session_delegation": composition_policy.to_binding_dict(),
            }
            agent_tool_policy_payload = composition_policy.to_binding_dict()
            execution_path = "sqlite-session-stateless-organization-context-subagent-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.application.invocations.service",
                *session_modules,
                *organization_context_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif sqlite_session_groupware_delegation:
            assert groupware_session_binding is not None
            session_policy = SQLiteSessionPolicyCatalog(self.project_root).resolve()
            composition_policy = groupware_session_binding.policy
            session_modules = (
                "okcanvas_agent_runtime.domain.sessions.models",
                "okcanvas_agent_runtime.domain.sessions.policy",
                "okcanvas_agent_runtime.adapters.storage.session_history",
                "okcanvas_agent_runtime.domain.sessions.compaction",
                "okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service",
            )
            groupware_modules = (
                "okcanvas_agent_runtime.application.groupware_read.models",
                "okcanvas_agent_runtime.application.groupware_read.catalog",
                "okcanvas_agent_runtime.application.groupware_read.session_delegation",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.runtime",
                "okcanvas_agent_runtime.adapters.mcp.clients.openai_factory",
                "okcanvas_agent_runtime.application.mcp_access.catalog",
            )
            session_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in session_modules)
            )
            agent_tool_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in groupware_modules)
            )
            session_policy_payload = {
                "sqlite_session": session_policy.to_binding_dict(),
                "groupware_session_delegation": composition_policy.to_binding_dict(),
            }
            agent_tool_policy_payload = composition_policy.to_binding_dict()
            execution_path = "sqlite-session-stateless-groupware-subagent-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.application.invocations.service",
                *session_modules,
                *groupware_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif sqlite_session_agent_tool:
            session_policy = SQLiteSessionPolicyCatalog(self.project_root).resolve()
            composition_policy = SQLiteSessionAgentToolPolicyCatalog(self.project_root).resolve()
            agent_tool_policy = AgentToolPolicyCatalog(self.project_root).resolve()
            child = AgentDefinitionCatalog(self.project_root).resolve(definition.agent_tools[0])
            validate_sqlite_session_agent_tool_definitions(
                parent=definition, child=child, policy=agent_tool_policy
            )
            if composition_policy.agent_tool_policy_id != agent_tool_policy.policy_id:
                raise RuntimeError("STEP049 Session Agent-as-Tool policy identity mismatch")
            session_modules = (
                "okcanvas_agent_runtime.domain.sessions.models",
                "okcanvas_agent_runtime.domain.sessions.policy",
                "okcanvas_agent_runtime.adapters.storage.session_history",
                "okcanvas_agent_runtime.domain.sessions.compaction",
                "okcanvas_agent_runtime.domain.sessions.agent_tool_policy",
                "okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service",
            )
            agent_tool_modules = (
                "okcanvas_agent_runtime.agent.subagents.agent_tools.models",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.policy",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.runtime",
            )
            session_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in session_modules)
            )
            agent_tool_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in agent_tool_modules)
            )
            session_policy_payload = {
                "sqlite_session": session_policy.to_binding_dict(),
                "agent_tool_composition": composition_policy.to_binding_dict(),
            }
            agent_tool_policy_payload = agent_tool_policy.to_binding_dict()
            execution_path = "sqlite-session-native-agent-tool-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.application.invocations.service",
                *session_modules,
                *agent_tool_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif sqlite_session:
            session_policy = SQLiteSessionPolicyCatalog(self.project_root).resolve()
            session_modules = (
                "okcanvas_agent_runtime.domain.sessions.models",
                "okcanvas_agent_runtime.domain.sessions.policy",
                "okcanvas_agent_runtime.adapters.storage.session_history",
                "okcanvas_agent_runtime.domain.sessions.compaction",
                "okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service",
            )
            session_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in session_modules)
            )
            session_policy_payload = session_policy.to_binding_dict()
            execution_path = "sqlite-session-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                *session_modules,
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif native_handoff:
            handoff_policy = NativeHandoffPolicyCatalog(self.project_root).resolve()
            child = AgentDefinitionCatalog(self.project_root).resolve(definition.handoffs[0])
            validate_native_handoff_definitions(
                parent=definition, child=child, policy=handoff_policy
            )
            handoff_modules = (
                "okcanvas_agent_runtime.agent.subagents.handoffs.models",
                "okcanvas_agent_runtime.agent.subagents.handoffs.policy",
                "okcanvas_agent_runtime.agent.subagents.handoffs.runtime",
            )
            handoff_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in handoff_modules)
            )
            handoff_policy_payload = handoff_policy.to_binding_dict()
            execution_path = "native-handoff-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.agent.subagents.handoffs.models",
                "okcanvas_agent_runtime.agent.subagents.handoffs.policy",
                "okcanvas_agent_runtime.agent.subagents.handoffs.runtime",
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif (
            len(definition.agent_tools) == 1
            and not definition.handoffs
            and not definition.tools
            and not definition.mcp_servers
            and definition.session_mode == "disabled"
        ):
            agent_tool_policy = AgentToolPolicyCatalog(self.project_root).resolve()
            child = AgentDefinitionCatalog(self.project_root).resolve(definition.agent_tools[0])
            validate_agent_tool_definitions(
                parent=definition, child=child, policy=agent_tool_policy
            )
            agent_tool_modules = (
                "okcanvas_agent_runtime.agent.subagents.agent_tools.models",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.policy",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.runtime",
            )
            agent_tool_runtime_sha = _combined_source_sha(
                tuple(_module_file(name) for name in agent_tool_modules)
            )
            agent_tool_policy_payload = agent_tool_policy.to_binding_dict()
            execution_path = "agent-as-tool-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.models",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.policy",
                "okcanvas_agent_runtime.agent.subagents.agent_tools.runtime",
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif definition.handoffs or definition.agent_tools:
            execution_path = "sub-agent-invocation-scope-only-v1"
            engine_modules = (
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif tool_runtimes and approval_modes == {FunctionToolApprovalMode.ALWAYS}:
            if len(tool_runtimes) != 1:
                raise RuntimeError("P0 approval Runtime permits exactly one Function Tool")
            execution_path = "governed-function-tool-approval-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.agent.tools.function.catalog",
                "okcanvas_agent_runtime.agent.tools.function.factories",
                "okcanvas_agent_runtime.agent.tools.function.implementations",
                "okcanvas_agent_runtime.adapters.workspace.tool_inspection",
                "okcanvas_agent_runtime.application.approvals.gateway",
                "okcanvas_agent_runtime.application.approvals.service",
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif tool_runtimes:
            execution_path = "generic-function-tool-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.agent.tools.function.catalog",
                "okcanvas_agent_runtime.agent.tools.function.factories",
                "okcanvas_agent_runtime.agent.tools.function.implementations",
                "okcanvas_agent_runtime.adapters.workspace.tool_inspection",
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif definition.hosted_tools:
            execution_path = "hosted-web-search-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.agent.tools.hosted_search.models",
                "okcanvas_agent_runtime.agent.tools.hosted_search.catalog",
                "okcanvas_agent_runtime.agent.tools.hosted_search.runtime",
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        elif mcp_definitions and mcp_definitions[0].is_remote_streamable_http:
            execution_path = (
                "multi-remote-mcp-delegated-identity-execution-v1"
                if any(item.requires_delegated_identity for item in mcp_definitions)
                else "remote-mcp-streamable-http-execution-v1"
            )
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.agent.mcp.definitions.models",
                "okcanvas_agent_runtime.agent.mcp.definitions.catalog",
                "okcanvas_agent_runtime.adapters.mcp.clients.openai_factory",
                "okcanvas_agent_runtime.application.mcp_access.models",
                "okcanvas_agent_runtime.application.mcp_access.catalog",
                "okcanvas_agent_runtime.application.mcp_access.service",
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
            )
        else:
            execution_path = "generic-agent-execution-v1"
            engine_modules = (
                "okcanvas_agent_runtime.application.submissions.service",
                "okcanvas_agent_runtime.application.submissions.execution",
                "okcanvas_agent_runtime.application.execution.service",
                "okcanvas_agent_runtime.adapters.openai.generic_gateway",
                "okcanvas_agent_runtime.adapters.streaming.adapter",
                "okcanvas_agent_runtime.adapters.streaming.broker",
                "okcanvas_agent_runtime.application.execution.output_registry",
                "okcanvas_agent_runtime.bootstrap.runtime_binding",
                "okcanvas_agent_runtime.adapters.mcp.clients.openai_factory",
            )
        invocation_modules = (
            "okcanvas_agent_runtime.domain.invocations.models",
            "okcanvas_agent_runtime.domain.invocations.policy",
            "okcanvas_agent_runtime.agent.subagents.invocation_graph",
            "okcanvas_agent_runtime.application.invocations.service",
            "okcanvas_agent_runtime.adapters.workspace.invocation_workspace",
        )
        invocation_scope_runtime_sha = _combined_source_sha(
            tuple(_module_file(name) for name in invocation_modules)
        )
        engine_modules = (
            *engine_modules,
            *invocation_modules,
            *model_provider_modules,
            *model_retry_modules,
            *reasoning_evidence_modules,
            *response_storage_modules,
            *provider_identifier_modules,
            *trace_export_modules,
            *sandbox_runtime_modules,
            *(skill_modules if skill_packages else ()),
        )
        engine_sha = _combined_source_sha(tuple(_module_file(name) for name in engine_modules))
        canonical = {
            "schema_version": "okcanvas-agent-runtime-binding-v1",
            "agent_definition_id": definition.agent_id,
            "agent_definition_version": definition.version,
            "agent_definition_sha256": definition.definition_sha256,
            "execution_path": execution_path,
            "sdk_package": "openai-agents",
            "sdk_version": EXPECTED_OPENAI_AGENTS_VERSION,
            "capability_topology": capability_topology.to_public_dict(),
            "capability_topology_runtime_sha256": capability_topology_runtime_sha,
            "sdk_example_inventory_sha256": sdk_example_inventory.inventory_sha256,
            "architecture_constitution": architecture_constitution.to_public_dict(),
            "architecture_constitution_runtime_sha256": architecture_constitution_runtime_sha,
            "model_routing_policy": model_policy.to_binding_dict(),
            "model_provider_runtime_sha256": model_provider_runtime_sha,
            "model_retry_policy": model_retry_policy.to_binding_dict(),
            "model_retry_runtime_sha256": model_retry_runtime_sha,
            "reasoning_evidence_policy": reasoning_evidence_policy.to_binding_dict(),
            "reasoning_evidence_runtime_sha256": reasoning_evidence_runtime_sha,
            "response_storage_policy": response_storage_policy.to_binding_dict(),
            "response_storage_runtime_sha256": response_storage_runtime_sha,
            "provider_identifier_policy": provider_identifier_policy.to_binding_dict(),
            "provider_identifier_runtime_sha256": provider_identifier_runtime_sha,
            "trace_export_policy": trace_export_policy.to_binding_dict(),
            "trace_export_runtime_sha256": trace_export_runtime_sha,
            "sandbox_runtime_foundation": sandbox_runtime_foundation.to_binding_dict(),
            "sandbox_runtime_sha256": sandbox_runtime_sha,
            "output_contract": definition.output_contract,
            "output_contract_runtime_sha256": output_runtime.definition_sha256,
            "input_mode": definition.input_mode,
            "attachment_policy": attachment_policy_payload,
            "multimodal_model_policy": multimodal_model_policy_payload,
            "attachment_runtime_sha256": attachment_runtime_sha,
            "mcp_servers": mcp_entries,
            "hosted_tools": hosted_tool_entries,
            "hosted_tool_runtime_sha256": hosted_tool_runtime_sha,
            "skills": skill_entries,
            "skill_runtime_sha256": skill_runtime_sha,
            "local_tools": tool_entries,
            "child_agents": child_entries,
            "invocation_policy": self._invocation_policy.to_binding_dict(),
            "invocation_scope_runtime_sha256": invocation_scope_runtime_sha,
            "handoff_policy": handoff_policy_payload,
            "handoff_runtime_sha256": handoff_runtime_sha,
            "agent_tool_policy": agent_tool_policy_payload,
            "agent_tool_runtime_sha256": agent_tool_runtime_sha,
            "orchestration_policy": orchestration_policy_payload,
            "orchestration_runtime_sha256": orchestration_runtime_sha,
            "session_policy": session_policy_payload,
            "session_runtime_sha256": session_runtime_sha,
            "guardrails": guardrail_entries,
            "guardrail_runtime_sha256": guardrail_runtime_sha,
            "execution_engine_sha256": engine_sha,
        }
        digest = _canonical_sha(canonical)
        return AgentRuntimeBinding(
            schema_version=str(canonical["schema_version"]),
            agent_definition_id=definition.agent_id,
            agent_definition_version=definition.version,
            agent_definition_sha256=definition.definition_sha256,
            execution_path=execution_path,
            sdk_package="openai-agents",
            sdk_version=EXPECTED_OPENAI_AGENTS_VERSION,
            capability_topology=capability_topology.to_public_dict(),
            capability_topology_runtime_sha256=capability_topology_runtime_sha,
            sdk_example_inventory_sha256=sdk_example_inventory.inventory_sha256,
            architecture_constitution=architecture_constitution.to_public_dict(),
            architecture_constitution_runtime_sha256=architecture_constitution_runtime_sha,
            model_routing_policy=model_policy.to_binding_dict(),
            model_provider_runtime_sha256=model_provider_runtime_sha,
            model_retry_policy=model_retry_policy.to_binding_dict(),
            model_retry_runtime_sha256=model_retry_runtime_sha,
            reasoning_evidence_policy=reasoning_evidence_policy.to_binding_dict(),
            reasoning_evidence_runtime_sha256=reasoning_evidence_runtime_sha,
            response_storage_policy=response_storage_policy.to_binding_dict(),
            response_storage_runtime_sha256=response_storage_runtime_sha,
            provider_identifier_policy=provider_identifier_policy.to_binding_dict(),
            provider_identifier_runtime_sha256=provider_identifier_runtime_sha,
            trace_export_policy=trace_export_policy.to_binding_dict(),
            trace_export_runtime_sha256=trace_export_runtime_sha,
            sandbox_runtime_foundation=sandbox_runtime_foundation.to_binding_dict(),
            sandbox_runtime_sha256=sandbox_runtime_sha,
            output_contract=definition.output_contract,
            output_contract_runtime_sha256=output_runtime.definition_sha256,
            input_mode=definition.input_mode,
            attachment_policy=attachment_policy_payload,
            multimodal_model_policy=multimodal_model_policy_payload,
            attachment_runtime_sha256=attachment_runtime_sha,
            mcp_servers=tuple(mcp_entries),
            hosted_tools=tuple(hosted_tool_entries),
            hosted_tool_runtime_sha256=hosted_tool_runtime_sha,
            skills=tuple(skill_entries),
            skill_runtime_sha256=skill_runtime_sha,
            local_tools=tuple(tool_entries),
            child_agents=tuple(child_entries),
            invocation_policy=self._invocation_policy.to_binding_dict(),
            invocation_scope_runtime_sha256=invocation_scope_runtime_sha,
            handoff_policy=handoff_policy_payload,
            handoff_runtime_sha256=handoff_runtime_sha,
            agent_tool_policy=agent_tool_policy_payload,
            agent_tool_runtime_sha256=agent_tool_runtime_sha,
            orchestration_policy=orchestration_policy_payload,
            orchestration_runtime_sha256=orchestration_runtime_sha,
            session_policy=session_policy_payload,
            session_runtime_sha256=session_runtime_sha,
            guardrails=tuple(guardrail_entries),
            guardrail_runtime_sha256=guardrail_runtime_sha,
            execution_engine_sha256=engine_sha,
            runtime_binding_sha256=digest,
        )
