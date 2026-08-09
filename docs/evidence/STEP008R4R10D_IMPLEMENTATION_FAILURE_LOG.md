# STEP008R4R10D implementation failure log

## Actual R10C Windows failure

```text
failure_stage=execute_establish-employee-focus
CLI returncode=0
CLI one_request_completed=false
Runtime run_count=0
[RUN_SUBMISSION_INVALID] Root Agent must declare exactly the Groupware read Sub-agent
```

This is not an OpenAI/model failure. The request was rejected before Run creation.

## Confirmed owner defect

R10C aligned the Session root, Runtime binding and OpenAI gateway to
`CrossDomainSessionDelegationCatalog`, but `application/submissions/service.py` retained the historical
`GroupwareSessionDelegationCatalog`. The old catalog correctly rejected the new two-child root according to
its own obsolete current-path assumption.

## Correction rule

All current cross-domain execution owners must use the same canonical graph. Submission admission now selects
one exact MCP target from immutable Product routing context through `CrossDomainSessionDelegationCatalog`.
The old Groupware-only catalog is not aliased, relaxed, or used as a fallback.

## Regression closure

STEP094R2 adds source-level regression coverage that requires:

- current submission preflight to use `CrossDomainSessionDelegationCatalog`;
- no current submission reference to `GroupwareSessionDelegationCatalog` or
  `requires_groupware_session_delegation`;
- Organization and Groupware capabilities to resolve to their exact MCP server;
- two delegated read domains in one Turn to fail closed;
- current Runtime binding and gateway to use the same unified owner.

No executable tests were run while the user's MinIO hold remains active. Static/Fresh validation only.

## Parent-project manifest SOT drift found during final validation

R10C→R10D byte comparison proved the Groupware Connector (31 files) and Example (19 files) were unchanged, but their current parent-file manifests still declared STEP001R1/0.1.1 and contained 14/10 stale hashes against the actual STEP002/0.2.0 trees. This drift originated when STEP094 advanced those sibling projects without regenerating the current source manifests.

R10D regenerated only those two current source inventory manifests from the actual trees and recorded WORKSPACE-ISSUE-055. `reference/accepted-parent-artifacts.json` and historical STEP001R1 evidence remain unchanged. This is SOT repair, not a Groupware Product source change.
