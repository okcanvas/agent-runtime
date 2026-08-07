from __future__ import annotations

from typing import Any, Protocol

from okcanvas_agent_runtime.domain.runs.models import AgentInvocationRecord, ArtifactRecord, EventSource, InvocationKind, InvocationState, RunEventRecord, RunRecord, RunStatus, TaskRecord, TaskStatus, WorkspaceAccess


class ProductStore(Protocol):
    def initialize(self) -> None: ...

    def create_task(
        self,
        *,
        task_type: str,
        input_sha256: str,
        agent_definition_id: str,
        agent_definition_version: str,
        protected_payload_ref: str | None = None,
        task_id: str | None = None,
    ) -> TaskRecord: ...

    def get_task(self, task_id: str) -> TaskRecord: ...

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TaskRecord], int]: ...

    def task_status_counts(self) -> dict[str, int]: ...

    def transition_task(self, task_id: str, target: TaskStatus) -> TaskRecord: ...

    def create_run(self, *, task_id: str, run_id: str | None = None) -> RunRecord: ...

    def get_run(self, run_id: str) -> RunRecord: ...

    def list_runs(
        self,
        *,
        status: RunStatus | None = None,
        agent_definition_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RunRecord], int]: ...

    def run_status_counts(self) -> dict[str, int]: ...

    def artifact_count(self) -> int: ...

    def create_agent_invocation(
        self,
        *,
        run_id: str,
        parent_invocation_id: str | None,
        invocation_kind: InvocationKind,
        state: InvocationState,
        agent_definition_id: str,
        agent_definition_version: str,
        agent_definition_sha256: str,
        runtime_binding_sha256: str,
        depth: int,
        workspace_access: WorkspaceAccess,
        workspace_ref: str | None,
        invocation_id: str | None = None,
    ) -> AgentInvocationRecord: ...

    def get_agent_invocation(self, invocation_id: str) -> AgentInvocationRecord: ...

    def list_agent_invocations(self, run_id: str) -> list[AgentInvocationRecord]: ...

    def transition_agent_invocation(
        self, invocation_id: str, target: InvocationState
    ) -> AgentInvocationRecord: ...

    def update_agent_invocation_usage(
        self,
        invocation_id: str,
        *,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> AgentInvocationRecord: ...

    def transition_run(
        self,
        run_id: str,
        target: RunStatus,
        *,
        event_type: str,
        source: EventSource = EventSource.RUNTIME,
        payload: dict[str, Any] | None = None,
        payload_schema_version: str = "okcanvas-event-payload-v1",
    ) -> RunRecord: ...

    def append_event(
        self,
        run_id: str,
        *,
        event_type: str,
        source: EventSource,
        payload: dict[str, Any] | None = None,
        payload_schema_version: str = "okcanvas-event-payload-v1",
        require_active_run: bool = False,
    ) -> RunEventRecord: ...

    def list_events(self, run_id: str, *, after_sequence: int = 0) -> list[RunEventRecord]: ...

    def update_run_execution_metadata(
        self,
        run_id: str,
        *,
        trace_id: str | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> RunRecord: ...

    def register_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        storage_ref: str,
        sha256: str,
        byte_length: int,
        media_type: str,
        artifact_id: str | None = None,
    ) -> ArtifactRecord: ...

    def get_artifact(self, artifact_id: str) -> ArtifactRecord: ...

    def list_artifacts(self, run_id: str) -> list[ArtifactRecord]: ...

    def verify_artifact(self, artifact_id: str) -> ArtifactRecord: ...
