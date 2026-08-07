# STEP036_RECORDED_RUN_RUNTIME_BINDING_VERIFICATION

Status: **WINDOWS_LIVE_ACCEPTED**


## Goal

Make recorded-Run Evaluation depend on the same executable Runtime identity that governed preflight, confirmation, and execution.

## Code-audited gap

`agent.definition.resolved` already records `runtime_binding_sha256`, but `RecordedRunEvaluationService` previously ignored it. Evaluation could therefore pass after executable Runtime drift.

## Scope

- add `RUNTIME_BINDING_DRIFT`;
- re-resolve the current Runtime binding during recorded Evaluation;
- validate recorded binding and capability metadata;
- persist and expose `subject_runtime_binding_sha256`;
- migrate existing Evaluation SQLite schemas additively;
- reject unbound legacy Runs rather than guessing;
- add deterministic Product acceptance and Windows launcher.

## Acceptance

Require 18/18 checks, three seeded completed reference-research Runs, exactly three seed gateway calls, one persisted Evaluation, three preserved Artifacts, both drift cases returning HTTP 409 / `RUNTIME_BINDING_DRIFT`, unchanged References, and cleanup `COMPLETED`.

## Deferred

- archived executable Runtime bundles;
- historical evaluation under obsolete Runtime code;
- dynamic plugin loading;
- model-based evaluation;
- a new business Agent.

## Windows closure

The user-reported `sh_run_step036_acceptance.cmd` output passed all 18 checks with three seed gateway calls, one persisted Runtime-bound Evaluation, three Artifacts, two exact `RUNTIME_BINDING_DRIFT` rejections, and cleanup `COMPLETED`. See `docs/evidence/STEP036_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.
