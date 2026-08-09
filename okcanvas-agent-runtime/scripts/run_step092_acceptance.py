from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from scripts.package_source import DEFAULT_OUTPUT, PACKAGE_STEP
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step081_architecture import validate as validate_architecture

STEP = "STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS"
VERSION = "2.76.0"
PARENT_PATH = ROOT / "docs/evidence/STEP091D_DETERMINISTIC_ACCEPTANCE.json"
POSTGRESQL_LIVE_PATH = ROOT / "docs/evidence/windows/STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE.json"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP092_DETERMINISTIC_ACCEPTANCE.json"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run(command: list[str]) -> tuple[bool, str]:
    process = subprocess.run(
        command, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    return process.returncode == 0, process.stdout


def run(output: Path, *, emit_stdout: bool = True) -> int:
    started_at = _now()
    parent = json.loads(PARENT_PATH.read_text(encoding="utf-8"))
    postgresql_live = json.loads(POSTGRESQL_LIVE_PATH.read_text(encoding="utf-8"))
    registry = validate_registry()
    architecture = validate_architecture()
    focused_ok, focused_output = _run([
        sys.executable, "-m", "pytest", "-q",
        "tests/test_step092_session_contextual_follow_up_and_stable_entity_focus.py",
        "tests/test_step090_organization_context_ambiguous_result_normalization.py",
        "tests/test_step091_organization_context_mcp_output_adapter_and_tool_choice.py",
        "tests/test_step088_organization_context_session_delegation.py",
        "tests/test_step091b3_postgresql_approval_evaluation_and_session_metadata.py",
        "tests/test_baseline_version.py", "tests/test_runtime_info.py",
        "tests/test_packaging_policy.py", "tests/test_step081_windows_entrypoint_and_launcher_registry.py",
    ])
    compile_ok, compile_output = _run([
        sys.executable, "-m", "compileall", "-q",
        "okcanvas_agent_runtime", "okcanvas_agent_protocols", "okcanvas_agent_clients", "scripts", "tests",
    ])

    focus_source = (ROOT / "okcanvas_agent_runtime/domain/sessions/context_focus.py").read_text(encoding="utf-8")
    session_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/sessions/runtime_service.py").read_text(encoding="utf-8")
    pg_session_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/postgresql/session_runtime.py").read_text(encoding="utf-8")
    route_source = (ROOT / "okcanvas_agent_runtime/application/assistant_routing/session_context.py").read_text(encoding="utf-8")
    normalizer_source = (ROOT / "okcanvas_agent_runtime/application/organization_context/result_normalization.py").read_text(encoding="utf-8")
    execution_source = (ROOT / "okcanvas_agent_runtime/application/execution/service.py").read_text(encoding="utf-8")
    service_source = (ROOT / "okcanvas_agent_runtime/application/service/use_cases.py").read_text(encoding="utf-8")
    admin_source = (ROOT / "okcanvas_agent_runtime/application/admin/use_cases.py").read_text(encoding="utf-8")
    policy = json.loads((ROOT / "specs/assistant/session-context-follow-up-policy.json").read_text(encoding="utf-8"))

    checks = {
        "identity_exact": CURRENT_STEP == STEP and PROJECT_VERSION == VERSION,
        "step091d_parent_retained": parent.get("state") == "PASSED" and parent.get("passed_checks") == parent.get("total_checks") == 19,
        "real_postgresql_parent_live_retained": postgresql_live.get("state") == "PASSED" and postgresql_live.get("passed_checks") == postgresql_live.get("total_checks") == 19,
        "session_context_policy_exact": policy.get("policy_id") == "session-contextual-follow-up-stable-entity-v1" and policy.get("version") == "1.0.0" and policy.get("max_candidates") == 20,
        "stable_entity_focus_domain_present": all(token in focus_source for token in ("SessionContextFocusObservation", "SessionContextEntityRef", "AMBIGUOUS", "MULTIPLE")),
        "sqlite_session_focus_metadata_present": "CREATE TABLE IF NOT EXISTS product_session_context_focus" in session_source and "context_sha256" in session_source and "source_turn_count INTEGER NOT NULL" in session_source,
        "postgresql_session_focus_metadata_present": "CREATE TABLE IF NOT EXISTS product_session_context_focus" in pg_session_source and "context_sha256" in pg_session_source and "source_turn_count INTEGER NOT NULL" in pg_session_source,
        "focus_commit_is_turn_atomic": "if should_commit and context_focus is not None" in session_source and "_commit_context_focus" in session_source,
        "focus_read_validates_history_key": "self._validate_record_key(session_record)" in session_source,
        "focus_recency_is_last_committed_turn_only": "record.source_turn_count != session_record.turn_count" in session_source and "source_turn_count=turn_count" in session_source,
        "contextual_router_uses_stable_get": "OrganizationContextPreferredOperation.GET" in route_source and "model-guessing-blocked" in route_source,
        "contextual_router_supports_discourse_ellipsis": "_strip_continuation_prefix" in route_source and "continuation_prefixes" in route_source,
        "normalized_tool_evidence_drives_focus": '"session_context_focus": focus' in normalizer_source and "return observation.to_public_dict()" in normalizer_source,
        "ambiguous_candidate_bound_matches_focus": "candidates = candidates[:20]" in normalizer_source,
        "stable_get_result_fenced_to_routing_hint": "GET_STABLE_ENTITY_EVIDENCE_MISMATCH" in normalizer_source and "ROUTING_HINT_TOOL_MISMATCH" in normalizer_source and "len(records) != 1" in normalizer_source and "GET_STABLE_ENTITY_CARDINALITY_MISMATCH" in normalizer_source,
        "preflight_uses_one_session_focus_route_snapshot": service_source.count("decision = self._assistant_route_decision(route_request, principal)") == 1 and admin_source.count("decision = self._assistant_route_decision(route_request)") == 1,
        "admin_wraps_organization_context_routing_hint": "self._assistant.organization_remote.policy.root_agent_id" in admin_source and "self._assistant.organization_remote.policy.agent_id" in admin_source,
        "execution_commits_focus_only_after_success": "context_focus=session_context_focus" in execution_source and 'event_type="session.turn.completed"' in execution_source,
        "raw_tool_result_not_persisted_in_focus": '"context_focus_raw_tool_result_persisted": False' in execution_source,
        "launcher_registry_current_exact": registry.get("state") == "PASSED" and registry.get("current_step") == STEP and registry.get("current_step_token") == "092" and registry.get("current_record_count") == 2,
        "architecture_regression_passed": architecture.get("state") == "PASSED" and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "focused_regression_passed": focused_ok,
        "compileall_passed": compile_ok,
        "package_identity_exact": PACKAGE_STEP == STEP and DEFAULT_OUTPUT.name == "okcanvas-agent-runtime-step092-session-contextual-follow-up-and-stable-entity-focus.zip",
    }
    payload = {
        "schema_version": "okcanvas-step092-deterministic-acceptance-v1",
        "step": STEP, "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started_at, "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step091d_parent": parent,
        "postgresql_live_parent": postgresql_live,
        "launcher_registry": registry,
        "architecture_validation": architecture,
        "focused_output": focused_output,
        "compile_output": compile_output,
        "limitations": {
            "tests_deferred_by_user_until_minio_ready": False,
            "real_object_storage_server_executed_for_step091d": False,
            "cross_domain_context_focus_implemented": False,
            "organization_relational_follow_up_implemented": False,
            "model_generated_context_focus_enabled": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if emit_stdout:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    return run(args.output.resolve(), emit_stdout=not args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
