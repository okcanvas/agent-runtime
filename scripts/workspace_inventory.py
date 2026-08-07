from __future__ import annotations

import hashlib
from pathlib import Path

MUTABLE_ACCEPTANCE_EVIDENCE = {
    "docs/evidence/WORKSPACE_STEP001_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP001R1_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP001R2_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP001R3_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP002_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP002R1_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP003_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP003R1_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP003R2_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP004_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP004_LIVE_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP004R1_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP004R1_LIVE_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP004R2_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP004R2_LIVE_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP005_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP005R1_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP006_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP007_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP007_LIVE_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP007R1_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP007R1_LIVE_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R1_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R2_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R3_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R4_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R4R1_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R4R3_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R4R5_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R4R6_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R4R7_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008R4R7A_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP008_LIVE_ACCEPTANCE.json",
    "docs/evidence/WORKSPACE_STEP003_MAIN_ASSISTANT_GROUPWARE_E2E.json",
}
LOCAL_ENVIRONMENT_FILENAMES = {".env", ".env.local", ".env.local.cmd"}
ENVIRONMENT_OR_CACHE_PARTS = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_local_environment_file(relative: Path) -> bool:
    return relative.name in LOCAL_ENVIRONMENT_FILENAMES


def is_local_acceptance_output(relative: Path) -> bool:
    """Exclude only root-local redirected acceptance logs from identity and packages."""
    if len(relative.parts) != 1:
        return False
    name = relative.name.lower()
    return name == "log.txt" or name.endswith(".log")


def is_generated_workspace_output(relative: Path) -> bool:
    posix = relative.as_posix()
    return (
        posix.startswith("okcanvas-agent-cli/dist/")
        or posix.startswith("okcanvas-connectors/groupware-mcp-server/dist/")
        or posix.startswith("okcanvas-connector-examples/groupware/groupware-api-fake/dist/")
        or posix.startswith("okcanvas-connectors/organization-context-mcp-server/dist/")
        or posix.startswith("okcanvas-connector-examples/organization-context/organization-context-api-fake/dist/")
    )


def excluded_package_path(relative: Path) -> bool:
    posix = relative.as_posix()
    if posix in MUTABLE_ACCEPTANCE_EVIDENCE:
        return True
    if is_local_acceptance_output(relative):
        return True
    if is_local_environment_file(relative):
        return True
    if any(part in ENVIRONMENT_OR_CACHE_PARTS for part in relative.parts):
        return True
    return is_generated_workspace_output(relative)


def excluded_workspace_path(relative: Path) -> bool:
    if relative.as_posix() == "WORKSPACE_MANIFEST.json":
        return True
    return excluded_package_path(relative)


def excluded_parent_project_path(relative: Path) -> bool:
    if is_local_environment_file(relative):
        return True
    if any(part in ENVIRONMENT_OR_CACHE_PARTS for part in relative.parts):
        return True
    if relative.parts and relative.parts[0] in {"dist", "build"}:
        return True
    if any(part.endswith(".egg-info") for part in relative.parts):
        return True
    return False


def snapshot_files(base: Path, *, workspace: bool = False) -> dict[str, tuple[str, int]]:
    result: dict[str, tuple[str, int]] = {}
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(base)
        excluded = excluded_workspace_path(relative) if workspace else excluded_parent_project_path(relative)
        if excluded:
            continue
        result[relative.as_posix()] = (sha256(path), path.stat().st_size)
    return result
