# STEP084 Code Audit — Organization Knowledge, Glossary and Directory Foundation

## Audited baseline

STEP083 / 2.63.0 exposed an Agent-ID-free Assistant but classified organization knowledge as `NOT_CONFIGURED`. No glossary catalog, policy source repository or directory snapshot existed in Product code.

## Code-confirmed implementation

### Configuration SOT

```text
specs/organization/manifest.json
specs/organization/glossary.json
specs/organization/knowledge.json
specs/organization/directory.json
```

The default manifest is `EMPTY`, contains no organization records and binds the three payload hashes.

### Runtime implementation

```text
okcanvas_agent_runtime/application/organization_context/models.py
okcanvas_agent_runtime/application/organization_context/catalog.py
okcanvas_agent_runtime/application/organization_context/service.py
```

The catalog rejects malformed schemas, unknown keys, symlinks, hash drift and inconsistent counts. The service filters by effective date, tenant, principal and role before scoring records.

### Assistant integration

`OrganizationAssistantRoutingService` receives authenticated scope. For `SEARCH_KNOWLEDGE`:

```text
EMPTY catalog      -> NOT_CONFIGURED, no model submission
unauthorized match -> NO_MATCH, no model submission
no match           -> NO_MATCH, no model submission
ambiguous match    -> AMBIGUOUS, no model submission
authorized match   -> EXECUTABLE with versioned grounding
```

The model request includes `organization_grounding`, `authoritative_only=true`, source references and an explicit prohibition on inventing unlisted organization facts.

### HTTP boundary

Admin may supply an explicit audit scope. Service ignores caller-supplied scope and uses the authenticated Service principal context. Six read-only routes are registered.

### Fixture boundary

`fixtures/organization/step084-ready` contains four synthetic records for deterministic validation only. It is not presented as real organization data.

## Architecture effect

```text
RuntimeInfo fields: 861
Admin routes: 54
Service routes: 39
Other routes: 5
Total HTTP routes: 98
Canonical modules: 332
Compatibility aliases: 301
```

No import cycle, missing internal import, duplicate route or new Product execution plane was introduced.

## Retained limitations

- default Product catalog has zero records;
- no external sync or vector index;
- no delegated enterprise identity;
- MCP allowlist remains `reference-catalog` only;
- enterprise read connectors remain unconfigured;
- write and automation remain proposal-only;
- Tool Search and programmatic Tool calling remain disabled.

## Recorded implementation failures

```text
OR-ISSUE-071 acceptance runner referenced a nonexistent RuntimeInfo field
OR-ISSUE-072 current launcher regression retained STEP083 paths
OR-ISSUE-073 current-state assertions were stale and one historical evidence count was mutated
OR-ISSUE-074 source packager retained the STEP083 default filename
```

Each issue has a direct recurrence gate and is covered by the full cumulative regression.
