# ADR-003: Use Codex as a Specialized Tool

## Status
Accepted as the intended STEP002 direction; not implemented in STEP000.

## Decision
Do not rebuild a Codex-class repository explorer from raw shell and patch tools. Integrate Codex through the Agents SDK experimental Codex extension or an equivalent explicit adapter, initially in read-only mode.

## Constraint
Experimental APIs require a local adapter boundary and acceptance tests. Codex internal command approval is not assumed to be integrated with general Agents SDK human approval.
