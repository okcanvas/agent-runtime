# WORKSPACE-ISSUE-075 — ModelBehaviorError diagnostic was too coarse

## Status
FIXED_IN_R12R3_STEP096BR1R1

## Defect
The generic OpenAI gateway reduced pre-specialist `ModelBehaviorError` failures to only
`detail_type=ModelBehaviorError`. This preserved secrecy but made multiple materially different SDK
failure boundaries indistinguishable during Windows Live acceptance.

## Closure
STEP096BR1R1 adds only content-free diagnostics:

- model output item counts by bounded type: message / function_call / reasoning / other;
- safe ModelBehaviorError category;
- explicit markers that raw model output, raw Tool arguments, and raw error messages are not persisted.

No natural-language routing, child-selection, admission, MCP, SOT, stable-ID, or write semantics are
changed by this closure.

## Recurrence rule
A focused Live gate for new SDK orchestration must preserve enough payload-free lifecycle evidence to
locate the failure boundary without requiring raw provider content or Tool arguments.
