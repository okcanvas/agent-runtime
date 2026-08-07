# WORKSPACE-ISSUE-032 — Reference employee scalar and relation facts conflicted

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

Organization Context API Example `0.2.1`

## Evidence

The committed scalar employee records and relationship records disagreed:

```text
employee-0017
scalar:    department.platform-development / position.senior
relations: department.finance / position.lead

employee-0034
scalar:    department.enterprise-sales / position.team-leader + position.lead
relations: department.partner-sales / position.associate
```

The API returned scalar context and relationship summaries together, so one response could contain contradictory organization facts. The existing validator checked only referenced-ID existence.

## Root cause

Generated relation fixtures were not validated against scalar-backed employee facts or exact relation cardinality.

## Correction

Example STEP002R2:

- corrects four stale relationship targets;
- adds the missing second position relationship for `employee-0034`;
- changes tenant-a relation count from 892 to 893;
- validates department, position and manager scalar/relation equality whenever a fixture contains relationships;
- adds API tests and acceptance evidence for the two formerly contradictory employees.

## Recurrence gate

The fixture loader fails before server startup when employee department, position set or manager differs from relationship facts. Manifest relation counts are exact for both tenants.
