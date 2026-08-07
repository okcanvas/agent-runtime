from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _live_output() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    acceptance_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
    return ROOT / "docs" / "evidence" / "step022-live" / acceptance_id / "closure-summary.json"




def _redact(text: str) -> str:
    redacted = text
    for secret in (
        os.environ.get("OPENAI_API_KEY"),
        os.environ.get("OKCANVAS_CONTROL_ADMIN_KEY"),
        os.environ.get("OKCANVAS_RUN_SUBMITTER_KEY"),
        os.environ.get("OKCANVAS_PROTECTED_PAYLOAD_KEY"),
    ):
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _run_child(
    *,
    label: str,
    command: list[str],
    output_path: Path,
    log_path: Path,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                f"label={label}",
                f"exit_code={completed.returncode}",
                "--- stdout ---",
                _redact(completed.stdout),
                "--- stderr ---",
                _redact(completed.stderr),
            ]
        ),
        encoding="utf-8",
    )
    payload = _read_json(output_path)
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    workspace = (
        payload.get("acceptance_workspace")
        if isinstance(payload.get("acceptance_workspace"), dict)
        else {}
    )
    return {
        "label": label,
        "exit_code": completed.returncode,
        "state": payload.get("state"),
        "cleanup_state": workspace.get("cleanup_state"),
        "failed_checks": sorted(name for name, value in checks.items() if value is not True),
        "summary_file": output_path.name,
        "log_file": log_path.name,
        "payload": payload,
    }


def _step021_passed(result: dict[str, Any]) -> bool:
    payload = result["payload"]
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    return (
        result["exit_code"] == 0
        and result["state"] == "PASSED"
        and result["cleanup_state"] == "COMPLETED"
        and bool(checks)
        and all(value is True for value in checks.values())
    )


def _step020_passed(result: dict[str, Any], *, live: bool) -> bool:
    payload = result["payload"]
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    approve = payload.get("approve") if isinstance(payload.get("approve"), dict) else {}
    reject = payload.get("reject") if isinstance(payload.get("reject"), dict) else {}
    approve_checks = approve.get("checks") if isinstance(approve.get("checks"), dict) else {}
    reject_checks = reject.get("checks") if isinstance(reject.get("checks"), dict) else {}
    return (
        result["exit_code"] == 0
        and result["state"] == "PASSED"
        and result["cleanup_state"] == "COMPLETED"
        and payload.get("live_sdk") is live
        and bool(checks)
        and all(value is True for value in checks.values())
        and approve.get("state") == "PASSED"
        and reject.get("state") == "PASSED"
        and approve_checks.get("process_restart_proven") is True
        and reject_checks.get("process_restart_proven") is True
        and approve_checks.get("tool_executed_exactly_once") is True
        and reject_checks.get("tool_not_executed") is True
    )


def _safe_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = result["payload"]
    approve = payload.get("approve") if isinstance(payload.get("approve"), dict) else {}
    reject = payload.get("reject") if isinstance(payload.get("reject"), dict) else {}
    safe: dict[str, Any] = {
        "label": result["label"],
        "exit_code": result["exit_code"],
        "state": result["state"],
        "cleanup_state": result["cleanup_state"],
        "failed_checks": result["failed_checks"],
        "summary_file": result["summary_file"],
        "log_file": result["log_file"],
    }
    if approve or reject:
        safe["approve_state"] = approve.get("state")
        safe["reject_state"] = reject.get("state")
    if payload.get("error_type"):
        safe["error_type"] = payload.get("error_type")
        safe["error"] = payload.get("error")
    workspace = payload.get("acceptance_workspace") if isinstance(payload.get("acceptance_workspace"), dict) else {}
    if workspace.get("preserved_path"):
        safe["preserved_path"] = workspace.get("preserved_path")
    return safe


def _execute(work_dir: Path, *, live: bool) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now()
    before_results = ReferenceCatalogService(ROOT).verify_all()
    before = {item.reference_id: item.actual_tree_sha256 for item in before_results}

    step021_output = work_dir / "step021-summary.json"
    step021 = _run_child(
        label="STEP021_APPROVAL_INBOX",
        command=[
            sys.executable,
            str(ROOT / "scripts" / "run_step021_acceptance.py"),
            "--output",
            str(step021_output),
        ],
        output_path=step021_output,
        log_path=work_dir / "step021.log",
    )
    print(
        f"[STEP022] STEP021 state={step021['state']} cleanup={step021['cleanup_state']}",
        flush=True,
    )

    step020_output = work_dir / ("step020-live-summary.json" if live else "step020-summary.json")
    step020_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_step020_acceptance.py"),
        "--output",
        str(step020_output),
    ]
    if live:
        step020_command.append("--live")
    step020 = _run_child(
        label="STEP020_LIVE_SDK_APPROVAL" if live else "STEP020_DETERMINISTIC_APPROVAL",
        command=step020_command,
        output_path=step020_output,
        log_path=work_dir / ("step020-live.log" if live else "step020.log"),
    )
    print(
        f"[STEP022] STEP020 state={step020['state']} cleanup={step020['cleanup_state']} live={live}",
        flush=True,
    )

    after_results = ReferenceCatalogService(ROOT).verify_all()
    after = {item.reference_id: item.actual_tree_sha256 for item in after_results}
    api_key = os.environ.get("OPENAI_API_KEY")
    log_text = "".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in work_dir.glob("*.log")
        if path.is_file()
    )
    checks = {
        "step021_inbox_accepted": _step021_passed(step021),
        "step020_approval_accepted": _step020_passed(step020, live=live),
        "step020_mode_matches": step020["payload"].get("live_sdk") is live,
        "references_unchanged": before == after and all(item.verified for item in after_results),
        "api_key_not_in_child_logs": not api_key or api_key not in log_text,
    }
    payload: dict[str, Any] = {
        "schema_version": (
            "okcanvas-step022-live-acceptance-closure-v1"
            if live
            else "okcanvas-step022-acceptance-v1"
        ),
        "mode": "LIVE_SDK" if live else "DETERMINISTIC",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started_at,
        "completed_at": _utc_now(),
        "checks": checks,
        "step021": _safe_result(step021),
        "step020": _safe_result(step020),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if api_key and api_key in serialized:
        payload["state"] = "FAILED"
        payload["checks"]["api_key_not_in_summary"] = False
    else:
        payload["checks"]["api_key_not_in_summary"] = True
    return payload


def _live_readiness_issues() -> list[str]:
    issues: list[str] = []
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        issues.append("API_KEY_MISSING")
    if not os.environ.get("OKCANVAS_AGENT_MODEL", "").strip():
        issues.append("MODEL_NOT_CONFIGURED")
    if importlib.util.find_spec("agents") is None:
        issues.append("SDK_NOT_INSTALLED")
    return issues


def run_acceptance(output: Path, *, live: bool = False) -> int:
    output = output.resolve()
    if live:
        issues = _live_readiness_issues()
        if issues:
            final = {
                "schema_version": "okcanvas-step022-live-acceptance-closure-v1",
                "mode": "LIVE_SDK",
                "state": "FAILED",
                "started_at": _utc_now(),
                "completed_at": _utc_now(),
                "checks": {"live_environment_ready": False},
                "readiness_issue_codes": issues,
            }
            _write_json(output, final)
        else:
            payload = _execute(output.parent, live=True)
            _write_json(output, payload)
            final = payload
    else:
        with AcceptanceWorkspace(step_id="STEP022", output=output) as workspace:
            payload = _execute(workspace.scratch_dir, live=False)
            final = workspace.finalize(payload)
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    if live:
        print(f"Acceptance evidence: {output.parent}")
    return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (
        _live_output()
        if args.live
        else ROOT / "docs" / "evidence" / "STEP022_ACCEPTANCE.json"
    )
    return run_acceptance(output, live=args.live)


if __name__ == "__main__":
    raise SystemExit(main())
