# STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING

## Identity

```text
version: 2.61.0
source baseline: STEP080A / 2.60.1
baseline ZIP SHA-256: 11a554e6a0fda3e728002ce915e9b3729622928919f30c5d30390814d2d29702
state: DETERMINISTIC_AND_FRESH_ZIP_VALIDATED_WINDOWS_LIVE_PENDING
```

## Goal

Replace the legacy `src/okcanvas_agent_runtime` flat package with explicit root packages and enforce the ratified Client ↔ Protocol/Transport ↔ Application ↔ Agent/Domain ↔ Adapter architecture without changing Product authority, security, event truth, model execution policy, or public Python import names.

## Executed physical structure

```text
okcanvas_agent_runtime/    server and Agent Runtime
okcanvas_agent_protocols/  transport-neutral REST/SSE contracts
okcanvas_agent_clients/    Product/development Python clients
clients/                   Node/Web/Desktop product clients
```

Runtime canonical zones:

```text
adapters/
agent/
application/
bootstrap/
compatibility/
core/
domain/
support/
transport/
verticals/
```

The legacy root is absent. Every one of the STEP080A source-root files is registered in the executed relocation manifest: 262 Python files and 10 non-Python resources, with zero missing relocations.

## Boundary work completed

- Client→Runtime and Protocol→Runtime imports removed.
- Transport direct Store/Coordinator/SQLite/storage access replaced by Application use cases and ports.
- persisted SSE uses `RunEventSubscription` instead of ProductStore polling.
- Admin and Service REST implementations physically separated.
- Bootstrap reduced to concrete composition and wiring.
- SQLite, OpenAI, MCP/Codex, encrypted storage, Sandbox and evidence implementations moved to Adapter ownership.
- Runtime binding and Agent execution contracts separated from concrete gateways.
- RuntimeInfo split into six feature groups while preserving 797-field order/default/flat API.
- 301 bounded compatibility aliases preserve historical import identity.
- WebSocket remains runtime-disabled with zero registered routes.

## Execution-sequencing decision

The user directed a consolidated restructuring followed by final cumulative validation rather than intermediate full suites. This is recorded in `docs/governance/STEP081_CONSOLIDATED_RESTRUCTURING_EXECUTION_OVERRIDE.md` and OR-ISSUE-036. It does not relax architecture boundaries and does not permit official promotion before Windows live validation.

## Deterministic closure

```text
Static architecture:       38/38 PASS
Canonical modules:              323
Compatibility aliases:          301
Missing internal imports:         0
Import cycles:                    0
Dependency violations:            0
RuntimeInfo fields:              797
Admin routes:                     48
Service routes:                   33
Other routes:                      5
Duplicate routes:                 0
WebSocket routes:                  0

Python regression:          900/900 PASS
Python test files:               226
Skipped/errors/timeouts:           0
Node tests:                  14/14 PASS
Reference integrity:          4/4 PASS
Direct reference imports:          0
Installation validation:     16/16 PASS
Fresh ZIP Python:           900/900 PASS
```

## Promotion boundary

The package remains a deterministic candidate until a fresh Windows extraction runs:

```cmd
sh_setup.cmd
sh_run_step081_acceptance.cmd
sh_run_step081_live_acceptance.cmd
```

The live contract requires 73/73 checks with real dependencies, configured `OPENAI_API_KEY`, and `OKCANVAS_AGENT_MODEL=gpt-4.1`.
