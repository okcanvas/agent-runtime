# OR-ISSUE-007 — STEP075F model repair nondeterminism

## Status

`WINDOWS_LIVE_ACCEPTED`

## Exact symptom

STEP075F Windows live reached one completed read-only Sandbox Tool call and then invoked the permitted correction model call. The run recorded three total model calls, one Tool call, successful workspace materialization, selected-file hash verification, cleanup `COMPLETED`, and orphan count `0`, but failed closed with `ANSWER_COMPLETENESS_FAILED`. The correction output still did not satisfy the exact formula/constant and evidence-backed `unverified` rules.

## Code-confirmed root cause

The Product already possessed all required exact fragments in the single immutable, hash-verified Tool output, but delegated mechanical completion to another probabilistic model call. The repair prompt contained the required values, yet successful compliance was not guaranteed. The acceptance failure is therefore not missing evidence; it is a nondeterministic repair mechanism for a deterministic transformation.

## Impact

- one extra paid model call was consumed;
- the successful Sandbox result was discarded;
- the run failed despite complete verified evidence being available in memory;
- repeating or strengthening the prompt cannot provide a deterministic recurrence gate.

## Fix

STEP075G removes the correction model call from the active execution path. A Product-owned deterministic completion function:

1. uses only fragments derived by the existing exact-evidence validator from the single typed Tool output;
2. appends one bounded `CONFIRMED` finding containing exact identifiers, operators, literals, assignments, complete expressions, and repository-relative line evidence;
3. removes evidence-backed paths from `unverified`;
4. performs no Tool replay and no additional model call;
5. re-runs the same completeness validator and fails closed if requirements remain incomplete.

## Recurrence gates

- incomplete live draft is completed with exact formula and assignment;
- evidence-backed path is removed from `unverified`;
- gateway invokes `Runner.run` exactly once;
- no `agent.output.repair.*` events are emitted;
- deterministic completion emits bounded lifecycle events with `model_calls_added=0` and `tool_reexecuted=false`;
- exact requirements that cannot be derived fail closed;
- the 100-finding contract bound remains valid.

## Windows closure

On 2026-08-02, STEP075G Windows live acceptance passed 38/38 with exactly two model calls, one Sandbox Tool call, no model-repair Events, exact formula/constant evidence, empty `unverified`, verified selected-file hashes, cleanup `COMPLETED`, and orphan count `0`. The final count is 38 because the script builds 37 workflow/security checks and then appends `api_key_not_in_summary`. See `docs/evidence/STEP075G_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.
