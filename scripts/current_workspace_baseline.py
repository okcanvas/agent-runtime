from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "specs/workspace/current-baseline.json"


@dataclass(frozen=True)
class CurrentWorkspaceBaseline:
    workspace_step: str
    workspace_version: str
    runtime_step: str
    runtime_version: str
    current_documents: tuple[str, ...]
    state: str
    promotion: str


def load_current_baseline(root: Path = ROOT) -> CurrentWorkspaceBaseline:
    path = root / "specs/workspace/current-baseline.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = (
        "workspace_step",
        "workspace_version",
        "runtime_step",
        "runtime_version",
        "current_documents",
        "state",
        "promotion",
    )
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f"current baseline missing required fields: {missing}")
    documents = payload["current_documents"]
    if not isinstance(documents, list) or not documents or not all(isinstance(item, str) and item for item in documents):
        raise ValueError("current baseline current_documents must be a non-empty string list")
    return CurrentWorkspaceBaseline(
        workspace_step=str(payload["workspace_step"]),
        workspace_version=str(payload["workspace_version"]),
        runtime_step=str(payload["runtime_step"]),
        runtime_version=str(payload["runtime_version"]),
        current_documents=tuple(documents),
        state=str(payload["state"]),
        promotion=str(payload["promotion"]),
    )


def assert_catalog_matches_current_baseline(root: Path = ROOT) -> None:
    baseline = load_current_baseline(root)
    catalog = json.loads((root / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
    if catalog.get("workspace_step") != baseline.workspace_step:
        raise ValueError("project catalog workspace_step differs from current baseline SOT")
    if catalog.get("workspace_version") != baseline.workspace_version:
        raise ValueError("project catalog workspace_version differs from current baseline SOT")
    runtime = next((item for item in catalog.get("projects", []) if item.get("project_id") == "agent-runtime"), None)
    if runtime is None:
        raise ValueError("project catalog has no agent-runtime project")
    if runtime.get("baseline") != baseline.runtime_step:
        raise ValueError("project catalog Runtime baseline differs from current baseline SOT")
    if runtime.get("version") != baseline.runtime_version:
        raise ValueError("project catalog Runtime version differs from current baseline SOT")
