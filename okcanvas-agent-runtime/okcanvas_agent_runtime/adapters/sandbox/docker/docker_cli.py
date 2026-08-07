from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from okcanvas_agent_runtime.adapters.sandbox.docker.errors import SandboxDockerError
from okcanvas_agent_runtime.adapters.sandbox.docker.models import SandboxRuntimeFoundation

_DIGEST_REFERENCE = re.compile(
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*"
    r"@sha256:[0-9a-f]{64}$"
)
_LOCAL_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,254}$")
_SAFE_ENVIRONMENT_KEYS = {
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
    "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "PROGRAMDATA", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG",
}


@dataclass(frozen=True)
class DockerCommandResult:
    arguments: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    output_truncated: bool = False


def docker_operation_name(arguments: Sequence[str]) -> str:
    """Return a bounded stable operation identity without persisting raw arguments."""
    values = tuple(str(item) for item in arguments)
    if values[:2] == ("version", "--format"):
        return "docker.version"
    if values[:2] == ("image", "inspect"):
        return "image.inspect"
    if values[:2] == ("container", "create"):
        return "container.create"
    if values[:2] == ("container", "inspect"):
        return "container.inspect"
    if values[:2] == ("container", "start"):
        return "container.start"
    if values[:2] == ("container", "wait"):
        return "container.wait"
    if values[:2] == ("container", "logs"):
        return "container.logs"
    if values[:2] == ("container", "cp"):
        return "container.copy_snapshot"
    if values[:2] == ("container", "rm"):
        return "container.remove"
    if values[:2] == ("container", "ls"):
        return "container.list_orphans"
    if values[:2] == ("container", "exec"):
        executable = ""
        if len(values) > 6 and values[2:5] == ("--interactive", "--user", "0:0"):
            executable = values[6].casefold()
            if executable == "tar":
                return "container.extract_snapshot"
        elif len(values) > 3:
            executable = values[3].casefold()
        if executable in {"find", "cat", "grep", "tail"}:
            return f"container.exec.{executable}"
        return "container.exec.unknown"
    return "docker.unknown"


def docker_stderr_category(result: DockerCommandResult) -> str:
    """Classify bounded Docker output without exposing raw text."""
    text = (result.stderr + "\n" + result.stdout).casefold()
    categories = (
        ("DAEMON_UNAVAILABLE", ("cannot connect to the docker daemon", "docker daemon is not running")),
        ("PERMISSION_DENIED", ("permission denied", "access is denied")),
        ("OPERATION_NOT_PERMITTED", ("operation not permitted",)),
        ("READ_ONLY_FILESYSTEM", ("read-only file system", "read only file system")),
        ("EXECUTABLE_NOT_FOUND", ("executable file not found", "not found in $path")),
        ("NO_SUCH_FILE_OR_DIRECTORY", ("no such file or directory", "could not find the file")),
        ("CONTAINER_NOT_RUNNING", ("container is not running", "is not running")),
        ("CONTAINER_NOT_FOUND", ("no such container",)),
        ("IMAGE_NOT_FOUND", ("no such image", "unable to find image")),
        ("INVALID_ARGUMENT", ("invalid argument", "invalid reference format")),
        ("RESOURCE_EXHAUSTED", ("no space left on device", "not enough memory", "resource exhausted")),
        ("TIMEOUT", ("timed out", "timeout")),
    )
    for category, markers in categories:
        if any(marker in text for marker in markers):
            return category
    return "UNKNOWN"


class DockerCommandRunner(Protocol):
    def run(self, arguments: Sequence[str], *, timeout_seconds: int) -> DockerCommandResult: ...

    def run_with_input(
        self,
        arguments: Sequence[str],
        *,
        input_bytes: bytes,
        timeout_seconds: int,
    ) -> DockerCommandResult: ...


class SubprocessDockerCommandRunner:
    """Invoke the local Docker CLI without shell interpolation or secret-bearing environment."""

    def __init__(self, *, max_output_bytes: int, executable: str | None = None) -> None:
        resolved = executable or shutil.which("docker")
        if not resolved:
            raise SandboxDockerError("DOCKER_CLI_MISSING", "Docker CLI is not available on PATH")
        self.executable = resolved
        self.max_output_bytes = max_output_bytes

    @staticmethod
    def sanitized_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
        values = source or os.environ
        return {key: value for key, value in values.items() if key.upper() in _SAFE_ENVIRONMENT_KEYS}

    def run(self, arguments: Sequence[str], *, timeout_seconds: int) -> DockerCommandResult:
        return self._run(arguments, input_bytes=None, timeout_seconds=timeout_seconds)

    def run_with_input(
        self,
        arguments: Sequence[str],
        *,
        input_bytes: bytes,
        timeout_seconds: int,
    ) -> DockerCommandResult:
        if not isinstance(input_bytes, bytes):
            raise SandboxDockerError("DOCKER_INPUT_INVALID", "Docker stdin payload is invalid")
        return self._run(arguments, input_bytes=input_bytes, timeout_seconds=timeout_seconds)

    def _run(
        self,
        arguments: Sequence[str],
        *,
        input_bytes: bytes | None,
        timeout_seconds: int,
    ) -> DockerCommandResult:
        args = tuple(str(item) for item in arguments)
        if not args or any("\x00" in item for item in args):
            raise SandboxDockerError("DOCKER_ARGUMENT_INVALID", "Docker arguments are invalid")
        run_kwargs: dict[str, object] = {
            "cwd": Path.cwd(),
            "env": self.sanitized_environment(),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "shell": False,
            "check": False,
            "timeout": timeout_seconds,
        }
        if input_bytes is None:
            run_kwargs["stdin"] = subprocess.DEVNULL
        else:
            # subprocess.run(input=...) creates and owns the stdin pipe.  Passing
            # stdin=PIPE at the same time is invalid on every platform and raises
            # ValueError before the Docker process starts.
            run_kwargs["input"] = input_bytes
        try:
            completed = subprocess.run(
                [self.executable, *args],
                **run_kwargs,
            )
        except ValueError as exc:
            raise SandboxDockerError(
                "DOCKER_RUNNER_CONFIGURATION_INVALID",
                "Docker command runner configuration is invalid",
                operation=docker_operation_name(args),
                stderr_category="INVALID_ARGUMENT",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise SandboxDockerError(
                "DOCKER_COMMAND_TIMEOUT",
                "Docker command timed out",
                operation=docker_operation_name(args),
                stderr_category="TIMEOUT",
            ) from exc
        except OSError as exc:
            raise SandboxDockerError(
                "DOCKER_COMMAND_UNAVAILABLE",
                "Docker command could not start",
                operation=docker_operation_name(args),
                stderr_category="COMMAND_UNAVAILABLE",
            ) from exc
        stdout, stdout_truncated = self._decode_bounded(completed.stdout)
        stderr, stderr_truncated = self._decode_bounded(completed.stderr)
        return DockerCommandResult(
            arguments=args,
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            output_truncated=stdout_truncated or stderr_truncated,
        )

    def _decode_bounded(self, value: bytes) -> tuple[str, bool]:
        truncated = len(value) > self.max_output_bytes
        bounded = value[: self.max_output_bytes]
        return bounded.decode("utf-8", errors="replace"), truncated


@dataclass(frozen=True)
class DockerImageBinding:
    requested_reference: str
    immutable_reference: str
    image_id: str
    repo_digests: tuple[str, ...]
    operating_system: str
    architecture: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "requested_reference": self.requested_reference,
            "immutable_reference": self.immutable_reference,
            "image_id": self.image_id,
            "repo_digest_count": len(self.repo_digests),
            "operating_system": self.operating_system,
            "architecture": self.architecture,
        }


@dataclass(frozen=True)
class DockerSandboxLifecycleResult:
    schema_version: str
    state: str
    error_code: str | None
    error_message: str | None
    acceptance_id: str
    container_name: str
    container_id: str | None
    image: DockerImageBinding | None
    docker_server_version: str | None
    docker_call_count: int
    command_operations: tuple[str, ...]
    created: bool
    started: bool
    exited: bool
    exit_code: int | None
    deleted: bool
    orphan_count: int | None
    cleanup_state: str
    security: dict[str, object]
    output_sha256: str | None
    output_bytes: int
    output_tail: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "state": self.state,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "acceptance_id": self.acceptance_id,
            "container_name": self.container_name,
            "container_id": self.container_id,
            "image": self.image.to_public_dict() if self.image else None,
            "docker_server_version": self.docker_server_version,
            "docker_call_count": self.docker_call_count,
            "command_operations": list(self.command_operations),
            "created": self.created,
            "started": self.started,
            "exited": self.exited,
            "exit_code": self.exit_code,
            "deleted": self.deleted,
            "orphan_count": self.orphan_count,
            "cleanup_state": self.cleanup_state,
            "security": self.security,
            "output_sha256": self.output_sha256,
            "output_bytes": self.output_bytes,
            "output_tail": self.output_tail,
        }


class DockerSandboxLifecycleService:
    """Run one bounded Docker create/start/inspect/delete lifecycle with no Agent or model."""

    def __init__(self, foundation: SandboxRuntimeFoundation, runner: DockerCommandRunner) -> None:
        self.foundation = foundation
        self.runner = runner
        self._history: list[tuple[str, ...]] = []
        policy = foundation.policy
        provider = foundation.provider
        if not policy.provider_lifecycle_enabled or not provider.container_lifecycle_enabled:
            raise SandboxDockerError("DOCKER_LIFECYCLE_DISABLED", "Docker lifecycle is disabled")

    @property
    def command_history(self) -> tuple[tuple[str, ...], ...]:
        return tuple(self._history)

    def resolve_local_image(self, reference: str) -> DockerImageBinding:
        """Resolve an already-local image to one immutable RepoDigest without pulling."""
        return self._resolve_local_image(reference)

    def run_probe(self, image_reference: str, *, acceptance_id: str | None = None) -> DockerSandboxLifecycleResult:
        provider = self.foundation.provider
        acceptance = acceptance_id or uuid.uuid4().hex
        if not re.fullmatch(r"[a-z0-9-]{8,64}", acceptance):
            raise SandboxDockerError("ACCEPTANCE_ID_INVALID", "Acceptance ID is invalid")
        container_name = f"okcanvas-step074-{acceptance[:32]}"
        container_id: str | None = None
        image: DockerImageBinding | None = None
        server_version: str | None = None
        created = started = exited = deleted = False
        exit_code: int | None = None
        orphan_count: int | None = None
        cleanup_state = "NOT_REQUIRED"
        security: dict[str, object] = {}
        output = ""
        error_code: str | None = None
        error_message: str | None = None
        try:
            server = self._checked(["version", "--format", "{{json .Server.Version}}"])
            server_version = self._parse_json_string(server.stdout, "DOCKER_SERVER_VERSION_INVALID")
            image = self._resolve_local_image(image_reference)
            labels = {
                "com.okcanvas.agent-runtime.sandbox": "true",
                "com.okcanvas.agent-runtime.provider": provider.provider_id,
                "com.okcanvas.agent-runtime.step": "STEP074",
                "com.okcanvas.agent-runtime.acceptance-id": acceptance,
            }
            create_args = [
                "container", "create",
                "--pull=never",
                "--name", container_name,
                "--network", "none",
                "--read-only",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--pids-limit", str(provider.pids_limit),
                "--memory", str(provider.memory_limit_bytes),
                "--cpus", self._cpu_string(provider.nano_cpus),
                "--user", provider.non_root_user,
                "--restart", "no",
                "--stop-timeout", str(provider.stop_timeout_seconds),
                "--no-healthcheck",
            ]
            for key in provider.required_labels:
                create_args.extend(["--label", f"{key}={labels[key]}"])
            create_args.append(image.immutable_reference)
            created_result = self._checked(create_args)
            container_id = created_result.stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
                raise SandboxDockerError("CONTAINER_ID_INVALID", "Docker returned an invalid container ID")
            created = True
            created_inspect = self._inspect_container(container_id)
            security = self._validate_security(created_inspect, labels)
            started_result = self._checked(["container", "start", "--attach", container_id])
            output = (started_result.stdout + started_result.stderr)[: provider.max_captured_output_bytes]
            started = True
            final_inspect = self._inspect_container(container_id)
            state = self._mapping(final_inspect, "State")
            exited = not bool(state.get("Running")) and str(state.get("Status")) == "exited"
            raw_exit = state.get("ExitCode")
            if isinstance(raw_exit, bool) or not isinstance(raw_exit, int):
                raise SandboxDockerError("CONTAINER_EXIT_CODE_INVALID", "Container exit code is invalid")
            exit_code = raw_exit
            if not exited or exit_code != 0:
                raise SandboxDockerError("CONTAINER_PROCESS_FAILED", "Sandbox probe did not exit successfully")
        except SandboxDockerError as exc:
            error_code = exc.code
            error_message = str(exc)
        finally:
            if container_id is not None:
                cleanup_state = "ATTEMPTED"
                removal = self._call(["container", "rm", "--force", "--volumes", container_id])
                deleted = removal.returncode == 0
                cleanup_state = "COMPLETED" if deleted else "FAILED"
            try:
                orphan_result = self._checked([
                    "container", "ls", "--all", "--quiet", "--filter",
                    f"label=com.okcanvas.agent-runtime.acceptance-id={acceptance}",
                ])
                orphan_count = len([line for line in orphan_result.stdout.splitlines() if line.strip()])
                if orphan_count and error_code is None:
                    error_code = "ORPHAN_CONTAINER_REMAINS"
                    error_message = "Sandbox container cleanup left an orphan"
            except SandboxDockerError as exc:
                orphan_count = None
                if error_code is None:
                    error_code = exc.code
                    error_message = str(exc)
            if container_id is not None and not deleted and error_code is None:
                error_code = "CONTAINER_DELETE_FAILED"
                error_message = "Sandbox container deletion failed"
        state_value = "PASSED" if error_code is None and deleted and orphan_count == 0 else "FAILED"
        output_bytes = len(output.encode("utf-8"))
        return DockerSandboxLifecycleResult(
            schema_version="okcanvas-docker-sandbox-lifecycle-result-v1",
            state=state_value,
            error_code=error_code,
            error_message=error_message,
            acceptance_id=acceptance,
            container_name=container_name,
            container_id=container_id,
            image=image,
            docker_server_version=server_version,
            docker_call_count=len(self._history),
            command_operations=tuple(" ".join(item[:2]) for item in self._history),
            created=created,
            started=started,
            exited=exited,
            exit_code=exit_code,
            deleted=deleted,
            orphan_count=orphan_count,
            cleanup_state=cleanup_state,
            security=security,
            output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest() if output else None,
            output_bytes=output_bytes,
            output_tail=output[-4000:],
        )

    def _resolve_local_image(self, reference: str) -> DockerImageBinding:
        normalized = reference.strip()
        if not normalized or not _LOCAL_REFERENCE.fullmatch(normalized) or any(ch.isspace() for ch in normalized):
            raise SandboxDockerError("IMAGE_REFERENCE_INVALID", "Local image reference is invalid")
        inspected = self._checked(["image", "inspect", normalized])
        payload = self._json_array_one(inspected.stdout, "IMAGE_INSPECT_INVALID")
        repo_digests_raw = payload.get("RepoDigests")
        if not isinstance(repo_digests_raw, list):
            raise SandboxDockerError("IMAGE_REPODIGEST_MISSING", "Local image has no immutable RepoDigest")
        repo_digests = tuple(sorted(item for item in repo_digests_raw if isinstance(item, str) and _DIGEST_REFERENCE.fullmatch(item)))
        if not repo_digests:
            raise SandboxDockerError("IMAGE_REPODIGEST_MISSING", "Local image has no immutable RepoDigest")
        if _DIGEST_REFERENCE.fullmatch(normalized):
            if normalized not in repo_digests:
                raise SandboxDockerError("IMAGE_DIGEST_MISMATCH", "Requested image digest is not locally bound")
            immutable = normalized
        else:
            repository = self._repository_without_tag(normalized)
            matches = tuple(item for item in repo_digests if item.split("@", 1)[0] == repository)
            immutable = matches[0] if matches else repo_digests[0]
        image_id = payload.get("Id")
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise SandboxDockerError("IMAGE_ID_INVALID", "Local image ID is invalid")
        operating_system = payload.get("Os")
        architecture = payload.get("Architecture")
        if not isinstance(operating_system, str) or not isinstance(architecture, str):
            raise SandboxDockerError("IMAGE_PLATFORM_INVALID", "Local image platform is invalid")
        return DockerImageBinding(
            requested_reference=normalized,
            immutable_reference=immutable,
            image_id=image_id,
            repo_digests=repo_digests,
            operating_system=operating_system,
            architecture=architecture,
        )

    def _inspect_container(self, container_id: str) -> dict[str, object]:
        inspected = self._checked(["container", "inspect", container_id])
        return self._json_array_one(inspected.stdout, "CONTAINER_INSPECT_INVALID")

    def _validate_security(self, payload: dict[str, object], labels: Mapping[str, str]) -> dict[str, object]:
        provider = self.foundation.provider
        config = self._mapping(payload, "Config")
        host = self._mapping(payload, "HostConfig")
        mounts = payload.get("Mounts")
        networks = self._mapping(self._mapping(payload, "NetworkSettings"), "Networks")
        actual_labels = config.get("Labels")
        if not isinstance(actual_labels, dict):
            actual_labels = {}
        checks = {
            "network_none": host.get("NetworkMode") == "none",
            "no_ports": host.get("PortBindings") in (None, {}) and not bool(host.get("PublishAllPorts")),
            "no_mounts": mounts in (None, []) and host.get("Binds") in (None, []),
            "no_network_attachments": set(networks).issubset({"none"}),
            "privileged_false": host.get("Privileged") is False,
            "cap_add_empty": host.get("CapAdd") in (None, []),
            "cap_drop_all": "ALL" in tuple(host.get("CapDrop") or ()),
            "no_new_privileges": any(
                str(item).startswith("no-new-privileges") for item in tuple(host.get("SecurityOpt") or ())
            ),
            "read_only_rootfs": host.get("ReadonlyRootfs") is True,
            "non_root_user": config.get("User") == provider.non_root_user,
            "memory_limit": host.get("Memory") == provider.memory_limit_bytes,
            "nano_cpus": host.get("NanoCpus") == provider.nano_cpus,
            "pids_limit": host.get("PidsLimit") == provider.pids_limit,
            "restart_none": self._mapping(host, "RestartPolicy").get("Name") == "no",
            "labels_exact": all(actual_labels.get(key) == value for key, value in labels.items()),
        }
        failed = [key for key, value in checks.items() if value is not True]
        if failed:
            raise SandboxDockerError("CONTAINER_SECURITY_MISMATCH", "Container security contract mismatch: " + ",".join(failed))
        return checks

    def _checked(self, arguments: Sequence[str]) -> DockerCommandResult:
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

    def _call(self, arguments: Sequence[str]) -> DockerCommandResult:
        normalized = tuple(str(item) for item in arguments)
        self._history.append(normalized)
        return self.runner.run(
            normalized,
            timeout_seconds=self.foundation.provider.command_timeout_seconds,
        )

    @staticmethod
    def _json_array_one(text: str, code: str) -> dict[str, object]:
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SandboxDockerError(code, "Docker returned invalid JSON") from exc
        if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
            raise SandboxDockerError(code, "Docker returned an unexpected JSON shape")
        return value[0]

    @staticmethod
    def _parse_json_string(text: str, code: str) -> str:
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SandboxDockerError(code, "Docker returned invalid JSON text") from exc
        if not isinstance(value, str) or not value:
            raise SandboxDockerError(code, "Docker returned an empty value")
        return value

    @staticmethod
    def _mapping(payload: Mapping[str, object], key: str) -> dict[str, object]:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise SandboxDockerError("DOCKER_INSPECT_FIELD_INVALID", f"Docker inspect field {key} is invalid")
        return value

    @staticmethod
    def _repository_without_tag(reference: str) -> str:
        last_slash = reference.rfind("/")
        last_colon = reference.rfind(":")
        return reference[:last_colon] if last_colon > last_slash else reference

    @staticmethod
    def _cpu_string(nano_cpus: int) -> str:
        value = nano_cpus / 1_000_000_000
        text = f"{value:.9f}".rstrip("0").rstrip(".")
        return text or "0"
