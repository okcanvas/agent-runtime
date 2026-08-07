# STEP035_TERMINAL_OUTCOME_RETENTION_RECONCILIATION

## Goal

Reconcile durable terminal Product outcomes with governed submission state and protected-payload retention after process loss, without re-executing any Agent.

## Scope

- explicit local-operator endpoint and exact confirmation phrase;
- `SUCCEEDED`, `FAILED`, and `CANCELLED` Product outcomes;
- same Task/Run and existing Artifact preservation;
- success payload deletion;
- failure/cancel payload investigation retention;
- one retention Event per Run;
- replay no-op and previous-generation clearing.

## Non-goals

- no model, MCP, Tool, or scheduler invocation;
- no replacement Task/Run;
- no automatic startup reconciliation;
- no SDK resume;
- no distributed worker lease;
- no new domain behavior.

## Acceptance

- three previous-process terminal outcomes detected;
- three reconciled;
- one success payload deleted;
- two failure/cancel payloads retained;
- exact terminal submission states;
- exactly one retention Event per Run;
- previous claims cleared and generations inactive;
- successful Artifact preserved;
- zero gateway calls and zero Evaluations;
- replay no-op;
- References unchanged;
- cleanup `COMPLETED`.
