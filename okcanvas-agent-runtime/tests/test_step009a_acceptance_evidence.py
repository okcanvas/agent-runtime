import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step009a_live_acceptance_evidence_is_self_consistent() -> None:
    evidence = json.loads((ROOT / "docs/evidence/STEP009A_LIVE_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    assert evidence["schema_version"] == "okcanvas-step009a-live-acceptance-evidence-v1"
    assert evidence["baseline_step"] == "STEP009A_FIRST_READ_ONLY_MCP_LIVE_ACCEPTANCE"
    assert evidence["project_version"] == "0.9.1"
    assert evidence["source_runtime_version"] == "0.9.0"
    assert evidence["state"] == "PASSED"
    assert all(evidence["checks"].values())
    assert evidence["mcp"]["listed_tools"] == ["search_reference", "read_reference_file"]
    assert evidence["mcp"]["protocol_search_path"] == "src/agents/run_state.py"
    assert evidence["mcp"]["canonical_mcp_event_count"] == 4
    assert evidence["reference_integrity"]["all_verified"] is True
    assert evidence["agent"]["state"] == "SUCCEEDED"
    assert evidence["agent"]["usage"]["total_tokens"] == 2785
    assert evidence["trace_export"]["openai_trace_upload_live_accepted"] is False
    assert evidence["capability_boundary"]["mcp_protocol_live_accepted"] is True
    assert evidence["capability_boundary"]["mcp_agent_live_accepted"] is True
    assert evidence["capability_boundary"]["write_capable_mcp_enabled"] is False


def test_step009a_raw_acceptance_record_is_present_and_secret_free() -> None:
    text = (ROOT / "docs/evidence/STEP009A_LIVE_ACCEPTANCE_RAW.txt").read_text(encoding="utf-8")
    assert '"state": "PASSED"' in text
    assert '"protocol_connected": true' in text
    assert '"tool_arguments_redacted": true' in text
    assert 'Tracing client error 400' in text
    assert 'sk-' not in text
