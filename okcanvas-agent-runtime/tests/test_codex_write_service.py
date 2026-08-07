import asyncio
import subprocess
from pathlib import Path

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexUsageSummary
from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteErrorCode, CodexWriteResult
from okcanvas_agent_runtime.core.config import CodexWriteSettings
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import CodexReadiness
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_gateway import CodexWriteGatewayRunResult
from okcanvas_agent_runtime.adapters.openai.runtime.codex_write_service import CodexWriteService


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=path, check=True)


class FakeWriteGateway:
    def __init__(self, modified_files: tuple[str, ...]):
        self.modified_files = modified_files

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
        for relative in self.modified_files:
            target = workspace / relative
            if relative.endswith("pricing.py"):
                target.write_text(
                    'from __future__ import annotations\n\n\ndef calculate_total(lines: list[dict[str, int]]) -> int:\n    """Return an order total in Korean won."""\n    return sum(line["unit_price"] * line["quantity"] for line in lines)\n',
                    encoding="utf-8",
                )
            else:
                target.write_text(target.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
        journal.append(event_type="thread.started", payload={"type": "thread.started", "thread_id": "thread-write"}, thread_id="thread-write")
        journal.append(event_type="item.completed", payload={"type": "item.completed", "item": {"type": "file_change"}}, thread_id="thread-write")
        return CodexWriteGatewayRunResult(
            output=CodexWriteResult(
                summary="Applied the quantity fix.",
                inspected_files=["src/inventory/pricing.py", "tests/test_pricing.py"],
                modified_files=list(self.modified_files),
                commands_observed=["rg quantity"],
                unverified=["Independent validation pending"],
            ),
            agent_usage=UsageSummary(requests=2, input_tokens=100, output_tokens=20, total_tokens=120),
            codex_usage=CodexUsageSummary(input_tokens=80, output_tokens=10),
            trace_id="trace-write",
            response_id="resp-write",
            thread_id="thread-write",
            sdk_version="0.19.0",
            codex_cli_version="codex-cli 0.145.0",
        )


def _workspace(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    source = root / "fixtures" / "codex_write_repo"
    import shutil
    workspace = tmp_path / "repo"
    shutil.copytree(source, workspace)
    _init_repo(workspace)
    return workspace


def _settings() -> CodexWriteSettings:
    return CodexWriteSettings(agent_model="agent", codex_model="codex", api_key="key")


def test_codex_write_accepts_exact_minimal_patch(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    service = CodexWriteService(FakeWriteGateway(("src/inventory/pricing.py",)))
    envelope = asyncio.run(service.run(
        request="Fix quantity",
        settings=_settings(),
        workspace=workspace,
        event_file=tmp_path / "events.jsonl",
        patch_file=tmp_path / "change.patch",
        live_opt_in=True,
        trusted_workspace_opt_in=True,
        disposable_workspace_opt_in=True,
        workspace_write_opt_in=True,
        allowed_files=("src/inventory/pricing.py",),
        expected_files=("src/inventory/pricing.py",),
    ))
    assert envelope.state == "SUCCEEDED"
    assert envelope.verified_modified_files == ["src/inventory/pricing.py"]
    assert envelope.baseline_commit == envelope.final_commit
    assert envelope.patch_sha256
    assert (tmp_path / "change.patch").is_file()


def test_codex_write_rejects_change_outside_allowlist(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    service = CodexWriteService(FakeWriteGateway(("src/inventory/pricing.py", "tests/test_pricing.py")))
    envelope = asyncio.run(service.run(
        request="Fix quantity",
        settings=_settings(),
        workspace=workspace,
        event_file=tmp_path / "events.jsonl",
        patch_file=tmp_path / "change.patch",
        live_opt_in=True,
        trusted_workspace_opt_in=True,
        disposable_workspace_opt_in=True,
        workspace_write_opt_in=True,
        allowed_files=("src/inventory/pricing.py",),
        expected_files=("src/inventory/pricing.py",),
    ))
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code is CodexWriteErrorCode.MODIFIED_FILE_OUTSIDE_ALLOWLIST
    assert not (tmp_path / "change.patch").exists()


def test_codex_write_requires_all_explicit_opt_ins(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    service = CodexWriteService(FakeWriteGateway(("src/inventory/pricing.py",)))
    envelope = asyncio.run(service.run(
        request="Fix quantity",
        settings=_settings(),
        workspace=workspace,
        event_file=tmp_path / "events.jsonl",
        patch_file=tmp_path / "change.patch",
        live_opt_in=True,
        trusted_workspace_opt_in=True,
        disposable_workspace_opt_in=False,
        workspace_write_opt_in=True,
        allowed_files=("src/inventory/pricing.py",),
    ))
    assert envelope.error is not None
    assert envelope.error.code is CodexWriteErrorCode.DISPOSABLE_WORKSPACE_OPT_IN_REQUIRED


class StagingWriteGateway(FakeWriteGateway):
    async def run(self, **kwargs):
        result = await super().run(**kwargs)
        subprocess.run(["git", "add", "src/inventory/pricing.py"], cwd=kwargs["workspace"], check=True)
        return result


def test_codex_write_rejects_staged_changes(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    service = CodexWriteService(StagingWriteGateway(("src/inventory/pricing.py",)))
    envelope = asyncio.run(service.run(
        request="Fix quantity",
        settings=_settings(),
        workspace=workspace,
        event_file=tmp_path / "events.jsonl",
        patch_file=tmp_path / "change.patch",
        live_opt_in=True,
        trusted_workspace_opt_in=True,
        disposable_workspace_opt_in=True,
        workspace_write_opt_in=True,
        allowed_files=("src/inventory/pricing.py",),
        expected_files=("src/inventory/pricing.py",),
    ))
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code is CodexWriteErrorCode.STAGED_CHANGE_NOT_ALLOWED
