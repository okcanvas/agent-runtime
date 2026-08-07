"""Canonical repository and root-package paths for the flat STEP081 layout."""
from __future__ import annotations

from pathlib import Path

RUNTIME_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = RUNTIME_PACKAGE_ROOT.parent
PACKAGE_ROOT = PROJECT_ROOT
PROTOCOLS_PACKAGE_ROOT = PROJECT_ROOT / "okcanvas_agent_protocols"
CLIENTS_PACKAGE_ROOT = PROJECT_ROOT / "okcanvas_agent_clients"


def require_project_root() -> Path:
    """Return the immutable project root after validating the three package owners."""
    required = (
        RUNTIME_PACKAGE_ROOT / "__init__.py",
        PROTOCOLS_PACKAGE_ROOT / "__init__.py",
        CLIENTS_PACKAGE_ROOT / "__init__.py",
        PROJECT_ROOT / "pyproject.toml",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"STEP081 project root contract is incomplete: {missing}")
    return PROJECT_ROOT
