# STEP094 Implementation Failure Log

Step: STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER
Version: 2.78.0
State: IMPLEMENTED_STATIC_VALIDATED_TEST_PENDING

## Recorded implementation issues

1. **Name-search bridge rejected.** Existing Groupware tools had no stable Organization Context identifier input. Using `김민수` as a search surrogate would violate STEP092/093 stable-evidence rules and reintroduce ambiguity.
2. **Calendar forwarding omission caught by static review.** `context_ref` was initially missing from the calendar REST body despite being accepted at the client method boundary. Corrected before packaging.
3. **Authorization ordering made explicit.** Groupware Example applies tenant/principal/role visibility before the additional stable-reference filter. `context_ref` does not grant access.
4. **Model-generated Tool arguments remain untrusted.** Named Tool choice is Product-bound, but the model may still construct arguments. Runtime nested normalization therefore requires the actual MCP Tool result to echo the exact applied stable ref and requires every returned record to carry it.
5. **Zero-result semantics.** A zero-record response may preserve the prior Organization anchor only when the Connector Tool result proves the exact stable filter was applied. The anchor authority comes from prior Organization Tool evidence, not from a Groupware match.

No executable tests were run for this Step.

## R10-W4 — Model-created narrowing arguments were initially unconstrained

Static path review showed that exact Tool name + exact context_ref was not sufficient: a model could add a display-name query, shorter limit, or inferred calendar range and silently produce a false negative. The v1 cross-domain contract now requires canonical arguments only (`query=""`, no calendar time range, `limit=20`) whenever `context_ref` is present. The Connector rejects noncanonical contextual arguments fail-closed.

## R10-W5 — Focused Live source initially expected non-persisted citation metadata

Static lifecycle-path review showed `agent.tool.output.normalized` intentionally persists normalization metadata but not the normalized Groupware output/citations. The first focused Live draft incorrectly expected a `normalized_citations` field that does not exist. The harness was corrected without expanding lifecycle disclosure: it verifies exact applied stable ref, the normalizer-proven filtered record count, and exact fake API request bodies. No Groupware record ID/title was newly persisted in lifecycle metadata for test convenience.

## R10-W6 — Current architecture validation SOT lagged behind STEP094 modules

Static architecture validation exposed that the retained STEP081 physical module manifest and current-validation constants still described the parent STEP093-era module/runtime-info surface. The historical STEP081 identity was preserved, while only its physical current inventory was regenerated from the actual source and `CURRENT_VALIDATED_STEP/VERSION` plus the expected RuntimeInfo field count were aligned to STEP094. Static architecture validation then passed 40/40. No executable test was run.
