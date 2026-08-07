from __future__ import annotations

import argparse
import hashlib
import json
import gc
import os
import platform
import stat
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime import __version__
from okcanvas_agent_runtime.bootstrap.development_cli import main
from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteEnvelope
from okcanvas_agent_runtime.support.validation import PytestValidationResult, run_pytest_validation
from okcanvas_agent_runtime.adapters.workspace import snapshot_tree


LIVE_GATE = "OKCANVAS_STEP003_LIVE_ACCEPTANCE"
SUMMARY_SCHEMA_VERSION = "okcanvas-step003-live-acceptance-v2"
FIXTURE = ROOT / "fixtures" / "codex_write_repo"
_REQUIRED_ENV = ("OPENAI_API_KEY", "OKCANVAS_AGENT_MODEL", "OKCANVAS_CODEX_MODEL")
_ACCEPTANCE_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _default_acceptance_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def _validate_acceptance_id(value: str) -> str:
    if not _ACCEPTANCE_ID.fullmatch(value):
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


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        if hasattr(payload, "model_dump"):
            data = payload.model_dump(mode="json")
        else:
            data = payload
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)




def _force_remove_readonly(func: Callable[[str], object], path: str, exc_info: object) -> None:
    del exc_info
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    func(path)


def _cleanup_workspace(
    path: Path,
    *,
    attempts: int = 8,
    initial_delay_seconds: float = 0.1,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    started_ns = time.monotonic_ns()
    last_error: dict[str, str] | None = None
    attempted = 0

    for attempt in range(1, max(1, attempts) + 1):
        attempted = attempt
        if not path.exists():
            return {
                "state": "COMPLETED",
                "path": str(path),
                "attempts": attempted - 1,
                "duration_ms": max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                "error": None,
            }
        try:
            gc.collect()
            shutil.rmtree(path, onerror=_force_remove_readonly)
            return {
                "state": "COMPLETED",
                "path": str(path),
                "attempts": attempted,
                "duration_ms": max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                "error": None,
            }
        except Exception as exc:
            last_error = {"type": type(exc).__name__, "message": str(exc)[:500]}
            if attempt < attempts:
                sleeper(min(initial_delay_seconds * (2 ** (attempt - 1)), 1.0))

    return {
        "state": "WARNING",
        "path": str(path),
        "attempts": attempted,
        "duration_ms": max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
        "error": last_error,
    }


def _git_init(workspace: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.email", "acceptance@example.invalid"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.name", "STEP003 Acceptance"], cwd=workspace, check=True)
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture baseline"], cwd=workspace, check=True)


def _load_envelope(path: Path) -> CodexWriteEnvelope:
    return CodexWriteEnvelope.model_validate_json(path.read_text(encoding="utf-8"))


def _validation_record(path: Path, result: PytestValidationResult) -> dict[str, object]:
    return {
        "file": path.name,
        "sha256": _sha256_file(path),
        "state": result.state,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "passed": result.passed,
        "failed": result.failed,
        "errors": result.errors,
        "skipped": result.skipped,
        "duration_ms": result.duration_ms,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run isolated STEP003 live acceptance")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "docs" / "evidence" / "step003-live",
    )
    parser.add_argument("--acceptance-id")
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    command_runner: Callable[[list[str]], int] = main,
    cleanup_runner: Callable[[Path], dict[str, object]] = _cleanup_workspace,
) -> int:
    args = _build_parser().parse_args(list(argv or []))
    if os.getenv(LIVE_GATE) != "1":
        print(f"Refusing live execution: set {LIVE_GATE}=1", file=sys.stderr)
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

    run_dir = args.output_root.expanduser().resolve() / acceptance_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"Refusing to overwrite existing acceptance directory: {run_dir}", file=sys.stderr)
        return 2

    started_at = _utc_now()
    started_ns = time.monotonic_ns()
    summary_path = run_dir / "acceptance-summary.json"
    baseline_validation_path = run_dir / "baseline-validation.json"
    post_validation_path = run_dir / "post-validation.json"
    write_evidence = run_dir / "write-run.json"
    events = run_dir / "write-events.jsonl"
    patch = run_dir / "change.patch"
    original_before = snapshot_tree(FIXTURE)
    original_after = original_before
    baseline_validation: PytestValidationResult | None = None
    post_validation: PytestValidationResult | None = None
    envelope: CodexWriteEnvelope | None = None
    write_exit: int | None = None
    checks: dict[str, bool] = {}
    error: dict[str, str] | None = None
    cleanup: dict[str, object] = {
        "state": "NOT_ATTEMPTED",
        "path": None,
        "attempts": 0,
        "duration_ms": 0,
        "error": None,
    }
    temp_root = Path(tempfile.mkdtemp(prefix="okcanvas-step003-"))
    workspace = temp_root / "fixture-repo"

    try:
        shutil.copytree(FIXTURE, workspace)
        baseline_validation = run_pytest_validation(workspace)
        _atomic_write_json(baseline_validation_path, baseline_validation)
        _git_init(workspace)

        write_exit = command_runner(
            [
                "codex-write",
                "--workspace",
                str(workspace),
                "--input",
                (
                    "Fix the incorrect order total when a line quantity is greater than one. "
                    "Inspect the implementation and existing test, make the smallest source-only "
                    "change, and do not modify tests or project files. Do not install dependencies "
                    "or use the network. Independent validation will run after you finish."
                ),
                "--confirm-live-call",
                "--confirm-controlled-workspace",
                "--confirm-disposable-workspace",
                "--confirm-workspace-write",
                "--event-file",
                str(events),
                "--patch-file",
                str(patch),
                "--evidence-file",
                str(write_evidence),
                "--allow-file",
                "src/inventory/pricing.py",
                "--expect-file",
                "src/inventory/pricing.py",
                "--pretty",
            ]
        )
        if write_evidence.is_file():
            envelope = _load_envelope(write_evidence)
        post_validation = run_pytest_validation(workspace)
        _atomic_write_json(post_validation_path, post_validation)
        original_after = snapshot_tree(FIXTURE)

        checks = {
            "baseline_expected_failure": baseline_validation.state == "FAILED"
            and baseline_validation.failed == 1,
            "write_exit_zero": write_exit == 0,
            "write_succeeded": envelope is not None and envelope.state == "SUCCEEDED",
            "workspace_mutated": envelope is not None and envelope.mutation_detected,
            "exact_modified_file": envelope is not None
            and envelope.verified_modified_files == ["src/inventory/pricing.py"],
            "patch_present": patch.is_file() and patch.stat().st_size > 0,
            "post_validation_passed": post_validation.state == "PASSED"
            and post_validation.exit_code == 0
            and post_validation.passed >= 1,
            "original_fixture_unchanged": original_before == original_after,
            "head_unchanged": envelope is not None
            and envelope.baseline_commit == envelope.final_commit,
            "budget_accepted": envelope is not None and envelope.error is None,
        }
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:500]}
        original_after = snapshot_tree(FIXTURE)
    finally:
        cleanup = cleanup_runner(temp_root)

    core_passed = bool(checks) and all(checks.values()) and error is None
    cleanup_completed = cleanup.get("state") == "COMPLETED"
    if core_passed and cleanup_completed:
        acceptance_state = "PASSED"
    elif core_passed:
        acceptance_state = "PASSED_WITH_CLEANUP_WARNING"
    else:
        acceptance_state = "FAILED"
    completed_at = _utc_now()
    summary: dict[str, object] = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "acceptance_id": acceptance_id,
        "state": acceptance_state,
        "core_acceptance_passed": core_passed,
        "project_version": __version__,
        "started_at": _iso(started_at),
        "completed_at": _iso(completed_at),
        "duration_ms": max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
        "environment": {"python_version": platform.python_version(), "platform": platform.platform()},
        "checks": checks,
        "baseline_validation": _validation_record(baseline_validation_path, baseline_validation) if baseline_validation else None,
        "write_run": {
            "exit_code": write_exit,
            "file": write_evidence.name,
            "sha256": _sha256_file(write_evidence),
            "state": envelope.state if envelope else None,
            "run_id": envelope.run_id if envelope else None,
            "thread_id": envelope.thread_id if envelope else None,
            "modified_files": envelope.verified_modified_files if envelope else [],
            "patch_sha256": envelope.patch_sha256 if envelope else None,
            "agent_total_tokens": envelope.agent_usage.total_tokens if envelope else 0,
            "codex_total_tokens": (
                envelope.codex_usage.input_tokens + envelope.codex_usage.output_tokens
                if envelope else 0
            ),
            "error_code": envelope.error.code.value if envelope and envelope.error else None,
        },
        "post_validation": _validation_record(post_validation_path, post_validation) if post_validation else None,
        "patch_file": patch.name,
        "patch_sha256": _sha256_file(patch),
        "original_fixture_before": original_before.model_dump(mode="json"),
        "original_fixture_after": original_after.model_dump(mode="json"),
        "error": error,
        "cleanup": cleanup,
    }
    _atomic_write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Acceptance evidence: {run_dir}", file=sys.stderr)
    return 0 if core_passed else (write_exit or 4)


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
