from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "okcanvas-agent-runtime"
EXAMPLE = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"


class WorkspaceStep008ShortExpressionAndReferenceFactTests(unittest.TestCase):
    def test_current_catalog_is_step008(self) -> None:
        catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
        current = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], current["workspace_step"])
        self.assertEqual(catalog["workspace_version"], current["workspace_version"])

    def test_runtime_short_expression_contract_uses_existing_agent_boundary(self) -> None:
        policy = json.loads((RUNTIME / "specs/assistant/routing-policy.json").read_text(encoding="utf-8"))
        root = json.loads((RUNTIME / "specs/agents/organization-context-session-agent/definition.json").read_text(encoding="utf-8"))
        child = json.loads((RUNTIME / "specs/agents/organization-context-read-agent/definition.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["version"], "1.5.0")
        self.assertEqual(len(policy["organization_context_short_read_rules"]), 4)
        self.assertEqual(root["agent_tools"], ["organization-context-read-agent"])
        self.assertEqual(child["mcp_servers"], ["organization-context-read"])
        self.assertEqual(root["skills"], [])
        self.assertEqual(child["skills"], [])

    def test_reference_fixture_employee_facts_are_consistent_and_exact(self) -> None:
        employees = {item["employee_id"]: item for item in json.loads((EXAMPLE / "fixtures/tenant-a/employees.json").read_text(encoding="utf-8"))}
        relations = json.loads((EXAMPLE / "fixtures/tenant-a/relations.json").read_text(encoding="utf-8"))
        self.assertEqual(len(relations), 893)
        for employee_id in ("employee-0017", "employee-0034"):
            employee = employees[employee_id]
            departments = sorted(item["to_entity_id"] for item in relations if item["from_entity_id"] == employee_id and item["relation_type"] == "EMPLOYEE_BELONGS_TO_DEPARTMENT")
            positions = sorted(item["to_entity_id"] for item in relations if item["from_entity_id"] == employee_id and item["relation_type"] == "EMPLOYEE_HAS_POSITION")
            self.assertEqual(departments, [employee["department_id"]])
            self.assertEqual(positions, sorted(employee["position_ids"]))

    def test_workspace_acceptance_executes_current_runtime_acceptance(self) -> None:
        source = (ROOT / "scripts/run_workspace_step008_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("scripts/run_step091d_acceptance.py", source)
        self.assertIn('"--output", str(runtime_output)', source)
        self.assertNotIn('STEP089_DETERMINISTIC_ACCEPTANCE.json").read_text', source)


if __name__ == "__main__":
    unittest.main()
