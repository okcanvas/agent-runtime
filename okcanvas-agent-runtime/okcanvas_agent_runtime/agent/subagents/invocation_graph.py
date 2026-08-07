from __future__ import annotations

from okcanvas_agent_runtime.agent.definitions import AgentDefinition, AgentDefinitionCatalog, AgentDefinitionError

from okcanvas_agent_runtime.domain.invocations.errors import InvocationGraphError
from okcanvas_agent_runtime.domain.invocations.models import ChildAgentEdge, InvocationKind, InvocationPolicy, WorkspaceAccess


class ChildAgentGraphResolver:
    def __init__(self, definitions: AgentDefinitionCatalog, policy: InvocationPolicy) -> None:
        self._definitions = definitions
        self._policy = policy

    def resolve(self, root: AgentDefinition) -> tuple[ChildAgentEdge, ...]:
        edges: list[ChildAgentEdge] = []
        counts = {
            InvocationKind.HANDOFF: 0,
            InvocationKind.AGENT_AS_TOOL: 0,
            InvocationKind.ORCHESTRATION_CHILD: 0,
        }

        def visit(parent: AgentDefinition, *, depth: int, ancestry: tuple[str, ...]) -> None:
            declarations = (
                *((InvocationKind.HANDOFF, item) for item in parent.handoffs),
                *((InvocationKind.AGENT_AS_TOOL, item) for item in parent.agent_tools),
                *((InvocationKind.ORCHESTRATION_CHILD, item) for item in parent.orchestration_children),
            )
            seen_local: set[tuple[InvocationKind, str]] = set()
            for kind, child_id in declarations:
                marker = (kind, child_id)
                if marker in seen_local:
                    raise InvocationGraphError("Duplicate child Agent edge is forbidden")
                seen_local.add(marker)
                if child_id == parent.agent_id or child_id in ancestry:
                    raise InvocationGraphError("Self-referential or cyclic child Agent graph is forbidden")
                child_depth = depth + 1
                if child_depth > self._policy.max_depth:
                    raise InvocationGraphError("Child Agent graph exceeds the configured depth")
                try:
                    child = self._definitions.resolve(child_id)
                except AgentDefinitionError as exc:
                    raise InvocationGraphError(
                        f"Child Agent definition could not be resolved: {child_id}"
                    ) from exc
                counts[kind] += 1
                if (
                    kind is InvocationKind.HANDOFF
                    and counts[kind] > self._policy.max_handoffs_per_run
                ):
                    raise InvocationGraphError("Child Agent graph exceeds the Handoff limit")
                if (
                    kind is InvocationKind.AGENT_AS_TOOL
                    and counts[kind] > self._policy.max_agent_tools_per_run
                ):
                    raise InvocationGraphError("Child Agent graph exceeds the Agent-as-Tool limit")
                if kind is InvocationKind.ORCHESTRATION_CHILD:
                    if depth != 0 or child_depth != 1 or counts[kind] > 2:
                        raise InvocationGraphError(
                            "Bounded orchestration children must be exactly one level below the root"
                        )
                    if child.handoffs or child.agent_tools or child.orchestration_children:
                        raise InvocationGraphError(
                            "Bounded orchestration children must be terminal"
                        )
                edges.append(
                    ChildAgentEdge(
                        parent_agent_id=parent.agent_id,
                        child_agent_id=child.agent_id,
                        kind=kind,
                        depth=child_depth,
                        child_definition_version=child.version,
                        child_definition_sha256=child.definition_sha256,
                        workspace_access=WorkspaceAccess(child.workspace_access),
                    )
                )
                if kind is not InvocationKind.ORCHESTRATION_CHILD:
                    visit(child, depth=child_depth, ancestry=(*ancestry, child.agent_id))

        visit(root, depth=0, ancestry=(root.agent_id,))
        return tuple(
            sorted(
                edges,
                key=lambda item: (
                    item.depth,
                    item.parent_agent_id,
                    item.kind.value,
                    item.child_agent_id,
                ),
            )
        )
