from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.workspace_inventory import excluded_workspace_path, snapshot_files
RUNTIME = ROOT / "okcanvas-agent-runtime"
CLI = ROOT / "okcanvas-agent-cli"
CONNECTOR = ROOT / "okcanvas-connectors" / "groupware-mcp-server"
EXAMPLE = ROOT / "okcanvas-connector-examples" / "groupware" / "groupware-api-fake"
ORG_CONNECTOR = ROOT / "okcanvas-connectors" / "organization-context-mcp-server"
ORG_EXAMPLE = ROOT / "okcanvas-connector-examples" / "organization-context" / "organization-context-api-fake"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))



class WorkspaceStructureTest(unittest.TestCase):
    def test_required_sibling_projects_exist(self) -> None:
        required = {
            "docs", "reference", "scripts", "specs", "tests",
            "okcanvas-agent-runtime", "okcanvas-agent-cli",
            "okcanvas-connectors", "okcanvas-connector-examples",
        }
        self.assertTrue(required.issubset({path.name for path in ROOT.iterdir() if path.is_dir()}))
        self.assertTrue((RUNTIME / "pyproject.toml").is_file())
        self.assertTrue((CONNECTOR / "pyproject.toml").is_file())
        self.assertTrue((CLI / "package.json").is_file())
        self.assertTrue((EXAMPLE / "package.json").is_file())
        self.assertTrue((ORG_CONNECTOR / "pyproject.toml").is_file())
        self.assertTrue((ORG_EXAMPLE / "package.json").is_file())

    def test_runtime_does_not_contain_connector_projects(self) -> None:
        self.assertFalse((RUNTIME / "okcanvas-connectors").exists())
        self.assertFalse((RUNTIME / "okcanvas-connector-examples").exists())

    def test_workspace_root_has_no_shared_environment(self) -> None:
        self.assertFalse((ROOT / ".venv").exists())
        self.assertFalse((ROOT / "node_modules").exists())

    def test_parent_project_files_are_byte_identical(self) -> None:
        manifests = [
            ROOT / "reference/parent-file-manifests/okcanvas-agent-runtime.json",
            ROOT / "reference/parent-file-manifests/okcanvas-connectors__groupware-mcp-server.json",
            ROOT / "reference/parent-file-manifests/okcanvas-connector-examples__groupware__groupware-api-fake.json",
            ROOT / "reference/parent-file-manifests/okcanvas-connectors__organization-context-mcp-server.json",
            ROOT / "reference/parent-file-manifests/okcanvas-connector-examples__organization-context__organization-context-api-fake.json",
        ]
        for manifest_path in manifests:
            manifest = read_json(manifest_path)
            base = ROOT / str(manifest["project_path"])
            expected = {
                str(item["path"]): (str(item["sha256"]), int(item["size"]))
                for item in manifest["files"]
            }
            self.assertEqual(snapshot_files(base), expected, manifest_path.name)
            self.assertEqual(len(expected), int(manifest["file_count"]))

    def test_runtime_and_connector_provider_contracts_are_byte_identical(self) -> None:
        runtime_contract = RUNTIME / "specs/groupware/read-provider-contract.json"
        connector_contract = CONNECTOR / "contracts/runtime-provider-contract.json"
        self.assertEqual(runtime_contract.read_bytes(), connector_contract.read_bytes())

    def test_cross_project_source_imports_are_absent(self) -> None:
        runtime_source = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (RUNTIME / "okcanvas_agent_runtime").rglob("*.py")
        )
        connector_source = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (CONNECTOR / "groupware_mcp_server").rglob("*.py")
        )
        cli_source = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (CLI / "src").rglob("*") if path.is_file()
        )
        example_source = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (EXAMPLE / "src").rglob("*") if path.is_file()
        )
        self.assertNotIn("groupware_mcp_server", runtime_source)
        self.assertNotIn("okcanvas_agent_runtime", connector_source)
        self.assertNotIn("okcanvas_agent_runtime", cli_source)
        self.assertNotIn("groupware_mcp_server", cli_source)
        self.assertNotIn("@modelcontextprotocol", example_source)

    def test_product_cli_is_product_ready_and_service_api_only(self) -> None:
        contract = read_json(CLI / "specs/service-cli-boundary.json")
        self.assertEqual(contract["implementation_state"], "PRODUCT_READY")
        self.assertTrue(contract["request_execution_implemented"])
        self.assertTrue(contract["session_execution_implemented"])
        self.assertTrue(contract["automatic_assistant_routing"])
        self.assertEqual(contract["durable_event_stream"], "PERSISTED_SSE")
        self.assertEqual(contract["api_prefix"], "/v1/service/")
        self.assertEqual(contract["authority"], "EXTERNAL_BEARER")


    def test_product_cli_entrypoint_and_workspace_launcher_exist(self) -> None:
        self.assertTrue((CLI / "src/cli.mjs").is_file())
        self.assertTrue((CLI / "sh_run_cli.cmd").is_file())
        self.assertTrue((ROOT / "sh_run_agent_cli.cmd").is_file())
        package = read_json(CLI / "package.json")
        self.assertEqual(package["version"], "0.2.1")
        self.assertEqual(package["bin"]["okcanvas-agent"], "src/cli.mjs")

    def test_product_cli_acceptance_is_windows_path_space_safe(self) -> None:
        source = (CLI / "scripts/run-acceptance.mjs").read_text(encoding="utf-8")
        self.assertIn("shell: false", source)
        self.assertIn("...testFiles", source)
        self.assertNotIn("test/*.test.mjs", source)
        self.assertNotIn("shell: process.platform", source)

    def test_connector_optional_example_default_resolves_as_sibling(self) -> None:
        script = (CONNECTOR / "scripts/run_optional_example_integration.py").read_text(encoding="utf-8")
        self.assertIn('ROOT.parents[1]', script)
        self.assertIn('"okcanvas-connector-examples"', script)
        self.assertTrue(EXAMPLE.is_dir())

    def test_example_remains_optional_and_not_mcp(self) -> None:
        deployment = read_json(RUNTIME / "specs/groupware/deployment-boundary.json")
        self.assertFalse(deployment["connector_examples_required"])
        self.assertFalse(deployment["groupware_api_fake_is_mcp_server"])
        self.assertEqual(
            deployment["groupware_api_fake_example_path"],
            "okcanvas-connector-examples/groupware/groupware-api-fake",
        )


    def test_current_workspace_catalog_and_integration_contracts_are_exact(self) -> None:
        catalog = read_json(ROOT / "specs/workspace/project-catalog.json")
        current = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], current["workspace_step"])
        self.assertEqual(catalog["workspace_version"], current["workspace_version"])
        runtime = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")
        self.assertEqual(runtime["baseline"], current["runtime_step"])
        self.assertEqual(runtime["version"], current["runtime_version"])
        contracts = {item["id"]: item for item in read_json(ROOT / "specs/workspace/integration-contracts.json")["contracts"]}
        self.assertTrue(contracts["service-cli-runtime"]["implemented"])
        delegation = contracts["runtime-main-assistant-groupware-subagent"]
        self.assertTrue(delegation["implemented"])
        self.assertEqual(delegation["protocol"], "AGENT_AS_TOOL")
        self.assertEqual(delegation["root_agent_id"], "organization-assistant-session-agent")
        self.assertEqual(delegation["child_agent_id"], "groupware-read-agent")
        self.assertEqual(delegation["child_session"], "NONE")
        self.assertFalse(delegation["write_enabled"])
        organization_connector = next(item for item in catalog["projects"] if item["project_id"] == "organization-context-mcp-connector")
        self.assertEqual(organization_connector["version"], "0.3.0")
        organization_example = next(item for item in catalog["projects"] if item["project_id"] == "organization-context-api-fake-example")
        self.assertEqual(organization_example["version"], "0.3.0")
        self.assertFalse(organization_example["production"])
        self.assertTrue(contracts["runtime-organization-context-connector"]["implemented"])
        self.assertTrue(contracts["connector-organization-context-api"]["implemented"])
        self.assertTrue(contracts["connector-example-organization-context-api"]["construction_guide"])

    def test_step004_retains_delegation_and_adds_live_readiness_entrypoints(self) -> None:
        policy = read_json(RUNTIME / "specs/groupware/session-delegation-policy.json")
        definition = read_json(RUNTIME / "specs/agents/organization-assistant-session-agent/definition.json")
        self.assertEqual(policy["root_agent_id"], "organization-assistant-session-agent")
        self.assertEqual(policy["child_agent_id"], "groupware-read-agent")
        self.assertEqual(policy["child_session_mode"], "disabled")
        self.assertEqual(policy["max_agent_tool_calls_per_turn"], 1)
        self.assertFalse(policy["write_enabled"])
        self.assertIn("groupware-read-agent", definition["agent_tools"])
        self.assertTrue((ROOT / "tests/run_main_assistant_groupware_subagent_e2e.py").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step003_acceptance.py").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step003_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step003r1_acceptance.py").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step003r1_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step003r2_acceptance.py").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step003r2_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step004_acceptance.py").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step004_live_acceptance.py").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step004_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step004_live_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step004r1_acceptance.py").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step004r1_live_acceptance.py").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step004r2_acceptance.py").is_file())
        self.assertTrue((ROOT / "scripts/run_workspace_step004r2_live_acceptance.py").is_file())
        self.assertTrue((ROOT / "scripts/workspace_python_bytecode_isolation.py").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step004r1_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step004r1_live_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step004r2_acceptance.cmd").is_file())
        self.assertTrue((ROOT / "sh_run_workspace_step004r2_live_acceptance.cmd").is_file())
        self.assertEqual(definition["max_turns"], 2)
        child = read_json(RUNTIME / "specs/agents/groupware-read-agent/definition.json")
        self.assertEqual(child["max_turns"], 2)

    def test_workspace_manifest_is_current(self) -> None:
        manifest = read_json(ROOT / "WORKSPACE_MANIFEST.json")
        expected = {
            str(item["path"]): (str(item["sha256"]), int(item["size"]))
            for item in manifest["files"]
        }
        actual = snapshot_files(ROOT, workspace=True)
        self.assertEqual(actual, expected)
        self.assertEqual(len(expected), int(manifest["file_count"]))

    def test_independent_environment_boundaries_are_declared(self) -> None:
        catalog = read_json(ROOT / "specs/workspace/project-catalog.json")
        environments = {item["project_id"]: item["environment"] for item in catalog["projects"]}
        self.assertEqual(environments["agent-runtime"], ".venv")
        self.assertEqual(environments["groupware-mcp-connector"], ".venv")
        self.assertEqual(environments["agent-service-cli"], "node_modules")
        self.assertEqual(environments["groupware-api-fake-example"], "node_modules")
        self.assertEqual(environments["organization-context-mcp-connector"], ".venv")
        self.assertEqual(environments["organization-context-api-fake-example"], "node_modules")


if __name__ == "__main__":
    unittest.main()
