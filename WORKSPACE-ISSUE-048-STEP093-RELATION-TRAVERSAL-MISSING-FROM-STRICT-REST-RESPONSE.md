# WORKSPACE-ISSUE-048 — STEP093 relation traversal missing from strict REST response schema

## Status
FIX_IMPLEMENTED_LIVE_RERUN_REQUIRED

## Actual symptom
The user's R9A focused relation Live log contained an ASGI traceback ending in:

`organization_context_request_hint.relation_traversal — Extra inputs are not permitted`

## Root cause
STEP093's internal `OrganizationContextRequestHint.to_public_dict()` emitted `relation_traversal`, but `OrganizationContextRequestHintResponse` in the strict REST protocol did not declare the field.

## Prevention
Any new internal route field exposed through `to_public_dict()` must have a matching strict REST response type and a focused protocol regression.
