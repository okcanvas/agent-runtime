from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_BASELINE = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
STEP = CURRENT_BASELINE["workspace_step"]
VERSION = CURRENT_BASELINE["workspace_version"]
RUNTIME_STEP = "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"


def test_workspace_step008r4r7_selects_object_storage_deployment_after_read_only_audit() -> None:
    audit = (ROOT / "docs/audits/WORKSPACE_STEP008R4R7_NEXT_BOUNDARY_READ_ONLY_AUDIT.md").read_text(encoding="utf-8")
    assert "READ_ONLY" in audit
    assert "Object Storage deployment composition + explicit real-server Live acceptance gate" in audit
    assert "Artifact orphan inventory/GC remains next-after-live candidate" in audit


def test_workspace_step008r4r7_catalog_and_contract_match_runtime_step091d() -> None:
    catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
    assert catalog["workspace_step"] == STEP
    assert catalog["workspace_version"] == VERSION
    runtime = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")
    assert runtime["baseline"] == RUNTIME_STEP
    assert runtime["version"] == "2.75.0"
    contracts = json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))
    contract = next(item for item in contracts["contracts"] if item["id"] == "runtime-organization-context-connector")
    assert contract["artifact_object_storage_environment_composition"] is True
    assert contract["artifact_object_storage_live_gate_implemented"] is True
    assert contract["artifact_object_storage_live_accepted"] is False
