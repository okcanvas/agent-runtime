from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_current_document_sot import validate_current_documents
from scripts.workspace_inventory import excluded_workspace_path, snapshot_files

WORKSPACE_STEP = "WORKSPACE_STEP008R4R11_RUNTIME_STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION"
WORKSPACE_VERSION = "0.8.4-r11"
RUNTIME_STEP = "STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION"
RUNTIME_VERSION = "2.79.0"
PARENT_STEP = "WORKSPACE_STEP008R4R10ER1_CROSS_DOMAIN_LIVE_ACCEPTANCE_PROMOTION_CLOSURE"
PARENT_VERSION = "0.8.4-r10er1"
PARENT_PACKAGE_SHA256 = "b840758a000c79e076d361c27dd39c4f57884e1c7cbd8011107f7a9395e28270"


def _load(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _manifest_matches(project_relative: str, manifest_relative: str) -> bool:
    manifest = _load(manifest_relative)
    expected = {
        str(item["path"]): (str(item["sha256"]), int(item["size"]))
        for item in manifest.get("files", [])
    }
    actual = snapshot_files(ROOT / project_relative)
    return manifest.get("file_count") == len(expected) == len(actual) and expected == actual


def _workspace_manifest_matches() -> bool:
    path = ROOT / "WORKSPACE_MANIFEST.json"
    if not path.is_file():
        return False
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        str(item["path"]): (str(item["sha256"]), int(item["size"]))
        for item in manifest.get("files", [])
    }
    actual: dict[str, tuple[str, int]] = {}
    import hashlib
    for file in sorted(ROOT.rglob("*")):
        if not file.is_file():
            continue
        relative = file.relative_to(ROOT)
        if excluded_workspace_path(relative):
            continue
        actual[relative.as_posix()] = (hashlib.sha256(file.read_bytes()).hexdigest(), file.stat().st_size)
    return (
        manifest.get("step") == WORKSPACE_STEP
        and manifest.get("version") == WORKSPACE_VERSION
        and manifest.get("file_count") == len(expected) == len(actual)
        and expected == actual
    )


def _run_json(cwd: Path, script: str, *extra: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, script, *extra], cwd=cwd, text=True, capture_output=True, check=False
    )
    if completed.returncode != 0:
        return {"state": "FAILED", "returncode": completed.returncode, "stderr": completed.stderr[-2000:]}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"state": "FAILED", "returncode": completed.returncode, "stdout": completed.stdout[-2000:]}


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
    import re
    openai = re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b")
    aws = re.compile(rb"\bAKIA[A-Z0-9]{16}\b")
    private = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if excluded_workspace_path(relative):
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if openai.search(data) or aws.search(data) or private.search(data):
            return False
    return True


def validate() -> dict[str, Any]:
    baseline = _load("specs/workspace/current-baseline.json")
    catalog = _load("specs/workspace/project-catalog.json")
    runtime_project = next(p for p in catalog["projects"] if p["project_id"] == "agent-runtime")
    marker = _load("WORKSPACE_STEP008R4R11_PROMOTION_MARKER.json")
    acceptance = _load("okcanvas-agent-runtime/docs/evidence/STEP096A_DETERMINISTIC_ACCEPTANCE.json")
    parent_marker = _load("WORKSPACE_STEP008R4R10ER1_PROMOTION_MARKER.json")
    issue_registry = (ROOT / "docs/issues/ISSUE_REGISTRY.md").read_text(encoding="utf-8")
    memory_audit = (ROOT / "docs/plans/STEP095A_BOUNDED_DURABLE_MEMORY_EXHAUSTIVE_AUDIT.md").read_text(encoding="utf-8")
    runtime_root = ROOT / "okcanvas-agent-runtime"
    runtime_static = _run_json(runtime_root, "scripts/validate_step096a_static_contract.py")
    launcher = _run_json(runtime_root, "scripts/validate_acceptance_launcher_registry.py")
    constitution = _run_json(runtime_root, "scripts/validate_architecture_constitution.py", "--output", "/tmp/okcanvas-step096a-constitution-validation.json")
    architecture = _run_json(runtime_root, "scripts/validate_step081_architecture.py")
    py_clean, py_count = _first_party_python_ast_clean()
    json_clean, json_count = _first_party_json_clean()

    connector_manifests = {
        "groupware_connector": _manifest_matches(
            "okcanvas-connectors/groupware-mcp-server",
            "reference/parent-file-manifests/okcanvas-connectors__groupware-mcp-server.json",
        ),
        "groupware_example": _manifest_matches(
            "okcanvas-connector-examples/groupware/groupware-api-fake",
            "reference/parent-file-manifests/okcanvas-connector-examples__groupware__groupware-api-fake.json",
        ),
        "organization_context_connector": _manifest_matches(
            "okcanvas-connectors/organization-context-mcp-server",
            "reference/parent-file-manifests/okcanvas-connectors__organization-context-mcp-server.json",
        ),
        "organization_context_example": _manifest_matches(
            "okcanvas-connector-examples/organization-context/organization-context-api-fake",
            "reference/parent-file-manifests/okcanvas-connector-examples__organization-context__organization-context-api-fake.json",
        ),
    }

    checks = {
        "workspace_identity_exact": baseline.get("workspace_step") == WORKSPACE_STEP and baseline.get("workspace_version") == WORKSPACE_VERSION,
        "runtime_identity_exact": baseline.get("runtime_step") == RUNTIME_STEP and baseline.get("runtime_version") == RUNTIME_VERSION,
        "parent_release_exact": baseline.get("parent_workspace_step") == PARENT_STEP and baseline.get("parent_workspace_version") == PARENT_VERSION and baseline.get("source_release_sha256") == PARENT_PACKAGE_SHA256,
        "candidate_not_live_promoted": baseline.get("promotion") == "CANDIDATE_LOCAL_DETERMINISTIC_ACCEPTED_LIVE_NOT_RUN" and marker.get("promotion") == "CANDIDATE_LOCAL_DETERMINISTIC_ACCEPTED_LIVE_NOT_RUN" and baseline.get("grounded_llm_interpretation_windows_live") == "NOT_RUN",
        "parent_live_promotion_retained_historical": parent_marker.get("promotion") == "CURRENT_PROMOTED_BASELINE" and parent_marker.get("runtime_step") == "STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE",
        "catalog_matches_current": catalog.get("workspace_step") == WORKSPACE_STEP and catalog.get("workspace_version") == WORKSPACE_VERSION and runtime_project.get("baseline") == RUNTIME_STEP and runtime_project.get("version") == RUNTIME_VERSION,
        "runtime_product_source_declared_changed": baseline.get("runtime_product_source_changed") is True and marker.get("runtime_product_source_changed") is True,
        "runtime_step096a_static_19_of_19": runtime_static.get("state") == "PASSED" and runtime_static.get("passed_checks") == 19 and runtime_static.get("total_checks") == 19,
        "runtime_step096a_acceptance_6_of_6": acceptance.get("state") == "PASSED" and acceptance.get("passed_checks") == 6 and acceptance.get("total_checks") == 6,
        "runtime_focused_regression_48_of_48": "48 passed" in str((acceptance.get("focused_pytest") or {}).get("summary", "")),
        "runtime_acceptance_live_and_broad_claims_bounded": acceptance.get("windows_live") == "NOT_RUN" and acceptance.get("broad_regression") == "NOT_CLAIMED_HISTORICAL_STALE_TESTS_RECORDED_SEPARATELY",
        "launcher_registry_7_of_7": launcher.get("state") == "PASSED" and launcher.get("passed_checks") == 7 and launcher.get("current_step_token") == "096A",
        "architecture_constitution_16_of_16": constitution.get("state") == "PASSED" and constitution.get("passed_checks") == 16,
        "current_architecture_40_of_40": architecture.get("state") == "PASSED" and architecture.get("passed_checks") == 40,
        "current_document_sot_exact": not validate_current_documents(ROOT),
        "runtime_parent_manifest_exact": _manifest_matches("okcanvas-agent-runtime", "reference/parent-file-manifests/okcanvas-agent-runtime.json"),
        "groupware_connector_parent_manifest_exact": connector_manifests["groupware_connector"],
        "groupware_example_parent_manifest_exact": connector_manifests["groupware_example"],
        "organization_context_connector_parent_manifest_exact": connector_manifests["organization_context_connector"],
        "organization_context_example_parent_manifest_exact": connector_manifests["organization_context_example"],
        "connector_product_source_unchanged": all(connector_manifests.values()),
        "workspace_issue_registry_060_through_067": all(f"WORKSPACE-ISSUE-{n:03d} |" in issue_registry for n in range(60, 68)) and all(any((ROOT / "docs/issues").glob(f"WORKSPACE-ISSUE-{n:03d}-*.md")) for n in range(60, 68)),
        "step095a_memory_audit_retained_separate": all(token in memory_audit for token in ("READ_ONLY_AUDIT_PREPARED_NO_PRODUCT_MEMORY_IMPLEMENTATION", "no Runtime Product source modification", "no new database table or migration", "no memory API route", "no memory-driven routing")) and baseline.get("step095a_memory_audit") == "SEPARATE_BACKLOG_NOT_IMPLEMENTED",
        "hint_authority_explicitly_non_authoritative": baseline.get("grounded_llm_interpretation_hint_authority") == "NON_AUTHORITATIVE_TURN_LOCAL_MODEL_CONTEXT" and baseline.get("grounded_llm_interpretation_route_authority") == "LEGACY_V2_REMAINS_AUTHORITATIVE",
        "first_party_python_ast_clean": py_clean,
        "first_party_json_parse_clean": json_clean,
        "local_secret_environment_files_absent": _local_secret_files_absent(),
        "secret_like_literals_absent": _secret_like_literals_absent(),
        "workspace_manifest_exact": _workspace_manifest_matches(),
    }
    return {
        "schema_version": "okcanvas-workspace-step008r4r11-static-contract-v1",
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
            "current_architecture": {"state": architecture.get("state"), "passed": architecture.get("passed_checks"), "total": architecture.get("total_checks")},
            "first_party_python_ast_count": py_count,
            "first_party_json_count": json_count,
            "runtime_parent_manifest_file_count": _load("reference/parent-file-manifests/okcanvas-agent-runtime.json").get("file_count"),
            "connector_manifest_file_counts": {
                "groupware_connector": _load("reference/parent-file-manifests/okcanvas-connectors__groupware-mcp-server.json").get("file_count"),
                "groupware_example": _load("reference/parent-file-manifests/okcanvas-connector-examples__groupware__groupware-api-fake.json").get("file_count"),
                "organization_context_connector": _load("reference/parent-file-manifests/okcanvas-connectors__organization-context-mcp-server.json").get("file_count"),
                "organization_context_example": _load("reference/parent-file-manifests/okcanvas-connector-examples__organization-context__organization-context-api-fake.json").get("file_count"),
            },
        },
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2, sort_keys=True))
