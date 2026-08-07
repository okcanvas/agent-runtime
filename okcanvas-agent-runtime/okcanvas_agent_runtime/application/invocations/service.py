from __future__ import annotations

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.domain.runs.ports import ProductStore
from okcanvas_agent_runtime.application.orchestration import BoundedOrchestrationPolicyCatalog

from okcanvas_agent_runtime.domain.invocations.errors import InvocationGraphError, InvocationStateError
from okcanvas_agent_runtime.agent.subagents.invocation_graph import ChildAgentGraphResolver
from okcanvas_agent_runtime.domain.invocations.models import AgentInvocationRecord, InvocationKind, InvocationPolicy, InvocationState, WorkspaceAccess


class InvocationScopeService:
    def __init__(
        self,
        *,
        definitions: AgentDefinitionCatalog,
        store: ProductStore,
        policy: InvocationPolicy,
    ) -> None:
        self._definitions = definitions
        self._store = store
        self._policy = policy
        self._graphs = ChildAgentGraphResolver(definitions, policy)
        self._orchestration_policy_catalog = BoundedOrchestrationPolicyCatalog(
            definitions.project_root
        )

    def ensure_root(
        self,
        *,
        run_id: str,
        agent_definition_id: str,
        runtime_binding_sha256: str,
    ) -> AgentInvocationRecord:
        existing = self._store.list_agent_invocations(run_id)
        roots = [item for item in existing if item.invocation_kind is InvocationKind.ROOT]
        if roots:
            if len(roots) != 1:
                raise InvocationStateError("A Product Run must have exactly one root invocation")
            root = roots[0]
            if (
                root.agent_definition_id != agent_definition_id
                or root.runtime_binding_sha256 != runtime_binding_sha256
            ):
                raise InvocationStateError("Existing root invocation does not match the Runtime binding")
            return root
        definition = self._definitions.resolve(agent_definition_id)
        self._graphs.resolve(definition)
        return self._store.create_agent_invocation(
            run_id=run_id,
            parent_invocation_id=None,
            invocation_kind=InvocationKind.ROOT,
            state=InvocationState.RUNNING,
            agent_definition_id=definition.agent_id,
            agent_definition_version=definition.version,
            agent_definition_sha256=definition.definition_sha256,
            runtime_binding_sha256=runtime_binding_sha256,
            depth=0,
            workspace_access=WorkspaceAccess(definition.workspace_access),
            workspace_ref=None,
        )

    def plan_child(
        self,
        *,
        parent_invocation_id: str,
        child_agent_definition_id: str,
        invocation_kind: InvocationKind,
        runtime_binding_sha256: str,
    ) -> AgentInvocationRecord:
        if invocation_kind is InvocationKind.ROOT:
            raise InvocationGraphError("Child invocation kind cannot be ROOT")
        parent = self._store.get_agent_invocation(parent_invocation_id)
        parent_definition = self._definitions.resolve(parent.agent_definition_id)
        allowed_by_kind = {
            InvocationKind.HANDOFF: parent_definition.handoffs,
            InvocationKind.AGENT_AS_TOOL: parent_definition.agent_tools,
            InvocationKind.ORCHESTRATION_CHILD: parent_definition.orchestration_children,
        }
        allowed = allowed_by_kind.get(invocation_kind, ())
        if child_agent_definition_id not in allowed:
            raise InvocationGraphError("Child Agent is not in the immutable parent definition graph")
        child = self._definitions.resolve(child_agent_definition_id)
        if child.agent_id == parent.agent_definition_id:
            raise InvocationGraphError("Self-referential child invocation is forbidden")
        depth = parent.depth + 1
        if depth > self._policy.max_depth:
            raise InvocationGraphError("Child invocation exceeds the configured depth")
        existing = self._store.list_agent_invocations(parent.run_id)
        kind_count = sum(1 for item in existing if item.invocation_kind is invocation_kind)
        if invocation_kind is InvocationKind.HANDOFF:
            maximum = self._policy.max_handoffs_per_run
        elif invocation_kind is InvocationKind.AGENT_AS_TOOL:
            maximum = self._policy.max_agent_tools_per_run
        elif invocation_kind is InvocationKind.ORCHESTRATION_CHILD:
            maximum = self._orchestration_policy_catalog.resolve().child_count
        else:
            raise InvocationGraphError("Unsupported child invocation kind")
        if kind_count >= maximum:
            raise InvocationGraphError("Child invocation exceeds the configured per-Run limit")
        if any(
            item.parent_invocation_id == parent.invocation_id
            and item.invocation_kind is invocation_kind
            and item.agent_definition_id == child.agent_id
            for item in existing
        ):
            raise InvocationGraphError("Duplicate child invocation identity is forbidden")
        return self._store.create_agent_invocation(
            run_id=parent.run_id,
            parent_invocation_id=parent.invocation_id,
            invocation_kind=invocation_kind,
            state=InvocationState.PLANNED,
            agent_definition_id=child.agent_id,
            agent_definition_version=child.version,
            agent_definition_sha256=child.definition_sha256,
            runtime_binding_sha256=runtime_binding_sha256,
            depth=depth,
            workspace_access=WorkspaceAccess(child.workspace_access),
            workspace_ref=None,
        )

    def begin_handoff(
        self,
        *,
        parent_invocation_id: str,
        child_agent_definition_id: str,
        child_runtime_binding_sha256: str,
        parent_input_tokens: int,
        parent_output_tokens: int,
        parent_total_tokens: int,
    ) -> AgentInvocationRecord:
        parent = self._store.get_agent_invocation(parent_invocation_id)
        if parent.state is not InvocationState.RUNNING:
            raise InvocationStateError("Handoff parent invocation must be RUNNING")
        child = self.plan_child(
            parent_invocation_id=parent_invocation_id,
            child_agent_definition_id=child_agent_definition_id,
            invocation_kind=InvocationKind.HANDOFF,
            runtime_binding_sha256=child_runtime_binding_sha256,
        )
        self._store.update_agent_invocation_usage(
            parent.invocation_id,
            input_tokens=parent_input_tokens,
            output_tokens=parent_output_tokens,
            total_tokens=parent_total_tokens,
        )
        self._store.transition_agent_invocation(parent.invocation_id, InvocationState.SUCCEEDED)
        return self._store.transition_agent_invocation(child.invocation_id, InvocationState.RUNNING)


    def begin_agent_tool(
        self,
        *,
        parent_invocation_id: str,
        child_agent_definition_id: str,
        child_runtime_binding_sha256: str,
    ) -> AgentInvocationRecord:
        parent = self._store.get_agent_invocation(parent_invocation_id)
        if parent.state is not InvocationState.RUNNING:
            raise InvocationStateError("Agent-as-Tool parent invocation must be RUNNING")
        child = self.plan_child(
            parent_invocation_id=parent_invocation_id,
            child_agent_definition_id=child_agent_definition_id,
            invocation_kind=InvocationKind.AGENT_AS_TOOL,
            runtime_binding_sha256=child_runtime_binding_sha256,
        )
        return self._store.transition_agent_invocation(
            child.invocation_id, InvocationState.RUNNING
        )

    def plan_orchestration_children(
        self,
        *,
        parent_invocation_id: str,
        child_runtime_bindings: tuple[tuple[str, str], ...],
    ) -> tuple[AgentInvocationRecord, ...]:
        parent = self._store.get_agent_invocation(parent_invocation_id)
        if parent.state is not InvocationState.RUNNING:
            raise InvocationStateError("Orchestration root invocation must be RUNNING")
        parent_definition = self._definitions.resolve(parent.agent_definition_id)
        declared = parent_definition.orchestration_children
        if tuple(item[0] for item in child_runtime_bindings) != declared:
            raise InvocationGraphError(
                "Orchestration child bindings do not match the immutable declaration order"
            )
        if len(declared) != self._orchestration_policy_catalog.resolve().child_count:
            raise InvocationGraphError("STEP062 requires exactly two orchestration children")
        planned = []
        for child_id, binding_sha in child_runtime_bindings:
            planned.append(
                self.plan_child(
                    parent_invocation_id=parent_invocation_id,
                    child_agent_definition_id=child_id,
                    invocation_kind=InvocationKind.ORCHESTRATION_CHILD,
                    runtime_binding_sha256=binding_sha,
                )
            )
        return tuple(planned)

    def begin_orchestration_child(self, invocation_id: str) -> AgentInvocationRecord:
        current = self._store.get_agent_invocation(invocation_id)
        if current.invocation_kind is not InvocationKind.ORCHESTRATION_CHILD:
            raise InvocationStateError("Invocation is not an orchestration child")
        if current.state is not InvocationState.PLANNED:
            raise InvocationStateError("Orchestration child must begin from PLANNED")
        return self._store.transition_agent_invocation(invocation_id, InvocationState.RUNNING)

    def cancel_invocation(
        self,
        *,
        invocation_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ) -> AgentInvocationRecord:
        current = self._store.get_agent_invocation(invocation_id)
        if current.state not in {InvocationState.PLANNED, InvocationState.RUNNING}:
            raise InvocationStateError("Only a PLANNED or RUNNING invocation can be cancelled")
        self._store.update_agent_invocation_usage(
            invocation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        return self._store.transition_agent_invocation(invocation_id, InvocationState.CANCELLED)

    def complete_invocation(
        self,
        *,
        invocation_id: str,
        state: InvocationState,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> AgentInvocationRecord:
        if state not in {
            InvocationState.SUCCEEDED,
            InvocationState.FAILED,
            InvocationState.CANCELLED,
        }:
            raise InvocationStateError("Invocation completion requires a terminal state")
        current = self._store.get_agent_invocation(invocation_id)
        if current.state is not InvocationState.RUNNING:
            raise InvocationStateError("Only a RUNNING invocation can be completed")
        self._store.update_agent_invocation_usage(
            invocation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        return self._store.transition_agent_invocation(invocation_id, state)



    def synchronize_root_with_run(self, run_id: str) -> AgentInvocationRecord | None:
        run = self._store.get_run(run_id)
        invocations = self._store.list_agent_invocations(run_id)
        roots = [item for item in invocations if item.invocation_kind is InvocationKind.ROOT]
        if not roots:
            return None
        if len(roots) != 1:
            raise InvocationStateError("Root invocation identity is missing or ambiguous")
        target_by_run = {
            "SUCCEEDED": InvocationState.SUCCEEDED,
            "FAILED": InvocationState.FAILED,
            "CANCELLED": InvocationState.CANCELLED,
        }
        target = target_by_run.get(run.status.value)
        if target is None:
            return roots[0]
        running = [item for item in invocations if item.state is InvocationState.RUNNING]
        orchestration_children = [
            item
            for item in invocations
            if item.invocation_kind is InvocationKind.ORCHESTRATION_CHILD
        ]
        if orchestration_children:
            for item in orchestration_children:
                if item.state is InvocationState.PLANNED:
                    self._store.transition_agent_invocation(
                        item.invocation_id, InvocationState.CANCELLED
                    )
                elif item.state is InvocationState.RUNNING:
                    child_target = (
                        InvocationState.CANCELLED
                        if target is InvocationState.CANCELLED
                        else InvocationState.FAILED
                    )
                    self._store.transition_agent_invocation(item.invocation_id, child_target)
            root = self._store.get_agent_invocation(roots[0].invocation_id)
            if root.state is InvocationState.RUNNING:
                self._store.update_agent_invocation_usage(
                    root.invocation_id, input_tokens=0, output_tokens=0, total_tokens=0
                )
                self._store.transition_agent_invocation(root.invocation_id, target)
            return self._store.get_agent_invocation(roots[0].invocation_id)
        if len(running) > 2:
            raise InvocationStateError("A terminal Product Run has too many active invocations")
        if len(running) == 2:
            kinds = {item.invocation_kind for item in running}
            if kinds != {InvocationKind.ROOT, InvocationKind.AGENT_AS_TOOL}:
                raise InvocationStateError(
                    "Only a ROOT and one AGENT_AS_TOOL child may be concurrently active"
                )
            child = next(
                item for item in running if item.invocation_kind is InvocationKind.AGENT_AS_TOOL
            )
            self._store.transition_agent_invocation(child.invocation_id, target)
            running = [item for item in running if item.invocation_kind is InvocationKind.ROOT]
        if running:
            active = running[0]
            if active.invocation_kind is InvocationKind.ROOT:
                self._store.update_agent_invocation_usage(
                    active.invocation_id,
                    input_tokens=run.input_tokens,
                    output_tokens=run.output_tokens,
                    total_tokens=run.total_tokens,
                )
            self._store.transition_agent_invocation(active.invocation_id, target)
        return self._store.get_agent_invocation(roots[0].invocation_id)

    def complete_root(
        self,
        *,
        run_id: str,
        state: InvocationState,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> AgentInvocationRecord:
        if state not in {
            InvocationState.SUCCEEDED,
            InvocationState.FAILED,
            InvocationState.CANCELLED,
        }:
            raise InvocationStateError("Root invocation completion requires a terminal state")
        roots = [
            item
            for item in self._store.list_agent_invocations(run_id)
            if item.invocation_kind is InvocationKind.ROOT
        ]
        if len(roots) != 1:
            raise InvocationStateError("Root invocation identity is missing or ambiguous")
        self._store.update_agent_invocation_usage(
            roots[0].invocation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        return self._store.transition_agent_invocation(roots[0].invocation_id, state)
