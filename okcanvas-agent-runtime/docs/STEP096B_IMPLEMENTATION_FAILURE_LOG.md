# STEP096B Implementation Failure Log

## F-096B-001 — New Groupware admission initially used the broader generic max-results bound

Focused admission testing found that the general Groupware policy max (50) conflicts with the
existing cross-domain stable-context normalizer bound (<=20).

Correction: Session-focus admission uses `min(policy.max_results, 20)` and focused tests require 20.
Recorded as WORKSPACE-ISSUE-068.

## F-096B-002 — Source-text assertion assumed Markdown line wrapping

An early Root-instruction test searched one exact source line and failed when Markdown wrapped the
same sentence. No Product behavior failed.

Correction: assertions use stable semantic fragments rather than formatting layout.

Recurrence rule: source formatting is not a Product contract.

## F-096B-003 — Product non-read side-effect fence was not initially part of read admission

The first admission checked only the model's READ schema. Product-owned DRAFT/WRITE/AUTOMATION
classification could therefore have been ignored by an erroneous model read-child request.

Correction: admission allows read children only when the immutable parent side effect is NONE or
READ. Recorded as WORKSPACE-ISSUE-069.

## F-096B-004 — Max-one fence initially counted only successful admissions

A denied first specialist request could potentially be followed by a request for the other child.

Correction: a separate request counter permits only one specialist request per Turn, admitted or
denied. Recorded as WORKSPACE-ISSUE-070.

## F-096B-005 — Local analysis interpreter does not have openai-agents installed

Direct construction/mutation of the installed SDK `Agent` could not be executed in this container
because the `agents` package is absent. No Live SDK claim is made. The retained pinned
`openai-agents-python 0.19.0` source was inspected instead: `AgentBase` is a non-frozen dataclass,
`mcp_servers` and `model_settings` are mutable fields, and MCP lifecycle explicitly requires
`connect()` / `cleanup()`.

Recurrence rule: STEP096B remains LOCAL_DETERMINISTIC_ACCEPTED_LIVE_NOT_RUN until the real configured
Runtime environment executes the structured Root->child path with the pinned SDK.
