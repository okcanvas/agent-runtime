from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step007_runtime_capabilities_are_explicit() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.agent_definition_catalog_implemented is True
    assert info.generic_agent_execution_implemented is True
    assert info.generic_agent_execution_live_accepted is True
    assert info.generic_agent_tools_enabled is True
    assert info.generic_agent_sessions_enabled is True
    assert info.generic_agent_final_output_artifact_implemented is True
    assert info.agent_sdk_lifecycle_event_normalization_implemented is True
    assert info.handoffs_enabled is True
    assert info.mcp_enabled is True


def test_step007_records_exact_reference_paths_and_decisions() -> None:
    plan = (ROOT / "docs/plans/STEP007_GENERIC_AGENT_EXECUTION_SERVICE.md").read_text(
        encoding="utf-8"
    )
    for path in [
        "src/agents/agent.py",
        "src/agents/run.py",
        "src/agents/lifecycle.py",
        "src/agents/result.py",
        "src/agents/usage.py",
        "src/agents/tracing/create.py",
        "src/agents/memory/session.py",
    ]:
        assert path in plan
    assert "ADOPT" in plan
    assert "ADAPT" in plan
    assert "DEFER" in plan
    assert "REJECT for this STEP" in plan


def test_canonical_events_include_generic_lifecycle() -> None:
    events = (ROOT / "specs/runtime/canonical-events.yaml").read_text(encoding="utf-8")
    for event in [
        "agent.definition.resolved",
        "agent.started",
        "model.started",
        "model.completed",
        "agent.completed",
        "agent.failed",
        "artifact.created",
    ]:
        assert event in events
