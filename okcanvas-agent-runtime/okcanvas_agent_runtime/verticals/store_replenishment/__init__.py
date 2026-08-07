"""Store-replenishment vertical with lazy compatibility exports."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "JSON_SAFE_INTEGER_MAX",
    "MAX_DERIVED_ITEM_UNIT_VALUE",
    "MAX_INVENTORY_UNIT_VALUE",
    "MAX_REPLENISHMENT_ITEM_COUNT",
    "StoreReplenishmentInput",
    "StoreReplenishmentInputItem",
    "build_store_replenishment_result",
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module = import_module("okcanvas_agent_runtime.verticals.store_replenishment.store_replenishment")
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(globals().keys() | _EXPORTS)


__all__ = sorted(_EXPORTS)
