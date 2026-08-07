from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from okcanvas_agent_runtime.adapters.workspace import snapshot_tree


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "codex_readonly_repo"


def main() -> int:
    before = snapshot_tree(FIXTURE)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FIXTURE / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(FIXTURE / "tests" / "test_pricing.py")],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    after = snapshot_tree(FIXTURE)
    output = (completed.stdout + completed.stderr).strip()
    print(output)
    if before.sha256 != after.sha256:
        print("FAIL: fixture changed during verification", file=sys.stderr)
        return 4
    if completed.returncode == 0:
        print("FAIL: fixture defect was not reproduced", file=sys.stderr)
        return 4
    expected_fragments = ["1 failed", "25000", "15000"]
    if not all(fragment in output for fragment in expected_fragments):
        print("FAIL: fixture failed for an unexpected reason", file=sys.stderr)
        return 4
    print(
        f"PASS: intentional quantity defect reproduced; tree_sha256={before.sha256}; "
        f"files={before.file_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
