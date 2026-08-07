from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogError, ReferenceCatalogService

_MAX_SEARCH_RESULTS = 8
_MAX_READ_LINES = 80


class MCPToolServiceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ReferenceCatalogMCPTools:
    """Bounded read-only MCP Tool facade over the STEP006 reference service."""

    def __init__(self, project_root: str | Path, *, max_result_chars: int = 24_000) -> None:
        self._service = ReferenceCatalogService(project_root)
        self._max_result_chars = max_result_chars

    def search_reference(
        self,
        query: str,
        reference_ids: list[str] | None = None,
        max_results: int = 8,
    ) -> str:
        if not 1 <= max_results <= _MAX_SEARCH_RESULTS:
            raise MCPToolServiceError(
                "MCP_RESULT_LIMIT_INVALID",
                f"max_results must be between 1 and {_MAX_SEARCH_RESULTS}",
            )
        try:
            result = self._service.search(
                query,
                reference_ids=tuple(reference_ids) if reference_ids else None,
                max_results=max_results,
                max_file_bytes=524_288,
                max_matches_per_file=2,
            )
        except ReferenceCatalogError as exc:
            raise MCPToolServiceError(exc.code, str(exc)) from exc
        return self._serialize(
            {
                "schema_version": "okcanvas-reference-mcp-search-v1",
                "read_only": True,
                "result": result.to_dict(),
            }
        )

    def read_reference_file(
        self,
        reference_id: str,
        path: str,
        start_line: int,
        end_line: int,
    ) -> str:
        requested = end_line - start_line + 1
        if requested < 1 or requested > _MAX_READ_LINES:
            raise MCPToolServiceError(
                "MCP_RESULT_LIMIT_INVALID",
                f"Requested line range must contain 1..{_MAX_READ_LINES} lines",
            )
        try:
            result = self._service.read_lines(
                reference_id,
                path,
                start_line=start_line,
                end_line=end_line,
                max_lines=_MAX_READ_LINES,
                max_file_bytes=1_048_576,
            )
        except ReferenceCatalogError as exc:
            raise MCPToolServiceError(exc.code, str(exc)) from exc
        return self._serialize(
            {
                "schema_version": "okcanvas-reference-mcp-read-v1",
                "read_only": True,
                "result": result.to_dict(),
            }
        )

    def _serialize(self, payload: dict[str, Any]) -> str:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if len(text) > self._max_result_chars:
            raise MCPToolServiceError(
                "MCP_RESULT_TOO_LARGE",
                f"Tool result exceeds {self._max_result_chars} characters",
            )
        return text


def build_fastmcp(project_root: str | Path, *, max_result_chars: int = 24_000):
    try:
        from mcp.server.fastmcp import FastMCP
    except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover - live dependency boundary
        raise RuntimeError("mcp>=1.19,<2 is required to start the Reference Catalog server") from exc

    tools = ReferenceCatalogMCPTools(project_root, max_result_chars=max_result_chars)
    server = FastMCP("OKCanvas Read-only Reference Catalog")

    @server.tool()
    def search_reference(
        query: str,
        reference_ids: list[str] | None = None,
        max_results: int = 8,
    ) -> str:
        """Search immutable reference source using the code map first. Read-only."""
        return tools.search_reference(query, reference_ids, max_results)

    @server.tool()
    def read_reference_file(
        reference_id: str,
        path: str,
        start_line: int,
        end_line: int,
    ) -> str:
        """Read an exact bounded line range from one immutable reference file. Read-only."""
        return tools.read_reference_file(reference_id, path, start_line, end_line)

    return server


def main() -> int:
    project_root = os.getenv("OKCANVAS_PROJECT_ROOT")
    if not project_root:
        raise RuntimeError("OKCANVAS_PROJECT_ROOT is required")
    max_chars = int(os.getenv("OKCANVAS_REFERENCE_MCP_MAX_RESULT_CHARS", "24000"))
    build_fastmcp(project_root, max_result_chars=max_chars).run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
