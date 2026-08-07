from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


MAX_CAPTURE_CHARS = 20000


def _bounded(value: str) -> str:
    return value[-MAX_CAPTURE_CHARS:]


def _parse_json_output(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("validator produced empty stdout")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise TypeError("validator JSON payload must be an object")
    return payload


def run_json_python_validator(
    *,
    root: Path,
    script: Path,
    timeout_seconds: float = 180.0,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    resolved_root = root.resolve()
    resolved_script = script.resolve()
    environment = os.environ.copy()
    current_pythonpath = environment.get("PYTHONPATH", "")
    retained = [
        value
        for value in current_pythonpath.split(os.pathsep)
        if value and os.path.normcase(os.path.realpath(value)) != os.path.normcase(os.path.realpath(resolved_root))
    ]
    environment["PYTHONPATH"] = os.pathsep.join((str(resolved_root), *retained))
    environment["OKCANVAS_VALIDATION_PROJECT_ROOT"] = str(resolved_root)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, str(resolved_script)]
    try:
        completed = subprocess.run(
            command,
            cwd=resolved_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, {
            "schema_version": "okcanvas-json-subprocess-validator-v1",
            "script": resolved_script.relative_to(resolved_root).as_posix(),
            "completed": False,
            "returncode": None,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:2000],
            "stdout": "",
            "stderr": "",
        }

    payload: dict[str, Any] | None = None
    parse_error: str | None = None
    try:
        payload = _parse_json_output(completed.stdout)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        parse_error = f"{type(exc).__name__}: {exc}"

    diagnostic = {
        "schema_version": "okcanvas-json-subprocess-validator-v1",
        "script": resolved_script.relative_to(resolved_root).as_posix(),
        "completed": True,
        "returncode": completed.returncode,
        "json_parsed": payload is not None,
        "parse_error": parse_error,
        "stdout": _bounded(completed.stdout),
        "stderr": _bounded(completed.stderr),
    }
    return payload, diagnostic
