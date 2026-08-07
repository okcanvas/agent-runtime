from __future__ import annotations

from collections.abc import Sequence

from okcanvas_agent_runtime.agent.definitions import AgentDefinition
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary

from okcanvas_agent_runtime.application.orchestration.errors import BoundedOrchestrationContractError
from okcanvas_agent_runtime.application.orchestration.models import BoundedOrchestrationChildResult, BoundedOrchestrationPolicy, BoundedOrchestrationResult


def validate_bounded_orchestration_definitions(
    *,
    root: AgentDefinition,
    children: Sequence[AgentDefinition],
    policy: BoundedOrchestrationPolicy,
) -> None:
    if tuple(item.agent_id for item in children) != root.orchestration_children:
        raise BoundedOrchestrationContractError(
            "Resolved orchestration children do not match the immutable declaration order"
        )
    if len(children) != policy.child_count or len({item.agent_id for item in children}) != len(children):
        raise BoundedOrchestrationContractError(
            "STEP062 requires exactly two distinct sibling specialists"
        )
    if root.output_contract != policy.root_output_contract:
        raise BoundedOrchestrationContractError(
            "Orchestration root output contract does not match the policy"
        )
    if (
        root.tools
        or root.mcp_servers
        or root.handoffs
        or root.agent_tools
        or root.guardrails
        or root.session_mode != "disabled"
        or root.workspace_access != policy.workspace_access
    ):
        raise BoundedOrchestrationContractError(
            "Orchestration root must be Session-disabled, capability-free and workspace-free"
        )
    for child in children:
        if child.output_contract != policy.child_output_contract:
            raise BoundedOrchestrationContractError(
                "Orchestration child output contract does not match the policy"
            )
        if (
            child.tools
            or child.mcp_servers
            or child.handoffs
            or child.agent_tools
            or child.orchestration_children
            or child.guardrails
            or child.session_mode != policy.child_session_mode
            or child.workspace_access != policy.workspace_access
        ):
            raise BoundedOrchestrationContractError(
                "Orchestration specialists must be terminal language-only Agents"
            )


def sum_usage(items: Sequence[UsageSummary]) -> UsageSummary:
    return UsageSummary(
        requests=sum(item.requests for item in items),
        input_tokens=sum(item.input_tokens for item in items),
        output_tokens=sum(item.output_tokens for item in items),
        total_tokens=sum(item.total_tokens for item in items),
        cached_input_tokens=sum(item.cached_input_tokens for item in items),
        reasoning_tokens=sum(item.reasoning_tokens for item in items),
    )


def aggregate_child_results(
    *,
    children: Sequence[tuple[int, AgentDefinition, CodingAgentResult, UsageSummary]],
    policy: BoundedOrchestrationPolicy,
) -> BoundedOrchestrationResult:
    ordered = sorted(children, key=lambda item: item[0])
    if len(ordered) != policy.child_count or [item[0] for item in ordered] != [1, 2]:
        raise BoundedOrchestrationContractError(
            "Successful orchestration aggregation requires both declared child ordinals"
        )
    severity = {AgentStatus.PASS: 0, AgentStatus.PARTIAL: 1, AgentStatus.FAIL: 2}
    status = max((item[2].status for item in ordered), key=lambda item: severity[item])
    result = BoundedOrchestrationResult(
        status=status,
        summary=(
            f"{policy.child_count}/{policy.child_count} specialists completed; "
            f"aggregate status {status.value}."
        ),
        child_count=policy.child_count,
        children=[
            BoundedOrchestrationChildResult(
                ordinal=ordinal,
                agent_definition_id=definition.agent_id,
                result=child_result,
                usage=usage,
            )
            for ordinal, definition, child_result, usage in ordered
        ],
    )
    return result
