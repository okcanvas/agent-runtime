# STEP087R2_SESSION_REFERENTIAL_RESTATEMENT_ROUTING_CLOSURE

Version: 2.67.2

## Scope

Close the real Live continuation defect without weakening Groupware read routing.

- A Session-owned request that explicitly refers to an earlier answer and asks only for a restatement stays on the Root Session Agent.
- An explicit refresh/re-query request still routes to the stateless Groupware child.
- Write, draft, and automation requests are never downgraded to a language-only answer.
- Routing policy lexicons are Product-owned and versioned as `1.3.0`.
- STEP087R1 turn budgets, child-owned read-only MCP, delegated identity, and one-call policy are retained.

## Deterministic evidence

- Acceptance: 18/18 PASS
- Focused regression: 107/107 PASS
- Architecture: 40/40 PASS
- Execution plane: 13/13 PASS
- Distribution: 14/14 PASS
- Launcher registry: 7/7 PASS

Live OpenAI and real enterprise Groupware are not claimed by this Runtime-only step.
