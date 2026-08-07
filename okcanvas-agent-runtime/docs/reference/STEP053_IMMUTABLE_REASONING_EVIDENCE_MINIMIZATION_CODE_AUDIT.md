# STEP053 — Code and Immutable Reference Audit

## Audit rule

The STEP052 package, product event/usage path and immutable
`reference/upstream/openai-agents-python-0.19.0` snapshot were inspected before selecting STEP053.
No executable code imports from `/reference`.

## STEP052 Windows closure

The user report matched all 25 checks and is compacted in
`docs/evidence/STEP052_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`. STEP052 is Windows-live accepted.

## Candidate comparison

### Selected: reasoning evidence minimization

Product code already retained aggregate reasoning-token usage, while the SDK can return reasoning
items containing summaries, content, item IDs, encrypted content and provider-specific data. The
Product did not persist these fields, but the prohibition and safe count-only evidence were not
independently policy-bound. This is a cross-cutting confidentiality boundary and adds no new external
authority.

### Deferred: positive bounded retry

SDK 0.19.0 preserves a separate conversation-locked compatibility path whenever positive retry is
enabled. A global one-retry claim remains false without a separate wrapper/stateful replay design.

### Deferred: second provider, Session compaction, parallel orchestration and Sandbox

Those add provider parity, history transformation, cancellation or containment contracts unrelated
to the reasoning evidence gap.

## Product findings before change

- `UsageSummary` and recorded Evaluation already accepted `reasoning_tokens`.
- native streaming intentionally filtered reasoning content.
- `ModelSettings` specified zero retry but did not explicitly set reasoning or response includes.
- Runtime binding had no reasoning evidence policy/source identity.
- `model.completed` exposed output count but no safe reasoning count/non-persistence evidence.

## Immutable SDK findings

Inspected:

- `examples/reasoning_content/main.py`, `runner_example.py`, `gpt_oss_stream.py`;
- `src/agents/model_settings.py`;
- `src/agents/items.py`;
- `src/agents/result.py`;
- `src/agents/run_internal/items.py`, `streaming.py`;
- `src/agents/models/openai_responses.py`.

Confirmed:

- `ModelSettings.reasoning` can request reasoning summaries;
- `ModelSettings.response_include` can request additional response data;
- streamed and final results can contain reasoning events/items;
- reasoning items can carry summary/content/ID/encrypted/provider data;
- reasoning IDs have a distinct history-conversion policy, but STEP053 does not enable reasoning
  history persistence.

## Implemented files

- `specs/runtime/reasoning-evidence-policy.json`;
- `reasoning_evidence/models.py`, `catalog.py`, `runtime.py`;
- `execution/openai_gateway.py` explicit SDK settings and count-only Event evidence;
- `execution/runtime_binding.py` policy/source fingerprint;
- focused tests, STEP053 Acceptance, Evaluation case and Windows launcher;
- AGENTS/HANDOFF/PLANS/ROADMAP/README and STEP052 Windows evidence.

## Acceptance result

30/30 deterministic checks pass. One fake reasoning item with five private sentinel classes is
observed only as count `1`; usage records reasoning tokens `11`; every raw sentinel is absent from
Events, Product/Evaluation DB and Artifact. Policy drift returns `409` before a second Task/Run.
Windows live rerun remains pending.
