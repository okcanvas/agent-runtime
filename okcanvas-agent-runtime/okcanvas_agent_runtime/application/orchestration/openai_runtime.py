from __future__ import annotations

import asyncio
import importlib.metadata
from dataclasses import dataclass
from typing import Any

from okcanvas_agent_runtime.agent.definitions import AgentDefinition, AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import EXPECTED_OPENAI_AGENTS_VERSION, RuntimeSettings
from okcanvas_agent_runtime.core.contracts import CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionErrorCode, GenericGatewayRunResult, GatewayLifecycleEvent
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.application.execution.gateway import LifecycleSink
from okcanvas_agent_runtime.application.execution.output_registry import normalize_output, resolve_output_contract
from okcanvas_agent_runtime.agent.model.retry import ModelRetryPolicyCatalog, ModelRetryPolicyError, build_sdk_model_retry_settings
from okcanvas_agent_runtime.agent.model.routing import ModelRoutingError, ModelRoutingPolicyCatalog, PinnedOpenAIResponsesProvider
from okcanvas_agent_runtime.agent.model.provider_identity import ProviderIdentifierPolicyCatalog, ProviderIdentifierPolicyError, provider_identifier_presence
from okcanvas_agent_runtime.agent.model.reasoning_evidence import ReasoningEvidencePolicyCatalog, ReasoningEvidencePolicyError, build_sdk_reasoning_model_settings_kwargs, count_reasoning_items
from okcanvas_agent_runtime.agent.skills import resolve_effective_instructions
from okcanvas_agent_runtime.agent.model.trace_export import TraceExportPolicyCatalog, TraceExportPolicyError, build_sdk_trace_run_config_kwargs
from okcanvas_agent_runtime.agent.model.response_storage import ResponseStoragePolicyCatalog, ResponseStoragePolicyError, build_sdk_response_storage_model_settings_kwargs

from okcanvas_agent_runtime.application.orchestration.models import BoundedOrchestrationPolicy
from okcanvas_agent_runtime.application.orchestration.runtime import aggregate_child_results, sum_usage, validate_bounded_orchestration_definitions


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


@dataclass(frozen=True)
class _ChildSuccess:
    ordinal: int
    definition: AgentDefinition
    output: CodingAgentResult
    usage: UsageSummary


class _ChildExecutionFailure(Exception):
    def __init__(self, ordinal: int, failure: GenericExecutionFailure) -> None:
        super().__init__(failure.public_message)
        self.ordinal = ordinal
        self.failure = failure


async def run_openai_bounded_orchestration(
    *,
    root_definition: AgentDefinition,
    request: str,
    run_id: str,
    settings: RuntimeSettings,
    lifecycle_sink: LifecycleSink,
    policy: BoundedOrchestrationPolicy,
) -> GenericGatewayRunResult:
    assert settings.model is not None
    assert settings.api_key is not None
    project_root = root_definition.definition_path.parents[3]
    definitions = AgentDefinitionCatalog(project_root)
    children = tuple(
        definitions.resolve(agent_id) for agent_id in root_definition.orchestration_children
    )
    validate_bounded_orchestration_definitions(
        root=root_definition, children=children, policy=policy
    )

    try:
        from agents import Agent, ModelSettings, RunConfig, RunHooks, Runner, gen_trace_id, set_default_openai_key
    except (ImportError, ModuleNotFoundError) as exc:
        raise GenericExecutionFailure(
            GenericExecutionErrorCode.SDK_NOT_INSTALLED,
            f"openai-agents=={EXPECTED_OPENAI_AGENTS_VERSION} is not installed",
            detail_type=type(exc).__name__,
        ) from exc

    try:
        model_route = ModelRoutingPolicyCatalog(project_root).resolve_model(settings.model)
        model_retry_policy = ModelRetryPolicyCatalog(project_root).resolve()
        model_retry_settings = build_sdk_model_retry_settings(model_retry_policy)
        reasoning_policy = ReasoningEvidencePolicyCatalog(project_root).resolve()
        reasoning_settings = build_sdk_reasoning_model_settings_kwargs(reasoning_policy)
        storage_policy = ResponseStoragePolicyCatalog(project_root).resolve()
        storage_settings = build_sdk_response_storage_model_settings_kwargs(storage_policy)
        provider_identifier_policy = ProviderIdentifierPolicyCatalog(project_root).resolve()
        trace_export_policy = TraceExportPolicyCatalog(project_root).resolve()
        trace_run_config_settings = build_sdk_trace_run_config_kwargs(trace_export_policy)
    except (
        ModelRoutingError,
        ModelRetryPolicyError,
        ReasoningEvidencePolicyError,
        ResponseStoragePolicyError,
        ProviderIdentifierPolicyError,
        TraceExportPolicyError,
    ) as exc:
        raise GenericExecutionFailure(
            GenericExecutionErrorCode.MODEL_ROUTE_DENIED,
            "Bounded orchestration model policy is outside the immutable Runtime route",
            detail_type=type(exc).__name__,
        ) from exc

    trace_id = gen_trace_id()
    set_default_openai_key(settings.api_key)
    model_provider = PinnedOpenAIResponsesProvider(
        route=model_route,
        retry_policy=model_retry_policy,
        api_key=settings.api_key,
    )
    child_output_runtime = resolve_output_contract(policy.child_output_contract)
    usage_by_ordinal: dict[int, UsageSummary] = {}

    await lifecycle_sink(
        GatewayLifecycleEvent(
            "orchestration.started",
            {
                "root_agent_id": root_definition.agent_id,
                "child_agent_ids": [item.agent_id for item in children],
                "child_count": policy.child_count,
                "max_parallelism": policy.max_parallelism,
                "max_depth": policy.max_depth,
                "failure_mode": policy.failure_mode,
                "cancellation_mode": policy.cancellation_mode,
                "aggregation_mode": policy.aggregation_mode,
                "request_persisted": False,
                "workspace_access": policy.workspace_access,
            },
            payload_schema_version="okcanvas-bounded-orchestration-started-v1",
        )
    )

    # Child invocation start order is product-owned and deterministic even though model execution is parallel.
    for ordinal, child in enumerate(children, start=1):
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "orchestration.child.started",
                {
                    "ordinal": ordinal,
                    "agent_id": child.agent_id,
                    "agent_definition_version": child.version,
                    "agent_definition_sha256": child.definition_sha256,
                    "skill_ids": list(child.skills),
                    "workspace_access": child.workspace_access,
                    "workspace_materialized": False,
                    "session_mode": child.session_mode,
                },
                payload_schema_version="okcanvas-bounded-orchestration-child-started-v1",
            )
        )

    async def run_child(ordinal: int, definition: AgentDefinition) -> _ChildSuccess:
        sdk_agent: Any | None = None

        class ChildRunHooks(RunHooks):
            async def on_agent_start(self, context, agent) -> None:  # type: ignore[no-untyped-def]
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "agent.started",
                        {
                            "agent_id": definition.agent_id,
                            "orchestration_ordinal": ordinal,
                        },
                    )
                )

            async def on_llm_start(  # type: ignore[no-untyped-def]
                self, context, agent, system_prompt, input_items
            ) -> None:
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "model.started",
                        {
                            "agent_id": definition.agent_id,
                            "orchestration_ordinal": ordinal,
                            **model_route.to_safe_event_dict(),
                            "runner_managed_max_retries": model_retry_policy.runner_managed_max_retries,
                            "provider_managed_max_retries": model_retry_policy.provider_managed_max_retries,
                            "reasoning_summary_requested": reasoning_policy.reasoning_summary_requested,
                            "reasoning_content_persisted": False,
                            "response_store_requested": storage_policy.response_store_requested,
                        },
                    )
                )

            async def on_llm_end(self, context, agent, response) -> None:  # type: ignore[no-untyped-def]
                usage = _usage_summary(getattr(context, "usage", None))
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "model.completed",
                        {
                            "agent_id": definition.agent_id,
                            "orchestration_ordinal": ordinal,
                            "usage": usage.model_dump(mode="json"),
                            "reasoning_item_count": count_reasoning_items(response),
                            "reasoning_content_persisted": False,
                            "response_id_present": provider_identifier_presence(
                                getattr(response, "response_id", None),
                                provider_identifier_policy,
                            ),
                            "request_id_present": provider_identifier_presence(
                                getattr(response, "request_id", None),
                                provider_identifier_policy,
                            ),
                        },
                    )
                )

            async def on_agent_end(self, context, agent, output) -> None:  # type: ignore[no-untyped-def]
                await lifecycle_sink(
                    GatewayLifecycleEvent(
                        "agent.completed",
                        {
                            "agent_id": definition.agent_id,
                            "orchestration_ordinal": ordinal,
                            "output_persisted_in_event": False,
                        },
                    )
                )

        try:
            sdk_agent = Agent(
                name=definition.name,
                instructions=resolve_effective_instructions(definition),
                model=settings.model,
                tools=[],
                mcp_servers=[],
                handoffs=[],
                output_type=child_output_runtime.output_type,
            )
            run_config = RunConfig(
                model=settings.model,
                model_provider=model_provider,
                model_settings=ModelSettings(
                    retry=model_retry_settings,
                    **reasoning_settings,
                    **storage_settings,
                ),
                workflow_name=definition.workflow_name,
                trace_id=trace_id,
                group_id=run_id,
                **trace_run_config_settings,
                trace_metadata={
                    "run_id": run_id,
                    "invocation_kind": "ORCHESTRATION_CHILD",
                    "orchestration_root_agent_id": root_definition.agent_id,
                    "orchestration_ordinal": ordinal,
                    "agent_definition_id": definition.agent_id,
                    "agent_definition_version": definition.version,
                    "agent_definition_sha256": definition.definition_sha256,
                    "skill_ids": list(definition.skills),
                    "orchestration_policy_id": policy.policy_id,
                    "orchestration_policy_sha256": policy.policy_sha256,
                    "model_route_id": model_route.policy.route_id,
                    "model_routing_policy_sha256": model_route.policy.policy_sha256,
                    "model_retry_policy_sha256": model_retry_policy.policy_sha256,
                    "reasoning_evidence_policy_sha256": reasoning_policy.policy_sha256,
                    "response_storage_policy_sha256": storage_policy.policy_sha256,
                    "provider_identifier_policy_sha256": provider_identifier_policy.policy_sha256,
                    "provider_response_id_persisted": False,
                    "provider_request_id_persisted": False,
                    "trace_export_policy_id": trace_export_policy.policy_id,
                    "trace_export_policy_sha256": trace_export_policy.policy_sha256,
                    "provider_trace_export_enabled": False,
                    "session_mode": "disabled",
                    "workspace_access": "none",
                },
            )
            result = await Runner.run(
                sdk_agent,
                request,
                max_turns=definition.max_turns,
                hooks=ChildRunHooks(),
                run_config=run_config,
                session=None,
            )
            output = result.final_output_as(
                child_output_runtime.output_type, raise_if_incorrect_type=True
            )
            normalized = normalize_output(policy.child_output_contract, output)
            if not isinstance(normalized, CodingAgentResult):
                raise GenericExecutionFailure(
                    GenericExecutionErrorCode.OUTPUT_CONTRACT_INVALID,
                    "Orchestration child output did not match CodingAgentResult",
                    detail_type=type(normalized).__name__,
                )
            usage = _usage_summary(result.context_wrapper.usage)
            usage_by_ordinal[ordinal] = usage
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "orchestration.child.completed",
                    {
                        "ordinal": ordinal,
                        "agent_id": definition.agent_id,
                        "usage": usage.model_dump(mode="json"),
                        "output_contract": policy.child_output_contract,
                        "output_persisted_in_event": False,
                    },
                    payload_schema_version="okcanvas-bounded-orchestration-child-completed-v1",
                )
            )
            return _ChildSuccess(ordinal, definition, normalized, usage)
        except asyncio.CancelledError:
            usage = usage_by_ordinal.get(ordinal, UsageSummary())
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "orchestration.child.cancelled",
                    {
                        "ordinal": ordinal,
                        "agent_id": definition.agent_id,
                        "usage": usage.model_dump(mode="json"),
                        "reason": "SIBLING_FAILURE",
                        "raw_error_persisted": False,
                    },
                    payload_schema_version="okcanvas-bounded-orchestration-child-cancelled-v1",
                )
            )
            raise
        except GenericExecutionFailure as failure:
            usage = failure.usage or UsageSummary()
            usage_by_ordinal[ordinal] = usage
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "orchestration.child.failed",
                    {
                        "ordinal": ordinal,
                        "agent_id": definition.agent_id,
                        "code": failure.code.value,
                        "retryable": failure.retryable,
                        "detail_type": failure.detail_type,
                        "usage": usage.model_dump(mode="json"),
                        "raw_error_persisted": False,
                    },
                    payload_schema_version="okcanvas-bounded-orchestration-child-failed-v1",
                )
            )
            raise _ChildExecutionFailure(ordinal, failure) from failure
        except Exception as exc:
            failure = GenericExecutionFailure(
                GenericExecutionErrorCode.SDK_RUN_FAILED,
                "Bounded orchestration child SDK run failed",
                retryable=True,
                detail_type=type(exc).__name__,
            )
            usage_by_ordinal[ordinal] = UsageSummary()
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "orchestration.child.failed",
                    {
                        "ordinal": ordinal,
                        "agent_id": definition.agent_id,
                        "code": failure.code.value,
                        "retryable": failure.retryable,
                        "detail_type": failure.detail_type,
                        "usage": UsageSummary().model_dump(mode="json"),
                        "raw_error_persisted": False,
                    },
                    payload_schema_version="okcanvas-bounded-orchestration-child-failed-v1",
                )
            )
            raise _ChildExecutionFailure(ordinal, failure) from exc

    task_ordinals: dict[asyncio.Task[_ChildSuccess], int] = {}
    for ordinal, child in enumerate(children, start=1):
        task = asyncio.create_task(
            run_child(ordinal, child), name=f"orchestration-child-{ordinal}"
        )
        task_ordinals[task] = ordinal
    tasks = list(task_ordinals)
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        failures: list[_ChildExecutionFailure] = []
        for task in done:
            ordinal = task_ordinals[task]
            if task.cancelled():
                failures.append(
                    _ChildExecutionFailure(
                        ordinal,
                        GenericExecutionFailure(
                            GenericExecutionErrorCode.SDK_RUN_FAILED,
                            "Bounded orchestration child was cancelled unexpectedly",
                            retryable=True,
                        ),
                    )
                )
                continue
            exc = task.exception()
            if isinstance(exc, _ChildExecutionFailure):
                failures.append(exc)
            elif isinstance(exc, GenericExecutionFailure):
                failures.append(_ChildExecutionFailure(ordinal, exc))
            elif exc is not None:
                failures.append(
                    _ChildExecutionFailure(
                        ordinal,
                        GenericExecutionFailure(
                            GenericExecutionErrorCode.SDK_RUN_FAILED,
                            "Bounded orchestration child SDK run failed",
                            retryable=True,
                            detail_type=type(exc).__name__,
                        ),
                    )
                )
        failures.sort(key=lambda item: item.ordinal)
        if failures:
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            # Retrieve all completed task exceptions to avoid background warnings.
            for task in done:
                if not task.cancelled():
                    task.exception()
            failure = failures[0].failure
            usage = sum_usage(tuple(usage_by_ordinal[index] for index in sorted(usage_by_ordinal)))
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "orchestration.failed",
                    {
                        "root_agent_id": root_definition.agent_id,
                        "failed_ordinal": failures[0].ordinal,
                        "failure_mode": policy.failure_mode,
                        "cancellation_mode": policy.cancellation_mode,
                        "usage": usage.model_dump(mode="json"),
                        "artifact_created": False,
                    },
                    payload_schema_version="okcanvas-bounded-orchestration-failed-v1",
                )
            )
            raise GenericExecutionFailure(
                failure.code,
                failure.public_message,
                retryable=failure.retryable,
                detail_type=failure.detail_type,
                usage=usage,
                trace_id=trace_id,
            )
        successes = await asyncio.gather(*tasks)
        ordered = sorted(successes, key=lambda item: item.ordinal)
        aggregate = aggregate_child_results(
            children=tuple(
                (item.ordinal, item.definition, item.output, item.usage) for item in ordered
            ),
            policy=policy,
        )
        total_usage = sum_usage(tuple(item.usage for item in ordered))
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "orchestration.completed",
                {
                    "root_agent_id": root_definition.agent_id,
                    "child_agent_ids": [item.definition.agent_id for item in ordered],
                    "child_count": len(ordered),
                    "aggregation_mode": policy.aggregation_mode,
                    "aggregate_status": aggregate.status.value,
                    "usage": total_usage.model_dump(mode="json"),
                    "child_output_persisted_in_event": False,
                },
                payload_schema_version="okcanvas-bounded-orchestration-completed-v1",
            )
        )
        return GenericGatewayRunResult(
            output=aggregate,
            usage=total_usage,
            trace_id=trace_id,
            response_id=None,
            sdk_version=importlib.metadata.version("openai-agents"),
        )
    except asyncio.CancelledError:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        await model_provider.aclose()
