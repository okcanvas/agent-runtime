# WORKSPACE-ISSUE-010 — Product CLI acceptance split Node paths containing spaces

The Windows user run reached Product CLI acceptance but the CLI test runner used a shell. `C:\Program Files\...\node.exe` was split at the first space and tests never started. `WORKSPACE_STEP002R1` consumes CLI STEP001R1, whose runner uses direct process execution and explicit test-file arguments.
