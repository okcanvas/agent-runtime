# STEP081A code audit — Windows npm command resolution

## Audited failure path

```text
sh_run_step081_acceptance.cmd
→ scripts/run_step081_acceptance.py
→ scripts.node_acceptance.run_command(["npm", "pack", ...])
→ subprocess.run(shell=False)
→ Windows CreateProcess
→ WinError 2
```

## Repository-wide findings

Unsafe active calls found before correction:

1. `scripts/run_step081_acceptance.py` — bare npm pack.
2. `scripts/validate_step081_non_python.py` — bare npm pack.
3. `scripts/generate_node_cli_release_manifest.py` — resolved `tsc.cmd` passed directly to `subprocess.run`.

Native `node` and `git` calls were separately inspected. They resolve to `.exe` executables and are not the Windows batch-shim failure class. Historical evidence-only helpers remain preserved, while current Product paths use the common resolver.

## Corrected execution contract

```text
argv
→ resolve_subprocess_command
→ resolve explicit/bare executable
→ native executable: direct shell=False execution
→ .cmd/.bat: cmd.exe /d /c call <resolved batch> <args>
→ OSError/RuntimeError: bounded failed result, no Acceptance traceback escape
```

## Static recurrence audit

`scripts/validate_windows_subprocess_portability.py` parses Python ASTs under:

```text
scripts/
okcanvas_agent_runtime/
okcanvas_agent_clients/
```

It rejects direct `subprocess.run/Popen/check_call/check_output` use of npm, npx, pnpm, tsc, or variables resolved from their batch shims. It also verifies that STEP081 Acceptance, non-Python validation, and TypeScript manifest generation use the portable execution contract.

## Additional full-audit finding

The STEP081A live runner changed its mutable output directory to `docs/evidence/step081a-live/`, but the shared packaging inventory initially excluded only `step081-live/`. OR-ISSUE-043 adds the new directory to the Product packaging policy and `.gitignore`; the repository contract and Fresh-ZIP inspection require it to remain absent from packaged contents.

## Current deterministic result

```text
Architecture: 38/38 PASS
Windows subprocess portability: 7/7 PASS
Python files: 227
Python regression: 906/906 PASS
Node: 14/14 PASS
Reference: 4/4 PASS
Installation: 16/16 PASS
Windows rerun: pending
```

## Final Fresh result

The fully tested candidate SHA-256 is `bacb8e65dc81cdf22412c477eeec6e18971f7de848f646acabd4598fdaa58829`. A clean extraction passed Python 906/906, Architecture 38/38, subprocess portability 7/7, Installation 16/16, Compliance 16/16, integrated Acceptance 16/16, Node 14/14, Reference 4/4 and npm pack. Windows acceptance is not inferred.
