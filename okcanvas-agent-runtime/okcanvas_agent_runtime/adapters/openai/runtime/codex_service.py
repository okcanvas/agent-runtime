from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyEnvelope, CodexReadOnlyError, CodexReadOnlyErrorCode, CodexUsageSummary
from okcanvas_agent_runtime.agent.tools.codex.readonly_errors import CodexReadOnlyFailure
from okcanvas_agent_runtime.core.config import CodexReadOnlySettings
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.adapters.evidence import JsonlEventJournal, load_thread_state, write_thread_state
from okcanvas_agent_runtime.adapters.workspace import snapshot_tree
from okcanvas_agent_runtime.adapters.openai.runtime.codex_gateway import CodexReadOnlyGateway


MAX_CODEX_REQUEST_CHARS = 100_000


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


def _verified_workspace_file(root: Path, relative: str) -> bool:
    candidate = root / relative
    return candidate.is_file() and _is_within(candidate, root)


class CodexReadOnlyService:
    def __init__(self, gateway: CodexReadOnlyGateway):
        self._gateway = gateway

    async def run(
        self,
        *,
        request: str,
        settings: CodexReadOnlySettings,
        workspace: Path,
        event_file: Path,
        thread_state_file: Path | None,
        live_opt_in: bool,
        trusted_workspace_opt_in: bool,
        required_files: tuple[str, ...] = (),
        artifact_paths: tuple[Path, ...] = (),
        request_id: str | None = None,
    ) -> CodexReadOnlyEnvelope:
        run_id = _identifier("codexrun")
        effective_request_id = request_id or _identifier("req")
        started_at = _utc_now()
        started_ns = time.monotonic_ns()
        normalized_request = request.strip()
        resolved_workspace = workspace.expanduser().resolve()
        before = None
        after = None
        journal: JsonlEventJournal | None = None
        resumed_thread = False
        normalized_required: set[str] = set()
        verified_inspected_files: set[str] = set()

        def failed(
            failure: CodexReadOnlyFailure,
            *,
            live_call: bool = False,
            thread_id: str | None = None,
            sdk_version: str | None = None,
            codex_cli_version: str | None = None,
            trace_id: str | None = None,
            response_id: str | None = None,
            agent_usage: UsageSummary | None = None,
            codex_usage: CodexUsageSummary | None = None,
        ) -> CodexReadOnlyEnvelope:
            completed_at = _utc_now()
            mutation = bool(before and after and before.sha256 != after.sha256)
            return CodexReadOnlyEnvelope(
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
                resumed_thread=resumed_thread,
                workspace=str(resolved_workspace),
                input_sha256=_sha256_text(normalized_request),
                live_call=live_call,
                before=before,
                after=after,
                mutation_detected=mutation,
                event_file=str(journal.path) if journal else None,
                event_count=journal.count if journal else 0,
                event_sha256=journal.sha256() if journal else None,
                event_types=sorted(journal.event_types) if journal else [],
                item_types=sorted(journal.item_types) if journal else [],
                required_files=sorted(normalized_required),
                verified_inspected_files=sorted(verified_inspected_files),
                agent_usage=agent_usage or UsageSummary(),
                codex_usage=codex_usage or CodexUsageSummary(),
                error=CodexReadOnlyError(
                    code=failure.code,
                    message=failure.public_message,
                    retryable=failure.retryable,
                    detail_type=failure.detail_type,
                ),
            )

        if not normalized_request:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.INVALID_REQUEST,
                    "Request must not be blank",
                )
            )
        if len(normalized_request) > MAX_CODEX_REQUEST_CHARS:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.INVALID_REQUEST,
                    f"Request exceeds the {MAX_CODEX_REQUEST_CHARS} character limit",
                )
            )
        if not live_opt_in:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.LIVE_OPT_IN_REQUIRED,
                    "Codex execution requires the explicit confirmation flag",
                )
            )
        if not trusted_workspace_opt_in:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.WORKSPACE_TRUST_OPT_IN_REQUIRED,
                    "Codex execution requires explicit confirmation that the workspace is controlled",
                )
            )
        if not resolved_workspace.is_dir():
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.WORKSPACE_NOT_FOUND,
                    "The requested workspace directory does not exist",
                )
            )

        if not (resolved_workspace / ".git").exists():
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.GIT_REPOSITORY_REQUIRED,
                    "The controlled Codex workspace must be a Git repository",
                )
            )

        external_artifacts = [event_file, *artifact_paths]
        if thread_state_file is not None:
            external_artifacts.append(thread_state_file)
        if any(_is_within(path.expanduser(), resolved_workspace) for path in external_artifacts):
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.ARTIFACT_PATH_INSIDE_WORKSPACE,
                    "Event, thread, and run Evidence files must be outside the analyzed workspace",
                )
            )

        for item in required_files:
            normalized = _normalize_relative_file(item)
            if normalized is None:
                return failed(
                    CodexReadOnlyFailure(
                        CodexReadOnlyErrorCode.INVALID_REQUEST,
                        "Required file paths must be repository-relative and must not traverse parents",
                    )
                )
            normalized_required.add(normalized)

        readiness = self._gateway.readiness(settings)
        if not readiness.ready:
            issue = readiness.issues[0]
            return failed(
                CodexReadOnlyFailure(issue.code, issue.message),
                sdk_version=readiness.sdk_version,
                codex_cli_version=readiness.codex_cli_version,
            )

        try:
            before = snapshot_tree(resolved_workspace)
            if before.symlink_count:
                return failed(
                    CodexReadOnlyFailure(
                        CodexReadOnlyErrorCode.WORKSPACE_SYMLINK_NOT_ALLOWED,
                        "STEP002 controlled workspaces must not contain symbolic links",
                    )
                )
            state = load_thread_state(thread_state_file)
            existing_thread_id = None
            if state is not None:
                if state.workspace != str(resolved_workspace) or state.workspace_sha256 != before.sha256:
                    return failed(
                        CodexReadOnlyFailure(
                            CodexReadOnlyErrorCode.THREAD_STATE_INVALID,
                            "Stored Codex thread belongs to a different workspace snapshot",
                        )
                    )
                existing_thread_id = state.thread_id
                resumed_thread = True
            journal = JsonlEventJournal(event_file)
            gateway_result = await self._gateway.run(
                request=normalized_request,
                run_id=run_id,
                settings=settings,
                workspace=resolved_workspace,
                existing_thread_id=existing_thread_id,
                journal=journal,
            )
        except CodexReadOnlyFailure as failure:
            if resolved_workspace.is_dir():
                after = snapshot_tree(resolved_workspace)
            return failed(
                failure,
                live_call=failure.code
                in {
                    CodexReadOnlyErrorCode.CODEX_RUN_FAILED,
                    CodexReadOnlyErrorCode.OUTPUT_CONTRACT_INVALID,
                },
            )
        except Exception as exc:
            if resolved_workspace.is_dir():
                after = snapshot_tree(resolved_workspace)
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.INTERNAL_ERROR,
                    "Unexpected Codex read-only runtime failure",
                    detail_type=type(exc).__name__,
                ),
                live_call=True,
            )

        after = snapshot_tree(resolved_workspace)
        if before.sha256 != after.sha256:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.WORKSPACE_MUTATED,
                    "Read-only Codex execution changed the workspace",
                ),
                live_call=True,
                thread_id=gateway_result.thread_id,
                sdk_version=gateway_result.sdk_version,
                codex_cli_version=gateway_result.codex_cli_version,
                trace_id=gateway_result.trace_id,
                response_id=gateway_result.response_id,
                agent_usage=gateway_result.agent_usage,
                codex_usage=gateway_result.codex_usage,
            )

        if journal.count == 0:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.CODEX_EVENT_EVIDENCE_MISSING,
                    "Codex produced no JSONL event evidence",
                ),
                live_call=True,
                thread_id=gateway_result.thread_id,
                sdk_version=gateway_result.sdk_version,
                codex_cli_version=gateway_result.codex_cli_version,
                trace_id=gateway_result.trace_id,
                response_id=gateway_result.response_id,
                agent_usage=gateway_result.agent_usage,
                codex_usage=gateway_result.codex_usage,
            )
        if not gateway_result.thread_id:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.CODEX_THREAD_ID_MISSING,
                    "Codex did not return a resumable thread ID",
                ),
                live_call=True,
                sdk_version=gateway_result.sdk_version,
                codex_cli_version=gateway_result.codex_cli_version,
                trace_id=gateway_result.trace_id,
                response_id=gateway_result.response_id,
                agent_usage=gateway_result.agent_usage,
                codex_usage=gateway_result.codex_usage,
            )
        forbidden_items = {
            "file_change": CodexReadOnlyErrorCode.FILE_CHANGE_EVENT_OBSERVED,
            "web_search": CodexReadOnlyErrorCode.WEB_SEARCH_EVENT_OBSERVED,
            "mcp_tool_call": CodexReadOnlyErrorCode.MCP_EVENT_OBSERVED,
        }
        for item_type, code in forbidden_items.items():
            if item_type in journal.item_types:
                return failed(
                    CodexReadOnlyFailure(
                        code,
                        f"Forbidden Codex event observed in read-only mode: {item_type}",
                    ),
                    live_call=True,
                    thread_id=gateway_result.thread_id,
                    sdk_version=gateway_result.sdk_version,
                    codex_cli_version=gateway_result.codex_cli_version,
                    trace_id=gateway_result.trace_id,
                    response_id=gateway_result.response_id,
                    agent_usage=gateway_result.agent_usage,
                    codex_usage=gateway_result.codex_usage,
                )

        verified_inspected_files = {
            normalized
            for item in gateway_result.output.inspected_files
            if (normalized := _normalize_relative_file(item)) is not None
            and _verified_workspace_file(resolved_workspace, normalized)
        }
        if not verified_inspected_files:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.INSPECTION_EVIDENCE_MISSING,
                    "Codex did not report any verified repository file",
                ),
                live_call=True,
                thread_id=gateway_result.thread_id,
                sdk_version=gateway_result.sdk_version,
                codex_cli_version=gateway_result.codex_cli_version,
                trace_id=gateway_result.trace_id,
                response_id=gateway_result.response_id,
                agent_usage=gateway_result.agent_usage,
                codex_usage=gateway_result.codex_usage,
            )
        if normalized_required and "command_execution" not in journal.item_types:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.COMMAND_EVIDENCE_MISSING,
                    "Required-file acceptance needs at least one Codex command event",
                ),
                live_call=True,
                thread_id=gateway_result.thread_id,
                sdk_version=gateway_result.sdk_version,
                codex_cli_version=gateway_result.codex_cli_version,
                trace_id=gateway_result.trace_id,
                response_id=gateway_result.response_id,
                agent_usage=gateway_result.agent_usage,
                codex_usage=gateway_result.codex_usage,
            )
        missing = sorted(normalized_required - verified_inspected_files)
        if missing:
            return failed(
                CodexReadOnlyFailure(
                    CodexReadOnlyErrorCode.REQUIRED_FILE_NOT_DISCOVERED,
                    "Codex did not report every required relevant file",
                    detail_type=",".join(missing),
                ),
                live_call=True,
                thread_id=gateway_result.thread_id,
                sdk_version=gateway_result.sdk_version,
                codex_cli_version=gateway_result.codex_cli_version,
                trace_id=gateway_result.trace_id,
                response_id=gateway_result.response_id,
                agent_usage=gateway_result.agent_usage,
                codex_usage=gateway_result.codex_usage,
            )

        if thread_state_file is not None and gateway_result.thread_id:
            try:
                write_thread_state(
                    thread_state_file,
                    thread_id=gateway_result.thread_id,
                    workspace=str(resolved_workspace),
                    workspace_sha256=after.sha256,
                )
            except CodexReadOnlyFailure as failure:
                return failed(
                    failure,
                    live_call=True,
                    thread_id=gateway_result.thread_id,
                    sdk_version=gateway_result.sdk_version,
                    codex_cli_version=gateway_result.codex_cli_version,
                    trace_id=gateway_result.trace_id,
                    response_id=gateway_result.response_id,
                    agent_usage=gateway_result.agent_usage,
                    codex_usage=gateway_result.codex_usage,
                )

        completed_at = _utc_now()
        return CodexReadOnlyEnvelope(
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
            resumed_thread=resumed_thread,
            workspace=str(resolved_workspace),
            input_sha256=_sha256_text(normalized_request),
            live_call=True,
            before=before,
            after=after,
            mutation_detected=False,
            event_file=str(journal.path),
            event_count=journal.count,
            event_sha256=journal.sha256(),
            event_types=sorted(journal.event_types),
            item_types=sorted(journal.item_types),
            required_files=sorted(normalized_required),
            verified_inspected_files=sorted(verified_inspected_files),
            result=gateway_result.output,
            agent_usage=gateway_result.agent_usage,
            codex_usage=gateway_result.codex_usage,
        )
