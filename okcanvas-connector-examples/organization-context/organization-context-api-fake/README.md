# Organization Context API Reference Example

```text
Step: EXAMPLE_ORGANIZATION_CONTEXT_STEP002R2_REFERENCE_RELATION_FACT_CONSISTENCY_CLOSURE
Version: 0.2.2
Status: EXAMPLE_TEMPLATE_ONLY
Production SOT: DATABASE
Example SOT: COMMITTED_JSON_FIXTURES
```

This project is an executable construction guide for an external Organization Context product API.

```text
NOT AN MCP SERVER
NOT A PRODUCTION DEPENDENCY
NOT THE PRODUCTION DATASTORE
```

## Reference dataset

`tenant-a` contains:

| Entity | Count |
|---|---:|
| Departments | 13 |
| Positions / grades | 12 |
| Employees | 48 |
| Products | 120 |
| Clients | 120 |
| Glossary terms | 80 |
| Projects | 24 |
| Systems | 10 |
| Capabilities | 30 |
| Relations | 893 |

`tenant-b` remains a small isolation seed with a different meaning for `PI`.

## STEP002R2 consistency closure

The loader now verifies that employee scalar records and relationship facts agree exactly for department, position set and manager whenever the tenant fixture contains relationships. The previously contradictory `employee-0017` and `employee-0034` records are corrected, including the missing second position relation for `employee-0034`.

## Product APIs

```text
POST /api/v1/context/resolve
POST /api/v1/context/search
GET  /api/v1/context/entities/{entityType}/{entityId}

POST /api/v1/glossary/resolve
POST /api/v1/glossary/search
GET  /api/v1/glossary/terms/{termId}
GET  /api/v1/glossary/catalog-state
GET  /api/v1/glossary/changes
```

Ambiguity remains explicit. Production implementations must use a database as SOT; committed JSON exists only for deterministic construction and acceptance.

## Commands

```text
npm run setup
npm test
npm run acceptance
npm run start
```
