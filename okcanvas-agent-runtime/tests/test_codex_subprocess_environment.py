from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from okcanvas_agent_runtime.adapters.openai.runtime.codex_gateway import (
    _codex_subprocess_env as readonly_codex_env,
)
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_gateway import (
    _codex_subprocess_env as write_codex_env,
)


def _assert_no_bytecode(env: dict[str, str], tmp_path: Path) -> None:
    package = tmp_path / "samplepkg"
    package.mkdir()
    (package / "__init__.py").write_text("VALUE = 7\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-c", "import samplepkg; assert samplepkg.VALUE == 7"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert not (package / "__pycache__").exists()


def test_readonly_codex_child_python_does_not_create_bytecode(tmp_path: Path) -> None:
    _assert_no_bytecode(readonly_codex_env(), tmp_path)


def test_write_codex_child_python_does_not_create_bytecode(tmp_path: Path) -> None:
    _assert_no_bytecode(write_codex_env(), tmp_path)
