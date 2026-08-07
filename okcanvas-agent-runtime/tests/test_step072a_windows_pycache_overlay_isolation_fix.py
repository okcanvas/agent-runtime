from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.python_bytecode_isolation import (
    ENV_NAME,
    SCHEMA_VERSION,
    build_isolated_environment,
)

ROOT = Path(__file__).resolve().parents[1]


def _run_import(source_root: Path, *, environment: dict[str, str]) -> str:
    completed = subprocess.run(
        [sys.executable, "-c", "import overlay_probe; print(overlay_probe.VALUE)"],
        cwd=source_root,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def test_current_baseline_and_windows_gate_are_exact() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.openai_trace_export_windows_live_accepted is True
    assert info.windows_pycache_overlay_isolation_implemented is True
    assert info.windows_pycache_overlay_isolation_mode == "per-process-temporary-pycache-prefix"
    assert info.windows_pycache_overlay_isolation_deterministic_accepted is True
    assert info.windows_pycache_overlay_isolation_windows_accepted is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


def test_step072_windows_results_are_recorded_exactly() -> None:
    evidence = json.loads(
        (ROOT / "docs/evidence/STEP072_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["schema_version"] == "okcanvas-step072-windows-acceptance-summary-v1"
    assert evidence["deterministic"]["state"] == "FAILED"
    assert evidence["deterministic"]["passed_checks"] == 28
    assert evidence["deterministic"]["total_checks"] == 29
    assert evidence["deterministic"]["failed_checks"] == [
        "historical_skill_attachment_service_tests_pass"
    ]
    assert evidence["live"]["state"] == "PASSED"
    assert evidence["live"]["passed_checks"] == 13
    assert evidence["live"]["total_checks"] == 13
    assert evidence["live"]["model"] == "gpt-4.1"
    assert evidence["live"]["model_calls"] == 1
    assert evidence["live"]["usage"] == {
        "input_tokens": 827,
        "output_tokens": 228,
        "total_tokens": 1055,
    }
    assert evidence["live"]["terminal_status"] == "SUCCEEDED"
    assert evidence["live"]["trace_error_markers"] == []
    assert evidence["live"]["sdk_trace_export_observed"] is False


def test_python_timestamp_size_collision_is_reproduced_and_isolated(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    module = source_root / "overlay_probe.py"
    old_source = 'VALUE = "STEP071"\n'
    new_source = 'VALUE = "STEP072"\n'
    assert len(old_source.encode("utf-8")) == len(new_source.encode("utf-8"))
    fixed_timestamp = 1_700_000_000

    module.write_bytes(old_source.encode("utf-8"))
    os.utime(module, (fixed_timestamp, fixed_timestamp))
    unisolated = os.environ.copy()
    unisolated.pop(ENV_NAME, None)
    unisolated.pop("PYTHONDONTWRITEBYTECODE", None)
    unisolated["PYTHONPATH"] = str(source_root)
    assert _run_import(source_root, environment=unisolated) == "STEP071"
    assert list((source_root / "__pycache__").glob("overlay_probe.*.pyc"))

    module.write_bytes(new_source.encode("utf-8"))
    os.utime(module, (fixed_timestamp, fixed_timestamp))
    assert module.stat().st_size == len(new_source.encode("utf-8"))
    assert _run_import(source_root, environment=unisolated) == "STEP071"

    isolated, prefix, owns_prefix = build_isolated_environment(
        unisolated, temp_root=tmp_path / "isolated"
    )
    assert owns_prefix is True
    isolated["PYTHONPATH"] = str(source_root)
    assert prefix.is_absolute()
    assert source_root not in prefix.parents
    assert _run_import(source_root, environment=isolated) == "STEP072"


def test_existing_isolated_prefix_is_reused_without_ownership(tmp_path: Path) -> None:
    prefix = tmp_path / "existing-prefix"
    environment, resolved, owns_prefix = build_isolated_environment(
        {ENV_NAME: str(prefix)}, temp_root=tmp_path / "ignored"
    )
    assert environment[ENV_NAME] == str(prefix)
    assert resolved == prefix
    assert owns_prefix is False


def test_windows_launchers_start_through_bytecode_isolation_wrapper() -> None:
    expected = {
        "sh_run_api.cmd": "scripts\\python_bytecode_isolation.py scripts\\windows_entrypoint.py control-api",
        "sh_run_step072_acceptance.cmd": "scripts\\python_bytecode_isolation.py scripts\\run_step072_acceptance.py",
        "sh_run_step072_live_acceptance.cmd": "scripts\\python_bytecode_isolation.py scripts\\windows_entrypoint.py trace-export-disabled-live-acceptance",
        "sh_run_step072a_acceptance.cmd": "scripts\\python_bytecode_isolation.py scripts\\run_step072a_acceptance.py",
        "sh_run_step072a_live_acceptance.cmd": "scripts\\python_bytecode_isolation.py scripts\\windows_entrypoint.py windows-pycache-overlay-live-acceptance",
    }
    for relative, fragment in expected.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert fragment in source
        assert ".venv\\Scripts\\python.exe" in source


def test_packaging_excludes_adjacent_and_isolated_bytecode() -> None:
    packaging_policy = (ROOT / "scripts/step081_product_inventory.py").read_text(encoding="utf-8")
    assert '"__pycache__"' in packaging_policy
    assert 'EXCLUDED_SUFFIXES = {".pyc", ".pyo"}' in packaging_policy
    assert '".runtime-pycache"' not in packaging_policy
    assert SCHEMA_VERSION == "okcanvas-python-bytecode-isolation-v1"
