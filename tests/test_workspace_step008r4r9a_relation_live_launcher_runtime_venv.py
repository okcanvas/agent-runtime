from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_relation_live_launcher_uses_runtime_venv_and_bytecode_isolation() -> None:
    launcher = (ROOT / "sh_run_workspace_step008r4r9_relation_live_acceptance.cmd").read_text(encoding="utf-8")
    assert 'okcanvas-agent-runtime\\.venv\\Scripts\\python.exe' in launcher
    assert 'scripts\\workspace_python_bytecode_isolation.py' in launcher
    assert 'scripts\\run_workspace_step008r4r9_relation_live_entrypoint.py' in launcher
    assert '.workspace-venv' not in launcher
    assert 'py -3 scripts\\run_workspace_step008r4r9_relation_live_entrypoint.py' not in launcher
    assert 'Run sh_setup_workspace.cmd first.' in launcher


def test_runtime_setup_installs_runtime_dependencies_in_the_same_venv() -> None:
    setup = (ROOT / "okcanvas-agent-runtime/sh_setup.cmd").read_text(encoding="utf-8")
    pyproject = (ROOT / "okcanvas-agent-runtime/pyproject.toml").read_text(encoding="utf-8")
    assert '".venv\\Scripts\\python.exe" -m pip install -e .' in setup
    assert '"uvicorn>=0.35,<1"' in pyproject
