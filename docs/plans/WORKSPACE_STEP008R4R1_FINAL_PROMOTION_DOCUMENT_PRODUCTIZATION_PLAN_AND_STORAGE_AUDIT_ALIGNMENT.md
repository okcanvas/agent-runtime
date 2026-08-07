# Workspace STEP008R4R1 — Final promotion document, productization plan and storage audit alignment

## Identity

```text
WORKSPACE_STEP008R4R1_FINAL_PROMOTION_DOCUMENT_PRODUCTIZATION_PLAN_AND_STORAGE_AUDIT_ALIGNMENT
Version: 0.8.4-r1
Parent: STEP008R4 / 0.8.4
Runtime: STEP090R1 / 2.70.1 unchanged
Mode: DOCUMENTATION_AND_READ_ONLY_AUDIT
```

## Purpose

1. Align every current README and HANDOFF with the actual STEP008R4 Windows approval.
2. Preserve historical Issue, Plan and Evidence states without rewriting history.
3. Record one durable productization master plan.
4. Complete STEP091A as a code-grounded read-only storage boundary audit.
5. Prevent PostgreSQL or object-storage implementation before the required ports and transaction
   ownership are explicit.

## Allowed changes

- Workspace README, HANDOFF, PLANS and current project catalog identity.
- Runtime README and HANDOFF only.
- Workspace specifications, tests, audit documents and mutable acceptance wiring.
- Manifest regeneration and package evidence.

## Forbidden changes

- `okcanvas-agent-runtime/okcanvas_agent_runtime/**/*.py`
- Runtime Agent definitions, routing policy, Tool/MCP definitions and Product Skill packages.
- Connector and Example Product implementation.
- Model retry, Tool retry, fallback Agent or topology changes.
- PostgreSQL, object storage, API/Worker split or distributed lease implementation.

## Acceptance

- Workspace unit tests pass.
- Runtime STEP090R1 deterministic acceptance passes.
- Connector, Example and Connector→Example acceptance pass.
- Workspace manifest drift is zero.
- Product Runtime Python source digest equals the STEP008R4 parent digest.
- Current documents contain no stale STEP008R2/STEP008R3 candidate or pending-live claim.
- Historical documents remain unchanged except the Issue Registry receives the new closure rows.
