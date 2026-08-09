# WORKSPACE STEP008R4R10ER1 — Cross-domain Live acceptance promotion closure

Workspace version: `0.8.4-r10er1`  
Runtime: `STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE` / `2.78.2` (unchanged)

## Purpose

Close STEP094 after the user-reported clean R10E Windows focused Live result returned `24/24 PASSED`, while preserving the exact provenance inputs of the executed R10E release.

## Acceptance interpretation

The R10E v2 harness has 24 final checks. A terminal `PASSED` is emitted only when every check is true. The 24 checks cover:

1. Live gate/environment/model readiness;
2. Workspace baseline ↔ project catalog identity;
3. Workspace Runtime identity ↔ executable Runtime baseline;
4. Runtime package metadata identity;
5. started Service runtime-version identity;
6. dedicated unified Session creation;
7. exact three-route resolution;
8. exact three CLI request completions and exactly three successful Runtime Runs;
9. exact Tool sequence `resolve_organization_context → list_calendar_events → search_notices`;
10. stable `employee-0017` focus preservation and exact Groupware `context_ref` filtering;
11. exact Connector paths, authorization redaction and secret absence;
12. clean harness cleanup.

Therefore the reported `24/24 PASSED` closes both the R10E provenance fence and the existing STEP094 functional focused-Live gate.

## Evidence handling

The complete generated Windows JSON was not supplied. R10ER1 does not invent it. It retains:

- the exact user-provided terminal summary;
- the uploaded R10E package SHA-256;
- exact R10E baseline/catalog/Workspace-manifest bytes;
- hashes of the unchanged executable Runtime baseline, Runtime pyproject and focused Live harness.

## Promotion rule

R10E remains the immutable Live-executed parent. R10ER1 is a promotion-only child and is the current promoted Workspace baseline for STEP094. Runtime Product behavior is unchanged.

## Deferred items

Broad tests and MinIO/Object Storage Live remain explicitly deferred. They are productionization backlog and do not reopen STEP094 focused cross-domain acceptance.

## Next Agent-native work

Proceed with a read-only exhaustive audit for bounded durable memory before adding Product code. Durable memory must remain distinct from SDK Session history and STEP092 Session Context Focus, and must define provenance, tenant/principal scope, TTL/retention, update/conflict, deletion and sensitivity/privacy policy before memory can influence model context or routing.
