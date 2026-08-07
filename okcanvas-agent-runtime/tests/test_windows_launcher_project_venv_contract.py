from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BARE_PYTHON = re.compile(r"(?im)^\s*(?:call\s+)?python(?:\.exe)?\s+")


def test_all_runtime_windows_launchers_use_project_venv_python() -> None:
    launchers = sorted(
        path
        for path in ROOT.glob("sh_*.cmd")
        if path.name != "sh_setup.cmd"
    )
    assert launchers
    for launcher in launchers:
        text = launcher.read_text(encoding="utf-8")
        assert not _BARE_PYTHON.search(text), launcher.name
        if launcher.name == "sh_tui.cmd":
            assert "node \"clients\\cli\\dist\\cli.js\" %*" in text
            assert ".venv\\Scripts\\python.exe" not in text
        else:
            assert ".venv\\Scripts\\python.exe" in text, launcher.name


def test_step030_launcher_fails_closed_when_project_venv_is_missing() -> None:
    text = (ROOT / "sh_run_step030_acceptance.cmd").read_text(encoding="utf-8")
    assert 'if not exist ".venv\\Scripts\\python.exe" (' in text
    assert "Run sh_setup.cmd first." in text
    assert "exit /b 2" in text
