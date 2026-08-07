from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import (
    CodexReadOnlyEnvelope,
    CodexReadOnlyResult,
    TreeSnapshot,
)
from scripts import run_step002_live_acceptance as acceptance


def _argument(args: list[str], name: str) -> Path:
    return Path(args[args.index(name) + 1])


def _write_success_envelope(args: list[str], *, resumed: bool) -> None:
    evidence = _argument(args, "--evidence-file")
    event_file = _argument(args, "--event-file")
    thread_file = _argument(args, "--thread-state-file")
    workspace = _argument(args, "--workspace")
    event_file.write_text('{"type":"item.completed","item":{"type":"command_execution"}}\n', encoding="utf-8")
    thread_file.write_text('{"thread_id":"thread-1"}\n', encoding="utf-8")
    snapshot = TreeSnapshot(
        sha256="a" * 64,
        file_count=2,
        total_bytes=100,
        symlink_count=0,
        ignored_names=[],
    )
    now = datetime.now(timezone.utc)
    envelope = CodexReadOnlyEnvelope(
        run_id="run-2" if resumed else "run-1",
        request_id="request-2" if resumed else "request-1",
        state="SUCCEEDED",
        started_at=now,
        completed_at=now,
        duration_ms=1,
        agent_model="agent-model",
        codex_model="codex-model",
        sdk_version="0.19.0",
        codex_cli_version="codex-test",
        trace_id="trace-1",
        response_id="response-1",
        thread_id="thread-1",
        resumed_thread=resumed,
        workspace=str(workspace.resolve()),
        input_sha256="b" * 64,
        live_call=True,
        before=snapshot,
        after=snapshot,
        mutation_detected=False,
        event_file=str(event_file.resolve()),
        event_count=1,
        event_sha256="c" * 64,
        event_types=["item.completed"],
        item_types=["command_execution"],
        required_files=[],
        verified_inspected_files=["src/inventory/pricing.py"],
        result=CodexReadOnlyResult(
            summary="confirmed",
            inspected_files=["src/inventory/pricing.py"],
        ),
    )
    evidence.write_text(envelope.model_dump_json(indent=2) + "\n", encoding="utf-8")


def test_acceptance_run_uses_unique_directory_and_ignores_stale_root_thread(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(acceptance.LIVE_GATE, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "agent-model")
    monkeypatch.setenv("OKCANVAS_CODEX_MODEL", "codex-model")
    monkeypatch.setattr(acceptance, "_git_init", lambda workspace: None)

    output_root = tmp_path / "evidence"
    output_root.mkdir()
    (output_root / "thread.json").write_text('{"thread_id":"stale"}\n', encoding="utf-8")
    calls = 0

    def fake_runner(args: list[str]) -> int:
        nonlocal calls
        calls += 1
        _write_success_envelope(args, resumed=calls == 2)
        return 0

    result = acceptance.run(
        ["--output-root", str(output_root), "--acceptance-id", "acceptance-001"],
        command_runner=fake_runner,
    )

    assert result == 0
    assert calls == 2
    run_dir = output_root / "acceptance-001"
    summary = json.loads((run_dir / "acceptance-summary.json").read_text(encoding="utf-8"))
    assert summary["state"] == "PASSED"
    assert summary["checks"]["thread_preserved"] is True
    assert summary["checks"]["second_resumed"] is True
    assert (output_root / "thread.json").read_text(encoding="utf-8").find("stale") >= 0
    assert (run_dir / "thread.json").is_file()


def test_acceptance_refuses_to_overwrite_existing_run_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(acceptance.LIVE_GATE, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "agent-model")
    monkeypatch.setenv("OKCANVAS_CODEX_MODEL", "codex-model")
    existing = tmp_path / "acceptance-001"
    existing.mkdir()

    assert (
        acceptance.run(
            ["--output-root", str(tmp_path), "--acceptance-id", "acceptance-001"],
            command_runner=lambda args: 0,
        )
        == 2
    )


def test_acceptance_requires_all_live_environment_values(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(acceptance.LIVE_GATE, "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "agent-model")
    monkeypatch.setenv("OKCANVAS_CODEX_MODEL", "codex-model")

    assert acceptance.run(["--output-root", str(tmp_path)]) == 2
    assert list(tmp_path.iterdir()) == []
