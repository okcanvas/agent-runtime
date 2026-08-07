from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.workspace_inventory import excluded_package_path

FIXED_TIME = (2026, 8, 6, 0, 0, 0)


def excluded(relative: Path) -> bool:
    return excluded_package_path(relative)


def package(output: Path) -> dict[str, object]:
    files = [path for path in sorted(ROOT.rglob("*")) if path.is_file() and not excluded(path.relative_to(ROOT))]
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        root_info = zipfile.ZipInfo(f"{ROOT.name}/", FIXED_TIME)
        root_info.external_attr = 0o40755 << 16
        archive.writestr(root_info, b"")
        for path in files:
            relative = Path(ROOT.name) / path.relative_to(ROOT)
            info = zipfile.ZipInfo(relative.as_posix(), FIXED_TIME)
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return {"output": str(output), "sha256": digest, "file_count": len(files), "entry_count": len(files) + 1}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.output.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
