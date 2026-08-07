import asyncio
import shutil

import pytest
from pathlib import Path

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import (
    CodexFinding,
    CodexFindingSeverity,
    CodexReadOnlyErrorCode,
    CodexReadOnlyResult,
    CodexUsageSummary,
)
from okcanvas_agent_runtime.core.config import CodexReadOnlySettings
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.adapters.openai.runtime.codex_gateway import CodexGatewayRunResult
from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import CodexReadiness
from okcanvas_agent_runtime.adapters.openai.runtime.codex_service import CodexReadOnlyService


class FakeGateway:
    def __init__(
        self,
        *,
        inspected_files=None,
        mutate=False,
        emit_events=True,
        thread_id="thread_fixture",
        extra_item_type=None,
    ):
        self.inspected_files = inspected_files or [
            "src/inventory/pricing.py",
            "tests/test_pricing.py",
        ]
        self.mutate = mutate
        self.emit_events = emit_events
        self.thread_id = thread_id
        self.extra_item_type = extra_item_type
        self.existing_thread_ids = []

    def readiness(self, settings):
        return CodexReadiness(
            ready=True,
            sdk_installed=True,
            sdk_version="0.19.0",
            codex_cli_installed=True,
            codex_cli_path="/fake/codex",
            codex_cli_version="codex-cli 1.0.0",
            agent_model_configured=True,
            codex_model_configured=True,
            api_key_configured=True,
            experimental_codex_importable=True,
            issues=(),
        )

    async def run(
        self,
        *,
        request,
        run_id,
        settings,
        workspace,
        existing_thread_id,
        journal,
    ):
        self.existing_thread_ids.append(existing_thread_id)
        effective_thread_id = existing_thread_id or self.thread_id
        if self.emit_events:
            journal.append(
                event_type="thread.started",
                thread_id=effective_thread_id,
                payload={"type": "thread.started"},
            )
            journal.append(
                event_type="item.completed",
                thread_id=effective_thread_id,
                payload={
                    "type": "item.completed",
                    "item": {"type": "command_execution", "command": "rg quantity"},
                },
            )
            if self.extra_item_type:
                journal.append(
                    event_type="item.completed",
                    thread_id=effective_thread_id,
                    payload={
                        "type": "item.completed",
                        "item": {"type": self.extra_item_type},
                    },
                )
        if self.mutate:
            (workspace / "src/inventory/pricing.py").write_text("mutated\n", encoding="utf-8")
        return CodexGatewayRunResult(
            output=CodexReadOnlyResult(
                summary="Quantity is ignored.",
                inspected_files=self.inspected_files,
                commands_observed=["rg quantity"],
                findings=[
                    CodexFinding(
                        severity=CodexFindingSeverity.ERROR,
                        title="Quantity is not multiplied",
                        detail="The total sums unit prices only.",
                        evidence=["src/inventory/pricing.py"],
                    )
                ],
                unverified=["No tests were executed"],
            ),
            agent_usage=UsageSummary(requests=1, input_tokens=10, output_tokens=5, total_tokens=15),
            codex_usage=CodexUsageSummary(input_tokens=20, output_tokens=8),
            trace_id="trace_fixture",
            response_id="resp_fixture",
            thread_id=effective_thread_id,
            sdk_version="0.19.0",
            codex_cli_version="codex-cli 1.0.0",
        )


def _fixture_copy(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "fixtures" / "codex_readonly_repo"
    target = tmp_path / "repo"
    shutil.copytree(source, target)
    (target / ".git").mkdir()
    return target


def _settings() -> CodexReadOnlySettings:
    return CodexReadOnlySettings(
        agent_model="agent-model",
        codex_model="codex-model",
        api_key="secret",
    )


def test_success_preserves_workspace_and_persists_thread(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    gateway = FakeGateway()
    service = CodexReadOnlyService(gateway)
    thread_file = tmp_path / "thread.json"
    envelope = asyncio.run(
        service.run(
            request="Find why quantity totals are wrong. Do not modify files.",
            settings=_settings(),
            workspace=workspace,
            event_file=tmp_path / "events.jsonl",
            thread_state_file=thread_file,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
            required_files=("src/inventory/pricing.py", "tests/test_pricing.py"),
        )
    )
    assert envelope.state == "SUCCEEDED"
    assert envelope.mutation_detected is False
    assert envelope.before == envelope.after
    assert envelope.event_count == 2
    assert envelope.thread_id == "thread_fixture"
    assert envelope.event_types == ["item.completed", "thread.started"]
    assert envelope.item_types == ["command_execution"]
    assert envelope.required_files == ["src/inventory/pricing.py", "tests/test_pricing.py"]
    assert envelope.verified_inspected_files == [
        "src/inventory/pricing.py",
        "tests/test_pricing.py",
    ]
    assert thread_file.is_file()
    assert "secret" not in envelope.model_dump_json()


def test_second_run_resumes_saved_thread(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    gateway = FakeGateway()
    service = CodexReadOnlyService(gateway)
    thread_file = tmp_path / "thread.json"
    common = dict(
        request="Continue the same read-only analysis.",
        settings=_settings(),
        workspace=workspace,
        thread_state_file=thread_file,
        live_opt_in=True,
        trusted_workspace_opt_in=True,
    )
    first = asyncio.run(service.run(event_file=tmp_path / "first.jsonl", **common))
    second = asyncio.run(service.run(event_file=tmp_path / "second.jsonl", **common))
    assert first.state == "SUCCEEDED"
    assert second.state == "SUCCEEDED"
    assert second.resumed_thread is True
    assert gateway.existing_thread_ids == [None, "thread_fixture"]


def test_mutation_is_fail_closed(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    envelope = asyncio.run(
        CodexReadOnlyService(FakeGateway(mutate=True)).run(
            request="Analyze read-only.",
            settings=_settings(),
            workspace=workspace,
            event_file=tmp_path / "events.jsonl",
            thread_state_file=None,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.mutation_detected is True
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.WORKSPACE_MUTATED


def test_required_file_discovery_is_enforced(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    envelope = asyncio.run(
        CodexReadOnlyService(FakeGateway(inspected_files=["README.md"])).run(
            request="Analyze quantity defect.",
            settings=_settings(),
            workspace=workspace,
            event_file=tmp_path / "events.jsonl",
            thread_state_file=None,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
            required_files=("src/inventory/pricing.py",),
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.REQUIRED_FILE_NOT_DISCOVERED


def test_unconfirmed_run_does_not_create_event_file(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    event_file = tmp_path / "events.jsonl"
    envelope = asyncio.run(
        CodexReadOnlyService(FakeGateway()).run(
            request="Analyze.",
            settings=_settings(),
            workspace=workspace,
            event_file=event_file,
            thread_state_file=None,
            live_opt_in=False,
            trusted_workspace_opt_in=False,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.LIVE_OPT_IN_REQUIRED
    assert event_file.exists() is False


def test_artifact_paths_inside_workspace_are_rejected(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    envelope = asyncio.run(
        CodexReadOnlyService(FakeGateway()).run(
            request="Analyze read-only.",
            settings=_settings(),
            workspace=workspace,
            event_file=workspace / "events.jsonl",
            thread_state_file=None,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.ARTIFACT_PATH_INSIDE_WORKSPACE
    assert not (workspace / "events.jsonl").exists()


class NotReadyGateway(FakeGateway):
    def readiness(self, settings):
        from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import (
            CodexReadiness,
            CodexReadinessIssue,
        )

        return CodexReadiness(
            ready=False,
            sdk_installed=False,
            sdk_version=None,
            codex_cli_installed=False,
            codex_cli_path=None,
            codex_cli_version=None,
            agent_model_configured=True,
            codex_model_configured=True,
            api_key_configured=True,
            experimental_codex_importable=False,
            issues=(
                CodexReadinessIssue(
                    CodexReadOnlyErrorCode.SDK_NOT_INSTALLED,
                    "SDK missing",
                ),
            ),
        )


def test_readiness_failure_happens_before_event_creation(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    event_file = tmp_path / "events.jsonl"
    envelope = asyncio.run(
        CodexReadOnlyService(NotReadyGateway()).run(
            request="Analyze read-only.",
            settings=_settings(),
            workspace=workspace,
            event_file=event_file,
            thread_state_file=None,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.live_call is False
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.SDK_NOT_INSTALLED
    assert not event_file.exists()


def test_missing_codex_events_is_rejected(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    envelope = asyncio.run(
        CodexReadOnlyService(FakeGateway(emit_events=False)).run(
            request="Analyze read-only.",
            settings=_settings(),
            workspace=workspace,
            event_file=tmp_path / "events.jsonl",
            thread_state_file=None,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.CODEX_EVENT_EVIDENCE_MISSING


def test_missing_thread_id_is_rejected(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    envelope = asyncio.run(
        CodexReadOnlyService(FakeGateway(thread_id=None)).run(
            request="Analyze read-only.",
            settings=_settings(),
            workspace=workspace,
            event_file=tmp_path / "events.jsonl",
            thread_state_file=None,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.CODEX_THREAD_ID_MISSING


def test_forbidden_codex_item_events_are_rejected(tmp_path: Path) -> None:
    cases = [
        ("file_change", CodexReadOnlyErrorCode.FILE_CHANGE_EVENT_OBSERVED),
        ("web_search", CodexReadOnlyErrorCode.WEB_SEARCH_EVENT_OBSERVED),
        ("mcp_tool_call", CodexReadOnlyErrorCode.MCP_EVENT_OBSERVED),
    ]
    for index, (item_type, expected_code) in enumerate(cases):
        workspace = _fixture_copy(tmp_path / str(index))
        envelope = asyncio.run(
            CodexReadOnlyService(FakeGateway(extra_item_type=item_type)).run(
                request="Analyze read-only.",
                settings=_settings(),
                workspace=workspace,
                event_file=tmp_path / f"events-{index}.jsonl",
                thread_state_file=None,
                live_opt_in=True,
            trusted_workspace_opt_in=True,
            )
        )
        assert envelope.state == "FAILED"
        assert envelope.error is not None
        assert envelope.error.code == expected_code


def test_controlled_workspace_confirmation_is_required(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    event_file = tmp_path / "events.jsonl"
    envelope = asyncio.run(
        CodexReadOnlyService(FakeGateway()).run(
            request="Analyze read-only.",
            settings=_settings(),
            workspace=workspace,
            event_file=event_file,
            thread_state_file=None,
            live_opt_in=True,
            trusted_workspace_opt_in=False,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.WORKSPACE_TRUST_OPT_IN_REQUIRED
    assert not event_file.exists()


def test_git_repository_is_required_before_readiness(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    shutil.rmtree(workspace / ".git")
    envelope = asyncio.run(
        CodexReadOnlyService(NotReadyGateway()).run(
            request="Analyze read-only.",
            settings=_settings(),
            workspace=workspace,
            event_file=tmp_path / "events.jsonl",
            thread_state_file=None,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.GIT_REPOSITORY_REQUIRED


def test_symbolic_links_are_rejected(tmp_path: Path) -> None:
    workspace = _fixture_copy(tmp_path)
    external = tmp_path / "external.txt"
    external.write_text("outside\n", encoding="utf-8")
    link = workspace / "external-link.txt"
    try:
        link.symlink_to(external)
    except OSError:
        pytest.skip("symbolic links are not available in this environment")
    envelope = asyncio.run(
        CodexReadOnlyService(FakeGateway()).run(
            request="Analyze read-only.",
            settings=_settings(),
            workspace=workspace,
            event_file=tmp_path / "events.jsonl",
            thread_state_file=None,
            live_opt_in=True,
            trusted_workspace_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code == CodexReadOnlyErrorCode.WORKSPACE_SYMLINK_NOT_ALLOWED
