# WORKSPACE-ISSUE-053 — Cross-domain Session root and routed Agent binding diverged

## Status

FIX_IMPLEMENTED_LIVE_RERUN_REQUIRED

## Actual Windows evidence

The R10B focused cross-domain Live run failed on the first executed Turn after the route had already succeeded.

```text
failure_stage=execute_establish-employee-focus
CLI returncode=0
CLI one_request_completed=false
Runtime run_count=0
Product error=[RUN_SUBMISSION_INVALID] Session Agent or Runtime binding changed
```

## Root cause

The focused cross-domain harness correctly created one long-lived Session using
`organization-assistant-session-agent`, because later Groupware Turns require that Session root.
However, the current Organization Context session route still selected
`organization-context-session-agent` for the first `김선임 연락처` Turn.

The governed submission boundary then received:

```text
bound Session Agent = organization-assistant-session-agent
submitted Agent     = organization-context-session-agent
```

`SessionRuntime.validate_binding()` correctly rejected that mismatch. The failure was therefore not a
Session-integrity false positive; it exposed that STEP094 attempted a cross-domain conversation while the
Runtime still had two mutually exclusive single-domain Session roots.

## Canonical correction

STEP094R1 makes `organization-assistant-session-agent` the canonical cross-domain Session root. It owns
exactly two stateless read children:

```text
organization-assistant-session-agent
  ├─ groupware-read-agent
  └─ organization-context-read-agent
```

A versioned Product policy binds both children and their exact MCP servers into the Runtime binding.
For each Turn, immutable Product routing context may select at most one domain child. The non-selected
child is not exposed to the model for that Turn.

The Organization Context current read policy now points its Session root at the unified root. A new
route-level fence also rejects any executable route whose selected Agent differs from the Agent already
bound to the supplied Session.

## Explicitly forbidden non-fixes

The correction does not:

- switch Session IDs between turns;
- copy Session focus from one Session to another;
- retry with a different Agent after binding rejection;
- use display-name lookup as a stable-ID fallback;
- add a helper alias for either Session Agent ID;
- weaken `SessionRuntime.validate_binding()`.

The historical dedicated `organization-context-session-agent` remains an explicit historical/specialized
Agent definition; it is not used as an alias for the unified current Session root.
