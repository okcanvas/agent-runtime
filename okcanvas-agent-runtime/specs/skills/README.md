# Product-owned Skills

This directory contains immutable server-installed Skill packages. Each package must satisfy
`contracts/PRODUCT_OWNED_SKILL_PACKAGE_V1.md` and is resolved only through the product-owned closed
`ProductSkillCatalog`.

Current package:

- `document-review-v1` — bounded instructions and static resources for
  `skill-document-review-agent`.

These packages are declarative specifications, not Python packages. Do not add `__init__.py`,
executable code, dependencies, or client-side assets here.
