# STEP008R4R10 Implementation Failure Log

Current Workspace: WORKSPACE_STEP008R4R10_RUNTIME_STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER
Workspace Version: 0.8.4-r10
Current Runtime: STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER
Runtime Version: 2.78.0

## Scope

Agent-core cross-domain continuity only. No executable test gate was run under the current user test hold.

## Failures / corrections observed during implementation

### R10-W1 — Unsafe name fallback would violate stable-evidence continuity

Initial architectural candidate was to reuse the Organization Context display label as a Groupware search query. Code inspection showed the Groupware MCP contract had no Organization stable identifier input, so this would have converted an evidence-bound `employee-0017` focus back into an ambiguous name string. The design was rejected before packaging.

Correction: add exact `context_ref {entity_type, entity_id}` across Runtime -> MCP Connector -> Groupware API and revalidate it on the Tool result.

### R10-W2 — Calendar connector client initially accepted context_ref but did not forward it

During static end-to-end wiring review, `HttpGroupwareClient.list_calendar_events()` accepted `context_ref` but the REST body initially omitted it. This would have made the runtime hint and Connector result appear wired while the actual Groupware API did not filter by the stable ref.

Correction: calendar request body now contains `context_ref` exactly like notice/mail requests. STEP094 static validation checks this path.

### R10-W3 — Example health identity stayed at 0.1.0 after package version moved to 0.2.0

The Groupware Example health payload still returned version `0.1.0` after STEP002 package metadata became `0.2.0`.

Correction: health response version aligned to `0.2.0`. No acceptance result is claimed because executable tests remain deferred.

## Recurrence rules

- Never translate a stable Organization Context ID back to a display-name query when crossing domains.
- A context reference is an additive content filter, never an authorization identity.
- All three Groupware read paths must forward the exact stable context reference.
- Runtime must revalidate Tool name, applied ref and returned record refs before preserving focus.
- Version identity must stay aligned across baseline/package/health/current SOT.

## R10-W4 — Model-created narrowing arguments were initially unconstrained

Static path review showed that exact Tool name + exact context_ref was not sufficient: a model could add a display-name query, shorter limit, or inferred calendar range and silently produce a false negative. The v1 cross-domain contract now requires canonical arguments only (`query=""`, no calendar time range, `limit=20`) whenever `context_ref` is present. The Connector rejects noncanonical contextual arguments fail-closed.

## R10-W5 — Focused Live source initially expected non-persisted citation metadata

Static lifecycle-path review showed `agent.tool.output.normalized` intentionally persists normalization metadata but not the normalized Groupware output/citations. The first focused Live draft incorrectly expected a `normalized_citations` field that does not exist. The harness was corrected without expanding lifecycle disclosure: it verifies exact applied stable ref, the normalizer-proven filtered record count, and exact fake API request bodies. No Groupware record ID/title was newly persisted in lifecycle metadata for test convenience.

## R10-W6 — Current architecture validation SOT lagged behind STEP094 modules

Static architecture validation exposed that the retained STEP081 physical module manifest and current-validation constants still described the parent STEP093-era module/runtime-info surface. The historical STEP081 identity was preserved, while only its physical current inventory was regenerated from the actual source and `CURRENT_VALIDATED_STEP/VERSION` plus the expected RuntimeInfo field count were aligned to STEP094. Static architecture validation then passed 40/40. No executable test was run.
