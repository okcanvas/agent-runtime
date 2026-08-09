from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'okcanvas-agent-runtime'
WS_STEP = 'WORKSPACE_STEP008R4R9B_RUNTIME_STEP093R1_RELATION_ROUTE_PROTOCOL_AND_LIVE_FALSE_POSITIVE_CLOSURE'
WS_VERSION = '0.8.4-r9b'
RT_STEP = 'STEP093R1_RELATION_ROUTE_PROTOCOL_AND_LIVE_FALSE_POSITIVE_CLOSURE'
RT_VERSION = '2.77.1'


def main() -> int:
    current = json.loads((ROOT / 'specs/workspace/current-baseline.json').read_text(encoding='utf-8'))
    admin = (RUNTIME / 'okcanvas_agent_protocols/rest/admin.py').read_text(encoding='utf-8')
    harness = (ROOT / 'scripts/run_workspace_step008r4r9_relation_live_acceptance.py').read_text(encoding='utf-8')
    regression = (RUNTIME / 'tests/test_step093r1_relation_route_protocol_and_live_failure_fence.py').read_text(encoding='utf-8')
    failure_summary = json.loads((ROOT / 'docs/evidence/windows/WORKSPACE_STEP008R4R9A_RELATION_LIVE_FAILURE_SUMMARY.json').read_text(encoding='utf-8'))
    baseline = (RUNTIME / 'okcanvas_agent_runtime/core/baseline.py').read_text(encoding='utf-8')
    pyproject = (RUNTIME / 'pyproject.toml').read_text(encoding='utf-8')
    checks = {
        'workspace_identity_exact': current.get('workspace_step') == WS_STEP and current.get('workspace_version') == WS_VERSION,
        'runtime_identity_exact': current.get('runtime_step') == RT_STEP and current.get('runtime_version') == RT_VERSION and f'CURRENT_STEP = "{RT_STEP}"' in baseline,
        'runtime_pyproject_exact': f'version = "{RT_VERSION}"' in pyproject,
        'typed_relation_traversal_rest_response_present': 'class OrganizationContextRelationTraversalHintResponse(StrictModel):' in admin and 'relation_traversal: OrganizationContextRelationTraversalHintResponse | None = None' in admin,
        'rest_direction_is_bounded': 'direction: Literal["OUTBOUND", "INBOUND"]' in admin,
        'rest_max_results_is_bounded': 'max_results: int = Field(ge=1, le=20)' in admin,
        'live_success_fence_true_path_present': '"harness_execution_completed_without_exception": True' in harness,
        'live_failure_fence_false_path_present': '"harness_execution_completed_without_exception": False' in harness,
        'live_failed_state_is_monotone': 'payload.get("state") == "PASSED" and all(checks.values())' in harness,
        'actual_r9a_failure_evidence_preserved': failure_summary.get('effective_state') == 'FAILED_INVALID_FALSE_POSITIVE' and failure_summary.get('observed_asgi_exception') is True,
        'actual_false_positive_observed': failure_summary.get('observed_reported_summary_passed_6_of_6') is True and failure_summary.get('acceptance_evidence_valid') is False,
        'source_regression_prepared': 'test_step093r1_rest_route_protocol_accepts_typed_relation_traversal' in regression and 'test_step093r1_live_harness_exception_path_has_explicit_false_fence' in regression,
        'promotion_not_ready': current.get('promotion') == 'NOT_READY',
        'relation_live_rerun_required': current.get('state') == 'IMPLEMENTED_STATIC_VALIDATED_RELATION_LIVE_RERUN_REQUIRED',
        'minio_still_deferred': current.get('minio_object_storage_live') == 'DEFERRED_BY_USER',
    }
    failed = [k for k,v in checks.items() if v is not True]
    payload = {
        'schema_version':'okcanvas-workspace-step008r4r9b-static-contract-validation-v1',
        'workspace_step':WS_STEP,
        'workspace_version':WS_VERSION,
        'runtime_step':RT_STEP,
        'runtime_version':RT_VERSION,
        'validation_mode':'STATIC_SOURCE_AND_ACTUAL_FAILURE_EVIDENCE_ONLY_NO_TEST_EXECUTION',
        'state':'PASSED' if not failed else 'FAILED',
        'checks':checks,
        'passed_checks':sum(v is True for v in checks.values()),
        'total_checks':len(checks),
        'failed_checks':failed,
        'limitations':{
            'unit_tests_executed':False,
            'deterministic_acceptance_executed':False,
            'corrected_relation_live_rerun_executed':False,
            'object_storage_live_executed':False,
        },
    }
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if not failed else 1

if __name__ == '__main__':
    raise SystemExit(main())
