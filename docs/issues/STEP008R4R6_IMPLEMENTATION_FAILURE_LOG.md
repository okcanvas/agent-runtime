# STEP008R4R6 Implementation Failure Log

## Purpose

Record Workspace integration, validation and packaging failures for Runtime STEP091B3R1.

## Imported Runtime failures

The nested Runtime record is authoritative for implementation failures:

- `okcanvas-agent-runtime/docs/issues/STEP091B3R1_IMPLEMENTATION_FAILURE_LOG.md`

It records direct-script bootstrap omission, fixed launcher cardinality/path assumptions,
physical-manifest drift, partition command-window behavior, stale package-name assertions,
and the absence of a real PostgreSQL environment.

## Workspace failures

### W1 — Historical acceptance-source test fixed the STEP091B3 runner path

- Symptom: Workspace unit tests rejected the current STEP091B3R1 runner.
- Cause: the retained short-expression test owned a concrete current Runtime script path.
- Correction: advance the current-runner assertion to `run_step091b3r1_acceptance.py`.
- Prevention: tests for current acceptance execution must resolve from current Runtime identity.

### W2 — Historical diagnostic test fixed the STEP008R4R5 stage label

- Symptom: the current deterministic runner was rejected solely because its stage prefix advanced to R6.
- Cause: a retained test treated a diagnostic label as a permanent capability contract.
- Correction: advance the current-label assertion to STEP008R4R6.
- Prevention: historical tests should assert structured identity or behavior rather than temporary log labels.

### W3 — Workspace manifest was stale after planned source and documentation changes

- Symptom: `test_workspace_manifest_is_current` failed with changed and unexpected paths.
- Cause: the immutable Workspace manifest still described STEP008R4R5.
- Correction: regenerate it only after current source, tests, contracts and documents are stable.
- Prevention: manifest generation is the final pre-acceptance source step, never an early implementation step.

### W4 — Aggregate Connector→Example E2E depended on captured-pipe EOF

- Symptom: the full Workspace acceptance reached `connector-example integration start`
  and the outer execution window ended without aggregate evidence.
- Code verification: the same E2E executed independently and passed 17/17.
- Cause: this one aggregate child still used `run_process(capture_output=True)` while
  long-lived child boundaries elsewhere already used file-backed capture.
- Correction: execute the integration through `run_process_to_files` with dedicated
  stdout/stderr evidence files.
- Prevention: acceptance children that can spawn servers must use file-backed
  direct-child completion and must not depend on pipe EOF from descendants.

### W5 — Completed acceptance emitted a multi-megabyte aggregate JSON to the outer command

- Symptom: internal evidence reached `PASSED 33/33`, but the external execution wrapper
  did not return before its command window while processing the large console payload.
- Proven state: the UTF-8 evidence file was complete, parseable, 33/33, and all five
  child return codes were zero.
- Correction: add a Workspace `--quiet` mode that still writes the complete evidence
  file but suppresses the duplicate console JSON.
- Prevention: large aggregate acceptances must separate durable evidence from optional
  human-console rendering.

### W6 — File-backed parent capture alone did not bound the nested Node server I/O

- Symptom: a later aggregate attempt again stopped after integration start with zero
  bytes in the child evidence files, while rerunning the exact retained temp tree passed
  17/17 in about three seconds.
- Verified source boundary: the E2E child launched its Node server with unread
  `stdout=PIPE` and `stderr=PIPE`, and the npm build had no timeout.
- Correction: bound the npm build to 60 seconds and route the server's unused stdin,
  stdout and stderr to `DEVNULL`; server termination/wait remains bounded in `finally`.
- Prevention: nested acceptance servers must not own unread pipes and every synchronous
  build subprocess must have an explicit timeout.

### W7 — Foreground tool wrapper timeout was not the Workspace process state

- Symptom: foreground tool calls reported timeout even with `--quiet`.
- Verification: a supervised background run of the same command reached every final
  stage, wrote parseable 33/33 evidence, exited with code 0, and left no child process.
- Conclusion: the external tool wrapper timeout is not a Product or acceptance failure;
  W5's large-console-output hypothesis was insufficient because quiet mode showed the
  same wrapper behavior.
- Prevention: determine acceptance state from the child exit code and durable evidence,
  and never convert an outer tool timeout into a pass or Product failure without
  inspecting the process tree and evidence file.

## Candidate Fresh validation closure

- Candidate manifest matched 4,642/4,642 files.
- Candidate package contained 4,643 files plus the archive root entry.
- Fresh Workspace tests passed 131/131.
- Fresh Runtime STEP091B3R1 passed 21/21 with source snapshot unchanged.
- Fresh Workspace acceptance passed 33/33.
- Connector 11/11, Example 19/19 and Connector→Example 17/17 passed.
- Fresh post-acceptance manifest drift was zero.
- Final documentation/evidence was rebound to a 4,643-file manifest; the final package repeated the same Fresh gates and passed.

### W8 — Duplicate `.env.local` key blocked Windows Live preflight

- Symptom: `run_workspace_step008_live_entrypoint.py` raised `LocalEnvironmentError` at
  `.env.local:8` for duplicate `OKCANVAS_CODEX_MODEL` before the Live child ran.
- Code verification: `windows_entrypoint.parse_environment_text()` rejects a key already
  present in the same parsed file; this is intentional fail-fast behavior.
- Correction: remove the duplicate local declaration; do not change Product code or relax
  duplicate detection.
- Prevention: diagnose duplicate-key preflight first, keep `.env.local` package-excluded, and
  never persist secret values while recording this failure.
- Durable issue: `WORKSPACE-ISSUE-039-DUPLICATE-LOCAL-ENVIRONMENT-KEY-BLOCKED-LIVE-PREFLIGHT.md`.

### W9 — Promotion-only current-document changes invalidated exact manifests

- Symptom: first promotion-packaging Workspace unit run failed five tests. Two current-document
  assertions missed retained lineage/launcher tokens; Runtime parent-file manifest and Workspace
  manifest were stale after current README/HANDOFF/evidence changes.
- Cause: promotion status was updated before the final exact manifest regeneration, and the rewritten
  current HANDOFF omitted `STEP091B1` lineage plus the retained live launcher environment names.
- Correction: restore the lineage/launcher contract in current documents, regenerate the Runtime parent
  file manifest from `snapshot_files()`, then regenerate `WORKSPACE_MANIFEST.json` only after all
  promotion files stabilize.
- Prevention: promotion packaging follows `current documents → parent manifests → workspace manifest →
  unit/deterministic validation`; current HANDOFF rewrites must preserve exact operational tokens already
  protected by regression tests.

### W10 — Promotion Fresh aggregate repeated the known outer command-window timeout

- Symptom: a combined Fresh command completed Workspace 131/131 and advanced the aggregate into
  Connector acceptance, but the controlling tool window expired before the final durable evidence.
- Verification: rerunning the exact Fresh aggregate as a supervised direct child completed with
  exit code 0, final state 33/33 PASSED, every child return code 0, and manifest drift zero.
- Classification: recurrence of W7's outer-wrapper boundary, not a Product or acceptance failure.
- Prevention: final acceptance state is derived from child exit code plus durable evidence; a wrapper
  timeout alone is never converted into pass/fail.
