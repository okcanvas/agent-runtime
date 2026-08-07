from __future__ import annotations

import argparse
import json
import sys
import tempfile
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

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP063_ACCEPTANCE.json"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _run_historical_acceptance(step: str, output: Path) -> tuple[bool, dict[str, Any], str]:
    ok, console = run_command(
        [sys.executable, f"scripts/run_step{step}_acceptance.py", "--output", str(output)], ROOT
    )
    payload = _load_json(output) if output.is_file() else {}
    return ok, payload, console


def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
    from okcanvas_agent_runtime.domain.sessions import SQLiteSessionPolicyCatalog, SessionHistoryKey

    info = RuntimeInfo()
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    predecessor = _load_json(ROOT / "docs/evidence/STEP062C_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    policy_json = _load_json(ROOT / "specs/runtime/sqlite-session-policy.json")
    encryption_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/encryption.py")).read_text(
        encoding="utf-8"
    )
    session_service_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/service.py")).read_text(
        encoding="utf-8"
    )
    control_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/app.py")).read_text(
        encoding="utf-8"
    )
    windows_source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    runtime_binding_source = (
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")
    ).read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="okcanvas-step063-") as temp_dir:
        temp = Path(temp_dir)
        historical: dict[str, dict[str, Any]] = {}
        historical_ok = True
        historical_console_tails: dict[str, str] = {}
        for step in ("043", "046", "047", "048", "049", "050"):
            ok, payload, console = _run_historical_acceptance(step, temp / f"step{step}.json")
            historical[step] = payload
            historical_ok = historical_ok and ok and payload.get("state") == "PASSED"
            historical_console_tails[step] = console.splitlines()[-1] if console else ""

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step063_strict_encrypted_sqlite_session_history.py",
            "tests/test_sqlite_session_runtime.py",
            "tests/test_sqlite_session_approval_composition.py",
            "tests/test_windows_entrypoint.py",
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
            "scripts/run_step063_acceptance.py",
            "scripts/run_step043_acceptance.py",
            "scripts/run_step046_acceptance.py",
            "scripts/run_step047_acceptance.py",
            "scripts/run_step048_acceptance.py",
            "scripts/run_step049_acceptance.py",
            "scripts/run_step050_acceptance.py",
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
    references = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(references) == 4 and all(item.verified for item in references)

    required_docs = [
        ROOT / "docs/plans/STEP063_STRICT_ENCRYPTED_SQLITE_SESSION_HISTORY_V1.md",
        ROOT / "docs/reference/STEP063_STRICT_ENCRYPTED_SQLITE_SESSION_HISTORY_V1_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP062C_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    ]
    baseline_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    docs_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in required_docs)

    key_hex = bytes(range(32)).hex()
    key_b64 = __import__("base64").urlsafe_b64encode(bytes(range(32))).decode("ascii")
    key_formats_exact = SessionHistoryKey.from_text(key_hex).key_id == SessionHistoryKey.from_text(
        key_b64
    ).key_id

    checks = {
        "baseline_version_and_step_exact": (
            info.version == "2.43.1"
            and info.step == "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"
            and 'PROJECT_VERSION = "2.43.1"' in baseline_source
            and 'CURRENT_STEP = "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"'
            in baseline_source
        ),
        "step062c_windows_live_closure_exact": (
            predecessor.get("state") == "PASSED"
            and predecessor.get("passed_checks") == 26
            and predecessor.get("total_checks") == 26
            and predecessor.get("corrected_step062", {}).get("passed_checks") == 29
            and predecessor.get("supersedes_prior_failed_step062c_run") is True
        ),
        "predecessor_runtime_flags_closed": (
            info.bounded_multi_agent_orchestration_windows_live_accepted is True
            and info.windows_node_acceptance_windows_live_accepted is True
            and info.windows_typescript_direct_compiler_windows_live_accepted is True
            and info.node_cli_committed_dist_release_integrity_windows_live_accepted is True
        ),
        "session_policy_identity_and_sha_exact": (
            policy_json.get("schema_version") == "okcanvas-sqlite-session-policy-v2"
            and policy.policy_id == "local-strict-encrypted-sqlite-session-v1"
            and policy.version == "2.0.0"
            and len(policy.policy_sha256) == 64
            and binding.session_policy == policy.to_binding_dict()
        ),
        "session_policy_encryption_bounds_exact": (
            policy.encryption_enabled is True
            and policy.encryption_mode == "STRICT_AES_256_GCM_HKDF_SHA256_V1"
            and policy.encryption_envelope_version == 1
            and policy.key_derivation == "PER_SESSION_HKDF_SHA256_V1"
            and policy.legacy_plaintext_mode == "REJECT"
            and policy.ttl_seconds is None
            and policy.compaction_enabled is False
        ),
        "step063_runtime_flags_exact": (
            info.sqlite_session_history_encrypted is True
            and info.sqlite_session_history_key_separation_required is True
            and info.sqlite_session_legacy_plaintext_rejected is True
            and info.sqlite_session_history_ttl_enabled is False
            and info.sqlite_session_compaction_enabled is False
            and info.strict_encrypted_sqlite_session_history_implemented is True
            and info.strict_encrypted_sqlite_session_history_deterministic_accepted is True
            and info.strict_encrypted_sqlite_session_history_windows_live_accepted is False
        ),
        "external_key_formats_exact": key_formats_exact,
        "aes_256_gcm_hkdf_source_present": (
            "AESGCM" in encryption_source
            and "HKDF" in encryption_source
            and "hashes.SHA256" in encryption_source
            and "length=32" in encryption_source
        ),
        "exact_authenticated_envelope_present": (
            '__okcanvas_session_encrypted__' in encryption_source
            and '"nonce_b64"' in encryption_source
            and '"ciphertext_b64"' in encryption_source
            and '"okcanvas-session-history-aad-v1"' in encryption_source
            and '"session_id": self.session_id' in encryption_source
            and '"key_id": self.key.key_id' in encryption_source
        ),
        "plaintext_and_corruption_fail_closed_source": (
            "contains plaintext or an unsupported encryption envelope" in encryption_source
            and "ciphertext integrity validation failed" in encryption_source
            and "key ID does not match" in encryption_source
            and "return [self._decrypt(item) for item in encrypted_items]" in encryption_source
        ),
        "catalog_key_id_and_migration_present": (
            "history_encryption_key_id TEXT" in session_service_source
            and "ALTER TABLE product_session ADD COLUMN history_encryption_key_id TEXT"
            in session_service_source
            and "must be cleared and recreated" in session_service_source
        ),
        "turn_lifecycle_key_fencing_present": all(
            marker in session_service_source
            for marker in (
                "def validate_binding",
                "def acquire_turn",
                "def release_turn",
                "def assert_active_turn",
                "def update_active_item_count",
                "self._validate_record_key(record)",
            )
        ),
        "clear_without_decrypt_path_present": (
            "session = self.raw_sdk_session(session_id)" in session_service_source
            and "await session.clear_session()" in session_service_source
        ),
        "protected_payload_key_reuse_rejected": (
            "must be distinct from the protected payload key" in control_source
            and "hmac.compare_digest" in control_source
            and "OKCANVAS_SESSION_HISTORY_KEY" in windows_source
        ),
        "control_api_environment_key_wired": (
            "session_history_key=os.environ.get(\"OKCANVAS_SESSION_HISTORY_KEY\")" in control_source
            and "history_key=resolved_session_history_key" in control_source
        ),
        "runtime_binding_binds_encryption_implementation": (
            binding.session_runtime_sha256 is not None
            and len(binding.session_runtime_sha256) == 64
            and '"okcanvas_agent_runtime.adapters.storage.session_history"' in runtime_binding_source
        ),
        "public_contract_exposes_only_key_id": (
            "history_encryption_key_id" in (
                legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/contracts.py")
            ).read_text(encoding="utf-8")
            and "OKCANVAS_SESSION_HISTORY_KEY" not in (
                legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/contracts.py")
            ).read_text(encoding="utf-8")
        ),
        "historical_sqlite_session_continuity_pass": (
            historical.get("043", {}).get("state") == "PASSED"
        ),
        "historical_session_approval_pass": historical.get("046", {}).get("state") == "PASSED",
        "historical_session_handoff_pass": historical.get("047", {}).get("state") == "PASSED",
        "historical_session_guardrail_pass": historical.get("048", {}).get("state") == "PASSED",
        "historical_session_agent_tool_pass": historical.get("049", {}).get("state") == "PASSED",
        "historical_session_mcp_pass": historical.get("050", {}).get("state") == "PASSED",
        "all_historical_session_compositions_pass": historical_ok,
        "focused_strict_encryption_tests_pass": focused_ok and "53 passed" in focused_output,
        "python_compileall_pass": compile_ok,
        "committed_node_release_integrity_pass": release_ok and "VERIFIED" in release_output,
        "node_tests_pass": node_ok and "# pass 14" in node_output,
        "no_direct_reference_imports": no_reference_imports_ok,
        "references_unchanged": references_ok,
        "step063_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launcher_present": (
            (ROOT / "sh_run_step063_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step063_acceptance.py").is_file()
        ),
        "step064_not_selected": "STEP064_" not in docs_text,
    }

    payload = {
        "schema_version": "okcanvas-step063-acceptance-v1",
        "step": "STEP063_STRICT_ENCRYPTED_SQLITE_SESSION_HISTORY_V1",
        "version": "2.43.1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "policy": {
            "policy_id": policy.policy_id,
            "policy_sha256": policy.policy_sha256,
            "encryption_mode": policy.encryption_mode,
            "envelope_version": policy.encryption_envelope_version,
            "key_derivation": policy.key_derivation,
            "legacy_plaintext_mode": policy.legacy_plaintext_mode,
            "ttl_seconds": policy.ttl_seconds,
            "compaction_enabled": policy.compaction_enabled,
        },
        "historical_session_states": {
            step: historical.get(step, {}).get("state") for step in sorted(historical)
        },
        "focused_test_output": focused_output.splitlines()[-1] if focused_output else "",
        "python_compile_output": compile_output.splitlines()[-1] if compile_output else "",
        "node_release_output": release_output,
        "node_test_output_tail": node_output.splitlines()[-1] if node_output else "",
        "reference_import_output_tail": no_reference_imports_output.splitlines()[-1]
        if no_reference_imports_output
        else "",
        "reference_count": len(references),
        "historical_console_tails": historical_console_tails,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
