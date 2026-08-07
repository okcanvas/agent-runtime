from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.current_workspace_baseline import load_current_baseline
from scripts.workspace_inventory import MUTABLE_ACCEPTANCE_EVIDENCE, excluded_workspace_path, sha256

OUTPUT = ROOT / "WORKSPACE_MANIFEST.json"
CURRENT = load_current_baseline(ROOT)
STEP = CURRENT.workspace_step
VERSION = CURRENT.workspace_version


def main() -> int:
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if excluded_workspace_path(relative):
            continue
        files.append({
            "path": relative.as_posix(),
            "sha256": sha256(path),
            "size": path.stat().st_size,
        })
    payload = {
        "schema_version": "okcanvas-agent-platform-workspace-manifest-v1",
        "step": STEP,
        "version": VERSION,
        "hash_algorithm": "SHA-256",
        "excluded_mutable_paths": [
            "WORKSPACE_MANIFEST.json",
            *sorted(MUTABLE_ACCEPTANCE_EVIDENCE),
            "**/.env",
            "**/.env.local",
            "**/.env.local.cmd",
            "log.txt",
            "*.log",
        ],
        "file_count": len(files),
        "files": files,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "file_count": len(files)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
