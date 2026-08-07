from __future__ import annotations

import os

import uvicorn

from .app import create_app


def main() -> None:
    host = os.environ.get("OKCANVAS_CONNECTOR_HOST", "127.0.0.1")
    port = int(os.environ.get("OKCANVAS_CONNECTOR_PORT", "18081"))
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
