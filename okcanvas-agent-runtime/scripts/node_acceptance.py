from __future__ import annotations

import hashlib
import json
import locale
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Sequence

WINDOWS_BATCH_SUFFIXES = {".bat", ".cmd"}
TYPESCRIPT_COMPILER_RELATIVE_PATHS = (
    Path("node_modules/typescript/bin/tsc"),
    Path("node_modules/typescript/bin/tsc.js"),
    Path("node_modules/typescript/lib/tsc.js"),
)
NODE_RELEASE_MANIFEST = "typescript-release-manifest.json"
NODE_RELEASE_MANIFEST_SCHEMA = "okcanvas-node-typescript-release-manifest-v1"


def _decode_output(raw: bytes) -> str:
    encodings: list[str] = ["utf-8"]
    preferred = locale.getpreferredencoding(False)
    if preferred and preferred.lower() not in {item.lower() for item in encodings}:
        encodings.append(preferred)
    if os.name == "nt":
        for encoding in ("mbcs", "cp949"):
            if encoding.lower() not in {item.lower() for item in encodings}:
                encodings.append(encoding)
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _has_path_separator(value: str) -> bool:
    return "/" in value or "\\" in value


def resolve_subprocess_command(
    command: Sequence[str],
    *,
    platform_name: str | None = None,
    comspec: str | None = None,
    which: Any | None = None,
) -> list[str]:
    """Resolve one argv command without relying on Windows shell/PATHEXT side effects.

    Python launches subprocesses with ``shell=False``. Native executables such as
    ``node.exe`` are safe in that mode, but npm/npx/tsc are commonly installed as
    ``.cmd`` shims on Windows and must be invoked through ``cmd.exe``. This helper
    resolves the executable first and wraps every discovered ``.cmd``/``.bat``
    command deterministically.
    """
    if not command:
        raise RuntimeError("subprocess command must not be empty")
    resolver = shutil.which if which is None else which
    platform_name = os.name if platform_name is None else platform_name
    program = os.fspath(command[0])
    arguments = [os.fspath(item) for item in command[1:]]

    resolved = program
    path = Path(program)
    if not _has_path_separator(program) and not path.is_absolute():
        candidates = [program]
        if platform_name == "nt" and not path.suffix:
            candidates = [f"{program}.cmd", f"{program}.bat", program]
        for candidate in candidates:
            found = resolver(candidate)
            if found:
                resolved = found
                break

    if platform_name == "nt" and Path(resolved).suffix.lower() in WINDOWS_BATCH_SUFFIXES:
        command_processor = comspec or os.environ.get("COMSPEC") or resolver("cmd.exe")
        if not command_processor:
            raise RuntimeError("Windows command processor not found")
        return [command_processor, "/d", "/c", "call", resolved, *arguments]
    return [resolved, *arguments]


def run_command(command: Sequence[str], cwd: Path) -> tuple[bool, str]:
    try:
        prepared = resolve_subprocess_command(command)
        completed = subprocess.run(
            prepared,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except (OSError, RuntimeError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return completed.returncode == 0, _decode_output(completed.stdout).strip()


def npm_script_command(
    npm: str,
    script: str,
    *,
    platform_name: str | None = None,
    comspec: str | None = None,
) -> list[str]:
    """Retained only for STEP062A failure evidence and non-acceptance callers."""
    platform_name = os.name if platform_name is None else platform_name
    if platform_name == "nt":
        command_processor = comspec or os.environ.get("COMSPEC") or shutil.which("cmd.exe")
        if not command_processor:
            raise RuntimeError("Windows command processor not found")
        return [command_processor, "/d", "/c", "call", npm, "run", script]
    return [npm, "run", script]


def run_npm_script(script: str, cwd: Path) -> tuple[bool, str]:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        return False, "npm executable not found"
    try:
        command = npm_script_command(npm, script)
    except RuntimeError as exc:
        return False, str(exc)
    return run_command(command, cwd)


def run_npm_pack(cwd: Path) -> tuple[bool, str]:
    """Run the network-free npm pack inspection through the portable resolver."""
    return run_command(["npm", "pack", "--dry-run", "--json"], cwd)


def _add_candidate(candidates: list[Path], candidate: Path) -> None:
    normalized = candidate.resolve(strict=False)
    if normalized not in candidates:
        candidates.append(normalized)


def typescript_compiler_candidates(cwd: Path, tsc_command: str) -> list[Path]:
    """Historical STEP062B compiler candidates retained for exact failure evidence."""
    candidates: list[Path] = []
    for relative in TYPESCRIPT_COMPILER_RELATIVE_PATHS:
        _add_candidate(candidates, cwd / relative)

    shim = Path(tsc_command)
    resolved = shim.resolve(strict=False)
    if shim.suffix.lower() not in WINDOWS_BATCH_SUFFIXES:
        _add_candidate(candidates, resolved)

    for parent in (shim.parent, resolved.parent):
        for relative in TYPESCRIPT_COMPILER_RELATIVE_PATHS:
            _add_candidate(candidates, parent / relative)

    for parent in (shim.parent, resolved.parent):
        if parent.name.lower() == "bin":
            for relative in (
                Path("../lib/node_modules/typescript/bin/tsc"),
                Path("../lib/node_modules/typescript/bin/tsc.js"),
                Path("../lib/node_modules/typescript/lib/tsc.js"),
            ):
                _add_candidate(candidates, parent / relative)
    return candidates


def resolve_typescript_compiler(cwd: Path, tsc_command: str | None = None) -> Path:
    command = tsc_command or shutil.which("tsc.cmd") or shutil.which("tsc")
    if not command:
        raise RuntimeError("TypeScript compiler command not found on PATH")
    candidates = typescript_compiler_candidates(cwd, command)
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() not in WINDOWS_BATCH_SUFFIXES:
            return candidate
    searched = ", ".join(str(item) for item in candidates)
    raise RuntimeError(f"TypeScript compiler JavaScript entrypoint not found; searched: {searched}")


def typescript_build_command(
    node: str,
    cwd: Path,
    *,
    tsc_command: str | None = None,
) -> list[str]:
    compiler = resolve_typescript_compiler(cwd, tsc_command)
    return [node, str(compiler), "-p", "tsconfig.json"]


def run_typescript_build(cwd: Path) -> tuple[bool, str]:
    """Historical direct-compiler attempt retained for STEP062B evidence only."""
    node = shutil.which("node.exe") or shutil.which("node")
    if not node:
        return False, "node executable not found"
    try:
        command = typescript_build_command(node, cwd)
    except RuntimeError as exc:
        return False, str(exc)
    return run_command(command, cwd)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_file_hashes(root: Path, paths: Sequence[Path]) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix())
    }


def node_release_input_files(cwd: Path) -> list[Path]:
    files = [cwd / "package.json", cwd / "package-lock.json", cwd / "tsconfig.json"]
    files.extend(path for path in (cwd / "src").rglob("*.ts") if path.is_file())
    return sorted(files, key=lambda item: item.relative_to(cwd).as_posix())


def node_release_output_files(cwd: Path) -> list[Path]:
    return sorted(
        (path for path in (cwd / "dist").rglob("*") if path.is_file()),
        key=lambda item: item.relative_to(cwd).as_posix(),
    )


def node_release_test_files(cwd: Path) -> list[Path]:
    return sorted(
        (path for path in (cwd / "test").glob("*.test.mjs") if path.is_file()),
        key=lambda item: item.relative_to(cwd).as_posix(),
    )


def build_node_release_manifest(cwd: Path, *, typescript_version: str) -> dict[str, Any]:
    package = json.loads((cwd / "package.json").read_text(encoding="utf-8"))
    return {
        "schema_version": NODE_RELEASE_MANIFEST_SCHEMA,
        "package_name": package.get("name"),
        "package_version": package.get("version"),
        "artifact_mode": "committed-typescript-dist",
        "release_build": {
            "tool": "typescript",
            "version": typescript_version,
            "command": "tsc -p tsconfig.json",
            "dist_reproduced_byte_identical": True,
        },
        "acceptance": {
            "external_typescript_compiler_required": False,
            "npm_install_required": False,
            "network_required": False,
            "validation": "manifest-sha256+source-map-contract+dist-syntax+node-tests",
        },
        "inputs": _relative_file_hashes(cwd, node_release_input_files(cwd)),
        "outputs": _relative_file_hashes(cwd, node_release_output_files(cwd)),
        "tests": _relative_file_hashes(cwd, node_release_test_files(cwd)),
    }


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def _validate_source_maps(cwd: Path) -> list[str]:
    errors: list[str] = []
    maps = sorted((cwd / "dist").glob("*.js.map"))
    javascript = sorted((cwd / "dist").glob("*.js"))
    if len(maps) != len(javascript):
        errors.append(f"source map count {len(maps)} != JavaScript count {len(javascript)}")
    for map_path in maps:
        try:
            payload = _read_object(map_path)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"invalid source map {map_path.name}: {exc}")
            continue
        expected_js = map_path.name.removesuffix(".map")
        if payload.get("file") != expected_js:
            errors.append(f"source map file mismatch: {map_path.name}")
        sources = payload.get("sources")
        if not isinstance(sources, list) or len(sources) != 1 or not isinstance(sources[0], str):
            errors.append(f"source map sources invalid: {map_path.name}")
            continue
        source_path = (map_path.parent / sources[0]).resolve(strict=False)
        if not source_path.is_file() or cwd.resolve() not in source_path.parents:
            errors.append(f"source map source missing/outside package: {map_path.name}")
    return errors


def validate_committed_typescript_release(cwd: Path) -> tuple[bool, str]:
    """Validate the packaged TypeScript source and committed dist without external tsc.

    The CLI product executes committed `dist/*.js`, declares no TypeScript dependency, and ships no
    `node_modules`. Release creation performs the real `tsc` build and records the exact input/output
    hashes. Windows acceptance verifies that immutable release pair, JS syntax, and Node tests.
    """
    manifest_path = cwd / NODE_RELEASE_MANIFEST
    if not manifest_path.is_file():
        return False, f"Node release manifest missing: {manifest_path}"
    try:
        manifest = _read_object(manifest_path)
        package = _read_object(cwd / "package.json")
        lock = _read_object(cwd / "package-lock.json")
    except (OSError, ValueError, TypeError) as exc:
        return False, str(exc)

    errors: list[str] = []
    if manifest.get("schema_version") != NODE_RELEASE_MANIFEST_SCHEMA:
        errors.append("release manifest schema mismatch")
    if manifest.get("package_name") != package.get("name"):
        errors.append("release manifest package name mismatch")
    if manifest.get("package_version") != package.get("version"):
        errors.append("release manifest package version mismatch")
    acceptance = manifest.get("acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("external_typescript_compiler_required") is not False:
        errors.append("external TypeScript compiler acceptance contract mismatch")
    if package.get("dependencies") or package.get("devDependencies"):
        errors.append("Node CLI package must retain zero npm dependencies")
    packages = lock.get("packages")
    if not isinstance(packages, dict) or set(packages) != {""}:
        errors.append("package-lock must retain only the root package")
    if (cwd / "node_modules").exists():
        errors.append("node_modules must not be packaged")
    temporary_sources = sorted((cwd / "src").rglob("*.tmp"))
    if temporary_sources:
        errors.append("temporary source files present: " + ", ".join(path.name for path in temporary_sources))

    expected_groups = {
        "inputs": _relative_file_hashes(cwd, node_release_input_files(cwd)),
        "outputs": _relative_file_hashes(cwd, node_release_output_files(cwd)),
        "tests": _relative_file_hashes(cwd, node_release_test_files(cwd)),
    }
    for group, actual in expected_groups.items():
        recorded = manifest.get(group)
        if recorded != actual:
            errors.append(f"release manifest {group} hash set mismatch")

    outputs = expected_groups["outputs"]
    expected_suffix_counts = {".js": 7, ".ts": 7, ".map": 7}
    actual_suffix_counts = {
        ".js": sum(1 for item in outputs if item.endswith(".js")),
        ".ts": sum(1 for item in outputs if item.endswith(".d.ts")),
        ".map": sum(1 for item in outputs if item.endswith(".js.map")),
    }
    if actual_suffix_counts != expected_suffix_counts:
        errors.append(f"compiled dist shape mismatch: {actual_suffix_counts}")
    errors.extend(_validate_source_maps(cwd))

    node = shutil.which("node.exe") or shutil.which("node")
    if not node:
        errors.append("node executable not found")
    else:
        for path in sorted((cwd / "dist").glob("*.js")):
            ok, output = run_command([node, "--check", str(path.relative_to(cwd))], cwd)
            if not ok:
                errors.append(f"Node syntax failed for {path.name}: {output}")

    if errors:
        return False, "\n".join(errors)
    return True, (
        "COMMITTED_TYPESCRIPT_RELEASE_VERIFIED "
        f"inputs={len(expected_groups['inputs'])} outputs={len(outputs)} "
        f"tests={len(expected_groups['tests'])} external_tsc_required=false"
    )


def node_test_command(node: str, cwd: Path) -> list[str]:
    test_files = node_release_test_files(cwd)
    if not test_files:
        raise RuntimeError(f"Node test files not found: {cwd / 'test'}")
    return [node, "--test", *(str(path.relative_to(cwd)) for path in test_files)]


def run_node_tests(cwd: Path) -> tuple[bool, str]:
    node = shutil.which("node.exe") or shutil.which("node")
    if not node:
        return False, "node executable not found"
    try:
        command = node_test_command(node, cwd)
    except RuntimeError as exc:
        return False, str(exc)
    return run_command(command, cwd)
