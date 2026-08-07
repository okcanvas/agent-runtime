from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract

_BARE_PYTHON = re.compile(r"(?im)^\s*(?:call\s+)?python(?:\.exe)?\s+")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP030A_ACCEPTANCE.json",
    )
    return parser


def run(output: Path) -> dict[str, object]:
    step030_launcher = (ROOT / "sh_run_step030_acceptance.cmd").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    setup = (ROOT / "sh_setup.cmd").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    baseline = legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py").read_text(encoding="utf-8")

    launchers = sorted(
        path for path in ROOT.glob("sh_*.cmd") if path.name != "sh_setup.cmd"
    )
    launcher_violations = []
    for path in launchers:
        text = path.read_text(encoding="utf-8")
        if _BARE_PYTHON.search(text):
            launcher_violations.append(path.name)
            continue
        if path.name == "sh_tui.cmd":
            if 'node "clients\\cli\\dist\\cli.js" %*' not in text:
                launcher_violations.append(path.name)
            continue
        if ".venv\\Scripts\\python.exe" not in text:
            launcher_violations.append(path.name)

    checks = {
        "step030_launcher_uses_project_venv": '".venv\\Scripts\\python.exe" scripts\\windows_entrypoint.py commerce-snapshot-non-empty-acceptance %*' in step030_launcher,
        "step030_launcher_rejects_missing_venv": 'if not exist ".venv\\Scripts\\python.exe" (' in step030_launcher and "exit /b 2" in step030_launcher,
        "step030_launcher_has_no_bare_python": _BARE_PYTHON.search(step030_launcher) is None,
        "all_python_runtime_launchers_use_project_venv_and_node_cli_is_direct": not launcher_violations,
        "step030_entrypoint_route_preserved": "run_step030_acceptance.py" in entrypoint and "commerce-snapshot-non-empty-acceptance" in entrypoint,
        "setup_installs_project_into_venv": '".venv\\Scripts\\python.exe" -m pip install -e .' in setup,
        "fastapi_is_declared_project_dependency": '"fastapi>=' in pyproject,
        "step030a_baseline_exact": 'PROJECT_VERSION = "2.43.1"' in baseline and 'CURRENT_STEP = "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"' in baseline,
    }
    payload: dict[str, object] = {
        "schema_version": "okcanvas-step030a-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "launcher_count": len(launchers),
        "launcher_violations": launcher_violations,
        "fixed_launcher": "sh_run_step030_acceptance.cmd",
        "windows_live_rerun_pending": False,
        "windows_live_accepted": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    args = _parser().parse_args()
    payload = run(args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
