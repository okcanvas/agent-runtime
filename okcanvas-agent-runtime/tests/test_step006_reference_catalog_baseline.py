from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.domain.runs import EventSource


ROOT = Path(__file__).resolve().parents[1]


def test_step006_runtime_capabilities_are_explicit() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.reference_catalog_implemented is True
    assert info.reference_catalog_accepted is True
    assert info.reference_catalog_backend == "immutable-filesystem"
    assert info.reference_tree_verification_enabled is True
    assert info.reference_access_event_recording_implemented is True
    assert info.reference_catalog_mcp_exposed is True


def test_reference_event_source_and_contract_are_declared() -> None:
    assert EventSource.REFERENCE.value == "reference"
    events = (ROOT / "specs/runtime/canonical-events.yaml").read_text(encoding="utf-8")
    assert "reference.search.completed" in events
    assert "reference.file.read" in events
    assert "  - reference" in events


def test_step006_records_exact_upstream_adoption_paths() -> None:
    plan = (ROOT / "docs/plans/STEP006_READ_ONLY_REFERENCE_CATALOG_SERVICE.md").read_text(
        encoding="utf-8"
    )
    assert "src/agents/sandbox/workspace_paths.py" in plan
    assert "src/agents/sandbox/session/archive_extraction.py" in plan
    assert "src/agents/sandbox/util/token_truncation.py" in plan
    assert "ADAPT" in plan
    assert "REJECT for this STEP" in plan


def test_reference_tool_policy_is_read_only_and_bounded() -> None:
    policy = (ROOT / "specs/tools/reference-search/policy.yaml").read_text(encoding="utf-8")
    assert "mode: immutable-read-only" in policy
    assert "verify_tree_before_access: true" in policy
    assert "symbolic_links: forbidden" in policy
    assert "hard_max_results: 100" in policy
    assert "persist_raw_query: false" in policy
    assert "mcp_enabled: false" in policy
