from __future__ import annotations


class ProductSkillError(RuntimeError):
    """Base error for Product-owned Skill packages."""


class ProductSkillNotFoundError(ProductSkillError):
    pass


class ProductSkillContractError(ProductSkillError):
    pass


class ProductSkillIntegrityError(ProductSkillError):
    pass
