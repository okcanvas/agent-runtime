# STEP081B Code Audit

## Preserved Windows evidence

`STEP081A_WINDOWS_LIVE_ACCEPTANCE_75_OF_77_FAILURE_SUMMARY.json` is derived from the user-provided Windows output without inferring the missing sub-validator result.

Confirmed facts:

```text
STEP081A state: FAILED
passed_checks: 75/77
terminal_status: SUCCEEDED
model_calls: 2
tool_calls: 1
Sandbox cleanup: COMPLETED
orphan_count: 0
false checks: 2 architecture/topology aggregates
architecture validator detail in output: absent
```

## Code finding

Before STEP081B, `run_step081_live_acceptance.py` imported and called the architecture validator inside the populated live process. It retained only boolean aggregate checks. The full validator payload, failed sub-checks, route inventory, return code, stdout and stderr were discarded.

The available evidence does not identify which exact route/topology sub-check differed on Windows. STEP081B therefore does not guess. It removes process-state coupling and makes the next result diagnostic-complete.

## Implementation

### Isolated validator runner

`scripts/json_subprocess_validation.py`:

- invokes the repository validator through `sys.executable`;
- sets repository root `cwd` and first `PYTHONPATH` entry;
- sets `PYTHONDONTWRITEBYTECODE=1`;
- applies a bounded timeout;
- captures UTF-8 stdout/stderr;
- parses an object JSON result;
- returns structured diagnostics for process and parse failures.

### Live evidence

The STEP081B live summary now includes:

```text
step081_architecture_validation
step081_architecture_validation_process
```

The static architecture check requires child return code zero, parsed JSON, `state=PASSED` and exact `38/38`. The transport topology check still requires the four underlying route/WebSocket predicates; it is not bypassed.

### Runtime contract

RuntimeInfo adds four fields:

```text
architecture_live_validator_process_isolation_implemented
architecture_live_validator_diagnostic_payload_preserved
architecture_live_validator_failure_fail_closed
architecture_live_validator_process_isolation_windows_live_accepted
```

The last field remains false until the real Windows STEP081B run succeeds.

### Service identity correction

Full regression found a separate literal in `application/service/use_cases.py` that still projected the STEP081A pending Gate. It is aligned to STEP081B and retained API regressions verify the authenticated capabilities response.

## Architecture preservation

```text
Static architecture: 38/38 PASS
Canonical modules: 323
Compatibility aliases: 301
RuntimeInfo fields: 807
Admin routes: 48
Service routes: 33
Other routes: 5
WebSocket routes: 0
Dependency violations: 0
Import cycles: 0
```

## Recurrence gates

- `tests/test_step081b_live_architecture_validator_isolation.py`
- authenticated STEP069/070/074 Service capability tests
- STEP081B full Python regression
- STEP081B deterministic and Fresh-ZIP Acceptance
- real Windows STEP081B live rerun


## Final deterministic and Fresh evidence

```text
Static architecture: 38/38 PASS
Windows subprocess portability: 7/7 PASS
Python test files: 228
Python regression: 911/911 PASS
Node tests: 14/14 PASS
Reference integrity: 4/4 PASS
Installation/wheel/editable: 16/16 PASS
Constitution Compliance: 16/16 PASS
Integrated Acceptance: 18/18 PASS
```

Fresh candidate evidence:

```text
Candidate: okcanvas-agent-runtime-step081b-candidate2.zip
SHA-256: 800699c5ceee1a40de6fa97264e33eddfdb980840c4b6c6c7fad009bce7c6f5b
Canonical roots: 1
ZIP file entries: 3510
Forbidden entries: 0
Fresh Python: 911/911 PASS
Fresh Architecture: 38/38 PASS
Fresh portability: 7/7 PASS
Fresh Installation: 16/16 PASS
Fresh Compliance: 16/16 PASS
Fresh Acceptance: 18/18 PASS
Protected payload identity: 2738 files, missing/extra/SHA mismatch 0
```

The Windows promotion Gate remains external and requires the exact 80/80 result.
