from __future__ import annotations
import json
from dataclasses import fields
from pathlib import Path
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.step081_architecture import EXPECTED_RUNTIME_INFO_FIELDS
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane
ROOT=Path(__file__).resolve().parents[1]
STEP='STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL'
VERSION='2.77.0'

def test_step082b_identity_and_step081d_live_promotion_are_exact() -> None:
    info=RuntimeInfo()
    assert CURRENT_STEP==info.step==STEP
    assert PROJECT_VERSION==info.version==VERSION
    assert len(fields(RuntimeInfo))==EXPECTED_RUNTIME_INFO_FIELDS
    assert info.step081d_windows_live_accepted is True
    assert info.step081d_windows_live_passed_checks==80
    assert info.step081d_windows_live_total_checks==80
    assert info.windows_npm_pack_acceptance_portability_windows_live_accepted is True
    assert info.architecture_live_validator_process_isolation_windows_live_accepted is True
    assert info.architecture_step081d_windows_deterministic_accepted is True
    assert info.product_owned_capability_topology_windows_live_accepted is True
    assert info.architecture_constitution_windows_live_accepted is True
    assert info.next_selected_step=='UNSELECTED_PENDING_USER_SELECTION'

def test_step081d_real_windows_live_summary_is_nonsecret_and_complete() -> None:
    payload=json.loads((ROOT/'docs/evidence/STEP081D_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json').read_text())
    assert payload['state']==payload['outcome_classification']=='PASSED'
    assert payload['passed_checks']==payload['total_checks']==80
    assert payload['architecture']['passed_checks']==payload['architecture']['total_checks']==40
    assert payload['architecture']['admin_route_count']==48
    assert payload['architecture']['service_route_count']==33
    assert payload['architecture']['http_route_count']==86
    assert payload['model_calls']==2
    assert payload['tool_calls']==1
    assert payload['sandbox']['cleanup_state']=='COMPLETED'
    assert payload['sandbox']['orphan_count']==0
    assert payload['failure_diagnostics']['agent_failed']==[]
    assert payload['failure_diagnostics']['run_failed']==[]
    assert 'api_key' not in json.dumps(payload).casefold()

def test_generic_runtime_is_the_only_product_control_plane() -> None:
    result=validate_execution_plane()
    assert result['state']=='PASSED'
    assert result['passed_checks']==result['total_checks']==13
    assert result['product_control_plane']['plane_id']=='generic-agent-runtime'
    assert result['agent_definition_count']==32
    assert result['tool_definition_count']==4

def test_distribution_contract_requires_configuration_and_reference_packs() -> None:
    policy=json.loads((ROOT/'specs/distribution/product-artifact-boundaries.json').read_text())
    assert policy['startup_modes']=={
        'full_source_bundle':'SUPPORTED',
        'wheel_only':'UNSUPPORTED_MISSING_PRODUCT_CONFIGURATION',
        'wheel_plus_configuration_pack':'UNSUPPORTED_MISSING_IMMUTABLE_REFERENCE_PACK',
        'wheel_plus_configuration_and_reference_pack':'SUPPORTED',
    }
    info=RuntimeInfo()
    assert info.product_distribution_boundary_contract_implemented is True
    assert info.product_configuration_pack_contract_implemented is True
    assert info.product_reference_pack_contract_implemented is True
    assert info.wheel_only_full_app_startup_supported is False
    assert info.wheel_plus_configuration_pack_startup_supported is False
    assert info.wheel_plus_configuration_and_reference_pack_startup_supported is True
    assert info.full_source_bundle_startup_supported is True

def test_step082b_issue_records_and_packagers_are_present() -> None:
    for name in (
        'OR-ISSUE-054-STEP081D-WINDOWS-LIVE-PASS-NOT-PROMOTED-IN-PRODUCT-STATE.md',
        'OR-ISSUE-055-CODING-EXECUTION-CONTROL-PLANE-SPLIT.md',
        'OR-ISSUE-056-WHEEL-STARTUP-DEPENDS-ON-EXTERNAL-CONFIG-AND-REFERENCE-PACKS.md',
    ):
        assert (ROOT/'docs/issues'/name).is_file()
    assert (ROOT/'scripts/package_product_configuration_pack.py').is_file()
    assert (ROOT/'scripts/package_reference_pack.py').is_file()
    assert (ROOT/'scripts/validate_step082b_non_python.py').is_file()
    assert (ROOT/'scripts/validate_step082b_installation.py').is_file()
    assert (ROOT/'scripts/validate_step082b_windows_subprocess_portability.py').is_file()
    assert (ROOT/'scripts/build_step082b_fresh_validation_summary.py').is_file()
    assert (ROOT/'scripts/generate_step082b_compliance.py').is_file()
    assert (ROOT/'scripts/validate_step082b_compliance.py').is_file()

def test_step082b_python_regression_supports_external_fresh_log_directory(tmp_path: Path) -> None:
    from scripts.run_step082b_python_regression import _evidence_path

    external = tmp_path / "fresh-logs" / "chunk.txt"
    assert _evidence_path(external) == external.resolve().as_posix()
    internal = ROOT / "docs/evidence/step082b-local/python-regression/chunk.txt"
    assert _evidence_path(internal) == "docs/evidence/step082b-local/python-regression/chunk.txt"
