from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step068_runtime_flags_and_baseline_are_exact() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.hosted_web_search_windows_live_accepted is True
    assert info.bounded_local_pdf_image_input_implemented is True
    assert info.bounded_local_attachment_count == 1
    assert info.bounded_local_attachment_max_bytes == 8388608
    assert info.bounded_local_attachment_media_types == "application/pdf,image/png,image/jpeg"
    assert info.bounded_local_attachment_max_pdf_pages == 50
    assert info.bounded_local_attachment_remote_urls_enabled is False
    assert info.bounded_local_attachment_provider_file_ids_enabled is False
    assert info.bounded_local_attachment_raw_bytes_in_events is False
    assert info.bounded_local_attachment_raw_bytes_in_artifacts is False
    assert info.bounded_local_attachment_encrypted_store_implemented is True
    assert info.bounded_local_attachment_allowed_model_ids == "gpt-4.1"
    assert info.bounded_local_attachment_deterministic_accepted is True
    assert info.bounded_local_attachment_windows_live_accepted is True
    assert info.bounded_local_attachment_live_provider_accepted is False


def test_step068_agent_and_binding_are_isolated() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("local-document-review-agent")
    assert definition.input_mode == "local-attachment-v1"
    assert definition.session_mode == "disabled"
    assert not definition.tools
    assert not definition.mcp_servers
    assert not definition.hosted_tools
    assert not definition.handoffs
    assert not definition.agent_tools
    assert not definition.orchestration_children
    assert not definition.guardrails
    assert definition.workspace_access == "none"
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.execution_path == "bounded-local-pdf-image-input-execution-v1"
    assert binding.attachment_policy["max_attachments"] == 1
    assert binding.multimodal_model_policy["allowed_model_ids"] == ["gpt-4.1"]
    assert len(binding.attachment_runtime_sha256) == 64


def test_step068_does_not_implement_file_search_or_provider_files() -> None:
    product_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "okcanvas_agent_runtime").rglob("*.py"))
    )
    assert "FileSearchTool" not in product_source
    assert "vector_store_ids" not in product_source
    assert "provider_file_id" in product_source
