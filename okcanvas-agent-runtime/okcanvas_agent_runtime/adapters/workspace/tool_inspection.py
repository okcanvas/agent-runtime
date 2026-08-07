from __future__ import annotations

import hashlib
from pathlib import Path

from okcanvas_agent_runtime.core.paths import PROJECT_ROOT
from okcanvas_agent_runtime.adapters.workspace import inspect_readonly_project
from okcanvas_agent_runtime.agent.tools.function.implementations import _validate_text
from okcanvas_agent_runtime.agent.tools.function.models import (
    ProjectEvidenceOutput, ProjectReadonlyInspectOutput, SandboxProjectReadonlyInspectOutput,
)

def project_readonly_inspect(root: str | Path, query: str) -> ProjectReadonlyInspectOutput:
    inspection = inspect_readonly_project(root, _validate_text(query))
    return ProjectReadonlyInspectOutput(
        workspace_label=inspection.workspace_label,
        snapshot_sha256=inspection.snapshot_sha256,
        files_considered=inspection.files_considered,
        bytes_considered=inspection.bytes_considered,
        inspected_files=list(inspection.inspected_files),
        evidence=[
            ProjectEvidenceOutput(
                path=item.path,
                line_start=item.line_start,
                line_end=item.line_end,
                excerpt=item.excerpt,
            )
            for item in inspection.evidence
        ],
        evidence_characters=inspection.evidence_characters,
        query_terms_considered=inspection.query_terms_considered,
        truncated=inspection.truncated,
    )


def sandbox_project_readonly_inspect(
    root: str | Path,
    query: str,
    *,
    image_reference: str,
    runner=None,
    temporary_parent: str | Path | None = None,
) -> SandboxProjectReadonlyInspectOutput:
    """Run bounded project inspection inside the Product-owned Docker Sandbox."""
    from okcanvas_agent_runtime.adapters.sandbox.docker import ProductOwnedReadonlySandboxInspector, SandboxRuntimeCatalog, SubprocessDockerCommandRunner

    foundation = SandboxRuntimeCatalog(PROJECT_ROOT).resolve()
    active_runner = runner or SubprocessDockerCommandRunner(
        max_output_bytes=foundation.provider.max_captured_output_bytes
    )
    result = ProductOwnedReadonlySandboxInspector(foundation, active_runner).inspect(
        source_root=root,
        query=_validate_text(query),
        image_reference=image_reference,
        temporary_parent=temporary_parent,
    )
    inspection = result.inspection
    return SandboxProjectReadonlyInspectOutput(
        workspace_label=inspection.workspace_label,
        snapshot_sha256=inspection.snapshot_sha256,
        files_considered=inspection.files_considered,
        bytes_considered=inspection.bytes_considered,
        inspected_files=list(inspection.inspected_files),
        evidence=[
            ProjectEvidenceOutput(
                path=item.path,
                line_start=item.line_start,
                line_end=item.line_end,
                excerpt=item.excerpt,
            )
            for item in inspection.evidence
        ],
        evidence_characters=inspection.evidence_characters,
        query_terms_considered=inspection.query_terms_considered,
        truncated=inspection.truncated,
        workspace_access="sandbox-readonly-v1",
        workspace_materialized=True,
        docker_call_count=result.lifecycle.docker_call_count,
        selected_file_hashes_verified=result.lifecycle.selected_file_hashes_verified,
        cleanup_state=result.lifecycle.cleanup_state,
        orphan_count=result.lifecycle.orphan_count,
        image_binding_sha256=hashlib.sha256(
            result.lifecycle.image.immutable_reference.encode("utf-8")
        ).hexdigest(),
        network_mode="none",
        shell_enabled=False,
        apply_patch_enabled=False,
    )
