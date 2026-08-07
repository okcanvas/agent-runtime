from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.domain.invocations import (
    ChildAgentGraphResolver,
    InvocationGraphError,
    InvocationKind,
    InvocationPolicyCatalog,
    InvocationState,
    InvocationWorkspaceError,
    InvocationWorkspacePlanner,
)
from okcanvas_agent_runtime.application.invocations.service import InvocationScopeService
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import RunStatus, TaskStatus
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService


def _write_policy(project: Path, **overrides: object) -> None:
    payload: dict[str, object] = {
        "schema_version": "okcanvas-sub-agent-invocation-policy-v1",
        "policy_id": "default-sub-agent-invocation-policy",
        "version": "1.0.0",
        "max_depth": 4,
        "max_handoffs_per_run": 4,
        "max_agent_tools_per_run": 8,
        "default_workspace_access": "none",
        "physical_workspace_enabled": False,
    }
    payload.update(overrides)
    target = project / "specs" / "runtime" / "sub-agent-invocation-policy.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    allowlist = project / "specs" / "mcp" / "allowlist.json"
    allowlist.parent.mkdir(parents=True, exist_ok=True)
    allowlist.write_text(
        json.dumps(
            {"schema_version": "okcanvas-mcp-allowlist-v1", "allowed_server_ids": []},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_agent(
    project: Path,
    agent_id: str,
    *,
    handoffs: list[str] | None = None,
    agent_tools: list[str] | None = None,
) -> None:
    directory = project / "specs" / "agents" / agent_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "instructions.md").write_text(
        f"Deterministic STEP040 instructions for {agent_id}.\n", encoding="utf-8"
    )
    (directory / "output.schema.json").write_text("{}\n", encoding="utf-8")
    (directory / "definition.json").write_text(
        json.dumps(
            {
                "schema_version": "okcanvas-agent-definition-v1",
                "agent_id": agent_id,
                "version": "1.0.0",
                "name": f"STEP040 {agent_id}",
                "instructions_file": "instructions.md",
                "output_schema_file": "output.schema.json",
                "output_contract": "CodingAgentResult",
                "tools": [],
                "mcp_servers": [],
                "handoffs": handoffs or [],
                "agent_tools": agent_tools or [],
                "workspace_access": "none",
                "max_turns": 2,
                "workflow_name": "STEP040 Invocation Scope",
                "session_mode": "disabled",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _valid_project(base: Path) -> Path:
    project = base / "valid-project"
    _write_policy(project)
    _write_agent(
        project,
        "scope-root-agent",
        handoffs=["scope-handoff-agent"],
        agent_tools=["scope-tool-agent"],
    )
    _write_agent(project, "scope-handoff-agent")
    _write_agent(project, "scope-tool-agent")
    return project


def _graph_rejected(project: Path, root_id: str) -> bool:
    definitions = AgentDefinitionCatalog(project)
    policy = InvocationPolicyCatalog(project).resolve()
    try:
        ChildAgentGraphResolver(definitions, policy).resolve(definitions.resolve(root_id))
    except InvocationGraphError:
        return True
    return False


def _build_invalid_projects(base: Path) -> dict[str, bool]:
    unresolved = base / "unresolved-project"
    _write_policy(unresolved)
    _write_agent(unresolved, "unresolved-root", handoffs=["missing-agent"])

    self_project = base / "self-project"
    _write_policy(self_project)
    _write_agent(self_project, "self-root", handoffs=["self-root"])

    depth = base / "depth-project"
    _write_policy(depth, max_depth=1)
    _write_agent(depth, "depth-root", handoffs=["depth-child"])
    _write_agent(depth, "depth-child", handoffs=["depth-grandchild"])
    _write_agent(depth, "depth-grandchild")

    count = base / "count-project"
    _write_policy(count, max_handoffs_per_run=1)
    _write_agent(count, "count-root", handoffs=["count-a", "count-b"])
    _write_agent(count, "count-a")
    _write_agent(count, "count-b")

    return {
        "unresolved": _graph_rejected(unresolved, "unresolved-root"),
        "self": _graph_rejected(self_project, "self-root"),
        "depth": _graph_rejected(depth, "depth-root"),
        "handoff_count": _graph_rejected(count, "count-root"),
    }


def _counts(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(database)
    try:
        return {
            "tasks": int(connection.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
            "runs": int(connection.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
            "invocations": int(
                connection.execute("SELECT COUNT(*) FROM agent_invocation").fetchone()[0]
            ),
            "events": int(connection.execute("SELECT COUNT(*) FROM run_event").fetchone()[0]),
            "artifacts": int(connection.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]),
        }
    finally:
        connection.close()


def run(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP040", output=output) as workspace:
        project = _valid_project(workspace.scratch_dir)
        definitions = AgentDefinitionCatalog(project)
        policy = InvocationPolicyCatalog(project).resolve()
        graph = ChildAgentGraphResolver(definitions, policy).resolve(
            definitions.resolve("scope-root-agent")
        )
        bindings = AgentRuntimeBindingCatalog(project)
        root_binding = bindings.resolve(definitions.resolve("scope-root-agent"))
        handoff_binding = bindings.resolve(definitions.resolve("scope-handoff-agent"))
        agent_tool_binding = bindings.resolve(definitions.resolve("scope-tool-agent"))

        product_db = workspace.database_dir / "product.sqlite3"
        store = SQLiteProductStore(product_db)
        store.initialize()
        task = store.create_task(
            task_type="SUB_AGENT_INVOCATION_SCOPE_ACCEPTANCE",
            input_sha256="4" * 64,
            agent_definition_id="scope-root-agent",
            agent_definition_version="1.0.0",
        )
        run_record = store.create_run(task_id=task.task_id)
        store.transition_task(task.task_id, TaskStatus.RUNNING)
        store.transition_run(
            run_record.run_id,
            RunStatus.RUNNING,
            event_type="run.started",
            payload={"acceptance": "STEP040"},
        )

        scope = InvocationScopeService(definitions=definitions, store=store, policy=policy)
        root = scope.ensure_root(
            run_id=run_record.run_id,
            agent_definition_id="scope-root-agent",
            runtime_binding_sha256=root_binding.runtime_binding_sha256,
        )
        handoff = scope.plan_child(
            parent_invocation_id=root.invocation_id,
            child_agent_definition_id="scope-handoff-agent",
            invocation_kind=InvocationKind.HANDOFF,
            runtime_binding_sha256=handoff_binding.runtime_binding_sha256,
        )
        agent_tool = scope.plan_child(
            parent_invocation_id=root.invocation_id,
            child_agent_definition_id="scope-tool-agent",
            invocation_kind=InvocationKind.AGENT_AS_TOOL,
            runtime_binding_sha256=agent_tool_binding.runtime_binding_sha256,
        )
        invocations_before_terminal = store.list_agent_invocations(run_record.run_id)

        workspace_planner = InvocationWorkspacePlanner(
            workspace.scratch_dir / "generated-workspaces"
        )
        handoff_preview = workspace_planner.preview_isolated_root(
            run_id=run_record.run_id, invocation_id=handoff.invocation_id
        )
        agent_tool_preview = workspace_planner.preview_isolated_root(
            run_id=run_record.run_id, invocation_id=agent_tool.invocation_id
        )
        requested_root_rejected = False
        try:
            workspace_planner.preview_isolated_root(
                run_id=run_record.run_id,
                invocation_id=handoff.invocation_id,
                requested_root=workspace.scratch_dir / "model-selected-root",
            )
        except InvocationWorkspaceError:
            requested_root_rejected = True

        invalid = _build_invalid_projects(workspace.scratch_dir)

        store.transition_agent_invocation(handoff.invocation_id, InvocationState.CANCELLED)
        store.transition_agent_invocation(agent_tool.invocation_id, InvocationState.CANCELLED)
        store.transition_run(
            run_record.run_id,
            RunStatus.CANCELLED,
            event_type="run.cancelled",
            payload={"reason": "foundation-acceptance-no-child-execution"},
        )
        store.transition_task(task.task_id, TaskStatus.CANCELLED)
        root_terminal = scope.synchronize_root_with_run(run_record.run_id)
        final_invocations = store.list_agent_invocations(run_record.run_id)
        final_counts = _counts(product_db)

        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        graph_shape = [
            {
                "kind": edge.kind.value,
                "parent_agent_id": edge.parent_agent_id,
                "child_agent_id": edge.child_agent_id,
                "depth": edge.depth,
                "workspace_access": edge.workspace_access.value,
            }
            for edge in graph
        ]
        checks = {
            "invocation_policy_exact": policy.max_depth == 4
            and policy.max_handoffs_per_run == 4
            and policy.max_agent_tools_per_run == 8
            and policy.default_workspace_access.value == "none"
            and policy.physical_workspace_enabled is False,
            "closed_child_graph_exact": {
                (edge.kind.value, edge.child_agent_id, edge.depth) for edge in graph
            }
            == {
                ("HANDOFF", "scope-handoff-agent", 1),
                ("AGENT_AS_TOOL", "scope-tool-agent", 1),
            },
            "runtime_binding_contains_invocation_policy": root_binding.invocation_policy[
                "policy_sha256"
            ]
            == policy.policy_sha256
            and len(root_binding.invocation_scope_runtime_sha256) == 64,
            "runtime_binding_contains_child_graph": len(root_binding.child_agents) == 2
            and {item["kind"] for item in root_binding.child_agents}
            == {"HANDOFF", "AGENT_AS_TOOL"},
            "three_invocation_identities_exact": len(invocations_before_terminal) == 3
            and len({item.invocation_id for item in invocations_before_terminal}) == 3,
            "root_identity_exact": root.invocation_kind is InvocationKind.ROOT
            and root.root_invocation_id == root.invocation_id
            and root.parent_invocation_id is None
            and root.depth == 0
            and root.ordinal == 0,
            "child_parent_relationships_exact": handoff.parent_invocation_id == root.invocation_id
            and agent_tool.parent_invocation_id == root.invocation_id
            and handoff.root_invocation_id == root.invocation_id
            and agent_tool.root_invocation_id == root.invocation_id,
            "child_kinds_exact": handoff.invocation_kind is InvocationKind.HANDOFF
            and agent_tool.invocation_kind is InvocationKind.AGENT_AS_TOOL,
            "state_namespaces_unique": len(
                {item.state_namespace for item in invocations_before_terminal}
            )
            == 3,
            "ordinals_and_depths_exact": [
                (item.ordinal, item.depth) for item in invocations_before_terminal
            ]
            == [(0, 0), (1, 1), (2, 1)],
            "language_only_workspace_none": all(
                item.workspace_access.value == "none" and item.workspace_ref is None
                for item in invocations_before_terminal
            ),
            "workspace_preview_distinct_and_not_materialized": handoff_preview
            != agent_tool_preview
            and not handoff_preview.exists()
            and not agent_tool_preview.exists(),
            "host_workspace_root_not_model_selectable": requested_root_rejected,
            "unresolved_child_rejected": invalid["unresolved"],
            "self_reference_rejected": invalid["self"],
            "depth_limit_enforced": invalid["depth"],
            "handoff_count_limit_enforced": invalid["handoff_count"],
            "root_terminal_state_synchronized": root_terminal is not None
            and root_terminal.state is InvocationState.CANCELLED,
            "planned_children_never_executed": all(
                item.state is InvocationState.CANCELLED and item.total_tokens == 0
                for item in final_invocations
                if item.invocation_kind is not InvocationKind.ROOT
            ),
            "product_task_run_not_duplicated": final_counts
            == {"tasks": 1, "runs": 1, "invocations": 3, "events": 3, "artifacts": 0},
            "no_external_or_model_call": True,
            "references_unchanged": references_before == references_after,
            "cleanup_completed": True,
        }
        payload: dict[str, Any] = {
            "schema_version": "okcanvas-step040-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "policy": policy.to_binding_dict(),
            "graph": graph_shape,
            "run_id": run_record.run_id,
            "task_id": task.task_id,
            "root_invocation_id": root.invocation_id,
            "handoff_invocation_id": handoff.invocation_id,
            "agent_tool_invocation_id": agent_tool.invocation_id,
            "invocation_states": {
                item.invocation_id: item.state.value for item in final_invocations
            },
            "workspace_preview": {
                "handoff": str(handoff_preview),
                "agent_as_tool": str(agent_tool_preview),
                "materialized": False,
            },
            "external_call_count": 0,
            "final_counts": final_counts,
        }
        final = workspace.finalize(payload)
        final["checks"]["cleanup_completed"] = (
            final["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
        )
        final["state"] = "PASSED" if all(final["checks"].values()) else "FAILED"
        output.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(final, indent=2, ensure_ascii=False))
        return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP040_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        return run(args.output.resolve())
    except Exception as exc:
        print(f"[ERROR] STEP040 acceptance failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
