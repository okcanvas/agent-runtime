from __future__ import annotations

import io
import json
import subprocess
import tarfile
from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.adapters.sandbox.docker import (
    ProductOwnedReadonlySandboxInspector,
    SandboxRuntimeCatalog,
    SubprocessDockerCommandRunner,
    build_readonly_snapshot,
    build_readonly_snapshot_archive,
)
from okcanvas_agent_runtime.adapters.sandbox.docker.docker_cli import docker_operation_name
from tests.test_step075_product_owned_readonly_sandbox_workspace_agent import (
    IMAGE_TAG,
    ReadonlyRunner,
    _fixture,
)

ROOT = Path(__file__).resolve().parents[1]


def test_provider_binds_stdin_tar_materialization_contract() -> None:
    provider = SandboxRuntimeCatalog(ROOT).resolve().provider
    assert provider.version == "1.3.0"
    assert provider.workspace_materialization_mode == "docker-exec-stdin-tar-to-root-owned-tmpfs"
    assert provider.workspace_archive_format == "gnu-tar-v1"
    assert provider.workspace_materializer_user == "0:0"
    assert provider.workspace_materializer_command == ("tar", "-x", "-f", "-", "-C", "/workspace")


def test_snapshot_archive_is_deterministic_root_owned_and_read_only(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    foundation = SandboxRuntimeCatalog(ROOT).resolve()
    snapshot = build_readonly_snapshot(project, foundation=foundation)
    try:
        first = build_readonly_snapshot_archive(snapshot)
        second = build_readonly_snapshot_archive(snapshot)
        assert first == second
        assert str(snapshot.staging_root).encode("utf-8") not in first
        with tarfile.open(fileobj=io.BytesIO(first), mode="r:*") as archive:
            members = archive.getmembers()
            names = [member.name.rstrip("/") for member in members]
            assert names == sorted(names, key=lambda item: (item.count("/"), item)) or set(names) == {
                "src", "README.md", "src/health.py", ".okcanvas-snapshot-manifest.json"
            }
            assert {member.name.rstrip("/") for member in members} == {
                "src", "README.md", "src/health.py", ".okcanvas-snapshot-manifest.json"
            }
            for member in members:
                assert member.uid == member.gid == 0
                assert member.uname == member.gname == ""
                assert member.mtime == 0
                assert not member.issym() and not member.islnk() and not member.isdev()
                assert member.mode == (0o755 if member.isdir() else 0o444)
    finally:
        __import__("shutil").rmtree(snapshot.staging_root, ignore_errors=True)


def test_inspector_streams_tar_without_host_path_or_docker_cp(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    runner = ReadonlyRunner({})
    result = ProductOwnedReadonlySandboxInspector(
        SandboxRuntimeCatalog(ROOT).resolve(), runner
    ).inspect(
        source_root=project,
        query="health_route",
        image_reference=IMAGE_TAG,
        acceptance_id="acceptance-075c-stream",
    )
    operations = [docker_operation_name(call) for call in runner.calls]
    assert "container.copy_snapshot" not in operations
    assert operations.count("container.extract_snapshot") == 1
    extract = next(call for call in runner.calls if docker_operation_name(call) == "container.extract_snapshot")
    assert extract[:5] == ("container", "exec", "--interactive", "--user", "0:0")
    assert not any(str(project) in value or str(result.lifecycle.container_id) in value and False for value in extract)
    assert result.lifecycle.selected_file_hashes_verified is True
    assert result.lifecycle.cleanup_state == "COMPLETED"
    assert result.lifecycle.orphan_count == 0


def test_subprocess_runner_passes_bounded_bytes_to_stdin(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SubprocessDockerCommandRunner(max_output_bytes=1024, executable="docker")
    payload = b"deterministic-tar"
    result = runner.run_with_input(
        (
            "container", "exec", "--interactive", "--user", "0:0", "c" * 64,
            "tar", "-x", "-f", "-", "-C", "/workspace",
        ),
        input_bytes=payload,
        timeout_seconds=30,
    )
    assert result.returncode == 0
    assert captured["input"] == payload
    assert "stdin" not in captured
    assert captured["shell"] is False
    assert "OPENAI_API_KEY" not in captured["env"]


def test_product_sources_do_not_use_host_path_docker_cp() -> None:
    source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/read_only_workspace.py")).read_text(
        encoding="utf-8"
    )
    assert '"container", "cp"' not in source
    assert "build_readonly_snapshot_archive" in source
    assert "run_with_input" in source
    assert '"--interactive", "--user"' in source
