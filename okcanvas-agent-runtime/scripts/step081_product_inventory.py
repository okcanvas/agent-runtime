from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "artifacts",
    "node_modules",
    ".local",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_FILES = {".env.local", ".env.local.cmd"}
EXCLUDED_ROOT_FILES = {"yarn.lock"}
EXCLUDED_ROOT_SUFFIXES = {".zip", ".sha256"}
EXCLUDED_PREFIXES = {
    ("docs", "evidence", "step002-live"),
    ("docs", "evidence", "step003-live"),
    ("docs", "evidence", "step004-live"),
    ("docs", "evidence", "step007-live"),
    ("docs", "evidence", "step008-live"),
    ("docs", "evidence", "step009-live"),
    ("docs", "evidence", "step020-live"),
    ("docs", "evidence", "step022-live"),
    ("docs", "evidence", "step024-live"),
    ("docs", "evidence", "step071-live"),
    ("docs", "evidence", "step072-live"),
    ("docs", "evidence", "step072a-live"),
    ("docs", "evidence", "step072b-live"),
    ("docs", "evidence", "step074-live"),
    ("docs", "evidence", "step075-live"),
    ("docs", "evidence", "step075a-live"),
    ("docs", "evidence", "step075b-live"),
    ("docs", "evidence", "step075c-live"),
    ("docs", "evidence", "step075d-live"),
    ("docs", "evidence", "step075e-live"),
    ("docs", "evidence", "step075f-live"),
    ("docs", "evidence", "step075g-live"),
    ("docs", "evidence", "step076-live"),
    ("docs", "evidence", "step077-live"),
    ("docs", "evidence", "step078-live"),
    ("docs", "evidence", "step079-live"),
    ("docs", "evidence", "step079a-live"),
    ("docs", "evidence", "step080a-live"),
    ("docs", "evidence", "step081-live"),
    ("docs", "evidence", "step081a-live"),
    ("docs", "evidence", "step081b-live"),
    ("docs", "evidence", "step081c-live"),
    ("docs", "evidence", "step081c-local"),
    ("docs", "evidence", "step081b-python-regression"),
    ("docs", "evidence", "step081d-live"),
    ("docs", "evidence", "step081d-local"),
    ("docs", "evidence", "step082b-local"),
    ("docs", "evidence", "step083-local"),
    ("docs", "evidence", "step084-local"),
    ("docs", "evidence", "step085-local"),
    ("docs", "evidence", "step086-local"),
    ("docs", "evidence", "step086r1-local"),
    ("docs", "evidence", "step086r2-local"),
}


def included_relative_path(relative: Path) -> bool:
    if relative.name in EXCLUDED_FILES:
        return False
    if len(relative.parts) == 1 and relative.name in EXCLUDED_ROOT_FILES:
        return False
    if len(relative.parts) == 1 and any(relative.name.endswith(suffix) for suffix in EXCLUDED_ROOT_SUFFIXES):
        return False
    if any(relative.parts[: len(prefix)] == prefix for prefix in EXCLUDED_PREFIXES):
        return False
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if "dist" in relative.parts and relative.parts[:3] != ("clients", "cli", "dist"):
        return False
    return relative.suffix not in EXCLUDED_SUFFIXES


def classified_workspace_residue(root: Path) -> list[dict[str, str]]:
    """Return known non-product residue without admitting it to the Product inventory."""
    records: list[dict[str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if included_relative_path(relative):
            continue
        reason = None
        if len(relative.parts) == 1 and relative.name in EXCLUDED_ROOT_FILES:
            reason = "root_local_lockfile"
        elif len(relative.parts) == 1 and any(relative.name.endswith(suffix) for suffix in EXCLUDED_ROOT_SUFFIXES):
            reason = "root_local_archive"
        elif relative.parts[:3] == ("docs", "evidence", "step081b-python-regression"):
            reason = "superseded_local_regression_evidence"
        if reason is not None:
            records.append({"path": relative.as_posix(), "reason": reason})
    return records

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if not included_relative_path(relative):
            continue
        result[relative.as_posix()] = {
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
    return result


def changed_paths(baseline: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(
        path
        for path in set(baseline) | set(current)
        if baseline.get(path) != current.get(path)
    )


def json_sha_without_self(payload: dict[str, Any], field: str) -> str:
    clone = dict(payload)
    clone.pop(field, None)
    encoded = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
