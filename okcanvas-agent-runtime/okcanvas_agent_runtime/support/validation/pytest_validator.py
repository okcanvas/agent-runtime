from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field

from okcanvas_agent_runtime.core.contracts import StrictModel


_SUMMARY_PATTERNS = {
    "passed": re.compile(r"(?<!\d)(\d+) passed\b"),
    "failed": re.compile(r"(?<!\d)(\d+) failed\b"),
    "errors": re.compile(r"(?<!\d)(\d+) errors?\b"),
    "skipped": re.compile(r"(?<!\d)(\d+) skipped\b"),
}
_VALIDATOR_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "USERPROFILE",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "TMP",
    "TEMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
)
_MAX_CAPTURE_CHARS = 12_000


class PytestValidationResult(StrictModel):
    schema_version: str = "okcanvas-pytest-validation-v1"
    state: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    command: list[str]
    cwd: str
    exit_code: int | None
    timed_out: bool
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    stdout_sha256: str
    stderr_sha256: str
    stdout_tail: str
    stderr_tail: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _counts(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for name, pattern in _SUMMARY_PATTERNS.items():
        matches = pattern.findall(text)
        result[name] = int(matches[-1]) if matches else 0
    return result


def _validator_environment() -> dict[str, str]:
    env = {name: os.environ[name] for name in _VALIDATOR_ENV_ALLOWLIST if os.environ.get(name)}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_pytest_validation(workspace: Path, *, timeout_seconds: float = 60.0) -> PytestValidationResult:
    workspace = workspace.expanduser().resolve()
    started_at = _utc_now()
    started_ns = time.monotonic_ns()
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    stdout = b""
    stderr = b""
    exit_code: int | None = None
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=_validator_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
    completed_at = _utc_now()
    decoded_stdout = stdout.decode("utf-8", errors="replace")
    decoded_stderr = stderr.decode("utf-8", errors="replace")
    counts = _counts(decoded_stdout + "\n" + decoded_stderr)
    state = "PASSED" if exit_code == 0 and not timed_out and counts["failed"] == 0 and counts["errors"] == 0 else "FAILED"
    return PytestValidationResult(
        state=state,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
        command=["<python>", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=str(workspace),
        exit_code=exit_code,
        timed_out=timed_out,
        passed=counts["passed"],
        failed=counts["failed"],
        errors=counts["errors"],
        skipped=counts["skipped"],
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        stdout_tail=decoded_stdout[-_MAX_CAPTURE_CHARS:],
        stderr_tail=decoded_stderr[-_MAX_CAPTURE_CHARS:],
    )
