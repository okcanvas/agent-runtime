from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.project_source_identity import force_project_root_first
force_project_root_first(ROOT)

from scripts.run_step081_live_acceptance import main


if __name__ == "__main__":
    raise SystemExit(main())
