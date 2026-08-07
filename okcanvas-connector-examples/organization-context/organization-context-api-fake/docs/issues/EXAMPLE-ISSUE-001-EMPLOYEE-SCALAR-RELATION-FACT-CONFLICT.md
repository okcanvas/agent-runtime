# EXAMPLE-ISSUE-001 — Employee scalar/relation fact conflict

Status: `FIXED_IN_STEP002R2`

The tenant-a scalar records for `employee-0017` and `employee-0034` disagreed with department and position relation rows. Existing validation proved only that referenced IDs existed.

STEP002R2 corrects the rows, adds the missing `employee-0034 -> position.lead` relation, records the exact count 893, and rejects future department, position-set or manager mismatches before startup.
