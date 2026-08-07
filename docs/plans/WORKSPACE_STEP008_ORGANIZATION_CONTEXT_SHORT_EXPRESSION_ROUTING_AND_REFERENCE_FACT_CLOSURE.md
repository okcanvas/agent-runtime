# WORKSPACE_STEP008_ORGANIZATION_CONTEXT_SHORT_EXPRESSION_ROUTING_AND_REFERENCE_FACT_CLOSURE

## Decision

Do not add `employee-directory-read` as a Product Skill. The existing Organization Context Child already owns the read policy and MCP Tool boundary, while the delegation validator requires Root and Child Skill arrays to remain empty.

## Implemented vertical

```text
User short expression
→ strict Product-owned short-read matcher
→ structured request hint (not entity evidence)
→ existing organization-context-session-agent
→ existing organization-context-read-agent
→ existing read-only Organization Context MCP
```

Supported first vertical:

```text
김민수 정보
김선임 연락처
김민수 직책
과장들 목록
```

Negative expressions involving content creation, definitions, general advice, Groupware, enterprise writes, web or code remain outside this admission path.

## Corrective prerequisites included

1. Runtime package STEP/default archive identity aligned and directly accepted.
2. Example employee scalar/relation facts corrected and validated.
3. Current Workspace acceptance executes Runtime STEP089 fresh rather than trusting only retained JSON.
4. Agent IDs, Session ownership, Skill arrays, MCP server and Tool allowlist remain unchanged.

## Claim boundary

This STEP is local deterministic only until the user runs the Windows acceptance. It does not claim a real OpenAI call, production database access or real enterprise Connector execution.
