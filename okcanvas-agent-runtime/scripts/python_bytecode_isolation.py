from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
ENV_NAME = "PYTHONPYCACHEPREFIX"
SCHEMA_VERSION = "okcanvas-python-bytecode-isolation-v1"


def build_isolated_environment(
    base_environment: Mapping[str, str] | None = None,
    *,
    temp_root: Path | None = None,
) -> tuple[dict[str, str], Path, bool]:
    environment = dict(base_environment or os.environ)
    existing = environment.get(ENV_NAME, "").strip()
    if existing:
        return environment, Path(existing), False

    parent = temp_root if temp_root is not None else Path(tempfile.gettempdir())
    parent.mkdir(parents=True, exist_ok=True)
    prefix = Path(
        tempfile.mkdtemp(prefix="okcanvas-agent-runtime-pycache-", dir=str(parent))
    ).resolve()
    environment[ENV_NAME] = str(prefix)
    return environment, prefix, True


def run_isolated_python(arguments: list[str]) -> int:
    if not arguments:
        raise ValueError("A Python script path is required")

    target = Path(arguments[0])
    if not target.is_absolute():
        target = (ROOT / target).resolve()
    else:
        target = target.resolve()
    try:
        target.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("The target script must be inside the project root") from exc
    if target.suffix.casefold() != ".py" or not target.is_file():
        raise ValueError("The target must be an existing Python script")

    environment, prefix, owns_prefix = build_isolated_environment()
    try:
        completed = subprocess.run(
            [sys.executable, str(target), *arguments[1:]],
            cwd=ROOT,
            env=environment,
            check=False,
        )
        return completed.returncode
    finally:
        if owns_prefix:
            shutil.rmtree(prefix, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python_bytecode_isolation")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        return run_isolated_python(list(args.arguments))
    except (OSError, ValueError) as exc:
        print(f"[ERROR] Python bytecode isolation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
