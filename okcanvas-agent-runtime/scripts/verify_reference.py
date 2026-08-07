from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reference" / "MANIFEST.json"


def tree_hash(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    discovered = list(root.rglob("*"))
    symbolic = [path for path in discovered if path.is_symlink()]
    if symbolic:
        raise RuntimeError(f"symbolic link found in immutable reference: {symbolic[0]}")
    files = sorted((p for p in discovered if p.is_file()), key=lambda p: p.relative_to(root).as_posix())
    total = 0
    for path in files:
        data = path.read_bytes()
        total += len(data)
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest(), len(files), total


def main() -> int:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []
    for item in payload["references"]:
        root = ROOT / "reference" / "upstream" / item["dest"]
        if root.is_symlink() or not root.is_dir():
            errors.append(f"missing or symbolic directory: {root}")
            continue
        license_path = root / "LICENSE"
        if not license_path.is_file():
            errors.append(f"missing LICENSE: {license_path}")
        try:
            actual_hash, actual_count, actual_bytes = tree_hash(root)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        if actual_hash != item["tree_sha256"]:
            errors.append(f"tree sha mismatch: {item['id']} expected={item['tree_sha256']} actual={actual_hash}")
        if actual_count != item["file_count"]:
            errors.append(f"file count mismatch: {item['id']} expected={item['file_count']} actual={actual_count}")
        if actual_bytes != item["byte_count"]:
            errors.append(f"byte count mismatch: {item['id']} expected={item['byte_count']} actual={actual_bytes}")
        print(f"PASS {item['id']} files={actual_count} bytes={actual_bytes} tree_sha256={actual_hash}")
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    print(f"PASS reference baseline: {len(payload['references'])}/{len(payload['references'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
