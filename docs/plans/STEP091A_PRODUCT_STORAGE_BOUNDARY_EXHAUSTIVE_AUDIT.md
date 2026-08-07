# STEP091A — Product Storage Boundary Exhaustive Audit Plan

## Mode

```text
READ_ONLY
Product source modifications: 0
Implementation: prohibited in this step
```

## Audit questions

1. Which domain/application ports already isolate persistence?
2. Which application services import or type against concrete SQLite classes?
3. Which adapters share the Product DB file and which transactions cross table ownership?
4. Where are Task/Run/Event/Artifact invariants enforced?
5. Which filesystem payloads have ports and which are written directly by application services?
6. Which Session semantics are coupled to `sqlite-v1` rather than a generic capability contract?
7. What must remain atomic when moved to PostgreSQL?
8. What is the smallest safe implementation order?

## Required evidence

- Class/method inventory for Product, Submission, Approval, Ownership, Session and encrypted stores.
- Bootstrap construction map.
- Direct concrete-type coupling list.
- Transaction and cross-store atomicity map.
- Artifact metadata/binary ownership map.
- Migration risks and explicit non-goals.

## Exit

The audit must produce a ranked implementation plan. It must not claim PostgreSQL readiness merely
because `ProductStore` is a Protocol.
