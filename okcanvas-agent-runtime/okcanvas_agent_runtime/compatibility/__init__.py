"""Bounded compatibility support for pre-STEP081 imports and call surfaces."""
from __future__ import annotations

from .import_aliases import ALIASES, install_import_aliases


def install_legacy_product_tool_executors() -> None:
    """Bind historical synchronous Tool calls without adding Agent→Adapter imports."""
    from okcanvas_agent_runtime.adapters.workspace.tool_inspection import project_readonly_inspect
    from okcanvas_agent_runtime.agent.tools.function.factories import (
        install_legacy_project_inspect_executor,
    )

    install_legacy_project_inspect_executor(project_readonly_inspect)


__all__ = ["ALIASES", "install_import_aliases", "install_legacy_product_tool_executors"]
