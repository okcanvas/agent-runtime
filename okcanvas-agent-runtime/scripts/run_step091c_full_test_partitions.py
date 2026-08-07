from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"
EVIDENCE_ROOT = ROOT / "docs" / "evidence" / "step091c-runtime-full-suite-partitions"
SUMMARY_PATH = ROOT / "docs" / "evidence" / "STEP091C_FULL_RUNTIME_TEST_PARTITIONS.json"
PARTITION_COUNT = 12
STEP = "STEP091C_ARTIFACT_BLOB_STORE_AND_OBJECT_STORAGE_BOUNDARY"
SCHEMA_VERSION = "okcanvas-step091c-full-runtime-test-partitions-v1"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def collected_test_files() -> list[str]:
    return sorted(path.relative_to(ROOT).as_posix() for path in TEST_ROOT.rglob("test_*.py") if path.is_file())


def partitions(files: list[str]) -> list[list[str]]:
    quotient, remainder = divmod(len(files), PARTITION_COUNT)
    result: list[list[str]] = []
    cursor = 0
    for index in range(PARTITION_COUNT):
        size = quotient + (1 if index < remainder else 0)
        result.append(files[cursor : cursor + size])
        cursor += size
    if cursor != len(files) or any(not group for group in result):
        raise RuntimeError("invalid deterministic test partition allocation")
    return result


def summary_counts(output: str) -> tuple[int, int, int]:
    passed = skipped = failed = 0
    for pattern, target in (
        (r"(?<!\d)(\d+) passed", "passed"),
        (r"(?<!\d)(\d+) skipped", "skipped"),
        (r"(?<!\d)(\d+) failed", "failed"),
    ):
        matches = re.findall(pattern, output)
        value = int(matches[-1]) if matches else 0
        if target == "passed":
            passed = value
        elif target == "skipped":
            skipped = value
        else:
            failed = value
    return passed, skipped, failed


def partition_paths(number: int) -> tuple[Path, Path]:
    stem = f"partition-{number:02d}"
    return EVIDENCE_ROOT / f"{stem}.log", EVIDENCE_ROOT / f"{stem}.json"


def run_partition(number: int) -> int:
    if number < 1 or number > PARTITION_COUNT:
        raise SystemExit(f"partition must be between 1 and {PARTITION_COUNT}")
    files = collected_test_files()
    groups = partitions(files)
    selected = groups[number - 1]
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    log_path, json_path = partition_paths(number)

    command = [sys.executable, "-m", "pytest", "-q", *selected]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    process = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    duration = round(time.monotonic() - started, 3)
    combined = process.stdout
    if process.stderr:
        combined += ("\n" if combined and not combined.endswith("\n") else "") + "[stderr]\n" + process.stderr
    log_bytes = combined.encode("utf-8")
    log_path.write_bytes(log_bytes)
    passed, skipped, failed = summary_counts(combined)
    files_bytes = ("\n".join(selected) + "\n").encode("utf-8")
    payload: dict[str, Any] = {
        "schema_version": "okcanvas-step091c-runtime-test-partition-v1",
        "step": STEP,
        "partition_id": f"part-{number:02d}",
        "partition_number": number,
        "partition_count": PARTITION_COUNT,
        "state": "PASSED" if process.returncode == 0 else "FAILED",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, "-m", "pytest", "-q", "<partition-files>"],
        "file_count": len(selected),
        "test_count": passed + skipped + failed,
        "passed_tests": passed,
        "skipped_tests": skipped,
        "failed_tests": failed,
        "duration_seconds": duration,
        "exit_code": process.returncode,
        "files_sha256": sha256_bytes(files_bytes),
        "log_sha256": sha256_bytes(log_bytes),
        "raw_provider_output_persisted": False,
        "files": selected,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return process.returncode


def aggregate() -> int:
    files = collected_test_files()
    expected_groups = partitions(files)
    payloads: list[dict[str, Any]] = []
    missing_evidence: list[str] = []
    for number in range(1, PARTITION_COUNT + 1):
        log_path, json_path = partition_paths(number)
        if not log_path.is_file() or not json_path.is_file():
            missing_evidence.append(f"part-{number:02d}")
            continue
        item = json.loads(json_path.read_text(encoding="utf-8"))
        log_bytes = log_path.read_bytes()
        expected_files = expected_groups[number - 1]
        item["log_hash_current"] = sha256_bytes(log_bytes)
        item["log_hash_valid"] = item.get("log_sha256") == item["log_hash_current"]
        item["file_assignment_exact"] = item.get("files") == expected_files
        payloads.append(item)

    covered = [path for item in payloads for path in item.get("files", [])]
    unique = sorted(set(covered))
    duplicates = sorted({path for path in covered if covered.count(path) > 1})
    missing = sorted(set(files) - set(unique))
    unexpected = sorted(set(unique) - set(files))
    all_exit_codes_zero = len(payloads) == PARTITION_COUNT and all(item.get("exit_code") == 0 for item in payloads)
    all_hashes_valid = len(payloads) == PARTITION_COUNT and all(item.get("log_hash_valid") for item in payloads)
    assignments_exact = len(payloads) == PARTITION_COUNT and all(item.get("file_assignment_exact") for item in payloads)
    exact_coverage = not missing and not unexpected and not duplicates and len(covered) == len(files)
    state = "PASSED" if not missing_evidence and all_exit_codes_zero and all_hashes_valid and assignments_exact and exact_coverage else "FAILED"
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "step": STEP,
        "state": state,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "execution_mode": "DETERMINISTIC_PARTITIONED_FULL_SUITE",
        "reason": "The monolithic suite can exceed bounded command windows; exact test-file partitions provide complete non-overlapping coverage.",
        "collected_test_file_count": len(files),
        "covered_test_file_count": len(covered),
        "unique_covered_test_file_count": len(unique),
        "total_passed_tests": sum(int(item.get("passed_tests", 0)) for item in payloads),
        "total_skipped_tests": sum(int(item.get("skipped_tests", 0)) for item in payloads),
        "total_failed_tests": sum(int(item.get("failed_tests", 0)) for item in payloads),
        "partition_count": PARTITION_COUNT,
        "completed_partition_count": len(payloads),
        "missing_partition_evidence": missing_evidence,
        "all_exit_codes_zero": all_exit_codes_zero,
        "all_log_hashes_valid": all_hashes_valid,
        "partition_assignments_exact": assignments_exact,
        "exact_file_coverage": exact_coverage,
        "missing_files": missing,
        "unexpected_files": unexpected,
        "duplicate_files": duplicates,
        "raw_provider_output_persisted": False,
        "partitions": payloads,
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if state == "PASSED" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition", type=int)
    parser.add_argument("--aggregate", action="store_true")
    args = parser.parse_args(argv)
    if args.partition is not None and args.aggregate:
        parser.error("choose either --partition or --aggregate")
    if args.partition is not None:
        return run_partition(args.partition)
    if args.aggregate:
        return aggregate()
    for number in range(1, PARTITION_COUNT + 1):
        return_code = run_partition(number)
        if return_code != 0:
            return return_code
    return aggregate()


if __name__ == "__main__":
    raise SystemExit(main())
