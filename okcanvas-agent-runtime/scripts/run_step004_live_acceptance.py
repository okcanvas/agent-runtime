from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from okcanvas_agent_runtime import __version__
from okcanvas_agent_runtime.agent.tools.codex.approval_contracts import (
    ApprovalPrepareEnvelope,
    ApprovalRecord,
    ApprovalResumeEnvelope,
)
from okcanvas_agent_runtime.support.validation import run_pytest_validation
from okcanvas_agent_runtime.adapters.workspace import snapshot_tree


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "codex_write_repo"
LIVE_GATE = "OKCANVAS_STEP004_LIVE_ACCEPTANCE"
SUMMARY_SCHEMA_VERSION = "okcanvas-step004-live-acceptance-v1"
_REQUIRED_ENV = ("OPENAI_API_KEY", "OKCANVAS_AGENT_MODEL", "OKCANVAS_CODEX_MODEL")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _git_init(workspace: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.email", "step004@example.invalid"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.name", "STEP004 Acceptance"], cwd=workspace, check=True)
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture baseline"], cwd=workspace, check=True)


def _force_remove_readonly(function, path, _exc_info) -> None:
    target = Path(path)
    try:
        target.chmod(stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    function(path)


def _cleanup(path: Path) -> dict[str, Any]:
    started = time.monotonic_ns()
    try:
        shutil.rmtree(path, onerror=_force_remove_readonly)
        return {
            "state": "COMPLETED",
            "path": str(path),
            "duration_ms": max(0, (time.monotonic_ns() - started) // 1_000_000),
            "error": None,
        }
    except Exception as exc:
        return {
            "state": "WARNING",
            "path": str(path),
            "duration_ms": max(0, (time.monotonic_ns() - started) // 1_000_000),
            "error": {"type": type(exc).__name__, "message": str(exc)[:500]},
        }


def _run_cli(arguments: list[str]) -> int:
    command = [sys.executable, "-m", "okcanvas_agent_runtime", *arguments]
    completed = subprocess.run(command, cwd=ROOT, check=False, text=True)
    return completed.returncode


def _prepare_args(workspace: Path, branch_dir: Path) -> list[str]:
    return [
        "codex-approval-prepare",
        "--workspace",
        str(workspace),
        "--input",
        (
            "Fix the incorrect order total when a line quantity is greater than one. "
            "Inspect the implementation and existing test, make the smallest source-only "
            "change, and do not modify tests or project files. Do not install dependencies "
            "or use the network. Independent validation will run after approval."
        ),
        "--confirm-live-call",
        "--confirm-controlled-workspace",
        "--confirm-disposable-workspace",
        "--confirm-workspace-write",
        "--state-file",
        str(branch_dir / "run-state.json"),
        "--approval-file",
        str(branch_dir / "approval.json"),
        "--event-file",
        str(branch_dir / "write-events.jsonl"),
        "--patch-file",
        str(branch_dir / "change.patch"),
        "--write-evidence-file",
        str(branch_dir / "write-run.json"),
        "--evidence-file",
        str(branch_dir / "prepare.json"),
        "--allow-file",
        "src/inventory/pricing.py",
        "--expect-file",
        "src/inventory/pricing.py",
    ]


def _resume_args(branch_dir: Path, decision: str, evidence_name: str) -> list[str]:
    return [
        "codex-approval-resume",
        "--approval-file",
        str(branch_dir / "approval.json"),
        "--decision",
        decision,
        "--evidence-file",
        str(branch_dir / evidence_name),
    ]


def _load_model(path: Path, model):
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def _secret_absent(paths: list[Path]) -> bool:
    key = os.getenv("OPENAI_API_KEY", "").encode("utf-8")
    if not key:
        return False
    return all(not path.is_file() or key not in path.read_bytes() for path in paths)


def _run_branch(run_dir: Path, decision: str) -> dict[str, Any]:
    branch_dir = run_dir / decision
    branch_dir.mkdir(parents=True, exist_ok=False)
    temp_root = Path(tempfile.mkdtemp(prefix=f"okcanvas-step004-{decision}-"))
    workspace = temp_root / "fixture-repo"
    cleanup: dict[str, Any] = {"state": "NOT_ATTEMPTED", "path": str(temp_root)}
    error: dict[str, str] | None = None
    checks: dict[str, bool] = {}
    prepare_exit: int | None = None
    resume_exit: int | None = None
    duplicate_exit: int | None = None
    prepare: ApprovalPrepareEnvelope | None = None
    resume: ApprovalResumeEnvelope | None = None
    duplicate: ApprovalResumeEnvelope | None = None
    record: ApprovalRecord | None = None
    baseline = None
    post = None
    source_before = snapshot_tree(FIXTURE)
    source_after = source_before

    try:
        shutil.copytree(FIXTURE, workspace)
        baseline = run_pytest_validation(workspace)
        _atomic_write_json(branch_dir / "baseline-validation.json", baseline.model_dump(mode="json"))
        _git_init(workspace)
        workspace_before_prepare = snapshot_tree(workspace)

        prepare_exit = _run_cli(_prepare_args(workspace, branch_dir))
        if (branch_dir / "prepare.json").is_file():
            prepare = _load_model(branch_dir / "prepare.json", ApprovalPrepareEnvelope)
        workspace_after_prepare = snapshot_tree(workspace)

        resume_exit = _run_cli(_resume_args(branch_dir, decision, "resume.json"))
        if (branch_dir / "resume.json").is_file():
            resume = _load_model(branch_dir / "resume.json", ApprovalResumeEnvelope)

        duplicate_exit = _run_cli(_resume_args(branch_dir, decision, "duplicate-resume.json"))
        if (branch_dir / "duplicate-resume.json").is_file():
            duplicate = _load_model(
                branch_dir / "duplicate-resume.json", ApprovalResumeEnvelope
            )
        record = ApprovalRecord.model_validate_json(
            (branch_dir / "approval.json").read_text(encoding="utf-8")
        )
        source_after = snapshot_tree(FIXTURE)

        sensitive_paths = [branch_dir / "run-state.json", branch_dir / "approval.json"]
        common = {
            "prepare_exit_zero": prepare_exit == 0,
            "prepare_awaiting": prepare is not None and prepare.state == "AWAITING_APPROVAL",
            "prepare_codex_not_called": prepare is not None and not prepare.codex_called,
            "prepare_workspace_unchanged": workspace_before_prepare == workspace_after_prepare,
            "persisted_state_present": (branch_dir / "run-state.json").is_file(),
            "approval_record_present": (branch_dir / "approval.json").is_file(),
            "secret_absent_from_persisted_state": _secret_absent(sensitive_paths),
            "duplicate_resume_blocked": duplicate_exit not in (None, 0)
            and duplicate is not None
            and duplicate.error is not None
            and duplicate.error.code.value == "APPROVAL_ALREADY_DECIDED",
            "source_fixture_unchanged": source_before == source_after,
        }
        if decision == "approve":
            post = run_pytest_validation(workspace)
            _atomic_write_json(
                branch_dir / "post-validation.json", post.model_dump(mode="json")
            )
            checks = {
                **common,
                "resume_exit_zero": resume_exit == 0,
                "resume_succeeded": resume is not None and resume.state == "SUCCEEDED",
                "execution_exactly_once": record.execution_count == 1,
                "record_succeeded": record.state.value == "SUCCEEDED",
                "workspace_mutated": resume is not None and resume.workspace_mutated,
                "write_evidence_present": (branch_dir / "write-run.json").is_file(),
                "patch_present": (branch_dir / "change.patch").is_file()
                and (branch_dir / "change.patch").stat().st_size > 0,
                "post_validation_passed": post.state == "PASSED"
                and post.exit_code == 0
                and post.passed >= 1,
            }
        else:
            checks = {
                **common,
                "resume_exit_zero": resume_exit == 0,
                "resume_rejected": resume is not None and resume.state == "REJECTED",
                "execution_count_zero": record.execution_count == 0,
                "record_rejected": record.state.value == "REJECTED",
                "workspace_unchanged": snapshot_tree(workspace) == workspace_before_prepare,
                "write_evidence_absent": not (branch_dir / "write-run.json").exists(),
                "patch_absent": not (branch_dir / "change.patch").exists(),
                "event_evidence_absent": not (branch_dir / "write-events.jsonl").exists(),
            }
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:500]}
        source_after = snapshot_tree(FIXTURE)
    finally:
        cleanup = _cleanup(temp_root)

    passed = bool(checks) and all(checks.values()) and error is None
    return {
        "decision": decision.upper(),
        "state": "PASSED" if passed else "FAILED",
        "checks": checks,
        "prepare_exit": prepare_exit,
        "resume_exit": resume_exit,
        "duplicate_exit": duplicate_exit,
        "approval_id": record.approval_id if record else None,
        "execution_id": record.execution_id if record else None,
        "execution_count": record.execution_count if record else None,
        "record_state": record.state.value if record else None,
        "prepare_file": "prepare.json",
        "prepare_sha256": _sha256_file(branch_dir / "prepare.json"),
        "resume_file": "resume.json",
        "resume_sha256": _sha256_file(branch_dir / "resume.json"),
        "approval_file": "approval.json",
        "approval_sha256": _sha256_file(branch_dir / "approval.json"),
        "run_state_file": "run-state.json",
        "run_state_sha256": _sha256_file(branch_dir / "run-state.json"),
        "write_run_sha256": _sha256_file(branch_dir / "write-run.json"),
        "patch_sha256": _sha256_file(branch_dir / "change.patch"),
        "baseline_validation": baseline.model_dump(mode="json") if baseline else None,
        "post_validation": post.model_dump(mode="json") if post else None,
        "source_fixture_before": source_before.model_dump(mode="json"),
        "source_fixture_after": source_after.model_dump(mode="json"),
        "cleanup": cleanup,
        "error": error,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run persisted STEP004 approval acceptance")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "docs" / "evidence" / "step004-live",
    )
    parser.add_argument("--acceptance-id")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv or []))
    if os.getenv(LIVE_GATE) != "1":
        print(f"Refusing live execution: set {LIVE_GATE}=1", file=sys.stderr)
        return 2
    missing = [name for name in _REQUIRED_ENV if not os.getenv(name)]
    if missing:
        print(f"Refusing live execution: missing {', '.join(missing)}", file=sys.stderr)
        return 2
    acceptance_id = args.acceptance_id or (
        _utc_now().strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    )
    run_dir = args.output_root.expanduser().resolve() / acceptance_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"Refusing to overwrite existing acceptance directory: {run_dir}", file=sys.stderr)
        return 2

    started = _utc_now()
    started_ns = time.monotonic_ns()
    approve = _run_branch(run_dir, "approve")
    reject = _run_branch(run_dir, "reject")
    passed = approve["state"] == "PASSED" and reject["state"] == "PASSED"
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "acceptance_id": acceptance_id,
        "state": "PASSED" if passed else "FAILED",
        "project_version": __version__,
        "started_at": _iso(started),
        "completed_at": _iso(_utc_now()),
        "duration_ms": max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "approve": approve,
        "reject": reject,
    }
    _atomic_write_json(run_dir / "acceptance-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Acceptance evidence: {run_dir}", file=sys.stderr)
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
