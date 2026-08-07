# Workspace STEP008R4R5 — Runtime STEP091B3 PostgreSQL Metadata Alignment

```text
WORKSPACE_STEP008R4R5_RUNTIME_STEP091B3_POSTGRESQL_APPROVAL_EVALUATION_AND_SESSION_METADATA
Version: 0.8.4-r5
Runtime: STEP091B3 / 2.74.0
```

## Objective

Integrate the Runtime STEP091B3 PostgreSQL metadata boundary into the Workspace without
changing Organization Context Router, Agent, Skill, MCP, Connector or Example semantics.

## Runtime boundary admitted

- Product, Submission and Service ownership remain PostgreSQL-backed in opt-in mode.
- Tool Approval state and resume fencing move to the same PostgreSQL DSN.
- Evaluation results, suites and baselines move to the same PostgreSQL DSN.
- Product Session lifecycle metadata moves to PostgreSQL.
- Encrypted SDK Session history remains local SQLite.
- SQLite remains the default product topology.
- Artifact binary storage remains behind STEP091C `ArtifactBlobStorePort`.

## Workspace acceptance additions

- Runtime STEP091B3 identity and 22 deterministic checks.
- Shared PostgreSQL DSN contract across Product/Submission/Ownership/Approval/Evaluation/Session metadata.
- Approval transaction-domain retention.
- Session metadata row locking and local encrypted-history boundary.
- Full Runtime exact partition evidence: 249 files and 1,038 tests.
- Parent STEP091C Artifact boundary retention.
- Existing Organization Context short-expression and ambiguity contracts unchanged.

## Explicit limitations

- No real PostgreSQL server is executed by deterministic acceptance.
- No distributed Session history is implemented.
- No Production DB migration is claimed.
- No API/Worker split or distributed lease is introduced.
- No new Windows or Live acceptance is claimed until user execution.

## Promotion conditions

```text
Workspace tests              all pass
Runtime STEP091B3            22/22
Workspace deterministic      all checks pass
Connector                    11/11
Example                      19/19
Connector→Example            17/17
Fresh ZIP                    exact manifest and repeated gates
Windows deterministic        required
Windows Live OpenAI          required
Real PostgreSQL live         separately required for production claim
```
