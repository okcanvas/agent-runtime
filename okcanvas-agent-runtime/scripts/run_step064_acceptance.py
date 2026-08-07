from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from scripts.node_acceptance import run_command, run_node_tests, validate_committed_typescript_release

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP064_ACCEPTANCE.json"
POLICY_SHA256 = "379e868d22b7b6c216fe2988d875846ed021f53cd8cb86f5630c399f68519d99"
ENCRYPTION_SOURCE_SHA256 = "b2127cf828e1e4d44663295edac0b4451d8b452a352e73789b3272d6e7a781b0"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> int:
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
    from okcanvas_agent_runtime.domain.sessions import SQLiteSessionPolicyCatalog

    info = RuntimeInfo()
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    predecessor = _load_json(ROOT / "docs/evidence/STEP063A_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    compaction_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/compaction.py")).read_text(encoding="utf-8")
    session_service_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/service.py")).read_text(encoding="utf-8")
    gateway_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    execution_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(encoding="utf-8")
    approval_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/tool_approval/service.py")).read_text(encoding="utf-8")
    binding_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text(encoding="utf-8")
    sdk_source = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/src/agents/memory/openai_responses_compaction_session.py"
    ).read_text(encoding="utf-8")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step064_bounded_encrypted_sqlite_session_compaction.py",
        ],
        ROOT,
    )
    historical_files = [
        "tests/test_sqlite_session_runtime.py",
        "tests/test_sqlite_session_approval_composition.py",
        "tests/test_sqlite_session_handoff_composition.py",
        "tests/test_sqlite_session_guardrail_composition.py",
        "tests/test_sqlite_session_agent_tool_composition.py",
        "tests/test_sqlite_session_mcp_composition.py",
    ]
    historical_ok, historical_output = run_command(
        [sys.executable, "-m", "pytest", "-q", *historical_files], ROOT
    )
    compile_ok, compile_output = run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "src",
            "scripts/run_step064_acceptance.py",
        ],
        ROOT,
    )
    release_ok, release_output = validate_committed_typescript_release(
        ROOT / "clients/cli"
    )
    node_ok, node_output = run_node_tests(ROOT / "clients/cli")
    no_reference_imports_ok, no_reference_imports_output = run_command(
        [sys.executable, "scripts/verify_no_reference_imports.py"], ROOT
    )
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    release_index = execution_source.index("session_record = self._sessions.release_turn(")
    compact_index = execution_source.index("await self._sessions.compact_after_committed_turn(")
    terminal_index = execution_source.index("RunStatus.SUCCEEDED", compact_index)

    required_docs = [
        ROOT / "docs/plans/STEP064_BOUNDED_ENCRYPTED_SQLITE_SESSION_COMPACTION_V1.md",
        ROOT / "docs/reference/STEP064_BOUNDED_ENCRYPTED_SQLITE_SESSION_COMPACTION_V1_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP063A_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    ]
    docs_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in [ROOT / "HANDOFF.md", ROOT / "PLANS.md", ROOT / "docs/plans/ROADMAP.md"]
    )

    checks = {
        "baseline_version_and_step_exact": (
            info.version == "2.44.1"
            and info.step == "STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX"
            and 'PROJECT_VERSION = "2.44.1"' in baseline_source
            and 'CURRENT_STEP = "STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX"'
            in baseline_source
        ),
        "step063a_windows_live_closure_exact": (
            predecessor.get("state") == "PASSED"
            and predecessor.get("passed_checks") == 20
            and predecessor.get("total_checks") == 20
            and predecessor.get("corrected_step063_passed_checks") == 33
        ),
        "predecessor_runtime_flags_closed": (
            info.strict_encrypted_sqlite_session_history_windows_live_accepted is True
            and info.windows_symlink_integrity_test_windows_live_accepted is True
        ),
        "session_policy_identity_and_sha_exact": (
            policy.schema_version == "okcanvas-sqlite-session-policy-v3"
            and policy.policy_id == "local-strict-encrypted-compacted-sqlite-session-v1"
            and policy.version == "3.0.0"
            and policy.policy_sha256 == POLICY_SHA256
            and _sha256(ROOT / "specs/runtime/sqlite-session-policy.json") == POLICY_SHA256
        ),
        "session_policy_compaction_bounds_exact": (
            policy.compaction_enabled is True
            and policy.compaction_mode == "INPUT_ONLY"
            and policy.compaction_provider == "openai"
            and policy.compaction_api == "responses.compact"
            and policy.compaction_model == "gpt-4.1"
            and policy.compaction_trigger_candidate_items == 10
            and policy.compaction_max_input_items == 256
            and policy.compaction_store is False
            and policy.compaction_previous_response_id_allowed is False
            and policy.compaction_automatic is True
            and policy.compaction_restore_previous_on_failure is True
            and policy.compaction_raw_history_in_events is False
        ),
        "step063_encryption_source_unchanged": (
            _sha256(legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/encryption.py"))
            == ENCRYPTION_SOURCE_SHA256
        ),
        "step064_runtime_flags_exact": (
            info.sqlite_session_compaction_enabled is True
            and info.sqlite_session_compaction_mode == "input-only"
            and info.sqlite_session_compaction_trigger_candidate_items == 10
            and info.sqlite_session_compaction_max_input_items == 256
            and info.sqlite_session_compaction_store_enabled is False
            and info.sqlite_session_compaction_previous_response_id_enabled is False
            and info.sqlite_session_compaction_runs_inside_runner is False
            and info.sqlite_session_compaction_post_commit_only is True
            and info.sqlite_session_compaction_database_lease_enforced is True
            and info.sqlite_session_compaction_provider_request_event_recorded is True
            and info.sqlite_session_compaction_token_usage_recorded is False
            and info.bounded_encrypted_sqlite_session_compaction_deterministic_accepted is True
            and info.bounded_encrypted_sqlite_session_compaction_windows_live_accepted is False
        ),
        "pinned_sdk_candidate_contract_exact": (
            "DEFAULT_COMPACTION_THRESHOLD = 10" in sdk_source
            and 'item.get("type") == "compaction"' in sdk_source
            and 'item.get("role") == "user"' in sdk_source
            and "compact_kwargs[\"input\"] = session_items" in sdk_source
        ),
        "input_only_store_false_no_response_id_exact": all(
            marker in compaction_source
            for marker in (
                '"force": True',
                '"compaction_mode": "input"',
                '"store": False',
                "Session compaction cannot accept a provider response ID",
            )
        ),
        "bounded_input_and_strict_reduction_exact": (
            "len(before) > self.policy.compaction_max_input_items" in compaction_source
            and "non-empty strict item reduction" in compaction_source
        ),
        "exact_history_restore_on_failure_present": (
            "async def _restore_exact_history" in compaction_source
            and "restored != before" in compaction_source
            and '"exact_history_restored": True' in compaction_source
        ),
        "official_zero_retry_lazy_compactor_exact": all(
            marker in session_service_source
            for marker in (
                'base_url="https://api.openai.com/v1"',
                "max_retries=0",
                "OPENAI_API_KEY is required when Session compaction threshold is reached",
            )
        ),
        "runner_uses_encrypted_session_without_compaction_wrapper": (
            "BoundedEncryptedCompactionSession" not in gateway_source
            and "session_runtime.sdk_session(session_id)" in gateway_source
        ),
        "generic_execution_compaction_is_post_commit": release_index < compact_index < terminal_index,
        "approval_paths_compact_only_after_committed_turn": (
            approval_source.count("await self._sessions.compact_after_committed_turn(") == 2
            and approval_source.count("session.turn.completed") >= 2
        ),
        "database_compaction_lease_exact": all(
            marker in session_service_source
            for marker in (
                '"WHERE session_id=? AND active_run_id IS NULL"',
                'current.active_run_id != run_id',
                '"UPDATE product_session SET active_run_id=NULL, item_count=?',
                "Session already has an active Turn or compaction lease",
            )
        ),
        "catalog_item_count_updated_after_compaction": (
            '"UPDATE product_session SET active_run_id=NULL, item_count=?' in session_service_source
            and '"output_item_count": item_count' in session_service_source
        ),
        "metadata_only_compaction_events_exact": (
            '"history_persisted_in_product_events": False' in compaction_source
            and '"provider_request_count": 1' in compaction_source
            and '"provider_token_usage_recorded": False' in compaction_source
            and '"history_persisted_in_product_events": False' in session_service_source
        ),
        "runtime_binding_includes_compaction_source": (
            binding_source.count('"okcanvas_agent_runtime.domain.sessions.compaction"') == 6
        ),
        "focused_compaction_tests_pass": focused_ok and "11 passed" in focused_output and "skipped" not in focused_output,
        "historical_session_compositions_pass": historical_ok and "29 passed" in historical_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok and "VERIFIED" in release_output,
        "node_tests_pass": node_ok and "# pass 14" in node_output,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step064_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launcher_present": (
            (ROOT / "scripts/run_step064_acceptance.py").is_file()
            and (ROOT / "sh_run_step064_acceptance.cmd").is_file()
        ),
        "step065_not_selected": "STEP065_" not in docs_text,
    }

    payload = {
        "schema_version": "okcanvas-step064-acceptance-v1",
        "step": "STEP064_BOUNDED_ENCRYPTED_SQLITE_SESSION_COMPACTION_V1",
        "version": "2.44.1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "policy": {
            "policy_id": policy.policy_id,
            "policy_sha256": policy.policy_sha256,
            "compaction_mode": policy.compaction_mode,
            "compaction_model": policy.compaction_model,
            "trigger_candidate_items": policy.compaction_trigger_candidate_items,
            "max_input_items": policy.compaction_max_input_items,
            "store": policy.compaction_store,
            "previous_response_id_allowed": policy.compaction_previous_response_id_allowed,
            "post_commit_only": True,
        },
        "focused_test_output": focused_output.splitlines()[-1] if focused_output else "",
        "historical_session_output": historical_output.splitlines()[-1] if historical_output else "",
        "python_compile_output": compile_output.splitlines()[-1] if compile_output else "",
        "node_release_output": release_output.splitlines()[-1] if release_output else "",
        "node_test_output_tail": node_output.splitlines()[-1] if node_output else "",
        "reference_import_output_tail": no_reference_imports_output.splitlines()[-1]
        if no_reference_imports_output
        else "",
        "reference_count": len(reference_results),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
