from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Final, Iterator


_COMPONENT_PATHS: Final[dict[str, tuple[str, ...]]] = {
    "control_api.app": (
        "okcanvas_agent_runtime/bootstrap/application.py",
        "okcanvas_agent_runtime/application/admin/use_cases.py",
        "okcanvas_agent_runtime/application/service/use_cases.py",
        "okcanvas_agent_runtime/transport/admin/rest/routes.py",
        "okcanvas_agent_runtime/transport/service/rest/routes.py",
    ),
    "execution.openai_gateway": (
        "okcanvas_agent_runtime/adapters/openai/generic_gateway.py",
    ),
    "execution.runtime_binding": (
        "okcanvas_agent_runtime/agent/runtime/binding.py",
        "okcanvas_agent_runtime/bootstrap/runtime_binding.py",
    ),
    "service_clients.routes": (
        "okcanvas_agent_runtime/transport/service/rest/routes.py",
        "okcanvas_agent_runtime/application/service/use_cases.py",
    ),
    "tool_approval.gateway": (
        "okcanvas_agent_runtime/application/approvals/gateway.py",
        "okcanvas_agent_runtime/adapters/openai/local_tool_approval.py",
    ),
    "run_submission.execution": (
        "okcanvas_agent_runtime/application/submissions/execution.py",
    ),
    "run_submission.store": (
        "okcanvas_agent_runtime/adapters/persistence/run_submission.py",
    ),
    "run_submission.lifecycle": (
        "okcanvas_agent_runtime/application/submissions/lifecycle.py",
    ),
    "evaluation.application": (
        "okcanvas_agent_runtime/application/evaluation/application.py",
    ),
}

_ASSET_ROOTS: Final[dict[str, str]] = {
    "operations_console.assets": "okcanvas_agent_clients/dev_console/assets",
    "interactive_runner.assets": "okcanvas_agent_clients/dev_runner/assets",
    "tui_client.package": "okcanvas_agent_clients/tui",
}


def _project_root(project_root: str | Path) -> Path:
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project root does not exist: {root}")
    return root


def component_source_paths(
    project_root: str | Path,
    logical_component: str,
) -> tuple[Path, ...]:
    root = _project_root(project_root)
    if logical_component == "runtime.all":
        paths = tuple(
            path
            for path in sorted((root / "okcanvas_agent_runtime").rglob("*.py"))
            if "__pycache__" not in path.parts
        )
    else:
        relative_paths = _COMPONENT_PATHS.get(logical_component)
        if relative_paths is None:
            raise KeyError(f"Unknown logical source component: {logical_component}")
        paths = tuple((root / relative).resolve() for relative in relative_paths)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Logical source component {logical_component!r} has missing canonical files: {missing}"
        )
    for path in paths:
        path.relative_to(root)
    return paths


def read_component_source(
    project_root: str | Path,
    logical_component: str,
) -> str:
    chunks: list[str] = []
    root = _project_root(project_root)
    for path in component_source_paths(root, logical_component):
        relative = path.relative_to(root).as_posix()
        chunks.append(f"# --- canonical-source: {relative} ---\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def component_asset_root(
    project_root: str | Path,
    logical_component: str,
) -> Path:
    root = _project_root(project_root)
    relative = _ASSET_ROOTS.get(logical_component)
    if relative is None:
        raise KeyError(f"Unknown logical asset component: {logical_component}")
    path = (root / relative).resolve()
    path.relative_to(root)
    if not path.is_dir():
        raise FileNotFoundError(
            f"Logical asset component {logical_component!r} is missing: {path}"
        )
    return path


@dataclass(frozen=True)
class LegacySourceContract:
    """Path-like read contract for one historical logical source component.

    It deliberately does not recreate the removed legacy package tree. Reads are
    resolved through the canonical relocation map, while split components are
    deterministically concatenated for historical source assertions.
    """

    project_root: Path
    logical_component: str
    paths: tuple[Path, ...]
    annotate_sources: bool = True

    def read_text(self, encoding: str = "utf-8", errors: str | None = None) -> str:
        del errors
        if len(self.paths) == 1 and not self.annotate_sources:
            return self.paths[0].read_text(encoding=encoding)
        chunks: list[str] = []
        for path in self.paths:
            relative = path.relative_to(self.project_root).as_posix()
            chunks.append(
                f"# --- canonical-source: {relative} ---\n"
                + path.read_text(encoding=encoding)
            )
        return "\n\n".join(chunks)

    def read_bytes(self) -> bytes:
        return self.read_text(encoding="utf-8").encode("utf-8")

    def is_file(self) -> bool:
        return bool(self.paths) and all(path.is_file() for path in self.paths)

    def is_dir(self) -> bool:
        return (
            len(self.paths) == 1
            and self.paths[0].name == "__init__.py"
            and self.paths[0].parent.is_dir()
        )

    def exists(self) -> bool:
        return self.is_file() or self.is_dir()

    @property
    def name(self) -> str:
        return self.paths[0].name

    @property
    def suffix(self) -> str:
        return self.paths[0].suffix

    def stat(self):
        return self.paths[0].stat()

    def open(self, mode: str = "r", encoding: str | None = None, **kwargs):
        if len(self.paths) != 1:
            raise OSError(
                f"Split logical source {self.logical_component!r} cannot be opened as one file"
            )
        return self.paths[0].open(mode=mode, encoding=encoding, **kwargs)

    def __fspath__(self) -> str:
        return os.fspath(self.paths[0])

    def __str__(self) -> str:
        return os.fspath(self.paths[0])


def _alias_map(project_root: Path) -> dict[str, str]:
    path = project_root / "okcanvas_agent_runtime/compatibility/aliases.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    aliases = payload.get("aliases")
    if not isinstance(aliases, dict):
        raise ValueError("Compatibility alias registry is invalid")
    return {str(key): str(value) for key, value in aliases.items()}


def _module_path(project_root: Path, module_name: str) -> Path | None:
    relative = Path(*module_name.split("."))
    file_path = project_root / relative.with_suffix(".py")
    if file_path.is_file():
        return file_path.resolve()
    package_path = project_root / relative / "__init__.py"
    if package_path.is_file():
        return package_path.resolve()
    return None


def _resolve_alias_target(project_root: Path, module_name: str) -> Path:
    aliases = _alias_map(project_root)
    visited: set[str] = set()
    current = module_name
    while current not in visited:
        visited.add(current)
        path = _module_path(project_root, current)
        if path is not None:
            return path
        target = aliases.get(current)
        if target is None:
            break
        current = target
    raise FileNotFoundError(
        f"Historical module {module_name!r} has no canonical source target; chain={sorted(visited)}"
    )


def legacy_source_contract(
    project_root: str | Path,
    legacy_relative_path: str,
) -> LegacySourceContract:
    root = _project_root(project_root)
    normalized = legacy_relative_path.replace("\\", "/").lstrip("/")
    direct = (root / normalized).resolve()
    try:
        direct.relative_to(root)
    except ValueError as exc:
        raise KeyError(f"Historical source path escapes project root: {legacy_relative_path}") from exc
    if direct.is_file():
        return LegacySourceContract(root, normalized, (direct,), annotate_sources=False)
    asset_mappings = {
        "okcanvas_agent_runtime/operations_console/assets/": "operations_console.assets",
        "okcanvas_agent_runtime/interactive_runner/assets/": "interactive_runner.assets",
        "okcanvas_agent_runtime/tui_client/": "tui_client.package",
    }
    for prefix, logical_asset in asset_mappings.items():
        if normalized.startswith(prefix):
            suffix = normalized[len(prefix):]
            target = (component_asset_root(root, logical_asset) / suffix).resolve()
            if not target.is_file():
                raise FileNotFoundError(target)
            return LegacySourceContract(root, normalized, (target,))

    if normalized.startswith("okcanvas_agent_runtime/") and not normalized.endswith(".py"):
        module = normalized.rstrip("/").replace("/", ".")
        target = _resolve_alias_target(root, module)
        if target.name != "__init__.py":
            raise KeyError(f"Historical package path does not resolve to a package: {legacy_relative_path}")
        return LegacySourceContract(root, module, (target,), annotate_sources=False)

    if not normalized.startswith("okcanvas_agent_runtime/") or not normalized.endswith(".py"):
        raise KeyError(f"Unsupported historical source path: {legacy_relative_path}")
    module = normalized[:-3].replace("/", ".")
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]
    logical = module.removeprefix("okcanvas_agent_runtime.")
    if logical in _COMPONENT_PATHS:
        paths = component_source_paths(root, logical)
    else:
        paths = (_resolve_alias_target(root, module),)
    return LegacySourceContract(root, logical, paths)
