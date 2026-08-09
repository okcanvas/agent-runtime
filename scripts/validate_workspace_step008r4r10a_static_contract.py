from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HARNESS=ROOT/'scripts/run_workspace_step008r4r10_cross_domain_live_acceptance.py'
BASELINE=ROOT/'specs/workspace/current-baseline.json'
ISSUE=ROOT/'WORKSPACE-ISSUE-051-CROSS-DOMAIN-LIVE-DISCARDED-FIRST-TURN-CLI-DIAGNOSTICS.md'
FAILURE=ROOT/'STEP008R4R10A_IMPLEMENTATION_FAILURE_LOG.md'
STEP='WORKSPACE_STEP008R4R10A_CROSS_DOMAIN_LIVE_FAILURE_DIAGNOSTIC_CLOSURE'
VERSION='0.8.4-r10a'

def main()->int:
    text=HARNESS.read_text(encoding='utf-8')
    baseline=json.loads(BASELINE.read_text(encoding='utf-8'))
    checks={
      'current_workspace_step': baseline.get('workspace_step')==STEP,
      'current_workspace_version': baseline.get('workspace_version')==VERSION,
      'runtime_unchanged': baseline.get('runtime_step')=='STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER' and baseline.get('runtime_version')=='2.78.0' and baseline.get('runtime_product_source_changed') is False,
      'cli_failure_diagnostic_declared': 'failure_cli_diagnostic: dict[str, object] | None = None' in text,
      'runtime_failure_diagnostic_declared': 'failure_runtime_diagnostic: dict[str, object] | None = None' in text,
      'redacted_cli_stdout_stderr_persisted': '"stdout": cli["stdout"]' in text and '"stderr": cli["stderr"]' in text,
      'failed_runtime_evidence_collected_before_raise': 'failed_evidence = await collect_runtime_evidence' in text and 'raise RuntimeError(f"Product CLI failed for {case[' in text,
      'exception_payload_retains_failure_diagnostics': '"failure_diagnostics": {' in text and '"runtime_collection_error_type": failure_runtime_diagnostic_error_type' in text,
      'final_state_remains_fail_closed': 'payload["state"] = "PASSED" if payload.get("state") == "PASSED" and all(checks.values()) else "FAILED"' in text,
      'issue_and_failure_log_present': ISSUE.is_file() and FAILURE.is_file(),
    }
    passed=sum(v is True for v in checks.values())
    payload={'schema_version':'okcanvas-workspace-step008r4r10a-static-contract-v1','state':'PASSED' if passed==len(checks) else 'FAILED','passed_checks':passed,'total_checks':len(checks),'checks':checks}
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if payload['state']=='PASSED' else 1
if __name__=='__main__': raise SystemExit(main())
