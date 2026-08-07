from __future__ import annotations
import json
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'specs/acceptance/launcher-registry.json'

def _load()->dict[str,Any]:
    payload=json.loads(REGISTRY.read_text(encoding='utf-8'))
    if not isinstance(payload,dict): raise TypeError('Acceptance launcher registry must contain an object')
    return payload

def validate()->dict[str,Any]:
    payload=_load(); records=payload.get('records')
    if payload.get('schema_version')!='okcanvas-acceptance-launcher-registry-v2': raise ValueError('Invalid acceptance launcher registry schema')
    if not isinstance(records,list): raise ValueError('Acceptance launcher registry records must be a list')
    current_step=payload.get('current_step'); current_token=payload.get('current_step_token'); required=payload.get('required_current_records')
    if not isinstance(current_step,str) or not current_step: raise ValueError('Current step is invalid')
    if not isinstance(current_token,str) or not current_token: raise ValueError('Current step token is invalid')
    if not isinstance(required,list) or not required: raise ValueError('Current required record contract is invalid')
    required_pairs={(item.get('kind'),item.get('mode')) for item in required if isinstance(item,dict)}
    if len(required_pairs)!=len(required): raise ValueError('Current required record pairs must be unique')
    actual_scripts={p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts').glob('run_step*_acceptance.py')}
    actual_launchers={p.relative_to(ROOT).as_posix() for p in ROOT.glob('sh_run_step*_acceptance.cmd')}
    registered=[]; current=[]
    for record in records:
        if not isinstance(record,dict): raise ValueError('Acceptance launcher registry record must be an object')
        path=record.get('path'); kind=record.get('kind'); classification=record.get('classification'); mode=record.get('mode'); token=record.get('step_token')
        if not isinstance(path,str) or not path: raise ValueError('Acceptance launcher registry path is invalid')
        if kind not in {'python-script','windows-launcher'}: raise ValueError(f'Invalid acceptance registry kind for {path}')
        if mode not in {'DETERMINISTIC','LIVE'}: raise ValueError(f'Invalid acceptance registry mode for {path}')
        if classification not in {'CURRENT','HISTORICAL'}: raise ValueError(f'Invalid acceptance registry classification for {path}')
        if not isinstance(token,str) or not token: raise ValueError(f'Invalid acceptance registry token for {path}')
        if not (ROOT/path).is_file(): raise ValueError(f'Registered acceptance path does not exist: {path}')
        registered.append(path)
        if classification=='CURRENT':
            current.append(record)
            if token!=current_token or current_token.casefold() not in path.casefold():
                raise ValueError(f'Only {current_token} records may be CURRENT: {path}')
    if len(registered)!=len(set(registered)): raise ValueError('Acceptance launcher registry paths must be unique')
    registered_scripts={p for p in registered if p.startswith('scripts/')}; registered_launchers={p for p in registered if p.startswith('sh_run_')}
    if registered_scripts!=actual_scripts: raise ValueError(f'Acceptance script registry drift: missing={sorted(actual_scripts-registered_scripts)}, extra={sorted(registered_scripts-actual_scripts)}')
    if registered_launchers!=actual_launchers: raise ValueError(f'Acceptance launcher registry drift: missing={sorted(actual_launchers-registered_launchers)}, extra={sorted(registered_launchers-actual_launchers)}')
    current_pairs={(r['kind'],r['mode']) for r in current}
    if current_pairs!=required_pairs or len(current)!=len(required_pairs):
        raise ValueError(f'Current record contract mismatch: expected={sorted(required_pairs)}, actual={sorted(current_pairs)}')
    checks={'schema_exact':True,'registered_paths_unique':True,'all_registered_paths_exist':True,'all_step_acceptance_scripts_registered':True,'all_step_windows_launchers_registered':True,'current_classification_exact':True,'current_record_contract_exact':True}
    return {'schema_version':'okcanvas-acceptance-launcher-registry-validation-v2','state':'PASSED','passed_checks':len(checks),'total_checks':len(checks),'checks':checks,'current_step':current_step,'current_step_token':current_token,'script_count':len(actual_scripts),'launcher_count':len(actual_launchers),'record_count':len(records),'current_record_count':len(current),'current_records':sorted(r['path'] for r in current)}
if __name__=='__main__': print(json.dumps(validate(),indent=2,sort_keys=True))
