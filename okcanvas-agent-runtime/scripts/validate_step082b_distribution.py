from __future__ import annotations
import importlib.util, json, os, shutil, site, subprocess, sys, tempfile, tomllib, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.package_product_configuration_pack import package as package_config
from scripts.package_reference_pack import package as package_reference
from scripts.validate_step081_installation import _backend_source
POLICY=ROOT/'specs/distribution/product-artifact-boundaries.json'
STEP='STEP082B_CODING_EXECUTION_PLANE_AND_DISTRIBUTION_BOUNDARY_CONSOLIDATION'
VERSION='2.62.2'

def _run(command,cwd,env=None,timeout=300):
    cp=subprocess.run(command,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout,check=False)
    return cp.returncode==0,cp.stdout

def _external_deps():
    return os.pathsep.join(str(Path(x).resolve()) for x in site.getsitepackages() if Path(x).is_dir())

def _probe(py:Path,cwd:Path,project_root:Path,mode:str,env:dict[str,str]):
    code="""
import json,sys
from pathlib import Path
from okcanvas_agent_runtime.bootstrap.application import create_app
root=Path(sys.argv[1]); base=Path(sys.argv[2]); mode=sys.argv[3]
try:
 app=create_app(project_root=root,product_db=base/(mode+'.sqlite3'),artifact_root=base/(mode+'-artifacts'),admin_key='0123456789abcdef')
 print(json.dumps({'state':'PASSED','route_count':len(app.routes),'runtime_origin':__import__('okcanvas_agent_runtime').__file__}))
except Exception as exc:
 print(json.dumps({'state':'FAILED','error_type':type(exc).__name__,'error':str(exc)}))
"""
    ok,out=_run([str(py),'-c',code,str(project_root),str(cwd),mode],cwd,env)
    try: payload=json.loads(out.strip().splitlines()[-1])
    except Exception: payload={'state':'PROCESS_FAILED','output':out}
    payload['process_ok']=ok
    return payload

def validate():
    policy=json.loads(POLICY.read_text(encoding='utf-8'))
    pyproject=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
    configured=tuple(pyproject['tool']['hatch']['build']['targets']['wheel']['packages'])
    with tempfile.TemporaryDirectory(prefix='step082b-dist-') as td:
        temp=Path(td); wheel_dir=temp/'wheel'; wheel_dir.mkdir(); backend=temp/'backend'; venv=temp/'venv'; execution=temp/'execution'; execution.mkdir()
        env=os.environ.copy(); external=importlib.util.find_spec('hatchling') is not None
        if not external:
            pkg=backend/'hatchling'; pkg.mkdir(parents=True); (pkg/'__init__.py').write_text(''); (pkg/'build.py').write_text(_backend_source())
            env['PYTHONPATH']=str(backend)
        wheel_ok,wheel_output=_run([sys.executable,'-m','pip','wheel','.', '--no-deps','--no-build-isolation','-w',str(wheel_dir)],ROOT,env)
        wheels=sorted(wheel_dir.glob('*.whl'))
        venv_ok,venv_output=_run([sys.executable,'-m','venv',str(venv)],execution)
        py=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        install_ok=False; install_output='not built'
        if venv_ok and len(wheels)==1: install_ok,install_output=_run([str(py),'-m','pip','install','--no-deps',str(wheels[0])],execution)
        runtime_env=os.environ.copy(); runtime_env['PYTHONPATH']=_external_deps()
        empty=temp/'empty'; empty.mkdir()
        config_zip=temp/'config.zip'; ref_zip=temp/'reference.zip'
        config=package_config(config_zip); reference=package_reference(ref_zip)
        config_only=temp/'config-only'; composite=temp/'composite'; config_only.mkdir(); composite.mkdir()
        with zipfile.ZipFile(config_zip) as z: z.extractall(temp/'config-extract')
        with zipfile.ZipFile(ref_zip) as z: z.extractall(temp/'reference-extract')
        shutil.copytree(temp/'config-extract'/'okcanvas-agent-runtime-config'/'specs',config_only/'specs')
        shutil.copytree(config_only/'specs',composite/'specs')
        shutil.copytree(temp/'reference-extract'/'okcanvas-agent-runtime-reference'/'reference',composite/'reference')
        empty_probe=_probe(py,execution,empty,'wheel-only',runtime_env) if install_ok else {'state':'NOT_RUN'}
        config_probe=_probe(py,execution,config_only,'wheel-config-only',runtime_env) if install_ok else {'state':'NOT_RUN'}
        composite_probe=_probe(py,execution,composite,'wheel-config-reference',runtime_env) if install_ok else {'state':'NOT_RUN'}
        source_probe=_probe(Path(sys.executable),execution,ROOT,'full-source',dict(os.environ, PYTHONPATH=str(ROOT)))
        checks={
          'distribution_policy_schema_exact':policy.get('schema_version')=='okcanvas-product-distribution-boundary-v1',
          'wheel_package_allowlist_exact':configured==('okcanvas_agent_runtime','okcanvas_agent_protocols','okcanvas_agent_clients'),
          'specs_not_in_wheel_allowlist':'specs' not in configured,
          'reference_not_in_wheel_allowlist':'reference' not in configured,
          'wheel_build_completed':wheel_ok and len(wheels)==1,
          'wheel_install_completed':install_ok,
          'full_source_startup_passed':source_probe.get('state')=='PASSED',
          'wheel_only_fails_closed_without_config':empty_probe.get('state')=='FAILED',
          'wheel_plus_config_fails_closed_without_reference':config_probe.get('state')=='FAILED',
          'wheel_plus_config_and_reference_startup_passed':composite_probe.get('state')=='PASSED',
          'configuration_pack_nonempty':config['entry_count']>0,
          'reference_pack_nonempty':reference['entry_count']>0,
          'configuration_pack_root_exact':config['root']=='okcanvas-agent-runtime-config',
          'reference_pack_root_exact':reference['root']=='okcanvas-agent-runtime-reference',
        }
        return {'schema_version':'okcanvas-step082b-distribution-validation-v1','step':STEP,'version':VERSION,'state':'PASSED' if all(checks.values()) else 'FAILED','checks':checks,'passed_checks':sum(checks.values()),'total_checks':len(checks),'configured_wheel_packages':list(configured),'probes':{'full_source':source_probe,'wheel_only':empty_probe,'wheel_plus_config':config_probe,'wheel_plus_config_and_reference':composite_probe},'packs':{'configuration':{k:v for k,v in config.items() if k!='entries'},'reference':{k:v for k,v in reference.items() if k!='entries'}},'outputs':{'wheel_build':wheel_output,'venv':venv_output,'install':install_output}}
if __name__=='__main__':
    result=validate(); print(json.dumps(result,indent=2,sort_keys=True)); raise SystemExit(0 if result['state']=='PASSED' else 1)
