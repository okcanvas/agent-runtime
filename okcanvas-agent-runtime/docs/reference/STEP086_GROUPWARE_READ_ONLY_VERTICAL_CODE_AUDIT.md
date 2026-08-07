# STEP086 Code Audit — Groupware Read-only Vertical

## Parent evidence

The exact user-provided Windows log parses as STEP085 `PASSED`, 12/12, version 2.65.0. Nested
Architecture 40/40, Multi-MCP 22/22, execution plane 13/13, distribution 14/14, and retained
Organization Context 18/18 are all passed. The distribution probe states named `FAILED` are the
expected fail-closed wheel-only modes and their enclosing 14/14 contract is `PASSED`.

## Code-confirmed vertical

```text
specs/groupware/read-policy.json
specs/mcp/servers/groupware-read/server.json
specs/mcp/access/credential-references.json
specs/agents/groupware-read-agent/*
okcanvas_agent_runtime/application/groupware_read/*
okcanvas_agent_runtime/application/assistant_routing/service.py
```

The Groupware Agent has one V3 read-only remote MCP and no Function Tool, hosted Tool, Skill,
Session, workspace, child Agent, Guardrail, or write authority. Routing dynamically promotes the
static `NOT_CONFIGURED` capability only when endpoint, credential reference, secret value, identity,
and role gates all pass.

## No unsupported claim

No real company endpoint or secret was present in the input ZIP or Windows log. The committed
`.invalid` endpoint is intentionally non-routable, so STEP086 implements the executable vertical
without claiming a live external Groupware integration.

## Deterministic validation closure

The full repository regression was executed through the Product-owned resumable bounded runner in
12 chunks of at most 20 test files. The completed checkpoint records 235 files and 962 tests with
zero failures, errors, skips, or timeouts. Machine-local chunk logs are excluded from the Product
inventory; `docs/evidence/STEP086_PYTHON_REGRESSION.json` retains the cumulative result.

The current exact topology is 30 Agent definitions, 35 capability bindings, 890 RuntimeInfo fields,
339 canonical modules, 301 compatibility aliases, and 98 HTTP routes (54 Admin, 39 Service, 5
Other) with zero missing or duplicate routes.

STEP086 does not claim a live Groupware endpoint. Final Fresh validation proves the immutable source
ZIP contains the fail-closed configuration, validation evidence, issue registry, handoff, and the
Windows deterministic launcher. External artifact evidence records the final ZIP hashes and roots.
