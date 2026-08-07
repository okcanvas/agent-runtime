from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from okcanvas_agent_runtime import __version__
from okcanvas_agent_runtime.bootstrap.development_cli import main
from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyEnvelope


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "codex_readonly_repo"
LIVE_GATE = "OKCANVAS_STEP002_LIVE_ACCEPTANCE"
SUMMARY_SCHEMA_VERSION = "okcanvas-step002-live-acceptance-v1"
_REQUIRED_ENV = ("OPENAI_API_KEY", "OKCANVAS_AGENT_MODEL", "OKCANVAS_CODEX_MODEL")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _default_acceptance_id() -> str:
    timestamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _validate_acceptance_id(value: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise ValueError("acceptance ID must match [A-Za-z0-9._-] and be at most 80 characters")
    return value


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _git_init(workspace: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(
        ["git", "config", "user.email", "acceptance@example.invalid"],
        cwd=workspace,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "STEP002 Acceptance"], cwd=workspace, check=True
    )
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture baseline"], cwd=workspace, check=True)


def _load_envelope(path: Path) -> CodexReadOnlyEnvelope:
    return CodexReadOnlyEnvelope.model_validate_json(path.read_text(encoding="utf-8"))


def _run_record(
    *,
    exit_code: int | None,
    envelope_path: Path,
    event_path: Path,
) -> dict[str, object]:
    record: dict[str, object] = {
        "exit_code": exit_code,
        "evidence_file": envelope_path.name,
        "event_file": event_path.name,
        "evidence_sha256": _sha256_file(envelope_path),
        "event_sha256": _sha256_file(event_path),
    }
    if envelope_path.is_file():
        try:
            envelope = _load_envelope(envelope_path)
            record.update(
                {
                    "state": envelope.state,
                    "run_id": envelope.run_id,
                    "thread_id": envelope.thread_id,
                    "resumed_thread": envelope.resumed_thread,
                    "sdk_version": envelope.sdk_version,
                    "codex_cli_version": envelope.codex_cli_version,
                    "event_count": envelope.event_count,
                    "mutation_detected": envelope.mutation_detected,
                    "error_code": envelope.error.code.value if envelope.error else None,
                }
            )
        except Exception as exc:  # acceptance evidence must still record parse failure
            record["evidence_parse_error"] = type(exc).__name__
    return record


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run isolated STEP002 live acceptance")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "docs" / "evidence" / "step002-live",
        help="Parent directory for a unique acceptance run directory",
    )
    parser.add_argument("--acceptance-id", help="Optional unique run ID")
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    command_runner: Callable[[list[str]], int] = main,
) -> int:
    args = _build_parser().parse_args(list(argv or []))
    if os.getenv(LIVE_GATE) != "1":
        print(
            f"Refusing live execution: set {LIVE_GATE}=1 and all required model credentials",
            file=sys.stderr,
        )
        return 2

    missing = [name for name in _REQUIRED_ENV if not os.getenv(name)]
    if missing:
        print(f"Refusing live execution: missing {', '.join(missing)}", file=sys.stderr)
        return 2

    try:
        acceptance_id = _validate_acceptance_id(args.acceptance_id or _default_acceptance_id())
    except ValueError as exc:
        print(f"Invalid acceptance ID: {exc}", file=sys.stderr)
        return 2

    output_root = args.output_root.expanduser().resolve()
    run_dir = output_root / acceptance_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"Refusing to overwrite existing acceptance directory: {run_dir}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Unable to create acceptance directory ({type(exc).__name__})", file=sys.stderr)
        return 4

    started_at = _utc_now()
    started_ns = time.monotonic_ns()
    summary_path = run_dir / "acceptance-summary.json"
    first_evidence = run_dir / "first-run.json"
    second_evidence = run_dir / "second-run.json"
    first_events = run_dir / "first-events.jsonl"
    second_events = run_dir / "second-events.jsonl"
    thread_state = run_dir / "thread.json"
    first_exit: int | None = None
    second_exit: int | None = None
    checks: dict[str, bool] = {}
    error: dict[str, str] | None = None

    try:
        with tempfile.TemporaryDirectory(prefix="okcanvas-step002-") as temp_dir:
            workspace = Path(temp_dir) / "fixture-repo"
            shutil.copytree(FIXTURE, workspace)
            _git_init(workspace)

            first_exit = command_runner(
                [
                    "codex-readonly",
                    "--workspace",
                    str(workspace),
                    "--input",
                    (
                        "Investigate why an order total is incorrect when a line quantity is greater "
                        "than one. Inspect the implementation and its tests. Do not modify files. "
                        "Report repository-relative files and distinguish inspection from execution."
                    ),
                    "--confirm-live-call",
                    "--confirm-controlled-workspace",
                    "--event-file",
                    str(first_events),
                    "--thread-state-file",
                    str(thread_state),
                    "--evidence-file",
                    str(first_evidence),
                    "--require-file",
                    "src/inventory/pricing.py",
                    "--require-file",
                    "tests/test_pricing.py",
                    "--pretty",
                ]
            )
            if first_exit == 0:
                second_exit = command_runner(
                    [
                        "codex-readonly",
                        "--workspace",
                        str(workspace),
                        "--input",
                        (
                            "Continue the same read-only investigation. Summarize the confirmed root "
                            "cause and explicitly list anything still unverified. Do not modify files."
                        ),
                        "--confirm-live-call",
                        "--confirm-controlled-workspace",
                        "--event-file",
                        str(second_events),
                        "--thread-state-file",
                        str(thread_state),
                        "--evidence-file",
                        str(second_evidence),
                        "--pretty",
                    ]
                )

            first = _load_envelope(first_evidence) if first_evidence.is_file() else None
            second = _load_envelope(second_evidence) if second_evidence.is_file() else None
            checks = {
                "first_exit_zero": first_exit == 0,
                "second_exit_zero": second_exit == 0,
                "first_succeeded": first is not None and first.state == "SUCCEEDED",
                "second_succeeded": second is not None and second.state == "SUCCEEDED",
                "first_unchanged": first is not None
                and first.before == first.after
                and not first.mutation_detected,
                "second_unchanged": second is not None
                and second.before == second.after
                and not second.mutation_detected,
                "thread_preserved": first is not None
                and second is not None
                and bool(first.thread_id)
                and first.thread_id == second.thread_id,
                "second_resumed": second is not None and second.resumed_thread,
                "first_events_present": first is not None and first.event_count > 0,
                "second_events_present": second is not None and second.event_count > 0,
            }
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:500]}

    passed = bool(checks) and all(checks.values()) and error is None
    completed_at = _utc_now()
    summary: dict[str, object] = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "acceptance_id": acceptance_id,
        "state": "PASSED" if passed else "FAILED",
        "project_version": __version__,
        "started_at": _iso(started_at),
        "completed_at": _iso(completed_at),
        "duration_ms": max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "checks": checks,
        "first_run": _run_record(
            exit_code=first_exit, envelope_path=first_evidence, event_path=first_events
        ),
        "second_run": _run_record(
            exit_code=second_exit, envelope_path=second_evidence, event_path=second_events
        ),
        "thread_state_file": thread_state.name,
        "thread_state_sha256": _sha256_file(thread_state),
        "error": error,
    }
    _atomic_write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Acceptance evidence: {run_dir}", file=sys.stderr)
    return 0 if passed else (first_exit or second_exit or 4)


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
