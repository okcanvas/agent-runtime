from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from okcanvas_agent_runtime.compatibility.source_contracts import read_component_source
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.adapters.sandbox.docker import (
    DockerCommandResult,
    ProductOwnedReadonlySandboxInspector,
    SandboxDockerError,
    SandboxRuntimeCatalog,
    SandboxRuntimeService,
    build_readonly_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
IMAGE_TAG = "busybox:1.36"
IMAGE_DIGEST = "busybox@sha256:" + "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
CONTAINER_ID = "c" * 64


class ReadonlyRunner:
    def __init__(
        self,
        files: dict[str, bytes],
        *,
        network_mode: str = "none",
        tmpfs_value: str = "rw,noexec,nosuid,nodev,size=33554432,uid=0,gid=0,mode=0755",
    ) -> None:
        self.files = files
        self.network_mode = network_mode
        self.tmpfs_value = tmpfs_value
        self.calls: list[tuple[str, ...]] = []
        self.labels: dict[str, str] = {}

    def run(self, arguments, *, timeout_seconds: int) -> DockerCommandResult:
        assert timeout_seconds == 30
        args = tuple(str(item) for item in arguments)
        self.calls.append(args)
        stdout = ""
        returncode = 0
        if args[:2] == ("image", "inspect"):
            stdout = json.dumps([{
                "Id": IMAGE_ID,
                "RepoDigests": [IMAGE_DIGEST],
                "Os": "linux",
                "Architecture": "amd64",
            }])
        elif args[:2] == ("container", "create"):
            for index, value in enumerate(args):
                if value == "--label" and index + 1 < len(args):
                    key, label_value = args[index + 1].split("=", 1)
                    self.labels[key] = label_value
            stdout = CONTAINER_ID + "\n"
        elif args[:2] == ("container", "inspect"):
            stdout = json.dumps([{
                "Config": {"User": "65532:65532", "Labels": self.labels, "Cmd": ["tail", "-f", "/dev/null"]},
                "HostConfig": {
                    "NetworkMode": self.network_mode,
                    "PortBindings": None,
                    "PublishAllPorts": False,
                    "Binds": None,
                    "Tmpfs": {"/workspace": self.tmpfs_value},
                    "Privileged": False,
                    "CapAdd": None,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges"],
                    "ReadonlyRootfs": True,
                    "Memory": 134217728,
                    "NanoCpus": 500000000,
                    "PidsLimit": 64,
                    "RestartPolicy": {"Name": "no"},
                },
                "Mounts": [],
                "NetworkSettings": {"Networks": {"none": {}}},
            }])
        elif args[:2] == ("container", "start"):
            stdout = CONTAINER_ID + "\n"
        elif args[:3] == ("container", "exec", CONTAINER_ID) and args[3] == "find":
            paths = sorted(self.files) + [".okcanvas-snapshot-manifest.json"]
            stdout = "".join(f"/workspace/{path}\n" for path in paths)
        elif args[:3] == ("container", "exec", CONTAINER_ID) and args[3] == "cat":
            path = args[4].removeprefix("/workspace/")
            stdout = self.files[path].decode("utf-8")
        elif args[:2] == ("container", "rm"):
            stdout = CONTAINER_ID + "\n"
        elif args[:2] == ("container", "ls"):
            stdout = ""
        else:
            raise AssertionError(f"Unexpected Docker command: {args}")
        return DockerCommandResult(args, returncode, stdout, "", False)

    def run_with_input(self, arguments, *, input_bytes: bytes, timeout_seconds: int) -> DockerCommandResult:
        assert timeout_seconds == 30
        args = tuple(str(item) for item in arguments)
        self.calls.append(args)
        assert args[:7] == (
            "container", "exec", "--interactive", "--user", "0:0", CONTAINER_ID, "tar"
        )
        extracted: dict[str, bytes] = {}
        with tarfile.open(fileobj=io.BytesIO(input_bytes), mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                stream = archive.extractfile(member)
                assert stream is not None
                extracted[member.name] = stream.read()
        assert ".okcanvas-snapshot-manifest.json" in extracted
        self.files = {key: value for key, value in extracted.items() if key != ".okcanvas-snapshot-manifest.json"}
        return DockerCommandResult(args, 0, "", "", False)


def _fixture(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "health.py").write_bytes(
        b'def health_route():\n    return {"status": "ok"}\n'
    )
    (project / "README.md").write_bytes(b"# Example\n")
    return project


def test_runtime_selects_step075_windows_live_gate() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.product_owned_docker_lifecycle_windows_live_accepted is True
    assert info.product_owned_readonly_sandbox_agent_implemented is True
    assert info.product_owned_readonly_sandbox_windows_live_accepted is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


def test_catalog_activates_only_none_and_readonly_workspace() -> None:
    foundation = SandboxRuntimeCatalog(ROOT).resolve()
    assert foundation.policy.version == "1.2.0"
    assert foundation.policy.agent_execution_enabled is True
    assert foundation.policy.physical_workspace_materialization_enabled is True
    assert foundation.policy.active_workspace_access_modes == ("none", "sandbox-readonly-v1")
    assert foundation.policy.shell_enabled is False
    assert foundation.policy.apply_patch_enabled is False
    assert foundation.provider.version == "1.3.0"
    assert foundation.provider.workspace_materialization_mode == "docker-exec-stdin-tar-to-root-owned-tmpfs"
    assert foundation.provider.workspace_mount_path == "/workspace"
    assert foundation.provider.workspace_allowed_commands == ("find", "cat", "grep", "tail")


def test_catalog_has_one_exact_readonly_sandbox_agent() -> None:
    definitions = AgentDefinitionCatalog(ROOT).list_definitions()
    assert len(definitions) == 32
    sandbox = [item for item in definitions if item.workspace_access == "sandbox-readonly-v1"]
    assert len(sandbox) == 1
    definition = sandbox[0]
    assert definition.agent_id == "sandbox-readonly-coding-agent"
    assert definition.tools == ("sandbox_project_readonly_inspect",)
    assert definition.mcp_servers == definition.hosted_tools == definition.skills == ()
    assert definition.handoffs == definition.agent_tools == definition.orchestration_children == ()
    assert definition.guardrails == ()
    assert definition.session_mode == "disabled"


def test_readonly_tool_and_runtime_binding_are_exact() -> None:
    tool = FunctionToolRuntimeCatalog(ROOT).resolve("sandbox_project_readonly_inspect")
    assert tool.factory_id == "sandbox_project_readonly_inspect_v1"
    assert tool.read_only is True
    assert tool.filesystem_access == "sandbox-read-only"
    assert tool.network_access == tool.shell_access == "none"
    definition = AgentDefinitionCatalog(ROOT).resolve("sandbox-readonly-coding-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.execution_path == "product-owned-readonly-sandbox-agent-execution-v1"
    assert binding.sandbox_runtime_foundation["policy"]["agent_execution_enabled"] is True
    assert binding.sandbox_runtime_foundation["policy"]["shell_enabled"] is False
    assert binding.sandbox_runtime_foundation["provider"]["workspace_mount_path"] == "/workspace"


def test_runtime_service_allows_readonly_and_rejects_other_modes() -> None:
    service = SandboxRuntimeService(SandboxRuntimeCatalog(ROOT).resolve())
    service.require_agent_execution("sandbox-readonly-v1")
    with pytest.raises(Exception):
        service.require_agent_execution("sandbox-shell-v1")


def test_snapshot_is_bounded_canonical_and_excludes_reference(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    (project / "reference").mkdir()
    (project / "reference" / "upstream.py").write_bytes(b"secret = True\n")
    snapshot = build_readonly_snapshot(project, foundation=SandboxRuntimeCatalog(ROOT).resolve())
    try:
        assert snapshot.file_count == 2
        assert snapshot.total_bytes > 0
        assert len(snapshot.snapshot_sha256) == 64
        assert {item.path for item in snapshot.entries} == {"README.md", "src/health.py"}
        assert not any("reference" in item.path for item in snapshot.entries)
        manifest = json.loads((snapshot.staging_root / ".okcanvas-snapshot-manifest.json").read_text())
        assert manifest["snapshot_sha256"] == snapshot.snapshot_sha256
    finally:
        __import__("shutil").rmtree(snapshot.staging_root, ignore_errors=True)


def test_snapshot_rejects_symlink(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    try:
        (project / "escape.py").symlink_to(project / "src" / "health.py")
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(SandboxDockerError, match="symbolic links"):
        build_readonly_snapshot(project, foundation=SandboxRuntimeCatalog(ROOT).resolve())


def test_inspector_materializes_tmpfs_reads_container_bytes_and_cleans_up(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    files = {
        "README.md": (project / "README.md").read_bytes(),
        "src/health.py": (project / "src" / "health.py").read_bytes(),
    }
    runner = ReadonlyRunner(files)
    result = ProductOwnedReadonlySandboxInspector(
        SandboxRuntimeCatalog(ROOT).resolve(), runner
    ).inspect(
        source_root=project,
        query="Where is health_route implemented?",
        image_reference=IMAGE_TAG,
        acceptance_id="acceptance-075",
    )
    inspection = result.inspection
    assert inspection.workspace_label.startswith("docker-tmpfs:")
    assert inspection.inspected_files == ("src/health.py",)
    assert inspection.evidence[0].path == "src/health.py"
    assert "health_route" in inspection.evidence[0].excerpt
    lifecycle = result.lifecycle
    assert lifecycle.snapshot_file_count == 2
    assert lifecycle.materialized_file_count == 3
    assert lifecycle.selected_file_hashes_verified is True
    assert lifecycle.deleted is True
    assert lifecycle.orphan_count == 0
    create = next(call for call in runner.calls if call[:2] == ("container", "create"))
    assert "--pull=never" in create
    assert "--tmpfs" in create
    assert not any(item in create for item in ("--mount", "--volume", "-v", "--env", "-e", "--publish", "-p"))
    assert create[-4:] == (IMAGE_DIGEST, "tail", "-f", "/dev/null")
    assert all("sh" not in call[3:4] and "bash" not in call[3:4] for call in runner.calls)


def test_inspector_accepts_semantically_equal_windows_tmpfs_normalization(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    files = {
        "README.md": (project / "README.md").read_bytes(),
        "src/health.py": (project / "src/health.py").read_bytes(),
    }
    runner = ReadonlyRunner(
        files,
        tmpfs_value="nodev,rw,size=32m,mode=755,gid=0,nosuid,uid=0,noexec",
    )
    result = ProductOwnedReadonlySandboxInspector(
        SandboxRuntimeCatalog(ROOT).resolve(), runner
    ).inspect(
        source_root=project,
        query="health_route",
        image_reference=IMAGE_TAG,
        acceptance_id="acceptance-075a",
    )
    assert result.lifecycle.security["tmpfs_workspace_semantic"] is True
    assert result.lifecycle.cleanup_state == "COMPLETED"
    assert result.lifecycle.orphan_count == 0


def test_inspector_rejects_tmpfs_missing_noexec_and_cleans_up(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    files = {
        "README.md": (project / "README.md").read_bytes(),
        "src/health.py": (project / "src/health.py").read_bytes(),
    }
    runner = ReadonlyRunner(
        files,
        tmpfs_value="rw,nosuid,nodev,size=33554432,uid=0,gid=0,mode=755",
    )
    with pytest.raises(SandboxDockerError, match="security mismatch"):
        ProductOwnedReadonlySandboxInspector(
            SandboxRuntimeCatalog(ROOT).resolve(), runner
        ).inspect(
            source_root=project,
            query="health_route",
            image_reference=IMAGE_TAG,
            acceptance_id="acceptance-075a-fail",
        )
    assert any(call[:2] == ("container", "rm") for call in runner.calls)
    assert any(call[:2] == ("container", "ls") for call in runner.calls)


def test_inspector_security_mismatch_fails_and_deletes(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    files = {"README.md": b"# Example\n", "src/health.py": b"def health_route():\n    pass\n"}
    runner = ReadonlyRunner(files, network_mode="bridge")
    with pytest.raises(SandboxDockerError, match="security mismatch"):
        ProductOwnedReadonlySandboxInspector(SandboxRuntimeCatalog(ROOT).resolve(), runner).inspect(
            source_root=project,
            query="health_route",
            image_reference=IMAGE_TAG,
            acceptance_id="acceptance-075",
        )
    assert any(call[:2] == ("container", "rm") for call in runner.calls)
    assert any(call[:2] == ("container", "ls") for call in runner.calls)


def test_public_metadata_exposes_limits_not_image_or_host_path() -> None:
    public = SandboxRuntimeCatalog(ROOT).resolve().to_public_dict()
    serialized = json.dumps(public, sort_keys=True)
    assert public["agent_execution_enabled"] is True
    assert public["provider_workspace_materialization_mode"] == "docker-exec-stdin-tar-to-root-owned-tmpfs"
    assert public["provider_workspace_tmpfs_max_bytes"] == 33554432
    assert "requested_reference" not in serialized
    assert "immutable_reference" not in serialized
    assert "host_path" not in public
    assert "docker.sock" not in serialized


def test_source_contains_no_sdk_sandbox_agent_or_default_capability_use() -> None:
    sources = read_component_source(ROOT, "runtime.all")
    assert "SandboxAgent(" not in sources
    assert "Capabilities.default(" not in sources
    assert "DockerSandboxClient(" not in sources


def test_sandbox_tool_output_exposes_bounded_lifecycle_evidence(tmp_path: Path) -> None:
    from okcanvas_agent_runtime.agent.tools.function.implementations import sandbox_project_readonly_inspect
    from okcanvas_agent_runtime.agent.tools.function.models import SandboxProjectReadonlyInspectOutput

    project = _fixture(tmp_path)
    files = {
        "README.md": (project / "README.md").read_bytes(),
        "src/health.py": (project / "src" / "health.py").read_bytes(),
    }
    output = sandbox_project_readonly_inspect(
        project,
        "Where is health_route implemented?",
        image_reference=IMAGE_TAG,
        runner=ReadonlyRunner(files),
    )
    assert isinstance(output, SandboxProjectReadonlyInspectOutput)
    assert output.workspace_access == "sandbox-readonly-v1"
    assert output.workspace_materialized is True
    assert output.docker_call_count > 0
    assert output.selected_file_hashes_verified is True
    assert output.cleanup_state == "COMPLETED"
    assert output.orphan_count == 0
    assert output.network_mode == "none"
    assert output.shell_enabled is output.apply_patch_enabled is False
    assert len(output.image_binding_sha256) == 64


def test_snapshot_normalizes_cp949_to_utf8_before_hashing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    text = "재고 계산 함수"
    (project / "README.md").write_bytes(text.encode("cp949"))
    snapshot = build_readonly_snapshot(project, foundation=SandboxRuntimeCatalog(ROOT).resolve())
    try:
        normalized = (snapshot.staging_root / "README.md").read_bytes()
        assert normalized == text.encode("utf-8")
        assert snapshot.entries[0].sha256 == hashlib.sha256(normalized).hexdigest()
    finally:
        __import__("shutil").rmtree(snapshot.staging_root, ignore_errors=True)
