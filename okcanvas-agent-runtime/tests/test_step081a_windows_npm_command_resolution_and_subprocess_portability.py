from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.node_acceptance import resolve_subprocess_command, run_command
from scripts.step081_product_inventory import EXCLUDED_PREFIXES
from scripts.validate_windows_subprocess_portability import validate

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clients/cli"


def _windows_which(name: str) -> str | None:
    values = {
        "npm.cmd": r"C:\Program Files\nodejs\npm.cmd",
        "tsc.cmd": r"C:\Users\tester\AppData\Roaming\npm\tsc.cmd",
        "node.exe": r"C:\Program Files\nodejs\node.exe",
        "cmd.exe": r"C:\Windows\System32\cmd.exe",
    }
    return values.get(name.lower())


def test_bare_npm_resolves_to_cmd_call_on_windows() -> None:
    command = resolve_subprocess_command(
        ["npm", "pack", "--dry-run", "--json"],
        platform_name="nt",
        comspec=r"C:\Windows\System32\cmd.exe",
        which=_windows_which,
    )
    assert command == [
        r"C:\Windows\System32\cmd.exe",
        "/d",
        "/c",
        "call",
        r"C:\Program Files\nodejs\npm.cmd",
        "pack",
        "--dry-run",
        "--json",
    ]


def test_explicit_tsc_cmd_resolves_to_cmd_call_on_windows() -> None:
    command = resolve_subprocess_command(
        [r"C:\Users\tester\AppData\Roaming\npm\tsc.cmd", "--version"],
        platform_name="nt",
        comspec=r"C:\Windows\System32\cmd.exe",
        which=_windows_which,
    )
    assert command[:5] == [
        r"C:\Windows\System32\cmd.exe",
        "/d",
        "/c",
        "call",
        r"C:\Users\tester\AppData\Roaming\npm\tsc.cmd",
    ]
    assert command[5:] == ["--version"]


def test_native_node_executable_remains_direct() -> None:
    command = resolve_subprocess_command(
        ["node.exe", "--version"],
        platform_name="nt",
        which=_windows_which,
    )
    assert command == [r"C:\Program Files\nodejs\node.exe", "--version"]


def test_missing_executable_is_reported_not_raised(tmp_path: Path) -> None:
    ok, output = run_command(["definitely-not-an-okcanvas-executable"], tmp_path)
    assert ok is False
    assert "FileNotFoundError" in output


def test_repository_wide_windows_subprocess_portability_gate_passes() -> None:
    payload = validate(ROOT)
    assert payload["state"] == "PASSED", payload
    assert payload["passed_checks"] == payload["total_checks"] == 7
    assert payload["violations"] == []
    assert ("docs", "evidence", "step081a-live") in EXCLUDED_PREFIXES
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "docs/evidence/step081a-live/" in gitignore


def test_runtime_info_exposes_corrective_revision_contract() -> None:
    info = RuntimeInfo()
    assert info.windows_batch_subprocess_resolution_fix_implemented is True
    assert info.windows_batch_subprocess_resolution_mode == "resolve-executable-and-cmd-call-v1"
    assert info.windows_batch_subprocess_oserror_bounded is True
    assert info.windows_batch_subprocess_repository_audit_implemented is True
    assert info.windows_npm_pack_acceptance_portability_deterministic_accepted is True
    assert info.windows_npm_pack_acceptance_portability_windows_live_accepted is True
