# STEP011 — Agent Definition and Evaluation Catalog API

## Objective

Expose immutable Agent definition metadata, evaluation case definitions, persisted evaluation history and deterministic result comparison through authenticated read-only Control API endpoints.

## Inspected Reference

- `reference/upstream/openai-cs-agents-demo/python-backend/server.py`
- `reference/upstream/openai-agents-streaming-api/src/api/utils/agent_router.py`
- existing project `control_api`, `agent_definitions`, and `evaluation` modules

## Decisions

- ADAPT compact Agent metadata listing from the customer-support demo.
- REJECT instruction/system prompt and internal configuration disclosure from the streaming demo.
- ADOPT existing immutable project catalogs and SQLite evaluation history.
- REJECT direct `/reference` imports.

## Scope

- authenticated list/detail endpoints;
- evaluation history filters and bounded pagination;
- comparison of two persisted results;
- canonical 400/404/500 errors;
- output-schema exposure without instruction text;
- Windows deterministic acceptance launcher.

## Non-scope

- UI;
- evaluation execution endpoint;
- remote MCP;
- write MCP;
- tenant authorization;
- distributed workers;
- model calls.

## Acceptance

- unauthorized reads rejected;
- definitions and cases sorted and validated;
- instructions and local paths not exposed;
- history/detail/comparison correct;
- missing results return canonical 404;
- GET requests do not mutate evaluation DB;
- `/reference` trees remain unchanged;
- no direct Reference import.
