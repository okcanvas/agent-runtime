# Product API contract

`/api/v1/**` is the customer construction contract. `/_fake/**` is test-only and must not appear in a
production implementation. Reads require delegated `agent-user`; admin mutations additionally
require `admin`. Authorization values must never be retained in request evidence.
