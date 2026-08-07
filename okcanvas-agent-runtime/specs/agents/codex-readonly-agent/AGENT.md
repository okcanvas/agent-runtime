# Codex Read-only Agent

Purpose: coordinate one official OpenAI Agents SDK `codex_tool` call over a controlled read-only workspace and return structured, evidence-bound findings.

- Tool: `codex_engineer` only.
- Handoffs: none.
- Workspace mutation: forbidden.
- Network and web search: disabled.
- Codex approval policy: `never` because the sandbox is read-only.
- Thread continuation: explicit persisted thread ID.
