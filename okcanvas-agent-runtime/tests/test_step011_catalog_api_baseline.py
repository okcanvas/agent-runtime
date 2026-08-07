from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step011_runtime_capabilities_are_explicit() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.agent_definition_catalog_api_implemented is True
    assert info.evaluation_catalog_api_implemented is True
    assert info.evaluation_history_api_implemented is True
    assert info.evaluation_comparison_api_implemented is True
    assert info.catalog_api_read_only is True
    assert info.catalog_api_accepted is True


def test_step011_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP011_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["checks"]
    assert all(payload["checks"].values())
    assert payload["agent_definition_count"] == 2
    assert payload["evaluation_case_count"] == 1
