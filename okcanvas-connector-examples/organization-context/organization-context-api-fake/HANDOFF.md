# Organization Context API Reference HANDOFF

```text
Step: EXAMPLE_ORGANIZATION_CONTEXT_STEP002R2_REFERENCE_RELATION_FACT_CONSISTENCY_CLOSURE
Version: 0.2.2
State: LOCAL_DETERMINISTIC_ACCEPTED_CANDIDATE
Node tests: 12/12
Acceptance: 19/19
Status: EXAMPLE_TEMPLATE_ONLY
Production SOT: DATABASE
Example SOT: COMMITTED_JSON_FIXTURES
```

`tenant-a` provides 13 departments, 12 positions, 48 employees, 120 products, 120 clients, 80 glossary terms, 24 projects, 10 systems, 30 capabilities and 893 relations.

STEP002R2 corrects stale department and position relationships for `employee-0017` and `employee-0034`, adds the missing `position.lead` relation for `employee-0034`, and adds a startup validator that compares employee scalar facts with relationship facts.

The Example exposes unified resolve/search/get-entity APIs while retaining Glossary APIs and the mutable admin REST boundary. It is not an MCP server and not a production datastore.
