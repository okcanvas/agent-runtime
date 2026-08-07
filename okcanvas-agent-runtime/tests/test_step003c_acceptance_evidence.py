import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_step003c_live_acceptance_evidence_is_self_consistent() -> None:
    evidence = json.loads((ROOT / "docs/evidence/STEP003C_LIVE_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    assert evidence["schema_version"] == "okcanvas-step003c-live-acceptance-evidence-v1"
    assert evidence["baseline_step"] == "STEP003C_DISPOSABLE_WORKSPACE_WRITE_LIVE_ACCEPTANCE"
    assert evidence["project_version"] == "0.3.3"
    assert evidence["state"] == "PASSED"
    assert all(evidence["checks"].values())
    assert evidence["sdk_version"] == "0.19.0"
    assert evidence["codex_cli_version"] == "codex-cli 0.145.0"
    assert evidence["baseline_commit"] == evidence["final_commit"]
    assert evidence["modified_files"] == ["src/inventory/pricing.py"]
    assert evidence["baseline_validation"]["failed"] == 1
    assert evidence["post_validation"]["passed"] == 1
    assert evidence["cleanup"]["state"] == "COMPLETED"
    assert evidence["usage"]["agent_total_tokens"] == 75521
    assert evidence["capability_boundary"]["workspace_write_live_accepted"] is True
    assert evidence["capability_boundary"]["workspace_write_enabled_for_external_projects"] is False


def test_step003c_raw_acceptance_record_is_present() -> None:
    text = (ROOT / "docs/evidence/STEP003C_LIVE_ACCEPTANCE_RAW.txt").read_text(encoding="utf-8")
    assert "final state=PASSED" in text
    assert "cleanup state=COMPLETED" in text
    assert "all ten acceptance checks=true" in text
