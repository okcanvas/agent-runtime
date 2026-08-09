# WORKSPACE-ISSUE-068 — Grounded Groupware admission must preserve the cross-domain result bound

Status: FIXED_IN_STEP096B

## Failure

The first STEP096B admission used the general Groupware read policy maximum (50) when creating a
Session-focus `groupware_context_filter`. The existing authoritative cross-domain normalizer accepts
only `1..20`, so the new path would have widened an established safety/evidence bound.

## Correction

`GroundedDelegationAdmission.admit_groupware()` now sets the Session-focus bound to
`min(groupware_policy.max_results, 20)`. Focused tests require the exact value 20.

## Recurrence gate

Any new execution path reusing an existing normalized evidence contract must inherit the narrower
existing evidence bound rather than a broader upstream catalog default.
