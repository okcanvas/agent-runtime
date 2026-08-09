from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step066_remote_mcp_remains_implemented_and_windows_accepted() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.mcp_mode == "allowlisted-read-only-local-stdio-and-remote-streamable-http"
    assert info.remote_mcp_streamable_http_implemented is True
    assert info.remote_mcp_streamable_http_mode == "v2-single-exact-or-v3-multi-tenant-delegated-read-only"
    assert info.remote_mcp_streamable_http_authorization_modes == "none,bearer-env"
    assert info.remote_mcp_streamable_http_redirects_enabled is False
    assert info.remote_mcp_streamable_http_proxy_environment_enabled is False
    assert info.remote_mcp_streamable_http_retry_attempts == 0
    assert info.remote_mcp_streamable_http_session_composition_enabled is False
    assert info.remote_mcp_streamable_http_deterministic_accepted is True
    assert info.remote_mcp_streamable_http_windows_live_accepted is True


def test_step066_windows_live_evidence_is_exact() -> None:
    payload = json.loads(
        (ROOT / "docs/evidence/STEP066_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["step"] == "STEP066_REMOTE_MCP_STREAMABLE_HTTP_MVP_FOUNDATION"
    assert payload["version"] == "2.46.0"
    assert payload["reported_state"] == "PASSED"
    assert payload["reported_passed_checks"] == 28
    assert payload["reported_total_checks"] == 28
    assert payload["external_network_calls"] == 0
    assert payload["model_calls"] == 0


def test_step066_reprioritization_keeps_step065_post_mvp() -> None:
    payload = json.loads(
        (ROOT / "docs/evidence/STEP065_MVP_REPRIORITIZATION_DECISION.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["decision"] == "OPERATIONS_STABILITY_AFTER_MVP"
    assert payload["implemented_but_not_windows_accepted"]["step"] == (
        "STEP065_STRICT_SESSION_HISTORY_KEY_ROTATION_AND_RECOVERY_V1"
    )
    assert payload["implemented_but_not_windows_accepted"]["classification"] == (
        "POST_MVP_OPERATIONAL_HARDENING_FROZEN"
    )


def test_remote_template_remains_non_enabled_and_reserved() -> None:
    catalog = MCPServerCatalog(ROOT)
    server_ids = [item.server_id for item in catalog.list_servers()]
    assert "reference-catalog" in server_ids
    assert "organization-search" not in server_ids
    groupware = catalog.resolve("groupware-read")
    assert groupware.schema_version == "okcanvas-mcp-server-v3"
    assert groupware.read_only is True
    template = json.loads(
        (ROOT / "specs/mcp/examples/remote-streamable-http.server.json").read_text(
            encoding="utf-8"
        )
    )
    assert template["schema_version"] == "okcanvas-mcp-server-v2"
    assert template["kind"] == "remote-streamable-http"
    assert template["url"] == "https://mcp.example.invalid/mcp"
