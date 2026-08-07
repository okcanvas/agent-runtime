# WORKSPACE ISSUE 025 — Static Organization Context catalog cannot serve frequent CRUD

The Runtime STEP084 catalog is a startup-loaded hashed JSON snapshot. It is valid for deterministic
fixtures and fail-closed local configuration, but it has no CRUD API, catalog revision, change feed,
row-version conflict handling, tombstone, or live reload. Treating it as the mutable organization
terminology source would require Runtime restarts and blur product ownership.

STEP005 establishes the external product API and read-only Connector boundary first. Runtime wiring
is deliberately deferred until the external contract and construction guide are independently
accepted. Recurrence gates verify the Connector has no fake mode and the Workspace contract marks
Runtime integration as deferred.
