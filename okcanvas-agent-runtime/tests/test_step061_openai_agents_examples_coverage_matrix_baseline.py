from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step061_runtime_baseline_is_exact() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.query_directed_project_retrieval_windows_live_accepted is True
    assert info.sdk_examples_coverage_matrix_implemented is True
    assert info.sdk_examples_filesystem_python_file_count == 216
    assert info.sdk_examples_excluded_runner_support_file_count == 4
    assert info.sdk_examples_classified_count == 212
    assert info.sdk_examples_area_count == 15
    assert info.sdk_examples_adopt_count == 16
    assert info.sdk_examples_adapt_count == 16
    assert info.sdk_examples_defer_count == 171
    assert info.sdk_examples_reject_count == 9
    assert info.sdk_examples_matrix_sha_bound is True
    assert info.sdk_examples_coverage_matrix_deterministic_accepted is True
    assert info.sdk_examples_coverage_matrix_windows_live_accepted is True
    assert (
        info.sdk_examples_next_selected_step
        == "STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION"
    )
    assert info.bounded_multi_agent_orchestration_implemented is True


def test_step061_matrix_is_complete_and_exact() -> None:
    matrix = json.loads(
        (ROOT / "docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX.json").read_text(
            encoding="utf-8"
        )
    )
    assert matrix["filesystem_python_file_count"] == 216
    assert matrix["classified_example_count"] == 212
    assert matrix["area_count"] == 15
    assert matrix["decision_counts"] == {
        "ADAPT": 16,
        "ADOPT": 16,
        "DEFER": 171,
        "REJECT": 9,
    }
    entries = matrix["entries"]
    assert len(entries) == len({item["path"] for item in entries}) == 212
    by_path = {item["path"]: item for item in entries}
    assert by_path["agent_patterns/parallelization.py"]["decision"] == "DEFER"
    assert by_path["memory/sqlite_session_example.py"]["decision"] == "ADOPT"
    assert by_path["tools/codex.py"]["decision"] == "ADAPT"
    assert by_path["basic/previous_response_id.py"]["decision"] == "REJECT"
    assert sum(1 for item in entries if item["area"] == "sandbox") == 71


def test_step060_user_reported_windows_closure_is_recorded() -> None:
    closure = json.loads(
        (ROOT / "docs/evidence/STEP060_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert closure["state"] == "PASSED"
    assert closure["deterministic_acceptance"]["passed_checks"] == 20
    assert closure["real_openai_rerun"]["artifact_status"] == "PASS"
    assert (
        closure["real_openai_rerun"]["exact_evidence"]
        == "src/okcanvas_agent_runtime/control_api/app.py:485-487"
    )
    assert closure["real_openai_rerun"]["total_tokens"] == 2688
