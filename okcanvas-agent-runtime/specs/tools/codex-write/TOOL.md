# Codex workspace-write tool

The official experimental `codex_tool` runs with `sandbox_mode=workspace-write` only inside a
throwaway Git copy. The entire invocation is pre-approved through four explicit flags. Internal
command-level approval is not claimed. Git diff, patch, allowed files, HEAD, events, and token usage
are independently checked after the tool returns.
