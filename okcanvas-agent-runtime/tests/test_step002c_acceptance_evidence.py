import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_step002c_live_acceptance_evidence_is_self_consistent() -> None:
    evidence = json.loads((ROOT / "docs/evidence/STEP002C_LIVE_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    assert evidence["schema_version"] == "okcanvas-step002c-live-acceptance-evidence-v1"
    assert evidence["baseline_step"] == "STEP002C_CODEX_READ_ONLY_LIVE_ACCEPTANCE"
    assert evidence["project_version"] == "0.2.3"
    assert evidence["state"] == "PASSED"
    assert all(evidence["checks"].values())
    assert evidence["sdk_version"] == "0.19.0"
    assert evidence["codex_cli_version"] == "codex-cli 0.145.0"
    assert evidence["thread_id"]
    assert evidence["first_run_id"] != evidence["second_run_id"]
    assert evidence["usage"]["combined_agent_total_tokens"] == 168949
    assert evidence["workspace_tree_sha256"] == "06ac7d3e056fc4f1ea97b9d2654d0648df090f4708df329ca5dcc22df9cd604a"


def test_raw_acceptance_log_is_present() -> None:
    text = (ROOT / "docs/evidence/STEP002C_LIVE_ACCEPTANCE_RAW.txt").read_text(encoding="utf-8")
    assert '"ready": true' in text
    assert '"state": "PASSED"' in text
    assert '"resumed_thread": true' in text
