from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog, execute_product_tool
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step060_runtime_baseline_is_exact() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.bounded_project_readonly_windows_live_accepted is True
    assert info.actual_sdk_function_tool_windows_live_accepted is True
    assert info.actual_sdk_tool_context_windows_live_accepted is True
    assert info.query_directed_project_retrieval_implemented is True
    assert info.query_directed_project_retrieval_line_window_scoring is True
    assert info.query_directed_project_retrieval_rare_term_weighting is True
    assert info.query_directed_project_retrieval_implementation_source_preferred is True
    assert info.query_directed_project_retrieval_unrelated_audit_suppressed is True
    assert info.query_directed_project_retrieval_max_evidence_files == 4
    assert info.query_directed_project_retrieval_max_evidence_characters == 5_000
    assert info.query_directed_project_retrieval_real_token_target == 5_000
    assert info.query_directed_project_retrieval_deterministic_accepted is True
    assert info.query_directed_project_retrieval_windows_live_accepted is True


def test_step060_agent_and_tool_versions_and_instructions_are_exact() -> None:
    agent = AgentDefinitionCatalog(ROOT).resolve("project-readonly-coding-agent")
    tool = FunctionToolRuntimeCatalog(ROOT).resolve("project_readonly_inspect")
    assert agent.version == "1.1.0"
    assert tool.runtime_version == "1.1.0"
    assert "Answer only the user's exact question" in agent.instructions
    assert "Prefer implementation source" in agent.instructions
    assert "no more than three findings" in agent.instructions
    assert tool.output_model.model_fields["evidence"].metadata
    schema = tool.output_model.model_json_schema()
    assert schema["properties"]["evidence"]["maxItems"] == 4
    assert schema["properties"]["inspected_files"]["maxItems"] == 4
    assert schema["properties"]["evidence_characters"]["maximum"] == 5_000
    assert schema["$defs"]["ProjectEvidenceOutput"]["properties"]["excerpt"]["maxLength"] == 1_600


def test_step060_real_repository_health_query_targets_exact_registration() -> None:
    runtime = FunctionToolRuntimeCatalog(ROOT).resolve("project_readonly_inspect")
    output = execute_product_tool(
        runtime,
        "Health API가 어디에서 등록되는지 파일과 라인 근거로 알려줘",
        workspace_root=ROOT,
    )
    assert output.inspected_files[0] == "okcanvas_agent_runtime/bootstrap/application.py"
    primary = output.evidence[0]
    assert '@app.get("/healthz")' in primary.excerpt
    assert "async def health" in primary.excerpt
    assert len(output.evidence) <= 4
    assert output.evidence_characters <= 5_000
    assert output.query_terms_considered == 2
    assert all(len(item.excerpt) <= 1_600 for item in output.evidence)
    assert all(item.line_end - item.line_start + 1 <= 16 for item in output.evidence)


def test_step060_docs_acceptance_and_windows_predecessor_evidence_exist() -> None:
    summary = json.loads(
        (ROOT / "docs/evidence/STEP059B_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["state"] == "PASSED"
    assert summary["real_openai_run"]["total_tokens"] == 8086
    assert summary["product_quality_observation"]["token_efficiency_accepted"] is False
    assert (ROOT / "docs/plans/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION.md").is_file()
    assert (ROOT / "docs/reference/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION_CODE_AUDIT.md").is_file()
    assert (ROOT / "scripts/run_step060_acceptance.py").is_file()
    assert (ROOT / "sh_run_step060_acceptance.cmd").is_file()
