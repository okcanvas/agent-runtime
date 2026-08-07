from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from okcanvas_agent_runtime.agent.tools.codex.write_contracts import GitChange, GitDiffSummary


class GitInspectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitInspection:
    head: str
    clean: bool
    diff: GitDiffSummary
    patch: bytes


def _run_git(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise GitInspectionError(completed.stderr.decode("utf-8", errors="replace")[:1000])
    return completed.stdout


def git_head(root: Path) -> str:
    return _run_git(root, "rev-parse", "HEAD").decode("ascii").strip()


def git_is_clean(root: Path) -> bool:
    return not _run_git(root, "status", "--porcelain=v1", "-z")


def _name_status(root: Path) -> list[tuple[str, str]]:
    raw = _run_git(root, "diff", "--name-status", "-z", "HEAD", "--")
    parts = raw.decode("utf-8", errors="strict").split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    changes: list[tuple[str, str]] = []
    index = 0
    while index < len(parts):
        status = parts[index]
        index += 1
        if status.startswith(("R", "C")):
            if index + 1 >= len(parts):
                raise GitInspectionError("Malformed rename/copy status output")
            old_path = parts[index]
            new_path = parts[index + 1]
            index += 2
            changes.append((status[0], f"{old_path} -> {new_path}"))
        else:
            if index >= len(parts):
                raise GitInspectionError("Malformed name-status output")
            changes.append((status[:1], parts[index]))
            index += 1
    return changes


def _numstat(root: Path) -> dict[str, tuple[int | None, int | None, bool]]:
    raw = _run_git(root, "diff", "--numstat", "-z", "HEAD", "--")
    records = raw.decode("utf-8", errors="strict").split("\0")
    result: dict[str, tuple[int | None, int | None, bool]] = {}
    for record in records:
        if not record:
            continue
        fields = record.split("\t", 2)
        if len(fields) != 3:
            raise GitInspectionError("Malformed numstat output")
        added, deleted, path = fields
        binary = added == "-" or deleted == "-"
        result[path] = (
            None if binary else int(added),
            None if binary else int(deleted),
            binary,
        )
    return result


def inspect_git(root: Path) -> GitInspection:
    root = root.expanduser().resolve()
    head = git_head(root)
    patch = _run_git(root, "diff", "--binary", "--no-ext-diff", "HEAD", "--")
    numstat = _numstat(root)
    status_entries = _name_status(root)
    untracked_raw = _run_git(root, "ls-files", "--others", "--exclude-standard", "-z")
    untracked = sorted(
        item for item in untracked_raw.decode("utf-8", errors="strict").split("\0") if item
    )
    staged_raw = _run_git(root, "diff", "--cached", "--name-only", "-z", "HEAD", "--")
    staged = sorted(
        item for item in staged_raw.decode("utf-8", errors="strict").split("\0") if item
    )
    changes: list[GitChange] = []
    for status, path in status_entries:
        additions, deletions, binary = numstat.get(path, (None, None, False))
        changes.append(
            GitChange(
                status=status,
                path=path,
                additions=additions,
                deletions=deletions,
                binary=binary,
            )
        )
    files = sorted(change.path for change in changes)
    diff = GitDiffSummary(
        sha256=hashlib.sha256(patch).hexdigest(),
        bytes=len(patch),
        files=files,
        changes=changes,
        untracked_files=untracked,
        staged_files=staged,
    )
    return GitInspection(
        head=head,
        clean=not changes and not untracked and not staged,
        diff=diff,
        patch=patch,
    )
