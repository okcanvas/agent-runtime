from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.domain.sessions import SQLiteSessionApprovalPolicyCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_step046_assets_and_handoff_documents_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/approval_policy.py"),
        ROOT / "specs/runtime/sqlite-session-approval-policy.json",
        ROOT / "specs/agents/session-approval-agent/definition.json",
        ROOT / "specs/evaluations/sqlite-session-approval-v1/case.json",
        ROOT / "scripts/run_step046_acceptance.py",
        ROOT / "sh_run_step046_acceptance.cmd",
        ROOT / "docs/plans/STEP049_SQLITE_SESSION_NATIVE_AGENT_AS_TOOL_COMPOSITION_V1.md",
        ROOT / "docs/reference/STEP046_SQLITE_SESSION_APPROVAL_COMPOSITION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP045_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/evidence/STEP046_ACCEPTANCE.json",
        ROOT / "docs/evidence/STEP046_VALIDATION.txt",
    ]
    assert all(path.is_file() for path in required)


def test_step046_runtime_info_is_current() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.integrated_walking_skeleton_windows_live_accepted is True
    assert info.sqlite_session_approval_composition_implemented is True
    assert info.sqlite_session_approval_turn_lease_held_while_interrupted is True
    assert info.sqlite_session_approval_rejected_turn_committed is True
    assert info.sqlite_session_approval_failed_turn_rolled_back is True
    assert info.sqlite_session_approval_raw_history_persisted_in_product_events is False
    assert info.sqlite_session_approval_deterministic_accepted is True
    assert info.sqlite_session_approval_windows_live_accepted is True


def test_step046_policy_definition_and_binding_are_exact() -> None:
    policy = SQLiteSessionApprovalPolicyCatalog(ROOT).resolve()
    assert policy.session_mode == "sqlite-v1"
    assert policy.approval_mode == "ALWAYS"
    assert policy.max_tools == 1
    assert policy.hold_turn_lease_while_interrupted is True
    assert policy.commit_rejected_turn is True
    assert policy.rollback_failed_turn is True
    assert policy.workspace_access == "none"
    definition = AgentDefinitionCatalog(ROOT).resolve("session-approval-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.execution_path == "sqlite-session-approval-execution-v1"
    assert binding.session_policy["approval_composition"]["policy_sha256"] == policy.policy_sha256


def test_step046_acceptance_is_complete() -> None:
    evidence = json.loads((ROOT / "docs/evidence/STEP046_ACCEPTANCE.json").read_text())
    assert evidence["state"] == "PASSED"
    assert len(evidence["checks"]) == 27
    assert all(value is True for value in evidence["checks"].values())
    assert evidence["gateway_counts"] == {
        "prepare": 2,
        "resume": 2,
        "session_closes": 10,
        "session_instances": 10,
    }
    assert evidence["session"]["after_approve"]["turn_count"] == 1
    assert evidence["session"]["after_approve"]["item_count"] == 4
    assert evidence["session"]["after_reject"]["turn_count"] == 2
    assert evidence["session"]["after_reject"]["item_count"] == 8
    assert evidence["final_counts"] == {
        "approvals": 2,
        "artifacts": 1,
        "evaluations": 1,
        "events": 37,
        "invocations": 2,
        "runs": 2,
        "submissions": 2,
        "tasks": 2,
    }
