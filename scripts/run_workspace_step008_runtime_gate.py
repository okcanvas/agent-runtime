from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from current_workspace_baseline import load_current_baseline
from workspace_inventory import snapshot_files
from workspace_process import resolve_project_python, run_process_to_files, write_json_stdout

RUNTIME_ROOT = ROOT / "okcanvas-agent-runtime"
CURRENT = load_current_baseline(ROOT)
RUNTIME_STEP = CURRENT.runtime_step


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def snapshot_digest(snapshot: dict[str, tuple[str, int]]) -> str:
    encoded = json.dumps(
        [[path, value[0], value[1]] for path, value in sorted(snapshot.items())],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run(*, runtime_evidence: Path, process_evidence: Path, stdout_log: Path, stderr_log: Path, focused_evidence: Path | None = None) -> int:
    started = now()
    before = snapshot_files(RUNTIME_ROOT)
    runtime_python = resolve_project_python(
        RUNTIME_ROOT,
        required_modules=("pytest", "fastapi", "pydantic"),
        fallback_executable=sys.executable,
        allow_fallback=sys.platform != "win32",
    )
    command = ["scripts/run_step093_acceptance.py", "--output", str(runtime_evidence), "--quiet"]
    process = run_process_to_files(
        runtime_python,
        command,
        cwd=RUNTIME_ROOT,
        stdout_path=stdout_log,
        stderr_path=stderr_log,
    )
    after = snapshot_files(RUNTIME_ROOT)
    runtime_payload = (
        json.loads(runtime_evidence.read_text(encoding="utf-8"))
        if runtime_evidence.is_file()
        else {}
    )
    unchanged = before == after
    state = (
        "PASSED"
        if process.get("returncode") == 0
        and runtime_payload.get("state") == "PASSED"
        and runtime_payload.get("passed_checks") == runtime_payload.get("total_checks")
        and runtime_payload.get("step") == RUNTIME_STEP
        and unchanged
        else "FAILED"
    )
    payload = {
        "schema_version": "okcanvas-workspace-step008r4r9-runtime-gate-process-v1",
        "state": state,
        "started_at": started,
        "completed_at": now(),
        "runtime_step": RUNTIME_STEP,
        "executed_fresh": True,
        "runtime_python": runtime_python,
        "source_snapshot_digest_before": snapshot_digest(before),
        "source_snapshot_digest_after": snapshot_digest(after),
        "source_unchanged": unchanged,
        "runtime_evidence_path": str(runtime_evidence),
        "runtime_evidence_sha256": hashlib.sha256(runtime_evidence.read_bytes()).hexdigest()
        if runtime_evidence.is_file()
        else None,
        "process": process,
    }
    process_evidence.parent.mkdir(parents=True, exist_ok=True)
    process_evidence.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_json_stdout(payload)
    return 0 if state == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-evidence", type=Path, required=True)
    parser.add_argument("--process-evidence", type=Path, required=True)
    parser.add_argument("--stdout-log", type=Path, required=True)
    parser.add_argument("--stderr-log", type=Path, required=True)
    parser.add_argument("--focused-evidence", type=Path)
    args = parser.parse_args()
    return run(
        runtime_evidence=args.runtime_evidence.resolve(),
        process_evidence=args.process_evidence.resolve(),
        stdout_log=args.stdout_log.resolve(),
        stderr_log=args.stderr_log.resolve(),
        focused_evidence=args.focused_evidence.resolve() if args.focused_evidence else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
