import subprocess
from pathlib import Path

from okcanvas_agent_runtime.adapters.workspace.git_diff import inspect_git


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=path, check=True)


def test_git_inspection_captures_exact_text_change(tmp_path: Path) -> None:
    target = tmp_path / "a.py"
    target.write_text("value = 1\n", encoding="utf-8")
    _init_repo(tmp_path)
    baseline = inspect_git(tmp_path)
    assert baseline.clean is True
    target.write_text("value = 2\n", encoding="utf-8")
    changed = inspect_git(tmp_path)
    assert changed.clean is False
    assert changed.diff.files == ["a.py"]
    assert changed.diff.changes[0].status == "M"
    assert changed.diff.changes[0].binary is False
    assert changed.diff.bytes > 0


def test_git_inspection_reports_untracked_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("value = 1\n", encoding="utf-8")
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("new = True\n", encoding="utf-8")
    inspection = inspect_git(tmp_path)
    assert inspection.diff.untracked_files == ["new.py"]
