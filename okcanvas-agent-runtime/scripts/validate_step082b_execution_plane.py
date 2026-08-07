from __future__ import annotations
import json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
POLICY=ROOT/'specs/runtime/product-execution-plane-policy.json'
STEP='STEP082B_CODING_EXECUTION_PLANE_AND_DISTRIBUTION_BOUNDARY_CONSOLIDATION'
VERSION='2.62.2'

def _source(paths):
    return '\n'.join(p.read_text(encoding='utf-8') for p in paths)

def validate():
    policy=json.loads(POLICY.read_text(encoding='utf-8'))
    application=ROOT/'okcanvas_agent_runtime/bootstrap/application.py'
    transport=list((ROOT/'okcanvas_agent_runtime/transport').rglob('*.py'))
    product_source=_source([application,*transport])
    dev_cli=(ROOT/'okcanvas_agent_runtime/bootstrap/development_cli/main.py').read_text(encoding='utf-8')
    required=policy['product_import_rules']['required_symbol']
    forbidden=policy['product_import_rules']['forbidden_symbols']
    agent_defs=list((ROOT/'specs/agents').glob('*/definition.json'))
    tool_defs=list((ROOT/'specs/tools').glob('*/definition.json'))
    codex_agent_dirs=sorted((ROOT/'specs/agents').glob('codex-*'))
    codex_tool_dirs=sorted((ROOT/'specs/tools').glob('codex*'))
    checks={
      'step082b_policy_retained_in_current_product':CURRENT_STEP.startswith('STEP') and tuple(int(x) for x in PROJECT_VERSION.split('.')) >= (2,62,2),
      'policy_schema_exact':policy.get('schema_version')=='okcanvas-product-execution-plane-policy-v1',
      'generic_runtime_required_in_product_bootstrap':required in application.read_text(encoding='utf-8'),
      'forbidden_developer_services_absent_from_product_transport':all(name not in product_source for name in forbidden),
      'developer_cli_retains_legacy_and_codex_services':all(name in dev_cli for name in forbidden),
      'generic_agent_catalog_count_retained':len(agent_defs)>=27,
      'generic_function_tool_catalog_count_retained':len(tool_defs)==4,
      'codex_agent_specs_not_silently_catalog_registered':all(not (d/'definition.json').exists() for d in codex_agent_dirs),
      'codex_tool_specs_not_silently_catalog_registered':all(not (d/'definition.json').exists() for d in codex_tool_dirs),
      'new_execution_plane_forbidden':policy['coding_capability_rules']['new_execution_plane_allowed'] is False,
      'repository_read_write_separated':policy['coding_capability_rules']['repository_read_write_separated'] is True,
      'write_approval_required':policy['coding_capability_rules']['write_requires_approval'] is True,
      'codex_removal_blocked_before_migration':policy['coding_capability_rules']['codex_removal_allowed_before_migration'] is False,
    }
    return {'schema_version':'okcanvas-step082b-execution-plane-validation-v1','step':STEP,'version':VERSION,'state':'PASSED' if all(checks.values()) else 'FAILED','checks':checks,'passed_checks':sum(checks.values()),'total_checks':len(checks),'product_control_plane':policy['product_control_plane'],'developer_only_planes':policy['developer_only_planes'],'agent_definition_count':len(agent_defs),'tool_definition_count':len(tool_defs)}
if __name__=='__main__':
    result=validate(); print(json.dumps(result,indent=2,sort_keys=True)); raise SystemExit(0 if result['state']=='PASSED' else 1)
