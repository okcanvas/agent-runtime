from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

from okcanvas_agent_runtime.agent.tools.codex.approval_contracts import (
    ApprovalDecision,
    ApprovalErrorCode,
    ApprovalRecord,
    ApprovalRecordState,
)
from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexUsageSummary
from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteResult
from okcanvas_agent_runtime.core.config import CodexWriteSettings
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.adapters.openai.runtime.codex_approval_gateway import (
    ApprovalGatewayPrepareResult,
    ApprovalGatewayResumeResult,
)
from okcanvas_agent_runtime.adapters.openai.runtime.codex_approval_service import CodexWriteApprovalService
from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import CodexReadiness
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_gateway import CodexWriteGatewayRunResult
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_service import CodexWriteService
from okcanvas_agent_runtime.adapters.workspace import snapshot_tree


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "approval@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Approval Test"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=path, check=True)


def _workspace(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "repo"
    shutil.copytree(root / "fixtures" / "codex_write_repo", workspace)
    _init_repo(workspace)
    return workspace


def _settings() -> CodexWriteSettings:
    return CodexWriteSettings(agent_model="agent", codex_model="codex", api_key="key")


class FakeApprovalGateway:
    def __init__(self) -> None:
        self.prepare_calls = 0
        self.resume_calls = 0
        self.executor_calls = 0

    def readiness(self, settings):
        return CodexReadiness(
            ready=True,
            sdk_installed=True,
            sdk_version="0.19.0",
            codex_cli_installed=True,
            codex_cli_path="/fake/codex",
            codex_cli_version="codex-cli 0.145.0",
            agent_model_configured=True,
            codex_model_configured=True,
            api_key_configured=True,
            experimental_codex_importable=True,
            issues=(),
        )

    async def prepare(self, *, settings, context, executor):
        self.prepare_calls += 1
        arguments = json.dumps({"execution_id": context["execution_id"]}, separators=(",", ":"))
        return ApprovalGatewayPrepareResult(
            state_json={"context": {"context": context}, "interruptions": [arguments]},
            tool_name="codex_workspace_write",
            call_id="call-approval",
            arguments=arguments,
            trace_id="trace-prepare",
            response_id="resp-prepare",
            agent_usage=UsageSummary(requests=1, input_tokens=10, output_tokens=2, total_tokens=12),
        )

    async def resume(self, *, settings, state_json, decision, executor):
        self.resume_calls += 1
        context = state_json["context"]["context"]
        output = None
        if decision == "APPROVE":
            self.executor_calls += 1
            output = await executor(context)
        return ApprovalGatewayResumeResult(
            final_output=output or "rejected",
            remaining_interruptions=0,
            trace_id="trace-resume",
            response_id="resp-resume",
            agent_usage=UsageSummary(requests=1, input_tokens=5, output_tokens=1, total_tokens=6),
        )


class FakeWriteGateway:
    def readiness(self, settings):
        return FakeApprovalGateway().readiness(settings)

    async def run(self, *, request, run_id, settings, workspace, journal):
        target = workspace / "src/inventory/pricing.py"
        target.write_text(
            'from __future__ import annotations\n\n\ndef calculate_total(lines: list[dict[str, int]]) -> int:\n    """Return an order total in Korean won."""\n    return sum(line["unit_price"] * line["quantity"] for line in lines)\n',
            encoding="utf-8",
        )
        journal.append(
            event_type="thread.started",
            payload={"type": "thread.started", "thread_id": "thread-approval"},
            thread_id="thread-approval",
        )
        journal.append(
            event_type="item.completed",
            payload={"type": "item.completed", "item": {"type": "file_change"}},
            thread_id="thread-approval",
        )
        return CodexWriteGatewayRunResult(
            output=CodexWriteResult(
                summary="Applied approved fix.",
                inspected_files=["src/inventory/pricing.py", "tests/test_pricing.py"],
                modified_files=["src/inventory/pricing.py"],
                commands_observed=["rg quantity"],
                unverified=["Independent validation pending"],
            ),
            agent_usage=UsageSummary(requests=2, input_tokens=50, output_tokens=10, total_tokens=60),
            codex_usage=CodexUsageSummary(input_tokens=40, output_tokens=8),
            trace_id="trace-write",
            response_id="resp-write",
            thread_id="thread-approval",
            sdk_version="0.19.0",
            codex_cli_version="codex-cli 0.145.0",
        )


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "state_file": tmp_path / "run-state.json",
        "approval_file": tmp_path / "approval.json",
        "event_file": tmp_path / "events.jsonl",
        "patch_file": tmp_path / "change.patch",
        "write_evidence_file": tmp_path / "write-run.json",
    }


def _prepare(service, workspace, paths):
    return asyncio.run(
        service.prepare(
            request="Fix quantity minimally",
            settings=_settings(),
            workspace=workspace,
            **paths,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
            disposable_workspace_opt_in=True,
            workspace_write_opt_in=True,
            allowed_files=("src/inventory/pricing.py",),
            expected_files=("src/inventory/pricing.py",),
        )
    )


def test_prepare_persists_interruption_without_codex_or_mutation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    before = snapshot_tree(workspace)
    gateway = FakeApprovalGateway()
    service = CodexWriteApprovalService(gateway, CodexWriteService(FakeWriteGateway()))
    paths = _paths(tmp_path / "evidence")

    envelope = _prepare(service, workspace, paths)

    assert envelope.state == "AWAITING_APPROVAL"
    assert envelope.codex_called is False
    assert gateway.executor_calls == 0
    assert snapshot_tree(workspace) == before
    record = ApprovalRecord.model_validate_json(paths["approval_file"].read_text(encoding="utf-8"))
    assert record.state is ApprovalRecordState.PENDING
    assert record.execution_count == 0
    assert paths["state_file"].is_file()
    assert not paths["event_file"].exists()
    assert not paths["patch_file"].exists()


def test_approve_executes_exactly_once_and_blocks_second_resume(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    workspace = _workspace(tmp_path)
    gateway = FakeApprovalGateway()
    service = CodexWriteApprovalService(gateway, CodexWriteService(FakeWriteGateway()))
    paths = _paths(tmp_path / "evidence")
    assert _prepare(service, workspace, paths).state == "AWAITING_APPROVAL"

    approved = asyncio.run(
        service.resume(
            settings=_settings(),
            approval_file=paths["approval_file"],
            decision=ApprovalDecision.APPROVE,
        )
    )
    assert approved.state == "SUCCEEDED"
    assert approved.execution_count == 1
    assert approved.workspace_mutated is True
    assert gateway.executor_calls == 1
    record = ApprovalRecord.model_validate_json(paths["approval_file"].read_text(encoding="utf-8"))
    assert record.state is ApprovalRecordState.SUCCEEDED
    assert record.execution_count == 1
    assert paths["write_evidence_file"].is_file()

    second = asyncio.run(
        service.resume(
            settings=_settings(),
            approval_file=paths["approval_file"],
            decision=ApprovalDecision.APPROVE,
        )
    )
    assert second.state == "FAILED"
    assert second.error is not None
    assert second.error.code is ApprovalErrorCode.APPROVAL_ALREADY_DECIDED
    assert gateway.executor_calls == 1


def test_reject_never_executes_codex_or_mutates_workspace(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    before = snapshot_tree(workspace)
    gateway = FakeApprovalGateway()
    service = CodexWriteApprovalService(gateway, CodexWriteService(FakeWriteGateway()))
    paths = _paths(tmp_path / "evidence")
    assert _prepare(service, workspace, paths).state == "AWAITING_APPROVAL"

    rejected = asyncio.run(
        service.resume(
            settings=_settings(),
            approval_file=paths["approval_file"],
            decision=ApprovalDecision.REJECT,
        )
    )
    assert rejected.state == "REJECTED"
    assert rejected.execution_count == 0
    assert rejected.workspace_mutated is False
    assert gateway.executor_calls == 0
    assert snapshot_tree(workspace) == before
    assert not paths["write_evidence_file"].exists()
    record = ApprovalRecord.model_validate_json(paths["approval_file"].read_text(encoding="utf-8"))
    assert record.state is ApprovalRecordState.REJECTED


def test_resume_rejects_tampered_run_state(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    gateway = FakeApprovalGateway()
    service = CodexWriteApprovalService(gateway, CodexWriteService(FakeWriteGateway()))
    paths = _paths(tmp_path / "evidence")
    assert _prepare(service, workspace, paths).state == "AWAITING_APPROVAL"
    paths["state_file"].write_text("{}\n", encoding="utf-8")

    result = asyncio.run(
        service.resume(
            settings=_settings(),
            approval_file=paths["approval_file"],
            decision=ApprovalDecision.APPROVE,
        )
    )
    assert result.state == "FAILED"
    assert result.error is not None
    assert result.error.code is ApprovalErrorCode.RUN_STATE_HASH_MISMATCH
    assert gateway.resume_calls == 0
    assert gateway.executor_calls == 0
