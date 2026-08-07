from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"
CONNECTOR = ROOT / "okcanvas-connectors/organization-context-mcp-server"


class WorkspaceStep006OrganizationContextDatasetTests(unittest.TestCase):
    def test_step006_windows_parent_is_retained(self) -> None:
        summary = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP006_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["step"], "WORKSPACE_STEP006_ORGANIZATION_CONTEXT_JSON_REFERENCE_DATASET_AND_UNIFIED_RESOLUTION_FOUNDATION")
        self.assertEqual(summary["version"], "0.6.0")
        self.assertEqual(summary["state"], "PASSED")
        self.assertEqual(summary["passed_checks"], 27)

    def test_json_fixture_manifest_declares_db_and_example_sot(self) -> None:
        manifest = json.loads((EXAMPLE / "fixtures/tenant-a/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["production_sot"], "DATABASE")
        self.assertEqual(manifest["example_sot"], "COMMITTED_JSON_FIXTURES")
        self.assertEqual(manifest["expected_counts"]["departments"], 13)
        self.assertEqual(manifest["expected_counts"]["positions"], 12)
        self.assertEqual(manifest["expected_counts"]["employees"], 48)
        self.assertEqual(manifest["expected_counts"]["products"], 120)
        self.assertEqual(manifest["expected_counts"]["clients"], 120)
        self.assertEqual(manifest["expected_counts"]["glossary"], 80)
        self.assertGreaterEqual(manifest["expected_counts"]["relations_minimum"], 200)

    def test_committed_json_fixture_counts_are_exact(self) -> None:
        expected = {"departments": 13, "positions": 12, "employees": 48, "products": 120, "clients": 120, "glossary": 80, "projects": 24, "systems": 10, "capabilities": 30, "relations": 893}
        for name, count in expected.items():
            records = json.loads((EXAMPLE / f"fixtures/tenant-a/{name}.json").read_text(encoding="utf-8"))
            self.assertEqual(len(records), count, name)

    def test_fixture_loader_validates_references_instead_of_hardcoding_seed(self) -> None:
        state = (EXAMPLE / "src/state.ts").read_text(encoding="utf-8")
        loader = (EXAMPLE / "src/fixture-loader.ts").read_text(encoding="utf-8")
        self.assertIn("loadReferenceDatasets", state)
        self.assertNotIn("function seedTerms", state)
        self.assertIn("production_sot", loader)
        self.assertIn("cross-tenant record detected", loader)
        self.assertIn("relation", loader)

    def test_unified_api_and_legacy_glossary_api_coexist(self) -> None:
        server = (EXAMPLE / "src/server.ts").read_text(encoding="utf-8")
        for path in ("/api/v1/context/resolve", "/api/v1/context/search", "/api/v1/context/entities/", "/api/v1/glossary/resolve", "/api/v1/glossary/search"):
            self.assertIn(path, server)

    def test_connector_has_exactly_eight_read_only_tools(self) -> None:
        binding = json.loads((CONNECTOR / "contracts/connector-binding-contract.json").read_text(encoding="utf-8"))
        self.assertEqual(len(binding["tool_names"]), 8)
        self.assertEqual(binding["tool_names"][:3], ["resolve_organization_context", "search_organization_context", "get_organization_entity"])
        self.assertTrue(binding["read_only"])
        self.assertEqual(binding["production_source_of_truth"], "DATABASE")
        self.assertFalse(binding["fake_mode_allowed"])

    def test_step006_deferred_boundary_is_superseded_by_step007(self) -> None:
        contracts = {item["id"]: item for item in json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]}
        runtime_contract = contracts["runtime-organization-context-connector"]
        self.assertTrue(runtime_contract["implemented"])
        self.assertEqual(runtime_contract["production_source_of_truth"], "DATABASE")
        self.assertFalse(runtime_contract["write_enabled"])

    def test_step006_launcher_exists(self) -> None:
        self.assertTrue((ROOT / "sh_run_workspace_step006_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step006_acceptance.py").is_file())


if __name__ == "__main__":
    unittest.main()
