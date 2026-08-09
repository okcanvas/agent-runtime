# Workspace R12R1 — STEP096B Grounded Structured Delegation Focused Live Acceptance Harness

Current Workspace: WORKSPACE_STEP008R4R12R1_STEP096B_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE_HARNESS
Workspace Version: 0.8.4-r12r1
Current Runtime: STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION
Runtime Version: 2.80.0

State: LIVE_ACCEPTANCE_HARNESS_READY_TEST_PENDING
Promotion: CANDIDATE_FOCUSED_WINDOWS_LIVE_TEST_PENDING

## Scope

R12R1 is a Workspace validation-only child of R12. Runtime Product behavior remains STEP096B/2.80.0.
No Agent capability, MCP server implementation, database schema, stable-ID authority or write path is
added in this revision.

Parent package:

```text
okcanvas-agent-platform-workspace-step008r4r12-runtime-step096b-grounded-llm-structured-delegation-admission-foundation.zip
SHA-256 4322e7fc7a862efc99af2c95a407aed7040b1bdea1bd817bb59ae7096e38484a
```

## Why this gate exists

STEP096B deterministic tests proved Product admission and normalizer contracts without executing the real
OpenAI Agents SDK nested Agent lifecycle in the analysis environment. BR1 must prove the actual model + SDK
path before structured LLM child selection is promoted or expanded.

## Windows command

```text
sh_run_workspace_step008r4r12r1_grounded_structured_delegation_live_acceptance
```

The launcher uses the Runtime-owned Windows environment loader and requires a local `.env.local` or
`.env.local.cmd` containing the configured OpenAI key/model. Local environment files are never packaged.

## Acceptance matrix

Eight semantic scenarios are isolated into eight Sessions. Two scenarios that use `그 사람` each execute
a separate stable-focus fixture first, so total Runtime Runs are ten.

| Scenario | Required outcome |
|---|---|
| `김민수 연락처 알려줘` | Organization child, structured admission, resolve, EMPLOYEE ambiguity preserved |
| `김민수 전화번호 좀 알려줘` | Same grounded Organization path; no suffix helper dependency |
| `한빛 담당자` | Organization child, CLIENT ambiguity preserved, no model stable-ID authority |
| stable focus -> `그 사람 일정 알려줘` | Groupware child, calendar Tool, exact `employee-0017` context_ref |
| `제품 코드 리뷰해줘` | No Organization/Groupware specialist execution |
| `OpenAI 정책 최신 내용 검색해줘` | No Organization/Groupware specialist execution |
| stable focus -> `그 사람 일정 삭제해줘` | No read specialist; final structured side effect must not be READ |
| `안녕하세요` | Direct Root answer; no specialist execution |

For each delegated read, evidence must include exactly one bounded sequence:

```text
agent.tool.requested
-> agent.tool.admitted
-> agent.tool.started
-> child MCP tool.started
-> agent.tool.output.normalized
```

`agent.tool.admitted.selected_child_mcp_connected` must be true. The model has no stable-ID/Tool-name input
surface. Organization stable identity is accepted only from normalized Tool evidence / SessionContextFocus.

## Hint-plane boundary

Every eligible turn may generate two Organization hint API calls:

```text
/api/v1/context/search
/api/v1/glossary/search
```

Both must receive the raw utterance unchanged. These calls are interpretation hints, not specialist execution
evidence. Direct-answer scenarios therefore require zero specialist lifecycle/MCP events and zero execution API
paths, not zero hint traffic.

## Current verification

- R12 STEP096B static/deterministic evidence retained: 20/20 static, 63/63 focused, 6/6 acceptance.
- BR1 harness + Windows entrypoint Python compile: PASS.
- BR1 no-environment dry-run: expected fail-closed; identity/provenance checks pass and Live environment checks fail.
- Windows/OpenAI Live: NOT RUN.

Do not promote from this package until the generated BR1 evidence JSON is PASSED.
