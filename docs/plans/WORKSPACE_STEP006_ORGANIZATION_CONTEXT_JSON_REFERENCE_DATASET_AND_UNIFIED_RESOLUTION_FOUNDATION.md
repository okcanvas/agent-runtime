# WORKSPACE STEP006 Plan

## Goal

Promote the Organization Context construction guide from a three-term hard-coded seed to a committed JSON reference dataset with validated relationships and unified context responses, while keeping the real service database as production SOT.

## Scope

- Example JSON manifests and collections for directory, products, clients, glossary, projects, systems, capabilities, and relations.
- Deterministic fixture validation and tenant isolation.
- Unified Context resolve/search/get-entity APIs.
- Three new read-only MCP Tools; five Glossary Tools retained.
- Existing admin REST CRUD/revision/CAS/tombstone retained.
- Workspace E2E through the real Connector and Node Example.

## Explicitly deferred

- Runtime wiring.
- Replacement of STEP084 local catalog.
- Production database implementation or migration.
- Admin UI.
- OpenAI and real enterprise calls.
