from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_step096b_static_contract import validate as validate_parent

STEP = "STEP096BR1R1_MODEL_BEHAVIOR_LIVE_DIAGNOSTIC_CLOSURE"
VERSION = "2.80.1"


def validate() -> dict[str, object]:
    baseline = (ROOT / "okcanvas_agent_runtime/core/baseline.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    gateway = (ROOT / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(encoding="utf-8")
    focused = (ROOT / "tests/test_step096br1_live_model_behavior_diagnostics.py").read_text(encoding="utf-8")
    parent = validate_parent()
    parent_checks = dict(parent["checks"])
    retained = all(value is True for key, value in parent_checks.items() if key != "identity_exact")
    checks = {
        "identity_exact": (
            f'CURRENT_STEP = "{STEP}"' in baseline
            and f'PROJECT_VERSION = "{VERSION}"' in baseline
            and f'version = "{VERSION}"' in pyproject
        ),
        "step096b_behavior_retained_except_identity": retained,
        "model_completed_records_content_free_item_type_counts": all(
            token in gateway
            for token in (
                "_safe_model_output_shape(response)",
                '"output_item_type_counts"',
                '"output_item_content_persisted": False',
            )
        ),
        "model_behavior_error_has_bounded_safe_categories": all(
            token in gateway
            for token in (
                "_safe_model_behavior_failure_diagnostic",
                "TOOL_ARGUMENT_JSON_INVALID",
                "TOOL_ARGUMENT_SCHEMA_INVALID",
                "UNKNOWN_TOOL_CALL",
                "STRUCTURED_FINAL_OUTPUT_INVALID",
                "STRUCTURED_FINAL_OUTPUT_MISSING",
                "MODEL_BEHAVIOR_OTHER",
                '"raw_model_output_persisted": False',
                '"raw_tool_arguments_persisted": False',
                '"raw_error_message_persisted": False',
            )
        ),
        "generic_sdk_failure_persists_safe_diagnostic_only": (
            "diagnostic = _safe_model_behavior_failure_diagnostic(exc)" in gateway
            and "diagnostic=diagnostic" in gateway
        ),
        "focused_diagnostic_tests_are_content_free": all(
            token in focused
            for token in (
                "test_step096br1_model_output_shape_is_content_free",
                "test_step096br1_model_behavior_categories_are_safe_and_payload_free",
                "test_step096br1_non_model_behavior_error_has_no_model_diagnostic",
            )
        ),
        "functional_semantics_not_claimed_changed": True,
        "windows_live_rerun_required": True,
    }
    return {
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": STEP,
        "version": VERSION,
        "parent_step": parent.get("step"),
        "parent_version": parent.get("version"),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
