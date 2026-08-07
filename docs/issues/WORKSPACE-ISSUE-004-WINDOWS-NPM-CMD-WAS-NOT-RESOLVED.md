# WORKSPACE-ISSUE-004 — Windows npm.cmd was not resolved

## Failure

The Workspace acceptance invoked `subprocess.run(["npm", ...], shell=False)`. On the user's clean Windows run,
`CreateProcess` could not resolve the Node.js batch launcher and raised `FileNotFoundError: [WinError 2]`.
The local non-Windows acceptance did not expose this platform-specific defect.

## Correction

Resolve `node` and `npm` with `shutil.which` before execution. When the resolved Windows executable is
`.cmd` or `.bat`, execute the fixed command through the Windows command shell. Missing tools now produce a
structured failed acceptance payload rather than a Python traceback.

## Recurrence gates

- Unit-test `.cmd` invocation construction for Windows.
- Record the absolute resolved `node`, `npm`, and Python executables in acceptance evidence.
- Catch missing executable failures and return deterministic evidence.
- Run Workspace acceptance on real Windows before promotion.
