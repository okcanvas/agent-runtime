from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONNECTOR = ROOT / "okcanvas-connectors/organization-context-mcp-server"
EXAMPLE = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"


class WorkspaceStep005OrganizationContextTest(unittest.TestCase):
    def test_example_is_construction_guide_not_mcp(self) -> None:
        readme = (EXAMPLE / "README.md").read_text(encoding="utf-8")
        source = "\n".join(path.read_text(encoding="utf-8") for path in (EXAMPLE / "src").glob("*.ts"))
        self.assertIn("EXAMPLE_TEMPLATE_ONLY", readme)
        self.assertIn("construction", readme.lower())
        self.assertIn("NOT AN MCP SERVER", readme)
        self.assertNotIn("@modelcontextprotocol", source)
        self.assertNotIn("/tenants/", source)

    def test_product_and_fake_control_routes_are_separated(self) -> None:
        source = (EXAMPLE / "src/server.ts").read_text(encoding="utf-8")
        for route in (
            "/api/v1/glossary/resolve",
            "/api/v1/glossary/search",
            "/api/v1/glossary/catalog-state",
            "/api/v1/glossary/changes",
            "/api/v1/admin/glossary/terms",
            "/_fake/reset",
            "/_fake/seed",
            "/_fake/faults",
            "/_fake/requests",
        ):
            self.assertIn(route, source)

    def test_frequent_change_contract_is_present(self) -> None:
        source = (EXAMPLE / "src/server.ts").read_text(encoding="utf-8")
        state = (EXAMPLE / "src/state.ts").read_text(encoding="utf-8")
        self.assertIn("catalog_revision", state)
        self.assertIn("appendChange", state)
        self.assertIn("row_version_conflict", source)
        self.assertIn('term.status = "RETIRED"', source)
        self.assertIn("change_seq", state)

    def test_connector_is_read_only_and_example_independent(self) -> None:
        binding = json.loads((CONNECTOR / "contracts/connector-binding-contract.json").read_text(encoding="utf-8"))
        self.assertTrue(binding["read_only"])
        self.assertFalse(binding["fake_mode_allowed"])
        self.assertEqual(len(binding["tool_names"]), 8)
        self.assertNotIn("create_organization_term", binding["tool_names"])
        product_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (CONNECTOR / "organization_context_mcp_server").rglob("*.py")
        )
        self.assertNotIn("organization-context-api-fake", product_source)
        self.assertNotIn("FAKE_MODE", product_source)

    def test_runtime_wiring_contract_is_now_aligned(self) -> None:
        runtime_contract = json.loads((CONNECTOR / "contracts/runtime-provider-contract.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime_contract["pre_routing_integration"], "IMPLEMENTED_RUNTIME_POLICY_CALL")
        self.assertEqual(runtime_contract["agent_grounding_integration"], "IMPLEMENTED_STATELESS_CHILD_MCP")
        contracts = {item["id"]: item for item in json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]}
        self.assertTrue(contracts["runtime-organization-context-connector"]["implemented"])

    def test_step005_launchers_exist(self) -> None:
        self.assertTrue((ROOT / "scripts/run_workspace_step005r1_acceptance.py").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step005r1_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step005_acceptance.cmd").is_file())


if __name__ == "__main__":
    unittest.main()
