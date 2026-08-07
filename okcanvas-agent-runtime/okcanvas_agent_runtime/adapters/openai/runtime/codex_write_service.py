from __future__ import annotations

import hashlib
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexUsageSummary
from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteEnvelope, CodexWriteError, CodexWriteErrorCode
from okcanvas_agent_runtime.agent.tools.codex.write_errors import CodexWriteFailure
from okcanvas_agent_runtime.core.config import CodexWriteSettings
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.adapters.evidence import JsonlEventJournal
from okcanvas_agent_runtime.adapters.workspace import snapshot_tree
from okcanvas_agent_runtime.adapters.workspace.git_diff import GitInspectionError, git_head, inspect_git
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_gateway import CodexWriteGateway


MAX_CODEX_WRITE_REQUEST_CHARS = 100_000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_relative_file(value: str) -> str | None:
    candidate = value.strip().replace("\\", "/")
    while candidate.startswith("./"):
        candidate = candidate[2:]
    path = PurePosixPath(candidate)
    if not candidate or path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _atomic_write_bytes(path: Path, payload: bytes) -> str:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(payload).hexdigest()


class CodexWriteService:
    def __init__(self, gateway: CodexWriteGateway):
        self._gateway = gateway

    async def run(
        self,
        *,
        request: str,
        settings: CodexWriteSettings,
        workspace: Path,
        event_file: Path,
        patch_file: Path,
        live_opt_in: bool,
        trusted_workspace_opt_in: bool,
        disposable_workspace_opt_in: bool,
        workspace_write_opt_in: bool,
        allowed_files: tuple[str, ...],
        expected_files: tuple[str, ...] = (),
        artifact_paths: tuple[Path, ...] = (),
        request_id: str | None = None,
    ) -> CodexWriteEnvelope:
        run_id = _identifier("codexwrite")
        effective_request_id = request_id or _identifier("req")
        started_at = _utc_now()
        started_ns = time.monotonic_ns()
        normalized_request = request.strip()
        resolved_workspace = workspace.expanduser().resolve()
        before = None
        after = None
        baseline_commit: str | None = None
        final_commit: str | None = None
        journal: JsonlEventJournal | None = None
        normalized_allowed: set[str] = set()
        normalized_expected: set[str] = set()
        verified_modified: set[str] = set()
        diff = None
        patch_sha256: str | None = None

        def failed(
            failure: CodexWriteFailure,
            *,
            live_call: bool = False,
            thread_id: str | None = None,
            sdk_version: str | None = None,
            codex_cli_version: str | None = None,
            trace_id: str | None = None,
            response_id: str | None = None,
            agent_usage: UsageSummary | None = None,
            codex_usage: CodexUsageSummary | None = None,
            result=None,
        ) -> CodexWriteEnvelope:
            completed_at = _utc_now()
            mutation = bool(before and after and before.sha256 != after.sha256)
            return CodexWriteEnvelope(
                run_id=run_id,
                request_id=effective_request_id,
                state="FAILED",
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                agent_model=settings.agent_model,
                codex_model=settings.codex_model,
                sdk_version=sdk_version,
                codex_cli_version=codex_cli_version,
                trace_id=trace_id,
                response_id=response_id,
                thread_id=thread_id,
                workspace=str(resolved_workspace),
                input_sha256=_sha256_text(normalized_request),
                live_call=live_call,
                baseline_commit=baseline_commit,
                final_commit=final_commit,
                before=before,
                after=after,
                mutation_detected=mutation,
                event_file=str(journal.path) if journal else None,
                event_count=journal.count if journal else 0,
                event_sha256=journal.sha256() if journal else None,
                event_types=sorted(journal.event_types) if journal else [],
                item_types=sorted(journal.item_types) if journal else [],
                allowed_files=sorted(normalized_allowed),
                expected_files=sorted(normalized_expected),
                verified_modified_files=sorted(verified_modified),
                diff=diff,
                patch_file=str(patch_file.expanduser().resolve()) if patch_sha256 else None,
                patch_sha256=patch_sha256,
                result=result,
                agent_usage=agent_usage or UsageSummary(),
                codex_usage=codex_usage or CodexUsageSummary(),
                error=CodexWriteError(
                    code=failure.code,
                    message=failure.public_message,
                    retryable=failure.retryable,
                    detail_type=failure.detail_type,
                ),
            )

        if not normalized_request:
            return failed(CodexWriteFailure(CodexWriteErrorCode.INVALID_REQUEST, "Request must not be blank"))
        if len(normalized_request) > MAX_CODEX_WRITE_REQUEST_CHARS:
            return failed(CodexWriteFailure(CodexWriteErrorCode.INVALID_REQUEST, f"Request exceeds the {MAX_CODEX_WRITE_REQUEST_CHARS} character limit"))
        if not live_opt_in:
            return failed(CodexWriteFailure(CodexWriteErrorCode.LIVE_OPT_IN_REQUIRED, "Codex execution requires the explicit confirmation flag"))
        if not trusted_workspace_opt_in:
            return failed(CodexWriteFailure(CodexWriteErrorCode.WORKSPACE_TRUST_OPT_IN_REQUIRED, "Codex execution requires explicit confirmation that the workspace is controlled"))
        if not disposable_workspace_opt_in:
            return failed(CodexWriteFailure(CodexWriteErrorCode.DISPOSABLE_WORKSPACE_OPT_IN_REQUIRED, "Workspace write requires explicit confirmation that the workspace is disposable"))
        if not workspace_write_opt_in:
            return failed(CodexWriteFailure(CodexWriteErrorCode.WORKSPACE_WRITE_OPT_IN_REQUIRED, "Workspace write requires explicit confirmation of mutation"))
        if not resolved_workspace.is_dir():
            return failed(CodexWriteFailure(CodexWriteErrorCode.WORKSPACE_NOT_FOUND, "The requested workspace directory does not exist"))
        if not (resolved_workspace / ".git").exists():
            return failed(CodexWriteFailure(CodexWriteErrorCode.GIT_REPOSITORY_REQUIRED, "The controlled Codex workspace must be a Git repository"))

        external_artifacts = [event_file, patch_file, *artifact_paths]
        if any(_is_within(path.expanduser(), resolved_workspace) for path in external_artifacts):
            return failed(CodexWriteFailure(CodexWriteErrorCode.ARTIFACT_PATH_INSIDE_WORKSPACE, "Event, patch, and run Evidence files must be outside the disposable workspace"))

        for item in allowed_files:
            normalized = _normalize_relative_file(item)
            if normalized is None:
                return failed(CodexWriteFailure(CodexWriteErrorCode.INVALID_REQUEST, "Allowed file paths must be repository-relative and must not traverse parents"))
            normalized_allowed.add(normalized)
        if not normalized_allowed:
            return failed(CodexWriteFailure(CodexWriteErrorCode.INVALID_REQUEST, "At least one exact allowed file is required"))
        for item in expected_files:
            normalized = _normalize_relative_file(item)
            if normalized is None or normalized not in normalized_allowed:
                return failed(CodexWriteFailure(CodexWriteErrorCode.INVALID_REQUEST, "Expected files must be normalized members of the allowlist"))
            normalized_expected.add(normalized)

        readiness = self._gateway.readiness(settings)
        if not readiness.ready:
            issue = readiness.issues[0]
            return failed(
                CodexWriteFailure(CodexWriteErrorCode(issue.code.value), issue.message),
                sdk_version=readiness.sdk_version,
                codex_cli_version=readiness.codex_cli_version,
            )

        gateway_result = None
        try:
            before = snapshot_tree(resolved_workspace)
            if before.symlink_count:
                return failed(CodexWriteFailure(CodexWriteErrorCode.WORKSPACE_SYMLINK_NOT_ALLOWED, "STEP003 disposable workspaces must not contain symbolic links"))
            baseline_inspection = inspect_git(resolved_workspace)
            baseline_commit = baseline_inspection.head
            if not baseline_inspection.clean:
                return failed(CodexWriteFailure(CodexWriteErrorCode.WORKSPACE_NOT_CLEAN, "The disposable workspace must start from a clean committed baseline"))
            journal = JsonlEventJournal(event_file)
            gateway_result = await self._gateway.run(
                request=normalized_request,
                run_id=run_id,
                settings=settings,
                workspace=resolved_workspace,
                journal=journal,
            )
            after = snapshot_tree(resolved_workspace)
            final_commit = git_head(resolved_workspace)
            inspection = inspect_git(resolved_workspace)
            diff = inspection.diff
        except CodexWriteFailure as failure:
            if resolved_workspace.is_dir():
                after = snapshot_tree(resolved_workspace)
            return failed(failure, live_call=True)
        except (GitInspectionError, OSError, ValueError) as exc:
            if resolved_workspace.is_dir():
                after = snapshot_tree(resolved_workspace)
            return failed(CodexWriteFailure(CodexWriteErrorCode.INTERNAL_ERROR, "Unable to inspect the disposable Git workspace", detail_type=type(exc).__name__), live_call=gateway_result is not None)
        except Exception as exc:
            if resolved_workspace.is_dir():
                after = snapshot_tree(resolved_workspace)
            return failed(CodexWriteFailure(CodexWriteErrorCode.INTERNAL_ERROR, "Unexpected Codex workspace-write runtime failure", detail_type=type(exc).__name__), live_call=True)

        assert gateway_result is not None
        common = dict(
            live_call=True,
            thread_id=gateway_result.thread_id,
            sdk_version=gateway_result.sdk_version,
            codex_cli_version=gateway_result.codex_cli_version,
            trace_id=gateway_result.trace_id,
            response_id=gateway_result.response_id,
            agent_usage=gateway_result.agent_usage,
            codex_usage=gateway_result.codex_usage,
            result=gateway_result.output,
        )
        if baseline_commit != final_commit:
            return failed(CodexWriteFailure(CodexWriteErrorCode.COMMIT_CHANGED, "Codex must not commit or move HEAD in STEP003"), **common)
        if before.sha256 == after.sha256 or not diff.files:
            return failed(CodexWriteFailure(CodexWriteErrorCode.WORKSPACE_NOT_MUTATED, "Codex did not produce a source change"), **common)
        if journal.count == 0:
            return failed(CodexWriteFailure(CodexWriteErrorCode.CODEX_EVENT_EVIDENCE_MISSING, "Codex produced no JSONL event evidence"), **common)
        if not gateway_result.thread_id:
            return failed(CodexWriteFailure(CodexWriteErrorCode.CODEX_THREAD_ID_MISSING, "Codex did not return a thread ID"), **common)
        if "web_search" in journal.item_types:
            return failed(CodexWriteFailure(CodexWriteErrorCode.WEB_SEARCH_EVENT_OBSERVED, "Web search is forbidden in STEP003"), **common)
        if "mcp_tool_call" in journal.item_types:
            return failed(CodexWriteFailure(CodexWriteErrorCode.MCP_EVENT_OBSERVED, "MCP calls are forbidden in STEP003"), **common)
        if diff.untracked_files:
            return failed(CodexWriteFailure(CodexWriteErrorCode.UNTRACKED_FILE_NOT_ALLOWED, "Codex created untracked files", detail_type=",".join(diff.untracked_files)), **common)
        if diff.staged_files:
            return failed(CodexWriteFailure(CodexWriteErrorCode.STAGED_CHANGE_NOT_ALLOWED, "Codex staged changes in the disposable workspace", detail_type=",".join(diff.staged_files)), **common)
        if any(change.status == "D" for change in diff.changes):
            return failed(CodexWriteFailure(CodexWriteErrorCode.FILE_DELETION_NOT_ALLOWED, "File deletion is forbidden in STEP003"), **common)
        if any(change.status != "M" for change in diff.changes):
            return failed(CodexWriteFailure(CodexWriteErrorCode.MODIFIED_FILE_OUTSIDE_ALLOWLIST, "STEP003 permits modification of existing files only"), **common)
        if any(change.binary for change in diff.changes):
            return failed(CodexWriteFailure(CodexWriteErrorCode.BINARY_CHANGE_NOT_ALLOWED, "Binary changes are forbidden in STEP003"), **common)

        verified_modified = set(diff.files)
        outside = sorted(verified_modified - normalized_allowed)
        if outside:
            return failed(CodexWriteFailure(CodexWriteErrorCode.MODIFIED_FILE_OUTSIDE_ALLOWLIST, "Codex modified files outside the exact allowlist", detail_type=",".join(outside)), **common)
        missing = sorted(normalized_expected - verified_modified)
        if missing:
            return failed(CodexWriteFailure(CodexWriteErrorCode.EXPECTED_FILE_NOT_MODIFIED, "Codex did not modify every expected file", detail_type=",".join(missing)), **common)

        reported = {
            normalized
            for item in gateway_result.output.modified_files
            if (normalized := _normalize_relative_file(item)) is not None
        }
        if reported != verified_modified:
            return failed(CodexWriteFailure(CodexWriteErrorCode.REPORTED_CHANGE_MISMATCH, "Codex reported modified files do not exactly match the Git diff"), **common)
        if gateway_result.agent_usage.total_tokens > settings.max_agent_total_tokens:
            return failed(CodexWriteFailure(CodexWriteErrorCode.AGENT_TOKEN_BUDGET_EXCEEDED, "Agent token budget exceeded"), **common)
        codex_total = gateway_result.codex_usage.input_tokens + gateway_result.codex_usage.output_tokens
        if codex_total > settings.max_codex_total_tokens:
            return failed(CodexWriteFailure(CodexWriteErrorCode.CODEX_TOKEN_BUDGET_EXCEEDED, "Codex token budget exceeded"), **common)

        try:
            patch_sha256 = _atomic_write_bytes(patch_file, inspection.patch)
        except OSError as exc:
            return failed(CodexWriteFailure(CodexWriteErrorCode.EVIDENCE_WRITE_FAILED, "Unable to write patch Evidence", detail_type=type(exc).__name__), **common)

        completed_at = _utc_now()
        return CodexWriteEnvelope(
            run_id=run_id,
            request_id=effective_request_id,
            state="SUCCEEDED",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
            agent_model=settings.agent_model,
            codex_model=settings.codex_model,
            sdk_version=gateway_result.sdk_version,
            codex_cli_version=gateway_result.codex_cli_version,
            trace_id=gateway_result.trace_id,
            response_id=gateway_result.response_id,
            thread_id=gateway_result.thread_id,
            workspace=str(resolved_workspace),
            input_sha256=_sha256_text(normalized_request),
            live_call=True,
            baseline_commit=baseline_commit,
            final_commit=final_commit,
            before=before,
            after=after,
            mutation_detected=True,
            event_file=str(journal.path),
            event_count=journal.count,
            event_sha256=journal.sha256(),
            event_types=sorted(journal.event_types),
            item_types=sorted(journal.item_types),
            allowed_files=sorted(normalized_allowed),
            expected_files=sorted(normalized_expected),
            verified_modified_files=sorted(verified_modified),
            diff=diff,
            patch_file=str(patch_file.expanduser().resolve()),
            patch_sha256=patch_sha256,
            result=gateway_result.output,
            agent_usage=gateway_result.agent_usage,
            codex_usage=gateway_result.codex_usage,
        )
