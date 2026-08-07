import asyncio
import json
from pathlib import Path

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexUsageSummary
from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteResult
from okcanvas_agent_runtime.core.config import CodexWriteSettings
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.adapters.evidence import write_run_evidence
from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import CodexReadiness
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_gateway import CodexWriteGatewayRunResult
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_service import CodexWriteService
from scripts import run_step003_live_acceptance


class AcceptanceGateway:
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

    async def run(self, *, request, run_id, settings, workspace, journal):
        target = workspace / "src" / "inventory" / "pricing.py"
        target.write_text(
            'from __future__ import annotations\n\n\ndef calculate_total(lines: list[dict[str, int]]) -> int:\n    """Return an order total in Korean won."""\n    return sum(line["unit_price"] * line["quantity"] for line in lines)\n',
            encoding="utf-8",
        )
        journal.append(
            event_type="thread.started",
            payload={"type": "thread.started", "thread_id": "thread-acceptance"},
            thread_id="thread-acceptance",
        )
        journal.append(
            event_type="item.completed",
            payload={"type": "item.completed", "item": {"type": "file_change"}},
            thread_id="thread-acceptance",
        )
        return CodexWriteGatewayRunResult(
            output=CodexWriteResult(
                summary="Fixed quantity multiplication.",
                inspected_files=["src/inventory/pricing.py", "tests/test_pricing.py"],
                modified_files=["src/inventory/pricing.py"],
                commands_observed=["rg quantity"],
                unverified=["Independent validation pending"],
            ),
            agent_usage=UsageSummary(requests=2, input_tokens=100, output_tokens=20, total_tokens=120),
            codex_usage=CodexUsageSummary(input_tokens=80, output_tokens=10),
            trace_id="trace-acceptance",
            response_id="resp-acceptance",
            thread_id="thread-acceptance",
            sdk_version="0.19.0",
            codex_cli_version="codex-cli 0.145.0",
        )


def _value(args: list[str], name: str) -> str:
    return args[args.index(name) + 1]


def test_step003_acceptance_harness_proves_failure_patch_and_pass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OKCANVAS_STEP003_LIVE_ACCEPTANCE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "agent")
    monkeypatch.setenv("OKCANVAS_CODEX_MODEL", "codex")

    def fake_command_runner(args: list[str]) -> int:
        service = CodexWriteService(AcceptanceGateway())
        envelope = asyncio.run(
            service.run(
                request=_value(args, "--input"),
                settings=CodexWriteSettings(agent_model="agent", codex_model="codex", api_key="key"),
                workspace=Path(_value(args, "--workspace")),
                event_file=Path(_value(args, "--event-file")),
                patch_file=Path(_value(args, "--patch-file")),
                live_opt_in=True,
                trusted_workspace_opt_in=True,
                disposable_workspace_opt_in=True,
                workspace_write_opt_in=True,
                allowed_files=("src/inventory/pricing.py",),
                expected_files=("src/inventory/pricing.py",),
                artifact_paths=(Path(_value(args, "--evidence-file")),),
            )
        )
        write_run_evidence(Path(_value(args, "--evidence-file")), envelope)
        return 0 if envelope.state == "SUCCEEDED" else 4

    output_root = tmp_path / "evidence"
    exit_code = run_step003_live_acceptance.run(
        ["--output-root", str(output_root), "--acceptance-id", "test-run"],
        command_runner=fake_command_runner,
    )
    assert exit_code == 0
    run_dir = output_root / "test-run"
    summary = json.loads((run_dir / "acceptance-summary.json").read_text(encoding="utf-8"))
    assert summary["state"] == "PASSED"
    assert all(summary["checks"].values())
    assert summary["baseline_validation"]["failed"] == 1
    assert summary["post_validation"]["passed"] == 1
    assert (run_dir / "change.patch").is_file()


def test_cleanup_workspace_retries_transient_windows_failure(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    target.mkdir()
    (target / "locked.pyc").write_bytes(b"x")
    calls = {"count": 0}
    real_rmtree = run_step003_live_acceptance.shutil.rmtree

    def flaky_rmtree(path, onerror=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise PermissionError(5, "access denied", str(path / "locked.pyc"))
        return real_rmtree(path, onerror=onerror)

    monkeypatch.setattr(run_step003_live_acceptance.shutil, "rmtree", flaky_rmtree)
    result = run_step003_live_acceptance._cleanup_workspace(
        target,
        attempts=3,
        initial_delay_seconds=0,
        sleeper=lambda _: None,
    )
    assert result["state"] == "COMPLETED"
    assert result["attempts"] == 2
    assert result["error"] is None
    assert not target.exists()


def test_cleanup_warning_does_not_reverse_core_acceptance(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OKCANVAS_STEP003_LIVE_ACCEPTANCE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "agent")
    monkeypatch.setenv("OKCANVAS_CODEX_MODEL", "codex")

    def fake_command_runner(args: list[str]) -> int:
        service = CodexWriteService(AcceptanceGateway())
        envelope = asyncio.run(
            service.run(
                request=_value(args, "--input"),
                settings=CodexWriteSettings(agent_model="agent", codex_model="codex", api_key="key"),
                workspace=Path(_value(args, "--workspace")),
                event_file=Path(_value(args, "--event-file")),
                patch_file=Path(_value(args, "--patch-file")),
                live_opt_in=True,
                trusted_workspace_opt_in=True,
                disposable_workspace_opt_in=True,
                workspace_write_opt_in=True,
                allowed_files=("src/inventory/pricing.py",),
                expected_files=("src/inventory/pricing.py",),
                artifact_paths=(Path(_value(args, "--evidence-file")),),
            )
        )
        write_run_evidence(Path(_value(args, "--evidence-file")), envelope)
        return 0 if envelope.state == "SUCCEEDED" else 4

    def cleanup_warning(path: Path) -> dict[str, object]:
        return {
            "state": "WARNING",
            "path": str(path),
            "attempts": 8,
            "duration_ms": 1000,
            "error": {"type": "PermissionError", "message": "access denied"},
        }

    output_root = tmp_path / "evidence"
    exit_code = run_step003_live_acceptance.run(
        ["--output-root", str(output_root), "--acceptance-id", "cleanup-warning"],
        command_runner=fake_command_runner,
        cleanup_runner=cleanup_warning,
    )
    assert exit_code == 0
    summary = json.loads(
        (output_root / "cleanup-warning" / "acceptance-summary.json").read_text(encoding="utf-8")
    )
    assert summary["core_acceptance_passed"] is True
    assert summary["state"] == "PASSED_WITH_CLEANUP_WARNING"
    assert summary["error"] is None
    assert summary["cleanup"]["state"] == "WARNING"
    assert all(summary["checks"].values())
