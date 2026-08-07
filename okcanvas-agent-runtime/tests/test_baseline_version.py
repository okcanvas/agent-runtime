from __future__ import annotations

import tomllib
from pathlib import Path

from okcanvas_agent_runtime import __version__
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def test_runtime_version_is_consistent_with_pyproject() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    declared = pyproject["project"]["version"]
    assert declared == PROJECT_VERSION == __version__ == RuntimeInfo().version


def test_runtime_step_uses_baseline_constant() -> None:
    assert RuntimeInfo().step == CURRENT_STEP
