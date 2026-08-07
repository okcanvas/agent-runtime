from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.step081_product_inventory import file_map, json_sha_without_self
DEFAULT_OUTPUT = ROOT / "specs/architecture/STEP081_PRODUCT_BASELINE_INVENTORY.json"
DEFAULT_BASELINE_ZIP_SHA256 = "11a554e6a0fda3e728002ce915e9b3729622928919f30c5d30390814d2d29702"


def generate(baseline_root: Path, output: Path, baseline_zip_sha256: str) -> dict[str, object]:
    files = file_map(baseline_root)
    payload: dict[str, object] = {
        "schema_version": "okcanvas-step081-product-baseline-inventory-v1",
        "baseline_step": "STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES",
        "baseline_version": "2.60.1",
        "baseline_zip_sha256": baseline_zip_sha256,
        "file_count": len(files),
        "files": [
            {"path": path, **metadata}
            for path, metadata in sorted(files.items())
        ],
    }
    payload["inventory_sha256_without_self"] = json_sha_without_self(
        payload, "inventory_sha256_without_self"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--baseline-zip-sha256", default=DEFAULT_BASELINE_ZIP_SHA256)
    args = parser.parse_args()
    payload = generate(args.baseline_root.resolve(), args.output.resolve(), args.baseline_zip_sha256)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
