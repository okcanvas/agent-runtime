from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from scripts.current_workspace_baseline import load_current_baseline
from scripts.validate_current_document_sot import validate_current_documents

ROOT = Path(__file__).resolve().parents[1]


def test_current_baseline_catalog_and_runtime_identity_are_exact() -> None:
    baseline = load_current_baseline(ROOT)
    catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
    assert catalog["workspace_step"] == baseline.workspace_step
    assert catalog["workspace_version"] == baseline.workspace_version
    runtime = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")
    assert runtime["baseline"] == baseline.runtime_step
    assert runtime["version"] == baseline.runtime_version
    assert "okcanvas-agent-runtime/PLANS.md" in baseline.current_documents


def test_each_current_document_matches_sot_independently() -> None:
    assert validate_current_documents(ROOT) == []


def test_stale_nested_runtime_plan_fails_closed_even_when_siblings_are_current() -> None:
    baseline = load_current_baseline(ROOT)
    with tempfile.TemporaryDirectory(prefix="okcanvas-current-sot-") as temp_dir:
        temp_root = Path(temp_dir)
        for relative in baseline.current_documents:
            source = ROOT / relative
            target = temp_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        stale = temp_root / "okcanvas-agent-runtime/PLANS.md"
        text = stale.read_text(encoding="utf-8")
        text = text.replace(
            f"Current Runtime: {baseline.runtime_step}",
            "Current Runtime: STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE",
            1,
        )
        stale.write_text(text, encoding="utf-8")
        errors = validate_current_documents(temp_root, baseline=baseline)
        assert errors
        assert any("okcanvas-agent-runtime/PLANS.md" in item for item in errors)
        assert any("Current Runtime" in item for item in errors)
