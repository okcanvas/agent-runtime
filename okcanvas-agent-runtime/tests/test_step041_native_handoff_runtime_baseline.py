from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.package_source import DEFAULT_OUTPUT

ROOT = Path(__file__).resolve().parents[1]


def test_step041_runtime_and_handoff_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/handoffs/models.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/handoffs/policy.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/handoffs/runtime.py"),
        ROOT / "specs/runtime/native-handoff-policy.json",
        ROOT / "specs/agents/handoff-triage-agent/definition.json",
        ROOT / "specs/agents/handoff-specialist-agent/definition.json",
        ROOT / "specs/evaluations/native-handoff-v1/case.json",
        ROOT / "scripts/run_step041_acceptance.py",
        ROOT / "sh_run_step041_acceptance.cmd",
        ROOT / "docs/plans/STEP045_INTEGRATED_WALKING_SKELETON_ACCEPTANCE.md",
        ROOT / "docs/reference/STEP041_NATIVE_HANDOFF_RUNTIME_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP041_ACCEPTANCE.json",
        ROOT / "docs/evidence/STEP041_VALIDATION.txt",
        ROOT / "docs/evidence/STEP040_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step041_baseline_identifiers_are_current() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"


def test_step041_native_handoff_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(
        encoding="utf-8"
    )
    execution = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(
        encoding="utf-8"
    )
    invocation = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/invocations/service.py")).read_text(
        encoding="utf-8"
    )
    policy = (ROOT / "specs/runtime/native-handoff-policy.json").read_text(encoding="utf-8")
    assert "build_sdk_native_handoff" in gateway
    assert "agent.handoff" in execution
    assert "begin_handoff" in invocation
    assert '"max_handoffs_per_run": 1' in policy
    assert '"input_filter_mode": "REMOVE_ALL_TOOLS"' in policy
    assert '"nest_handoff_history": false' in policy
    packaging = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    assert DEFAULT_OUTPUT.name in packaging
