from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]


def test_step040_runtime_and_plan_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/invocations/models.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/invocations/policy.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/invocations/graph.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/invocations/service.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/invocations/workspace.py"),
        ROOT / "specs/runtime/sub-agent-invocation-policy.json",
        ROOT / "scripts/run_step040_acceptance.py",
        ROOT / "sh_run_step040_acceptance.cmd",
        ROOT / "docs/plans/STEP045_INTEGRATED_WALKING_SKELETON_ACCEPTANCE.md",
        ROOT / "docs/reference/STEP040_SUB_AGENT_INVOCATION_SCOPE_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP040_ACCEPTANCE.json",
        ROOT / "docs/evidence/STEP040_VALIDATION.txt",
        ROOT / "docs/evidence/STEP039_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step040_baseline_identifiers_are_current() -> None:
    baseline = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'PROJECT_VERSION = "2.75.0"' in baseline
    assert 'CURRENT_STEP = "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"' in baseline
    assert 'version = "2.75.0"' in pyproject
