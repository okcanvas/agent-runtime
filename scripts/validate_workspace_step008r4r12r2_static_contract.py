from __future__ import annotations
import hashlib, importlib.util, json, subprocess, sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
for p in (ROOT,SCRIPTS):
    if str(p) not in sys.path: sys.path.insert(0,str(p))
from scripts.validate_current_document_sot import validate_current_documents
from scripts.workspace_inventory import MUTABLE_ACCEPTANCE_EVIDENCE, excluded_workspace_path
from scripts.validate_workspace_step008r4r12r1_static_contract import (
    _first_party_json_clean,_first_party_python_ast_clean,_local_secret_files_absent,
    _manifest_matches,_product_python_parent_exact,_run_json,_secret_like_literals_absent,
)
STEP='WORKSPACE_STEP008R4R12R2_STEP096B_LIVE_HARNESS_EVIDENCE_REDACTION_SERIALIZATION_CLOSURE'
VERSION='0.8.4-r12r2'
RUNTIME_STEP='STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION'
RUNTIME_VERSION='2.80.0'
PARENT_STEP='WORKSPACE_STEP008R4R12R1_STEP096B_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE_HARNESS'
PARENT_VERSION='0.8.4-r12r1'
PARENT_SHA='65fa8e11820b68208a363f179c3bf1663bf8eed8b2360f220aa26ec47f26ab03'
EVIDENCE='docs/evidence/WORKSPACE_STEP008R4R12R2_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE.json'

def load(rel:str)->dict[str,Any]: return json.loads((ROOT/rel).read_text(encoding='utf-8'))
def workspace_manifest_exact()->bool:
    p=ROOT/'WORKSPACE_MANIFEST.json'
    if not p.is_file(): return False
    m=load('WORKSPACE_MANIFEST.json')
    expected={i['path']:(i['sha256'],int(i['size'])) for i in m.get('files',[])}
    actual={}
    for f in sorted(ROOT.rglob('*')):
        if f.is_file() and not excluded_workspace_path(f.relative_to(ROOT)):
            b=f.read_bytes(); actual[f.relative_to(ROOT).as_posix()]=(hashlib.sha256(b).hexdigest(),len(b))
    return m.get('step')==STEP and m.get('version')==VERSION and EVIDENCE in m.get('excluded_mutable_paths',[]) and expected==actual and m.get('file_count')==len(actual)
def redaction_regression()->bool:
    path=ROOT/'scripts/run_workspace_step008r4r12r2_grounded_structured_delegation_live_acceptance.py'
    spec=importlib.util.spec_from_file_location('r12r2_live',path)
    if spec is None or spec.loader is None: return False
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    secret='synthetic-secret-r12r2'
    payload={'outer':{'token':secret,'items':['ok',secret]},'number':7,'flag':True}
    text=mod._redacted_json_text(payload,[secret])
    parsed=json.loads(text)
    return secret not in text and text.count('[REDACTED]')==2 and parsed['outer']['token']=='[REDACTED]' and parsed['outer']['items'][1]=='[REDACTED]' and parsed['number']==7

def main()->int:
    base=load('specs/workspace/current-baseline.json'); cat=load('specs/workspace/project-catalog.json')
    marker=load('WORKSPACE_STEP008R4R12R2_PROMOTION_MARKER.json')
    runtime=ROOT/'okcanvas-agent-runtime'
    rs=_run_json(runtime,'scripts/validate_step096b_static_contract.py')
    acc_path=Path('/tmp/step096b-r12r2.json')
    acc_proc=subprocess.run([sys.executable,'scripts/run_step096b_acceptance.py',str(acc_path)],cwd=runtime,text=True,capture_output=True,check=False)
    acc=json.loads(acc_path.read_text(encoding='utf-8')) if acc_proc.returncode==0 and acc_path.is_file() else {'state':'FAILED','focused_pytest':{}}
    launch=_run_json(runtime,'scripts/validate_acceptance_launcher_registry.py')
    const=_run_json(runtime,'scripts/validate_architecture_constitution.py','--output','/tmp/step096b-r12r2-constitution.json')
    arch=_run_json(runtime,'scripts/validate_step081_architecture.py')
    afalse=sorted(k for k,v in (arch.get('checks') or {}).items() if v is not True)
    prod_exact,prod_count=_product_python_parent_exact()
    pyok,pycount=_first_party_python_ast_clean(); jsok,jscount=_first_party_json_clean()
    issues=(ROOT/'docs/issues/ISSUE_REGISTRY.md').read_text(encoding='utf-8')
    failure=load('docs/evidence/WORKSPACE_STEP008R4R12R1_LIVE_FAILURE_USER_REPORTED.json')
    checks={
      'workspace_identity_exact': base.get('workspace_step')==STEP and base.get('workspace_version')==VERSION and cat.get('workspace_step')==STEP and cat.get('workspace_version')==VERSION,
      'parent_r12r1_exact': base.get('parent_workspace_step')==PARENT_STEP and base.get('parent_workspace_version')==PARENT_VERSION and base.get('source_release_sha256')==PARENT_SHA,
      'runtime_identity_unchanged': base.get('runtime_step')==RUNTIME_STEP and base.get('runtime_version')==RUNTIME_VERSION and base.get('runtime_product_source_changed') is False,
      'promotion_rerun_pending': marker.get('promotion')=='CANDIDATE_FOCUSED_WINDOWS_LIVE_RERUN_PENDING' and marker.get('step096br1_windows_live')=='RERUN_NOT_RUN',
      'r12r1_failure_preserved_unknown': failure.get('failure_stage')=='EVIDENCE_REDACTION_SERIALIZATION' and failure.get('live_functional_result')=='UNKNOWN_NOT_CLAIMED',
      'redaction_regression_nested_payload': redaction_regression(),
      'r12r2_harness_trio_present': all((ROOT/p).is_file() for p in ['scripts/run_workspace_step008r4r12r2_grounded_structured_delegation_live_acceptance.py','scripts/run_workspace_step008r4r12r2_grounded_structured_delegation_live_entrypoint.py','sh_run_workspace_step008r4r12r2_grounded_structured_delegation_live_acceptance.cmd']),
      'r12r2_evidence_mutable': EVIDENCE in MUTABLE_ACCEPTANCE_EVIDENCE,
      'issue_073_recorded': 'WORKSPACE-ISSUE-073 | FIXED_IN_R12R2' in issues and (ROOT/'docs/issues/WORKSPACE-ISSUE-073-BR1-EVIDENCE-REDACTION-DICT-TYPE-CONTRACT.md').is_file(),
      'runtime_step096b_static_20_of_20': rs.get('state')=='PASSED' and rs.get('passed_checks')==20 and rs.get('total_checks')==20,
      'runtime_step096b_acceptance_6_of_6': acc.get('state')=='PASSED' and acc.get('passed_checks')==6 and acc.get('total_checks')==6,
      'runtime_focused_regression_63_of_63': '63 passed' in str((acc.get('focused_pytest') or {}).get('summary','')),
      'launcher_registry_7_of_7': launch.get('state')=='PASSED' and launch.get('passed_checks')==7,
      'architecture_constitution_16_of_16': const.get('state')=='PASSED' and const.get('passed_checks')==16,
      'current_architecture_except_historical_identity': arch.get('passed_checks')==39 and arch.get('total_checks')==40 and afalse==['identity_exact'],
      'runtime_product_python_379_parent_exact': prod_exact and prod_count==379,
      'connectors_examples_unchanged': all([_manifest_matches('okcanvas-connectors/groupware-mcp-server','reference/parent-file-manifests/okcanvas-connectors__groupware-mcp-server.json'),_manifest_matches('okcanvas-connector-examples/groupware/groupware-api-fake','reference/parent-file-manifests/okcanvas-connector-examples__groupware__groupware-api-fake.json'),_manifest_matches('okcanvas-connectors/organization-context-mcp-server','reference/parent-file-manifests/okcanvas-connectors__organization-context-mcp-server.json'),_manifest_matches('okcanvas-connector-examples/organization-context/organization-context-api-fake','reference/parent-file-manifests/okcanvas-connector-examples__organization-context__organization-context-api-fake.json')]),
      'current_document_sot_exact': not validate_current_documents(ROOT),
      'first_party_python_ast_clean': pyok,
      'first_party_json_clean': jsok,
      'local_secret_environment_files_absent': _local_secret_files_absent(),
      'secret_like_literals_absent': _secret_like_literals_absent(),
      'workspace_manifest_exact': workspace_manifest_exact(),
    }
    out={'schema_version':'okcanvas-workspace-step008r4r12r2-static-contract-v1','state':'PASSED' if all(checks.values()) else 'FAILED','step':STEP,'version':VERSION,'runtime_step':RUNTIME_STEP,'runtime_version':RUNTIME_VERSION,'checks':checks,'passed_checks':sum(v is True for v in checks.values()),'total_checks':len(checks),'python_files_parsed':pycount,'json_files_parsed':jscount}
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)); return 0 if out['state']=='PASSED' else 2
if __name__=='__main__': raise SystemExit(main())
