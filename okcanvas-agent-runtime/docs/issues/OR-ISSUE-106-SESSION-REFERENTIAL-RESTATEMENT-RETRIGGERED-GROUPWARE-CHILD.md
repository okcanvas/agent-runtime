# OR-ISSUE-106 — Session referential restatement retriggered Groupware child

## Observed evidence

The real STEP004R1 Windows Live run used the same Root Session for two turns. The second request was:

`앞선 답변에서 확인한 공지 제목만 그대로 다시 말해줘.`

Because the deterministic router matched `공지` and `확인`, it selected `READ_SYSTEM` and invoked the stateless Groupware child again instead of using Root Session history.

## Root cause

Routing recognized only external-system nouns and read verbs. It had no Product-owned distinction between:

- a referential restatement of an already-grounded answer; and
- an explicit refresh or re-query.

## Correction

Routing policy `1.3.0` adds exact lexicons for session reference, restatement, and external refresh. A Session request is routed to `ANSWER` only when it is referential, restatement-only, and contains no refresh, write, draft, or automation intent.

Explicit re-query and all side-effecting requests retain their previous routes.

## Recurrence gates

- Referential notice-title restatement selects `organization-assistant-session-agent` with no external capability.
- Explicit `다시 조회` still selects Groupware read routing.
- Write and automation requests remain proposal-only.
