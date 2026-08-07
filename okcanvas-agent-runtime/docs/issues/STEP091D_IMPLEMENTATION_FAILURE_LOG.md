# STEP091D Implementation Failure Log

## Purpose

Record implementation and validation failures so later Object Storage, packaging and Worker waves
do not repeat them.

## F1 — Working-copy destination parent was not created first

- Failure: the first copy command targeted a child under a nonexistent work directory.
- Cause: workspace/tooling path ordering, not Product code.
- Correction: create the work root before copying the promoted source.
- Prevention: preparation scripts must create the destination root and verify it before copy.

## F2 — Launcher registry records were advanced but top-level current token remained stale

- Failure: focused launcher validation passed 30/31; current records were STEP091D but
  `current_step_token` still identified STEP091B3R1.
- Correction: update the registry's top-level current identity and token together with record state.
- Prevention: a launcher promotion must validate both current record set and top-level SOT fields.

## F3 — New Python module invalidated STEP081 physical inventory

- Failure: STEP091D deterministic acceptance initially passed 18/19 because Architecture rejected
  `physical_module_inventory_current`.
- Cause: adding `s3_compatible.py` changed current physical inventory.
- Correction: regenerate only the current STEP081 physical module manifest from retained relocation
  evidence; historical relocation evidence was not rewritten.
- Prevention: any canonical module add/remove/hash change requires current physical inventory
  regeneration before architecture acceptance.

## F4 — Live gate used a negative boolean inside all-checks success evaluation

- Failure: `checks["secret_values_persisted"] = False` made `all(checks.values())` permanently false,
  so a fully successful live run could never report PASSED.
- Cause: evidence fact and success predicate were modeled in the same check map with opposite
  polarity.
- Correction: express the gate as the positive invariant `secret_values_not_persisted = true` while
  retaining `credentials_persisted=false` as metadata.
- Prevention: every item in a success-check map must have positive-pass polarity; negative facts
  belong in evidence/limitations or must be named as positive invariants.

## F5 — Current package-name regressions remained pinned to STEP091B3R1

- Failure: Runtime full partitions exposed STEP084 and STEP089 tests expecting the old archive name
  while correctly expecting the new current `PACKAGE_STEP`.
- Cause: current package identity was duplicated in historical-named tests.
- Correction: advance only the assertions that intentionally own current package identity.
- Prevention: current archive name should derive from the packager SOT wherever feasible; historical
  semantics must not freeze a later current package name.

## F6 — Prior promoted Runtime HANDOFF had lost retained Product identities

- Failure: STEP086 finalization regression failed because the promoted STEP091B3R1 Runtime HANDOFF
  omitted `local_text_fingerprint`, `local_text_metrics`, `project_readonly_inspect`,
  `sandbox_project_readonly_inspect`, `reference-catalog` and `OR-ISSUE-091`.
- Code verification: the omission exists in the actual promoted R6 ZIP, while the STEP086 test still
  requires the retained identity ledger.
- Cause: the prior promotion-only documentation rewrite was validated with the current deterministic
  gate and historical full-suite evidence rather than rerunning the complete Runtime suite after the
  HANDOFF mutation.
- Correction: restore the retained Product identity ledger in the current HANDOFF and rerun all 18
  Runtime partitions.
- Prevention: after any current HANDOFF rewrite, rerun the complete current Runtime regression rather
  than relying only on an earlier full-suite summary.

## F7 — Long partition grouping exceeded the external command window

- Failure: grouped full-suite execution stopped between partitions although completed partition
  evidence was valid.
- Correction: retain per-partition durable evidence and resume at the first incomplete partition.
- Prevention: keep exact non-overlapping partition execution restartable and aggregate only after all
  partition JSON/log hashes are present.

## F8 — Deployment composition was implemented before the local environment template exposed it

- Failure: code and HANDOFF documented STEP091D variables, but `.env.local.example` contained none of
  the Object Storage selection/bucket/endpoint/region/addressing settings.
- Correction: add commented, secret-free STEP091D deployment examples while keeping local filesystem
  as the uncommented default.
- Prevention: every new environment-owned deployment contract must update the canonical environment
  template in the same Step; secrets must remain placeholders or SDK-chain owned.

## F9 — Compensation object was not initially part of final cleanup tracking

- Failure: the live gate intentionally creates an object before provoking Product metadata failure.
  If the compensation delete itself failed, that known object reference was not in `tracked_refs`, so
  final cleanup could not retry it.
- Correction: register the compensation reference before creation and remove it from tracking only
  after the compensation absence check succeeds.
- Prevention: live gates must add every known destructive resource to final-cleanup tracking before
  the first mutation, not after the happy-path mutation succeeds.
