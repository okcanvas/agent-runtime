from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import UTC, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane
from scripts.validate_step082b_distribution import validate as validate_distribution
STEP='STEP082B_CODING_EXECUTION_PLANE_AND_DISTRIBUTION_BOUNDARY_CONSOLIDATION'
VERSION='2.62.2'
OUTPUT_DEFAULT=ROOT/'docs/evidence/step082b-local/STEP082B_ACCEPTANCE.json'

def _now(): return datetime.now(UTC).isoformat().replace('+00:00','Z')
def run(output:Path)->int:
    started=_now(); info=RuntimeInfo(); live=json.loads((ROOT/'docs/evidence/STEP081D_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json').read_text())
    execution=validate_execution_plane(); distribution=validate_distribution(); registry=validate_registry()
    architecture,architecture_process=run_json_python_validator(root=ROOT,script=ROOT/'scripts/validate_step081_architecture.py')
    focused_ok,focused_output=run_command([sys.executable,'-m','pytest','-q','tests/test_step082b_coding_execution_plane_and_distribution_boundary.py','tests/test_baseline_version.py','tests/test_runtime_info.py','tests/test_step081_windows_entrypoint_and_launcher_registry.py','tests/test_step081_root_package_and_architecture_restructuring.py'],ROOT)
    compile_ok,compile_output=run_command([sys.executable,'-m','compileall','-q','okcanvas_agent_runtime','okcanvas_agent_protocols','okcanvas_agent_clients','scripts','tests'],ROOT)
    checks={
      'identity_exact':CURRENT_STEP==STEP and PROJECT_VERSION==VERSION and info.step==STEP and info.version==VERSION,
      'step081d_windows_live_promoted':live.get('state')=='PASSED' and live.get('passed_checks')==live.get('total_checks')==80 and info.step081d_windows_live_accepted is True,
      'step081d_architecture_live_promoted':live.get('architecture',{}).get('passed_checks')==live.get('architecture',{}).get('total_checks')==40 and info.architecture_constitution_windows_live_accepted is True,
      'execution_plane_validation_passed':execution.get('state')=='PASSED' and execution.get('passed_checks')==execution.get('total_checks')==13,
      'distribution_validation_passed':distribution.get('state')=='PASSED' and distribution.get('passed_checks')==distribution.get('total_checks')==14,
      'architecture_regression_passed':architecture_process.get('returncode')==0 and architecture.get('state')=='PASSED' and architecture.get('passed_checks')==architecture.get('total_checks')==40,
      'launcher_registry_passed':registry.get('state')=='PASSED' and registry.get('current_step')==STEP and registry.get('current_record_count')==2,
      'focused_regression_passed':focused_ok,
      'compileall_passed':compile_ok,
      'issues_recorded':all((ROOT/'docs/issues'/name).is_file() for name in ('OR-ISSUE-054-STEP081D-WINDOWS-LIVE-PASS-NOT-PROMOTED-IN-PRODUCT-STATE.md','OR-ISSUE-055-CODING-EXECUTION-CONTROL-PLANE-SPLIT.md','OR-ISSUE-056-WHEEL-STARTUP-DEPENDS-ON-EXTERNAL-CONFIG-AND-REFERENCE-PACKS.md')),
      'next_step_exact':info.next_selected_step=='STEP083_ORGANIZATION_ASSISTANT_MAIN_AGENT_AND_ACTION_ROUTING_FOUNDATION',
      'product_source_movement_still_blocked':info.architecture_constitution_source_movement_allowed is False,
    }
    payload={'schema_version':'okcanvas-step082b-acceptance-v1','step':STEP,'version':VERSION,'state':'PASSED' if all(checks.values()) else 'FAILED','started_at':started,'completed_at':_now(),'checks':checks,'passed_checks':sum(checks.values()),'total_checks':len(checks),'step081d_windows_live_summary':live,'execution_plane_validation':execution,'distribution_validation':distribution,'architecture_validation':architecture,'architecture_validation_process':architecture_process,'launcher_registry':registry,'focused_output':focused_output,'compile_output':compile_output}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)); return 0 if payload['state']=='PASSED' else 1
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=OUTPUT_DEFAULT); a=ap.parse_args(); return run(a.output.resolve())
if __name__=='__main__': raise SystemExit(main())
