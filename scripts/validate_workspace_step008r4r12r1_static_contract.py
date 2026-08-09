from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_current_document_sot import validate_current_documents
from scripts.workspace_inventory import MUTABLE_ACCEPTANCE_EVIDENCE, excluded_workspace_path, snapshot_files

WORKSPACE_STEP = "WORKSPACE_STEP008R4R12R1_STEP096B_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE_HARNESS"
WORKSPACE_VERSION = "0.8.4-r12r1"
RUNTIME_STEP = "STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION"
RUNTIME_VERSION = "2.80.0"
PARENT_STEP = "WORKSPACE_STEP008R4R12_RUNTIME_STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION"
PARENT_VERSION = "0.8.4-r12"
PARENT_PACKAGE_SHA256 = "4322e7fc7a862efc99af2c95a407aed7040b1bdea1bd817bb59ae7096e38484a"
BR1_EVIDENCE = "docs/evidence/WORKSPACE_STEP008R4R12R1_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE.json"
PRODUCT_PYTHON_MANIFEST = "reference/parent-file-manifests/okcanvas-agent-runtime-product-python-r12.json"


def _load(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _manifest_matches(project_relative: str, manifest_relative: str) -> bool:
    manifest = _load(manifest_relative)
    expected = {str(item["path"]): (str(item["sha256"]), int(item["size"])) for item in manifest.get("files", [])}
    actual = snapshot_files(ROOT / project_relative)
    return manifest.get("file_count") == len(expected) == len(actual) and expected == actual


def _product_python_parent_exact() -> tuple[bool, int]:
    manifest = _load(PRODUCT_PYTHON_MANIFEST)
    runtime = ROOT / "okcanvas-agent-runtime"
    expected = {str(item["path"]): (str(item["sha256"]), int(item["size"])) for item in manifest.get("files", [])}
    actual: dict[str, tuple[str, int]] = {}
    for root_name in manifest.get("roots", []):
        base = runtime / str(root_name)
        for path in sorted(base.rglob("*.py")):
            relative = path.relative_to(runtime).as_posix()
            data = path.read_bytes()
            actual[relative] = (hashlib.sha256(data).hexdigest(), len(data))
    identity = (
        manifest.get("parent_workspace_step") == PARENT_STEP
        and manifest.get("parent_workspace_version") == PARENT_VERSION
        and manifest.get("parent_package_sha256") == PARENT_PACKAGE_SHA256
        and manifest.get("runtime_step") == RUNTIME_STEP
        and manifest.get("runtime_version") == RUNTIME_VERSION
    )
    return identity and manifest.get("file_count") == len(expected) == len(actual) == 379 and expected == actual, len(actual)


def _workspace_manifest_matches() -> bool:
    path = ROOT / "WORKSPACE_MANIFEST.json"
    if not path.is_file():
        return False
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {str(item["path"]): (str(item["sha256"]), int(item["size"])) for item in manifest.get("files", [])}
    actual: dict[str, tuple[str, int]] = {}
    for file in sorted(ROOT.rglob("*")):
        if not file.is_file():
            continue
        relative = file.relative_to(ROOT)
        if excluded_workspace_path(relative):
            continue
        data = file.read_bytes()
        actual[relative.as_posix()] = (hashlib.sha256(data).hexdigest(), len(data))
    return (
        manifest.get("step") == WORKSPACE_STEP
        and manifest.get("version") == WORKSPACE_VERSION
        and BR1_EVIDENCE in manifest.get("excluded_mutable_paths", [])
        and manifest.get("file_count") == len(expected) == len(actual)
        and expected == actual
    )


def _run_json(cwd: Path, script: str, *extra: str) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, script, *extra], cwd=cwd, text=True, capture_output=True, check=False)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"state": "FAILED", "returncode": completed.returncode, "stdout": completed.stdout[-2000:], "stderr": completed.stderr[-2000:]}
    payload["returncode"] = completed.returncode
    return payload


def _first_party_python_ast_clean() -> tuple[bool, int]:
    roots = (
        ROOT / "scripts",
        ROOT / "okcanvas-agent-runtime" / "okcanvas_agent_runtime",
        ROOT / "okcanvas-agent-runtime" / "okcanvas_agent_protocols",
        ROOT / "okcanvas-agent-runtime" / "okcanvas_agent_clients",
        ROOT / "okcanvas-agent-runtime" / "scripts",
        ROOT / "okcanvas-agent-runtime" / "tests",
        ROOT / "okcanvas-connectors" / "groupware-mcp-server",
        ROOT / "okcanvas-connectors" / "organization-context-mcp-server",
    )
    count = 0
    try:
        for base in roots:
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.py")):
                if any(part in {".venv", "__pycache__", "node_modules"} for part in path.parts):
                    continue
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                count += 1
    except (SyntaxError, UnicodeDecodeError):
        return False, count
    return True, count


def _first_party_json_clean() -> tuple[bool, int]:
    roots = (
        ROOT / "specs",
        ROOT / "docs" / "evidence",
        ROOT / "reference" / "parent-file-manifests",
        ROOT / "okcanvas-agent-runtime" / "specs",
        ROOT / "okcanvas-agent-runtime" / "docs" / "evidence",
        ROOT / "okcanvas-connectors" / "groupware-mcp-server",
        ROOT / "okcanvas-connectors" / "organization-context-mcp-server",
        ROOT / "okcanvas-connector-examples" / "groupware" / "groupware-api-fake",
        ROOT / "okcanvas-connector-examples" / "organization-context" / "organization-context-api-fake",
    )
    count = 0
    try:
        for base in roots:
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.json")):
                if any(part in {".venv", "node_modules", "dist", "__pycache__"} for part in path.parts):
                    continue
                json.loads(path.read_text(encoding="utf-8"))
                count += 1
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False, count
    return True, count


def _local_secret_files_absent() -> bool:
    forbidden = {".env", ".env.local", ".env.local.cmd"}
    return not any(
        path.is_file() and path.name in forbidden
        for path in ROOT.rglob("*")
        if not any(part in {".venv", "node_modules", "__pycache__"} for part in path.parts)
    )


def _secret_like_literals_absent() -> bool:
    patterns = (
        re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
        re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if excluded_workspace_path(relative):
            continue
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in patterns):
            return False
    return True


def validate() -> dict[str, Any]:
    baseline = _load("specs/workspace/current-baseline.json")
    catalog = _load("specs/workspace/project-catalog.json")
    runtime_project = next(p for p in catalog["projects"] if p["project_id"] == "agent-runtime")
    marker = _load("WORKSPACE_STEP008R4R12R1_PROMOTION_MARKER.json")
    parent_marker = _load("WORKSPACE_STEP008R4R12_PROMOTION_MARKER.json")
    live_marker = _load("WORKSPACE_STEP008R4R10ER1_PROMOTION_MARKER.json")
    preflight = _load("WORKSPACE_STEP008R4R12R1_LIVE_HARNESS_PREFLIGHT_SUMMARY.json")
    acceptance = _load("okcanvas-agent-runtime/docs/evidence/STEP096B_DETERMINISTIC_ACCEPTANCE.json")
    runtime_root = ROOT / "okcanvas-agent-runtime"
    runtime_static = _run_json(runtime_root, "scripts/validate_step096b_static_contract.py")
    launcher = _run_json(runtime_root, "scripts/validate_acceptance_launcher_registry.py")
    constitution = _run_json(runtime_root, "scripts/validate_architecture_constitution.py", "--output", "/tmp/okcanvas-step096br1-constitution-validation.json")
    architecture = _run_json(runtime_root, "scripts/validate_step081_architecture.py")
    architecture_false = sorted(k for k, v in (architecture.get("checks") or {}).items() if v is not True)
    issue_registry = (ROOT / "docs/issues/ISSUE_REGISTRY.md").read_text(encoding="utf-8")
    memory_audit = (ROOT / "docs/plans/STEP095A_BOUNDED_DURABLE_MEMORY_EXHAUSTIVE_AUDIT.md").read_text(encoding="utf-8")
    runtime_readme = (ROOT / "okcanvas-agent-runtime/README.md").read_text(encoding="utf-8")
    harness = (ROOT / "scripts/run_workspace_step008r4r12r1_grounded_structured_delegation_live_acceptance.py").read_text(encoding="utf-8")
    py_clean, py_count = _first_party_python_ast_clean()
    json_clean, json_count = _first_party_json_clean()
    product_python_exact, product_python_count = _product_python_parent_exact()

    connectors = {
        "groupware_connector": _manifest_matches("okcanvas-connectors/groupware-mcp-server", "reference/parent-file-manifests/okcanvas-connectors__groupware-mcp-server.json"),
        "groupware_example": _manifest_matches("okcanvas-connector-examples/groupware/groupware-api-fake", "reference/parent-file-manifests/okcanvas-connector-examples__groupware__groupware-api-fake.json"),
        "organization_connector": _manifest_matches("okcanvas-connectors/organization-context-mcp-server", "reference/parent-file-manifests/okcanvas-connectors__organization-context-mcp-server.json"),
        "organization_example": _manifest_matches("okcanvas-connector-examples/organization-context/organization-context-api-fake", "reference/parent-file-manifests/okcanvas-connector-examples__organization-context__organization-context-api-fake.json"),
    }
    case_ids = (
        "short-contact-natural-variation",
        "short-phone-natural-variation",
        "hanbit-account-manager-grounded-ambiguity",
        "stable-focus-calendar-cross-domain",
        "code-overroute-no-specialist",
        "web-overroute-no-specialist",
        "write-shaped-calendar-delete-no-read-child",
        "greeting-no-specialist",
    )

    checks = {
        "workspace_identity_exact": baseline.get("workspace_step") == WORKSPACE_STEP and baseline.get("workspace_version") == WORKSPACE_VERSION,
        "runtime_identity_exact": baseline.get("runtime_step") == RUNTIME_STEP and baseline.get("runtime_version") == RUNTIME_VERSION,
        "parent_r12_exact": baseline.get("parent_workspace_step") == PARENT_STEP and baseline.get("parent_workspace_version") == PARENT_VERSION and baseline.get("source_release_sha256") == PARENT_PACKAGE_SHA256,
        "candidate_live_test_pending_not_promoted": baseline.get("promotion") == "CANDIDATE_FOCUSED_WINDOWS_LIVE_TEST_PENDING" and marker.get("promotion") == "CANDIDATE_FOCUSED_WINDOWS_LIVE_TEST_PENDING" and marker.get("step096br1_windows_live") == "NOT_RUN",
        "r12_parent_candidate_retained": parent_marker.get("workspace_step") == PARENT_STEP and parent_marker.get("runtime_step") == RUNTIME_STEP,
        "r10er1_last_live_promoted_retained": live_marker.get("promotion") == "CURRENT_PROMOTED_BASELINE" and live_marker.get("runtime_step") == "STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE",
        "project_catalog_matches_current": catalog.get("workspace_step") == WORKSPACE_STEP and catalog.get("workspace_version") == WORKSPACE_VERSION and runtime_project.get("baseline") == RUNTIME_STEP and runtime_project.get("version") == RUNTIME_VERSION,
        "runtime_product_source_declared_unchanged": baseline.get("runtime_product_source_changed") is False and marker.get("runtime_product_source_changed") is False,
        "runtime_product_python_parent_r12_exact_379": product_python_exact and product_python_count == 379,
        "runtime_step096b_static_20_of_20": runtime_static.get("state") == "PASSED" and runtime_static.get("passed_checks") == 20 and runtime_static.get("total_checks") == 20,
        "runtime_step096b_acceptance_6_of_6": acceptance.get("state") == "PASSED" and acceptance.get("passed_checks") == 6 and acceptance.get("total_checks") == 6,
        "runtime_focused_regression_63_of_63": "63 passed" in str((acceptance.get("focused_pytest") or {}).get("summary", "")),
        "runtime_live_still_not_claimed": acceptance.get("windows_live") == "NOT_RUN" and baseline.get("grounded_llm_structured_delegation_windows_live") == "NOT_RUN",
        "runtime_launcher_registry_7_of_7": launcher.get("state") == "PASSED" and launcher.get("passed_checks") == 7 and launcher.get("current_step_token") == "096B",
        "architecture_constitution_16_of_16": constitution.get("state") == "PASSED" and constitution.get("passed_checks") == 16,
        "current_architecture_exact_except_historical_identity": architecture.get("passed_checks") == 39 and architecture.get("total_checks") == 40 and architecture_false == ["identity_exact"],
        "current_physical_manifest_and_runtime_info_exact": (architecture.get("checks") or {}).get("physical_module_inventory_current") is True and (architecture.get("checks") or {}).get("runtime_info_feature_groups_exact") is True,
        "current_document_sot_exact": not validate_current_documents(ROOT),
        "runtime_readme_successor_narrative_exact": "STEP096B/2.80.0 is the current Runtime Product candidate" in runtime_readme and "STEP096BR1 focused Windows/OpenAI Live: NOT RUN" in runtime_readme and "STEP096A/2.79.0 is the current local-deterministic candidate" not in runtime_readme and "STEP096B will" not in runtime_readme,
        "br1_harness_entrypoint_launcher_present": all((ROOT / path).is_file() for path in ("scripts/run_workspace_step008r4r12r1_grounded_structured_delegation_live_acceptance.py", "scripts/run_workspace_step008r4r12r1_grounded_structured_delegation_live_entrypoint.py", "sh_run_workspace_step008r4r12r1_grounded_structured_delegation_live_acceptance.cmd")),
        "br1_harness_exact_eight_scenarios_and_ten_turn_contract": all(case_id in harness for case_id in case_ids) and "len(runs) == total_turn_count == 10" in harness and "ten_runtime_turns_created_for_eight_scenarios_plus_two_focus_fixtures" in harness,
        "br1_harness_lifecycle_evidence_exact": all(token in harness for token in ("agent.tool.requested", "agent.tool.admitted", "agent.tool.started", "tool.started", "agent.tool.output.normalized", "selected_child_mcp_connected")),
        "br1_harness_hint_execution_boundary_exact": all(token in harness for token in ("/api/v1/context/search", "/api/v1/glossary/search", "/api/v1/context/resolve", "context_ref", "employee-0017")),
        "br1_evidence_registered_mutable": BR1_EVIDENCE in MUTABLE_ACCEPTANCE_EVIDENCE,
        "br1_preflight_fail_closed_no_live_claim": preflight.get("state") == "EXPECTED_FAILED_NO_LOCAL_LIVE_ENVIRONMENT" and preflight.get("identity_and_harness_checks") == "6/6 PASSED" and preflight.get("openai_live_run_executed") is False and preflight.get("secret_values_persisted") is False,
        "connector_and_example_products_unchanged": all(connectors.values()),
        "workspace_issue_registry_060_through_072": all(f"WORKSPACE-ISSUE-{n:03d} |" in issue_registry for n in range(60, 73)) and all(any((ROOT / "docs/issues").glob(f"WORKSPACE-ISSUE-{n:03d}-*.md")) for n in range(60, 73)),
        "step095a_memory_audit_retained_separate": all(token in memory_audit for token in ("READ_ONLY_AUDIT_PREPARED_NO_PRODUCT_MEMORY_IMPLEMENTATION", "no Runtime Product source modification", "no new database table or migration", "no memory API route", "no memory-driven routing")) and baseline.get("step095a_memory_audit") == "SEPARATE_BACKLOG_NOT_IMPLEMENTED",
        "first_party_python_ast_clean": py_clean,
        "first_party_json_parse_clean": json_clean,
        "local_secret_environment_files_absent": _local_secret_files_absent(),
        "secret_like_literals_absent": _secret_like_literals_absent(),
        "workspace_manifest_exact_and_live_evidence_excluded": _workspace_manifest_matches(),
    }
    return {
        "schema_version": "okcanvas-workspace-step008r4r12r1-static-contract-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": WORKSPACE_STEP,
        "version": WORKSPACE_VERSION,
        "runtime_step": RUNTIME_STEP,
        "runtime_version": RUNTIME_VERSION,
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "details": {
            "runtime_static": {"state": runtime_static.get("state"), "passed": runtime_static.get("passed_checks"), "total": runtime_static.get("total_checks")},
            "launcher_registry": {"state": launcher.get("state"), "passed": launcher.get("passed_checks"), "total": launcher.get("total_checks")},
            "architecture_constitution": {"state": constitution.get("state"), "passed": constitution.get("passed_checks"), "total": constitution.get("total_checks")},
            "current_architecture": {"passed": architecture.get("passed_checks"), "total": architecture.get("total_checks"), "expected_historical_identity_failure": architecture_false},
            "runtime_product_python_count": product_python_count,
            "first_party_python_ast_count": py_count,
            "first_party_json_count": json_count,
            "connector_manifest_exact": connectors,
        },
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2, sort_keys=True))
