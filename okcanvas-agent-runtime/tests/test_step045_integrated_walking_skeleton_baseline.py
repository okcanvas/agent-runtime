import json
from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step045_assets_and_plan_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/walking_skeleton/models.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/walking_skeleton/catalog.py"),
        ROOT / "specs/runtime/walking-skeleton-scenarios.json",
        ROOT / "scripts/run_step045_acceptance.py",
        ROOT / "sh_run_step045_acceptance.cmd",
        ROOT / "docs/plans/STEP045_INTEGRATED_WALKING_SKELETON_ACCEPTANCE.md",
        ROOT / "docs/reference/STEP045_INTEGRATED_WALKING_SKELETON_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP044_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/evidence/STEP045_ACCEPTANCE.json",
        ROOT / "docs/evidence/STEP045_VALIDATION.txt",
    ]
    assert all(path.is_file() for path in required)


def test_step045_runtime_info_is_current() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.native_guardrail_windows_live_accepted is True
    assert info.walking_skeleton_scenario_catalog_implemented is True
    assert info.walking_skeleton_scenario_count == 10
    assert info.walking_skeleton_runner_matrix_implemented is True
    assert info.walking_skeleton_invocation_visibility_implemented is True
    assert info.basic_agent_runtime_skeleton_complete is True
    assert info.integrated_walking_skeleton_deterministic_accepted is True
    assert info.integrated_walking_skeleton_windows_live_accepted is True


def test_step045_acceptance_is_complete() -> None:
    evidence = json.loads((ROOT / "docs/evidence/STEP045_ACCEPTANCE.json").read_text())
    assert evidence["state"] == "PASSED"
    assert evidence["skeleton_state"] == "BASIC_AGENT_RUNTIME_SKELETON_COMPLETE"
    assert len(evidence["checks"]) == 28
    assert all(evidence["checks"].values())
    assert evidence["scenario_catalog"]["scenario_count"] == 10
    assert len(evidence["primitive_acceptances"]) == 7
