from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STEP='STEP094R1_UNIFIED_CROSS_DOMAIN_SESSION_ROOT_AND_BINDING_CLOSURE'
VERSION='2.78.1'

def validate() -> dict[str, object]:
    baseline=(ROOT/'okcanvas_agent_runtime/core/baseline.py').read_text(encoding='utf-8')
    pyproject=(ROOT/'pyproject.toml').read_text(encoding='utf-8')
    definition=json.loads((ROOT/'specs/agents/organization-assistant-session-agent/definition.json').read_text(encoding='utf-8'))
    policy=json.loads((ROOT/'specs/assistant/cross-domain-session-delegation-policy.json').read_text(encoding='utf-8'))
    read_policy=json.loads((ROOT/'specs/organization-context/read-policy.json').read_text(encoding='utf-8'))
    gateway=(ROOT/'okcanvas_agent_runtime/adapters/openai/generic_gateway.py').read_text(encoding='utf-8')
    cross_session=(ROOT/'okcanvas_agent_runtime/application/assistant_routing/cross_domain_session.py').read_text(encoding='utf-8')
    binding=(ROOT/'okcanvas_agent_runtime/bootstrap/runtime_binding.py').read_text(encoding='utf-8')
    session=(ROOT/'okcanvas_agent_runtime/adapters/persistence/sessions/runtime_service.py').read_text(encoding='utf-8')
    definitions=(ROOT/'okcanvas_agent_runtime/agent/definitions/catalog.py').read_text(encoding='utf-8')
    service=(ROOT/'okcanvas_agent_runtime/application/service/use_cases.py').read_text(encoding='utf-8')
    admin=(ROOT/'okcanvas_agent_runtime/application/admin/use_cases.py').read_text(encoding='utf-8')
    checks={
      'identity_exact': f'CURRENT_STEP = "{STEP}"' in baseline and f'PROJECT_VERSION = "{VERSION}"' in baseline and f'version = "{VERSION}"' in pyproject,
      'unified_root_exact_two_children': definition.get('agent_tools')==['groupware-read-agent','organization-context-read-agent'] and definition.get('version')=='1.2.0',
      'cross_domain_policy_exact': policy.get('policy_id')=='organization-assistant-cross-domain-read-session-v1' and [x.get('domain') for x in policy.get('targets',[])]==['GROUPWARE','ORGANIZATION_CONTEXT'],
      'organization_read_current_root_unified': read_policy.get('root_agent_id')=='organization-assistant-session-agent',
      'definition_catalog_explicit_cross_domain_mode': 'session_cross_domain_agent_tool_mode' in definitions and 'organization-context-read-agent' in definitions,
      'session_store_explicit_cross_domain_mode': 'session_cross_domain_agent_tool_mode' in session and 'organization-context-read-agent' in session,
      'gateway_selects_one_child_from_immutable_context': 'CrossDomainSessionDelegationCatalog' in gateway and 'target_for_request(request)' in gateway and 'Exactly one delegated read domain is required per Turn' in cross_session,
      'runtime_binding_includes_both_child_mcp_owners': all(x in binding for x in ('sqlite-session-bounded-cross-domain-read-subagent-execution-v1','cross_domain_session_binding.targets','owner_agent_id')),
      'service_route_session_binding_fence': 'ASSISTANT_SESSION_BINDING_MISMATCH' in service and 'decision.selected_agent_id != session_record.agent_definition_id' in service,
      'admin_route_session_binding_fence': 'ASSISTANT_SESSION_BINDING_MISMATCH' in admin and 'decision.selected_agent_id != session_record.agent_definition_id' in admin,
      'no_display_name_fallback': 'display-name fallback' not in gateway.lower() and 'label/name fallback' in (ROOT/'specs/agents/organization-assistant-session-agent/instructions.md').read_text(encoding='utf-8'),
      'current_acceptance_source_present': (ROOT/'scripts/run_step094r1_acceptance.py').is_file() and (ROOT/'sh_run_step094r1_acceptance.cmd').is_file(),
    }
    return {'state':'PASSED' if all(checks.values()) else 'FAILED','checks':checks,'passed_checks':sum(v is True for v in checks.values()),'total_checks':len(checks),'step':STEP,'version':VERSION}

if __name__=='__main__': print(json.dumps(validate(),ensure_ascii=False,indent=2))
