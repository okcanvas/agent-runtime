from __future__ import annotations

from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, CodingFinding, FindingConfidence, FindingSeverity, UsageSummary
from okcanvas_agent_runtime.application.execution.contracts import GatewayLifecycleEvent

from okcanvas_agent_runtime.application.approvals.gateway import ToolApprovalGatewayPrepare, ToolApprovalGatewayResume
from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog


class DeterministicToolApprovalGateway:
    """No-network gateway used only by deterministic acceptance and unit tests."""

    async def prepare(self, *, definition, execution_id, run_id, settings, lifecycle_sink, executor, session=None):
        runtime = FunctionToolRuntimeCatalog(definition.definition_path.parents[3]).resolve_many(definition.tools)[0]
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id, "agent_name": definition.name}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"agent_id": definition.agent_id, "model": settings.model, "input_item_count": 1}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"agent_id": definition.agent_id, "response_id": "resp_prepare", "output_item_count": 1}))
        if session is not None:
            await session.add_items([
                {"role": "user", "content": [{"type": "input_text", "text": f"execution:{execution_id}"}]},
                {"type": "function_call", "name": runtime.tool_id, "call_id": "call_fixture", "arguments": f'{{"execution_id":"{execution_id}"}}'},
            ])
        return ToolApprovalGatewayPrepare(
            state_json={
                "schema_version": "deterministic-runstate-v1",
                "execution_id": execution_id,
                "run_id": run_id,
                "interruption": {"tool_name": runtime.tool_id, "call_id": "call_fixture"},
            },
            tool_name=runtime.tool_id,
            call_id="call_fixture",
            arguments=f'{{"execution_id":"{execution_id}"}}',
            trace_id="trace_prepare_fixture",
            response_id="resp_prepare",
            usage=UsageSummary(requests=1, input_tokens=20, output_tokens=5, total_tokens=25),
        )

    async def resume(self, *, definition, state_json, decision, run_id, settings, lifecycle_sink, executor, session=None):
        runtime = FunctionToolRuntimeCatalog(definition.definition_path.parents[3]).resolve_many(definition.tools)[0]
        if state_json.get("run_id") != run_id:
            raise RuntimeError("Deterministic RunState identity mismatch")
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id, "agent_name": definition.name}))
        if decision == "REJECT":
            if session is not None:
                await session.add_items([
                    {"type": "function_call_output", "call_id": "call_fixture", "output": "Tool call rejected by operator"},
                    {"role": "assistant", "content": [{"type": "output_text", "text": "The requested Tool action was rejected."}]},
                ])
            await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id, "output_contract": definition.output_contract}))
            return ToolApprovalGatewayResume(
                output=None,
                trace_id="trace_reject_fixture",
                response_id="resp_reject",
                usage=UsageSummary(requests=1, input_tokens=5, output_tokens=2, total_tokens=7),
                remaining_interruptions=0,
                tool_executed=False,
            )
        await lifecycle_sink(GatewayLifecycleEvent("tool.started", {"tool_id": runtime.tool_id, "tool_name": runtime.tool_id, "runtime_version": runtime.runtime_version, "approval_required": True, "arguments_persisted": False, "tool_call_id_present": True}))
        result = await executor()
        await lifecycle_sink(GatewayLifecycleEvent("tool.completed", {"tool_id": runtime.tool_id, "tool_name": runtime.tool_id, "runtime_version": runtime.runtime_version, "approval_required": True, "result_persisted": False, "result_present": True, "tool_call_id_present": True}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id, "output_contract": definition.output_contract}))
        if session is not None:
            await session.add_items([
                {"type": "function_call_output", "call_id": "call_fixture", "output": "Approved Tool completed"},
                {"role": "assistant", "content": [{"type": "output_text", "text": "The approved local text metrics Tool completed."}]},
            ])
        output = CodingAgentResult(
            status=AgentStatus.PASS,
            summary="The approved local text metrics Tool completed.",
            findings=[
                CodingFinding(
                    severity=FindingSeverity.INFO,
                    confidence=FindingConfidence.CONFIRMED,
                    title="Protected text metrics",
                    detail=(
                        f"characters={result['characters']}, words={result['words']}, "
                        f"lines={result['lines']}, sha256={result['sha256']}"
                    ),
                    evidence=["local_text_metrics approved execution"],
                )
            ],
            unverified=[],
        )
        return ToolApprovalGatewayResume(
            output=output,
            trace_id="trace_approve_fixture",
            response_id="resp_approve",
            usage=UsageSummary(requests=1, input_tokens=15, output_tokens=10, total_tokens=25),
            remaining_interruptions=0,
            tool_executed=True,
        )
