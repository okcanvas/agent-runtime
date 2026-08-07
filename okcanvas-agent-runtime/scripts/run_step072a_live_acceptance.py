from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/evidence/step072a-live/STEP072A_LIVE_ACCEPTANCE.json"
STEP = "STEP072A_WINDOWS_PYCACHE_OVERLAY_ISOLATION_FIX"
VERSION = "2.52.1"
EXPECTED_MODEL = "gpt-4.1"


def _redact(value: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    return value.replace(api_key, "[REDACTED]") if api_key else value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("STEP072 child evidence must be an object")
    return value


def run(output: Path) -> int:
    child_output = output.parent / "STEP072_CHILD_LIVE_ACCEPTANCE.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if child_output.exists():
        child_output.unlink()

    pycache_value = os.getenv("PYTHONPYCACHEPREFIX", "").strip()
    pycache_prefix = Path(pycache_value).resolve() if pycache_value else None
    command = [
        sys.executable,
        str(ROOT / "scripts/run_step072_live_acceptance.py"),
        "--output",
        str(child_output),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    combined = completed.stdout + "\n" + completed.stderr
    child: dict[str, Any] = {}
    child_error: str | None = None
    try:
        child = _load_json(child_output)
    except Exception as exc:  # noqa: BLE001 - compact acceptance evidence
        child_error = f"{type(exc).__name__}: {_redact(str(exc))}"

    usage = child.get("usage") if isinstance(child.get("usage"), dict) else {}
    child_checks = child.get("checks") if isinstance(child.get("checks"), dict) else {}
    prefix_outside_project = pycache_prefix is not None and not (
        pycache_prefix == ROOT or ROOT in pycache_prefix.parents
    )
    checks = {
        "live_environment_ready": bool(os.getenv("OPENAI_API_KEY", "").strip())
        and os.getenv("OKCANVAS_AGENT_MODEL", "").strip() == EXPECTED_MODEL,
        "bytecode_isolation_environment_present": pycache_prefix is not None,
        "bytecode_isolation_active_in_interpreter": pycache_prefix is not None
        and Path(sys.pycache_prefix or "").resolve() == pycache_prefix,
        "bytecode_isolation_prefix_outside_project": prefix_outside_project,
        "step072_child_process_succeeded": completed.returncode == 0,
        "step072_child_evidence_loaded": child_error is None and bool(child),
        "step072_live_checks_exact": child.get("state") == "PASSED"
        and child.get("passed_checks") == 13
        and child.get("total_checks") == 13,
        "single_model_call_observed": child.get("model_calls") == 1,
        "positive_token_usage_recorded": isinstance(usage.get("total_tokens"), int)
        and usage.get("total_tokens", 0) > 0,
        "run_succeeded": child.get("terminal_status") == "SUCCEEDED",
        "provider_trace_export_diagnostic_absent": child.get("trace_error_markers") == []
        and child.get("sdk_trace_export_observed") is False,
        "api_key_not_in_captured_output": os.getenv("OPENAI_API_KEY", "") not in combined,
        "child_api_key_not_persisted": child_checks.get("child_api_key_not_persisted") is True,
        "child_raw_attachment_not_persisted": child_checks.get("child_raw_attachment_not_persisted")
        is True,
        "child_workspace_cleanup_completed": child_checks.get(
            "child_workspace_cleanup_completed"
        )
        is True,
    }
    payload: dict[str, Any] = {
        "schema_version": "okcanvas-step072a-live-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "python_pycache_prefix_active": pycache_prefix is not None,
        "python_pycache_prefix_inside_project": not prefix_outside_project,
        "model": child.get("model"),
        "model_calls": child.get("model_calls"),
        "usage": usage,
        "terminal_status": child.get("terminal_status"),
        "run_id": child.get("run_id"),
        "trace_error_markers": child.get("trace_error_markers"),
        "sdk_trace_export_observed": child.get("sdk_trace_export_observed"),
        "child_evidence_error": child_error,
        "child_stdout_tail": _redact(completed.stdout[-2000:]),
        "child_stderr_tail": _redact(completed.stderr[-2000:]),
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return run(args.output or DEFAULT_OUTPUT)


if __name__ == "__main__":
    raise SystemExit(main())
