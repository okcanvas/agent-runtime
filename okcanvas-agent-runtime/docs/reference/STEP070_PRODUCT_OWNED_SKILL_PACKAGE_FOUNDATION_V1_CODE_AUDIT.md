# STEP070 code audit

## Audited baseline

`okcanvas-agent-runtime-step069-multi-user-service-client-contract-foundation-v1.zip`, reported
Windows live accepted 31/31.

## Confirmed pre-STEP070 state

- `AgentDefinition` had no `skills` field;
- `specs/skills` and a Skill catalog did not exist;
- OpenAI SDK Agents received `definition.instructions` directly;
- Runtime binding had no Skill package or composition implementation identity;
- `/v1/service/capabilities` reported `skills_available=false`;
- no service Skill list/detail API existed.

## Upstream reference finding

The pinned SDK examples include Shell/Sandbox Skill references such as
`examples/tools/local_shell_skill.py` and `examples/tools/container_shell_skill_reference.py`.
Those examples couple Skills to Shell or container execution and are outside the MVP server safety
boundary. STEP070 therefore adapts only the reusable package concept and does not adopt executable
Shell/Sandbox behavior.

## Implemented product boundary

`ProductSkillCatalog` validates one exact declarative package inventory. The package may contain
`skill.json`, `instructions.md`, and 1..8 declared UTF-8 resources under `resources/`. Instructions
are bounded to 32,000 bytes, each resource to 32,000 bytes, and all resources together to 64,000
bytes. Only Markdown, plain text, and JSON resources are accepted.

An Agent may declare at most one Skill. The manifest allowlists Agent IDs, input modes, output
contracts and required Tool/MCP/Hosted Tool identities. Required identities must already exist in the
Agent definition; the Skill never changes the Agent capability graph.

The Runtime composes one deterministic `<OKCANVAS_PRODUCT_SKILL>` block at SDK Agent construction.
The exact package metadata and the Skill catalog/runtime implementation SHA are included in the
Runtime binding. Service responses omit instruction and resource content.

## First package

`document-review-v1` is bound only to `skill-document-review-agent`. It uses the already accepted
single encrypted local PDF/PNG/JPEG ingress and the existing strict `LocalDocumentReviewResult`.
It declares no Tool, MCP, Hosted Tool, Session, child Agent, workspace, Shell, network, or code
capability.

## Deliberate exclusions

No user upload, remote installation, marketplace, arbitrary code, Shell, dependency install,
client-side execution, mutable Skill state, or model-selected Skill discovery was introduced.
