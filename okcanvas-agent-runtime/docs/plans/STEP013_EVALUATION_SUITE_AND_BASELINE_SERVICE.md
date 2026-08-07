# STEP013 — Evaluation Suite and Baseline Service

## Status

`COMPLETE`

## Purpose

Group deterministic Evaluation Cases into immutable, versioned Suites and evaluate explicit completed Product Runs in bounded batches. Persist aggregate results and compare only against an operator-selected immutable Baseline.

## Reference decisions

Inspected before implementation:

- `reference/upstream/openai-agents-python-0.19.0/AGENTS.md` — baseline review and full-diff regression expectations (`ADAPT`).
- `reference/upstream/openai-agents-python-0.19.0/examples/agent_patterns/llm_as_a_judge.py` — model-judge pattern (`DEFER`; not authoritative for this step).
- `reference/upstream/openai-agents-python-0.19.0/src/agents/usage.py` — additive Usage aggregation (`ADAPT`).
- `reference/upstream/openai-agents-python-0.19.0/tests/**` explicit fixture/assertion patterns (`ADAPT`).

`/reference` remains immutable and is never imported by runtime code.

## Contract

- Suite manifests live under `specs/evaluation-suites/<suite-id>/suite.json`.
- A Suite declares named slots, each bound to one deterministic Evaluation Case.
- An invocation supplies explicit `subject_id`, `slot_id`, and completed Product `run_id` values.
- No implicit Run discovery, latest-run selection, or Case×Run cross product occurs.
- Each Suite limits subjects to at most 20 globally and may configure a smaller limit.
- All Run evidence is prepared and validated before any Evaluation or Suite row is committed.
- Evaluation rows, Suite aggregate, and Suite members are persisted in one SQLite transaction.
- Baselines are created only by an explicit operation from a passed Suite execution.
- Comparison requires the same Suite ID/version/manifest SHA and the same subject/slot/case shape.
- Regression reporting is evidence only; it does not deploy, block a release, or mutate Product Runs.

## Non-scope

- model judge;
- automatic release gate;
- automatic latest baseline;
- live model execution;
- distributed workers;
- remote/write MCP;
- UI.
