from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _clean_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def test_step081_inventory_generator_direct_execution_bootstraps_project_root(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/generate_step081_product_baseline_inventory.py"), "--help"],
        cwd=tmp_path,
        env=_clean_environment(),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--baseline-root" in result.stdout
    for script in (
        "run_step081a_acceptance.py",
        "run_step081a_live_acceptance.py",
        "run_step081b_acceptance.py",
        "run_step081b_live_acceptance.py",
    ):
        wrapper = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--help"],
            cwd=tmp_path,
            env=_clean_environment(),
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert wrapper.returncode == 0, f"{script}: {wrapper.stderr}"
        assert "--output" in wrapper.stdout


def test_step081_package_source_direct_execution_bootstraps_project_root(tmp_path: Path) -> None:
    output = tmp_path / "candidate.zip"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/package_source.py"), str(output)],
        cwd=tmp_path,
        env=_clean_environment(),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert output.is_file()
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    assert "okcanvas-agent-runtime/pyproject.toml" in names
    assert "okcanvas-agent-runtime/okcanvas_agent_runtime/__init__.py" in names
    assert not any(name.startswith("okcanvas-agent-runtime/src/okcanvas_agent_runtime/") for name in names)

def test_package_main_module_is_import_safe() -> None:
    import importlib

    module = importlib.import_module("okcanvas_agent_runtime.__main__")
    assert callable(module.main)

