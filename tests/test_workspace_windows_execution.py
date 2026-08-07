from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.package_workspace import excluded as package_excluded
from scripts.workspace_inventory import excluded_package_path, excluded_parent_project_path, excluded_workspace_path, is_local_acceptance_output
from scripts.workspace_process import decode_process_output, prepare_invocation, render_json_for_console, workspace_root_errors, write_json_stdout


class Cp949MemoryStream:
    encoding = "cp949"

    def __init__(self) -> None:
        self.parts: list[str] = []

    def write(self, text: str) -> int:
        text.encode(self.encoding)
        self.parts.append(text)
        return len(text)

    def flush(self) -> None:
        return None

    def value(self) -> str:
        return "".join(self.parts)


class WorkspaceWindowsExecutionTest(unittest.TestCase):
    def test_windows_cmd_tools_use_shell_invocation(self) -> None:
        invocation, use_shell = prepare_invocation(
            r"C:\Program Files\nodejs\npm.cmd", ["run", "acceptance"], platform_name="nt"
        )
        self.assertTrue(use_shell)
        self.assertIsInstance(invocation, str)
        self.assertIn("npm.cmd", invocation)
        self.assertIn("acceptance", invocation)

    def test_native_executables_do_not_use_shell(self) -> None:
        invocation, use_shell = prepare_invocation(
            r"C:\Program Files\nodejs\node.exe", ["script.js"], platform_name="nt"
        )
        self.assertFalse(use_shell)
        self.assertEqual(invocation[-1], "script.js")

    def test_utf8_output_decodes_before_cp949_preference(self) -> None:
        text, encoding = decode_process_output(
            "상태 → PASS".encode("utf-8"), preferred_encoding="cp949"
        )
        self.assertEqual(text, "상태 → PASS")
        self.assertEqual(encoding, "utf-8")

    def test_cp949_output_falls_back_to_windows_preference(self) -> None:
        text, encoding = decode_process_output(
            "상태 통과".encode("cp949"), preferred_encoding="cp949"
        )
        self.assertEqual(text, "상태 통과")
        self.assertEqual(encoding.lower().replace("-", ""), "cp949")

    def test_undecodable_output_never_raises(self) -> None:
        text, encoding = decode_process_output(b"\xff\xfe\xfa", preferred_encoding="ascii")
        self.assertTrue(text)
        self.assertEqual(encoding, "utf-8-replace")

    def test_cp949_parent_json_output_falls_back_to_valid_ascii_json(self) -> None:
        payload = {"korean": "상태", "symbol": "✔", "arrow": "→", "emoji": "🧪"}
        text, encoding, escaped = render_json_for_console(payload, encoding="cp949")
        self.assertTrue(escaped)
        self.assertEqual(encoding, "ascii-json-escape")
        self.assertEqual(json.loads(text), payload)
        self.assertEqual(text.encode("cp949").decode("cp949"), text)

    def test_cp949_parent_json_writer_never_raises_and_round_trips(self) -> None:
        payload = {"state": "PASSED", "child_output": "✔ 상태 → 🧪"}
        stream = Cp949MemoryStream()
        encoding, escaped = write_json_stdout(payload, stream=stream)
        self.assertEqual(encoding, "ascii-json-escape")
        self.assertTrue(escaped)
        self.assertEqual(json.loads(stream.value()), payload)

    def test_shared_runner_captures_bytes_not_locale_text(self) -> None:
        source = (ROOT / "scripts/workspace_process.py").read_text(encoding="utf-8")
        self.assertIn("text=False", source)
        self.assertNotIn("text=True", source)

    def test_current_workspace_root_contract_is_exact(self) -> None:
        self.assertEqual(workspace_root_errors(ROOT), [])

    def test_product_root_is_rejected_as_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            fake = Path(temp_name) / "okcanvas-agent-runtime"
            fake.mkdir()
            (fake / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            errors = workspace_root_errors(fake)
        self.assertTrue(errors)
        self.assertTrue(any("management workspace root" in error for error in errors))

    def test_mutable_acceptance_evidence_is_excluded_from_workspace_package(self) -> None:
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP001_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP001R1_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP001R2_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP001R3_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP002_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP002R1_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP003_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP003R1_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP003R2_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP003_MAIN_ASSISTANT_GROUPWARE_E2E.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP005_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP005R1_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP006_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP007_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP007_LIVE_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP007R1_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP007R1_LIVE_ACCEPTANCE.json")))
        self.assertTrue(package_excluded(Path("docs/evidence/WORKSPACE_STEP008_ACCEPTANCE.json")))
        self.assertFalse(package_excluded(Path("docs/evidence/WORKSPACE_STEP003_LOCAL_DETERMINISTIC_ACCEPTANCE_SUMMARY.json")))
        self.assertFalse(package_excluded(Path("docs/evidence/WORKSPACE_STEP003R1_LOCAL_DETERMINISTIC_ACCEPTANCE_SUMMARY.json")))
        self.assertFalse(package_excluded(Path("docs/evidence/WORKSPACE_STEP003_MAIN_ASSISTANT_GROUPWARE_E2E_SUMMARY.json")))
        self.assertFalse(package_excluded(Path("docs/evidence/STEP086R2_WINDOWS_ACCEPTANCE_SUMMARY.json")))

    def test_workspace_manifest_is_packaged_but_not_self_hashed(self) -> None:
        manifest = Path("WORKSPACE_MANIFEST.json")
        self.assertTrue(excluded_workspace_path(manifest))
        self.assertFalse(excluded_package_path(manifest))
        self.assertFalse(package_excluded(manifest))

    def test_local_environment_files_are_excluded_from_identity_and_package(self) -> None:
        for name in (".env", ".env.local", ".env.local.cmd"):
            self.assertTrue(excluded_parent_project_path(Path(name)), name)
            self.assertTrue(excluded_workspace_path(Path(f"okcanvas-agent-runtime/{name}")), name)
            self.assertTrue(package_excluded(Path(f"okcanvas-agent-runtime/{name}")), name)
        self.assertFalse(excluded_parent_project_path(Path(".env.local.example")))
        self.assertFalse(excluded_workspace_path(Path("okcanvas-agent-runtime/.env.local.example")))

    def test_workspace_scripts_import_from_workspace_root(self) -> None:
        import scripts.package_workspace as package_workspace
        import scripts.workspace_process as workspace_process
        self.assertTrue(Path(package_workspace.__file__).resolve().is_relative_to(ROOT))
        self.assertTrue(Path(workspace_process.__file__).resolve().is_relative_to(ROOT))
        acceptance = (ROOT / "scripts/run_workspace_step003r2_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('"discover", "-s", "tests", "-t", ".", "-v"', acceptance)

    def test_step003r1_runner_uses_retained_runtime_evidence_without_nested_full_runtime_acceptance(self) -> None:
        source = (ROOT / "scripts/run_workspace_step003r1_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("STEP087_DETERMINISTIC_ACCEPTANCE.json", source)
        self.assertNotIn("run_step087_acceptance.py", source)

    def test_step003_compatibility_launchers_delegate_to_step003r2(self) -> None:
        for name in ("sh_run_workspace_step003_acceptance.cmd", "sh_run_workspace_step003r1_acceptance.cmd"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("call sh_run_workspace_step003r2_acceptance.cmd %*", source)

    def test_step003r2_runner_uses_project_owned_python_interpreters(self) -> None:
        source = (ROOT / "scripts/run_workspace_step003r2_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("resolve_project_python", source)
        self.assertIn("connector_python, [\"scripts/run_acceptance.py\"]", source)
        self.assertIn("connector_python,", source)
        self.assertIn("runtime_python,", source)
        self.assertNotIn("run_process(sys.executable, [\"scripts/run_acceptance.py\"]", source)

    def test_root_redirected_acceptance_logs_are_local_outputs(self) -> None:
        for name in ("log.txt", "workspace-step003r2.log"):
            path = Path(name)
            self.assertTrue(is_local_acceptance_output(path), name)
            self.assertTrue(excluded_workspace_path(path), name)
            self.assertTrue(excluded_package_path(path), name)
        self.assertFalse(is_local_acceptance_output(Path("docs/architecture.log")))
        self.assertFalse(excluded_workspace_path(Path("HANDOFF.md")))


    def test_retained_json_emitters_use_cp949_safe_shared_writer(self) -> None:
        relative_paths = (
            "scripts/run_workspace_step001r2_acceptance.py",
            "scripts/run_workspace_step001r3_acceptance.py",
            "scripts/run_workspace_step002r1_acceptance.py",
            "scripts/run_workspace_step003_acceptance.py",
            "scripts/run_workspace_step003r1_acceptance.py",
            "scripts/run_workspace_step003r2_acceptance.py",
            "scripts/run_workspace_step004_acceptance.py",
            "scripts/run_workspace_step004r1_acceptance.py",
            "scripts/run_workspace_step004r1_live_acceptance.py",
            "scripts/run_workspace_step005_acceptance.py",
            "tests/run_groupware_connector_example_e2e.py",
            "tests/run_main_assistant_groupware_subagent_e2e.py",
        )
        for relative in relative_paths:
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("write_json_stdout", source, relative)
            self.assertNotIn("print(json.dumps(payload, ensure_ascii=False", source, relative)

    def test_launchers_have_workspace_root_guard(self) -> None:
        for name in (
            "sh_setup_workspace.cmd",
            "sh_run_workspace_step001_acceptance.cmd",
            "sh_run_workspace_step001r1_acceptance.cmd",
            "sh_run_workspace_step001r2_acceptance.cmd",
            "sh_run_workspace_step001r3_acceptance.cmd",
            "sh_run_workspace_step002_acceptance.cmd",
            "sh_run_workspace_step002r1_acceptance.cmd",
            "sh_run_workspace_step003_acceptance.cmd",
            "sh_run_workspace_step003r1_acceptance.cmd",
            "sh_run_workspace_step003r2_acceptance.cmd",
            "sh_run_workspace_step004_acceptance.cmd",
            "sh_run_workspace_step004_live_acceptance.cmd",
            "sh_run_workspace_step004r1_acceptance.cmd",
            "sh_run_workspace_step004r1_live_acceptance.cmd",
            "sh_run_workspace_step005_acceptance.cmd",
            "sh_run_workspace_step007r1_acceptance.cmd",
            "sh_run_workspace_step007r1_live_acceptance.cmd",
            "sh_run_all_subproject_acceptance.cmd",
        ):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("okcanvas-agent-cli\\package.json", source, name)
            self.assertIn("Workspace root is invalid", source, name)


if __name__ == "__main__":
    unittest.main()
