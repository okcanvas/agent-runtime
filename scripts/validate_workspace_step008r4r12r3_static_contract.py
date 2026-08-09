from __future__ import annotations

import ast
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

STEP = "WORKSPACE_STEP008R4R12R3_STEP096BR1R1_MODEL_BEHAVIOR_LIVE_DIAGNOSTIC_CLOSURE"
VERSION = "0.8.4-r12r3"
RUNTIME_STEP = "STEP096BR1R1_MODEL_BEHAVIOR_LIVE_DIAGNOSTIC_CLOSURE"
RUNTIME_VERSION = "2.80.1"
PARENT_STEP = "WORKSPACE_STEP008R4R12R2_STEP096B_LIVE_HARNESS_EVIDENCE_REDACTION_SERIALIZATION_CLOSURE"
PARENT_VERSION = "0.8.4-r12r2"
PARENT_SHA = "fb290e8e497f4b857ff5c74ff81d0553390b92b3e0c018f73dad09a34ce88ef7"
LIVE_EVIDENCE = "docs/evidence/WORKSPACE_STEP008R4R12R3_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE.json"
PARENT_PRODUCT_MANIFEST = ROOT / "reference/parent-file-manifests/okcanvas-agent-runtime-product-python-r12r2.json"


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
        and manifest.get("runtime_step") == "STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION"
        and manifest.get("runtime_version") == "2.80.0"
    )
    return (
        identity
        and len(expected) == len(actual) == 379
        and changed == [
            "okcanvas_agent_runtime/adapters/openai/generic_gateway.py",
            "okcanvas_agent_runtime/core/baseline.py",
        ],
        changed,
        len(actual),
    )


def main() -> int:
    base = load("specs/workspace/current-baseline.json")
    catalog = load("specs/workspace/project-catalog.json")
    marker = load("WORKSPACE_STEP008R4R12R3_PROMOTION_MARKER.json")
    failure = load("docs/evidence/WORKSPACE_STEP008R4R12R2_LIVE_FAILURE_USER_REPORTED_MODEL_BEHAVIOR.json")
    runtime = ROOT / "okcanvas-agent-runtime"
    runtime_static = _run_json(runtime, "scripts/validate_step096br1r1_static_contract.py")
    acceptance_path = Path("/tmp/step096br1r1-r12r3.json")
    proc = subprocess.run(
        [sys.executable, "scripts/run_step096br1r1_acceptance.py", str(acceptance_path)],
        cwd=runtime,
        text=True,
        capture_output=True,
        check=False,
    )
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8")) if proc.returncode == 0 and acceptance_path.is_file() else {"state": "FAILED"}
    launcher = _run_json(runtime, "scripts/validate_acceptance_launcher_registry.py")
    constitution = _run_json(runtime, "scripts/validate_architecture_constitution.py", "--output", "/tmp/r12r3-constitution.json")
    architecture = _run_json(runtime, "scripts/validate_step081_architecture.py")
    architecture_false = sorted(key for key, value in (architecture.get("checks") or {}).items() if value is not True)
    product_ok, changed_product, product_count = runtime_product_diff()
    py_ok, py_count = _first_party_python_ast_clean()
    json_ok, json_count = _first_party_json_clean()
    issues = (ROOT / "docs/issues/ISSUE_REGISTRY.md").read_text(encoding="utf-8")
    checks = {
        "workspace_identity_exact": (
            base.get("workspace_step") == STEP
            and base.get("workspace_version") == VERSION
            and catalog.get("workspace_step") == STEP
            and catalog.get("workspace_version") == VERSION
        ),
        "parent_r12r2_exact": (
            base.get("parent_workspace_step") == PARENT_STEP
            and base.get("parent_workspace_version") == PARENT_VERSION
            and base.get("source_release_sha256") == PARENT_SHA
        ),
        "runtime_identity_exact": (
            base.get("runtime_step") == RUNTIME_STEP
            and base.get("runtime_version") == RUNTIME_VERSION
            and any(
                item.get("project_id") == "agent-runtime"
                and item.get("baseline") == RUNTIME_STEP
                and item.get("version") == RUNTIME_VERSION
                for item in catalog.get("projects", [])
            )
        ),
        "r12r2_live_failure_preserved": (
            failure.get("state") == "FAILED"
            and failure.get("passed_checks") == 12
            and failure.get("total_checks") == 14
            and failure.get("failure_stage") == "case_short-contact-natural-variation"
            and (failure.get("first_run") or {}).get("detail_type") == "ModelBehaviorError"
            and (failure.get("first_run") or {}).get("agent_tool_requested_count") == 0
        ),
        "runtime_diagnostic_product_diff_exact_two_files": product_ok and product_count == 379,
        "runtime_step096br1r1_static": runtime_static.get("state") == "PASSED" and runtime_static.get("passed_checks") == 8,
        "runtime_step096br1r1_acceptance_6_of_6": acceptance.get("state") == "PASSED" and acceptance.get("passed_checks") == 6 and acceptance.get("total_checks") == 6,
        "runtime_focused_regression_66_of_66": "66 passed" in str((acceptance.get("focused_pytest") or {}).get("summary", "")),
        "launcher_registry_7_of_7": launcher.get("state") == "PASSED" and launcher.get("passed_checks") == 7,
        "architecture_constitution_16_of_16": constitution.get("state") == "PASSED" and constitution.get("passed_checks") == 16,
        "current_architecture_except_historical_identity": architecture.get("passed_checks") == 39 and architecture.get("total_checks") == 40 and architecture_false == ["identity_exact"],
        "connectors_examples_unchanged": all([
            _manifest_matches("okcanvas-connectors/groupware-mcp-server", "reference/parent-file-manifests/okcanvas-connectors__groupware-mcp-server.json"),
            _manifest_matches("okcanvas-connector-examples/groupware/groupware-api-fake", "reference/parent-file-manifests/okcanvas-connector-examples__groupware__groupware-api-fake.json"),
            _manifest_matches("okcanvas-connectors/organization-context-mcp-server", "reference/parent-file-manifests/okcanvas-connectors__organization-context-mcp-server.json"),
            _manifest_matches("okcanvas-connector-examples/organization-context/organization-context-api-fake", "reference/parent-file-manifests/okcanvas-connector-examples__organization-context__organization-context-api-fake.json"),
        ]),
        "r12r3_live_harness_trio_present": all((ROOT / path).is_file() for path in [
            "scripts/run_workspace_step008r4r12r3_grounded_structured_delegation_live_acceptance.py",
            "scripts/run_workspace_step008r4r12r3_grounded_structured_delegation_live_entrypoint.py",
            "sh_run_workspace_step008r4r12r3_grounded_structured_delegation_live_acceptance.cmd",
        ]),
        "r12r3_live_evidence_mutable": LIVE_EVIDENCE in MUTABLE_ACCEPTANCE_EVIDENCE,
        "issues_074_076_recorded": (
            "WORKSPACE-ISSUE-074 | RECORDED_ROOT_CAUSE_NOT_YET_CLASSIFIED_R12R3_DIAGNOSTIC_READY" in issues
            and "WORKSPACE-ISSUE-075 | FIXED_IN_R12R3_STEP096BR1R1" in issues
            and "WORKSPACE-ISSUE-076 | FIXED_IN_R12R3_RELEASE_VALIDATION" in issues
        ),
        "promotion_diagnostic_rerun_pending": marker.get("promotion") == "CANDIDATE_FOCUSED_WINDOWS_LIVE_DIAGNOSTIC_RERUN_PENDING" and marker.get("step096br1_windows_live") == "RERUN_NOT_RUN",
        "current_document_sot_exact": not validate_current_documents(ROOT),
        "first_party_python_ast_clean": py_ok,
        "first_party_json_clean": json_ok,
        "local_secret_environment_files_absent": _local_secret_files_absent(),
        "secret_like_literals_absent": _secret_like_literals_absent(),
        "workspace_manifest_exact": workspace_manifest_exact(),
    }
    payload = {
        "schema_version": "okcanvas-workspace-step008r4r12r3-static-contract-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": STEP,
        "version": VERSION,
        "runtime_step": RUNTIME_STEP,
        "runtime_version": RUNTIME_VERSION,
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "runtime_product_python_count": product_count,
        "runtime_product_python_changed": changed_product,
        "python_files_parsed": py_count,
        "json_files_parsed": json_count,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
