# STEP002B_WINDOWS_ENV_LOADER_FIX

## Purpose

Correct the Windows launch failure observed when `sh_doctor.cmd` executed `.env.local.cmd` as a batch program. Local configuration must be parsed as data, never executed as commands.

## Confirmed failure

The STEP002A launchers used:

```bat
if exist ".env.local.cmd" call ".env.local.cmd"
```

A malformed, wrapped, or non-batch line was therefore interpreted by `cmd.exe` as a command. The reported output showed environment fragments and Korean text being executed before the Python doctor started.

## Scope

- replace batch `call` with a standard-library Python environment loader;
- support `.env.local` and legacy `.env.local.cmd`;
- support UTF-8, UTF-16 BOM, and CP949 text;
- allow only four known variables;
- reject prose, duplicates, unknown names, and ambiguous dual files with line-numbered errors;
- pass secrets to the child only through its environment;
- preserve the STEP002 live acceptance boundary.

## Non-scope

- live OpenAI or Codex execution;
- Workspace write;
- MCP;
- API, SSE, or UI;
- general-purpose dotenv semantics.

## Completion criteria

- launchers no longer execute `.env.local.cmd`;
- valid CMD and plain dotenv forms parse correctly;
- malformed local configuration fails before Agent/Codex execution;
- secret values do not appear in child command arguments or error messages;
- full regression suite and reference verification pass;
- source packaging excludes both local secret file forms.
