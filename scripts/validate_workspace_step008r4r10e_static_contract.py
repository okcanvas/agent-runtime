from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_STEP = "WORKSPACE_STEP008R4R10E_CROSS_DOMAIN_LIVE_EVIDENCE_PROVENANCE_IDENTITY_CLOSURE"
WORKSPACE_VERSION = "0.8.4-r10e"
RUNTIME_STEP = "STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE"
RUNTIME_VERSION = "2.78.2"
PARENT_STEP = "WORKSPACE_STEP008R4R10D_RUNTIME_STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE"
PARENT_SHA = "e4e0603c0fd1ac9135cd5e530cb2511fc46891d5b160bc6e4a6af6efdd4143b8"


def _load(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> dict[str, object]:
    baseline = _load("specs/workspace/current-baseline.json")
    catalog = _load("specs/workspace/project-catalog.json")
    runtime = next(p for p in catalog["projects"] if p["project_id"] == "agent-runtime")
    harness = (ROOT / "scripts/run_workspace_step008r4r10_cross_domain_live_acceptance.py").read_text(encoding="utf-8")
    issue = (ROOT / "docs/issues/WORKSPACE-ISSUE-056-CROSS-DOMAIN-LIVE-EVIDENCE-FOOTER-DID-NOT-MATCH-EXECUTED-RUNTIME.md").read_text(encoding="utf-8")
    inventory = (ROOT / "scripts/workspace_inventory.py").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    retained = _load("docs/evidence/WORKSPACE_STEP008R4R10D_CROSS_DOMAIN_LIVE_FUNCTIONAL_PASS_PROVENANCE_INVALID_USER_REPORTED.json")
    first_cli = (retained.get("cli_summaries") or [{}])[0]
    retained_stdout = str(first_cli.get("stdout") or "")
    checks = {
        "workspace_identity_exact": baseline.get("workspace_step") == WORKSPACE_STEP and baseline.get("workspace_version") == WORKSPACE_VERSION,
        "runtime_identity_unchanged": baseline.get("runtime_step") == RUNTIME_STEP and baseline.get("runtime_version") == RUNTIME_VERSION,
        "parent_r10d_exact": baseline.get("parent_workspace_step") == PARENT_STEP and baseline.get("source_release_sha256") == PARENT_SHA,
        "runtime_product_source_unchanged": baseline.get("runtime_product_source_changed") is False,
        "project_catalog_matches_current": catalog.get("workspace_step") == WORKSPACE_STEP and catalog.get("workspace_version") == WORKSPACE_VERSION and runtime.get("baseline") == RUNTIME_STEP and runtime.get("version") == RUNTIME_VERSION,
        "harness_schema_v2": "okcanvas-workspace-step008r4r10-cross-domain-live-acceptance-v2" in harness,
        "harness_records_file_hashes": all(token in harness for token in ("_sha256_file", "workspace_current_baseline", "workspace_project_catalog", "runtime_executable_baseline", "runtime_package_metadata", "focused_live_harness")),
        "harness_compares_catalog_to_baseline": "workspace_catalog_identity_matches_current_baseline" in harness and "workspace_runtime_identity_matches_project_catalog" in harness,
        "harness_compares_executable_runtime": "workspace_runtime_identity_matches_executable_runtime" in harness and "EXECUTABLE_RUNTIME_STEP" in harness and "EXECUTABLE_RUNTIME_VERSION" in harness,
        "harness_compares_runtime_pyproject": "workspace_runtime_version_matches_runtime_package_metadata" in harness and "tomllib.loads" in harness,
        "harness_compares_live_service_version": "runtime_service_version_matches_workspace_baseline" in harness and 'client.get("/v1/service/capabilities")' in harness,
        "identity_mismatch_fails_closed": harness.count("LIVE_IDENTITY_PROVENANCE_MISMATCH") >= 2 and "Runtime Service version differs from Workspace current baseline" in harness,
        "functional_cases_unchanged": all(token in harness for token in ('"김선임 연락처"', '"그 사람 일정은?"', '"그 사람 관련 공지 알려줘"', '[["resolve_organization_context"], ["list_calendar_events"], ["search_notices"]]')),
        "prior_functional_pass_retained": retained.get("state") == "PASSED" and retained.get("passed_checks") == 19 and retained.get("total_checks") == 19,
        "prior_provenance_contradiction_retained": retained.get("runtime_version") == "2.78.1" and retained.get("version") == "0.8.4-r10c" and "Runtime 2.78.2" in retained_stdout,
        "issue_forbids_relabel_and_fallback": all(token in issue for token in ("No helper alias", "fallback", "compatibility shim", "not rewritten")),
        "clean_live_rerun_required": "CLEAN_R10E_LIVE_RERUN_REQUIRED" in handoff and baseline.get("promotion") == "NOT_READY",
        "provenance_sot_exact": baseline.get("cross_domain_live_identity_provenance") == "BASELINE_CATALOG_EXECUTABLE_RUNTIME_PYPROJECT_AND_SERVICE_VERSION_MUST_MATCH_BEFORE_ACCEPTANCE",
        "focused_live_outputs_explicitly_mutable": all(token in inventory for token in ("WORKSPACE_STEP008R4R9_RELATION_LIVE_ACCEPTANCE.json", "WORKSPACE_STEP008R4R10_CROSS_DOMAIN_LIVE_ACCEPTANCE.json")),
    }
    return {
        "schema_version": "okcanvas-workspace-step008r4r10e-static-contract-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": WORKSPACE_STEP,
        "version": WORKSPACE_VERSION,
        "runtime_step": RUNTIME_STEP,
        "runtime_version": RUNTIME_VERSION,
        "checks": checks,
        "passed_checks": sum(v is True for v in checks.values()),
        "total_checks": len(checks),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2, sort_keys=True))
