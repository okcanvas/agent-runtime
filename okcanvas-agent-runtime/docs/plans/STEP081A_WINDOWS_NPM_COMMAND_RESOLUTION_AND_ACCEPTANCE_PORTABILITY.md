# STEP081A — Windows npm command resolution and Acceptance portability

## Identity

```text
STEP081A_WINDOWS_NPM_COMMAND_RESOLUTION_AND_ACCEPTANCE_PORTABILITY
version: 2.61.1
baseline: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING 2.61.0
```

## Selected failure

The real Windows STEP081 deterministic launcher terminated at `npm pack --dry-run --json` with `FileNotFoundError [WinError 2]` because the script passed bare `npm` to `subprocess.run(shell=False)` instead of resolving and invoking `npm.cmd` through the Windows command processor.

## Scope

- Introduce one resolver for native executables and Windows `.cmd`/`.bat` shims.
- Use the resolver for npm pack and TypeScript version discovery.
- Convert subprocess launch errors into bounded deterministic evidence.
- Audit every Python subprocess call for unsafe npm/npx/pnpm/tsc invocation.
- Add STEP081A deterministic/live scripts and Windows launchers while retaining STEP081 launchers as compatibility entrypoints.
- Preserve all STEP081 physical architecture, REST/SSE, Client, Protocol, Application, Adapter, compatibility, and security contracts.
- Re-run full Python, Node, Reference, installation, packaging, Compliance, and Fresh-ZIP validation.

## Non-goals

- No architecture movement or package ownership change.
- No REST/SSE route or persistence behavior change.
- No WebSocket activation.
- No model, Tool, Sandbox, Docker, MCP, Skill, Client credential, or authority expansion.
- No Windows acceptance claim before a real rerun.

## Windows contract

The corrected deterministic launcher must complete without an uncaught traceback and produce a full STEP081A Acceptance payload. The live contract preserves the prior 73 workflow checks and adds four command-portability checks, for 77 total checks.

## Final deterministic and Fresh result

```text
Architecture: 38/38 PASS
Windows subprocess portability: 7/7 PASS
Python files: 227
Python regression: 906/906 PASS
Node: 14/14 PASS
Reference: 4/4 PASS
Installation/wheel/editable: 16/16 PASS
Compliance: 16/16 PASS
Integrated Acceptance: 16/16 PASS
Fresh ZIP Python: 906/906 PASS
Fresh ZIP Compliance/Acceptance: 16/16 PASS each
Windows deterministic rerun: pending
Windows live: pending 77/77
```
