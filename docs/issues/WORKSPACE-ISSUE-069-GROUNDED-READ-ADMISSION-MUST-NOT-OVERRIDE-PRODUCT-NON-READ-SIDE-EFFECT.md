# WORKSPACE-ISSUE-069 — Grounded read admission must not override a Product-owned non-read side effect

Status: FIXED_IN_STEP096B

## Failure

The initial structured read admission validated only the model's read-only schema. A Turn that the
Product router had already classified as `DRAFT`, `WRITE_IRREVERSIBLE`, or `AUTOMATION_DEFINITION`
could therefore still be submitted to a read child if the model selected one incorrectly.

## Correction

The admission fence now receives the immutable parent routing side effect and permits a read child
only for `NONE` or `READ`. This does not add a natural-language parser; it preserves an already
established Product safety boundary.

## Recurrence gate

LLM interpretation may improve or defer semantic routing, but it may not downgrade an existing
Product-owned non-read side-effect fence into read execution.
