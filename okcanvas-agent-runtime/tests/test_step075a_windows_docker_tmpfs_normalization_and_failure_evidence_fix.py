from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.adapters.sandbox.docker.read_only_workspace import (
    _parse_tmpfs_mode,
    _parse_tmpfs_size_bytes,
    _tmpfs_workspace_semantically_matches,
)

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_selects_step075a_windows_live_rerun_gate() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.product_owned_readonly_sandbox_agent_implemented is True
    assert info.product_owned_readonly_sandbox_windows_live_accepted is True
    assert info.product_owned_readonly_sandbox_tmpfs_semantic_validation_implemented is True
    assert info.product_owned_readonly_sandbox_failure_evidence_implemented is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


def test_tmpfs_size_and_mode_normalization_is_exact() -> None:
    assert _parse_tmpfs_size_bytes("33554432") == 33_554_432
    assert _parse_tmpfs_size_bytes("32m") == 33_554_432
    assert _parse_tmpfs_size_bytes("32MiB") == 33_554_432
    assert _parse_tmpfs_size_bytes("32mb") == 33_554_432
    assert _parse_tmpfs_size_bytes("bad") is None
    assert _parse_tmpfs_mode("0755") == 0o755
    assert _parse_tmpfs_mode("755") == 0o755
    assert _parse_tmpfs_mode("0o755") == 0o755
    assert _parse_tmpfs_mode("0777x") is None


def test_tmpfs_security_is_order_independent_but_fail_closed() -> None:
    normalized = "nodev,rw,size=32m,mode=755,gid=0,nosuid,uid=0,noexec"
    assert _tmpfs_workspace_semantically_matches(normalized, size_bytes=33_554_432)
    assert not _tmpfs_workspace_semantically_matches(
        "rw,nosuid,nodev,size=33554432,uid=0,gid=0,mode=755",
        size_bytes=33_554_432,
    )
    assert not _tmpfs_workspace_semantically_matches(
        "rw,noexec,nosuid,nodev,size=33554432,uid=0,gid=0,mode=777",
        size_bytes=33_554_432,
    )
    assert not _tmpfs_workspace_semantically_matches(
        "rw,noexec,nosuid,nodev,size=32m,uid=0,gid=0,mode=755,unknown=1",
        size_bytes=33_554_432,
    )


def test_gateway_persists_bounded_sandbox_tool_failure_event() -> None:
    source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(
        encoding="utf-8"
    )
    assert '"tool.failed"' in source
    assert '"code": exc.code' in source
    assert '"arguments_persisted": False' in source
    assert '"result_persisted": False' in source
    assert 'payload_schema_version="okcanvas-function-tool-failed-v1"' in source
    assert 'detail_type=f"SandboxDockerError:{exc.code}"' in source


def test_step075a_documents_and_failure_evidence_exist() -> None:
    required = (
        ROOT / "docs/issues/ISSUE_REGISTRY.md",
        ROOT / "docs/issues/OR-ISSUE-001-STEP075-WINDOWS-DOCKER-TMPFS-NORMALIZATION.md",
        ROOT / "docs/evidence/STEP075_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json",
        ROOT / "docs/plans/STEP075A_WINDOWS_DOCKER_TMPFS_NORMALIZATION_AND_FAILURE_EVIDENCE_FIX.md",
        ROOT / "docs/reference/STEP075A_WINDOWS_DOCKER_TMPFS_NORMALIZATION_AND_FAILURE_EVIDENCE_FIX_CODE_AUDIT.md",
    )
    assert all(path.is_file() for path in required)
