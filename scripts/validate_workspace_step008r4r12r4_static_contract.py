from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.validate_current_document_sot import validate_current_documents
from scripts.validate_workspace_step008r4r12r1_static_contract import (
    _first_party_json_clean,
    _first_party_python_ast_clean,
    _local_secret_files_absent,
    _manifest_matches,
    _run_json,
    _secret_like_literals_absent,
)
from scripts.workspace_inventory import MUTABLE_ACCEPTANCE_EVIDENCE, excluded_workspace_path

STEP = "WORKSPACE_STEP008R4R12R4_STEP096BR1R2_GROUNDED_SESSION_DELEGATED_IDENTITY_HINT_ACTIVATION_CLOSURE"
VERSION = "0.8.4-r12r4"
RUNTIME_STEP = "STEP096BR1R2_GROUNDED_SESSION_DELEGATED_IDENTITY_HINT_ACTIVATION_CLOSURE"
RUNTIME_VERSION = "2.80.2"
PARENT_STEP = "WORKSPACE_STEP008R4R12R3_STEP096BR1R1_MODEL_BEHAVIOR_LIVE_DIAGNOSTIC_CLOSURE"
PARENT_VERSION = "0.8.4-r12r3"
PARENT_SHA = "588cc040b9654150cd1350b37f858ef9f42aefbd24d72da0d21171438acd70ff"
LIVE_EVIDENCE = "docs/evidence/WORKSPACE_STEP008R4R12R4_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE.json"
PARENT_PRODUCT_MANIFEST = ROOT / "reference/parent-file-manifests/okcanvas-agent-runtime-product-python-r12r3.json"
EXPECTED_PRODUCT_DIFF = [
    "okcanvas_agent_runtime/adapters/mcp/organization_interpretation_hints.py",
    "okcanvas_agent_runtime/adapters/openai/generic_gateway.py",
    "okcanvas_agent_runtime/application/assistant_interpretation/models.py",
    "okcanvas_agent_runtime/application/submissions/service.py",
    "okcanvas_agent_runtime/core/baseline.py",
]


def load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def workspace_manifest_exact() -> bool:
    path = ROOT / "WORKSPACE_MANIFEST.json"
    if not path.is_file():
        return False
    manifest = load("WORKSPACE_MANIFEST.json")
    expected = {item["path"]: (item["sha256"], int(item["size"])) for item in manifest.get("files", [])}
    actual: dict[str, tuple[str, int]] = {}
    for file in sorted(ROOT.rglob("*")):
        if file.is_file() and not excluded_workspace_path(file.relative_to(ROOT)):
            data = file.read_bytes()
            actual[file.relative_to(ROOT).as_posix()] = (hashlib.sha256(data).hexdigest(), len(data))
    return (
        manifest.get("step") == STEP
        and manifest.get("version") == VERSION
        and LIVE_EVIDENCE in manifest.get("excluded_mutable_paths", [])
        and manifest.get("file_count") == len(expected) == len(actual)
        and expected == actual
    )


def runtime_product_diff() -> tuple[bool, list[str], int]:
    manifest = json.loads(PARENT_PRODUCT_MANIFEST.read_text(encoding="utf-8"))
    runtime = ROOT / "okcanvas-agent-runtime"
    expected = {item["path"]: (item["sha256"], int(item["size"])) for item in manifest.get("files", [])}
    actual: dict[str, tuple[str, int]] = {}
    for root_name in manifest.get("roots", []):
        for path in sorted((runtime / root_name).rglob("*.py")):
            data = path.read_bytes()
            actual[path.relative_to(runtime).as_posix()] = (hashlib.sha256(data).hexdigest(), len(data))
    changed = sorted(path for path in set(expected) | set(actual) if expected.get(path) != actual.get(path))
    identity = (
        manifest.get("parent_workspace_step") == PARENT_STEP
        and manifest.get("parent_workspace_version") == PARENT_VERSION
        and manifest.get("parent_package_sha256") == PARENT_SHA
        and manifest.get("runtime_step") == "STEP096BR1R1_MODEL_BEHAVIOR_LIVE_DIAGNOSTIC_CLOSURE"
        and manifest.get("runtime_version") == "2.80.1"
    )
    return identity and len(expected) == len(actual) == 379 and changed == EXPECTED_PRODUCT_DIFF, changed, len(actual)


def main() -> int:
    base = load("specs/workspace/current-baseline.json")
    catalog = load("specs/workspace/project-catalog.json")
    marker = load("WORKSPACE_STEP008R4R12R4_PROMOTION_MARKER.json")
    failure = load("docs/evidence/WORKSPACE_STEP008R4R12R3_LIVE_FAILURE_USER_REPORTED_HINT_UNAVAILABLE.json")
    runtime = ROOT / "okcanvas-agent-runtime"
    runtime_static = _run_json(runtime, "scripts/validate_step096br1r2_static_contract.py")
    acceptance_path = Path("/tmp/step096br1r2-r12r4.json")
    proc = subprocess.run(
        [sys.executable, "scripts/run_step096br1r2_acceptance.py", str(acceptance_path)],
        cwd=runtime, text=True, capture_output=True, check=False,
    )
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8")) if proc.returncode == 0 and acceptance_path.is_file() else {"state": "FAILED"}
    launcher = _run_json(runtime, "scripts/validate_acceptance_launcher_registry.py")
    constitution = _run_json(runtime, "scripts/validate_architecture_constitution.py", "--output", "/tmp/r12r4-constitution.json")
    architecture = _run_json(runtime, "scripts/validate_step081_architecture.py")
    architecture_false = sorted(key for key, value in (architecture.get("checks") or {}).items() if value is not True)
    product_ok, changed_product, product_count = runtime_product_diff()
    py_ok, py_count = _first_party_python_ast_clean()
    json_ok, json_count = _first_party_json_clean()
    issues = (ROOT / "docs/issues/ISSUE_REGISTRY.md").read_text(encoding="utf-8")
    submission_src = (runtime / "okcanvas_agent_runtime/application/submissions/service.py").read_text(encoding="utf-8")
    hint_src = (runtime / "okcanvas_agent_runtime/adapters/mcp/organization_interpretation_hints.py").read_text(encoding="utf-8")
    gateway_src = (runtime / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(encoding="utf-8")
    harness_src = (ROOT / "scripts/run_workspace_step008r4r12r4_grounded_structured_delegation_live_acceptance.py").read_text(encoding="utf-8")
    checks = {
        "workspace_identity_exact": base.get("workspace_step") == STEP and base.get("workspace_version") == VERSION and catalog.get("workspace_step") == STEP and catalog.get("workspace_version") == VERSION,
        "parent_r12r3_exact": base.get("parent_workspace_step") == PARENT_STEP and base.get("parent_workspace_version") == PARENT_VERSION and base.get("source_release_sha256") == PARENT_SHA,
        "runtime_identity_exact": base.get("runtime_step") == RUNTIME_STEP and base.get("runtime_version") == RUNTIME_VERSION and any(item.get("project_id") == "agent-runtime" and item.get("baseline") == RUNTIME_STEP and item.get("version") == RUNTIME_VERSION for item in catalog.get("projects", [])),
        "r12r3_user_live_failure_preserved": failure.get("state") == "FAILED" and failure.get("passed_checks") == 12 and failure.get("total_checks") == 14 and failure.get("failure_stage") == "fixture_stable-focus-calendar-cross-domain" and (failure.get("observed") or {}).get("shown_interpretation_hint_state") == "UNAVAILABLE" and (failure.get("observed") or {}).get("all_shown_runs_agent_tool_requested_count") == 0,
        "runtime_corrective_product_diff_exact_five_files": product_ok and product_count == 379 and changed_product == EXPECTED_PRODUCT_DIFF,
        "runtime_step096br1r2_static_11_of_11": runtime_static.get("state") == "PASSED" and runtime_static.get("passed_checks") == 11 and runtime_static.get("total_checks") == 11,
        "runtime_step096br1r2_acceptance_7_of_7": acceptance.get("state") == "PASSED" and acceptance.get("passed_checks") == 7 and acceptance.get("total_checks") == 7,
        "runtime_focused_regression_69_of_69": "69 passed" in str((acceptance.get("focused_pytest") or {}).get("summary", "")),
        "launcher_registry_7_of_7": launcher.get("state") == "PASSED" and launcher.get("passed_checks") == 7 and launcher.get("current_step_token") == "096BR1R2",
        "architecture_constitution_16_of_16": constitution.get("state") == "PASSED" and constitution.get("passed_checks") == 16,
        "current_architecture_except_historical_identity": architecture.get("passed_checks") == 39 and architecture.get("total_checks") == 40 and architecture_false == ["identity_exact"],
        "connectors_examples_unchanged": all([
            _manifest_matches("okcanvas-connectors/groupware-mcp-server", "reference/parent-file-manifests/okcanvas-connectors__groupware-mcp-server.json"),
            _manifest_matches("okcanvas-connector-examples/groupware/groupware-api-fake", "reference/parent-file-manifests/okcanvas-connector-examples__groupware__groupware-api-fake.json"),
            _manifest_matches("okcanvas-connectors/organization-context-mcp-server", "reference/parent-file-manifests/okcanvas-connectors__organization-context-mcp-server.json"),
            _manifest_matches("okcanvas-connector-examples/organization-context/organization-context-api-fake", "reference/parent-file-manifests/okcanvas-connector-examples__organization-context__organization-context-api-fake.json"),
        ]),
        "grounded_identity_decoupled_from_legacy_child_selection": "grounded_identity_required = bool(" in submission_src and "or grounded_identity_required" in submission_src and "Delegated or grounded Session read requires an authenticated service principal" in submission_src,
        "grounded_identity_does_not_prebind_all_mcps": "if mcp_servers:" in submission_src and "hint and lazy child MCPs bind" in submission_src,
        "hint_unavailable_bounded_diagnostics_present": all(token in hint_src for token in ["DELEGATED_IDENTITY_UNAVAILABLE", "ENDPOINT_ROLE_OR_CREDENTIAL_UNAVAILABLE", "MCP_CONNECTION_UNAVAILABLE", "BOTH_TOOL_OR_CONTRACT_UNAVAILABLE"]),
        "hint_diagnostics_persist_safe_only": all(token in gateway_src for token in ['"hint_diagnostic_code"', '"delegated_identity_present"', '"capability_availability"']),
        "r12r4_cleanup_exact_helper_contract": "removed, removal_errors = remove_temp_tree(temp)" in harness_src and "retry_error_types=" not in harness_src,
        "r12r4_live_harness_trio_present": all((ROOT / path).is_file() for path in ["scripts/run_workspace_step008r4r12r4_grounded_structured_delegation_live_acceptance.py", "scripts/run_workspace_step008r4r12r4_grounded_structured_delegation_live_entrypoint.py", "sh_run_workspace_step008r4r12r4_grounded_structured_delegation_live_acceptance.cmd"]),
        "r12r4_live_evidence_mutable": LIVE_EVIDENCE in MUTABLE_ACCEPTANCE_EVIDENCE,
        "issues_077_079_recorded": all(token in issues for token in ["WORKSPACE-ISSUE-077 | FIXED_IN_R12R4_STEP096BR1R2", "WORKSPACE-ISSUE-078 | FIXED_IN_R12R4_STEP096BR1R2", "WORKSPACE-ISSUE-079 | FIXED_IN_R12R4_LIVE_HARNESS"]),
        "root_direct_answer_policy_intentionally_unchanged": base.get("r12r4_grounded_identity_rule") == "AUTHENTICATED_SESSION_ROOT_MARKER_MATERIALIZES_DELEGATED_IDENTITY_BEFORE_LEGACY_CHILD_SELECTION",
        "promotion_live_rerun_pending": marker.get("promotion") == "CANDIDATE_FOCUSED_WINDOWS_LIVE_HINT_ACTIVATION_RERUN_PENDING" and marker.get("step096br1_windows_live") == "RERUN_NOT_RUN",
        "current_document_sot_exact": not validate_current_documents(ROOT),
        "first_party_python_ast_clean": py_ok,
        "first_party_json_clean": json_ok,
        "local_secret_environment_files_absent": _local_secret_files_absent(),
        "secret_like_literals_absent": _secret_like_literals_absent(),
        "workspace_manifest_exact": workspace_manifest_exact(),
    }
    payload = {
        "schema_version": "okcanvas-workspace-step008r4r12r4-static-contract-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": STEP, "version": VERSION, "runtime_step": RUNTIME_STEP, "runtime_version": RUNTIME_VERSION,
        "checks": checks, "passed_checks": sum(v is True for v in checks.values()), "total_checks": len(checks),
        "runtime_product_python_count": product_count, "runtime_product_changed_files": changed_product,
        "first_party_python_count": py_count, "first_party_json_count": json_count,
        "architecture_false_checks": architecture_false,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
