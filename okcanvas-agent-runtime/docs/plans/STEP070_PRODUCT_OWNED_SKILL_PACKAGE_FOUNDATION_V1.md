# STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1

## Baseline

- predecessor: STEP069 / 2.49.0 / Windows live accepted 31/31;
- implementation version: 2.50.0;
- Runtime remains a multi-user server;
- current TUI and `clients/okcanvas-agent-cli` remain development/acceptance harnesses.

## Problem confirmed by code audit

Agent definitions could declare Tool, MCP, Hosted Tool, child Agent, Guardrail, Session and input
mode, but there was no Product-owned Skill namespace, immutable Skill manifest, Skill Runtime
binding, instruction composition, or service catalog. Adding Skill behavior only in prompts would
leave package contents outside the confirmation-bound Runtime fingerprint.

## Selected scope

1. add `specs/skills/<skill-id>` immutable packages;
2. add a closed Product Skill catalog with exact file inventory and SHA-256 identities;
3. permit at most one explicit Skill ID per Agent definition;
4. prove that Skills require but never add Agent capabilities;
5. compose base instructions and static resources deterministically at SDK Agent construction;
6. bind package identity and Skill Runtime implementation into the Agent Runtime binding;
7. expose read-only metadata through `/v1/service/skills`;
8. add one `document-review-v1` package and one explicit Skill-enabled document Agent.

## Excluded

- user or tenant uploads;
- executable Skill code;
- Shell, arbitrary filesystem access, or dependency installation;
- marketplace or remote installation;
- model-selected Skill discovery;
- multiple Skills per Agent;
- client-side Skill execution;
- Skill-specific mutable database state;
- final `agent-cli`, `agent-web`, or `agent-desktop` implementation.

## Acceptance

`sh_run_step070_acceptance.cmd` must verify the predecessor Windows closure, package inventory,
capability non-expansion, effective instructions, Runtime binding, service API, historical service
and attachment behavior, compileall, Node release integrity, Reference integrity, and no direct
Reference imports. Deterministic acceptance performs zero network and model calls.

No STEP071 is selected by this implementation. The next scope requires a fresh audit of the
STEP070 Windows-live ZIP.
