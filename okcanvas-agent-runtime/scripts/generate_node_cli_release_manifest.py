from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.node_acceptance import NODE_RELEASE_MANIFEST, build_node_release_manifest, run_command

CLI = ROOT / "clients" / "cli"


def _typescript_version() -> str:
    command = shutil.which("tsc.cmd") or shutil.which("tsc")
    if not command:
        raise RuntimeError("Release manifest generation requires TypeScript tsc on PATH")
    ok, output = run_command([command, "--version"], CLI)
    if not ok:
        raise RuntimeError(output)
    match = re.fullmatch(r"Version\s+([0-9]+(?:\.[0-9]+){2})\s*", output)
    if not match:
        raise RuntimeError(f"Unexpected tsc version output: {output!r}")
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--typescript-version", default=None)
    args = parser.parse_args()
    version = args.typescript_version or _typescript_version()
    manifest = build_node_release_manifest(CLI, typescript_version=version)
    output = CLI / NODE_RELEASE_MANIFEST
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
