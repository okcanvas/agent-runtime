from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP065_ACCEPTANCE.json"
STEP = "STEP065_STRICT_SESSION_HISTORY_KEY_ROTATION_AND_RECOVERY_V1"
VERSION = "2.45.0"
SDK_SQLITE_SHA = "55e998777c4d15e667b819965b1bd5d66c7391969e4cd270fdd1a6498dccbf16"


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
    from okcanvas_agent_runtime.domain.sessions import SQLiteSessionKeyRotationPolicyCatalog

    info = RuntimeInfo()
    policy = SQLiteSessionKeyRotationPolicyCatalog(ROOT).resolve()
    predecessor = _load_json(
        ROOT / "docs/evidence/STEP064A_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json"
    )
    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(
        encoding="utf-8"
    )
    rotation_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/rotation.py")
    ).read_text(encoding="utf-8")
    service_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/service.py")
    ).read_text(encoding="utf-8")
    encryption_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/encryption.py")
    ).read_text(encoding="utf-8")
    control_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/app.py")
    ).read_text(encoding="utf-8")
    contract_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/contracts.py")
    ).read_text(encoding="utf-8")
    windows_source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    sdk_source_path = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/src/agents/memory/sqlite_session.py"
    )

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step065_session_history_key_rotation.py",
        ],
        ROOT,
    )
    historical_ok, historical_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_sqlite_session_runtime.py",
            "tests/test_step063_strict_encrypted_sqlite_session_history.py",
            "tests/test_step063a_windows_symlink_integrity_test_portability_fix.py",
            "tests/test_step064_bounded_encrypted_sqlite_session_compaction.py",
            "tests/test_step064a_pytest_async_plugin_independence_fix.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "src",
            "scripts/run_step065_acceptance.py",
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

    required_docs = [
        ROOT / "docs/plans/STEP065_STRICT_SESSION_HISTORY_KEY_ROTATION_AND_RECOVERY_V1.md",
        ROOT
        / "docs/reference/STEP065_STRICT_SESSION_HISTORY_KEY_ROTATION_AND_RECOVERY_V1_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP064A_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
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
            info.version == VERSION
            and info.step == STEP
            and f'PROJECT_VERSION = "{VERSION}"' in baseline_source
            and f'CURRENT_STEP = "{STEP}"' in baseline_source
        ),
        "step064a_windows_live_closure_exact": (
            predecessor.get("reported_state") == "PASSED"
            and predecessor.get("reported_passed_checks") == 19
            and predecessor.get("reported_total_checks") == 19
            and predecessor.get("corrected_step064_state") == "PASSED"
            and predecessor.get("corrected_step064_passed_checks") == 29
        ),
        "predecessor_runtime_flags_closed": (
            info.bounded_encrypted_sqlite_session_compaction_windows_live_accepted is True
            and info.step064_focused_tests_windows_live_accepted is True
        ),
        "rotation_policy_identity_and_sha_exact": (
            policy.schema_version == "okcanvas-sqlite-session-key-rotation-policy-v1"
            and policy.policy_id == "local-explicit-single-session-key-rotation-v1"
            and policy.version == "1.0.0"
            and len(policy.policy_sha256) == 64
            and policy.policy_sha256
            == _sha256(ROOT / "specs/runtime/sqlite-session-key-rotation-policy.json")
        ),
        "rotation_policy_bounds_exact": (
            policy.mode == "EXPLICIT_SINGLE_SESSION"
            and policy.automatic_rotation is False
            and policy.resume_incomplete_rotation is True
            and policy.max_history_items == 256
            and policy.plaintext_mode == "REJECT"
            and policy.mixed_key_envelope_mode == "REJECT"
            and policy.raw_history_in_events is False
            and policy.clear_incomplete_rotation_without_decrypt is True
        ),
        "pinned_sdk_sqlite_source_and_schema_exact": (
            policy.sdk_version == "0.19.0"
            and policy.sdk_sqlite_session_source_sha256 == SDK_SQLITE_SHA
            and _sha256(sdk_source_path) == SDK_SQLITE_SHA
            and policy.sessions_table == "agent_sessions"
            and policy.messages_table == "agent_messages"
            and policy.message_data_column == "message_data"
        ),
        "step065_runtime_flags_exact": (
            info.sqlite_session_key_rotation_implemented is True
            and info.sqlite_session_key_rotation_mode == "explicit-single-session"
            and info.sqlite_session_key_rotation_automatic is False
            and info.sqlite_session_key_rotation_max_history_items == 256
            and info.sqlite_session_key_rotation_resume_incomplete is True
            and info.sqlite_session_key_rotation_mixed_key_mode == "reject"
            and info.sqlite_session_key_rotation_raw_history_in_events is False
            and info.sqlite_session_key_rotation_clear_incomplete_without_decrypt is True
            and info.sqlite_session_key_rotation_deterministic_accepted is True
            and info.sqlite_session_key_rotation_windows_live_accepted is False
        ),
        "external_current_previous_key_boundary_exact": (
            "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY" in windows_source
            and "Current and previous Session history keys must be distinct" in control_source
            and "Previous Session history key must be distinct from the protected payload key"
            in control_source
        ),
        "catalog_intent_and_maintenance_lease_present": (
            "CREATE TABLE IF NOT EXISTS product_session_key_rotation" in service_source
            and "session_rotation_" in service_source
            and "active_run_id" in service_source
        ),
        "physical_row_exact_inspection_present": (
            "SELECT id," in rotation_source
            and "inspect_session_envelope_key_id" in rotation_source
            and "Session history contains invalid JSON" in rotation_source
            and "mixed or unexpected encryption key IDs" in rotation_source
        ),
        "atomic_history_rewrite_and_verification_present": (
            'conn.execute("BEGIN IMMEDIATE")' in rotation_source
            and "conn.executemany" in rotation_source
            and "key rotation verification failed" in rotation_source
            and "conn.commit()" in rotation_source
        ),
        "resume_after_history_commit_present": (
            'observed_mode="ALREADY_TARGET"' in rotation_source
            and "resumed or outcome.observed_mode == \"ALREADY_TARGET\"" in service_source
        ),
        "bounded_and_fail_closed_modes_present": (
            "bounded key rotation item limit" in rotation_source
            and "plaintext or an unsupported encryption envelope" in encryption_source
            and policy.max_history_items == 256
        ),
        "incomplete_rotation_clear_without_decrypt_present": (
            "clear_incomplete_rotation_without_decrypt" in service_source
            and "SQLiteSessionHistoryRotator" in service_source
            and "clear_session" in rotation_source
        ),
        "control_api_rotation_endpoint_exact": (
            '"/v1/sessions/{session_id}/rotate-history-key"' in control_source
            and "SessionKeyRotationResponse" in control_source
            and "okcanvas-session-key-rotation-result-v1" in contract_source
        ),
        "raw_keys_not_in_http_contract": (
            "session_history_key" not in contract_source.lower()
            and "previous_key" not in contract_source.lower()
        ),
        "focused_rotation_tests_pass": focused_ok and "11 passed" in focused_output,
        "historical_session_and_compaction_tests_pass": historical_ok,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok and "VERIFIED" in release_output,
        "node_tests_pass": node_ok and "# pass 14" in node_output,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step065_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launcher_present": (
            (ROOT / "scripts/run_step065_acceptance.py").is_file()
            and (ROOT / "sh_run_step065_acceptance.cmd").is_file()
        ),
        "step066_not_selected": "STEP066_" not in docs_text,
    }

    payload = {
        "schema_version": "okcanvas-step065-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "policy": policy.to_public_dict(),
        "focused_test_output": focused_output.splitlines()[-1] if focused_output else "",
        "historical_test_output": historical_output.splitlines()[-1]
        if historical_output
        else "",
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
