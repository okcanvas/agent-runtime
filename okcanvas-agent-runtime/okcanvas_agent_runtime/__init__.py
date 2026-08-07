"""Evidence-first OKCanvas Agent Runtime."""

from .compatibility import install_import_aliases, install_legacy_product_tool_executors

install_import_aliases()
install_legacy_product_tool_executors()

from .core.baseline import PROJECT_VERSION

__version__ = PROJECT_VERSION
