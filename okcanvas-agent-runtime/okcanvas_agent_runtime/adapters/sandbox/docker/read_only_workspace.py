from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from okcanvas_agent_runtime.adapters.workspace import inspect_readonly_project

from okcanvas_agent_runtime.adapters.sandbox.docker.docker_cli import DockerCommandRunner, DockerImageBinding, DockerSandboxLifecycleService, docker_operation_name, docker_stderr_category
from okcanvas_agent_runtime.adapters.sandbox.docker.errors import SandboxDockerError
from okcanvas_agent_runtime.adapters.sandbox.docker.models import SandboxRuntimeFoundation

_EXCLUDED_NAMES = frozenset({
    ".git", ".hg", ".svn", ".idea", ".vscode", ".venv", "venv", "node_modules",
    "dist", "build", "target", "coverage", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".local", "reference",
})
_TEXT_FILENAMES = frozenset({
    "README", "README.md", "AGENTS.md", "HANDOFF.md", "PLANS.md", "ROADMAP.md",
    "Makefile", "Dockerfile", "package.json", "package-lock.json", "pyproject.toml",
    "requirements.txt", "pom.xml", "build.gradle", "settings.gradle", "go.mod", "Cargo.toml",
})
_TEXT_SUFFIXES = frozenset({
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".kt",
    ".kts", ".go", ".rs", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php", ".rb",
    ".scala", ".sql", ".graphql", ".proto", ".xml", ".html", ".css", ".scss", ".vue",
    ".svelte", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".properties", ".md", ".txt", ".sh", ".bash", ".zsh", ".cmd", ".bat", ".ps1",
})
_SAFE_ACCEPTANCE_ID = re.compile(r"^[a-z0-9-]{8,64}$")
_SNAPSHOT_MANIFEST_PATH = ".okcanvas-snapshot-manifest.json"
_SAFE_RELATIVE = re.compile(r"^[A-Za-z0-9._/@+-][A-Za-z0-9._/@+ -]{0,510}$")


def _parse_tmpfs_size_bytes(value: str) -> int | None:
    text = value.strip().casefold()
    match = re.fullmatch(r"(\d+)([kmgt]?i?b?)?", text)
    if match is None:
        return None
    amount = int(match.group(1))
    suffix = (match.group(2) or "").replace("ib", "i").replace("b", "")
    multipliers = {"": 1, "k": 1024, "ki": 1024, "m": 1024**2, "mi": 1024**2, "g": 1024**3, "gi": 1024**3, "t": 1024**4, "ti": 1024**4}
    multiplier = multipliers.get(suffix)
    return None if multiplier is None else amount * multiplier


def _parse_tmpfs_mode(value: str) -> int | None:
    text = value.strip().casefold()
    if text.startswith("0o"):
        text = text[2:]
    if not re.fullmatch(r"[0-7]{3,4}", text):
        return None
    return int(text, 8)


def _tmpfs_workspace_semantically_matches(value: object, *, size_bytes: int) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    flags: set[str] = set()
    options: dict[str, str] = {}
    for raw_token in value.split(","):
        token = raw_token.strip().casefold()
        if not token:
            return False
        if "=" in token:
            key, option_value = token.split("=", 1)
            if not key or not option_value or key in options:
                return False
            options[key] = option_value
        else:
            flags.add(token)
    required_flags = {"rw", "noexec", "nosuid", "nodev"}
    forbidden_flags = {"ro", "exec", "suid", "dev"}
    if not required_flags.issubset(flags) or forbidden_flags.intersection(flags):
        return False
    if flags - required_flags - {"relatime", "noatime", "nodiratime", "strictatime"}:
        return False
    if set(options) != {"size", "uid", "gid", "mode"}:
        return False
    try:
        uid = int(options["uid"], 10)
        gid = int(options["gid"], 10)
    except ValueError:
        return False
    return (
        _parse_tmpfs_size_bytes(options["size"]) == size_bytes
        and uid == 0
        and gid == 0
        and _parse_tmpfs_mode(options["mode"]) == 0o755
    )


@dataclass(frozen=True)
class SandboxSnapshotEntry:
    path: str
    sha256: str
    bytes: int

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "sha256": self.sha256, "bytes": self.bytes}


@dataclass(frozen=True)
class SandboxReadonlySnapshot:
    source_label: str
    snapshot_sha256: str
    file_count: int
    total_bytes: int
    entries: tuple[SandboxSnapshotEntry, ...]
    staging_root: Path


@dataclass(frozen=True)
class SandboxReadonlyLifecycle:
    acceptance_id: str
    image: DockerImageBinding
    container_id: str
    container_name: str
    docker_call_count: int
    command_operations: tuple[str, ...]
    snapshot_sha256: str
    snapshot_file_count: int
    snapshot_total_bytes: int
    materialized_file_count: int
    selected_file_hashes_verified: bool
    security: dict[str, object]
    deleted: bool
    orphan_count: int
    cleanup_state: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "acceptance_id": self.acceptance_id,
            "image": self.image.to_public_dict(),
            "container_id": self.container_id,
            "container_name": self.container_name,
            "docker_call_count": self.docker_call_count,
            "command_operations": list(self.command_operations),
            "snapshot_sha256": self.snapshot_sha256,
            "snapshot_file_count": self.snapshot_file_count,
            "snapshot_total_bytes": self.snapshot_total_bytes,
            "materialized_file_count": self.materialized_file_count,
            "selected_file_hashes_verified": self.selected_file_hashes_verified,
            "security": dict(self.security),
            "deleted": self.deleted,
            "orphan_count": self.orphan_count,
            "cleanup_state": self.cleanup_state,
        }


@dataclass(frozen=True)
class SandboxReadonlyInspection:
    inspection: object
    lifecycle: SandboxReadonlyLifecycle


def _is_text_candidate(path: Path) -> bool:
    return path.name in _TEXT_FILENAMES or path.suffix.lower() in _TEXT_SUFFIXES


def _decode_text(raw: bytes) -> str | None:
    if b"\x00" in raw:
        return None
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _safe_source_root(root: str | Path) -> Path:
    raw = Path(root).expanduser()
    if raw.is_symlink():
        raise SandboxDockerError("SANDBOX_SOURCE_ROOT_UNSAFE", "Sandbox source root cannot be a symbolic link")
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise SandboxDockerError("SANDBOX_SOURCE_ROOT_MISSING", "Sandbox source root is unavailable") from exc
    if not resolved.is_dir():
        raise SandboxDockerError("SANDBOX_SOURCE_ROOT_INVALID", "Sandbox source root must be a directory")
    return resolved


def _relative_file(path: Path, root: Path) -> str:
    if path.is_symlink():
        raise SandboxDockerError("SANDBOX_SOURCE_SYMLINK_FORBIDDEN", "Sandbox snapshot cannot include symbolic links")
    try:
        relative = path.resolve(strict=True).relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise SandboxDockerError("SANDBOX_SOURCE_PATH_ESCAPE", "Sandbox source path escaped its root") from exc
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or ".." in pure.parts:
        raise SandboxDockerError("SANDBOX_SOURCE_PATH_INVALID", "Sandbox source path is invalid")
    return relative


def build_readonly_snapshot(
    source_root: str | Path,
    *,
    foundation: SandboxRuntimeFoundation,
    temporary_parent: str | Path | None = None,
) -> SandboxReadonlySnapshot:
    root = _safe_source_root(source_root)
    provider = foundation.provider
    staging = Path(tempfile.mkdtemp(prefix="okcanvas-sandbox-readonly-", dir=temporary_parent)).resolve()
    entries: list[SandboxSnapshotEntry] = []
    total = 0
    try:
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
            try:
                relative_parts = path.relative_to(root).parts
            except ValueError as exc:
                raise SandboxDockerError("SANDBOX_SOURCE_PATH_ESCAPE", "Sandbox source path escaped its root") from exc
            if any(part in _EXCLUDED_NAMES for part in relative_parts):
                continue
            if path.is_symlink():
                raise SandboxDockerError("SANDBOX_SOURCE_SYMLINK_FORBIDDEN", "Sandbox snapshot cannot include symbolic links")
            if not path.is_file() or not _is_text_candidate(path):
                continue
            relative = _relative_file(path, root)
            source_raw = path.read_bytes()
            if len(source_raw) > provider.workspace_max_file_bytes:
                continue
            decoded = _decode_text(source_raw)
            if decoded is None:
                continue
            # Canonicalize all accepted source encodings to UTF-8 before hashing and
            # Docker materialization. Docker CLI stdout is UTF-8 text; preserving
            # CP949 bytes would make a correctly decoded container read fail the
            # immutable hash comparison.
            raw = decoded.encode("utf-8")
            if len(raw) > provider.workspace_max_file_bytes:
                continue
            if len(entries) >= provider.workspace_max_files:
                raise SandboxDockerError("SANDBOX_SNAPSHOT_FILE_LIMIT", "Sandbox snapshot exceeds the file limit")
            if total + len(raw) > provider.workspace_max_total_bytes:
                raise SandboxDockerError("SANDBOX_SNAPSHOT_BYTE_LIMIT", "Sandbox snapshot exceeds the byte limit")
            destination = (staging / PurePosixPath(relative)).resolve()
            if staging not in destination.parents:
                raise SandboxDockerError("SANDBOX_STAGING_PATH_ESCAPE", "Sandbox staging path escaped its root")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            entry = SandboxSnapshotEntry(relative, hashlib.sha256(raw).hexdigest(), len(raw))
            entries.append(entry)
            total += len(raw)
        if not entries:
            raise SandboxDockerError("SANDBOX_SNAPSHOT_EMPTY", "Sandbox snapshot contains no bounded text files")
        manifest_payload = {
            "schema_version": "okcanvas-sandbox-readonly-snapshot-v1",
            "entries": [entry.to_dict() for entry in entries],
        }
        canonical = json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        snapshot_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        manifest_payload["snapshot_sha256"] = snapshot_sha
        (staging / _SNAPSHOT_MANIFEST_PATH).write_text(
            json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return SandboxReadonlySnapshot(
            source_label=root.name,
            snapshot_sha256=snapshot_sha,
            file_count=len(entries),
            total_bytes=total,
            entries=tuple(entries),
            staging_root=staging,
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise




def build_readonly_snapshot_archive(snapshot: SandboxReadonlySnapshot) -> bytes:
    """Build one deterministic root-owned GNU tar stream for tmpfs extraction.

    The archive contains only canonical snapshot files and parent directories. It
    carries no host paths, links, devices, timestamps, user names or writable bits.
    """
    file_paths = [entry.path for entry in snapshot.entries] + [_SNAPSHOT_MANIFEST_PATH]
    directories: set[str] = set()
    for path in file_paths:
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts:
            raise SandboxDockerError("SANDBOX_ARCHIVE_PATH_INVALID", "Sandbox archive path is invalid")
        current = pure.parent
        while str(current) not in {"", "."}:
            directories.add(current.as_posix())
            current = current.parent

    buffer = io.BytesIO()
    try:
        with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
            for directory in sorted(directories, key=lambda item: (item.count("/"), item)):
                info = tarfile.TarInfo(directory + "/")
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                archive.addfile(info)
            for path in sorted(file_paths):
                source = (snapshot.staging_root / PurePosixPath(path)).resolve()
                if snapshot.staging_root not in source.parents or not source.is_file() or source.is_symlink():
                    raise SandboxDockerError("SANDBOX_ARCHIVE_SOURCE_INVALID", "Sandbox archive source is invalid")
                raw = source.read_bytes()
                info = tarfile.TarInfo(path)
                info.size = len(raw)
                info.mode = 0o444
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                archive.addfile(info, io.BytesIO(raw))
    except (OSError, tarfile.TarError) as exc:
        raise SandboxDockerError("SANDBOX_ARCHIVE_BUILD_FAILED", "Sandbox snapshot archive could not be built") from exc
    payload = buffer.getvalue()
    maximum = snapshot.total_bytes + (snapshot.file_count + len(directories) + 2) * 4096 + 1024 * 1024
    if len(payload) > maximum:
        raise SandboxDockerError("SANDBOX_ARCHIVE_SIZE_INVALID", "Sandbox snapshot archive exceeded its bound")
    return payload


class ProductOwnedReadonlySandboxInspector:
    """Materialize a bounded snapshot into Docker tmpfs and read selected evidence without Shell."""

    def __init__(self, foundation: SandboxRuntimeFoundation, runner: DockerCommandRunner) -> None:
        self.foundation = foundation
        self.runner = runner
        self._history: list[tuple[str, ...]] = []
        policy = foundation.policy
        provider = foundation.provider
        if not policy.agent_execution_enabled or "sandbox-readonly-v1" not in policy.active_workspace_access_modes:
            raise SandboxDockerError("SANDBOX_READONLY_DISABLED", "Read-only Sandbox Agent execution is disabled")
        if not policy.physical_workspace_materialization_enabled:
            raise SandboxDockerError("SANDBOX_MATERIALIZATION_DISABLED", "Sandbox workspace materialization is disabled")
        if provider.workspace_allowed_commands != ("find", "cat", "grep", "tail"):
            raise SandboxDockerError("SANDBOX_COMMAND_ALLOWLIST_INVALID", "Sandbox command allowlist is invalid")

    @property
    def command_history(self) -> tuple[tuple[str, ...], ...]:
        return tuple(self._history)

    def inspect(
        self,
        *,
        source_root: str | Path,
        query: str,
        image_reference: str,
        acceptance_id: str | None = None,
        temporary_parent: str | Path | None = None,
    ) -> SandboxReadonlyInspection:
        acceptance = acceptance_id or ("step075-" + uuid.uuid4().hex)
        if not _SAFE_ACCEPTANCE_ID.fullmatch(acceptance):
            raise SandboxDockerError("ACCEPTANCE_ID_INVALID", "Acceptance ID is invalid")
        query_value = query.strip()
        if not query_value or len(query_value) > 16_000 or "\x00" in query_value:
            raise SandboxDockerError("SANDBOX_QUERY_INVALID", "Sandbox query is invalid")
        snapshot = build_readonly_snapshot(
            source_root, foundation=self.foundation, temporary_parent=temporary_parent
        )
        container_id: str | None = None
        container_name = f"okcanvas-step075-{acceptance[:32]}"
        deleted = False
        orphan_count: int | None = None
        cleanup_state = "NOT_REQUIRED"
        image: DockerImageBinding | None = None
        security: dict[str, object] = {}
        materialized_file_count = 0
        selected_hashes_verified = False
        failure: SandboxDockerError | None = None
        cleanup_attempted = False
        try:
            resolver = DockerSandboxLifecycleService(self.foundation, self.runner)
            # Preserve one command history owned by this higher-level Product service.
            image = resolver.resolve_local_image(image_reference)
            self._history.extend(resolver.command_history)
            labels = {
                "com.okcanvas.agent-runtime.sandbox": "true",
                "com.okcanvas.agent-runtime.provider": self.foundation.provider.provider_id,
                "com.okcanvas.agent-runtime.step": "STEP075",
                "com.okcanvas.agent-runtime.acceptance-id": acceptance,
            }
            provider = self.foundation.provider
            tmpfs_value = (
                f"{provider.workspace_mount_path}:rw,noexec,nosuid,nodev,"
                f"size={provider.workspace_tmpfs_max_bytes},uid=0,gid=0,mode=0755"
            )
            create_args = [
                "container", "create", "--pull=never", "--name", container_name,
                "--network", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--pids-limit", str(provider.pids_limit),
                "--memory", str(provider.memory_limit_bytes), "--cpus", self._cpu_string(provider.nano_cpus),
                "--user", provider.non_root_user, "--restart", "no", "--stop-timeout",
                str(provider.stop_timeout_seconds), "--no-healthcheck", "--tmpfs", tmpfs_value,
            ]
            for key in provider.required_labels:
                create_args.extend(["--label", f"{key}={labels[key]}"])
            create_args.extend([image.immutable_reference, "tail", "-f", "/dev/null"])
            created = self._checked(create_args)
            container_id = created.stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
                raise SandboxDockerError("CONTAINER_ID_INVALID", "Docker returned an invalid container ID")
            security = self._validate_created_container(container_id, labels, tmpfs_value)
            self._checked(["container", "start", container_id])
            archive_bytes = build_readonly_snapshot_archive(snapshot)
            self._checked_with_input(
                [
                    "container", "exec", "--interactive", "--user",
                    provider.workspace_materializer_user, container_id,
                    *provider.workspace_materializer_command,
                ],
                input_bytes=archive_bytes,
            )
            listed = self._checked(["container", "exec", container_id, "find", provider.workspace_mount_path, "-type", "f"])
            materialized_paths = {
                line.strip()[len(provider.workspace_mount_path) + 1 :]
                for line in listed.stdout.splitlines()
                if line.strip().startswith(provider.workspace_mount_path + "/")
            }
            expected_paths = {entry.path for entry in snapshot.entries} | {_SNAPSHOT_MANIFEST_PATH}
            if materialized_paths != expected_paths:
                raise SandboxDockerError("SANDBOX_MATERIALIZATION_MISMATCH", "Materialized workspace inventory does not match the snapshot")
            materialized_file_count = len(materialized_paths)
            entry_by_path = {entry.path: entry for entry in snapshot.entries}
            host_inspection = inspect_readonly_project(
                snapshot.staging_root,
                query_value,
                allowed_relative_paths=entry_by_path.keys(),
            )
            container_text_by_path: dict[str, str] = {}
            for path in host_inspection.inspected_files:
                self._validate_relative_argument(path)
                expected = entry_by_path.get(path)
                if expected is None:
                    raise SandboxDockerError(
                        "SANDBOX_SELECTED_FILE_NOT_IN_SNAPSHOT",
                        "Selected file is outside the immutable project snapshot",
                    )
                result = self._checked(["container", "exec", container_id, "cat", f"{provider.workspace_mount_path}/{path}"])
                raw = result.stdout.encode("utf-8")
                if hashlib.sha256(raw).hexdigest() != expected.sha256:
                    raise SandboxDockerError("SANDBOX_SELECTED_FILE_HASH_MISMATCH", "Sandbox file differs from the immutable snapshot")
                container_text_by_path[path] = result.stdout
            selected_hashes_verified = True
            # Rebuild evidence excerpts from bytes read inside the container.
            rebuilt_evidence = []
            for evidence in host_inspection.evidence:
                text = container_text_by_path[evidence.path]
                lines = text.splitlines()
                excerpt = "\n".join(lines[evidence.line_start - 1 : evidence.line_end])
                rebuilt_evidence.append(type(evidence)(evidence.path, evidence.line_start, evidence.line_end, excerpt))
            inspection = type(host_inspection)(
                workspace_label="docker-tmpfs:" + snapshot.source_label,
                snapshot_sha256=snapshot.snapshot_sha256,
                files_considered=host_inspection.files_considered,
                bytes_considered=host_inspection.bytes_considered,
                inspected_files=host_inspection.inspected_files,
                evidence=tuple(rebuilt_evidence),
                evidence_characters=sum(len(item.excerpt) for item in rebuilt_evidence),
                query_terms_considered=host_inspection.query_terms_considered,
                truncated=host_inspection.truncated,
            )
        except SandboxDockerError as exc:
            failure = exc
        finally:
            cleanup_attempted = container_id is not None
            if container_id is not None:
                cleanup_state = "ATTEMPTED"
                try:
                    removal = self._call(["container", "rm", "--force", "--volumes", container_id])
                except SandboxDockerError as cleanup_error:
                    deleted = False
                    cleanup_state = "FAILED"
                    if failure is None:
                        failure = cleanup_error
                else:
                    deleted = removal.returncode == 0 and not removal.output_truncated
                    cleanup_state = "COMPLETED" if deleted else "FAILED"
                    if not deleted and failure is None:
                        failure = SandboxDockerError(
                            "DOCKER_COMMAND_FAILED" if removal.returncode != 0 else "DOCKER_OUTPUT_LIMIT_EXCEEDED",
                            "Docker cleanup command failed safely",
                            operation=docker_operation_name(removal.arguments),
                            return_code=removal.returncode,
                            stderr_category=docker_stderr_category(removal),
                            output_truncated=removal.output_truncated,
                        )
            try:
                orphan = self._call([
                    "container", "ls", "--all", "--quiet", "--filter",
                    f"label=com.okcanvas.agent-runtime.acceptance-id={acceptance}",
                ])
            except SandboxDockerError as orphan_error:
                orphan_count = None
                if failure is None:
                    failure = orphan_error
            else:
                if orphan.returncode == 0 and not orphan.output_truncated:
                    orphan_count = len([line for line in orphan.stdout.splitlines() if line.strip()])
                else:
                    orphan_count = None
                    if failure is None:
                        failure = SandboxDockerError(
                            "DOCKER_COMMAND_FAILED" if orphan.returncode != 0 else "DOCKER_OUTPUT_LIMIT_EXCEEDED",
                            "Docker orphan reconciliation failed safely",
                            operation=docker_operation_name(orphan.arguments),
                            return_code=orphan.returncode,
                            stderr_category=docker_stderr_category(orphan),
                            output_truncated=orphan.output_truncated,
                        )
            shutil.rmtree(snapshot.staging_root, ignore_errors=True)
        if failure is not None:
            raise failure.attach_cleanup(
                cleanup_attempted=cleanup_attempted,
                cleanup_completed=(not cleanup_attempted or deleted),
                orphan_count=orphan_count,
            )
        if image is None or container_id is None or not deleted or orphan_count != 0:
            raise SandboxDockerError(
                "SANDBOX_CLEANUP_FAILED",
                "Read-only Sandbox cleanup did not complete",
                operation="sandbox.cleanup",
                cleanup_attempted=cleanup_attempted,
                cleanup_completed=(not cleanup_attempted or deleted),
                orphan_count=orphan_count,
            )
        lifecycle = SandboxReadonlyLifecycle(
            acceptance_id=acceptance,
            image=image,
            container_id=container_id,
            container_name=container_name,
            docker_call_count=len(self._history),
            command_operations=tuple(" ".join(item[:2]) for item in self._history),
            snapshot_sha256=snapshot.snapshot_sha256,
            snapshot_file_count=snapshot.file_count,
            snapshot_total_bytes=snapshot.total_bytes,
            materialized_file_count=materialized_file_count,
            selected_file_hashes_verified=selected_hashes_verified,
            security=security,
            deleted=deleted,
            orphan_count=orphan_count,
            cleanup_state=cleanup_state,
        )
        return SandboxReadonlyInspection(inspection=inspection, lifecycle=lifecycle)

    def _validate_created_container(self, container_id: str, labels: Mapping[str, str], tmpfs_value: str) -> dict[str, object]:
        inspected = self._checked(["container", "inspect", container_id])
        try:
            payload = json.loads(inspected.stdout)
        except json.JSONDecodeError as exc:
            raise SandboxDockerError("CONTAINER_INSPECT_INVALID", "Docker returned invalid container JSON") from exc
        if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
            raise SandboxDockerError("CONTAINER_INSPECT_INVALID", "Docker returned an unexpected container JSON shape")
        item = payload[0]
        config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
        host = item.get("HostConfig") if isinstance(item.get("HostConfig"), dict) else {}
        networks = ((item.get("NetworkSettings") or {}).get("Networks") if isinstance(item.get("NetworkSettings"), dict) else {}) or {}
        actual_labels = config.get("Labels") if isinstance(config.get("Labels"), dict) else {}
        tmpfs = host.get("Tmpfs") if isinstance(host.get("Tmpfs"), dict) else {}
        actual_tmpfs = tmpfs.get(self.foundation.provider.workspace_mount_path)
        checks = {
            "network_none": host.get("NetworkMode") == "none",
            "no_ports": host.get("PortBindings") in (None, {}) and not bool(host.get("PublishAllPorts")),
            "no_bind_mounts": host.get("Binds") in (None, []) and item.get("Mounts") in (None, []),
            "tmpfs_workspace_semantic": _tmpfs_workspace_semantically_matches(
                actual_tmpfs, size_bytes=self.foundation.provider.workspace_tmpfs_max_bytes
            ),
            "no_network_attachments": set(networks).issubset({"none"}),
            "privileged_false": host.get("Privileged") is False,
            "cap_add_empty": host.get("CapAdd") in (None, []),
            "cap_drop_all": "ALL" in tuple(host.get("CapDrop") or ()),
            "no_new_privileges": any(str(value).startswith("no-new-privileges") for value in tuple(host.get("SecurityOpt") or ())),
            "read_only_rootfs": host.get("ReadonlyRootfs") is True,
            "non_root_user": config.get("User") == self.foundation.provider.non_root_user,
            "memory_limit": host.get("Memory") == self.foundation.provider.memory_limit_bytes,
            "nano_cpus": host.get("NanoCpus") == self.foundation.provider.nano_cpus,
            "pids_limit": host.get("PidsLimit") == self.foundation.provider.pids_limit,
            "restart_none": ((host.get("RestartPolicy") or {}).get("Name") if isinstance(host.get("RestartPolicy"), dict) else None) == "no",
            "labels_exact": all(actual_labels.get(key) == value for key, value in labels.items()),
            "fixed_tail_command": config.get("Cmd") == ["tail", "-f", "/dev/null"],
        }
        failed = [key for key, value in checks.items() if value is not True]
        if failed:
            raise SandboxDockerError("CONTAINER_SECURITY_MISMATCH", "Read-only Sandbox security mismatch: " + ",".join(failed))
        return checks

    def _checked(self, arguments: list[str]):
        result = self._call(arguments)
        operation = docker_operation_name(arguments)
        if result.returncode != 0:
            raise SandboxDockerError(
                "DOCKER_COMMAND_FAILED",
                "Docker command failed safely",
                operation=operation,
                return_code=result.returncode,
                stderr_category=docker_stderr_category(result),
                output_truncated=result.output_truncated,
            )
        if result.output_truncated:
            raise SandboxDockerError(
                "DOCKER_OUTPUT_LIMIT_EXCEEDED",
                "Docker output exceeded its bound",
                operation=operation,
                return_code=result.returncode,
                stderr_category=docker_stderr_category(result),
                output_truncated=True,
            )
        return result

    def _checked_with_input(self, arguments: list[str], *, input_bytes: bytes):
        result = self._call_with_input(arguments, input_bytes=input_bytes)
        operation = docker_operation_name(arguments)
        if result.returncode != 0:
            raise SandboxDockerError(
                "DOCKER_COMMAND_FAILED",
                "Docker command failed safely",
                operation=operation,
                return_code=result.returncode,
                stderr_category=docker_stderr_category(result),
                output_truncated=result.output_truncated,
            )
        if result.output_truncated:
            raise SandboxDockerError(
                "DOCKER_OUTPUT_LIMIT_EXCEEDED",
                "Docker output exceeded its bound",
                operation=operation,
                return_code=result.returncode,
                stderr_category=docker_stderr_category(result),
                output_truncated=True,
            )
        return result

    def _call(self, arguments: list[str]):
        normalized = tuple(str(item) for item in arguments)
        self._history.append(normalized)
        return self.runner.run(normalized, timeout_seconds=self.foundation.provider.command_timeout_seconds)

    def _call_with_input(self, arguments: list[str], *, input_bytes: bytes):
        normalized = tuple(str(item) for item in arguments)
        self._history.append(normalized)
        run_with_input = getattr(self.runner, "run_with_input", None)
        if not callable(run_with_input):
            raise SandboxDockerError(
                "DOCKER_STDIN_UNSUPPORTED",
                "Docker runner does not support bounded stdin",
                operation=docker_operation_name(normalized),
                stderr_category="COMMAND_UNAVAILABLE",
            )
        return run_with_input(
            normalized,
            input_bytes=input_bytes,
            timeout_seconds=self.foundation.provider.command_timeout_seconds,
        )

    @staticmethod
    def _validate_relative_argument(value: str) -> None:
        pure = PurePosixPath(value)
        if pure.is_absolute() or ".." in pure.parts or not _SAFE_RELATIVE.fullmatch(value):
            raise SandboxDockerError("SANDBOX_FILE_ARGUMENT_INVALID", "Sandbox file argument is invalid")

    @staticmethod
    def _cpu_string(nano_cpus: int) -> str:
        value = nano_cpus / 1_000_000_000
        return f"{value:.3f}".rstrip("0").rstrip(".")
