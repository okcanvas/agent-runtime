from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.project_source_identity import force_project_root_first
force_project_root_first(ROOT)

from scripts.run_step081_acceptance import run

OUTPUT_DEFAULT = ROOT / "docs/evidence/step081d-local/STEP081D_ACCEPTANCE.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
