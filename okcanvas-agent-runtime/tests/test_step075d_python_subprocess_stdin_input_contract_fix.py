from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.adapters.sandbox.docker import SandboxDockerError, SubprocessDockerCommandRunner

ROOT = Path(__file__).resolve().parents[1]


def test_real_subprocess_stdin_round_trip_uses_input_contract_only() -> None:
    runner = SubprocessDockerCommandRunner(max_output_bytes=1024, executable=sys.executable)
    payload = b"deterministic-tar-stream"
    result = runner.run_with_input(
        (
            "-c",
            "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())",
        ),
        input_bytes=payload,
        timeout_seconds=10,
    )
    assert result.returncode == 0
    assert result.stdout == payload.decode("utf-8")
    assert result.stderr == ""
    assert result.output_truncated is False


def test_input_path_never_passes_stdin_and_input_together(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        assert "input" in kwargs
        assert "stdin" not in kwargs
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = SubprocessDockerCommandRunner(max_output_bytes=1024, executable="docker").run_with_input(
        (
            "container", "exec", "--interactive", "--user", "0:0", "c" * 64,
            "tar", "-x", "-f", "-", "-C", "/workspace",
        ),
        input_bytes=b"archive",
        timeout_seconds=30,
    )
    assert result.returncode == 0
    assert captured["input"] == b"archive"
    assert captured["shell"] is False


def test_no_input_path_uses_devnull_without_input(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = SubprocessDockerCommandRunner(max_output_bytes=1024, executable="docker").run(
        ("version", "--format", "{{.Server.Version}}"),
        timeout_seconds=10,
    )
    assert result.returncode == 0
    assert captured["stdin"] is subprocess.DEVNULL
    assert "input" not in captured


def test_runner_configuration_value_error_is_bounded(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        raise ValueError("sensitive runner detail")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SubprocessDockerCommandRunner(max_output_bytes=1024, executable="docker")
    with pytest.raises(SandboxDockerError) as caught:
        runner.run_with_input(
            (
                "container", "exec", "--interactive", "--user", "0:0", "c" * 64,
                "tar", "-x", "-f", "-", "-C", "/workspace",
            ),
            input_bytes=b"archive",
            timeout_seconds=30,
        )
    assert caught.value.code == "DOCKER_RUNNER_CONFIGURATION_INVALID"
    assert caught.value.operation == "container.extract_snapshot"
    assert caught.value.stderr_category == "INVALID_ARGUMENT"
    assert "sensitive runner detail" not in str(caught.value)


def test_product_source_uses_mutually_exclusive_stdin_contract() -> None:
    source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sandbox_runtime/docker_cli.py")).read_text(
        encoding="utf-8"
    )
    assert 'run_kwargs["input"] = input_bytes' in source
    assert 'run_kwargs["stdin"] = subprocess.DEVNULL' in source
    assert "stdin=subprocess.PIPE if input_bytes is not None" not in source
    assert "except ValueError as exc" in source
    assert "DOCKER_RUNNER_CONFIGURATION_INVALID" in source
