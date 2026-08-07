from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.current_workspace_baseline import CurrentWorkspaceBaseline, assert_catalog_matches_current_baseline, load_current_baseline


def expected_marker_lines(baseline: CurrentWorkspaceBaseline) -> tuple[str, ...]:
    return (
        f"Current Workspace: {baseline.workspace_step}",
        f"Workspace Version: {baseline.workspace_version}",
        f"Current Runtime: {baseline.runtime_step}",
        f"Runtime Version: {baseline.runtime_version}",
    )


def validate_one_document(path: Path, baseline: CurrentWorkspaceBaseline) -> list[str]:
    if not path.is_file():
        return [f"missing current document: {path}"]
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    errors: list[str] = []
    for expected in expected_marker_lines(baseline):
        label = expected.split(":", 1)[0] + ":"
        observed = [line for line in lines if line.startswith(label)]
        if observed != [expected]:
            errors.append(f"{path}: expected exactly one `{expected}` marker, observed={observed}")
    return errors


def validate_current_documents(
    root: Path = ROOT,
    *,
    baseline: CurrentWorkspaceBaseline | None = None,
) -> list[str]:
    current = baseline or load_current_baseline(root)
    errors: list[str] = []
    for relative in current.current_documents:
        errors.extend(validate_one_document(root / relative, current))
    if baseline is None:
        try:
            assert_catalog_matches_current_baseline(root)
        except (ValueError, StopIteration) as exc:
            errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate each current document against current-baseline.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate_current_documents(args.root.resolve())
    payload = {
        "schema_version": "okcanvas-current-document-sot-validation-v1",
        "state": "PASSED" if not errors else "FAILED",
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
