# Recorded Run Evaluation

STEP012 connects the deterministic evaluator to product-owned execution state.

## Authoritative input

```text
Product Run (SUCCEEDED)
+ Product Task (SUCCEEDED)
+ canonical Run Events
+ verified agent.final-output Artifact
+ immutable Agent Definition identity
+ selected Evaluation Case
-> deterministic Evaluation Result
```

The application service does not invoke the OpenAI Agents SDK Runner, a model, MCP, Codex, or an external validator. It does not deserialize an SDK `RunResult`.

## Integrity checks

Before an Evaluation Result is persisted, the service requires:

- one `agent.definition.resolved` Event whose ID, version, and SHA match the current immutable definition;
- one `artifact.created` Event for `agent.final-output`;
- one `run.completed` Event referring to the same Artifact;
- Artifact SHA-256, byte length, media type, Run ownership, and storage-root containment;
- no symbolic path component;
- JSON object output smaller than 1 MiB;
- validation against the declared Pydantic output contract;
- one consistent model identity from `model.started` Events;
- Run token totals equal to the completion Event Usage evidence;
- valid start/completion timestamps.

Any mismatch is fail-closed and creates no Evaluation Result.

## Public application surface

```text
POST /v1/runs/{run_id}/evaluations
```

Request:

```json
{"case_id":"reference-runstate"}
```

The response is the same safe Evaluation Result contract used by the read-only history API. It does not contain the model output, Tool arguments/results, prompts, or Artifact path.

## CLI

```bash
PYTHONPATH=src python -m okcanvas_agent_runtime evaluation-run-recorded \
  --project-root . \
  --run-id run_... \
  --case-id reference-runstate \
  --product-db .local/product.sqlite3 \
  --artifact-root .local/artifacts \
  --evaluation-db .local/evaluation.sqlite3 \
  --pretty
```

The previous file-based `evaluation-run` remains available for fixture and migration compatibility, but product operation should use `evaluation-run-recorded` or the Control API.
