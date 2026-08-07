from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from okcanvas_agent_runtime.agent.tools.codex.approval_contracts import ApprovalDecision, ApprovalError, ApprovalErrorCode, ApprovalInterruption, ApprovalPrepareEnvelope, ApprovalRecord, ApprovalRecordState, ApprovalResumeEnvelope
from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteEnvelope
from okcanvas_agent_runtime.core.config import CodexWriteSettings
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.adapters.evidence import write_run_evidence
from okcanvas_agent_runtime.adapters.workspace import snapshot_tree
from okcanvas_agent_runtime.adapters.workspace.git_diff import inspect_git
from okcanvas_agent_runtime.adapters.openai.runtime.codex_approval_gateway import OpenAICodexApprovalGateway
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_gateway import OpenAICodexWriteGateway
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_service import CodexWriteService


TOOL_NAME = "codex_workspace_write"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.expanduser().resolve().relative_to(root.expanduser().resolve())
        return True
    except ValueError:
        return False


def _normalize_file(value: str) -> str | None:
    candidate = value.strip().replace("\\", "/")
    while candidate.startswith("./"):
        candidate = candidate[2:]
    path = PurePosixPath(candidate)
    if not candidate or path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix()


def _atomic_write_json(path: Path, payload: Any, *, exclusive: bool = False) -> str:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    if exclusive and path.exists():
        raise FileExistsError(path)
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive and path.exists():
            raise FileExistsError(path)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return _sha256_bytes(data)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def _record_write(path: Path, record: ApprovalRecord) -> None:
    _atomic_write_json(path, record.model_dump(mode="json"))


def _error(code: ApprovalErrorCode, message: str, exc: Exception | None = None) -> ApprovalError:
    return ApprovalError(
        code=code,
        message=message,
        retryable=False,
        detail_type=type(exc).__name__ if exc else None,
    )


def _readiness_error(gateway: OpenAICodexApprovalGateway, settings: CodexWriteSettings) -> ApprovalError | None:
    readiness = gateway.readiness(settings)
    if readiness.ready:
        return None
    issue = readiness.issues[0]
    try:
        code = ApprovalErrorCode(issue.code.value)
    except ValueError:
        code = ApprovalErrorCode.INTERNAL_ERROR
    return _error(code, issue.message)


class CodexWriteApprovalService:
    def __init__(
        self,
        gateway: OpenAICodexApprovalGateway | None = None,
        write_service: CodexWriteService | None = None,
    ) -> None:
        self._gateway = gateway or OpenAICodexApprovalGateway()
        self._write_service = write_service or CodexWriteService(OpenAICodexWriteGateway())

    async def prepare(
        self,
        *,
        request: str,
        settings: CodexWriteSettings,
        workspace: Path,
        state_file: Path,
        approval_file: Path,
        event_file: Path,
        patch_file: Path,
        write_evidence_file: Path,
        live_opt_in: bool,
        trusted_workspace_opt_in: bool,
        disposable_workspace_opt_in: bool,
        workspace_write_opt_in: bool,
        allowed_files: tuple[str, ...],
        expected_files: tuple[str, ...],
        request_id: str | None = None,
    ) -> ApprovalPrepareEnvelope:
        started = _utc_now()
        started_ns = time.monotonic_ns()
        approval_id = _id("approval")
        execution_id = _id("execution")
        resolved_workspace = workspace.expanduser().resolve()
        normalized_request = request.strip()
        before = snapshot_tree(resolved_workspace) if resolved_workspace.is_dir() else None

        def failed(error: ApprovalError) -> ApprovalPrepareEnvelope:
            after = snapshot_tree(resolved_workspace) if resolved_workspace.is_dir() else None
            return ApprovalPrepareEnvelope(
                approval_id=approval_id,
                execution_id=execution_id,
                state="FAILED",
                started_at=started,
                completed_at=_utc_now(),
                duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                workspace=str(resolved_workspace),
                request_sha256=_sha256_text(normalized_request),
                workspace_unchanged=before == after,
                error=error,
            )

        if not normalized_request:
            return failed(_error(ApprovalErrorCode.INVALID_REQUEST, "Request must not be blank"))
        confirmations = [
            (live_opt_in, ApprovalErrorCode.LIVE_OPT_IN_REQUIRED, "Explicit live-call confirmation is required"),
            (trusted_workspace_opt_in, ApprovalErrorCode.WORKSPACE_TRUST_OPT_IN_REQUIRED, "Controlled workspace confirmation is required"),
            (disposable_workspace_opt_in, ApprovalErrorCode.DISPOSABLE_WORKSPACE_OPT_IN_REQUIRED, "Disposable workspace confirmation is required"),
            (workspace_write_opt_in, ApprovalErrorCode.WORKSPACE_WRITE_OPT_IN_REQUIRED, "Workspace write confirmation is required"),
        ]
        for confirmed, code, message in confirmations:
            if not confirmed:
                return failed(_error(code, message))
        if not resolved_workspace.is_dir():
            return failed(_error(ApprovalErrorCode.WORKSPACE_NOT_FOUND, "Workspace does not exist"))
        if not (resolved_workspace / ".git").exists():
            return failed(_error(ApprovalErrorCode.GIT_REPOSITORY_REQUIRED, "Workspace must be a Git repository"))
        if before and before.symlink_count:
            return failed(_error(ApprovalErrorCode.WORKSPACE_SYMLINK_NOT_ALLOWED, "Workspace symbolic links are forbidden"))
        try:
            if not inspect_git(resolved_workspace).clean:
                return failed(_error(ApprovalErrorCode.WORKSPACE_NOT_CLEAN, "Workspace must start clean"))
        except Exception as exc:
            return failed(_error(ApprovalErrorCode.GIT_REPOSITORY_REQUIRED, "Unable to inspect Git workspace", exc))

        artifacts = [state_file, approval_file, event_file, patch_file, write_evidence_file]
        if any(_is_within(path, resolved_workspace) for path in artifacts):
            return failed(_error(ApprovalErrorCode.ARTIFACT_PATH_INSIDE_WORKSPACE, "Approval and write artifacts must be outside the workspace"))
        if any(path.expanduser().resolve().exists() for path in (state_file, approval_file)):
            return failed(_error(ApprovalErrorCode.APPROVAL_ARTIFACT_EXISTS, "Approval state artifacts already exist"))

        normalized_allowed = []
        for value in allowed_files:
            normalized = _normalize_file(value)
            if normalized is None or not (resolved_workspace / normalized).is_file():
                return failed(_error(ApprovalErrorCode.INVALID_REQUEST, "Allowed files must be existing repository-relative files"))
            normalized_allowed.append(normalized)
        if not normalized_allowed:
            return failed(_error(ApprovalErrorCode.INVALID_REQUEST, "At least one allowed file is required"))
        normalized_expected = []
        for value in expected_files:
            normalized = _normalize_file(value)
            if normalized is None or normalized not in normalized_allowed:
                return failed(_error(ApprovalErrorCode.INVALID_REQUEST, "Expected files must belong to the allowlist"))
            normalized_expected.append(normalized)

        readiness_error = _readiness_error(self._gateway, settings)
        if readiness_error:
            return failed(readiness_error)

        context: dict[str, Any] = {
            "schema_version": "okcanvas-codex-write-approval-context-v1",
            "approval_id": approval_id,
            "execution_id": execution_id,
            "request": normalized_request,
            "request_id": request_id or _id("req"),
            "workspace": str(resolved_workspace),
            "approval_file": str(approval_file.expanduser().resolve()),
            "event_file": str(event_file.expanduser().resolve()),
            "patch_file": str(patch_file.expanduser().resolve()),
            "write_evidence_file": str(write_evidence_file.expanduser().resolve()),
            "allowed_files": sorted(set(normalized_allowed)),
            "expected_files": sorted(set(normalized_expected)),
            "agent_model": settings.agent_model,
            "codex_model": settings.codex_model,
            "codex_path": settings.codex_path,
        }

        async def forbidden_executor(_context: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("Codex write executed before approval")

        try:
            prepared = await self._gateway.prepare(
                settings=settings,
                context=context,
                executor=forbidden_executor,
            )
            after = snapshot_tree(resolved_workspace)
            if before != after:
                return failed(_error(ApprovalErrorCode.APPROVAL_STATE_INVALID, "Workspace changed before approval"))
            if prepared.tool_name != TOOL_NAME or not prepared.call_id:
                return failed(_error(ApprovalErrorCode.APPROVAL_INTERRUPTION_INVALID, "Unexpected approval interruption"))
            try:
                arguments = json.loads(prepared.arguments)
            except json.JSONDecodeError as exc:
                return failed(_error(ApprovalErrorCode.APPROVAL_INTERRUPTION_INVALID, "Approval arguments are not valid JSON", exc))
            if arguments != {"execution_id": execution_id}:
                return failed(_error(ApprovalErrorCode.APPROVAL_INTERRUPTION_INVALID, "Approval execution identifier mismatch"))
            state_sha = _atomic_write_json(state_file, prepared.state_json, exclusive=True)
            now = _utc_now()
            interruption = ApprovalInterruption(
                tool_name=prepared.tool_name,
                call_id=prepared.call_id,
                arguments_sha256=_sha256_text(prepared.arguments),
            )
            record = ApprovalRecord(
                approval_id=approval_id,
                execution_id=execution_id,
                state=ApprovalRecordState.PENDING,
                created_at=now,
                updated_at=now,
                request_sha256=_sha256_text(normalized_request),
                workspace=str(resolved_workspace),
                state_file=str(state_file.expanduser().resolve()),
                state_sha256=state_sha,
                event_file=str(event_file.expanduser().resolve()),
                patch_file=str(patch_file.expanduser().resolve()),
                write_evidence_file=str(write_evidence_file.expanduser().resolve()),
                allowed_files=sorted(set(normalized_allowed)),
                expected_files=sorted(set(normalized_expected)),
                interruption=interruption,
                agent_model=str(settings.agent_model),
                codex_model=str(settings.codex_model),
                codex_path=settings.codex_path,
                request_id=context["request_id"],
            )
            _atomic_write_json(approval_file, record.model_dump(mode="json"), exclusive=True)
            return ApprovalPrepareEnvelope(
                approval_id=approval_id,
                execution_id=execution_id,
                state="AWAITING_APPROVAL",
                started_at=started,
                completed_at=_utc_now(),
                duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                workspace=str(resolved_workspace),
                request_sha256=record.request_sha256,
                state_file=record.state_file,
                state_sha256=state_sha,
                approval_file=str(approval_file.expanduser().resolve()),
                interruption=interruption,
                workspace_unchanged=True,
                codex_called=False,
                trace_id=prepared.trace_id,
                response_id=prepared.response_id,
                agent_usage=prepared.agent_usage,
            )
        except FileExistsError as exc:
            return failed(_error(ApprovalErrorCode.APPROVAL_ARTIFACT_EXISTS, "Approval artifacts already exist", exc))
        except Exception as exc:
            return failed(_error(ApprovalErrorCode.AGENT_RUN_FAILED, "Unable to create persisted approval interruption", exc))

    async def resume(
        self,
        *,
        settings: CodexWriteSettings,
        approval_file: Path,
        decision: ApprovalDecision,
    ) -> ApprovalResumeEnvelope:
        started = _utc_now()
        started_ns = time.monotonic_ns()
        approval_path = approval_file.expanduser().resolve()
        placeholder_id = "unknown"
        placeholder_execution = "unknown"
        placeholder_workspace = ""

        def failed(error: ApprovalError, *, record: ApprovalRecord | None = None, mutated: bool = False) -> ApprovalResumeEnvelope:
            return ApprovalResumeEnvelope(
                approval_id=record.approval_id if record else placeholder_id,
                execution_id=record.execution_id if record else placeholder_execution,
                state="FAILED",
                decision=decision,
                started_at=started,
                completed_at=_utc_now(),
                duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                workspace=record.workspace if record else placeholder_workspace,
                execution_count=record.execution_count if record else 0,
                workspace_mutated=mutated,
                write_run_id=record.write_run_id if record else None,
                write_run_state=record.write_run_state if record else None,
                write_run_sha256=record.write_run_sha256 if record else None,
                error=error,
            )

        if not approval_path.is_file():
            return failed(_error(ApprovalErrorCode.APPROVAL_RECORD_NOT_FOUND, "Approval record does not exist"))
        try:
            record = ApprovalRecord.model_validate(_read_json(approval_path))
        except Exception as exc:
            return failed(_error(ApprovalErrorCode.APPROVAL_STATE_INVALID, "Approval record is invalid", exc))
        workspace = Path(record.workspace)
        before = snapshot_tree(workspace) if workspace.is_dir() else None
        if record.state is not ApprovalRecordState.PENDING:
            return failed(_error(ApprovalErrorCode.APPROVAL_ALREADY_DECIDED, "Approval has already been decided"), record=record)
        state_path = Path(record.state_file)
        if not state_path.is_file():
            return failed(_error(ApprovalErrorCode.RUN_STATE_NOT_FOUND, "Persisted RunState does not exist"), record=record)
        raw_state = state_path.read_bytes()
        if _sha256_bytes(raw_state) != record.state_sha256:
            return failed(_error(ApprovalErrorCode.RUN_STATE_HASH_MISMATCH, "Persisted RunState hash mismatch"), record=record)
        try:
            state_json = json.loads(raw_state.decode("utf-8"))
        except Exception as exc:
            return failed(_error(ApprovalErrorCode.APPROVAL_STATE_INVALID, "Persisted RunState is invalid", exc), record=record)
        readiness_error = _readiness_error(self._gateway, settings)
        if readiness_error:
            return failed(readiness_error, record=record)

        now = _utc_now()
        record.state = (
            ApprovalRecordState.APPROVED
            if decision is ApprovalDecision.APPROVE
            else ApprovalRecordState.REJECTED
        )
        record.decision = decision
        record.decided_at = now
        record.updated_at = now
        _record_write(approval_path, record)

        async def executor(context: dict[str, Any]) -> dict[str, Any]:
            current = ApprovalRecord.model_validate(_read_json(approval_path))
            if current.state is not ApprovalRecordState.APPROVED or current.execution_count != 0:
                raise RuntimeError("Approval execution has already been claimed")
            lock_path = approval_path.with_suffix(approval_path.suffix + ".execute.lock")
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
            except FileExistsError as exc:
                raise RuntimeError("Approval execution lock already exists") from exc
            current.state = ApprovalRecordState.EXECUTING
            current.execution_count = 1
            current.execution_started_at = _utc_now()
            current.updated_at = current.execution_started_at
            _record_write(approval_path, current)
            write_settings = CodexWriteSettings.from_env(
                agent_model_override=context.get("agent_model"),
                codex_model_override=context.get("codex_model"),
                codex_path_override=context.get("codex_path"),
            )
            envelope = await self._write_service.run(
                request=str(context["request"]),
                settings=write_settings,
                workspace=Path(context["workspace"]),
                event_file=Path(context["event_file"]),
                patch_file=Path(context["patch_file"]),
                live_opt_in=True,
                trusted_workspace_opt_in=True,
                disposable_workspace_opt_in=True,
                workspace_write_opt_in=True,
                allowed_files=tuple(context["allowed_files"]),
                expected_files=tuple(context["expected_files"]),
                artifact_paths=(Path(context["write_evidence_file"]), Path(context["approval_file"])),
                request_id=str(context["request_id"]),
            )
            write_run_path = Path(context["write_evidence_file"])
            write_run_evidence(write_run_path, envelope)
            current = ApprovalRecord.model_validate(_read_json(approval_path))
            current.state = (
                ApprovalRecordState.SUCCEEDED
                if envelope.state == "SUCCEEDED"
                else ApprovalRecordState.FAILED
            )
            current.execution_completed_at = _utc_now()
            current.updated_at = current.execution_completed_at
            current.write_run_id = envelope.run_id
            current.write_run_state = envelope.state
            current.write_run_sha256 = _sha256_bytes(write_run_path.read_bytes())
            if envelope.error:
                current.error = _error(
                    ApprovalErrorCode.CODEX_WRITE_FAILED,
                    envelope.error.message,
                )
            _record_write(approval_path, current)
            return envelope.model_dump(mode="json")

        try:
            resumed = await self._gateway.resume(
                settings=settings,
                state_json=state_json,
                decision=decision.value,
                executor=executor,
            )
            current = ApprovalRecord.model_validate(_read_json(approval_path))
            after = snapshot_tree(workspace) if workspace.is_dir() else None
            mutated = before != after
            if resumed.remaining_interruptions:
                return failed(_error(ApprovalErrorCode.APPROVAL_INTERRUPTION_INVALID, "Resume produced another approval interruption"), record=current, mutated=mutated)
            if decision is ApprovalDecision.REJECT:
                if current.execution_count != 0 or mutated:
                    return failed(_error(ApprovalErrorCode.APPROVAL_STATE_INVALID, "Rejected approval executed or changed the workspace"), record=current, mutated=mutated)
                return ApprovalResumeEnvelope(
                    approval_id=current.approval_id,
                    execution_id=current.execution_id,
                    state="REJECTED",
                    decision=decision,
                    started_at=started,
                    completed_at=_utc_now(),
                    duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                    workspace=current.workspace,
                    execution_count=0,
                    workspace_mutated=False,
                    trace_id=resumed.trace_id,
                    response_id=resumed.response_id,
                    agent_usage=resumed.agent_usage,
                )
            if current.execution_count != 1 or current.state is not ApprovalRecordState.SUCCEEDED:
                return failed(_error(ApprovalErrorCode.CODEX_WRITE_FAILED, "Approved Codex write did not complete successfully"), record=current, mutated=mutated)
            return ApprovalResumeEnvelope(
                approval_id=current.approval_id,
                execution_id=current.execution_id,
                state="SUCCEEDED",
                decision=decision,
                started_at=started,
                completed_at=_utc_now(),
                duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                workspace=current.workspace,
                execution_count=current.execution_count,
                workspace_mutated=mutated,
                write_run_id=current.write_run_id,
                write_run_state=current.write_run_state,
                write_run_sha256=current.write_run_sha256,
                trace_id=resumed.trace_id,
                response_id=resumed.response_id,
                agent_usage=resumed.agent_usage,
            )
        except Exception as exc:
            current = ApprovalRecord.model_validate(_read_json(approval_path))
            if current.state is ApprovalRecordState.APPROVED:
                current.state = ApprovalRecordState.FAILED
                current.updated_at = _utc_now()
                current.error = _error(ApprovalErrorCode.AGENT_RUN_FAILED, "Unable to resume approval RunState", exc)
                _record_write(approval_path, current)
            after = snapshot_tree(workspace) if workspace.is_dir() else None
            return failed(_error(ApprovalErrorCode.AGENT_RUN_FAILED, "Unable to resume approval RunState", exc), record=current, mutated=before != after)
