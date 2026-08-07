from __future__ import annotations

import json
import locale
import os
import shutil
import sys
import subprocess
from pathlib import Path
from typing import Any, Sequence, TextIO

REQUIRED_WORKSPACE_PATHS = (
    "okcanvas-agent-runtime/pyproject.toml",
    "okcanvas-agent-cli/package.json",
    "okcanvas-connectors/groupware-mcp-server/pyproject.toml",
    "okcanvas-connectors/organization-context-mcp-server/pyproject.toml",
    "okcanvas-connector-examples/groupware/groupware-api-fake/package.json",
    "okcanvas-connector-examples/organization-context/organization-context-api-fake/package.json",
)


def workspace_root_errors(root: Path) -> list[str]:
    errors: list[str] = []
    if root.name != "okcanvas-agent-platform":
        errors.append(f"workspace root directory must be named okcanvas-agent-platform: {root}")
    for relative in REQUIRED_WORKSPACE_PATHS:
        if not (root / relative).is_file():
            errors.append(f"required workspace path is missing: {relative}")
    if (root / "pyproject.toml").is_file():
        errors.append("workspace launcher is running from a product project root, not the management workspace root")
    return errors


def resolve_executable(name: str) -> str:
    candidates = [name]
    if os.name == "nt" and Path(name).suffix == "":
        candidates.extend([f"{name}.cmd", f"{name}.exe", f"{name}.bat"])
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return str(Path(resolved).resolve())
    raise FileNotFoundError(f"required executable was not found on PATH: {name}")



def _python_module_probe(executable: str, modules: Sequence[str]) -> tuple[bool, str]:
    if not modules:
        return True, ""
    code = "\n".join(f"import {module}" for module in modules)
    completed = subprocess.run(
        [executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=False,
    )
    if completed.returncode == 0:
        return True, ""
    stderr, _ = decode_process_output(completed.stderr)
    stdout, _ = decode_process_output(completed.stdout)
    return False, (stderr or stdout).strip()


def resolve_project_python(
    project_root: Path,
    *,
    required_modules: Sequence[str] = (),
    fallback_executable: str | None = None,
    allow_fallback: bool = True,
) -> str:
    """Resolve the Python interpreter owned by one product project.

    Windows Workspace acceptance is only an orchestrator. Runtime and Connector must
    execute with their own ``.venv`` interpreters. A dependency-capable fallback is
    permitted for deterministic non-Windows packaging environments where local virtual
    environments are intentionally excluded from the ZIP.
    """
    candidates = (
        project_root / ".venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "Scripts" / "python",
        project_root / ".venv" / "bin" / "python",
        project_root / ".venv" / "bin" / "python3",
    )
    diagnostics: list[str] = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        resolved = str(candidate.resolve())
        ok, detail = _python_module_probe(resolved, required_modules)
        if ok:
            return resolved
        diagnostics.append(f"{resolved}: {detail}")

    fallback = fallback_executable or sys.executable
    if allow_fallback and fallback:
        resolved_fallback = str(Path(fallback).resolve())
        ok, detail = _python_module_probe(resolved_fallback, required_modules)
        if ok:
            return resolved_fallback
        diagnostics.append(f"{resolved_fallback}: {detail}")

    required = ", ".join(required_modules) or "project dependencies"
    details = "; ".join(diagnostics) if diagnostics else "no candidate interpreter exists"
    raise FileNotFoundError(
        f"project Python environment is not ready for {project_root}: required={required}; "
        f"details={details}. Run sh_setup_workspace.cmd from the Workspace root."
    )

def prepare_invocation(
    executable: str,
    arguments: Sequence[str],
    *,
    platform_name: str | None = None,
) -> tuple[list[str] | str, bool]:
    platform = os.name if platform_name is None else platform_name
    command = [executable, *arguments]
    if platform == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        return subprocess.list2cmdline(command), True
    return command, False


def decode_process_output(
    data: bytes | None,
    *,
    preferred_encoding: str | None = None,
) -> tuple[str, str]:
    """Decode captured subprocess bytes without relying on the parent console code page.

    Node/npm frequently emits UTF-8 even when Windows Python's preferred text encoding is CP949.
    Python child processes may emit the local Windows encoding. Try UTF-8 first, then the explicit
    or platform-preferred encoding, and finally replacement decoding so reader threads can never fail.
    """
    if not data:
        return "", "empty"

    candidates: list[str] = ["utf-8"]
    preferred = preferred_encoding or locale.getpreferredencoding(False)
    if preferred and preferred.lower().replace("-", "") not in {"utf8", "utf_8"}:
        candidates.append(preferred)
    if os.name == "nt" and all(name.lower().replace("-", "") != "cp949" for name in candidates):
        candidates.append("cp949")

    seen: set[str] = set()
    for encoding in candidates:
        key = encoding.lower().replace("-", "")
        if key in seen:
            continue
        seen.add(key)
        try:
            return data.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue

    return data.decode("utf-8", errors="replace"), "utf-8-replace"


def render_json_for_console(
    value: Any,
    *,
    encoding: str | None,
    indent: int | None = 2,
    sort_keys: bool = True,
) -> tuple[str, str, bool]:
    """Render JSON without assuming the parent console can encode every Unicode character.

    Windows redirected stdout commonly uses CP949. The detailed evidence remains UTF-8 on disk,
    while console output falls back to JSON's ASCII escape form only when the selected console
    encoding cannot represent the payload. The fallback remains valid JSON and round-trips to the
    original value, including symbols and supplementary-plane characters.
    """
    selected = encoding or "utf-8"
    readable = json.dumps(value, ensure_ascii=False, indent=indent, sort_keys=sort_keys)
    try:
        readable.encode(selected)
        return readable, selected, False
    except (UnicodeEncodeError, LookupError):
        escaped = json.dumps(value, ensure_ascii=True, indent=indent, sort_keys=sort_keys)
        return escaped, "ascii-json-escape", True


def write_json_stdout(
    value: Any,
    *,
    stream: TextIO | None = None,
    indent: int | None = 2,
    sort_keys: bool = True,
) -> tuple[str, bool]:
    """Write one JSON document to stdout without raising UnicodeEncodeError."""
    target = sys.stdout if stream is None else stream
    text, encoding, escaped = render_json_for_console(
        value,
        encoding=getattr(target, "encoding", None),
        indent=indent,
        sort_keys=sort_keys,
    )
    target.write(text + "\n")
    target.flush()
    return encoding, escaped



def run_process_to_files(
    executable: str,
    arguments: Sequence[str],
    *,
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run one direct child without pipe-EOF dependence on inherited descendant handles.

    Some acceptance subprocesses exercise SDK/pytest boundaries that may leave a short-lived
    descendant holding inherited stdout/stderr handles. ``capture_output=True`` then waits for EOF
    after the direct child has already exited. File-backed capture makes direct-child completion the
    process boundary while preserving byte-safe diagnostics on disk.
    """
    invocation, use_shell = prepare_invocation(executable, arguments)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with stdout_path.open("wb") as stdout_stream, stderr_path.open("wb") as stderr_stream:
            completed = subprocess.run(
                invocation,
                cwd=cwd,
                env=env,
                stdout=stdout_stream,
                stderr=stderr_stream,
                check=False,
                shell=use_shell,
            )
        stdout, stdout_encoding = decode_process_output(stdout_path.read_bytes())
        stderr, stderr_encoding = decode_process_output(stderr_path.read_bytes())
        return {
            "command": [executable, *arguments],
            "cwd": str(cwd),
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_encoding": stdout_encoding,
            "stderr_encoding": stderr_encoding,
            "shell": use_shell,
            "capture_mode": "file-backed-direct-child",
        }
    except FileNotFoundError as exc:
        return {
            "command": [executable, *arguments],
            "cwd": str(cwd),
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
            "stdout_encoding": "empty",
            "stderr_encoding": "exception-text",
            "shell": use_shell,
            "capture_mode": "file-backed-direct-child",
        }

def run_process(
    executable: str,
    arguments: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    invocation, use_shell = prepare_invocation(executable, arguments)
    try:
        completed = subprocess.run(
            invocation,
            cwd=cwd,
            env=env,
            text=False,
            capture_output=True,
            check=False,
            shell=use_shell,
        )
        stdout, stdout_encoding = decode_process_output(completed.stdout)
        stderr, stderr_encoding = decode_process_output(completed.stderr)
        return {
            "command": [executable, *arguments],
            "cwd": str(cwd),
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_encoding": stdout_encoding,
            "stderr_encoding": stderr_encoding,
            "shell": use_shell,
        }
    except FileNotFoundError as exc:
        return {
            "command": [executable, *arguments],
            "cwd": str(cwd),
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
            "stdout_encoding": "empty",
            "stderr_encoding": "exception-text",
            "shell": use_shell,
        }
