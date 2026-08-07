# Generic Agent Execution

STEP007 introduces a product-owned execution coordinator around, not instead of, the official SDK Runner.

```text
Declarative Agent Definition
        ↓
Task / Run product state
        ↓
OpenAI Agents SDK Runner
        ↓ RunHooks
Canonical Run Events
        ↓
Structured final-output Artifact
```

The definition is content-addressed from `definition.json`, `instructions.md`, and `output.schema.json`. Only registered output contracts are accepted. The first Agent has no Tools, Handoffs, Session, workspace, MCP or external-system access.
