from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.domain.invocations import (
    ChildAgentGraphResolver,
    InvocationGraphError,
    InvocationKind,
    InvocationPolicyCatalog,
    InvocationState,
    InvocationWorkspaceError,
    InvocationWorkspacePlanner,
    WorkspaceAccess,
)
from okcanvas_agent_runtime.application.invocations.service import InvocationScopeService
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import RunStatus, TaskStatus

ROOT = Path(__file__).resolve().parents[1]


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
    target.write_text(json.dumps(payload), encoding="utf-8")


def _write_agent(
    project: Path,
    agent_id: str,
    *,
    handoffs: list[str] | None = None,
    agent_tools: list[str] | None = None,
) -> None:
    directory = project / "specs" / "agents" / agent_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "instructions.md").write_text(f"Instructions for {agent_id}.\n", encoding="utf-8")
    (directory / "output.schema.json").write_text("{}\n", encoding="utf-8")
    (directory / "definition.json").write_text(
        json.dumps(
            {
                "schema_version": "okcanvas-agent-definition-v1",
                "agent_id": agent_id,
                "version": "1.0.0",
                "name": agent_id,
                "instructions_file": "instructions.md",
                "output_schema_file": "output.schema.json",
                "output_contract": "CodingAgentResult",
                "tools": [],
                "mcp_servers": [],
                "handoffs": handoffs or [],
                "agent_tools": agent_tools or [],
                "workspace_access": "none",
                "max_turns": 2,
                "workflow_name": "Invocation scope fixture",
                "session_mode": "disabled",
            }
        ),
        encoding="utf-8",
    )


def _fixture_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    _write_policy(project)
    import shutil
    shutil.copytree(ROOT / "specs/capabilities", project / "specs/capabilities")
    model_policy = project / "specs" / "runtime" / "model-routing-policy.json"
    model_policy.write_text(
        (ROOT / "specs/runtime/model-routing-policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    retry_policy = project / "specs" / "runtime" / "model-retry-policy.json"
    retry_policy.write_text(
        (ROOT / "specs/runtime/model-retry-policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    reasoning_policy = project / "specs" / "runtime" / "reasoning-evidence-policy.json"
    reasoning_policy.write_text(
        (ROOT / "specs/runtime/reasoning-evidence-policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    response_storage_policy = (
        project / "specs" / "runtime" / "openai-response-storage-policy.json"
    )
    response_storage_policy.write_text(
        (ROOT / "specs/runtime/openai-response-storage-policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    provider_identifier_policy = (
        project / "specs" / "runtime" / "openai-provider-identifier-policy.json"
    )
    provider_identifier_policy.write_text(
        (ROOT / "specs/runtime/openai-provider-identifier-policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    trace_export_policy = (
        project / "specs" / "runtime" / "openai-trace-export-policy.json"
    )
    trace_export_policy.write_text(
        (ROOT / "specs/runtime/openai-trace-export-policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    sandbox_policy = (
        project / "specs" / "sandbox" / "policies" / "default-sandbox-runtime-policy.json"
    )
    sandbox_policy.parent.mkdir(parents=True, exist_ok=True)
    sandbox_policy.write_bytes(
        (ROOT / "specs/sandbox/policies/default-sandbox-runtime-policy.json").read_bytes()
    )
    sandbox_provider = (
        project / "specs" / "sandbox" / "providers" / "docker-local-v1" / "provider.json"
    )
    sandbox_provider.parent.mkdir(parents=True, exist_ok=True)
    sandbox_provider.write_bytes(
        (ROOT / "specs/sandbox/providers/docker-local-v1/provider.json").read_bytes()
    )
    mcp = project / "specs" / "mcp" / "allowlist.json"
    mcp.parent.mkdir(parents=True, exist_ok=True)
    mcp.write_text(json.dumps({"schema_version": "okcanvas-mcp-allowlist-v1", "allowed_server_ids": []}), encoding="utf-8")
    _write_agent(
        project,
        "scope-root-agent",
        handoffs=["scope-handoff-agent"],
        agent_tools=["scope-tool-agent"],
    )
    _write_agent(project, "scope-handoff-agent")
    _write_agent(project, "scope-tool-agent")
    return project


def test_child_graph_and_runtime_binding_are_closed_and_runtime_bound(tmp_path: Path) -> None:
    project = _fixture_project(tmp_path)
    definitions = AgentDefinitionCatalog(project)
    root = definitions.resolve("scope-root-agent")
    assert root.handoffs == ("scope-handoff-agent",)
    assert root.agent_tools == ("scope-tool-agent",)
    assert root.workspace_access == "none"

    policy = InvocationPolicyCatalog(project).resolve()
    graph = ChildAgentGraphResolver(definitions, policy).resolve(root)
    assert [(edge.kind.value, edge.child_agent_id, edge.depth) for edge in graph] == [
        ("AGENT_AS_TOOL", "scope-tool-agent", 1),
        ("HANDOFF", "scope-handoff-agent", 1),
    ]

    binding = AgentRuntimeBindingCatalog(project).resolve(root)
    assert binding.invocation_policy["policy_sha256"] == policy.policy_sha256
    assert len(binding.invocation_scope_runtime_sha256) == 64
    assert {item["kind"] for item in binding.child_agents} == {"HANDOFF", "AGENT_AS_TOOL"}
    assert binding.runtime_binding_sha256 != root.definition_sha256


def test_child_graph_rejects_unresolved_self_cycle_and_bounds(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_policy(project, max_depth=1, max_handoffs_per_run=1)
    _write_agent(project, "unresolved-root", handoffs=["missing-agent"])
    definitions = AgentDefinitionCatalog(project)
    policy = InvocationPolicyCatalog(project).resolve()
    with pytest.raises(InvocationGraphError):
        ChildAgentGraphResolver(definitions, policy).resolve(definitions.resolve("unresolved-root"))

    _write_agent(project, "self-root", handoffs=["self-root"])
    with pytest.raises(InvocationGraphError):
        ChildAgentGraphResolver(definitions, policy).resolve(definitions.resolve("self-root"))

    _write_agent(project, "depth-root", handoffs=["depth-child"])
    _write_agent(project, "depth-child", handoffs=["depth-grandchild"])
    _write_agent(project, "depth-grandchild")
    with pytest.raises(InvocationGraphError):
        ChildAgentGraphResolver(definitions, policy).resolve(definitions.resolve("depth-root"))

    _write_agent(project, "count-root", handoffs=["count-a", "count-b"])
    _write_agent(project, "count-a")
    _write_agent(project, "count-b")
    with pytest.raises(InvocationGraphError):
        ChildAgentGraphResolver(definitions, policy).resolve(definitions.resolve("count-root"))


def test_invocation_ledger_has_distinct_parent_child_state_and_no_workspace(tmp_path: Path) -> None:
    project = _fixture_project(tmp_path)
    definitions = AgentDefinitionCatalog(project)
    policy = InvocationPolicyCatalog(project).resolve()
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    task = store.create_task(
        task_type="INVOCATION_SCOPE_FIXTURE",
        input_sha256="a" * 64,
        agent_definition_id="scope-root-agent",
        agent_definition_version="1.0.0",
    )
    run = store.create_run(task_id=task.task_id)
    store.transition_task(task.task_id, TaskStatus.RUNNING)
    store.transition_run(run.run_id, RunStatus.RUNNING, event_type="run.started")

    bindings = AgentRuntimeBindingCatalog(project)
    service = InvocationScopeService(definitions=definitions, store=store, policy=policy)
    root = service.ensure_root(
        run_id=run.run_id,
        agent_definition_id="scope-root-agent",
        runtime_binding_sha256=bindings.resolve(definitions.resolve("scope-root-agent")).runtime_binding_sha256,
    )
    handoff = service.plan_child(
        parent_invocation_id=root.invocation_id,
        child_agent_definition_id="scope-handoff-agent",
        invocation_kind=InvocationKind.HANDOFF,
        runtime_binding_sha256=bindings.resolve(definitions.resolve("scope-handoff-agent")).runtime_binding_sha256,
    )
    agent_tool = service.plan_child(
        parent_invocation_id=root.invocation_id,
        child_agent_definition_id="scope-tool-agent",
        invocation_kind=InvocationKind.AGENT_AS_TOOL,
        runtime_binding_sha256=bindings.resolve(definitions.resolve("scope-tool-agent")).runtime_binding_sha256,
    )

    records = store.list_agent_invocations(run.run_id)
    assert [item.ordinal for item in records] == [0, 1, 2]
    assert len({item.invocation_id for item in records}) == 3
    assert len({item.state_namespace for item in records}) == 3
    assert root.root_invocation_id == root.invocation_id
    assert handoff.parent_invocation_id == root.invocation_id
    assert agent_tool.parent_invocation_id == root.invocation_id
    assert {handoff.invocation_kind, agent_tool.invocation_kind} == {
        InvocationKind.HANDOFF,
        InvocationKind.AGENT_AS_TOOL,
    }
    assert all(item.workspace_access is WorkspaceAccess.NONE for item in records)
    assert all(item.workspace_ref is None for item in records)

    planner = InvocationWorkspacePlanner(tmp_path / "workspaces")
    first = planner.preview_isolated_root(run_id=run.run_id, invocation_id=handoff.invocation_id)
    second = planner.preview_isolated_root(run_id=run.run_id, invocation_id=agent_tool.invocation_id)
    assert first != second
    assert not first.exists() and not second.exists()
    with pytest.raises(InvocationWorkspaceError):
        planner.preview_isolated_root(
            run_id=run.run_id,
            invocation_id=handoff.invocation_id,
            requested_root=tmp_path / "model-selected-root",
        )

    store.transition_run(run.run_id, RunStatus.CANCELLED, event_type="run.cancelled")
    store.transition_task(task.task_id, TaskStatus.CANCELLED)
    terminal = service.synchronize_root_with_run(run.run_id)
    assert terminal is not None and terminal.state is InvocationState.CANCELLED


def test_control_api_lists_run_invocations_with_admin_auth(tmp_path: Path) -> None:
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    definitions = AgentDefinitionCatalog(ROOT)
    definition = definitions.resolve("coding-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    task = store.create_task(
        task_type="INVOCATION_API_FIXTURE",
        input_sha256="b" * 64,
        agent_definition_id=definition.agent_id,
        agent_definition_version=definition.version,
    )
    run = store.create_run(task_id=task.task_id)
    store.transition_task(task.task_id, TaskStatus.RUNNING)
    store.transition_run(run.run_id, RunStatus.RUNNING, event_type="run.started")
    service = InvocationScopeService(
        definitions=definitions,
        store=store,
        policy=InvocationPolicyCatalog(ROOT).resolve(),
    )
    root = service.ensure_root(
        run_id=run.run_id,
        agent_definition_id=definition.agent_id,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )

    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key="step040-admin-key",
    )
    with TestClient(app) as client:
        assert client.get(f"/v1/runs/{run.run_id}/invocations").status_code == 401
        response = client.get(
            f"/v1/runs/{run.run_id}/invocations",
            headers={"X-OKCanvas-Admin-Key": "step040-admin-key"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["invocations"][0]["invocation_id"] == root.invocation_id
    assert payload["invocations"][0]["workspace_access"] == "none"
