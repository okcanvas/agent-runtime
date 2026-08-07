# STEP033 — Agent Runtime Binding Fingerprint

STEP033 strengthens the reusable Agent Runtime rather than adding another business rule. It binds the executable Runtime behavior selected for a submission to the exact confirmation fingerprint and verifies the same binding again before Product Task/Run or approval state is created.

## Code-audited defect

Before STEP033, a governed submission fingerprint bound the policy, Agent definition, selected model, input, execution mode, and optional source snapshot. It did not bind several executable Runtime components that can materially change what happens after confirmation:

- output-contract type and contract-specific recovery implementation;
- installed Agents SDK version expectation;
- MCP server declaration and executable server module;
- controlled local Tool policy and executable implementation;
- the selected common execution engine path.

A pending confirmed submission could therefore survive a package or policy replacement while its Agent definition remained unchanged. The later execution could use behavior that was not present when the operator confirmed the fingerprint.

## Runtime binding

`AgentRuntimeBindingCatalog` resolves a closed, product-owned binding for one immutable Agent definition.

```text
Agent definition
+ Agents SDK package/version
+ output-contract Runtime definition SHA
+ MCP definition/module SHA set
+ local Tool policy/implementation SHA set
+ selected execution engine SHA
→ runtime_binding_sha256
```

The current executable paths are:

```text
generic-agent-execution-v1
governed-local-tool-approval-v1
non-executable-local-tool-proposal-v1
```

`non-executable-local-tool-proposal-v1` preserves the existing fail-closed proposal path for unregistered Tools. It does not grant execution authority.

## Bound state

The Runtime binding SHA is included in:

- the submission request fingerprint;
- the SQLite submission ledger;
- the encrypted protected-payload content;
- the AES-GCM associated-data identity;
- prepared generic execution state;
- the normalized `agent.definition.resolved` Event.

Before confirmation execution or local Tool preparation, the Runtime resolves the current binding again. A mismatch fails before Task, Run, approval, Artifact, Evaluation, scheduler, model Gateway, MCP, or Tool execution.

## Fail-closed compatibility rule

Pre-STEP033 pending submissions have no Runtime binding SHA and use the earlier protected-payload schema. They are not silently upgraded. They must be discarded or allowed to expire and then recreated and reconfirmed under STEP033.

This is intentional. Reconstructing a missing binding would assert that an old confirmation covered current executable behavior, which cannot be proven.

## Scope limits

STEP033 does not add:

- a new business Agent or business calculation;
- dynamic plugin loading;
- remote connector discovery;
- Tool, MCP, shell, browser, or write authority;
- automatic replay or migration of old submissions;
- Handoff, Session, distributed workers, or running-Run recovery.

## Deterministic acceptance

STEP033 creates governed submissions for three existing paths and then changes one bound Runtime component after preflight:

1. Coding output-contract Runtime drift;
2. read-only MCP definition drift;
3. controlled local Tool policy drift.

Each drift must fail before Product state and before scheduler, model, MCP, or Tool invocation. The output-contract drift must also conflict on same-key idempotent replay because the submission fingerprint has changed.
