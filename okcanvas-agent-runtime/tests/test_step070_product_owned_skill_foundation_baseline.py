from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.agent.skills import ProductSkillCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_step070_product_owned_skill_package_baseline() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    skill = ProductSkillCatalog(ROOT).resolve("document-review-v1")
    definition = AgentDefinitionCatalog(ROOT).resolve("skill-document-review-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert definition.skills == (skill.skill_id,)
    assert binding.skills[0]["package_sha256"] == skill.package_sha256
    assert binding.skill_runtime_sha256 is not None
