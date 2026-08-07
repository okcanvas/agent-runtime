from __future__ import annotations

import json
from pathlib import Path

from scripts.step081_architecture import route_inventory
from scripts.validate_step081_architecture import validate

ROOT = Path(__file__).resolve().parents[1]


def test_preserved_step081b_windows_deterministic_failure_is_exact() -> None:
    payload = json.loads(
        (ROOT / "docs/evidence/STEP081B_WINDOWS_DETERMINISTIC_ACCEPTANCE_15_OF_18_FAILURE_SUMMARY.json")
        .read_text(encoding="utf-8")
    )
    assert payload["passed_checks"] == 15
    assert payload["total_checks"] == 18
    assert payload["architecture_passed_checks"] == 36
    assert payload["architecture_total_checks"] == 38
    assert payload["api_or_billing_required"] is False
    assert payload["architecture_false_check_names_preserved"] is False


def test_architecture_reconciles_source_and_runtime_routes() -> None:
    result = validate()
    assert result["state"] == "PASSED"
    inventory = result["details"]["route_inventory"]
    assert inventory["source"]["admin_route_count"] == 54
    assert inventory["source"]["service_route_count"] == 39
    assert inventory["runtime"]["admin_route_count"] == 54
    assert inventory["runtime"]["service_route_count"] == 39
    assert inventory["missing_runtime_v1_routes"] == []
    assert inventory["unexpected_runtime_v1_routes"] == []
    assert inventory["source"]["duplicates"] == []
    assert inventory["runtime"]["duplicates"] == []


def test_deterministic_acceptance_preserves_subvalidator_payloads() -> None:
    source = (ROOT / "scripts/run_step081_acceptance.py").read_text(encoding="utf-8")
    assert source.count("run_json_python_validator(") >= 2
    assert '"architecture_validation": architecture' in source
    assert '"architecture_validation_process": architecture_process' in source
    assert '"compliance_validation": compliance' in source
    assert '"compliance_validation_process": compliance_process' in source
    assert 'architecture_process.get("returncode") == 0' in source
    assert 'compliance_process.get("returncode") == 0' in source


def test_local_acceptance_output_is_excluded_from_product_inventory() -> None:
    from scripts.run_step081c_acceptance import OUTPUT_DEFAULT
    from scripts.step081_product_inventory import EXCLUDED_PREFIXES, included_relative_path

    relative = OUTPUT_DEFAULT.relative_to(ROOT)
    assert relative.parts[:3] == ("docs", "evidence", "step081c-local")
    assert ("docs", "evidence", "step081c-local") in EXCLUDED_PREFIXES
    assert included_relative_path(relative) is False
    assert "docs/evidence/step081c-local/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_step081c_launcher_registry_is_current() -> None:
    from scripts.validate_acceptance_launcher_registry import validate as validate_registry

    result = validate_registry()
    assert result["state"] == "PASSED"
    registry = json.loads((ROOT / "specs/acceptance/launcher-registry.json").read_text(encoding="utf-8"))
    current_records = [record for record in registry["records"] if record["classification"] == "CURRENT"]
    current = [record["path"] for record in current_records]
    token = registry["current_step_token"].casefold()
    required = {(item["kind"], item["mode"]) for item in registry["required_current_records"]}
    assert {(item["kind"], item["mode"]) for item in current_records} == required
    assert all(token in path.casefold() for path in current)
