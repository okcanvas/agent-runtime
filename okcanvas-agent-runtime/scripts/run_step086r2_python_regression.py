from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
STEP = "STEP086R2_DELEGATED_ROLE_HEADER_AND_EXTERNAL_CONNECTOR_CONTRACT_CLOSURE"
VERSION = "2.66.2"
DEFAULT_OUTPUT = ROOT / "docs/evidence/step086r2-local/STEP086R2_PYTHON_REGRESSION.json"
DEFAULT_LOG_DIR = ROOT / "docs/evidence/step086r2-local/python-regression"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _test_files() -> tuple[Path, ...]:
    return tuple(sorted((ROOT / "tests").glob("test_*.py")))


def _test_inventory_sha256(files: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content_sha = hashlib.sha256(path.read_bytes()).digest()
        digest.update(content_sha)
    return digest.hexdigest()


def _junit_counts(path: Path) -> dict[str, int]:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        "tests": sum(int(item.attrib.get("tests", "0")) for item in suites),
        "failures": sum(int(item.attrib.get("failures", "0")) for item in suites),
        "errors": sum(int(item.attrib.get("errors", "0")) for item in suites),
        "skipped": sum(int(item.attrib.get("skipped", "0")) for item in suites),
    }


def _payload(
    *,
    files: tuple[Path, ...],
    chunks: list[dict[str, Any]],
    chunk_size: int,
    timeout_seconds: int,
    started_at: str,
    test_inventory_sha256: str,
) -> dict[str, Any]:
    expected_starts = tuple(range(0, len(files), chunk_size))
    completed_starts = {int(item["start_file_index"]) for item in chunks}
    totals = {
        key: sum(int(item["counts"][key]) for item in chunks)
        for key in ("tests", "failures", "errors", "skipped")
    }
    passed = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    any_failure = any(
        int(item["return_code"]) != 0 or bool(item["timed_out"])
        for item in chunks
    )
    complete = completed_starts == set(expected_starts)
    state = "FAILED" if any_failure else ("PASSED" if complete else "IN_PROGRESS")
    return {
        "schema_version": "okcanvas-step086r2-python-regression-v1",
        "step": STEP,
        "version": VERSION,
        "state": state,
        "started_at": started_at,
        "checkpointed_at": _utc_now(),
        "completed_at": _utc_now() if state in {"PASSED", "FAILED"} else None,
        "test_file_count": len(files),
        "test_inventory_sha256": test_inventory_sha256,
        "chunk_size": chunk_size,
        "expected_chunk_count": len(expected_starts),
        "completed_chunk_count": len(chunks),
        "per_chunk_timeout_seconds": timeout_seconds,
        "passed_tests": passed,
        "failed_tests": totals["failures"],
        "error_tests": totals["errors"],
        "skipped_tests": totals["skipped"],
        "total_tests": totals["tests"],
        "chunks": sorted(chunks, key=lambda item: int(item["start_file_index"])),
    }


def _load_checkpoint(
    output: Path,
    *,
    files: tuple[Path, ...],
    chunk_size: int,
    timeout_seconds: int,
    test_inventory_sha256: str,
) -> tuple[str, list[dict[str, Any]]]:
    if not output.is_file():
        return _utc_now(), []
    payload = json.loads(output.read_text(encoding="utf-8"))
    compatible = (
        payload.get("schema_version") == "okcanvas-step086r2-python-regression-v1"
        and payload.get("step") == STEP
        and payload.get("version") == VERSION
        and payload.get("test_file_count") == len(files)
        and payload.get("test_inventory_sha256") == test_inventory_sha256
        and payload.get("chunk_size") == chunk_size
        and payload.get("per_chunk_timeout_seconds") == timeout_seconds
    )
    if not compatible:
        raise RuntimeError("Existing STEP086R2 Python regression checkpoint is incompatible")
    chunks = payload.get("chunks", [])
    if not isinstance(chunks, list):
        raise RuntimeError("Existing STEP086R2 Python regression checkpoint is invalid")
    return str(payload.get("started_at") or _utc_now()), [dict(item) for item in chunks]


def _evidence_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _run_chunk(
    *,
    files: tuple[Path, ...],
    start: int,
    chunk_size: int,
    timeout_seconds: int,
    log_dir: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    selected = files[start : start + chunk_size]
    end = start + len(selected) - 1
    log_path = log_dir / f"chunk-{start:03d}-{end:03d}.txt"
    with tempfile.TemporaryDirectory(prefix="step086r2-pytest-") as temporary:
        junit_path = Path(temporary) / "junit.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *[path.relative_to(ROOT).as_posix() for path in selected],
            f"--junitxml={junit_path}",
        ]
        timed_out = False
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        with log_path.open("w", encoding="utf-8", errors="replace") as log_handle:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=os.name != "nt",
                creationflags=creationflags,
            )
            try:
                return_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                return_code = 124
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                log_handle.write(f"\nSTEP086R2_CHUNK_TIMEOUT seconds={timeout_seconds}\n")
        captured = log_path.read_text(encoding="utf-8", errors="replace")
        counts = (
            _junit_counts(junit_path)
            if junit_path.is_file()
            else {"tests": 0, "failures": 0, "errors": 1, "skipped": 0}
        )
        summary_match = re.findall(
            r"(?P<passed>\d+) passed(?:, (?P<skipped>\d+) skipped)?",
            captured,
        )
    return {
        "start_file_index": start,
        "end_file_index": end,
        "file_count": len(selected),
        "first_file": selected[0].relative_to(ROOT).as_posix(),
        "last_file": selected[-1].relative_to(ROOT).as_posix(),
        "return_code": return_code,
        "timed_out": timed_out,
        "counts": counts,
        "summary": summary_match[-1] if summary_match else None,
        "log_path": _evidence_path(log_path),
    }


def run(
    *,
    output: Path,
    log_dir: Path,
    chunk_size: int,
    timeout_seconds: int,
    max_chunks: int | None,
    reset: bool,
) -> int:
    files = _test_files()
    test_inventory_sha256 = _test_inventory_sha256(files)
    if not files:
        raise RuntimeError("No Python regression test files found")
    output.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    if reset:
        output.unlink(missing_ok=True)
        for stale in log_dir.glob("chunk-*.txt"):
            stale.unlink()

    started_at, chunks = _load_checkpoint(
        output,
        files=files,
        chunk_size=chunk_size,
        timeout_seconds=timeout_seconds,
        test_inventory_sha256=test_inventory_sha256,
    )
    completed_starts = {int(item["start_file_index"]) for item in chunks}
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(ROOT)
    executed_now = 0

    for start in range(0, len(files), chunk_size):
        if start in completed_starts:
            continue
        chunk = _run_chunk(
            files=files,
            start=start,
            chunk_size=chunk_size,
            timeout_seconds=timeout_seconds,
            log_dir=log_dir,
            environment=environment,
        )
        chunks.append(chunk)
        executed_now += 1
        payload = _payload(
            files=files,
            chunks=chunks,
            chunk_size=chunk_size,
            timeout_seconds=timeout_seconds,
            started_at=started_at,
            test_inventory_sha256=test_inventory_sha256,
        )
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if payload["state"] == "FAILED":
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 1
        if max_chunks is not None and executed_now >= max_chunks:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0

    payload = _payload(
        files=files,
        chunks=chunks,
        chunk_size=chunk_size,
        timeout_seconds=timeout_seconds,
        started_at=started_at,
        test_inventory_sha256=test_inventory_sha256,
    )
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--chunk-size", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--max-chunks", type=int)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    if args.chunk_size < 1:
        raise ValueError("chunk-size must be positive")
    if args.timeout_seconds < 1:
        raise ValueError("timeout-seconds must be positive")
    if args.max_chunks is not None and args.max_chunks < 1:
        raise ValueError("max-chunks must be positive")
    return run(
        output=args.output.resolve(),
        log_dir=args.log_dir.resolve(),
        chunk_size=args.chunk_size,
        timeout_seconds=args.timeout_seconds,
        max_chunks=args.max_chunks,
        reset=args.reset,
    )


if __name__ == "__main__":
    raise SystemExit(main())
