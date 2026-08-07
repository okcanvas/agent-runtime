# STEP081 candidate audit — Project structure full inventory and migration constitution

## Status

```text
Source package: STEP080_PRODUCT_OWNED_CAPABILITY_TOPOLOGY_AND_TOOL_DISCOVERY_FOUNDATION
Source version: 2.60.0
Audit state: COMPLETED_CODE_DERIVED
Product source modified: NO
STEP081 selected: NO
Gate: STEP080_WINDOWS_LIVE_ACCEPTANCE_REQUIRED
```

This document is a code-derived structural audit of the packaged STEP080 ZIP. It does not claim a new product baseline and does not move source files before STEP080 Windows live acceptance.

## Constitution applied

- No conclusions were drawn from directory names alone.
- All Python files under `src/okcanvas_agent_runtime` were parsed with `ast`.
- Internal imports were resolved into a module and top-level package graph.
- Root launchers, acceptance scripts, tests, specs, documents and immutable reference files were counted from the extracted ZIP.
- The current `ROADMAP.md` gate was respected: `UNSELECTED_PENDING_STEP080_WINDOWS_LIVE_ACCEPTANCE`.

## Exact repository inventory

```text
Top-level Python modules/packages under okcanvas_agent_runtime: 64
Python modules parsed: 258
Python parse failures: 0
Internal module cycles: 0

Source files: 266
Tests: 220 files
Scripts: 138 files
STEP acceptance Python scripts: 123
Root Windows .cmd launchers: 126
Specs: 272 files
Docs: 575 files
  plans: 118
  evidence: 317
  reference audits: 66
  decisions: 12
  issues: 15
Reference files: 1,540
```

The absence of import cycles is important: the repository is structurally crowded but is not currently dependency-cyclic. A compatibility-facade migration is feasible.

## Confirmed structural findings

### F-01 — Flat source namespace has exceeded a maintainable top-level size

`src/okcanvas_agent_runtime/` currently exposes 64 first-level modules/packages. The names mix architectural layers, implementation adapters and historical feature slices:

```text
agent_definitions / agents
function_tools / agent_tools / tools / tool_approval
mcp_clients / mcp_definitions / mcp_servers
execution / runtime / orchestration
product / run_submission / invocations
control_api / service_clients / approval_operator / operations_console / tui_client
attachments / project_snapshots / protected_payload
```

A developer cannot determine from the first-level path whether a module is a domain model, application service, SDK adapter, infrastructure adapter or user-facing interface.

**Decision:** Introduce canonical zones: `core`, `capabilities`, `domain`, `application`, `infrastructure`, `interfaces`, `support`, and `verticals`.

### F-02 — Similar names represent different contracts

The following clusters are code-confirmed distinct but visually ambiguous:

| Cluster | Current responsibilities |
|---|---|
| `tools` | Empty placeholder package |
| `function_tools` | Product Function Tool definitions, catalog and SDK factories |
| `agent_tools` | Agent-as-Tool policy/runtime |
| `tool_approval` | Durable native Tool approval lifecycle |
| `agents` | Concrete SDK Agent declarations |
| `agent_definitions` | Immutable Product Agent definition catalog |
| `mcp_clients` | Installed-SDK MCP construction |
| `mcp_definitions` | Product-owned MCP catalog and policy |
| `mcp_servers` | Product reference MCP server implementation |
| `runtime` | Codex/OpenAI gateway adapters and legacy execution services |
| `execution` | Generic governed execution application and OpenAI gateway |

**Decision:** Consolidate these under explicit subtrees rather than continuing to add sibling packages.

### F-03 — RuntimeInfo is a monolithic feature ledger

`src/okcanvas_agent_runtime/model.py` contains one `RuntimeInfo` dataclass with **786 annotated fields** in approximately 800 lines.

This file mixes:

- SDK and model identity;
- every accepted STEP feature flag;
- Tool, MCP, Skill and Sandbox policy summaries;
- Service API and ownership state;
- Windows acceptance flags;
- capability topology identities.

It is highly imported: `okcanvas_agent_runtime.model` appears in 132 test/script/client files.

**Decision:** Split implementation into immutable feature-group records and an assembler under `core/runtime_info/`, while retaining `okcanvas_agent_runtime.model` as a compatibility facade until a major-version removal gate.

### F-04 — Several modules exceed a safe responsibility size

Confirmed largest modules:

```text
control_api/app.py                  1,717 LOC, 51 HTTP routes
execution/openai_gateway.py        1,632 LOC
run_submission/store.py            1,617 LOC
execution/service.py               1,571 LOC
cli.py                             1,135 LOC
execution/runtime_binding.py       1,128 LOC
persistence/sqlite_store.py        1,053 LOC
service_clients/routes.py            851 LOC
sessions/service.py                  816 LOC
model.py                             800 LOC, 786 fields
control_api/contracts.py             798 LOC, 67 classes
```

**Decision:** Moving these files without responsibility decomposition would only relocate the problem. Split by route/resource, transaction aggregate, adapter family and feature-group contract before or during migration.

### F-05 — Root launcher and acceptance history dominate the repository surface

```text
Root Windows launchers: 126
scripts/run_step*.py: 123
Distinct referenced root STEP launchers: 110
Distinct referenced STEP script paths: 93
```

These files are valuable historical acceptance evidence, but they obscure the current operational entrypoints.

**Decision:** Future canonical implementations should live below:

```text
launchers/windows/current/
scripts/acceptance/current/
scripts/acceptance/history/<step>/
```

Existing root `.cmd` names must remain compatibility wrappers because they are referenced throughout documents and are the user-facing Windows contract.

### F-06 — Tests are fully flat

All 220 Python test files live directly under `tests/`. The names mix unit, integration, static contract, Windows launcher, historical baseline and live-harness tests.

**Decision:** Introduce a test inventory first, then migrate to:

```text
tests/unit/
tests/integration/
tests/contract/
tests/acceptance/current/
tests/regression/history/
tests/windows/
```

Do not move tests until scripts that pass exact file paths consume a generated manifest rather than hard-coded paths.

### F-07 — Empty placeholders create false architecture

Confirmed empty Python boundary packages:

```text
src/okcanvas_agent_runtime/api/
src/okcanvas_agent_runtime/policy/
src/okcanvas_agent_runtime/tools/
```

They contain only a deferred-boundary docstring and have no implementation imports.

**Decision:** Remove them in the first migration wave or replace them with real compatibility facades. Empty aspirational packages must not remain beside active packages.

### F-08 — Business-specific limits leak into the generic package root

`replenishment_limits.py` is a store-replenishment contract but resides beside generic `config.py`, `contracts.py` and `baseline.py`. `contracts.py` imports it directly.

**Decision:** Move replenishment contracts and limits to `verticals/store_replenishment/`. Generic output contracts must not depend on a vertical limit module; the vertical result contract should own that validator.

### F-09 — Interface assets are mixed into the Runtime package

Interactive Runner and Operations Console static assets are packaged inside Python implementation directories. This is valid for wheel resource loading, but they are not visibly grouped as interfaces.

**Decision:** Move them under `interfaces/web/<surface>/assets` while preserving package-resource loading and route paths.

### F-10 — Specs and historical documents are large but intentionally authoritative

`specs/agents`, `specs/mcp` and `specs/tools` are explicitly protected by `AGENTS.md`. `reference/upstream` is immutable. Existing Handoff and issue documents use exact paths extensively.

**Decision:** Do **not** mass-move these areas during source restructuring:

```text
reference/upstream/**
specs/agents/**
specs/mcp/**
specs/tools/**
docs/plans/**
docs/evidence/**
docs/issues/**
docs/reference/**
```

Add indexes/manifests instead. Any later path change requires a constitution amendment and compatibility mapping.

## Dependency hotspots

Top packages by code size and import fan-out:

| Current package | Files | LOC | Incoming imports | Outgoing imports |
|---|---:|---:|---:|---:|
| `execution` | 9 | 5,038 | 22 | 81 |
| `run_submission` | 8 | 3,428 | 7 | 31 |
| `control_api` | 8 | 2,964 | 7 | 41 |
| `runtime` | 12 | 2,606 | 15 | 54 |
| `sessions` | 14 | 2,366 | 8 | 4 |
| `sandbox_runtime` | 7 | 1,974 | 4 | 3 |
| `tool_approval` | 8 | 1,813 | 4 | 28 |
| `evaluation` | 5 | 1,449 | 5 | 9 |
| `service_clients` | 6 | 1,419 | 2 | 24 |

`execution` is the dominant application hub. It must be decomposed before enforcing strict layer direction.

## Public import compatibility risk

Most referenced current imports include:

```text
okcanvas_agent_runtime.agent_definitions   139 files
okcanvas_agent_runtime.model               132 files
okcanvas_agent_runtime.reference_catalog   112 files
okcanvas_agent_runtime.contracts           103 files
okcanvas_agent_runtime.execution            80+ files
okcanvas_agent_runtime.control_api           89 files
okcanvas_agent_runtime.acceptance            75 files
okcanvas_agent_runtime.config                70 files
```

**Decision:** No direct delete-and-move migration. Every widely imported path requires:

1. canonical implementation at the new path;
2. old-path compatibility re-export;
3. an import-equivalence test;
4. deprecation inventory;
5. removal only at a declared major-version boundary.

## Proposed canonical source tree

```text
src/okcanvas_agent_runtime/
├─ core/
│  ├─ baseline.py
│  ├─ config.py
│  ├─ contracts/
│  ├─ errors.py
│  └─ runtime_info/
├─ capabilities/
│  ├─ topology/
│  ├─ agents/
│  │  ├─ definitions/
│  │  └─ sdk/
│  ├─ tools/
│  │  ├─ function/
│  │  ├─ codex/
│  │  └─ hosted_search/
│  ├─ skills/
│  ├─ subagents/
│  │  ├─ handoffs/
│  │  └─ agent_tools/
│  ├─ mcp/
│  │  ├─ definitions/
│  │  ├─ clients/
│  │  └─ servers/
│  ├─ guardrails/
│  └─ model/
│     ├─ routing/
│     ├─ retry/
│     ├─ provider_identity/
│     ├─ reasoning_evidence/
│     ├─ response_storage/
│     └─ trace_export/
├─ domain/
│  ├─ runs/
│  ├─ invocations/
│  ├─ sessions/
│  ├─ attachments/
│  ├─ project_snapshots/
│  ├─ protected_payload/
│  ├─ tool_approvals/
│  └─ evaluations/
├─ application/
│  ├─ submissions/
│  ├─ execution/
│  └─ orchestration/
├─ infrastructure/
│  ├─ openai_runtime/
│  ├─ persistence/
│  ├─ sandbox/
│  ├─ workspace/
│  ├─ evidence/
│  ├─ streaming/
│  └─ reference_catalog/
├─ interfaces/
│  ├─ control_api/
│  ├─ service_api/
│  ├─ cli/
│  ├─ tui/
│  ├─ operator/
│  └─ web/
├─ support/
│  ├─ acceptance/
│  ├─ validation/
│  └─ scenarios/
└─ verticals/
   ├─ store_replenishment/
   └─ commerce_snapshot_ingress/
```

This is a migration target, not an active import path in STEP080.

## Exact migration-map coverage

The accompanying `STEP081_PROJECT_LAYOUT_MIGRATION_MAP.json` covers all 64 current first-level source entries. It records current files/LOC/fan-in/fan-out, target zone/path and migration wave. Map SHA-256:

```text
1d2ae78fc2dcaadd1c13f70cdec41d099357f962f8660d85e8ed15d9186f452c
```

## Migration waves

### Wave 0 — Gate and freeze

Required first:

```text
STEP080 Windows live: 62/62 PASS
```

Then add a machine-enforced layout manifest that rejects any new unclassified first-level package, root launcher or acceptance-script family.

### Wave 1 — Low-risk repository support layout

- Remove the three empty placeholder packages.
- Move vertical business code and replenishment limits under `verticals/` with compatibility imports.
- Group placeholder service clients under `apps/`.
- Add canonical launcher and acceptance indexes while retaining root wrappers.
- Add test and documentation inventories; do not mass-move historical evidence.

### Wave 2 — Capability and core consolidation

- Split `RuntimeInfo` into feature-group records and assembler.
- Consolidate Agent definitions/declarations.
- Consolidate Function Tool, Agent-as-Tool, Handoff, MCP, Skill, Guardrail and model-policy packages.
- Move root Codex contracts/errors under the Codex Tool capability.
- Retain old import facades and prove symbol identity.

### Wave 3 — Domain/application/infrastructure split

- Separate submission application workflow from stores.
- Separate Product Task/Run domain records from SQLite persistence.
- Move OpenAI/Codex adapters into infrastructure.
- Split `execution` and `runtime` by ports/adapters.
- Move API surfaces under interfaces.

This is the highest-risk wave and requires transaction, Runtime-binding and Windows live revalidation after each bounded sub-wave.

### Wave 4 — Remove compatibility paths

Only at an explicit major-version boundary after:

- no internal import uses an old path;
- no scripts/tests use an old path;
- ZIP Handoff lists deprecated paths;
- external client compatibility policy is declared.

## Required automated gates for the restructuring STEP

A future implementation STEP should add:

```text
project layout manifest completeness
no unclassified first-level source package
no new root launcher without registry entry
no new run_step script without registry entry
AST import graph parse success
module cycle count remains zero
compatibility facade symbol identity
old/new Runtime binding SHA equality where behavior is unchanged
spec path integrity
reference integrity
deterministic full regression
Windows live acceptance
fresh ZIP layout and hash verification
```

## Final audit judgment

```text
Project structure realignment required: YES
Emergency rewrite required: NO
Current dependency cycles: 0
Safe one-shot mass move: NO
Safe phased migration with compatibility facades: YES
First implementation prerequisite: STEP080 Windows live 62/62
Recommended next STEP after that gate:
STEP081_PROJECT_LAYOUT_CONSTITUTION_AND_COMPATIBILITY_MIGRATION_FOUNDATION
```

The first implementation STEP should establish the manifest, compatibility import mechanism and low-risk Wave 1 changes. It should not simultaneously move the execution, submission, persistence and API hubs.
