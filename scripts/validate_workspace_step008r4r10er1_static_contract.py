from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.workspace_inventory import MUTABLE_ACCEPTANCE_EVIDENCE, snapshot_files

WORKSPACE_STEP = "WORKSPACE_STEP008R4R10ER1_CROSS_DOMAIN_LIVE_ACCEPTANCE_PROMOTION_CLOSURE"
WORKSPACE_VERSION = "0.8.4-r10er1"
RUNTIME_STEP = "STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE"
RUNTIME_VERSION = "2.78.2"
PARENT_STEP = "WORKSPACE_STEP008R4R10E_CROSS_DOMAIN_LIVE_EVIDENCE_PROVENANCE_IDENTITY_CLOSURE"
PARENT_VERSION = "0.8.4-r10e"
PARENT_PACKAGE_SHA256 = "066c498be186995a6e2a19de6091c6c6fa1d5cde2d1ced81a918b884507ed097"
R10E_BASELINE_SHA256 = "68c03b0862664e911b3e543b26677edb560a287c5958acffccd41fcde0bc1004"
R10E_CATALOG_SHA256 = "c38310b0024aefe9270b5b1e923f833cb1f276c9d9c3f521e25bf4da304c2db9"
R10E_WORKSPACE_MANIFEST_SHA256 = "ad5baafa884d5ef6a6bd30cfbda65fc463e84ba4963b5590f0f74a2a52383279"
R10E_RUNTIME_PARENT_MANIFEST_SHA256 = "a40f0c828781cf2c2613fc130e64f3408d4567d4242a9806d841c0f9b6515203"
R10E_MARKER_SHA256 = "a7e5ac10eef8eeb10e35c6250fc88731c81d7f4e7c8c30ca140aaccd31c2f37d"
R10E_STATIC_SUMMARY_SHA256 = "30d205abbda160ffef398d323c53ea157ff3766f7b6c549b38d1c0d0c763eb54"
HARNESS_SHA256 = "a1953c4a66612c9331b63b523ae2efc178669a5694cc558252b00eff90fd7e9c"
RUNTIME_BASELINE_SHA256 = "1d00cbabf3abccd4453428f01953f3f3d86f3480719dc0f079f0691cbc502ddb"
RUNTIME_PYPROJECT_SHA256 = "ecbe598fbdad7876244dde9954312a704a9116aae4d5c4f5b0a606c39fdfc78c"


def _load(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _sha(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def _manifest_matches(project_relative: str, manifest_relative: str) -> bool:
    manifest = _load(manifest_relative)
    expected = {
        str(item["path"]): (str(item["sha256"]), int(item["size"]))
        for item in manifest.get("files", [])
    }
    actual = snapshot_files(ROOT / project_relative)
    return manifest.get("file_count") == len(expected) == len(actual) and expected == actual


def _runtime_product_python_unchanged_from_r10e() -> bool:
    retained = _load(
        "docs/evidence/retained/step008r4r10e-live-source/reference/parent-file-manifests/okcanvas-agent-runtime.json"
    )
    prior = {
        str(item["path"]): (str(item["sha256"]), int(item["size"]))
        for item in retained.get("files", [])
        if str(item.get("path", "")).startswith("okcanvas_agent_runtime/")
        and str(item.get("path", "")).endswith(".py")
    }
    current_all = snapshot_files(ROOT / "okcanvas-agent-runtime")
    current = {
        path: value
        for path, value in current_all.items()
        if path.startswith("okcanvas_agent_runtime/") and path.endswith(".py")
    }
    return len(prior) == 355 and prior == current


def validate() -> dict[str, object]:
    baseline = _load("specs/workspace/current-baseline.json")
    catalog = _load("specs/workspace/project-catalog.json")
    runtime = next(p for p in catalog["projects"] if p["project_id"] == "agent-runtime")
    evidence = _load("docs/evidence/WORKSPACE_STEP008R4R10E_CROSS_DOMAIN_LIVE_ACCEPTANCE_USER_REPORTED.json")
    marker = _load("WORKSPACE_STEP008R4R10ER1_PROMOTION_MARKER.json")
    issue_registry = (ROOT / "docs/issues/ISSUE_REGISTRY.md").read_text(encoding="utf-8")
    issue058 = (ROOT / "docs/issues/WORKSPACE-ISSUE-058-POST-LIVE-PROMOTION-MUST-NOT-MUTATE-EXECUTED-PROVENANCE-SOT.md").read_text(encoding="utf-8")
    issue059 = (ROOT / "docs/issues/WORKSPACE-ISSUE-059-ISSUE-REGISTRY-LAGGED-RECORDED-ISSUES-043-058.md").read_text(encoding="utf-8")
    audit = (ROOT / "docs/plans/STEP095A_BOUNDED_DURABLE_MEMORY_EXHAUSTIVE_AUDIT.md").read_text(encoding="utf-8")
    implied = list((evidence.get("code_level_interpretation") or {}).get("implied_true_checks") or [])
    limitations = evidence.get("limitations") or {}
    report = evidence.get("user_reported_execution") or {}
    source_package = evidence.get("source_package") or {}
    retained_hashes = evidence.get("retained_live_source_hashes") or {}
    required_provenance_checks = {
        "workspace_catalog_identity_matches_current_baseline",
        "workspace_runtime_identity_matches_project_catalog",
        "workspace_runtime_identity_matches_executable_runtime",
        "workspace_runtime_version_matches_runtime_package_metadata",
        "runtime_service_version_matches_workspace_baseline",
    }
    mutable_required = {
        "docs/evidence/WORKSPACE_STEP008R4R9_RELATION_LIVE_ACCEPTANCE.json",
        "docs/evidence/WORKSPACE_STEP008R4R10_CROSS_DOMAIN_LIVE_ACCEPTANCE.json",
    }
    checks = {
        "workspace_identity_exact": baseline.get("workspace_step") == WORKSPACE_STEP and baseline.get("workspace_version") == WORKSPACE_VERSION,
        "runtime_identity_exact": baseline.get("runtime_step") == RUNTIME_STEP and baseline.get("runtime_version") == RUNTIME_VERSION,
        "promotion_current": baseline.get("promotion") == "CURRENT_PROMOTED_BASELINE" and marker.get("promotion") == "CURRENT_PROMOTED_BASELINE",
        "promotion_parent_exact": baseline.get("parent_workspace_step") == PARENT_STEP and baseline.get("parent_workspace_version") == PARENT_VERSION and baseline.get("source_release_sha256") == PARENT_PACKAGE_SHA256,
        "catalog_matches_current": catalog.get("workspace_step") == WORKSPACE_STEP and catalog.get("workspace_version") == WORKSPACE_VERSION and runtime.get("baseline") == RUNTIME_STEP and runtime.get("version") == RUNTIME_VERSION,
        "user_report_exact_24_of_24": report.get("state") == "PASSED" and report.get("passed_checks") == 24 and report.get("total_checks") == 24,
        "user_report_source_exact": evidence.get("source_workspace_step") == PARENT_STEP and evidence.get("source_workspace_version") == PARENT_VERSION and evidence.get("source_runtime_step") == RUNTIME_STEP and evidence.get("source_runtime_version") == RUNTIME_VERSION and source_package.get("sha256") == PARENT_PACKAGE_SHA256,
        "user_report_no_fabrication": limitations.get("full_generated_live_evidence_json_embedded") is False and limitations.get("fabricated_missing_values") is False and limitations.get("exact_model_name_available_from_this_report") is False,
        "user_report_implies_24_checks": len(implied) == 24 and len(set(implied)) == 24,
        "user_report_includes_all_provenance_checks": required_provenance_checks.issubset(set(implied)),
        "user_report_includes_function_and_cleanup_checks": all(name in implied for name in ("expected_mcp_tool_sequence_observed", "groupware_context_ref_and_canonical_arguments_exact", "harness_cleanup_completed")),
        "retained_r10e_baseline_exact": _sha("docs/evidence/retained/step008r4r10e-live-source/specs/workspace/current-baseline.json") == R10E_BASELINE_SHA256 and retained_hashes.get("workspace_current_baseline_sha256") == R10E_BASELINE_SHA256,
        "retained_r10e_catalog_exact": _sha("docs/evidence/retained/step008r4r10e-live-source/specs/workspace/project-catalog.json") == R10E_CATALOG_SHA256 and retained_hashes.get("workspace_project_catalog_sha256") == R10E_CATALOG_SHA256,
        "retained_r10e_workspace_manifest_exact": _sha("docs/evidence/retained/step008r4r10e-live-source/WORKSPACE_MANIFEST.json") == R10E_WORKSPACE_MANIFEST_SHA256 and retained_hashes.get("workspace_manifest_sha256") == R10E_WORKSPACE_MANIFEST_SHA256,
        "retained_r10e_runtime_parent_manifest_exact": _sha("docs/evidence/retained/step008r4r10e-live-source/reference/parent-file-manifests/okcanvas-agent-runtime.json") == R10E_RUNTIME_PARENT_MANIFEST_SHA256,
        "r10e_marker_immutable": _sha("WORKSPACE_STEP008R4R10E_PROMOTION_MARKER.json") == R10E_MARKER_SHA256,
        "r10e_static_summary_immutable": _sha("WORKSPACE_STEP008R4R10E_STATIC_VALIDATION_SUMMARY.json") == R10E_STATIC_SUMMARY_SHA256,
        "focused_live_harness_immutable": _sha("scripts/run_workspace_step008r4r10_cross_domain_live_acceptance.py") == HARNESS_SHA256 and retained_hashes.get("focused_live_harness_sha256") == HARNESS_SHA256,
        "runtime_executable_baseline_immutable": _sha("okcanvas-agent-runtime/okcanvas_agent_runtime/core/baseline.py") == RUNTIME_BASELINE_SHA256,
        "runtime_pyproject_immutable": _sha("okcanvas-agent-runtime/pyproject.toml") == RUNTIME_PYPROJECT_SHA256,
        "runtime_product_python_unchanged": _runtime_product_python_unchanged_from_r10e(),
        "current_runtime_parent_manifest_exact": _manifest_matches("okcanvas-agent-runtime", "reference/parent-file-manifests/okcanvas-agent-runtime.json"),
        "focused_live_outputs_mutable": mutable_required.issubset(MUTABLE_ACCEPTANCE_EVIDENCE),
        "issue058_records_post_live_provenance_rule": "Never rewrite an already executed release's hashed identity inputs" in issue058,
        "issue059_and_registry_continuity": "WORKSPACE-ISSUE-059" in issue059 and all(f"WORKSPACE-ISSUE-{n:03d} |" in issue_registry for n in range(43, 60)),
        "step095a_is_read_only_audit": "READ_ONLY_AUDIT_PREPARED_NO_PRODUCT_MEMORY_IMPLEMENTATION" in audit and "no Runtime Product source modification" in audit and all(token in audit for token in ("no Runtime Product source modification", "no new database table or migration", "no memory API route", "no memory-driven routing")),
        "runtime_product_source_declared_unchanged": baseline.get("runtime_product_source_changed") is False and marker.get("runtime_product_source_changed") is False,
        "deferred_items_remain_nonblocking": baseline.get("minio_object_storage_live") == "DEFERRED_BY_USER" and marker.get("broad_tests") == "DEFERRED_BY_USER",
    }
    return {
        "schema_version": "okcanvas-workspace-step008r4r10er1-static-contract-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": WORKSPACE_STEP,
        "version": WORKSPACE_VERSION,
        "runtime_step": RUNTIME_STEP,
        "runtime_version": RUNTIME_VERSION,
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2, sort_keys=True))
