# WORKSPACE_STEP008R1_ORGANIZATION_CONTEXT_SHORT_EXPRESSION_WINDOWS_LIVE_ACCEPTANCE_CLOSURE

## Purpose

Close the acceptance gap left by STEP008: the Product-owned short-expression routing was
deterministically accepted, but no current-step Windows Live OpenAI harness existed.

## Preserved architecture

```text
organization-context-session-agent      skills=[]
→ organization-context-read-agent       skills=[]
→ organization-context-read MCP
→ external Organization Context API / database SOT
```

No Product Skill, Agent definition, MCP Tool, Connector contract or Runtime product version is
changed by this correction.

## Exact Live utterance inventory

```text
김민수 정보
김선임 연락처
김민수 직책
과장들 목록
```

## Live proof

For each utterance the harness must prove:

1. `/v1/service/assistant/routes` selects `organization-context-session-agent`.
2. The exact STEP008 request hint is produced and remains routing-only.
3. The configured OpenAI model emits actual `model.started/model.completed` events.
4. The Root calls `organization-context-read-agent` exactly once.
5. The Child calls the expected MCP Tool exactly once.
6. The actual Connector and Node Example receive the expected resolve/search request.
7. Same-name requests remain ambiguous; `김선임 연락처` cites `employee-0017`; the missing
   `과장` fixture returns a grounded no-result answer.
8. Provider identifiers, response storage, raw Tool payloads and secret values remain absent.

## Diagnostic boundary

The previous STEP007R1 Live rerun failed after the second Turn's MCP completion with
`ModelBehaviorError`. STEP008R1 does not guess the cause. It records per-turn bounded diagnostics:

```text
case_id
run status
model start/completion counts
Agent Tool start/completion counts
MCP Tool name
final output status
citation references
unverified count
safe code/detail_type/retryable fields
```

Raw provider errors, Tool arguments and Tool results remain unpersisted.

## Commands

```cmd
cd /d D:\NODE_AGENTS\okcanvas-agent-platform
sh_setup_workspace.cmd
sh_run_workspace_step008_acceptance.cmd > step008r1-deterministic.log
sh_run_workspace_step008_live_acceptance.cmd > step008r1-live.log
```

## Promotion condition

```text
STEP008R1 deterministic acceptance = PASSED
AND STEP008R1 Live evidence state = PASSED
AND actual_openai_model_called = true
AND all four short-expression Turns = SUCCEEDED
```

Until both commands pass on the user's Windows environment, STEP008R1 remains a candidate and must
not replace the last Windows Live accepted baseline.
