from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from okcanvas_agent_runtime.support.validation import run_pytest_validation
from okcanvas_agent_runtime.adapters.workspace import snapshot_tree


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "codex_write_repo"
TARGET = Path("src/inventory/pricing.py")


def main() -> int:
    source_before = snapshot_tree(FIXTURE)
    with tempfile.TemporaryDirectory(prefix="okcanvas-step003-static-") as temp_dir:
        workspace = Path(temp_dir) / "fixture-repo"
        shutil.copytree(FIXTURE, workspace)
        baseline = run_pytest_validation(workspace)
        target = workspace / TARGET
        target.write_text(
            'from __future__ import annotations\n\n\ndef calculate_total(lines: list[dict[str, int]]) -> int:\n    """Return an order total in Korean won."""\n    return sum(line["unit_price"] * line["quantity"] for line in lines)\n',
            encoding="utf-8",
        )
        repaired = run_pytest_validation(workspace)
    source_after = snapshot_tree(FIXTURE)
    checks = {
        "baseline_failed_once": baseline.state == "FAILED" and baseline.failed == 1,
        "known_minimal_repair_passed": repaired.state == "PASSED" and repaired.passed == 1,
        "source_fixture_unchanged": source_before == source_after,
    }
    payload = {
        "checks": checks,
        "baseline": baseline.model_dump(mode="json"),
        "repaired": repaired.model_dump(mode="json"),
        "source_before": source_before.model_dump(mode="json"),
        "source_after": source_after.model_dump(mode="json"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
