# STEP008R4R7 Implementation Failure Log

## Purpose

Record Workspace integration failures for Runtime STEP091D so later workspace waves do not repeat
identity, historical-evidence, manifest or finalization mistakes.

## F1 — Current Runtime runner assertions retained the previous runner literal

- Failure: Workspace regressions expected `run_step091b3r1_acceptance.py` after the aggregate had
  legitimately advanced to `run_step091d_acceptance.py`; one stage-label assertion also retained R6.
- Correction: advance only current-runner/current-label assertions to STEP091D/R7.
- Prevention: current runner identity should be derived from the Workspace current contract where
  feasible.

## F2 — Broad current-identity replacement corrupted historical STEP091B3R1 evidence assertions

- Failure: tests reading immutable `STEP091B3R1_DETERMINISTIC_ACCEPTANCE.json` and
  `STEP091B3R1_FULL_RUNTIME_TEST_PARTITIONS.json` were changed to expect STEP091D.
- Cause: historical evidence assertions and current catalog assertions shared one runtime constant.
- Correction: introduce explicit historical STEP091B3R1 identity constants for immutable evidence;
  retain STEP091D constants only for current catalog/contract assertions.
- Prevention: never mass-rewrite an immutable evidence identity. Separate `CURRENT_*` and
  `HISTORICAL_*` constants before advancing a baseline.

## F3 — Parent-project and Workspace manifests are intentionally stale during implementation

- Failure: initial Workspace unit run reported parent-project byte mismatch and Workspace manifest
  drift after legitimate source/test/doc additions.
- Correction: defer manifest regeneration until implementation, evidence and current docs are closed,
  then regenerate exact Runtime parent inventory and Workspace manifest and rerun tests.
- Prevention: do not repeatedly churn manifests during implementation; regenerate at the explicit
  finalization boundary and require zero drift afterwards.

## F4 — Runtime full-suite count changed after adding the STEP091D regression file

- Fact: the exact suite advanced from 250 files / 1,044 tests to 251 files / 1,047 tests.
- Correction: the R7 aggregate contract is updated from actual STEP091D partition evidence, while
  historical STEP091B3R1 tests continue to assert 250 / 1,044 against the historical evidence file.
- Prevention: never infer current regression cardinality from the parent Step; derive it from the
  current full-partition aggregate.

## F5 — Prior promoted HANDOFF regression was only visible after current full Runtime rerun

- Failure: STEP086 retained-identity regression failed against the actual R6 promoted Runtime HANDOFF.
- Correction: STEP091D restores the retained identity ledger and makes the complete Runtime suite a
  current-step closure requirement before Workspace packaging.
- Prevention: promotion-only documentation changes are Product-regression relevant when tests own
  HANDOFF continuity; rerun those suites instead of reusing stale evidence.

## F6 — Historical capability tests still asserted superseded current-document promotion text

- Failure: STEP091B1/B2/C-named tests read the current HANDOFF but expected the R6 phrases
  `Current Windows ...` and `Promotion: CURRENT_PROMOTED_BASELINE` after R7 had correctly become a
  new pending candidate.
- Correction: preserve the parent accepted Windows facts explicitly as parent facts and assert the
  current R7 `Promotion: NOT_READY` state.
- Prevention: tests may retain historical capability contracts, but any assertion against a current
  mutable document must distinguish parent evidence from current-step promotion state.

## F7 — Fresh aggregate command window ended before the child pipeline completed

- Failure: the first Fresh aggregate attempt ended after the Runtime child started and emitted no
  final aggregate result.
- Correction: rerun from the same untouched Fresh extraction with a bounded longer supervisor window;
  the complete pipeline then passed 34/34.
- Prevention: never infer aggregate success from partial child output. Require the final Workspace
  evidence state plus child return codes and zero manifest drift.

## F8 — Final Runtime partition 16 supervisor needed an explicit TERM in this Linux tool environment

- Failure: the architecture/launcher-heavy partition 16 was healthy in prior runs but one final
  supervisor invocation remained open without updating evidence while the outer command window
  expired; earlier attempts also emitted `TERM environment variable not set` from retained tests.
- Correction: rerun the exact same partition with `TERM=xterm`; it completed normally with 87/87
  PASSED and fresh JSON/log evidence, then partitions 17/18 and the aggregate passed.
- Prevention: Linux CI/supervisor environments that execute terminal-aware historical tests should
  provide a stable `TERM`; Windows launchers are unchanged and this is not treated as Product logic.
