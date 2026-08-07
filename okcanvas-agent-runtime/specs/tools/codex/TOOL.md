# Codex Tool

Implemented in STEP002 through the inspected official experimental `agents.extensions.experimental.codex.codex_tool` contract.

The runtime configures:

- tool name `codex_engineer`;
- `sandbox_mode=read-only`;
- `approval_policy=never`;
- web search disabled;
- explicit working directory;
- explicit Codex CLI path and version readiness;
- environment-variable allowlist rather than inheriting the entire Agent process environment;
- JSONL event callback;
- explicit Codex thread ID continuation.

The Agent SDK source passes `network_access_enabled` into the Codex CLI configuration key for `sandbox_workspace_write`. Because STEP002 uses `read-only`, the supplied source alone does not prove the effective arbitrary-command network policy. STEP002 therefore uses only a controlled disposable fixture and does not claim general untrusted-repository or network-isolation acceptance.
