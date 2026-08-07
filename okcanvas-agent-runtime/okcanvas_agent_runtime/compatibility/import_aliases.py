"""Lazy compatibility aliases for pre-STEP081 Python import paths."""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

_ALIAS_PATH = Path(__file__).with_name("aliases.json")
ALIASES: dict[str, str] = json.loads(_ALIAS_PATH.read_text(encoding="utf-8"))["aliases"]


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, alias: str, target: str) -> None:
        self.alias = alias
        self.target = target

    def create_module(self, spec):  # noqa: ANN001
        module = importlib.import_module(self.target)
        sys.modules[self.alias] = module
        return module

    def exec_module(self, module: ModuleType) -> None:
        sys.modules[self.alias] = module


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):  # noqa: ANN001
        canonical = ALIASES.get(fullname)
        if canonical is None:
            return None
        target_spec = importlib.util.find_spec(canonical)
        if target_spec is None:
            raise ModuleNotFoundError(f"compatibility alias target not found: {fullname} -> {canonical}")
        return importlib.util.spec_from_loader(
            fullname,
            _AliasLoader(fullname, canonical),
            is_package=target_spec.submodule_search_locations is not None,
        )


def install_import_aliases() -> None:
    if not any(isinstance(item, _AliasFinder) for item in sys.meta_path):
        sys.meta_path.insert(0, _AliasFinder())
