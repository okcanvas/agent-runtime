# Operations

## Fresh Windows installation

The deterministic ZIP excludes local environments. Do not merge it over an old Workspace when validating a new baseline.

```cmd
cd /d D:\NODE_AGENTS
ren okcanvas-agent-platform okcanvas-agent-platform-old
```

Extract the new ZIP so the root is:

```text
D:\NODE_AGENTS\okcanvas-agent-platform
```

Install independent environments:

```cmd
cd /d D:\NODE_AGENTS\okcanvas-agent-platform
sh_setup_workspace.cmd
```

This creates or updates:

```text
okcanvas-agent-runtime\.venv
okcanvas-connectors\groupware-mcp-server\.venv
okcanvas-agent-cli\node_modules
okcanvas-connector-examples\groupware\groupware-api-fake\node_modules
```

## STEP003R2 Windows acceptance

```cmd
sh_run_workspace_step003r2_acceptance.cmd > log.txt
```

The old STEP003 and STEP003R1 commands delegate to STEP003R2.

Expected interpreter ownership in the final JSON:

```text
resolved_executables.workspace_bootstrap_python
resolved_executables.runtime_python
resolved_executables.connector_python
```

When project `.venv` directories exist, Runtime and Connector must resolve to their respective `.venv\Scripts\python.exe` paths.

Expected Windows evidence:

```text
state: PASSED
windows_step003r2_executed: true
windows_step003r2_accepted: true
workspace_manifest_drift.missing: []
workspace_manifest_drift.changed: []
workspace_manifest_drift.unexpected: []
```

## Redirected output identity

The command redirection creates `log.txt` before Python starts. Root `log.txt` and root `*.log` are intentionally outside Workspace identity and packaging. This does not weaken tracked-source validation:

```text
HANDOFF.md missing/changed       FAIL
scripts/** missing/changed       FAIL
docs/** tracked file changed     FAIL
root log.txt                     ignored local output
root *.log                       ignored local output
nested docs/*.log                tracked
```

## Failure recovery

If the payload reports a project Python environment error, run:

```cmd
sh_setup_workspace.cmd
```

If manifest drift lists a missing or changed tracked file, discard the directory and extract the ZIP fresh. Do not regenerate the manifest to bless a damaged extraction.

## STEP004 deterministic Live-readiness gate

```cmd
sh_run_workspace_step004_acceptance.cmd > log.txt
```

Expected result:

```text
state: PASSED
passed_checks: 29
total_checks: 29
live_openai_model_called: false
windows_step004_live_executed: false
```

This bounded gate verifies Runtime STEP087R1's immutable 17/17 evidence against the Runtime parent byte manifest; it does not recursively rerun the complete Runtime acceptance. It then executes the Workspace-owned unit, subproject and deterministic full-E2E checks.

## STEP004 Windows Live OpenAI gate

The Runtime must contain exactly one local environment file:

```text
okcanvas-agent-runtime\.env.local
okcanvas-agent-runtime\.env.local.cmd
```

Required names:

```text
OPENAI_API_KEY
OKCANVAS_AGENT_MODEL
```

Run only through the official loader:

```cmd
sh_run_workspace_step004_live_acceptance.cmd > workspace-step004-live.log
```

Do not run the Python Live harness directly on Windows because direct execution bypasses environment-file loading and provenance evidence.

A successful Live result must report `state: PASSED`, `actual_openai_model_called: true`, all Live checks true and `real_enterprise_groupware_provider_called: false`. The API key value must not appear in the log, evidence, argv or errors.
