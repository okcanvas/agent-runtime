from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, cast

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import CodingAgentResult
from okcanvas_agent_runtime.agent.runtime import RuntimeBindingResolver
from okcanvas_agent_runtime.application.execution.contracts import GatewayLifecycleEvent
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from okcanvas_agent_runtime.domain.runs.ports import ProductStore
from okcanvas_agent_runtime.domain.invocations import InvocationPolicyCatalog
from okcanvas_agent_runtime.application.invocations.service import InvocationScopeService
from okcanvas_agent_runtime.domain.sessions import SQLiteSessionApprovalPolicyCatalog, SessionRuntimeError
from okcanvas_agent_runtime.application.ports import GovernedRunAdmissionPort, ProtectedPayloadStorePort, RunStateStorePort, RunSubmissionStorePort, SessionRuntimePort, ToolApprovalStorePort
from okcanvas_agent_runtime.agent.tools.function import FunctionToolApprovalMode, FunctionToolRuntimeCatalog, execute_product_tool
from okcanvas_agent_runtime.application.submissions import GovernedExecutionLifecycleService, RunSubmissionExecutionMode, RunSubmissionRecordState
from okcanvas_agent_runtime.application.submissions.errors import RunSubmissionIntegrityError, RunSubmissionStateError

from okcanvas_agent_runtime.application.approvals.errors import ToolApprovalIntegrityError, ToolApprovalStateError
from okcanvas_agent_runtime.application.approvals.gateway import ToolApprovalGateway
from okcanvas_agent_runtime.application.approvals.models import ToolApprovalDecision, ToolApprovalPrepareResult, ToolApprovalResumeResult, ToolApprovalState


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class GovernedLocalToolApprovalService:
    """Persist one SDK Tool interruption and resume it exactly once after an operator decision."""

    def __init__(
        self,
        *,
        project_root: str | Path,
        submission_store: RunSubmissionStorePort,
        admission_store: GovernedRunAdmissionPort | None = None,
        product_store: ProductStore,
        runtime_bindings: RuntimeBindingResolver,
        payload_store: ProtectedPayloadStorePort,
        run_state_store: RunStateStorePort,
        approval_store: ToolApprovalStorePort,
        artifact_root: str | Path,
        lifecycle_service: GovernedExecutionLifecycleService,
        session_runtime: SessionRuntimePort | None = None,
        gateway: ToolApprovalGateway,
        owner_id: str | None = None,
        artifact_service: ArtifactService,
    ) -> None:
        self._definitions = AgentDefinitionCatalog(project_root)
        self._runtime_bindings = runtime_bindings
        self._invocations = InvocationScopeService(
            definitions=self._definitions,
            store=product_store,
            policy=InvocationPolicyCatalog(project_root).resolve(),
        )
        self._function_tools = FunctionToolRuntimeCatalog(project_root)
        self._submissions = submission_store
        self._admission = admission_store or cast(GovernedRunAdmissionPort, submission_store)
        self._products = product_store
        self._payloads = payload_store
        self._states = run_state_store
        self._approvals = approval_store
        self._artifacts = Path(artifact_root).expanduser().resolve()
        self._artifact_service = artifact_service
        self._lifecycle = lifecycle_service
        self._sessions = session_runtime
        self._session_approval_policy = SQLiteSessionApprovalPolicyCatalog(project_root).resolve()
        self._gateway = gateway
        self._owner_id = owner_id or f"local-tool-approval-{uuid.uuid4().hex}"

    def _session_compaction_sink(self, run_id: str):
        async def emit(event_type: str, payload: dict[str, Any]) -> None:
            self._products.append_event(
                run_id,
                event_type=event_type,
                source=EventSource.RUNTIME,
                payload=payload,
                payload_schema_version="okcanvas-session-compaction-lifecycle-v1",
            )

        return emit

    async def prepare(self, *, submission_id: str, settings: RuntimeSettings) -> ToolApprovalPrepareResult:
        decision = self._submissions.get(submission_id)
        existing = self._approvals.find_by_submission(submission_id)
        if existing is not None:
            return ToolApprovalPrepareResult(existing, replayed=True)
        if decision.execution_mode is not RunSubmissionExecutionMode.APPROVAL_INTERRUPTED:
            raise RunSubmissionStateError("Submission is not a local-Tool approval flow")
        if decision.state is not RunSubmissionRecordState.APPROVAL_PATH_REQUIRED:
            raise RunSubmissionStateError("Submission is not ready to prepare an approval interruption")
        if decision.model != settings.model:
            raise RunSubmissionIntegrityError("Approval model does not match the fingerprinted submission")
        definition = self._definitions.resolve(decision.agent_definition_id)
        tool_runtime = self._validate_definition(decision, definition)
        payload = self._read_payload(decision)
        current = self._admission.create_governed_task_run(submission_id)
        claim = self._submissions.claim_execution(
            submission_id,
            owner_id=self._owner_id,
            lease_seconds=30,
            max_attempts=3,
        )
        if claim is None:
            raise RunSubmissionStateError("Approval preparation could not claim the Product Run")
        if not self._submissions.begin_execution(submission_id, claim_token=claim.token):
            raise RunSubmissionStateError("Approval preparation lost its execution claim")
        approval_id = f"approval_{uuid.uuid4().hex}"
        execution_id = f"execution_{uuid.uuid4().hex}"
        session_id = decision.session_id
        session_before: int | None = None
        session_acquired = False
        sdk_session = None

        async def sink(event: GatewayLifecycleEvent) -> None:
            self._products.append_event(
                current.run_id or "",
                event_type=event.event_type,
                source=event.source,
                payload=event.payload,
                payload_schema_version=event.payload_schema_version,
            )

        async def forbidden() -> dict[str, Any]:
            raise RuntimeError("Local Tool executed before approval")

        try:
            if session_id is not None:
                if self._sessions is None:
                    raise ToolApprovalIntegrityError("SQLite Session Runtime is not configured")
                record = self._sessions.acquire_turn(
                    session_id=session_id,
                    run_id=current.run_id or "",
                    definition=definition,
                    runtime_binding_sha256=decision.runtime_binding_sha256 or "",
                )
                session_acquired = True
                session_before = await self._sessions.count_items(session_id)
                self._products.append_event(
                    current.run_id or "",
                    event_type="session.turn.started",
                    source=EventSource.RUNTIME,
                    payload={
                        "session_id": session_id,
                        "turn_number": record.turn_count + 1,
                        "item_count_before": session_before,
                        "approval_interrupted": True,
                        "history_persisted_in_product_events": False,
                    },
                    payload_schema_version="okcanvas-session-turn-started-v1",
                )
                sdk_session = self._sessions.sdk_session(session_id)
            root_invocation = self._invocations.ensure_root(
                run_id=current.run_id or "",
                agent_definition_id=definition.agent_id,
                runtime_binding_sha256=decision.runtime_binding_sha256 or "",
            )
            self._products.append_event(
                current.run_id or "",
                event_type="agent.definition.resolved",
                source=EventSource.RUNTIME,
                payload={
                    "agent_definition_id": definition.agent_id,
                    "agent_definition_version": definition.version,
                    "agent_definition_sha256": definition.definition_sha256,
                    "runtime_binding_sha256": decision.runtime_binding_sha256,
                    "output_contract": definition.output_contract,
                    "local_tool_count": 1,
                    "local_tool_names": list(definition.tools),
                    "mcp_server_ids": list(definition.mcp_servers),
                    "mcp_server_count": 0,
                    "handoff_count": 0,
                    "agent_tool_count": 0,
                    "root_invocation_id": root_invocation.invocation_id,
                    "workspace_access": root_invocation.workspace_access.value,
                    "session_mode": definition.session_mode,
                },
                payload_schema_version="okcanvas-agent-definition-resolved-v1",
            )
            try:
                prepared = await self._gateway.prepare(
                    definition=definition,
                    execution_id=execution_id,
                    run_id=current.run_id or "",
                    settings=settings,
                    lifecycle_sink=sink,
                    executor=forbidden,
                    session=sdk_session,
                )
            finally:
                close = getattr(sdk_session, "close", None)
                if callable(close):
                    close()
                sdk_session = None
            if session_id is not None and self._sessions is not None:
                interrupted_item_count = await self._sessions.count_items(session_id)
                self._sessions.update_active_item_count(
                    session_id=session_id,
                    run_id=current.run_id or "",
                    item_count=interrupted_item_count,
                )
                self._products.append_event(
                    current.run_id or "",
                    event_type="session.turn.interrupted",
                    source=EventSource.RUNTIME,
                    payload={
                        "session_id": session_id,
                        "item_count_before": session_before,
                        "item_count_interrupted": interrupted_item_count,
                        "turn_lease_held": True,
                        "history_persisted_in_product_events": False,
                    },
                    payload_schema_version="okcanvas-session-turn-interrupted-v1",
                )
            if prepared.tool_name != tool_runtime.tool_id:
                raise ToolApprovalIntegrityError("Unexpected Function Tool requested approval")
            state_record = self._states.write(
                approval_id=approval_id,
                run_id=current.run_id or "",
                state_json=prepared.state_json,
            )
            try:
                record = self._approvals.create_pending(
                    approval_id=approval_id,
                    submission_id=submission_id,
                    task_id=current.task_id or "",
                    run_id=current.run_id or "",
                    tool_name=prepared.tool_name,
                    tool_call_id_sha256=_sha(prepared.call_id),
                    arguments_sha256=_sha(prepared.arguments),
                    run_state_ref=state_record.run_state_ref,
                    run_state_sha256=state_record.file_sha256,
                    run_state_byte_length=state_record.byte_length,
                    run_state_key_id=state_record.key_id,
                    trace_id=prepared.trace_id,
                    response_id=prepared.response_id,
                    session_id=session_id,
                    session_item_count_before=session_before,
                )
            except Exception:
                self._states.delete(state_record.run_state_ref)
                raise
            self._products.update_run_execution_metadata(
                current.run_id or "",
                trace_id=prepared.trace_id,
                input_tokens=prepared.usage.input_tokens,
                output_tokens=prepared.usage.output_tokens,
                total_tokens=prepared.usage.total_tokens,
            )
            return ToolApprovalPrepareResult(record, replayed=False)
        except Exception:
            # A failed preparation must not remain as RUNNING.
            run = self._products.get_run(current.run_id or "")
            task = self._products.get_task(current.task_id or "")
            if run.status is RunStatus.RUNNING:
                self._products.transition_run(
                    run.run_id,
                    RunStatus.FAILED,
                    event_type="run.failed",
                    source=EventSource.RUNTIME,
                    payload={"code": "TOOL_APPROVAL_PREPARE_FAILED"},
                    payload_schema_version="okcanvas-tool-approval-failed-v1",
                )
            if task.status is TaskStatus.RUNNING:
                self._products.transition_task(task.task_id, TaskStatus.FAILED)
            close = getattr(sdk_session, "close", None)
            if callable(close):
                close()
            if session_acquired and session_id is not None and self._sessions is not None:
                if session_before is None:
                    rollback_count = self._sessions.get(session_id).item_count
                else:
                    rollback_count = await self._sessions.rollback_to_item_count(
                        session_id=session_id, expected_item_count=session_before
                    )
                self._sessions.release_turn(
                    session_id=session_id, run_id=current.run_id or "",
                    committed=False, item_count=rollback_count
                )
            await self._lifecycle.observe_run_completion(current.run_id or "")
            self._invocations.synchronize_root_with_run(current.run_id or "")
            raise

    async def decide(
        self,
        *,
        approval_id: str,
        decision: ToolApprovalDecision,
        settings: RuntimeSettings,
    ) -> ToolApprovalResumeResult:
        preview = self._approvals.get(approval_id)
        if preview.state is ToolApprovalState.PENDING:
            preview_submission = self._submissions.get(preview.submission_id)
            if preview_submission.model != settings.model:
                raise ToolApprovalIntegrityError(
                    "Resume model does not match the persisted submission"
                )
            preview_definition = self._definitions.resolve(
                preview_submission.agent_definition_id
            )
            self._validate_definition(preview_submission, preview_definition)

        claimed, replayed, resume_token = self._approvals.claim_decision(approval_id, decision)
        if replayed:
            task = self._products.get_task(claimed.task_id)
            return ToolApprovalResumeResult(
                record=claimed,
                task_id=claimed.task_id,
                run_id=claimed.run_id,
                state=task.status.value,
                artifact_id=None,
                tool_executed=claimed.tool_execution_count > 0,
                replayed=True,
            )
        sdk_session = None
        try:
            submission = self._submissions.get(claimed.submission_id)
            if submission.model != settings.model:
                raise ToolApprovalIntegrityError(
                    "Resume model does not match the persisted submission"
                )
            definition = self._definitions.resolve(submission.agent_definition_id)
            tool_runtime = self._validate_definition(submission, definition)
            state_json = self._states.read(
                approval_id=claimed.approval_id,
                run_id=claimed.run_id,
                ref=claimed.run_state_ref,
                expected_sha256=claimed.run_state_sha256,
                expected_byte_length=claimed.run_state_byte_length,
            )
            payload = self._read_payload(submission)
            if claimed.session_id != submission.session_id:
                raise ToolApprovalIntegrityError("Approval Session identity mismatch")
            if claimed.session_id is not None:
                if self._sessions is None or claimed.session_item_count_before is None:
                    raise ToolApprovalIntegrityError("Approval Session state is incomplete")
                self._sessions.assert_active_turn(
                    session_id=claimed.session_id, run_id=claimed.run_id
                )
                sdk_session = self._sessions.sdk_session(claimed.session_id)
        except Exception:
            run = self._products.get_run(claimed.run_id)
            task = self._products.get_task(claimed.task_id)
            if run.status is RunStatus.RUNNING:
                self._products.transition_run(
                    claimed.run_id,
                    RunStatus.FAILED,
                    event_type="run.failed",
                    source=EventSource.RUNTIME,
                    payload={"code": "TOOL_APPROVAL_STATE_INTEGRITY_FAILED", "approval_id": approval_id},
                    payload_schema_version="okcanvas-tool-approval-failed-v1",
                )
            if task.status is TaskStatus.RUNNING:
                self._products.transition_task(claimed.task_id, TaskStatus.FAILED)
            self._invocations.synchronize_root_with_run(claimed.run_id)
            self._approvals.finish(approval_id, state=ToolApprovalState.FAILED, tool_execution_count=0)
            close = getattr(sdk_session, "close", None)
            if callable(close):
                close()
            if claimed.session_id is not None and self._sessions is not None and claimed.session_item_count_before is not None:
                rollback_count = await self._sessions.rollback_to_item_count(
                    session_id=claimed.session_id,
                    expected_item_count=claimed.session_item_count_before,
                )
                self._sessions.release_turn(
                    session_id=claimed.session_id, run_id=claimed.run_id,
                    committed=False, item_count=rollback_count
                )
            await self._lifecycle.observe_run_completion(claimed.run_id)
            raise
        metrics = execute_product_tool(tool_runtime, payload.request).model_dump(mode="json")
        calls = 0

        async def executor() -> dict[str, Any]:
            nonlocal calls
            if resume_token is None or not self._approvals.begin_tool_execution(approval_id, resume_token=resume_token):
                raise ToolApprovalStateError("Local Tool resume generation is no longer active")
            calls += 1
            return metrics

        async def sink(event: GatewayLifecycleEvent) -> None:
            self._products.append_event(
                claimed.run_id,
                event_type=event.event_type,
                source=event.source,
                payload=event.payload,
                payload_schema_version=event.payload_schema_version,
            )

        artifact_id = None
        try:
            try:
                resumed = await self._gateway.resume(
                    definition=definition,
                    state_json=state_json,
                    decision=decision.value,
                    run_id=claimed.run_id,
                    settings=settings,
                    lifecycle_sink=sink,
                    executor=executor,
                    session=sdk_session,
                )
            finally:
                close = getattr(sdk_session, "close", None)
                if callable(close):
                    close()
                sdk_session = None
            session_item_count_after = None
            if claimed.session_id is not None and self._sessions is not None:
                session_item_count_after = await self._sessions.count_items(claimed.session_id)
                self._sessions.update_active_item_count(
                    session_id=claimed.session_id, run_id=claimed.run_id,
                    item_count=session_item_count_after
                )
            prior = self._products.get_run(claimed.run_id)
            self._products.update_run_execution_metadata(
                claimed.run_id,
                trace_id=resumed.trace_id or prior.trace_id,
                input_tokens=prior.input_tokens + resumed.usage.input_tokens,
                output_tokens=prior.output_tokens + resumed.usage.output_tokens,
                total_tokens=prior.total_tokens + resumed.usage.total_tokens,
            )
            if decision is ToolApprovalDecision.REJECT:
                if calls != 0 or resumed.tool_executed:
                    raise ToolApprovalIntegrityError("Rejected Tool call executed unexpectedly")
                if claimed.session_id is not None and self._sessions is not None:
                    assert session_item_count_after is not None
                    session_record = self._sessions.release_turn(
                        session_id=claimed.session_id, run_id=claimed.run_id,
                        committed=True, item_count=session_item_count_after
                    )
                    self._products.append_event(
                        claimed.run_id,
                        event_type="session.turn.completed",
                        source=EventSource.RUNTIME,
                        payload={
                            "session_id": claimed.session_id,
                            "turn_number": session_record.turn_count,
                            "item_count_after": session_record.item_count,
                            "outcome": "REJECTED",
                            "history_persisted_in_product_events": False,
                        },
                        payload_schema_version="okcanvas-session-turn-completed-v1",
                    )
                    await self._sessions.compact_after_committed_turn(
                        session_id=claimed.session_id,
                        run_id=claimed.run_id,
                        compaction_api_key=settings.api_key,
                        compaction_event_sink=self._session_compaction_sink(claimed.run_id),
                    )
                self._products.transition_run(
                    claimed.run_id,
                    RunStatus.CANCELLED,
                    event_type="run.cancelled",
                    source=EventSource.OPERATOR,
                    payload={"reason": "tool-approval-rejected", "approval_id": approval_id},
                    payload_schema_version="okcanvas-tool-approval-rejected-v1",
                )
                self._products.transition_task(claimed.task_id, TaskStatus.CANCELLED)
                self._invocations.synchronize_root_with_run(claimed.run_id)
                record = self._approvals.finish(approval_id, state=ToolApprovalState.REJECTED, tool_execution_count=0)
                self._states.delete(claimed.run_state_ref)
                await self._lifecycle.observe_run_completion(claimed.run_id)
                return ToolApprovalResumeResult(record, claimed.task_id, claimed.run_id, "CANCELLED", None, False, False)

            if calls != 1 or not resumed.tool_executed or resumed.remaining_interruptions:
                raise ToolApprovalIntegrityError("Approved Tool call did not execute exactly once")
            if resumed.output is None:
                raise ToolApprovalIntegrityError("Approved Tool resume produced no structured output")
            artifact = self._artifact_service.create_json(
                run_id=claimed.run_id,
                artifact_type="agent.final-output",
                payload=resumed.output.model_dump(mode="json"),
            )
            artifact_id = artifact.artifact_id
            self._products.append_event(
                claimed.run_id,
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
            )
            completed_usage = resumed.usage.model_dump(mode="json")
            completed_usage.update(
                {
                    "requests": max(int(completed_usage.get("requests") or 0) + 1, 1),
                    "input_tokens": prior.input_tokens + resumed.usage.input_tokens,
                    "output_tokens": prior.output_tokens + resumed.usage.output_tokens,
                    "total_tokens": prior.total_tokens + resumed.usage.total_tokens,
                }
            )
            if claimed.session_id is not None and self._sessions is not None:
                assert session_item_count_after is not None
                session_record = self._sessions.release_turn(
                    session_id=claimed.session_id, run_id=claimed.run_id,
                    committed=True, item_count=session_item_count_after
                )
                self._products.append_event(
                    claimed.run_id,
                    event_type="session.turn.completed",
                    source=EventSource.RUNTIME,
                    payload={
                        "session_id": claimed.session_id,
                        "turn_number": session_record.turn_count,
                        "item_count_after": session_record.item_count,
                        "outcome": "APPROVED",
                        "history_persisted_in_product_events": False,
                    },
                    payload_schema_version="okcanvas-session-turn-completed-v1",
                )
                await self._sessions.compact_after_committed_turn(
                    session_id=claimed.session_id,
                    run_id=claimed.run_id,
                    compaction_api_key=settings.api_key,
                    compaction_event_sink=self._session_compaction_sink(claimed.run_id),
                )
            self._products.transition_run(
                claimed.run_id,
                RunStatus.SUCCEEDED,
                event_type="run.completed",
                source=EventSource.RUNTIME,
                payload={
                    "artifact_id": artifact.artifact_id,
                    "trace_id": resumed.trace_id,
                    "response_id": resumed.response_id,
                    "usage": completed_usage,
                    "approval_id": approval_id,
                },
                payload_schema_version="okcanvas-local-tool-run-completed-v1",
            )
            self._products.transition_task(claimed.task_id, TaskStatus.SUCCEEDED)
            self._invocations.synchronize_root_with_run(claimed.run_id)
            record = self._approvals.finish(approval_id, state=ToolApprovalState.SUCCEEDED, tool_execution_count=1)
            self._states.delete(claimed.run_state_ref)
            await self._lifecycle.observe_run_completion(claimed.run_id)
            return ToolApprovalResumeResult(record, claimed.task_id, claimed.run_id, "SUCCEEDED", artifact_id, True, False)
        except Exception:
            run = self._products.get_run(claimed.run_id)
            task = self._products.get_task(claimed.task_id)
            if run.status is RunStatus.RUNNING:
                self._products.transition_run(
                    claimed.run_id,
                    RunStatus.FAILED,
                    event_type="run.failed",
                    source=EventSource.RUNTIME,
                    payload={"code": "TOOL_APPROVAL_RESUME_FAILED", "approval_id": approval_id},
                    payload_schema_version="okcanvas-tool-approval-failed-v1",
                )
            if task.status is TaskStatus.RUNNING:
                self._products.transition_task(claimed.task_id, TaskStatus.FAILED)
            self._approvals.finish(approval_id, state=ToolApprovalState.FAILED, tool_execution_count=calls)
            close = getattr(sdk_session, "close", None)
            if callable(close):
                close()
            if claimed.session_id is not None and self._sessions is not None and claimed.session_item_count_before is not None:
                rollback_count = await self._sessions.rollback_to_item_count(
                    session_id=claimed.session_id,
                    expected_item_count=claimed.session_item_count_before,
                )
                self._sessions.release_turn(
                    session_id=claimed.session_id, run_id=claimed.run_id,
                    committed=False, item_count=rollback_count
                )
            await self._lifecycle.observe_run_completion(claimed.run_id)
            raise

    def _validate_definition(self, decision, definition):
        if (
            definition.version != decision.agent_definition_version
            or definition.definition_sha256 != decision.agent_definition_sha256
        ):
            raise ToolApprovalIntegrityError("Agent definition changed after submission")
        runtime_binding = self._runtime_bindings.resolve(definition)
        if (
            not decision.runtime_binding_sha256
            or runtime_binding.runtime_binding_sha256 != decision.runtime_binding_sha256
        ):
            raise ToolApprovalIntegrityError("Executable Runtime binding changed after submission")
        tools = self._function_tools.resolve_many(definition.tools)
        if (
            len(tools) != 1
            or tools[0].approval_mode is not FunctionToolApprovalMode.ALWAYS
            or definition.mcp_servers
            or definition.handoffs
            or definition.agent_tools
            or definition.workspace_access != "none"
        ):
            raise ToolApprovalIntegrityError(
                "Approval flow requires exactly one registered ALWAYS Function Tool without MCP, child Agents or workspace"
            )
        if definition.session_mode == "disabled":
            if decision.session_id is not None or runtime_binding.execution_path != "governed-function-tool-approval-v1":
                raise ToolApprovalIntegrityError("Non-Session approval binding is inconsistent")
        elif definition.session_mode == "sqlite-v1":
            if not decision.session_id or runtime_binding.execution_path != "sqlite-session-approval-execution-v1":
                raise ToolApprovalIntegrityError("SQLite Session approval binding is inconsistent")
            policy = self._session_approval_policy
            if (
                policy.session_mode != "sqlite-v1"
                or policy.approval_mode != "ALWAYS"
                or policy.max_tools != 1
                or not policy.hold_turn_lease_while_interrupted
                or not policy.commit_rejected_turn
                or policy.workspace_access != "none"
            ):
                raise ToolApprovalIntegrityError("SQLite Session approval policy is inconsistent")
        else:
            raise ToolApprovalIntegrityError("Unsupported approval Session mode")
        return tools[0]

    def _read_payload(self, decision):
        if not decision.protected_payload_persisted or not decision.protected_payload_ref or not decision.protected_payload_sha256 or decision.protected_payload_byte_length is None:
            raise ToolApprovalIntegrityError("Approval submission has no protected payload")
        payload = self._payloads.read(
            decision.protected_payload_ref,
            expected_file_sha256=decision.protected_payload_sha256,
            expected_byte_length=decision.protected_payload_byte_length,
        )
        if (
            payload.submission_id != decision.submission_id
            or payload.runtime_binding_sha256 != decision.runtime_binding_sha256
            or payload.session_id != decision.session_id
            or payload.input_sha256 != decision.input_sha256
            or payload.request_fingerprint_sha256 != decision.request_fingerprint_sha256
        ):
            raise ToolApprovalIntegrityError("Protected payload identity does not match approval submission")
        return payload
