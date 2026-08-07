from __future__ import annotations

import os
import sys
from pathlib import Path

from okcanvas_agent_runtime.bootstrap.development_cli import main


LIVE_GATE = "OKCANVAS_STEP001_LIVE_ACCEPTANCE"


def run() -> int:
    if os.getenv(LIVE_GATE) != "1":
        print(
            f"Refusing live execution: set {LIVE_GATE}=1 and OPENAI_API_KEY explicitly",
            file=sys.stderr,
        )
        return 2
    evidence = Path("docs/evidence/STEP001_LIVE_RUN.json")
    return main(
        [
            "run",
            "--input",
            (
                "Explain the confirmed scope of this STEP. Do not claim tools, file access, "
                "builds, or tests were executed by this live Agent run."
            ),
            "--confirm-live-call",
            "--evidence-file",
            str(evidence),
            "--pretty",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(run())
