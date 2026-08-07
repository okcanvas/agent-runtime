from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.domain.attachments import LocalAttachmentPolicyCatalog, validate_local_attachment
from okcanvas_agent_runtime.domain.attachments.models import PreparedLocalAttachment
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import (
    LocalDocumentReviewResult,
    LocalDocumentReviewStatus,
)
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness
from okcanvas_agent_runtime.agent.skills import (
    ProductSkillCatalog,
    ProductSkillContractError,
    ProductSkillIntegrityError,
    compose_skill_instructions,
    resolve_effective_instructions,
)

ROOT = Path(__file__).resolve().parents[1]
ADMIN = "step070-admin-secret-value"
SUBMITTER = "step070-submitter-secret-value"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
SERVICE_TOKEN = "step070-service-client-token-123456"


def _pdf_bytes() -> bytes:
    return b"%PDF-1.7\n1 0 obj << /Type /Page >> endobj\n%%EOF\n"


def _registry() -> str:
    return json.dumps(
        {
            "schema_version": "okcanvas-service-client-token-registry-v1",
            "tokens": [
                {
                    "token_id": "step070-web",
                    "token_sha256": hashlib.sha256(SERVICE_TOKEN.encode("utf-8")).hexdigest(),
                    "tenant_id": "tenant-a",
                    "principal_id": "alice",
                    "roles": ["agent-user"],
                }
            ],
        },
        sort_keys=True,
    )


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def test_step070_runtime_flags_are_exact() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.product_owned_skill_foundation_implemented is True
    assert info.product_owned_skill_mode == "server-installed-immutable-instructions-and-static-resources"
    assert info.product_owned_skill_count == 1
    assert info.product_owned_skill_agent_binding_explicit is True
    assert info.product_owned_skill_runtime_binding_implemented is True
    assert info.product_owned_skill_service_catalog_implemented is True
    assert info.product_owned_skill_user_upload_enabled is False
    assert info.product_owned_skill_executable_code_enabled is False
    assert info.product_owned_skill_shell_enabled is False
    assert info.product_owned_skill_dynamic_dependency_install_enabled is False
    assert info.product_owned_skill_client_side_execution_enabled is False
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


def test_product_skill_catalog_resolves_exact_immutable_package() -> None:
    catalog = ProductSkillCatalog(ROOT)
    packages = catalog.list_packages()
    assert len(packages) == 1
    skill = packages[0]
    assert skill.skill_id == "document-review-v1"
    assert skill.version == "1.0.0"
    assert skill.execution_mode == "instructions-and-static-resources"
    assert skill.allowed_agent_ids == ("skill-document-review-agent",)
    assert skill.allowed_input_modes == ("local-attachment-v1",)
    assert skill.allowed_output_contracts == ("LocalDocumentReviewResult",)
    assert skill.required_tools == ()
    assert skill.required_mcp_servers == ()
    assert skill.required_hosted_tools == ()
    assert len(skill.resources) == 2
    assert len(skill.manifest_sha256) == 64
    assert len(skill.package_sha256) == 64


def test_skill_public_contract_contains_hashes_but_no_content() -> None:
    skill = ProductSkillCatalog(ROOT).resolve("document-review-v1")
    payload = skill.to_public_dict()
    serialized = json.dumps(payload, sort_keys=True)
    assert "Review checklist" not in serialized
    assert "Apply the bounded" not in serialized
    assert "supplied-local-attachment-only" not in serialized
    assert payload["executable_code_included"] is False
    assert payload["dynamic_dependency_installation"] is False
    assert payload["client_side_execution"] is False
    assert all(len(item["sha256"]) == 64 for item in payload["resources"])


def test_skill_instructions_are_composed_deterministically() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("skill-document-review-agent")
    skill = ProductSkillCatalog(ROOT).resolve("document-review-v1")
    effective = resolve_effective_instructions(definition)
    assert effective == compose_skill_instructions(definition.instructions, skill)
    assert definition.instructions in effective
    assert f'id="{skill.skill_id}"' in effective
    assert f'package_sha256="{skill.package_sha256}"' in effective
    assert '<RESOURCE path="resources/review-checklist.md"' in effective
    assert "external_lookup_allowed" in effective
    assert effective.endswith("</OKCANVAS_PRODUCT_SKILL>\n")


def test_agent_binding_requires_explicit_allowlist_and_does_not_add_permissions() -> None:
    catalog = ProductSkillCatalog(ROOT)
    skill = catalog.resolve("document-review-v1")
    with pytest.raises(ProductSkillContractError):
        catalog.validate_agent_binding(
            skill=skill,
            agent_id="local-document-review-agent",
            input_mode="local-attachment-v1",
            output_contract="LocalDocumentReviewResult",
            tools=(),
            mcp_servers=(),
            hosted_tools=(),
            workspace_access="none",
        )
    assert skill.required_tools == ()
    assert skill.required_mcp_servers == ()
    assert skill.required_hosted_tools == ()


def test_skill_bound_agent_and_runtime_binding_are_exact() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("skill-document-review-agent")
    assert definition.skills == ("document-review-v1",)
    assert len(definition.skill_capabilities) == 1
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.execution_path == "bounded-local-pdf-image-input-execution-v1"
    assert len(binding.skills) == 1
    assert binding.skills[0]["skill_id"] == "document-review-v1"
    assert binding.skills[0]["package_sha256"] == ProductSkillCatalog(ROOT).resolve("document-review-v1").package_sha256
    assert isinstance(binding.skill_runtime_sha256, str) and len(binding.skill_runtime_sha256) == 64
    assert binding.to_fingerprint_dict()["skills"] == [dict(binding.skills[0])]


def test_skill_package_rejects_undeclared_file(tmp_path: Path) -> None:
    target = tmp_path / "specs" / "skills" / "document-review-v1"
    import shutil

    shutil.copytree(ROOT / "specs" / "skills" / "document-review-v1", target)
    (target / "unexpected.py").write_text("print('forbidden')\n", encoding="utf-8")
    with pytest.raises(ProductSkillIntegrityError):
        ProductSkillCatalog(tmp_path).resolve("document-review-v1")


def test_skill_package_rejects_simulated_symbolic_resource(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "specs" / "skills" / "document-review-v1"
    import shutil

    shutil.copytree(ROOT / "specs" / "skills" / "document-review-v1", target)
    unsafe = (target / "resources" / "review-checklist.md").resolve()
    original = Path.is_symlink

    def fake_is_symlink(path: Path) -> bool:
        if path.resolve() == unsafe:
            return True
        return original(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
    with pytest.raises(ProductSkillIntegrityError):
        ProductSkillCatalog(tmp_path).resolve("document-review-v1")


def test_service_skill_catalog_and_agent_binding_are_public_metadata_only(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN,
        run_submitter_key=SUBMITTER,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_KEY,
        service_client_token_registry_json=_registry(),
    )
    with TestClient(app) as client:
        capabilities = client.get("/v1/service/capabilities", headers=_headers()).json()
        assert capabilities["skills_available"] is True
        assert capabilities["skill_catalog_api"] == "/v1/service/skills"
        assert capabilities["skill_foundation_step"] == "STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1"
        assert capabilities["next_skill_step"] is None
        assert capabilities["next_selected_step"] == "UNSELECTED_PENDING_USER_SELECTION"
        listed = client.get("/v1/service/skills", headers=_headers())
        assert listed.status_code == 200
        body = listed.json()
        assert body["total"] == 1
        assert body["skills"][0]["skill_id"] == "document-review-v1"
        detail = client.get("/v1/service/skills/document-review-v1", headers=_headers())
        assert detail.status_code == 200
        assert "Review checklist" not in detail.text
        agent = client.get(
            "/v1/service/agent-definitions/skill-document-review-agent", headers=_headers()
        ).json()
        assert agent["skills"] == ["document-review-v1"]
        assert agent["skill_capabilities"][0]["package_sha256"] == detail.json()["package_sha256"]
        assert agent["effective_instructions_sha256"] != agent["instructions_sha256"]


def test_service_skill_catalog_requires_bearer_authentication(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN,
        service_client_token_registry_json=_registry(),
    )
    with TestClient(app) as client:
        assert client.get("/v1/service/skills").status_code == 401
        assert client.get("/v1/service/skills/missing-skill", headers=_headers()).status_code == 404


def test_openai_gateway_uses_effective_skill_instructions(monkeypatch) -> None:
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
            assert session is None
            usage = SimpleNamespace(
                requests=1,
                input_tokens=7,
                output_tokens=3,
                total_tokens=10,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            )
            output = LocalDocumentReviewResult(
                status=LocalDocumentReviewStatus.REVIEWED,
                summary="Reviewed with Product Skill.",
                observations=[],
                unverified=[],
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
    fake_agents.gen_trace_id = lambda: "trace_step070_sdk"
    fake_agents.set_default_openai_key = lambda value: captured.setdefault("api_key", value)

    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")

    async def sink(event):
        captured["events"].append(event)

    data = _pdf_bytes()
    metadata = validate_local_attachment(
        data, "document.pdf", LocalAttachmentPolicyCatalog(ROOT).resolve()
    )
    definition = AgentDefinitionCatalog(ROOT).resolve("skill-document-review-agent")
    asyncio.run(
        OpenAIGenericAgentGateway().run(
            definition=definition,
            request="Review using the installed Skill.",
            run_id="run_step070_fixed",
            settings=RuntimeSettings(model="gpt-4.1", api_key="hidden-key"),
            lifecycle_sink=sink,
            attachment=PreparedLocalAttachment(metadata=metadata, data=data),
        )
    )
    instructions = captured["agent"]["instructions"]
    assert instructions == resolve_effective_instructions(definition)
    assert "<OKCANVAS_PRODUCT_SKILL" in instructions
    assert "Review checklist" in instructions
    assert captured["run_config"]["trace_metadata"]["skill_ids"] == ["document-review-v1"]
