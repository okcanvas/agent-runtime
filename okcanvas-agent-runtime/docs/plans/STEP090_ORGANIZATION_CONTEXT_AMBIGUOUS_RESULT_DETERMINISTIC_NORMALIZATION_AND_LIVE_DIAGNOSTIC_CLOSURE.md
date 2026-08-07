# STEP090 — Organization Context ambiguous result deterministic normalization and Live diagnostic closure

## Objective

Close the actual Windows Live `ModelBehaviorError` observed only for ambiguous same-name
Organization Context results without changing the Root/Child/MCP topology or adding a Skill.

## Preserved boundary

```text
organization-context-session-agent      skills=[]
→ organization-context-read-agent       skills=[]
→ organization-context-read MCP
```

## Product decision

Provider structured output owns structural JSON validity. Product-owned post-Child normalization
owns semantics that require actual Tool evidence.

```text
ambiguous resolve Tool result
→ collect bounded stable candidate IDs
→ preserve department and position context
→ deterministic NEEDS_CLARIFICATION
→ return bounded structured Child result to Root
```

No retry is used. Non-ambiguous model wording is retained while operation, count, revision and
citations are aligned to observed Tool evidence.

## Acceptance

- STEP090 deterministic acceptance
- exact output JSON Schema equality
- safe diagnostic field-path/type tests
- full Runtime regression with exact non-overlapping file coverage
- STEP008R2 deterministic Workspace acceptance
- STEP008R2 actual Windows Live OpenAI rerun for the same four short expressions
