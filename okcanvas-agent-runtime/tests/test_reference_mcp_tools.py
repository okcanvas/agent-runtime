from __future__ import annotations

import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.adapters.mcp.servers.reference_catalog import (
    MCPToolServiceError,
    ReferenceCatalogMCPTools,
)

ROOT = Path(__file__).resolve().parents[1]


def test_search_and_read_are_bounded_and_read_only() -> None:
    tools = ReferenceCatalogMCPTools(ROOT)
    before = (ROOT / "reference/MANIFEST.json").read_bytes()
    search = json.loads(tools.search_reference("RunState", ["openai-agents-python"], 4))
    assert search["read_only"] is True
    matches = search["result"]["matches"]
    assert matches
    assert any(item["relative_path"] == "src/agents/run_state.py" for item in matches)
    read = json.loads(
        tools.read_reference_file(
            "openai-agents-python",
            "src/agents/run_state.py",
            1,
            20,
        )
    )
    assert read["read_only"] is True
    assert len(read["result"]["lines"]) == 20
    assert (ROOT / "reference/MANIFEST.json").read_bytes() == before


def test_search_result_and_read_line_limits_are_enforced() -> None:
    tools = ReferenceCatalogMCPTools(ROOT)
    with pytest.raises(MCPToolServiceError) as too_many:
        tools.search_reference("RunState", max_results=9)
    assert too_many.value.code == "MCP_RESULT_LIMIT_INVALID"
    with pytest.raises(MCPToolServiceError):
        tools.read_reference_file(
            "openai-agents-python",
            "src/agents/run_state.py",
            1,
            81,
        )


def test_result_character_limit_is_fail_closed() -> None:
    tools = ReferenceCatalogMCPTools(ROOT, max_result_chars=200)
    with pytest.raises(MCPToolServiceError) as error:
        tools.read_reference_file(
            "openai-agents-python",
            "src/agents/run_state.py",
            1,
            20,
        )
    assert error.value.code == "MCP_RESULT_TOO_LARGE"
