# STEP083 — Organization Assistant Main Agent and Action Routing Foundation

## Identity

```text
STEP083_ORGANIZATION_ASSISTANT_MAIN_AGENT_AND_ACTION_ROUTING_FOUNDATION
version 2.63.0
parent STEP082B / 2.62.2
```

STEP081D / 2.61.4 remains the Windows-live-accepted rollback baseline. STEP082B / 2.62.2 is Windows deterministic accepted and retains the single Product execution-plane and distribution contracts.

## Product objective

Provide one Agent-ID-free natural-language entrypoint that distinguishes direct answers, content drafting, attachment analysis, repository analysis, public Web search, organization knowledge, enterprise reads, enterprise writes and automation requests.

STEP083 is a routing and action-contract foundation. It does not activate semantic Tool Search, programmatic Tool calling, organization knowledge, ERP/ESS/Groupware writes or a durable Scheduler.

## Product invariants

- `GenericAgentExecutionService` remains the only Product Agent execution control plane.
- The user does not submit an Agent ID to Assistant route, session or preflight APIs.
- Unavailable organization or enterprise read capabilities fail closed without a model call.
- Enterprise write and automation requests are proposal-only and cannot claim execution.
- Tool-free questions and writing requests stay Tool-free.
- Existing hosted Web search, attachment review and read-only repository Sandbox capabilities are reused rather than duplicated.
- Repository write remains outside the Product Agent catalog and requires approval under the STEP082B boundary.
- Tool Search and programmatic Tool calling remain runtime-disabled.

## Request classes

```text
ANSWER
WRITE_CONTENT
ANALYZE_ATTACHMENT
CODE_ASSIST
SEARCH_WEB
SEARCH_KNOWLEDGE
READ_SYSTEM
DRAFT_ACTION
WRITE_ACTION
AUTOMATE
CLARIFY
REFUSE
```

## Side-effect classes

```text
NONE
READ
DRAFT
WRITE_REVERSIBLE
WRITE_IRREVERSIBLE
AUTOMATION_DEFINITION
```

## New Product agents

```text
organization-assistant-agent
organization-assistant-session-agent
```

Both return `OrganizationAssistantResult`. The one-shot Agent is session-disabled; the session Agent uses the existing encrypted SQLite Session policy. Both are language-only and cannot claim external access or action completion.

## Capability routing

Available now:

- general answer and content drafting;
- hosted public Web search;
- validated local attachment review;
- immutable project snapshot read-only Sandbox analysis.

Declared but not configured:

- organization knowledge and glossary;
- enterprise system read;
- enterprise draft/write;
- durable automation.

The router is deterministic and safety-first. It is not semantic Tool Search and does not turn on deferred Tool loading.

## Product APIs

Admin:

```text
POST /v1/assistant/sessions
POST /v1/assistant/routes
POST /v1/assistant/run-submissions/preflight
```

Service:

```text
POST /v1/service/assistant/sessions
POST /v1/service/assistant/routes
POST /v1/service/assistant/run-submissions/preflight
```

Service APIs preserve principal ownership checks for session, attachment and project snapshot resources.

## Acceptance scenarios

1. General explanation → `ANSWER`, no Tool.
2. Mail/report drafting → `WRITE_CONTENT`, no enterprise action.
3. Attached document → attachment review capability.
4. Immutable repository snapshot → read-only Sandbox capability.
5. Current public information → hosted Web search capability.
6. Organization term → `SEARCH_KNOWLEDGE`, `NOT_CONFIGURED`, no model call.
7. Leave balance/system data → `READ_SYSTEM`, `NOT_CONFIGURED`, no model call.
8. Leave application/write → `WRITE_ACTION`, proposal-only.
9. Recurring report → `AUTOMATE`, proposal-only.
10. Session creation → Organization Assistant Session Agent without a caller-supplied Agent ID.

## Known corrections

- OR-ISSUE-063: Admin preflight now forwards immutable project snapshot binding.
- OR-ISSUE-064: historical STEP082B policy gates no longer block additive Product Agents.
- OR-ISSUE-065: ordinary mail-content drafting is not treated as an enterprise transaction.

## Validation plan

- STEP083 Assistant routing validator;
- retained STEP082B execution-plane and distribution validators;
- STEP081 Architecture validator;
- launcher registry;
- full checkpointed Python regression;
- Node, Reference, direct Reference import and npm pack checks;
- Installation and isolated startup;
- Compliance exact changed-file validation;
- final immutable ZIP, Configuration Pack and Reference Pack Fresh rerun;
- Windows deterministic closure through `sh_run_step083_acceptance.cmd`.

## Next selected Product step

```text
STEP084_ORGANIZATION_KNOWLEDGE_GLOSSARY_AND_DIRECTORY_FOUNDATION
```
