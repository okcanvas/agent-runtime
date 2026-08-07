from __future__ import annotations

from okcanvas_agent_runtime.agent.definitions.models import AgentDefinition

from okcanvas_agent_runtime.agent.skills.catalog import ProductSkillCatalog
from okcanvas_agent_runtime.agent.skills.models import ProductSkillPackage

_MAX_EFFECTIVE_INSTRUCTIONS_BYTES = 96_000


def compose_skill_instructions(base_instructions: str, skill: ProductSkillPackage) -> str:
    resource_blocks = []
    for resource in skill.resources:
        resource_blocks.append(
            "\n".join(
                (
                    f'<RESOURCE path="{resource.path}" media_type="{resource.media_type}" sha256="{resource.sha256}">',
                    resource.text.rstrip("\n"),
                    "</RESOURCE>",
                )
            )
        )
    skill_block = "\n".join(
        (
            f'<OKCANVAS_PRODUCT_SKILL id="{skill.skill_id}" version="{skill.version}" package_sha256="{skill.package_sha256}">',
            skill.instructions.rstrip("\n"),
            *resource_blocks,
            "</OKCANVAS_PRODUCT_SKILL>",
        )
    )
    effective = base_instructions.rstrip("\n") + "\n\n" + skill_block + "\n"
    if len(effective.encode("utf-8")) > _MAX_EFFECTIVE_INSTRUCTIONS_BYTES:
        raise ValueError("Effective Agent instructions exceed the Product Skill byte limit")
    return effective


def resolve_effective_instructions(definition: AgentDefinition) -> str:
    if not definition.skills:
        return definition.instructions
    project_root = definition.definition_path.parents[3]
    packages = ProductSkillCatalog(project_root).resolve_many(definition.skills)
    if len(packages) != 1:
        raise ValueError("Product Skill V1 requires exactly one resolved package when skills are declared")
    return compose_skill_instructions(definition.instructions, packages[0])
