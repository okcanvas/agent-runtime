from __future__ import annotations

import json
from pathlib import Path

from scripts.json_subprocess_validation import run_json_python_validator

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_validator_runs_in_isolated_python_process() -> None:
    payload, diagnostic = run_json_python_validator(
        root=ROOT,
        script=ROOT / "scripts/validate_step081_architecture.py",
    )

    assert diagnostic["completed"] is True
    assert diagnostic["returncode"] == 0
    assert diagnostic["json_parsed"] is True
    assert payload is not None
    assert payload["state"] == "PASSED"
    assert payload["passed_checks"] == payload["total_checks"] == 40
    assert payload["checks"]["admin_route_inventory_exact"] is True
    assert payload["checks"]["service_route_inventory_exact"] is True
    assert payload["checks"]["route_method_path_duplicates_absent"] is True
    assert payload["checks"]["websocket_runtime_disabled"] is True


def test_live_acceptance_persists_full_architecture_diagnostic() -> None:
    source = (ROOT / "scripts/run_step081_live_acceptance.py").read_text(encoding="utf-8")

    assert "run_json_python_validator(" in source
    assert 'script=ROOT / "scripts/validate_step081_architecture.py"' in source
    assert '"step081_architecture_validation": architecture_validation' in source
    assert '"step081_architecture_validation_process": architecture_validation_process' in source
    assert 'architecture_validation_process.get("returncode") == 0' in source
    assert 'architecture_validation_process.get("json_parsed") is True' in source


def test_preserved_windows_failure_summary_is_exact() -> None:
    summary = json.loads(
        (ROOT / "docs/evidence/STEP081A_WINDOWS_LIVE_ACCEPTANCE_75_OF_77_FAILURE_SUMMARY.json")
        .read_text(encoding="utf-8")
    )

    assert summary["passed_checks"] == 75
    assert summary["total_checks"] == 77
    assert summary["terminal_status"] == "SUCCEEDED"
    assert summary["model_calls"] == 2
    assert summary["tool_calls"] == 1
    assert summary["sandbox_cleanup_state"] == "COMPLETED"
    assert summary["sandbox_orphan_count"] == 0
    assert summary["false_checks"] == [
        "step081_static_architecture_gate_complete",
        "step081_transport_topology_runtime_bound",
    ]
    assert summary["architecture_validation_detail_present"] is False
    assert summary["architecture_validation_process_detail_present"] is False


def test_step081b_live_evidence_is_excluded_from_source_packages() -> None:
    from scripts.step081_product_inventory import EXCLUDED_PREFIXES

    assert ("docs", "evidence", "step081c-live") in EXCLUDED_PREFIXES
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "docs/evidence/step081c-live/" in gitignore


def test_step081b_runtime_info_and_live_check_contract_are_exact() -> None:
    import ast

    from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

    info = RuntimeInfo()
    assert CURRENT_STEP == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert PROJECT_VERSION == "2.77.0"
    assert info.architecture_live_validator_process_isolation_implemented is True
    assert info.architecture_live_validator_diagnostic_payload_preserved is True
    assert info.architecture_live_validator_failure_fail_closed is True
    assert info.architecture_live_validator_process_isolation_windows_live_accepted is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"

    tree = ast.parse((ROOT / "scripts/run_step081_live_acceptance.py").read_text(encoding="utf-8"))
    check_counts = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not any(isinstance(target, ast.Name) and target.id == "checks" for target in node.targets):
            continue
        if isinstance(node.value, ast.Dict):
            check_counts.append(sum(isinstance(key, ast.Constant) and isinstance(key.value, str) for key in node.value.keys))
    assert max(check_counts) == 79
    source = (ROOT / "scripts/run_step081_live_acceptance.py").read_text(encoding="utf-8")
    assert 'payload["checks"]["api_key_not_in_summary"]' in source
