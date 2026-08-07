# STEP000_REFERENCE_BASELINE

## Objective
Create a reproducible repository baseline containing project rules, immutable supplied reference source, provenance, minimal executable code, tests, and packaging evidence.

## In scope
Repository structure, reference extraction, manifests, docs, minimal CLI, verification, tests, ZIP and SHA-256.

## Non-scope
Model calls, Codex, MCP execution, workspace mutation, API server, database, UI, PlanVM, and Windows worker.

## Acceptance

- Four archive SHA-256 values match the uploaded files.
- Four extracted tree hashes match `reference/MANIFEST.json`.
- Four required license files exist.
- Reference source is not imported as runtime code.
- Compile, CLI, verifier, and actual tests pass.
- Handoff, source ZIP, and SHA-256 are present.
