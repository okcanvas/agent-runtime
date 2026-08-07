from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "okcanvas-agent-runtime"
CONNECTOR = ROOT / "okcanvas-connectors/organization-context-mcp-server"
EXAMPLE = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"


class WorkspaceStep007R1BoundedResponseTests(unittest.TestCase):
    def test_current_identity_is_exact(self) -> None:
        catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
        current = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], current["workspace_step"])
        self.assertEqual(catalog["workspace_version"], current["workspace_version"])

    def test_runtime_keeps_fixed_mcp_budget_and_safe_diagnostic(self) -> None:
        server = json.loads((RUNTIME / "specs/mcp/servers/organization-context-read/server.json").read_text(encoding="utf-8"))
        self.assertEqual(server["max_result_chars"], 32000)
        gateway = (RUNTIME / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(encoding="utf-8")
        for token in ("MCP_RESULT_LIMIT_EXCEEDED", "okcanvas-mcp-tool-failed-v1", "tool_arguments_persisted", "tool_result_persisted", "raw_error_persisted"):
            self.assertIn(token, gateway)

    def test_example_resolve_and_search_shapes_are_bounded(self) -> None:
        source = (EXAMPLE / "src/context-resolver.ts").read_text(encoding="utf-8")
        self.assertIn('response_shape: "TOP_SCORE_CANDIDATES_WITH_DETAILS"', source)
        self.assertIn('response_shape: "RANKED_ENTITY_SUMMARIES"', source)
        self.assertIn("Math.max(1, Math.min(limit, 20))", source)

    def test_connector_propagates_bounded_metadata(self) -> None:
        source = (CONNECTOR / "organization_context_mcp_server/service.py").read_text(encoding="utf-8")
        for token in ("response_shape", "candidate_count", "returned_count", "truncated"):
            self.assertIn(token, source)

    def test_live_runner_retains_safe_failure_diagnostics_only(self) -> None:
        source = (ROOT / "scripts/run_workspace_step007r1_live_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("safe_tool_failures", source)
        self.assertIn("allowed_failure_keys", source)
        self.assertIn('"raw_tool_arguments_persisted": False', source)
        self.assertIn('"raw_tool_results_persisted": False', source)
        self.assertIn('"raw_error_persisted": False', source)

    def test_step007_compatibility_launchers_delegate_to_r1(self) -> None:
        self.assertIn("call sh_run_workspace_step007r1_acceptance.cmd %*", (ROOT / "sh_run_workspace_step007_acceptance.cmd").read_text(encoding="utf-8"))
        self.assertIn("call sh_run_workspace_step007r1_live_acceptance.cmd %*", (ROOT / "sh_run_workspace_step007_live_acceptance.cmd").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
