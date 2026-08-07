from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.reference_catalog import (
    ProductStoreReferenceAccessRecorder,
    ReferenceCatalogService,
    ReferencePathError,
)

ROOT = Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/evidence/STEP006_ACCEPTANCE.json",
    )
    args = parser.parse_args()

    started_at = _utc_now()
    catalog = ReferenceCatalogService(ROOT)
    before = {item.reference_id: item.to_dict() for item in catalog.verify_all()}
    references = [item.to_dict() for item in catalog.list_references()]

    search = catalog.search(
        "RunState",
        reference_ids=("openai-agents-python",),
        max_results=8,
    )
    mapped = next(
        item
        for item in search.code_map_matches
        if item.relative_path == "src/agents/run_state.py"
    )
    first_match = next(
        item
        for item in search.matches
        if item.relative_path == "src/agents/run_state.py"
    )
    read = catalog.read_lines(
        "openai-agents-python",
        mapped.relative_path,
        start_line=first_match.line_number,
        end_line=first_match.line_number + 4,
    )

    traversal_blocked = False
    try:
        catalog.read_lines(
            "openai-agents-python",
            "../AGENTS.md",
            start_line=1,
            end_line=1,
        )
    except ReferencePathError:
        traversal_blocked = True

    with AcceptanceWorkspace(step_id="STEP006", output=args.output) as workspace:
        store = SQLiteProductStore(workspace.database_dir / "acceptance-product.sqlite3")
        store.initialize()
        task = store.create_task(
            task_type="REFERENCE_ACCEPTANCE",
            input_sha256=hashlib.sha256(b"STEP006 acceptance").hexdigest(),
            agent_definition_id="reference-catalog",
            agent_definition_version="v1",
        )
        run = store.create_run(task_id=task.task_id)
        recorded_catalog = ReferenceCatalogService(
            ROOT, recorder=ProductStoreReferenceAccessRecorder(store)
        )
        recorded_search = recorded_catalog.search(
            "RunState",
            reference_ids=("openai-agents-python",),
            max_results=3,
            run_id=run.run_id,
        )
        recorded_catalog.read_lines(
            "openai-agents-python",
            "src/agents/run_state.py",
            start_line=1,
            end_line=3,
            run_id=run.run_id,
        )
        events = store.list_events(run.run_id)
        event_types = [event.event_type for event in events]
        raw_query_persisted = "RunState" in json.dumps(
            [event.payload for event in events], ensure_ascii=False
        )

    after = {item.reference_id: item.to_dict() for item in catalog.verify_all()}
    checks = {
        "manifest_reference_count": len(references) == 4,
        "all_trees_verified_before": all(item["verified"] for item in before.values()),
        "code_map_first_match": mapped.relative_path == "src/agents/run_state.py",
        "exact_search_match": first_match.relative_path == "src/agents/run_state.py",
        "exact_line_read": bool(read.lines) and "RunState" in read.lines[0].text,
        "file_sha_consistent": mapped.file_sha256 == read.file_sha256,
        "traversal_blocked": traversal_blocked,
        "search_event_recorded": "reference.search.completed" in event_types,
        "read_event_recorded": "reference.file.read" in event_types,
        "raw_query_not_persisted": not raw_query_persisted,
        "query_hash_persisted": recorded_search.query_sha256
        in json.dumps([event.payload for event in events]),
        "all_trees_unchanged": before == after,
    }
    state = "PASSED" if all(checks.values()) else "FAILED"
    payload: dict[str, object] = {
        "schema_version": "okcanvas-step006-acceptance-v1",
        "state": state,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "checks": checks,
        "references": references,
        "search": search.to_dict(),
        "read": read.to_dict(),
        "event_types": event_types,
        "reference_verification_before": before,
        "reference_verification_after": after,
    }
    payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if state == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
