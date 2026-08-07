from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step025_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.commerce_snapshot_ingress_implemented is True
    assert info.commerce_snapshot_ingress_mode == "product-owned-loopback-http-before-preflight"
    assert info.commerce_snapshot_ingress_adapter_id == "controlled-commerce-http"
    assert info.commerce_snapshot_ingress_read_only is True
    assert info.commerce_snapshot_ingress_model_calls == 0
    assert info.commerce_snapshot_ingress_redirects_enabled is False
    assert info.commerce_snapshot_ingress_retries_enabled is False
    assert info.commerce_snapshot_source_identity_fingerprint_bound is True
    assert info.commerce_snapshot_idempotent_replay_implemented is True
    assert info.commerce_snapshot_ingress_deterministic_accepted is True
    assert info.commerce_snapshot_ingress_windows_live_accepted is True


def test_step025_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP025_ACCEPTANCE.json").read_text(encoding="utf-8")
    )
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert len(payload["checks"]) == 21
    assert all(payload["checks"].values())
    assert payload["source"]["read_count"] == 1
    assert payload["source"]["write_count"] == 0
    assert payload["artifact_count"] == 1
    assert payload["artifact_error"] is None
    assert payload["outcome_http_status"] == 200
    assert payload["outcome"]["status"] == "SUCCEEDED"
    assert payload["result"]["total_reorder_units"] == 19


def test_step025_windows_launcher_and_environment_keys_are_present() -> None:
    launcher = (ROOT / "sh_run_step025_acceptance.cmd").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    assert "commerce-snapshot-ingress-acceptance" in launcher
    assert "run_step025_acceptance.py" in entrypoint
    assert "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL" in entrypoint
    assert "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN" in entrypoint
