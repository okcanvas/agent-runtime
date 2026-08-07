from __future__ import annotations

from tests.artifact_test_support import artifact_service, read_json_artifact

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.domain.attachments import (
    AttachmentValidationError,
    LocalAttachmentPolicyCatalog,
    MultimodalModelPolicyCatalog,
    validate_local_attachment,
)
from okcanvas_agent_runtime.adapters.storage.attachments import EncryptedLocalAttachmentStore
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import (
    LocalDocumentObservation,
    LocalDocumentReviewResult,
    LocalDocumentReviewStatus,
    UsageSummary,
)
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService, GenericGatewayRunResult
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import ProtectedPayloadKey

ROOT = Path(__file__).resolve().parents[1]
ADMIN = "admin-secret-value"
SUBMITTER = "submitter-secret-value"
PAYLOAD_KEY = "11" * 32
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN, "X-OKCanvas-Run-Submitter-Key": SUBMITTER}


def pdf_bytes(pages: int = 1) -> bytes:
    body = b"\n".join(b"1 0 obj << /Type /Page >> endobj" for _ in range(pages))
    return b"%PDF-1.7\n" + body + b"\n%%EOF\n"


def png_bytes(width: int = 2, height: int = 3) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def jpeg_bytes(width: int = 2, height: int = 3) -> bytes:
    return (
        b"\xff\xd8"
        + b"\xff\xc0\x00\x0b\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x01\x01\x11\x00"
        + b"\xff\xd9"
    )


class AttachmentGateway:
    def __init__(self) -> None:
        self.attachment = None

    async def run(self, *, attachment=None, **_kwargs):
        self.attachment = attachment
        return GenericGatewayRunResult(
            output=LocalDocumentReviewResult(
                status=LocalDocumentReviewStatus.REVIEWED,
                summary="The bounded attachment was reviewed.",
                observations=[
                    LocalDocumentObservation(
                        title="Content available",
                        detail="Validated local input was available to the Agent.",
                    )
                ],
                unverified=[],
            ),
            usage=UsageSummary(input_tokens=10, output_tokens=5, total_tokens=15),
            trace_id="trace_step068",
            response_id=None,
            sdk_version="0.19.0",
        )


def test_policy_agent_and_runtime_binding_are_exact() -> None:
    policy = LocalAttachmentPolicyCatalog(ROOT).resolve()
    assert policy.max_attachments == 1
    assert policy.max_bytes == 8 * 1024 * 1024
    assert policy.allowed_media_types == ("application/pdf", "image/png", "image/jpeg")
    assert policy.max_pdf_pages == 50
    assert policy.remote_urls_allowed is False
    model_policy = MultimodalModelPolicyCatalog(ROOT).resolve()
    assert model_policy.allowed_model_ids == ("gpt-4.1",)
    definition = AgentDefinitionCatalog(ROOT).resolve("local-document-review-agent")
    assert definition.input_mode == "local-attachment-v1"
    assert definition.output_contract == "LocalDocumentReviewResult"
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.execution_path == "bounded-local-pdf-image-input-execution-v1"
    assert binding.attachment_policy["policy_sha256"] == policy.policy_sha256
    assert binding.multimodal_model_policy["policy_sha256"] == model_policy.policy_sha256


@pytest.mark.parametrize(
    ("data", "filename", "media_type", "kind"),
    [
        (pdf_bytes(), "document.pdf", "application/pdf", "input_file"),
        (png_bytes(), "image.png", "image/png", "input_image"),
        (jpeg_bytes(), "photo.jpg", "image/jpeg", "input_image"),
    ],
)
def test_signature_validation_accepts_only_bounded_supported_media(
    data: bytes, filename: str, media_type: str, kind: str
) -> None:
    metadata = validate_local_attachment(data, filename, LocalAttachmentPolicyCatalog(ROOT).resolve())
    assert metadata.media_type == media_type
    assert metadata.input_kind == kind
    assert metadata.byte_length == len(data)


def test_validation_rejects_spoofed_path_encrypted_and_over_page_pdf() -> None:
    policy = LocalAttachmentPolicyCatalog(ROOT).resolve()
    with pytest.raises(AttachmentValidationError):
        validate_local_attachment(pdf_bytes(), "spoof.png", policy)
    with pytest.raises(AttachmentValidationError):
        validate_local_attachment(pdf_bytes(), "../document.pdf", policy)
    with pytest.raises(AttachmentValidationError):
        validate_local_attachment(pdf_bytes() + b"/Encrypt 1 0 R", "secret.pdf", policy)
    with pytest.raises(AttachmentValidationError):
        validate_local_attachment(pdf_bytes(policy.max_pdf_pages + 1), "large.pdf", policy)


def test_encrypted_slot_binding_contains_no_plaintext_and_round_trips(tmp_path: Path) -> None:
    data = pdf_bytes()
    store = EncryptedLocalAttachmentStore(
        tmp_path / "attachments",
        ProtectedPayloadKey.from_text(PAYLOAD_KEY),
        LocalAttachmentPolicyCatalog(ROOT).resolve(),
    )
    slot = store.create_slot(data, "document.pdf")
    slot_path = tmp_path / "attachments" / "slots" / f"{slot.record_ref}.json"
    assert data not in slot_path.read_bytes()
    bound, binding = store.bind_slot(slot.record_ref, "submission_" + "a" * 32)
    assert not slot_path.exists()
    prepared = store.read_bound(binding, "submission_" + "a" * 32)
    assert prepared.data == data
    assert prepared.metadata.content_sha256 == binding.metadata.content_sha256
    store.delete(bound.record_ref)
    assert not (tmp_path / "attachments" / "bound" / f"{bound.record_ref}.json").exists()


def test_generic_execution_persists_only_attachment_evidence(tmp_path: Path) -> None:
    gateway = AttachmentGateway()
    product = SQLiteProductStore(tmp_path / "product.sqlite3")
    product.initialize()
    service = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=product,
        gateway=gateway,
        artifact_root=tmp_path / "artifacts",
        artifact_service=artifact_service(product, tmp_path / "artifacts"),
    )
    data = png_bytes()
    metadata = validate_local_attachment(data, "image.png", LocalAttachmentPolicyCatalog(ROOT).resolve())
    from okcanvas_agent_runtime.domain.attachments.models import PreparedLocalAttachment

    envelope = asyncio.run(
        service.run(
            agent_definition_id="local-document-review-agent",
            request="Describe only the supplied image.",
            settings=RuntimeSettings(model="gpt-4.1", api_key="secret"),
            live_opt_in=True,
            attachment=PreparedLocalAttachment(metadata=metadata, data=data),
        )
    )
    assert envelope.state == "SUCCEEDED"
    assert gateway.attachment is not None and gateway.attachment.data == data
    artifact_events = [
        item for item in product.list_events(envelope.run_id or "")
        if item.event_type == "artifact.created"
    ]
    assert {item.payload["artifact_type"] for item in artifact_events} == {
        "agent.final-output",
        "agent.local-attachment-evidence",
    }
    evidence_event = next(
        item for item in artifact_events
        if item.payload["artifact_type"] == "agent.local-attachment-evidence"
    )
    evidence = read_json_artifact(
        product, tmp_path / "artifacts", evidence_event.payload["artifact_id"]
    )
    assert evidence["content_sha256"] == metadata.content_sha256
    assert evidence["raw_bytes_persisted"] is False
    for path in (tmp_path / "artifacts").rglob("*"):
        if path.is_file():
            assert data not in path.read_bytes()


def test_control_api_upload_and_preflight_bind_one_attachment(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN,
        run_submitter_key=SUBMITTER,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key=PAYLOAD_KEY,
        direct_run_submission_enabled=False,
    )
    with TestClient(app) as client:
        uploaded = client.post(
            "/v1/local-attachments",
            headers={**HEADERS, "X-OKCanvas-Attachment-Filename": "document.pdf"},
            content=pdf_bytes(),
        )
        assert uploaded.status_code == 201, uploaded.text
        upload = uploaded.json()
        assert upload["state"] == "UPLOADED"
        assert upload["media_type"] == "application/pdf"
        preflight = client.post(
            "/v1/run-submissions/preflight",
            headers=HEADERS,
            json={
                "agent_definition_id": "local-document-review-agent",
                "input": "Summarize the supplied PDF.",
                "model": "gpt-4.1",
                "attachment_id": upload["attachment_id"],
                "idempotency_key": "step068-preflight-key-0001",
            },
        )
        assert preflight.status_code == 201, preflight.text
        body = preflight.json()
        assert body["executable_now"] is True
        assert body["protected_payload_persisted"] is True
        slot_path = tmp_path / "protected-attachments" / "slots" / f"{upload['attachment_id']}.json"
        assert not slot_path.exists()
        bound_files = list((tmp_path / "protected-attachments" / "bound").glob("attachment_*.json"))
        assert len(bound_files) == 1
        assert pdf_bytes() not in bound_files[0].read_bytes()


def test_text_only_agent_rejects_attachment_and_local_agent_requires_it(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN,
        run_submitter_key=SUBMITTER,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key=PAYLOAD_KEY,
    )
    with TestClient(app) as client:
        missing = client.post(
            "/v1/run-submissions/preflight",
            headers=HEADERS,
            json={
                "agent_definition_id": "local-document-review-agent",
                "input": "Review.",
                "model": "gpt-4.1",
                "idempotency_key": "step068-missing-file-0001",
            },
        )
        assert missing.status_code == 422
        uploaded = client.post(
            "/v1/local-attachments",
            headers={**HEADERS, "X-OKCanvas-Attachment-Filename": "image.png"},
            content=png_bytes(),
        ).json()
        wrong = client.post(
            "/v1/run-submissions/preflight",
            headers=HEADERS,
            json={
                "agent_definition_id": "coding-agent",
                "input": "Review.",
                "model": "gpt-4.1",
                "attachment_id": uploaded["attachment_id"],
                "idempotency_key": "step068-wrong-agent-0001",
            },
        )
        assert wrong.status_code == 422


def test_openai_gateway_builds_exact_pinned_sdk_multimodal_input(monkeypatch) -> None:
    import sys
    import types
    from types import SimpleNamespace

    from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
    from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
    from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness
    from okcanvas_agent_runtime.domain.attachments.models import PreparedLocalAttachment

    captured: dict[str, object] = {"events": []}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeRunHooks:
        pass

    class FakeModelSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class FakeRunner:
        @classmethod
        async def run(cls, agent, request, *, max_turns, hooks, run_config, error_handlers=None, session):
            captured["request"] = request
            captured["max_turns"] = max_turns
            assert session is None
            output = LocalDocumentReviewResult(
                status=LocalDocumentReviewStatus.REVIEWED,
                summary="Reviewed.",
                observations=[],
                unverified=[],
            )
            usage = SimpleNamespace(
                requests=1,
                input_tokens=7,
                output_tokens=3,
                total_tokens=10,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            )

            class Result:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = None
                new_items = []

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is LocalDocumentReviewResult
                    assert raise_if_incorrect_type is True
                    return output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.retry_policies = SimpleNamespace(never=lambda: (lambda _context: False))
    fake_agents.gen_trace_id = lambda: "trace_step068_sdk"
    fake_agents.set_default_openai_key = lambda value: captured.setdefault("api_key", value)

    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")

    async def sink(event):
        captured["events"].append(event)

    data = pdf_bytes()
    metadata = validate_local_attachment(data, "document.pdf", LocalAttachmentPolicyCatalog(ROOT).resolve())
    result = asyncio.run(
        OpenAIGenericAgentGateway().run(
            definition=AgentDefinitionCatalog(ROOT).resolve("local-document-review-agent"),
            request="Summarize the supplied PDF.",
            run_id="run_step068_fixed",
            settings=RuntimeSettings(model="gpt-4.1", api_key="hidden-key"),
            lifecycle_sink=sink,
            attachment=PreparedLocalAttachment(metadata=metadata, data=data),
        )
    )
    request = captured["request"]
    assert isinstance(request, list) and len(request) == 2
    media = request[0]["content"][0]
    assert media["type"] == "input_file"
    assert media["filename"] == "document.pdf"
    assert media["file_data"].startswith("data:application/pdf;base64,")
    assert request[1] == {"role": "user", "content": "Summarize the supplied PDF."}
    assert "hidden-key" not in json.dumps(request)
    assert result.usage.total_tokens == 10


def test_successful_governed_run_deletes_bound_attachment_with_payload(tmp_path: Path) -> None:
    import time

    gateway = AttachmentGateway()
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN,
        gateway=gateway,
        run_submitter_key=SUBMITTER,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key=PAYLOAD_KEY,
    )
    with TestClient(app) as client:
        upload = client.post(
            "/v1/local-attachments",
            headers={**HEADERS, "X-OKCanvas-Attachment-Filename": "document.pdf"},
            content=pdf_bytes(),
        ).json()
        submission = client.post(
            "/v1/run-submissions/preflight",
            headers=HEADERS,
            json={
                "agent_definition_id": "local-document-review-agent",
                "input": "Summarize the supplied PDF.",
                "model": "gpt-4.1",
                "attachment_id": upload["attachment_id"],
                "idempotency_key": "step068-cleanup-key-0001",
            },
        ).json()
        confirmed = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/confirm",
            headers=HEADERS,
            json={"confirmation": submission["confirmation_challenge"]},
        )
        assert confirmed.status_code == 202, confirmed.text
        run_id = confirmed.json()["run_id"]
        deadline = time.monotonic() + 5
        status_value = None
        while time.monotonic() < deadline:
            status_value = client.get(f"/v1/runs/{run_id}", headers={"X-OKCanvas-Admin-Key": ADMIN}).json()["status"]
            if status_value in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                break
            time.sleep(0.02)
        assert status_value == "SUCCEEDED"
        detail = client.get(
            f"/v1/run-submissions/{submission['submission_id']}",
            headers={"X-OKCanvas-Admin-Key": ADMIN},
        ).json()
        assert detail["payload_retention_state"] == "DELETED"
    assert not list((tmp_path / "payloads").glob("payload_*.json"))
    assert not list((tmp_path / "protected-attachments" / "bound").glob("attachment_*.json"))
