from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "okcanvas-agent-runtime"
CURRENT_BASELINE = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
STEP = CURRENT_BASELINE["workspace_step"]
VERSION = CURRENT_BASELINE["workspace_version"]
RUNTIME_STEP = "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
RUNTIME_VERSION = "2.75.0"
HISTORICAL_RUNTIME_STEP = "STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE"
HISTORICAL_RUNTIME_VERSION = "2.74.1"


class WorkspaceStep008R4R6PostgreSQLLiveGateTest(unittest.TestCase):
    def test_current_identity_exact(self) -> None:
        catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], STEP)
        self.assertEqual(catalog["workspace_version"], VERSION)
        runtime = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")
        self.assertEqual(runtime["baseline"], RUNTIME_STEP)
        self.assertEqual(runtime["version"], RUNTIME_VERSION)

    def test_runtime_step091b3r1_deterministic_acceptance_exact(self) -> None:
        payload = json.loads((RUNTIME / "docs/evidence/STEP091B3R1_DETERMINISTIC_ACCEPTANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["step"], HISTORICAL_RUNTIME_STEP)
        self.assertEqual(payload["version"], HISTORICAL_RUNTIME_VERSION)
        self.assertEqual(payload["state"], "PASSED")
        self.assertEqual(payload["passed_checks"], payload["total_checks"])
        self.assertEqual(payload["total_checks"], 21)
        for name in (
            "real_postgresql_live_harness_present",
            "live_dsn_requires_dedicated_environment",
            "live_schema_isolated_and_cleanup_mandatory",
            "live_admission_concurrency_and_atomicity_covered",
            "live_event_sequence_concurrency_covered",
            "live_approval_resume_fence_covered",
            "live_evaluation_round_trip_covered",
            "live_session_row_lock_and_restart_covered",
            "live_sqlite_default_retention_covered",
            "live_evidence_is_secret_safe_by_construction",
        ):
            self.assertTrue(payload["checks"][name], name)
        self.assertFalse(payload["limitations"]["real_postgresql_server_executed"])

    def test_full_runtime_partition_evidence_exact(self) -> None:
        payload = json.loads((RUNTIME / "docs/evidence/STEP091B3R1_FULL_RUNTIME_TEST_PARTITIONS.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["step"], HISTORICAL_RUNTIME_STEP)
        self.assertEqual(payload["state"], "PASSED")
        self.assertEqual(payload["collected_test_file_count"], 250)
        self.assertEqual(payload["covered_test_file_count"], 250)
        self.assertEqual(payload["unique_covered_test_file_count"], 250)
        self.assertEqual(payload["total_passed_tests"], 1044)
        self.assertEqual(payload["total_failed_tests"], 0)
        self.assertEqual(payload["total_skipped_tests"], 0)
        self.assertEqual(payload["partition_count"], 18)
        self.assertEqual(payload["completed_partition_count"], 18)
        self.assertTrue(payload["all_log_hashes_valid"])
        self.assertTrue(payload["partition_assignments_exact"])
        self.assertTrue(payload["exact_file_coverage"])
        self.assertEqual(payload["missing_files"], [])
        self.assertEqual(payload["duplicate_files"], [])

    def test_workspace_contract_exposes_bounded_live_gate(self) -> None:
        contracts = json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]
        current = next(item for item in contracts if item["id"] == "runtime-organization-context-connector")
        self.assertEqual(current["runtime_baseline"], RUNTIME_STEP)
        self.assertEqual(current["runtime_version"], RUNTIME_VERSION)
        self.assertTrue(current["postgresql_live_gate_implemented"])
        self.assertEqual(current["postgresql_live_gate"], "real-postgresql-isolated-schema-v1")
        self.assertEqual(current["postgresql_live_dsn_env"], "OKCANVAS_POSTGRESQL_LIVE_DSN")
        self.assertEqual(current["postgresql_live_confirmation_env"], "OKCANVAS_POSTGRESQL_LIVE_CONFIRM")
        self.assertEqual(current["postgresql_live_confirmation_value"], "CREATE_AND_DROP_ISOLATED_TEST_SCHEMA")
        self.assertEqual(current["postgresql_live_schema_prefix"], "okcanvas_step091b3r1_")
        self.assertTrue(current["postgresql_live_accepted"])

    def test_connector_example_server_has_bounded_non_pipe_process_io(self) -> None:
        source = (ROOT / "tests/run_organization_context_connector_example_e2e.py").read_text(encoding="utf-8")
        self.assertIn("timeout=60", source)
        self.assertIn("stdin=subprocess.DEVNULL", source)
        self.assertIn("stdout=subprocess.DEVNULL", source)
        self.assertIn("stderr=subprocess.DEVNULL", source)
        self.assertNotIn("stdout=subprocess.PIPE, stderr=subprocess.PIPE", source)

    def test_workspace_acceptance_supports_quiet_evidence_mode(self) -> None:
        source = (ROOT / "scripts/run_workspace_step008_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--quiet", action="store_true")', source)
        self.assertIn("emit_stdout=not args.quiet", source)
        self.assertIn("if emit_stdout:", source)

    def test_connector_example_aggregate_uses_file_backed_direct_child(self) -> None:
        source = (ROOT / "scripts/run_workspace_step008_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('stdout_path=temp / "organization-context-integration.stdout.log"', source)
        self.assertIn('stderr_path=temp / "organization-context-integration.stderr.log"', source)
        self.assertIn("run_process_to_files(", source)

    def test_windows_live_launcher_and_handoff_are_explicit(self) -> None:
        launcher = (RUNTIME / "sh_run_step091b3r1_postgresql_live_acceptance.cmd").read_text(encoding="utf-8")
        handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("run_step091b3r1_postgresql_live_acceptance.py", launcher)
        self.assertIn("OKCANVAS_POSTGRESQL_LIVE_DSN", handoff)
        self.assertIn("CREATE_AND_DROP_ISOLATED_TEST_SCHEMA", handoff)
        self.assertIn("PostgreSQL live server: EXECUTED / 19/19 PASSED", handoff)
        self.assertIn("Parent promoted baseline: STEP008R4R6 / STEP091B3R1", handoff)


if __name__ == "__main__":
    unittest.main()
