from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    relation = (ROOT / "sh_run_workspace_step008r4r9_relation_live_acceptance.cmd").read_text(encoding="utf-8")
    base = (ROOT / "sh_run_workspace_step008_live_acceptance.cmd").read_text(encoding="utf-8")
    setup = (ROOT / "okcanvas-agent-runtime/sh_setup.cmd").read_text(encoding="utf-8")
    pyproject = (ROOT / "okcanvas-agent-runtime/pyproject.toml").read_text(encoding="utf-8")
    checks = {
        "relation_requires_runtime_venv": 'okcanvas-agent-runtime\\.venv\\Scripts\\python.exe' in relation,
        "relation_uses_bytecode_isolation": 'scripts\\workspace_python_bytecode_isolation.py' in relation,
        "relation_targets_relation_entrypoint": 'scripts\\run_workspace_step008r4r9_relation_live_entrypoint.py' in relation,
        "relation_has_no_workspace_venv_fallback": '.workspace-venv' not in relation,
        "relation_has_no_system_python_fallback": 'py -3 scripts\\run_workspace_step008r4r9_relation_live_entrypoint.py' not in relation,
        "base_live_uses_runtime_venv": 'okcanvas-agent-runtime\\.venv\\Scripts\\python.exe' in base,
        "base_live_uses_bytecode_isolation": 'scripts\\workspace_python_bytecode_isolation.py' in base,
        "runtime_setup_installs_editable_runtime": '".venv\\Scripts\\python.exe" -m pip install -e .' in setup,
        "uvicorn_is_runtime_dependency": '"uvicorn>=0.35,<1"' in pyproject,
    }
    payload = {
        "schema_version": "okcanvas-workspace-step008r4r9a-launcher-contract-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(v is True for v in checks.values()),
        "total_checks": len(checks),
        "checks": checks,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
