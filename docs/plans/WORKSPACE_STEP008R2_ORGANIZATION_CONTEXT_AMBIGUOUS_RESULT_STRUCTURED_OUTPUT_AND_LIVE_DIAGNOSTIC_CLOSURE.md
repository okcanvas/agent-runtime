# WORKSPACE STEP008R2 — Organization Context ambiguous result structured output and Live diagnostic closure

## Objective

Close the actual STEP008R1 Windows Live failure for ambiguous same-name Organization Context
results without changing the accepted short-expression router or Agent/MCP ownership.

## Preserved topology

```text
organization-context-session-agent      skills=[]
→ organization-context-read-agent       skills=[]
→ organization-context-read MCP
```

## Runtime dependency

```text
STEP090_ORGANIZATION_CONTEXT_AMBIGUOUS_RESULT_DETERMINISTIC_NORMALIZATION_AND_LIVE_DIAGNOSTIC_CLOSURE
Version 2.70.0
```

## Live acceptance

The existing four prompts remain exact:

```text
김민수 정보
김선임 연락처
김민수 직책
과장들 목록
```

In addition to route/OpenAI/Agent/MCP/Connector checks, STEP008R2 requires:

- exactly one `agent.tool.output.normalized` event per turn;
- `deterministic-ambiguous-tool-evidence-v1` for both ambiguous turns;
- at least two stable Employee citations and nonempty disambiguation;
- no extra model or Tool call;
- bounded structured-output diagnostics with no raw model/Tool/error persistence.

Promotion remains blocked until both Windows deterministic and Windows Live pass.

## Current validation state

```text
Local deterministic: PASSED 25/25
Workspace tests: 95/95 PASSED
Runtime STEP090: 24/24 PASSED
Runtime full regression: 244 files / 1,013 tests PASSED
Windows deterministic: PENDING
Windows Live OpenAI: PENDING
Promotion: NOT_READY
```
