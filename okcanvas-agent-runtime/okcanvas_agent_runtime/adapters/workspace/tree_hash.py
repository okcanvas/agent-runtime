from __future__ import annotations

import hashlib
from pathlib import Path

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import TreeSnapshot


DEFAULT_IGNORED_NAMES = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache"})


def snapshot_tree(
    root: Path,
    *,
    ignored_names: frozenset[str] = DEFAULT_IGNORED_NAMES,
) -> TreeSnapshot:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)

    digest = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    symlink_count = 0

    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if any(part in ignored_names for part in relative.parts):
            continue
        if path.is_symlink():
            target = path.readlink().as_posix().encode("utf-8")
            digest.update(b"L\0")
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(target)
            digest.update(b"\0")
            file_count += 1
            total_bytes += len(target)
            symlink_count += 1
            continue
        if not path.is_file():
            continue
        payload = path.read_bytes()
        digest.update(b"F\0")
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(path.stat().st_mode & 0o777).encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(payload).digest())
        digest.update(b"\0")
        file_count += 1
        total_bytes += len(payload)

    return TreeSnapshot(
        sha256=digest.hexdigest(),
        file_count=file_count,
        total_bytes=total_bytes,
        symlink_count=symlink_count,
        ignored_names=sorted(ignored_names),
    )
