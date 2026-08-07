from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "okcanvas-agent-runtime"


class WorkspaceStep007OrganizationContextRuntimeLiveReadinessTests(unittest.TestCase):
    def test_step007_identity_and_runtime_parent_are_exact(self) -> None:
        catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
        current = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], current["workspace_step"])
        self.assertEqual(catalog["workspace_version"], current["workspace_version"])
        runtime = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")
        self.assertEqual(runtime["baseline"], "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE")
        self.assertEqual(runtime["version"], "2.75.0")

    def test_dedicated_session_root_child_and_mcp_are_exact(self) -> None:
        root = json.loads((RUNTIME / "specs/agents/organization-context-session-agent/definition.json").read_text(encoding="utf-8"))
        child = json.loads((RUNTIME / "specs/agents/organization-context-read-agent/definition.json").read_text(encoding="utf-8"))
        server = json.loads((RUNTIME / "specs/mcp/servers/organization-context-read/server.json").read_text(encoding="utf-8"))
        self.assertEqual(root["session_mode"], "sqlite-v1")
        self.assertEqual(root["agent_tools"], ["organization-context-read-agent"])
        self.assertEqual(child["session_mode"], "disabled")
        self.assertEqual(child["mcp_servers"], ["organization-context-read"])
        self.assertEqual(server["credential_ref"], "organization-context-read-credential")
        self.assertEqual(len(server["allowed_tools"]), 3)

    def test_runtime_contract_is_implemented_read_only_and_database_sot(self) -> None:
        contracts = {item["id"]: item for item in json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]}
        contract = contracts["runtime-organization-context-connector"]
        self.assertTrue(contract["implemented"])
        self.assertEqual(contract["root_agent_id"], "organization-context-session-agent")
        self.assertEqual(contract["child_agent_id"], "organization-context-read-agent")
        self.assertEqual(contract["child_session"], "NONE")
        self.assertEqual(contract["production_source_of_truth"], "DATABASE")
        self.assertFalse(contract["write_enabled"])

    def test_live_harness_uses_actual_runtime_connector_example_and_cli(self) -> None:
        source = (ROOT / "scripts/run_workspace_step007r1_live_acceptance.py").read_text(encoding="utf-8")
        for token in (
            "organization_context_mcp_server",
            "create_runtime_app",
            "src/cli.mjs",
            "--session-id",
            "organization-context-session-agent",
            "organization-context-read/server.json",
            "/api/v1/context/resolve",
            "employee-0017",
            "NEEDS_CLARIFICATION",
        ):
            self.assertIn(token, source)
        self.assertIn("example-organization-context-api-token", source)
        self.assertIn("OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER", source)

    def test_live_and_deterministic_launchers_are_present_and_root_guarded(self) -> None:
        for name in ("sh_run_workspace_step007r1_acceptance.cmd", "sh_run_workspace_step007r1_live_acceptance.cmd"):
            path = ROOT / name
            self.assertTrue(path.is_file())
            source = path.read_text(encoding="utf-8")
            self.assertIn("cd /d", source)
            self.assertIn("okcanvas-agent-runtime\\.venv\\Scripts\\python.exe", source)

    def test_live_environment_loader_command_is_registered(self) -> None:
        source = (RUNTIME / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
        self.assertIn("workspace-step007r1-live-acceptance", source)
        self.assertIn("OKCANVAS_WORKSPACE_STEP007R1_LIVE_ACCEPTANCE", source)
        self.assertIn("run_workspace_step007r1_live_acceptance.py", source)

    def test_step006_and_step004r2_windows_parents_are_retained(self) -> None:
        deterministic = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP006_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
        live = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP004R2_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
        self.assertEqual(deterministic["state"], "PASSED")
        self.assertEqual(deterministic["passed_checks"], 27)
        self.assertEqual(live["state"], "PASSED")
        self.assertEqual(live["live"]["passed_checks"], 22)

    def test_step084_local_catalog_is_retained_as_fallback(self) -> None:
        self.assertTrue((RUNTIME / "specs/organization/manifest.json").is_file())
        self.assertTrue((RUNTIME / "specs/organization/glossary.json").is_file())


if __name__ == "__main__":
    unittest.main()
