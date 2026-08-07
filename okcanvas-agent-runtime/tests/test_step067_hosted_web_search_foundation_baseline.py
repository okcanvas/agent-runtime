from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.tools.hosted_search import HostedWebSearchPolicyCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step067_runtime_flags_and_baseline_are_exact() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.remote_mcp_streamable_http_windows_live_accepted is True
    assert info.hosted_web_search_implemented is True
    assert info.hosted_web_search_mode == "single-fixed-domain-source-policy-and-evidence"
    assert info.hosted_web_search_tool_id == "web-search-v1"
    assert info.hosted_web_search_allowed_domains == "developers.openai.com"
    assert info.hosted_web_search_max_calls == 1
    assert info.hosted_web_search_max_sources == 8
    assert info.hosted_web_search_max_citations == 8
    assert info.hosted_web_search_store_enabled is False
    assert info.hosted_web_search_evidence_artifact_implemented is True
    assert info.hosted_file_search_implemented is False
    assert info.hosted_web_search_deterministic_accepted is True
    assert info.hosted_web_search_windows_live_accepted is True
    assert info.hosted_web_search_live_provider_accepted is False


def test_step067_policy_and_agent_are_single_web_search_only() -> None:
    policy = HostedWebSearchPolicyCatalog(ROOT).resolve()
    definition = AgentDefinitionCatalog(ROOT).resolve("hosted-web-search-agent")
    assert policy.policy_id == "official-openai-docs-web-search-v1"
    assert policy.tool_id == "web-search-v1"
    assert policy.allowed_domains == ("developers.openai.com",)
    assert definition.hosted_tools == ("web-search-v1",)
    assert definition.output_contract == "HostedWebSearchResult"
    assert definition.max_turns == 2
    assert definition.session_mode == "disabled"


def test_step067_roadmap_separates_file_search_resource_lifecycle() -> None:
    roadmap = (ROOT / "docs/plans/ROADMAP.md").read_text(encoding="utf-8")
    assert "STEP068 bounded local PDF/PNG/JPEG input is Windows-live accepted" in roadmap
    assert "Hosted File Search remains post-MVP" in roadmap
    assert "consume bounded document input" in roadmap or "bounded local PDF/PNG/JPEG input" in roadmap
    assert "STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1" in roadmap
    decision = json.loads(
        (ROOT / "docs/evidence/STEP067_FILE_SEARCH_SCOPE_SEPARATION.json").read_text(
            encoding="utf-8"
        )
    )
    assert decision["decision"] == "SEPARATE_WEB_SEARCH_FROM_FILE_SEARCH"
    assert decision["step067_includes"] == ["WebSearchTool"]
    assert decision["step067_excludes"] == ["FileSearchTool", "vector-store-lifecycle"]


def test_step067_contract_forbids_raw_search_material() -> None:
    contract = (ROOT / "specs/hosted_tools/contracts/HOSTED_WEB_SEARCH_V1.md").read_text(
        encoding="utf-8"
    )
    assert "raw query" in contract
    assert "raw result content" in contract
    assert "provider call ID" in contract
    assert "agent.hosted-search-evidence" in contract
    assert "File Search" in contract
