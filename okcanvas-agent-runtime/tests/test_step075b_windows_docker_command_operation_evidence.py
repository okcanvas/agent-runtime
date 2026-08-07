from __future__ import annotations

from pathlib import Path

import pytest

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.adapters.sandbox.docker import (
    DockerCommandResult,
    ProductOwnedReadonlySandboxInspector,
    SandboxDockerError,
    SandboxRuntimeCatalog,
)
from okcanvas_agent_runtime.adapters.sandbox.docker.docker_cli import (
    docker_operation_name,
    docker_stderr_category,
)
from tests.test_step075_product_owned_readonly_sandbox_workspace_agent import (
    IMAGE_TAG,
    ReadonlyRunner,
    _fixture,
)

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_selects_step075b_live_rerun_gate() -> None:
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.product_owned_readonly_sandbox_command_operation_evidence_implemented is True
    assert info.product_owned_readonly_sandbox_windows_live_accepted is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


class FailingReadonlyRunner(ReadonlyRunner):
    def __init__(self, files: dict[str, bytes], *, failed_operation: str, stderr: str) -> None:
        super().__init__(files)
        self.failed_operation = failed_operation
        self.failure_stderr = stderr

    def _maybe_fail(self, result: DockerCommandResult) -> DockerCommandResult:
        operation = docker_operation_name(result.arguments)
        if operation == self.failed_operation:
            return DockerCommandResult(
                result.arguments,
                1,
                result.stdout,
                self.failure_stderr,
                False,
            )
        return result

    def run(self, arguments, *, timeout_seconds: int) -> DockerCommandResult:
        return self._maybe_fail(super().run(arguments, timeout_seconds=timeout_seconds))

    def run_with_input(self, arguments, *, input_bytes: bytes, timeout_seconds: int) -> DockerCommandResult:
        return self._maybe_fail(
            super().run_with_input(
                arguments, input_bytes=input_bytes, timeout_seconds=timeout_seconds
            )
        )


def test_operation_names_are_bounded_and_do_not_include_arguments() -> None:
    container_id = "c" * 64
    assert docker_operation_name(("image", "inspect", "private/image:secret")) == "image.inspect"
    assert docker_operation_name(("container", "create", "--env", "SECRET=value")) == "container.create"
    assert docker_operation_name(("container", "cp", "C:/private/path", f"{container_id}:/workspace")) == "container.copy_snapshot"
    assert docker_operation_name((
        "container", "exec", "--interactive", "--user", "0:0", container_id,
        "tar", "-x", "-f", "-", "-C", "/workspace",
    )) == "container.extract_snapshot"
    assert docker_operation_name(("container", "exec", container_id, "find", "/workspace")) == "container.exec.find"
    assert docker_operation_name(("container", "exec", container_id, "cat", "/workspace/secret.py")) == "container.exec.cat"
    assert docker_operation_name(("container", "exec", container_id, "sh", "-c", "secret")) == "container.exec.unknown"


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("permission denied", "PERMISSION_DENIED"),
        ("read-only file system", "READ_ONLY_FILESYSTEM"),
        ("executable file not found in $PATH", "EXECUTABLE_NOT_FOUND"),
        ("no such file or directory", "NO_SUCH_FILE_OR_DIRECTORY"),
        ("container is not running", "CONTAINER_NOT_RUNNING"),
        ("unexpected provider response", "UNKNOWN"),
    ],
)
def test_stderr_category_is_stable_and_bounded(stderr: str, expected: str) -> None:
    result = DockerCommandResult(("container", "cp"), 1, "", stderr, False)
    assert docker_stderr_category(result) == expected


def test_failed_extract_preserves_operation_return_category_and_cleanup(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    files = {
        "README.md": (project / "README.md").read_bytes(),
        "src/health.py": (project / "src" / "health.py").read_bytes(),
    }
    runner = FailingReadonlyRunner(
        files,
        failed_operation="container.extract_snapshot",
        stderr="Error response from daemon: read-only file system at C:/private/source",
    )
    with pytest.raises(SandboxDockerError) as captured:
        ProductOwnedReadonlySandboxInspector(
            SandboxRuntimeCatalog(ROOT).resolve(), runner
        ).inspect(
            source_root=project,
            query="health_route",
            image_reference=IMAGE_TAG,
            acceptance_id="acceptance-075b-copy",
        )
    error = captured.value
    assert error.code == "DOCKER_COMMAND_FAILED"
    assert error.operation == "container.extract_snapshot"
    assert error.return_code == 1
    assert error.stderr_category == "READ_ONLY_FILESYSTEM"
    assert error.output_truncated is False
    assert error.cleanup_attempted is True
    assert error.cleanup_completed is True
    assert error.orphan_count == 0
    assert "C:/private/source" not in repr(vars(error))


def test_failed_image_inspect_reports_no_cleanup_needed(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    files = {
        "README.md": (project / "README.md").read_bytes(),
        "src/health.py": (project / "src" / "health.py").read_bytes(),
    }
    runner = FailingReadonlyRunner(
        files,
        failed_operation="image.inspect",
        stderr="No such image: private/image:secret",
    )
    with pytest.raises(SandboxDockerError) as captured:
        ProductOwnedReadonlySandboxInspector(
            SandboxRuntimeCatalog(ROOT).resolve(), runner
        ).inspect(
            source_root=project,
            query="health_route",
            image_reference=IMAGE_TAG,
            acceptance_id="acceptance-075b-image",
        )
    error = captured.value
    assert error.operation == "image.inspect"
    assert error.stderr_category == "IMAGE_NOT_FOUND"
    assert error.cleanup_attempted is False
    assert error.cleanup_completed is True
    assert error.orphan_count == 0


def test_gateway_persists_operation_diagnostics_without_raw_values() -> None:
    source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    for token in (
        '"operation": exc.operation',
        '"return_code": exc.return_code',
        '"stderr_category": exc.stderr_category',
        '"output_truncated": exc.output_truncated',
        '"cleanup_attempted": exc.cleanup_attempted',
        '"cleanup_completed": exc.cleanup_completed',
        '"orphan_count": exc.orphan_count',
        '"raw_arguments_persisted": False',
        '"raw_output_persisted": False',
        '"raw_message_persisted": False',
    ):
        assert token in source
