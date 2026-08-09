from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step012_runtime_capabilities_are_explicit() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.recorded_run_evaluation_service_implemented is True
    assert info.recorded_run_evaluation_api_implemented is True
    assert info.recorded_run_evaluation_uses_product_state is True
    assert info.recorded_run_artifact_contract_validation is True
    assert info.recorded_run_evaluation_accepted is True
    assert info.evaluation_model_live_accepted is False
    assert info.direct_reference_import_forbidden is True


def test_step012_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP012_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["checks"]
    assert all(payload["checks"].values())
    assert payload["history_count"] == 2
