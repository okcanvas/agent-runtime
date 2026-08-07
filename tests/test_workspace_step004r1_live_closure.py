from __future__ import annotations

import asyncio
import os
import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_workspace_step004r1_live_acceptance as live
from scripts.workspace_python_bytecode_isolation import build_isolated_environment

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceStep004R1LiveClosureTests(unittest.TestCase):
    def test_builtin_permission_error_is_harness_failure_not_openai_auth(self) -> None:
        self.assertEqual(live.safe_failure_category(PermissionError("locked")), "HARNESS_FILESYSTEM_PERMISSION")

    def test_temp_cleanup_retries_transient_windows_lock(self) -> None:
        with tempfile.TemporaryDirectory() as parent:
            target = Path(parent) / "target"
            target.mkdir()
            (target / "value.txt").write_text("x", encoding="utf-8")
            real_rmtree = live.shutil.rmtree
            calls = 0

            def flaky(path: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise PermissionError("transient lock")
                real_rmtree(path)

            with patch.object(live.shutil, "rmtree", side_effect=flaky):
                removed, errors = live.remove_temp_tree(target)
            self.assertTrue(removed)
            self.assertEqual(errors, ["PermissionError"])
            self.assertFalse(target.exists())

    def test_execution_permission_error_is_preserved_after_successful_cleanup(self) -> None:
        environment = {
            live.LIVE_GATE: "1",
            live.ENV_SOURCE_NAME: ".env.local",
            live.ENV_LOADED_KEYS: "OPENAI_API_KEY,OKCANVAS_AGENT_MODEL",
            "OPENAI_API_KEY": "test-secret-not-persisted",
            "OKCANVAS_AGENT_MODEL": "gpt-4.1",
        }
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "evidence.json"
            with patch.dict(os.environ, environment, clear=False), \
                 patch.object(live, "resolve_executable", return_value=sys.executable), \
                 patch.object(live, "run_command", side_effect=PermissionError("locked")):
                payload = asyncio.run(live.execute(ROOT / "okcanvas-connector-examples/groupware/groupware-api-fake", output))
        self.assertEqual(payload["state"], "FAILED")
        self.assertEqual(payload["safe_error"]["category"], "HARNESS_FILESYSTEM_PERMISSION")
        self.assertEqual(payload["failure_stage"], "prepare_node_example")
        self.assertTrue(payload["harness_cleanup"]["completed"])
        self.assertTrue(payload["checks"]["harness_cleanup_completed"])
        self.assertNotIn("test-secret-not-persisted", str(payload))

    def test_live_source_stops_processes_before_temp_removal(self) -> None:
        source = (ROOT / "scripts/run_workspace_step004r1_live_acceptance.py").read_text(encoding="utf-8")
        self.assertLess(source.index("server.stop()"), source.index("remove_temp_tree(temp)"))
        self.assertLess(source.index("fake_process.terminate()"), source.index("remove_temp_tree(temp)"))
        self.assertIn('"failure_stage": execution_stage', source)
        self.assertIn('"harness_cleanup_completed"', source)
        self.assertIn('"transient_removal_error_types"', source)

    def test_workspace_pycache_overlay_ignores_valid_stale_in_tree_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            package = temp / "samplepkg"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            module = package / "value.py"
            module.write_text("VALUE = 'old'\n", encoding="utf-8")
            fixed_time = 1_700_000_000
            os.utime(module, (fixed_time, fixed_time))
            cache = package / "__pycache__" / f"value.{sys.implementation.cache_tag}.pyc"
            cache.parent.mkdir()
            py_compile.compile(
                str(module),
                cfile=str(cache),
                invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP,
                doraise=True,
            )
            module.write_text("VALUE = 'new'\n", encoding="utf-8")
            os.utime(module, (fixed_time, fixed_time))
            plain_environment = dict(os.environ)
            plain_environment.pop("PYTHONPYCACHEPREFIX", None)
            stale = subprocess.run(
                [sys.executable, "-c", "import samplepkg.value; print(samplepkg.value.VALUE)"],
                cwd=temp,
                env=plain_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
            self.assertEqual(stale.stdout.strip(), "old")
            environment, prefix, owns = build_isolated_environment(plain_environment, temp_root=temp / "overlay")
            try:
                current = subprocess.run(
                    [sys.executable, "-c", "import samplepkg.value; print(samplepkg.value.VALUE)"],
                    cwd=temp,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=True,
                )
                self.assertEqual(current.stdout.strip(), "new")
            finally:
                if owns:
                    live.shutil.rmtree(prefix, ignore_errors=True)

    def test_step004_compatibility_launchers_delegate_to_r2(self) -> None:
        deterministic = (ROOT / "sh_run_workspace_step004_acceptance.cmd").read_text(encoding="utf-8").casefold()
        live_launcher = (ROOT / "sh_run_workspace_step004_live_acceptance.cmd").read_text(encoding="utf-8").casefold()
        self.assertIn("step004r2_acceptance", deterministic)
        self.assertIn("step004r2_live_acceptance", live_launcher)


if __name__ == "__main__":
    unittest.main()
