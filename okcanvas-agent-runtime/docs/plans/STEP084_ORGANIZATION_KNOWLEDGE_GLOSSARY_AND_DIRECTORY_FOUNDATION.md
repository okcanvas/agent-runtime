# STEP084 — Organization Knowledge, Glossary and Directory Foundation

## Identity

```text
STEP084_ORGANIZATION_KNOWLEDGE_GLOSSARY_AND_DIRECTORY_FOUNDATION
version 2.64.0
parent STEP083 / 2.63.0
rollback baseline STEP081D / 2.61.4 Windows live 80/80
```

## Product objective

Turn STEP083 `SEARCH_KNOWLEDGE` routing into an actual read-only, evidence-grounded Product capability without pretending that an external vector database, HR directory, ERP, ESS or Groupware connector exists.

## Implemented scope

- versioned Product Configuration Pack snapshot under `specs/organization`;
- strict manifest and SHA-256 integrity validation;
- glossary, policy/knowledge and directory records;
- tenant, principal, role and validity-window filtering;
- source title, source version and source reference grounding;
- deterministic exact/alias/token search;
- explicit `EMPTY`, `READY`, `NOT_CONFIGURED`, `NO_MATCH` and `AMBIGUOUS` boundaries;
- Admin and authenticated Service read-only query APIs;
- Organization Assistant preflight grounding before any model submission;
- model submission blocked for no-match, ambiguity, wrong tenant or empty catalog;
- fixture-only demo snapshot used by deterministic tests and acceptance.

## Explicitly not implemented

- external ingestion or synchronization;
- vector or hybrid semantic search infrastructure;
- real employee or organization records in the default Product pack;
- delegated ERP/ESS/Groupware credentials;
- enterprise writes;
- durable automation;
- Tool Search or programmatic Tool calling.

## API surface

Admin:

```text
POST /v1/organization/glossary/resolve
POST /v1/organization/knowledge/search
POST /v1/organization/directory/search
```

Service:

```text
POST /v1/service/organization/glossary/resolve
POST /v1/service/organization/knowledge/search
POST /v1/service/organization/directory/search
```

## Safety contract

1. The default Product catalog is valid but empty.
2. Empty, mismatched, expired, unauthorized, ambiguous or unmatched context never becomes an organization fact.
3. Model grounding contains only authorized records and exact source/version references.
4. The model must not infer unlisted organization facts.
5. Organization read capability adds no write or automation authority.
6. Service calls derive tenant/principal/roles from authenticated context, not user-supplied scope.

## Validation plan

- Organization Context validator 20/20;
- Architecture 40/40;
- retained execution plane 13/13;
- retained distribution 14/14;
- integrated acceptance 12/12;
- portability, non-Python and installation gates;
- full source and Fresh-ZIP Python regression;
- exact Constitution Compliance changed-file closure;
- final Windows command `sh_run_step084_acceptance.cmd`.

## Next selected Product step

```text
STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION
```

STEP085 may connect multiple read-only MCP systems under authenticated delegated identity. It must not weaken STEP084 source, scope or fail-closed grounding.
