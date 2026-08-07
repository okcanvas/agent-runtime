# STEP012 — Recorded Run Evaluation Application Service

## Objective

Evaluate an existing successful Product Run without envelope/event files supplied by an operator.

## Inspected Reference

- `reference/CODE_MAP.md` and `reference/MANIFEST.json`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/result.py`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/usage.py`;
- `reference/upstream/openai-agents-python-0.19.0/.agents/references/run-item-lifecycle.md`.

## Scope

- product-owned Run, Task, Event, and Artifact loading;
- final-output Artifact integrity and output-contract validation;
- deterministic Evaluation Case application;
- Evaluation Result persistence;
- CLI and authenticated Control API command;
- deterministic acceptance and restart-history verification.

## Non-scope

- model judge;
- automatic release promotion or blocking;
- UI;
- remote/write-capable MCP;
- distributed Worker or active Run recovery;
- SDK `RunResult` persistence;
- direct `/reference` import.

## Acceptance

- successful recorded Run evaluates and persists;
- non-terminal Run is rejected;
- tampered Artifact is rejected and creates no result;
- Agent definition identity and output contract are verified;
- Usage and Tool calls come from canonical product evidence;
- raw output is absent from Evaluation SQLite;
- API requires local-admin authentication;
- Reference trees remain unchanged.
