# STEP082B — Coding Execution Plane and Distribution Boundary Consolidation

## Identity

```text
STEP082B_CODING_EXECUTION_PLANE_AND_DISTRIBUTION_BOUNDARY_CONSOLIDATION
version 2.62.2
parent STEP081D / 2.61.4
```

## Why this STEP exists

STEP081D is Windows-live accepted 80/80. Before adding the Organization Assistant, the repository still exposed three different Coding execution planes and an implicit distribution contract:

1. `AgentRuntimeService` fixed `coding-agent` language-only compatibility runtime;
2. `GenericAgentExecutionService` catalog-driven Product Runtime;
3. Codex read/write/approval services exposed through development CLI paths.

The wheel also imports successfully without proving full application startup. Runtime startup additionally requires Product configuration under `specs` and immutable pinned Reference sources under `reference`.

## Binding decisions

### Product execution plane

`GenericAgentExecutionService` is the only Product Agent execution control plane. Product bootstrap and transport must import it and must not import `AgentRuntimeService` or any Codex service.

The legacy language runtime is classified `DEVELOPER_ONLY_COMPATIBILITY`. Codex read/write/approval runtimes are classified `DEVELOPER_ONLY_EXPERIMENTAL` until a later migration gives them catalog-owned Product Task/Run/Event/Artifact, approval and recovery contracts.

No fourth Coding execution plane may be added. Codex code is not removed before consumer inventory and migration evidence exist. Repository read and write remain separate; write requires approval.

### Distribution contract

The Product is split logically into:

- Runtime wheel: the three Python packages;
- Product Configuration Pack: `specs`;
- immutable Reference Pack: `reference`;
- Developer Source/Test Bundle: `scripts`, `tests`, `fixtures`;
- Historical Evidence Archive: `docs/evidence`.

Supported startup contracts are:

```text
full source bundle                               SUPPORTED
wheel only                                      UNSUPPORTED_MISSING_PRODUCT_CONFIGURATION
wheel + Product Configuration Pack              UNSUPPORTED_MISSING_IMMUTABLE_REFERENCE_PACK
wheel + Configuration Pack + Reference Pack     SUPPORTED
```

No file is deleted merely because it is old, generated, duplicated or has zero static imports.

## Code changes

- promote the real STEP081D Windows live 80/80 result into RuntimeInfo and compact non-secret evidence;
- add `specs/runtime/product-execution-plane-policy.json`;
- add `specs/distribution/product-artifact-boundaries.json`;
- add execution-plane and distribution validators;
- add deterministic Configuration/Reference packagers;
- register STEP082B deterministic Python and Windows acceptance launchers;
- record OR-ISSUE-054 through OR-ISSUE-056;
- preserve the STEP081D architecture source identity while validating the current STEP082B Product identity;
- keep architecture source movement blocked.

## Validation plan

1. focused STEP082B and architecture/launcher regression;
2. Product execution-plane validator;
3. actual wheel startup matrix with isolated install;
4. STEP081 architecture 40/40;
5. STEP082B integrated deterministic acceptance;
6. complete Python regression;
7. Node, Reference, npm pack, installation and Compliance gates;
8. immutable ZIP and fresh-extraction rerun;
9. Windows deterministic acceptance by the user.

No new model, Tool, MCP, Sandbox, Docker, Shell, Apply Patch, network, persistence or source-movement authority is added. A new live OpenAI run is not required because STEP082B changes metadata, policy gates and packaging boundaries, not live execution authority.

## Promotion rule

STEP081D remains the accepted rollback baseline until the exact Windows output of `sh_run_step082b_acceptance.cmd` passes. STEP082B must not be called Windows accepted before that output exists.

## Next selected STEP

```text
STEP083_ORGANIZATION_ASSISTANT_MAIN_AGENT_AND_ACTION_ROUTING_FOUNDATION
```

## Completed local evidence

All planned local and preliminary Fresh gates passed. The final Product promotion remains blocked only on the separate Windows deterministic rerun of `sh_run_step082b_acceptance.cmd`; no new live provider run is required.
