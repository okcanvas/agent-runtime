# STEP094 — Cross-domain stable focus and Groupware context filter

Runtime Version: 2.78.0
State: IMPLEMENTED_STATIC_VALIDATED_TEST_PENDING

## Goal

Continue one stable Organization Context entity into bounded read-only Groupware queries without converting the stable identifier into a display-name search.

## Core contract

```text
normalized Organization Tool evidence
-> Session Context Focus
-> CrossDomainGroupwareResolver
-> GroupwareContextFilterHint
-> exact Groupware Tool selection
-> context_ref {entity_type, entity_id}
-> existing tenant/principal/role visibility
-> additive exact context_ref filter
-> MCP Tool result echoes applied context_ref
-> Runtime validates every returned record context_refs
-> prior Organization focus preserved
```

## Supported bridge

Source entity types: EMPLOYEE, PROJECT, CLIENT, PRODUCT, DEPARTMENT.

Target Groupware read resources: NOTICE (`search_notices`), MAIL (`search_mail`), CALENDAR (`list_calendar_events`).

This Step does not introduce new Groupware write capability, arbitrary graph reasoning, identity impersonation, principal mapping, or display-name fallback.

## Fail-closed rules

- focus must be RESOLVED;
- multi/ambiguous focus must not guess;
- resource/tool must be in the versioned policy;
- Tool output must match the immutable Tool name and stable ref;
- each returned record must carry the exact ref;
- record count must stay within the Product bound;
- normal non-contextual Groupware requests do not receive an invented filter.

## Validation state

Executable tests are source-prepared but unexecuted. Promotion remains NOT_READY.
