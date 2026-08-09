# WORKSPACE-ISSUE-073 — BR1 evidence redaction called a string-only helper with a dict

Status: FIXED_IN_R12R2
Scope: STEP096BR1 / Workspace R12R2 harness-only corrective closure

## Observed failure

The user executed the R12R1 Windows Live launcher. The harness reached final evidence persistence and then raised:

```text
AttributeError: 'dict' object has no attribute 'replace'
```

The failing expression was `json.dumps(redact(payload, secrets), ...)`.

## Code-confirmed root cause

`run_workspace_step008_live_acceptance.redact(text: str, secrets: list[str]) -> str` is a string-only helper. R12R1 passed the structured payload dict to it before JSON serialization.

## Correction

R12R2 serializes the payload first and then redacts the serialized JSON text:

```text
serialized_payload = json.dumps(payload, ...)
redact(serialized_payload, secrets)
```

The Runtime Product, Agent definitions, MCP Connectors, Examples, STEP096B admission behavior and 379 Product Python files are unchanged.

## Recurrence fence

The R12R2 static contract executes a focused redaction regression using a nested dict/list payload and a synthetic secret, proves the helper returns parseable JSON, proves the secret is absent, and proves the redaction marker is present. Live functional PASS/FAIL from the aborted R12R1 run is never inferred.
