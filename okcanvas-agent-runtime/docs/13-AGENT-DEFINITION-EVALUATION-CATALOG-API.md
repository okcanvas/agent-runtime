# Agent Definition and Evaluation Catalog API

## Purpose

Expose the immutable Agent definition catalog and deterministic evaluation catalog/history through the existing local-admin Control API without exposing Agent instructions, local file paths, raw model output, Tool arguments, Tool results, or `/reference` content.

## Endpoints

```text
GET /v1/agent-definitions
GET /v1/agent-definitions/{agent_id}
GET /v1/evaluation-cases
GET /v1/evaluation-cases/{case_id}
GET /v1/evaluations
GET /v1/evaluations/{evaluation_id}
GET /v1/evaluation-comparisons
```

All endpoints require `X-OKCanvas-Admin-Key` and are read-only.

## Agent definition response policy

List responses expose only stable operational metadata. Detail responses additionally expose the output JSON Schema and instruction SHA/byte length. They never expose:

- instruction text;
- instruction or schema filesystem paths;
- `/reference/upstream` paths;
- runtime secrets.

Only directories containing a validated `definition.json` are catalog entries. Legacy documentation-only Agent directories remain outside this generic definition catalog.

## Evaluation response policy

Evaluation case detail exposes deterministic required/forbidden result patterns, required/forbidden Tool names, and token/latency budgets. Evaluation history exposes stored checks, metrics, failures and subject identifiers. It does not expose the original model result or reference body.

History supports case, run and state filters plus bounded `limit`/`offset`. Comparisons are computed from two persisted evaluation IDs.

## Persistence

`OKCANVAS_EVALUATION_DB` configures the evaluation SQLite file. If omitted in embedded `create_app` usage, it defaults beside the product database as `evaluation.sqlite3`.

Catalog GET requests do not mutate the evaluation database. Acceptance verifies the database SHA before and after all reads.

## Reference adoption

### ADAPT

- `reference/upstream/openai-cs-agents-demo/python-backend/server.py::_build_agents_list`
  - adopted the concept of a compact Agent metadata list;
  - replaced live in-memory Agent introspection with immutable validated project definitions.

### REJECT

- `reference/upstream/openai-agents-streaming-api/src/api/utils/agent_router.py::get_agent_info`
  - rejected instruction text, internal endpoint/config and filesystem disclosure.

### ADOPT

- project-owned `AgentDefinitionCatalog` and `EvaluationCatalog` are the source of truth.

`/reference` is inspected only and is never imported.

## STEP012 write application endpoint

`POST /v1/runs/{run_id}/evaluations` is the only evaluation write endpoint. It applies a selected deterministic case to product-owned completed Run evidence and returns the safe Evaluation Result contract.
