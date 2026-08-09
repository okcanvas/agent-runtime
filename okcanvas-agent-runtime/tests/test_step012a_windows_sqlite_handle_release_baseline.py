from __future__ import annotations

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def test_step012a_runtime_baseline_and_handle_release_capability() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.recorded_run_evaluation_accepted is True
    assert info.evaluation_sqlite_connections_closed_explicitly is True
    assert info.evaluation_sqlite_windows_cleanup_live_accepted is True
    assert info.direct_reference_import_forbidden is True
