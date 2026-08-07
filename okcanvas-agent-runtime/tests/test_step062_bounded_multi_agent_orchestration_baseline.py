from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.admin.projections import agent_definition_summary
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.application.orchestration import BoundedOrchestrationPolicyCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_step062_runtime_baseline_is_exact() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.sdk_examples_coverage_matrix_windows_live_accepted is True
    assert info.bounded_multi_agent_orchestration_implemented is True
    assert info.bounded_multi_agent_orchestration_policy_id == "default-bounded-multi-agent-orchestration"
    assert info.bounded_multi_agent_orchestration_child_count == 2
    assert info.bounded_multi_agent_orchestration_max_parallelism == 2
    assert info.bounded_multi_agent_orchestration_max_depth == 1
    assert info.bounded_multi_agent_orchestration_failure_mode == "ALL_REQUIRED_FAIL_FAST"
    assert info.bounded_multi_agent_orchestration_cancellation_mode == "CANCEL_PENDING_SIBLINGS"
    assert info.bounded_multi_agent_orchestration_aggregation_mode == "DECLARATION_ORDER_STRUCTURED"
    assert info.bounded_multi_agent_orchestration_root_model_calls == 0
    assert info.bounded_multi_agent_orchestration_child_output_contract == "CodingAgentResult"
    assert info.bounded_multi_agent_orchestration_root_output_contract == "BoundedOrchestrationResult"
    assert info.bounded_multi_agent_orchestration_session_enabled is False
    assert info.bounded_multi_agent_orchestration_tools_enabled is False
    assert info.bounded_multi_agent_orchestration_mcp_enabled is False
    assert info.bounded_multi_agent_orchestration_workspace_enabled is False
    assert info.bounded_multi_agent_orchestration_native_child_streaming_enabled is False
    assert info.bounded_multi_agent_orchestration_deterministic_accepted is True
    assert info.bounded_multi_agent_orchestration_windows_live_accepted is True


def test_step062_agent_graph_policy_binding_and_api_visibility_are_exact() -> None:
    definitions = AgentDefinitionCatalog(ROOT)
    root = definitions.resolve("bounded-orchestration-manager-agent")
    policy = BoundedOrchestrationPolicyCatalog(ROOT).resolve()
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root)
    public = agent_definition_summary(root)

    assert root.orchestration_children == (
        "bounded-orchestration-architecture-agent",
        "bounded-orchestration-risk-agent",
    )
    assert policy.child_count == policy.max_parallelism == 2
    assert binding.execution_path == "bounded-multi-agent-orchestration-v1"
    assert [item["ordinal"] for item in binding.child_agents] == [1, 2]
    assert public.orchestration_children == list(root.orchestration_children)
    assert len(binding.runtime_binding_sha256) == 64
    assert len(binding.orchestration_runtime_sha256 or "") == 64


def test_step062_code_and_document_set_is_present() -> None:
    required = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/orchestration/models.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/orchestration/policy.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/orchestration/runtime.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/orchestration/openai_runtime.py"),
        ROOT / "specs/runtime/bounded-orchestration-policy.json",
        ROOT / "specs/agents/bounded-orchestration-manager-agent/definition.json",
        ROOT / "specs/agents/bounded-orchestration-architecture-agent/definition.json",
        ROOT / "specs/agents/bounded-orchestration-risk-agent/definition.json",
        ROOT / "docs/plans/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION.md",
        ROOT / "docs/reference/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION_CODE_AUDIT.md",
        ROOT / "scripts/run_step062_acceptance.py",
        ROOT / "sh_run_step062_acceptance.cmd",
    )
    assert all(path.is_file() for path in required)
