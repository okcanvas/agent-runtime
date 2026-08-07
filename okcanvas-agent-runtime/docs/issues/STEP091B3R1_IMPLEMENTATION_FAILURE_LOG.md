# STEP091B3R1 Implementation Failure Log

## Purpose

Record every failure observed while implementing and validating the real PostgreSQL
live acceptance gate so later storage and acceptance waves do not repeat them.

## Recorded failures

### F1 — New direct scripts imported project modules before bootstrapping the root

- Symptom: direct deterministic execution failed with `ModuleNotFoundError`.
- Cause: the new deterministic/live scripts imported Runtime modules before inserting
  the project root into `sys.path`.
- Correction: both scripts now resolve and insert `ROOT` before project imports.
- Prevention: every directly executable repository script must pass a fresh-shell
  bootstrap test before being registered as a launcher.

### F2 — Launcher registry regressions froze the current record count at two

- Symptom: a valid current step with deterministic and live Python/CMD pairs was
  rejected because historical tests required exactly two current records.
- Cause: tests duplicated a temporary registry cardinality instead of deriving it from
  `required_current_records`.
- Correction: affected STEP080A, STEP081, STEP081C and STEP086R2 regressions now derive
  current paths, record count and launcher pairs from the registry contract.
- Prevention: launcher tests may assert required pair completeness, but must not own a
  fixed current-step cardinality.

### F3 — STEP081 physical manifest became stale after baseline identity changed

- Symptom: architecture validation failed `physical_module_inventory_current`.
- Cause: `baseline.py` changed to STEP091B3R1 / 2.74.1, changing its canonical hash.
- Correction: regenerate `STEP081_PHYSICAL_RELOCATION_MANIFEST.json` from retained
  relocation evidence.
- Prevention: every canonical source identity change must be followed by physical
  manifest regeneration before architecture acceptance.

### F4 — A grouped partition command ended before all partitions completed

- Symptom: the outer command window ended although completed partition evidence was
  valid and individual pytest groups were healthy.
- Cause: several architecture and Node/CLI groups exceeded the practical grouped
  command window.
- Correction: retain completed evidence and split the exact full suite into 18 bounded,
  non-overlapping partitions.
- Prevention: full-suite runners must preserve per-partition evidence and support
  continuation without rerunning or discarding completed partitions.

### F5 — Additional historical tests repeated the fixed-two launcher assumption

- Symptom: later partitions exposed the same invalid assumption in STEP080A and
  STEP086R2 tests after the first occurrence had been fixed.
- Cause: the cardinality assumption was duplicated across historical regressions.
- Correction: search the complete test tree and generalize every current-launcher
  assertion to registry-derived expectations.
- Prevention: after fixing a duplicated invariant, perform a repository-wide literal
  and semantic search before resuming the full suite.

### F6 — STEP081C froze the current launcher path set to deterministic-only paths

- Symptom: the partition rejected the additive live Python/CMD pair.
- Cause: the test asserted the previous exact two-path set rather than the registry's
  declared current records.
- Correction: compare the registry current path set with `required_current_records`.
- Prevention: exact current path assertions must use the registry as the source of
  truth, not a historical step literal.

### F7 — Historical package tests owned the superseded archive name

- Symptom: STEP084 and STEP089 package identity regressions expected the STEP091B3 ZIP.
- Cause: tests intentionally checking current package identity were not advanced with
  the current baseline.
- Correction: update only those current-identity assertions to the STEP091B3R1 archive.
- Prevention: retained capability semantics stay historical; current package identity
  must resolve from the packager SOT wherever possible.

### F8 — Real PostgreSQL live execution was unavailable in this environment

- Symptom: no live evidence could be produced.
- Verified environment facts: no PostgreSQL client/server binary was available and
  importing `psycopg` raised `ModuleNotFoundError`.
- Correction: none claimed. The gate remains implemented but unexecuted.
- Prevention: never convert environment absence into a synthetic live pass. Run the
  dedicated gate later against an operator-supplied non-production PostgreSQL server.
