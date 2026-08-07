# WORKSPACE-ISSUE-022 — Live harness randomized token did not match Node Fake

The Live harness generated a random Groupware API bearer, while the retained Node Groupware API Fake accepts the fixed example product token `example-groupware-api-token`. Requests reached the Example with delegated identity and an Authorization header, but the Example returned 401. The child correctly produced `NEEDS_CAPABILITY`, so no enterprise citation was available.

STEP004R2 binds the Connector to the Example's exact product token and adds a source-level recurrence gate.
