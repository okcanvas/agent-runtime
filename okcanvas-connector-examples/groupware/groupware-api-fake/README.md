# OKCanvas Connector Examples — Groupware API Fake

`EXAMPLE_STEP002_GROUPWARE_STABLE_CONTEXT_REFERENCE_FIXTURE` / `0.2.0`

```text
STATUS: EXAMPLE_TEMPLATE_ONLY
NOT A PRODUCT
NOT A PRODUCTION DEPENDENCY
NOT AN AUTHORITATIVE GROUPWARE IMPLEMENTATION
```

This deterministic TypeScript example emulates the Groupware product REST/API behind the real Groupware MCP Connector.

STEP002 adds deterministic `context_refs` to fixture records and accepts optional exact `context_ref` on notice/mail/calendar reads. Existing tenant/principal/role visibility is evaluated first; the stable reference only narrows visible records.

Fixture examples deliberately reference Organization Context fixture IDs such as `employee-0017` and `project-001` to exercise cross-domain continuity. This is example linkage, not production identity mapping.

Current executable Node tests/acceptance are source-prepared but unexecuted under the workspace test hold.
