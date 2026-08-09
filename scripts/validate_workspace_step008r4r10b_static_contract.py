from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HARNESS=ROOT/'scripts/run_workspace_step008r4r10_cross_domain_live_acceptance.py'
BASELINE=ROOT/'specs/workspace/current-baseline.json'
ISSUE=ROOT/'WORKSPACE-ISSUE-052-CLI-PROCESS-SUCCESS-DID-NOT-PROVE-REQUEST-COMPLETION-OR-RUN-CARDINALITY.md'
FAILURE=ROOT/'STEP008R4R10B_IMPLEMENTATION_FAILURE_LOG.md'
USER_EVIDENCE=ROOT/'docs/evidence/WORKSPACE_STEP008R4R10A_CROSS_DOMAIN_LIVE_FAILURE_USER_REPORTED.json'
STEP='WORKSPACE_STEP008R4R10B_POST_CLI_REQUEST_COMPLETION_AND_RUN_CARDINALITY_DIAGNOSTIC_CLOSURE'
VERSION='0.8.4-r10b'

def main()->int:
    text=HARNESS.read_text(encoding='utf-8')
    baseline=json.loads(BASELINE.read_text(encoding='utf-8'))
    checks={
      'current_workspace_step': baseline.get('workspace_step')==STEP,
      'current_workspace_version': baseline.get('workspace_version')==VERSION,
      'runtime_product_identity_unchanged': baseline.get('runtime_step')=='STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER' and baseline.get('runtime_version')=='2.78.0' and baseline.get('runtime_product_source_changed') is False,
      'latest_cli_snapshot_is_unconditional_before_post_cli_assertions': 'failure_cli_diagnostic = dict(cli_summary)' in text and text.index('failure_cli_diagnostic = dict(cli_summary)') < text.index('if cli["returncode"] != 0:'),
      'runtime_run_snapshot_is_collected_before_post_cli_assertions': 'failure_runtime_diagnostic = {' in text and '"run_count": len(runs)' in text and '"runs": [' in text and text.index('failure_runtime_diagnostic = {') < text.index('if cli["returncode"] != 0:'),
      'process_exit_and_request_completion_are_separate': 'if cli["returncode"] != 0:' in text and 'if not cli_summary["one_request_completed"]:' in text,
      'request_completion_precedes_run_cardinality': text.index('if not cli_summary["one_request_completed"]:') < text.index('if len(runs) != index + 1:'),
      'run_cardinality_remains_exact': 'if len(runs) != index + 1:' in text,
      'exception_payload_retains_failure_diagnostics': '"failure_diagnostics": {' in text and '"runtime_collection_error_type": failure_runtime_diagnostic_error_type' in text,
      'final_state_remains_fail_closed': 'payload["state"] = "PASSED" if payload.get("state") == "PASSED" and all(checks.values()) else "FAILED"' in text,
      'no_fallback_alias_markers_added': all(token not in text for token in ('display_name_fallback','helper_alias','compatibility_fallback','tool_fallback')),
      'issue_failure_and_user_evidence_present': ISSUE.is_file() and FAILURE.is_file() and USER_EVIDENCE.is_file(),
    }
    passed=sum(v is True for v in checks.values())
    payload={'schema_version':'okcanvas-workspace-step008r4r10b-static-contract-v1','state':'PASSED' if passed==len(checks) else 'FAILED','passed_checks':passed,'total_checks':len(checks),'checks':checks}
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if payload['state']=='PASSED' else 1
if __name__=='__main__': raise SystemExit(main())
