from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
import sys
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
MATRIX_PATH = ROOT / "docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX.json"
EXAMPLES_ROOT = ROOT / "reference/upstream/openai-agents-python-0.19.0/examples"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP061_ACCEPTANCE.json"
EXPECTED_EXCLUDED = ["__init__.py", "auto_mode.py", "run_examples.py", "web_search_utils.py"]
EXPECTED_AREAS = {
    "agent_patterns",
    "basic",
    "customer_service",
    "financial_research_agent",
    "handoffs",
    "hosted_mcp",
    "mcp",
    "memory",
    "model_providers",
    "realtime",
    "reasoning_content",
    "research_bot",
    "sandbox",
    "tools",
    "voice",
}
EXPECTED_DECISIONS = {"ADOPT": 16, "ADAPT": 16, "DEFER": 171, "REJECT": 9}
NEXT_STEP = "STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence_path_exists(raw: str) -> bool:
    path = ROOT / raw.rstrip("/")
    return path.exists()


def run(output: Path) -> int:
    matrix = _load_json(MATRIX_PATH)
    entries = matrix.get("entries")
    if not isinstance(entries, list):
        entries = []
    all_py = sorted(EXAMPLES_ROOT.rglob("*.py"))
    paths = [str(item.get("path", "")) for item in entries if isinstance(item, dict)]
    decisions = Counter(
        str(item.get("decision", "")) for item in entries if isinstance(item, dict)
    )
    areas = {str(item.get("area", "")) for item in entries if isinstance(item, dict)}

    source_integrity = all(
        isinstance(item, dict)
        and (EXAMPLES_ROOT / str(item.get("path", ""))).is_file()
        and _sha(EXAMPLES_ROOT / str(item["path"])) == item.get("sha256")
        for item in entries
    )
    line_counts_match = all(
        isinstance(item, dict)
        and len((EXAMPLES_ROOT / str(item["path"])).read_text(encoding="utf-8").splitlines())
        == item.get("line_count")
        for item in entries
    )
    evidence_paths_exist = all(
        _evidence_path_exists(raw)
        for item in entries
        if isinstance(item, dict) and item.get("decision") in {"ADOPT", "ADAPT"}
        for raw in item.get("current_product_evidence", [])
    )
    by_path = {str(item.get("path")): item for item in entries if isinstance(item, dict)}
    key_decisions = {
        "parallelization_deferred": by_path.get("agent_patterns/parallelization.py", {}).get("decision")
        == "DEFER",
        "deterministic_deferred": by_path.get("agent_patterns/deterministic.py", {}).get("decision")
        == "DEFER",
        "sqlite_session_adopted": by_path.get("memory/sqlite_session_example.py", {}).get("decision")
        == "ADOPT",
        "stdio_mcp_adopted": by_path.get("mcp/filesystem_example/main.py", {}).get("decision")
        == "ADOPT",
        "codex_adapted": by_path.get("tools/codex.py", {}).get("decision") == "ADAPT",
        "previous_response_rejected": by_path.get("basic/previous_response_id.py", {}).get("decision")
        == "REJECT",
        "hosted_multi_agent_beta_rejected": by_path.get(
            "agent_patterns/hosted_multi_agent_beta.py", {}
        ).get("decision")
        == "REJECT",
        "web_search_deferred": by_path.get("tools/web_search.py", {}).get("decision") == "DEFER",
    }
    sandbox_entries = [item for item in entries if isinstance(item, dict) and item.get("area") == "sandbox"]
    sandbox_exact = len(sandbox_entries) == 71 and all(
        item.get("decision") == "DEFER" and item.get("target_track") == "SANDBOX_PLATFORM"
        for item in sandbox_entries
    )

    closure = _load_json(ROOT / "docs/evidence/STEP060_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")
    deterministic = closure.get("deterministic_acceptance", {})
    real = closure.get("real_openai_rerun", {})
    closure_exact = (
        closure.get("state") == "PASSED"
        and deterministic.get("passed_checks") == 20
        and deterministic.get("total_checks") == 20
        and deterministic.get("cleanup_state") == "COMPLETED"
        and deterministic.get("protected_payload_files") == 0
        and real.get("artifact_status") == "PASS"
        and real.get("exact_evidence")
        == "okcanvas_agent_runtime/control_api/app.py:485-487"
        and real.get("unrelated_findings_present") is False
        and real.get("total_tokens") == 2688
        and real.get("token_gate_passed") is True
    )

    baseline = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")
    model = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model.py")).read_text(encoding="utf-8")
    code_audit = (
        ROOT / "docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX_AND_NEXT_SCOPE_SELECTION_CODE_AUDIT.md"
    ).read_text(encoding="utf-8")
    plan = (
        ROOT / "docs/plans/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX_AND_NEXT_SCOPE_SELECTION.md"
    ).read_text(encoding="utf-8")
    matrix_md = (
        ROOT / "docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX.md"
    ).read_text(encoding="utf-8")

    # Product source must still have no orchestration fan-out implementation.
    src_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "okcanvas_agent_runtime").rglob("*.py")
    )
    orchestration_absent = (
        "asyncio.gather(" not in src_text
        and "TaskGroup(" not in src_text
        and "bounded_multi_agent_orchestration_implemented: bool = False" in model
    )

    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_unchanged = len(reference_results) == 4 and all(item.verified for item in reference_results)

    checks = {
        "baseline_version_and_step_exact": (
            'PROJECT_VERSION = "2.41.0"' in baseline
            and 'CURRENT_STEP = "STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX_AND_NEXT_SCOPE_SELECTION"'
            in baseline
        ),
        "matrix_schema_and_version_exact": (
            matrix.get("schema_version") == "okcanvas-openai-agents-examples-coverage-matrix-v1"
            and matrix.get("project_version") == "2.41.0"
        ),
        "filesystem_python_file_count_exact": len(all_py) == 216,
        "excluded_runner_support_files_exact": matrix.get("excluded_runner_support_files")
        == EXPECTED_EXCLUDED,
        "classified_example_count_exact": len(entries) == 212,
        "entry_paths_unique": len(paths) == len(set(paths)) == 212,
        "area_set_and_count_exact": areas == EXPECTED_AREAS and matrix.get("area_count") == 15,
        "decision_counts_exact": dict(decisions) == EXPECTED_DECISIONS,
        "source_sha256_integrity_exact": source_integrity,
        "source_line_counts_exact": line_counts_match,
        "adopt_adapt_evidence_paths_exist": evidence_paths_exist,
        "key_example_decisions_exact": all(key_decisions.values()),
        "sandbox_track_exact": sandbox_exact,
        "step060_windows_closure_exact": closure_exact,
        "next_step_single_and_exact": (
            matrix.get("next_selected_implementation_step") == NEXT_STEP
            and NEXT_STEP in code_audit
            and NEXT_STEP in plan
        ),
        "orchestration_not_implemented_in_step061": orchestration_absent,
        "matrix_markdown_has_212_rows": sum(
            1
            for line in matrix_md.splitlines()
            if line.startswith("| ")
            and len(line.split("|")) > 2
            and line.split("|")[1].strip().isdigit()
        )
        == 212,
        "step061_docs_present": all(
            path.is_file()
            for path in (
                MATRIX_PATH,
                ROOT / "docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX.md",
                ROOT / "docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX_AND_NEXT_SCOPE_SELECTION_CODE_AUDIT.md",
                ROOT
                / "docs/plans/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX_AND_NEXT_SCOPE_SELECTION.md",
            )
        ),
        "runtime_info_matrix_counts_exact": all(
            text in model
            for text in (
                "sdk_examples_classified_count: int = 212",
                "sdk_examples_area_count: int = 15",
                "sdk_examples_adopt_count: int = 16",
                "sdk_examples_adapt_count: int = 16",
                "sdk_examples_defer_count: int = 171",
                "sdk_examples_reject_count: int = 9",
            )
        ),
        "references_unchanged": references_unchanged,
    }
    payload = {
        "schema_version": "okcanvas-step061-acceptance-v1",
        "step": "STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX_AND_NEXT_SCOPE_SELECTION",
        "version": "2.41.0",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "decision_counts": dict(decisions),
        "area_count": len(areas),
        "classified_example_count": len(entries),
        "next_selected_step": matrix.get("next_selected_implementation_step"),
        "key_decisions": key_decisions,
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
