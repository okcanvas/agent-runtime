# WORKSPACE-ISSUE-050 — Groupware lacked a stable Organization Context bridge

Status: FIX_IMPLEMENTED_TEST_EXECUTION_DEFERRED_BY_USER

## Finding

STEP093 could preserve and traverse stable Organization Context entities, but Groupware read Tools accepted only text/time inputs. Therefore a natural cross-domain continuation such as `김선임 연락처 -> 그 사람 일정은?` could not carry `employee-0017` into Groupware without falling back to the display label.

A label fallback would lose the exact identity proof and could become ambiguous or match unrelated records.

## Closure implemented in STEP094

- Product-owned `GroupwareContextFilterHint` binds prior stable entity type/ID.
- Existing Groupware MCP Tools accept optional exact `context_ref`.
- Connector forwards it to the Groupware REST API and echoes the validated applied ref in Tool output.
- Groupware API applies existing authorization/visibility first and `context_ref` only as an additional filter.
- Returned records expose `context_refs`.
- Runtime nested normalization rejects Tool/ref/record mismatches and preserves the prior Organization focus only after exact evidence.
- Display-name fallback is explicitly forbidden.

## Remaining evidence

Unit, deterministic, Connector, Example and focused cross-domain Windows Live acceptance remain unexecuted under the current test hold. The issue cannot be marked CLOSED until those gates are run.
