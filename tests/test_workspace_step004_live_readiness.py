from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.workspace_inventory import excluded_package_path, excluded_workspace_path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "okcanvas-agent-runtime"


class WorkspaceStep004LiveReadinessTests(unittest.TestCase):
    def test_environment_file_loader_declares_exact_openai_inputs(self) -> None:
        source = (RUNTIME / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
        self.assertIn('"OPENAI_API_KEY"', source)
        self.assertIn('"OKCANVAS_AGENT_MODEL"', source)
        self.assertIn('environment["OKCANVAS_LOCAL_ENV_SOURCE_NAME"]', source)
        self.assertIn('environment["OKCANVAS_LOCAL_ENV_LOADED_KEYS"]', source)
        self.assertIn('workspace-step004-live-acceptance', source)
        self.assertNotIn("OKCANVAS_LOCAL_ENV_VALUES", source)

    def test_live_harness_uses_actual_runtime_connector_and_node_example(self) -> None:
        source = (ROOT / "scripts/run_workspace_step004r2_live_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("create_runtime_app(", source)
        self.assertIn("create_connector_app(", source)
        self.assertIn('"dist/src/main.js"', source)
        self.assertNotIn("DeterministicGroupwareSessionGateway", source)
        self.assertNotIn("gateway=", source)

    def test_live_harness_is_explicit_opt_in_and_secret_safe(self) -> None:
        source = (ROOT / "scripts/run_workspace_step004r2_live_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("OKCANVAS_WORKSPACE_STEP004_LIVE_ACCEPTANCE", source)
        self.assertIn('"secret_values_persisted": False', source)
        self.assertIn('"raw_provider_error_persisted": False', source)
        self.assertIn("safe_failure_category", source)
        self.assertNotIn("print(api_key", source)

    def test_loopback_connector_uses_tls_and_scoped_test_ca(self) -> None:
        source = (ROOT / "scripts/run_workspace_step004r2_live_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("create_loopback_certificates", source)
        self.assertIn('"verify": str(ca_path)', source)
        self.assertIn("strict_remote_http_client_factory = original_factory", source)
        self.assertIn('scheme = "https" if ssl_certfile is not None else "http"', source)

    def test_live_turn_budgets_and_child_tool_choice_are_exact(self) -> None:
        root = json.loads((RUNTIME / "specs/agents/organization-assistant-session-agent/definition.json").read_text(encoding="utf-8"))
        child = json.loads((RUNTIME / "specs/agents/groupware-read-agent/definition.json").read_text(encoding="utf-8"))
        gateway = (RUNTIME / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(encoding="utf-8")
        self.assertEqual(root["max_turns"], 2)
        self.assertEqual(child["max_turns"], 2)
        self.assertIn('child_agent_kwargs["model_settings"] = ModelSettings(', gateway)
        self.assertIn('tool_choice="required"', gateway)
        self.assertIn('child_agent_kwargs["reset_tool_choice"] = True', gateway)

    def test_live_environment_and_mutable_evidence_are_excluded(self) -> None:
        for relative in (
            Path("okcanvas-agent-runtime/.env.local"),
            Path("okcanvas-agent-runtime/.env.local.cmd"),
            Path("docs/evidence/WORKSPACE_STEP004R2_ACCEPTANCE.json"),
            Path("docs/evidence/WORKSPACE_STEP004R2_LIVE_ACCEPTANCE.json"),
        ):
            self.assertTrue(excluded_workspace_path(relative), relative)
            self.assertTrue(excluded_package_path(relative), relative)

    def test_live_and_readiness_launchers_are_present_and_root_guarded(self) -> None:
        for name in (
            "sh_run_workspace_step004r2_acceptance.cmd",
            "sh_run_workspace_step004r2_live_acceptance.cmd",
        ):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("okcanvas-agent-cli\\package.json", source)
            self.assertIn("Workspace root is invalid", source)
        live = (ROOT / "sh_run_workspace_step004r2_live_acceptance.cmd").read_text(encoding="utf-8")
        self.assertIn("windows_entrypoint.py", live)
        self.assertIn("workspace-step004-live-acceptance", live)

    def test_step004_runner_uses_retained_runtime_evidence_without_nested_acceptance(self) -> None:
        source = (ROOT / "scripts/run_workspace_step004r2_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("STEP087R2_DETERMINISTIC_ACCEPTANCE.json", source)
        self.assertNotIn('"scripts/run_step087r2_acceptance.py"', source)

    def test_live_fake_credential_session_continuation_and_stdout_contracts_are_exact(self) -> None:
        live = (ROOT / "scripts/run_workspace_step004r2_live_acceptance.py").read_text(encoding="utf-8")
        routing = (RUNTIME / "okcanvas_agent_runtime/application/assistant_routing/service.py").read_text(encoding="utf-8")
        entrypoint = (RUNTIME / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
        policy = json.loads((RUNTIME / "specs/assistant/routing-policy.json").read_text(encoding="utf-8"))
        self.assertIn('EXAMPLE_GROUPWARE_API_TOKEN = "example-groupware-api-token"', live)
        self.assertIn("groupware_token = EXAMPLE_GROUPWARE_API_TOKEN", live)
        self.assertNotIn('random_secret("step004-groupware")', live)
        self.assertIn("session-referential-restatement-v1", routing)
        self.assertEqual(policy["version"], "1.5.0")
        self.assertIn("session_reference", policy["lexicons"])
        self.assertIn("session_restatement", policy["lexicons"])
        self.assertIn("external_refresh", policy["lexicons"])
        self.assertIn("session_item_count >= 4", live)
        self.assertIn("session_item_count % 2 == 0", live)
        self.assertNotIn('session.get("item_count") == 4', live)
        self.assertIn("file=sys.stderr", entrypoint)

    def test_real_windows_step003r2_parent_is_immutable_and_passed(self) -> None:
        payload = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP003R2_WINDOWS_DETERMINISTIC_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "PASSED")
        self.assertEqual(payload["passed_checks"], 27)
        self.assertEqual(payload["total_checks"], 27)
        self.assertTrue(payload["windows_step003r2_executed"])
        self.assertTrue(payload["windows_step003r2_accepted"])


if __name__ == "__main__":
    unittest.main()
