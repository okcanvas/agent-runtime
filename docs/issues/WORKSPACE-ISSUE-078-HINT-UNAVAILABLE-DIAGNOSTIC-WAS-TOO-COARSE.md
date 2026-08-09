# WORKSPACE-ISSUE-078 — Hint UNAVAILABLE Diagnostic Was Too Coarse

Status: FIXED_IN_R12R4_STEP096BR1R2

The Organization hint provider previously returned only `UNAVAILABLE`, making missing identity, access/endpoint configuration, connection failure and Tool/contract failure indistinguishable.

STEP096BR1R2 adds bounded codes such as `DELEGATED_IDENTITY_UNAVAILABLE`, `ENDPOINT_ROLE_OR_CREDENTIAL_UNAVAILABLE`, `MCP_CONNECTION_UNAVAILABLE` and Tool/contract-unavailable categories. The Root lifecycle event may persist the bounded code plus booleans for delegated identity and capability availability. Raw exceptions, credentials and Tool payloads remain excluded, and `diagnostic_code` is not serialized into model context.
