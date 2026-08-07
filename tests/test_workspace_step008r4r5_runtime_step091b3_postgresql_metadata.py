from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "okcanvas-agent-runtime"
CURRENT_BASELINE = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
CURRENT_STEP = CURRENT_BASELINE["workspace_step"]
CURRENT_VERSION = CURRENT_BASELINE["workspace_version"]
CURRENT_RUNTIME_STEP = "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
CURRENT_RUNTIME_VERSION = "2.75.0"
PARENT_RUNTIME_STEP = "STEP091B3_POSTGRESQL_APPROVAL_EVALUATION_AND_SESSION_METADATA"
PARENT_RUNTIME_VERSION = "2.74.0"


class WorkspaceStep008R4R5PostgreSQLMetadataTest(unittest.TestCase):
    def test_current_identity_exact(self) -> None:
        catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], CURRENT_STEP)
        self.assertEqual(catalog["workspace_version"], CURRENT_VERSION)
        runtime = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")
        self.assertEqual(runtime["baseline"], CURRENT_RUNTIME_STEP)
        self.assertEqual(runtime["version"], CURRENT_RUNTIME_VERSION)

    def test_parent_runtime_step091b3_acceptance_exact(self) -> None:
        payload = json.loads((RUNTIME / "docs/evidence/STEP091B3_DETERMINISTIC_ACCEPTANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["step"], PARENT_RUNTIME_STEP)
        self.assertEqual(payload["version"], PARENT_RUNTIME_VERSION)
        self.assertEqual(payload["state"], "PASSED")
        self.assertEqual(payload["passed_checks"], payload["total_checks"])
        self.assertEqual(payload["total_checks"], 22)
        for name in (
            "postgresql_metadata_stores_share_one_dsn",
            "postgresql_tool_approval_implemented",
            "approval_product_transaction_domain_retained",
            "postgresql_evaluation_implemented",
            "postgresql_session_metadata_implemented",
            "session_history_remains_encrypted_local_sqlite",
            "session_metadata_row_locking_present",
            "postgresql_topology_uses_metadata_stores",
            "sqlite_default_topology_retained",
        ):
            self.assertTrue(payload["checks"][name], name)

    def test_workspace_contract_retains_postgresql_metadata_scope(self) -> None:
        contracts = json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]
        current = next(item for item in contracts if item["id"] == "runtime-organization-context-connector")
        self.assertEqual(current["runtime_baseline"], CURRENT_RUNTIME_STEP)
        self.assertEqual(current["runtime_version"], CURRENT_RUNTIME_VERSION)
        self.assertTrue(current["postgresql_tool_approval_implemented"])
        self.assertTrue(current["postgresql_evaluation_implemented"])
        self.assertTrue(current["postgresql_session_metadata_implemented"])
        self.assertEqual(current["postgresql_session_metadata_backend"], "postgresql-session-metadata-v1")
        self.assertEqual(current["session_history_backend"], "encrypted-local-sqlite-history-v1")
        self.assertFalse(current["distributed_session_history_implemented"])
        self.assertTrue(current["postgresql_live_accepted"])


if __name__ == "__main__":
    unittest.main()
