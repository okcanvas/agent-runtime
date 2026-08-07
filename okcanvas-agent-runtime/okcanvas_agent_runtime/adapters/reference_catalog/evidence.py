from __future__ import annotations

from okcanvas_agent_runtime.domain.runs import EventSource, ProductStore

from okcanvas_agent_runtime.adapters.reference_catalog.models import ReferenceReadResult, ReferenceSearchResult


class ProductStoreReferenceAccessRecorder:
    """Normalize reference access into the canonical STEP005 Run event journal."""

    def __init__(self, store: ProductStore) -> None:
        self._store = store

    def record_search(self, run_id: str, result: ReferenceSearchResult) -> None:
        self._store.append_event(
            run_id,
            event_type="reference.search.completed",
            source=EventSource.REFERENCE,
            payload_schema_version="okcanvas-reference-search-v1",
            payload={
                "query_sha256": result.query_sha256,
                "reference_ids": list(result.reference_ids),
                "code_map_match_count": len(result.code_map_matches),
                "match_count": len(result.matches),
                "scanned_files": result.scanned_files,
                "truncated": result.truncated,
            },
        )

    def record_read(self, run_id: str, result: ReferenceReadResult) -> None:
        self._store.append_event(
            run_id,
            event_type="reference.file.read",
            source=EventSource.REFERENCE,
            payload_schema_version="okcanvas-reference-file-read-v1",
            payload={
                "reference_id": result.reference_id,
                "relative_path": result.relative_path,
                "start_line": result.actual_start_line,
                "end_line": result.actual_end_line,
                "file_sha256": result.file_sha256,
                "byte_length": result.byte_length,
            },
        )
