"""Deterministic project-source import identity for repository validators."""
from __future__ import annotations

import importlib
import inspect
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable


def _normalized(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def force_project_root_first(root: Path) -> None:
    """Place the repository root first and remove duplicate representations."""
    resolved = root.resolve()
    normalized = _normalized(resolved)
    retained: list[str] = []
    for value in sys.path:
        candidate = value or os.getcwd()
        try:
            if _normalized(candidate) == normalized:
                continue
        except OSError:
            pass
        retained.append(value)
    sys.path[:] = [str(resolved), *retained]
    importlib.invalidate_caches()


def module_origin(module: ModuleType) -> str | None:
    value = inspect.getsourcefile(module) or getattr(module, "__file__", None)
    return str(Path(value).resolve()) if value else None


def object_origin(value: Any) -> str | None:
    source = inspect.getsourcefile(value)
    return str(Path(source).resolve()) if source else None


def origin_under_root(origin: str | None, root: Path) -> bool:
    if origin is None:
        return False
    try:
        return os.path.commonpath((_normalized(origin), _normalized(root))) == _normalized(root)
    except (OSError, ValueError):
        return False


def validate_module_origins(root: Path, names: Iterable[str]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for name in names:
        module = importlib.import_module(name)
        origin = module_origin(module)
        records.append(
            {
                "module": name,
                "origin": origin,
                "under_project_root": origin_under_root(origin, root),
            }
        )
    return {
        "project_root": str(root.resolve()),
        "sys_path_head": list(sys.path[:8]),
        "modules": records,
        "all_under_project_root": all(item["under_project_root"] for item in records),
    }
