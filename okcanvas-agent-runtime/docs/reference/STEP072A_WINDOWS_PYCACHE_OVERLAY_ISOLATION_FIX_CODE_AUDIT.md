# STEP072A code audit

## Audited Windows evidence

The user-reported STEP072 results were:

```text
Deterministic acceptance: FAILED, 28/29
Failed check: historical_skill_attachment_service_tests_pass
Historical tests: 40 passed, 1 failed
Live acceptance: PASSED, 13/13
Model calls: 1
Usage: 827 input, 228 output, 1,055 total
Run: SUCCEEDED
Trace error markers: []
SDK trace export observed: false
```

The live result closes the STEP072 provider trace-export behavior. The package baseline itself was not
accepted because deterministic acceptance returned a non-zero result.

## Source and archive evidence

Direct inspection of the STEP071 and STEP072 source ZIPs found:

```text
path: okcanvas-agent-runtime/src/okcanvas_agent_runtime/service_clients/routes.py
STEP071 ZIP timestamp: 2026-07-31 03:00:00
STEP072 ZIP timestamp: 2026-07-31 03:00:00
STEP071 size: 32,523 bytes
STEP072 size: 32,523 bytes
STEP071 content: UNSELECTED_PENDING_STEP071_WINDOWS_LIVE_ACCEPTANCE
STEP072 content: UNSELECTED_PENDING_STEP072_WINDOWS_LIVE_ACCEPTANCE
```

The STEP072 ZIP source itself is correct. The failing HTTP response contained the prior STEP071 value.
`RuntimeInfo` loaded the current STEP072 state because `model.py` changed size, while `routes.py` was
eligible for a timestamp-and-size stale `.pyc` collision. A deterministic test now recreates that
mechanism and proves the isolated-prefix result.

## Implementation audit

Added `scripts/python_bytecode_isolation.py`. It uses `tempfile.mkdtemp`, sets
`PYTHONPYCACHEPREFIX` in the child environment before interpreter startup, invokes
`sys.executable` with an argument vector and never uses a shell. An inherited prefix is reused by
nested Acceptance children. The creator removes the temporary tree after child termination.

Protected launchers:

```text
sh_run_api.cmd
sh_run_step072_acceptance.cmd
sh_run_step072_live_acceptance.cmd
sh_run_step072a_acceptance.cmd
sh_run_step072a_live_acceptance.cmd
```

The source ZIP continues to exclude `__pycache__`, `.pyc`, `.pyo`, virtual environments, local
secrets and live evidence.

## Preserved Product contracts

- trace policy SHA remains
  `6567645dc74b2850bad374f4e73eab50958c6e3e63440b0361dcadcea0b249cc`;
- provider trace export remains disabled;
- Product-local trace ID remains enabled;
- `document-review-v1` package SHA remains
  `60fbfca861141837d4486499687fde4257b83bcb68362b6b0a0b6f40b8df07b5`;
- no Tool, MCP, Hosted Tool, Shell or Network capability was added;
- STEP073 remains unselected.
