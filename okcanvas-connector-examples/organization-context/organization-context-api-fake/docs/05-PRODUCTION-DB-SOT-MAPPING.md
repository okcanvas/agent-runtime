# Production DB SOT Mapping

A real Organization Context service must store these entities in its database and expose the same product API. The database owns current rows, row versions, status, catalog revision, change feed, and tombstones.

The JSON fixture names map to logical DB aggregates:

```text
departments.json  -> organization_department
positions.json    -> organization_position
employees.json    -> organization_employee
products.json     -> organization_product
clients.json      -> organization_client
glossary.json     -> organization_term + aliases + bindings
projects.json     -> organization_project
systems.json      -> organization_system
capabilities.json -> organization_capability
relations.json    -> organization_entity_relation
```

The exact physical schema is implementation-specific. Stable IDs, tenant isolation, optimistic concurrency, provenance, and explicit ambiguity are contractual.
