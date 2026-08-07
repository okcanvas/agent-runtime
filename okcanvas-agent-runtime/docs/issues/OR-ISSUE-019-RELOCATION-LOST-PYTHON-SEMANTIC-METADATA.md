# OR-ISSUE-019 — Relocation lost Python semantic metadata and imports

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

Focused HTTP regressions failed with:

```text
AgentRuntimeBinding() takes no arguments
```

Additional moved modules failed because `TaskStatus` and one protocol forward-reference type were not imported at their new owners.

## Code-confirmed root cause

The physical split preserved class bodies but did not preserve every decorator and import that supplied runtime semantics. AST parse and target-existence checks cannot prove dataclass construction or runtime annotation resolution.

## Impact

Execution binding construction, Admin route handling, and protocol model resolution could fail even though all canonical modules parsed and their imports pointed to existing files.

## Fix

- restored `@dataclass(frozen=True)` on `AgentRuntimeBinding`;
- restored the missing Application and protocol imports;
- executed representative Control API, Operations, Session, Submission, Attachment, Service, and compatibility regressions;
- retained real app construction in the STEP081 architecture Gate.

## Recurrence-prevention gate

`tests/test_agent_runtime_binding.py`, representative HTTP regressions, the STEP081 focused suite, and the executable route inventory exercise runtime construction rather than source presence alone.
