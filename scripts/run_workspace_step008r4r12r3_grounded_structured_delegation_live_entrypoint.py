from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "okcanvas-agent-runtime"
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from scripts.windows_entrypoint import build_child_environment, load_local_environment

ENV_SOURCE_NAME = "OKCANVAS_LOCAL_ENV_SOURCE_NAME"
ENV_LOADED_KEYS = "OKCANVAS_LOCAL_ENV_LOADED_KEYS"
LIVE_GATE = "OKCANVAS_WORKSPACE_STEP008R4R12R3_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE"


def main() -> int:
    local_values, source = load_local_environment(RUNTIME_ROOT)
    environment = build_child_environment(local_values)
    environment[LIVE_GATE] = "1"
    environment[ENV_SOURCE_NAME] = source.name if source is not None else ""
    environment[ENV_LOADED_KEYS] = ",".join(sorted(local_values))
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_workspace_step008r4r12r3_grounded_structured_delegation_live_acceptance.py"),
            *sys.argv[1:],
        ],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
