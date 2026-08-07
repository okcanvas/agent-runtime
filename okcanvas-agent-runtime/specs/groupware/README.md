# Groupware Read-only Vertical

`read-policy.json` defines the first named enterprise read vertical. It is bound to the
`groupware-read` MCP V3 server and `groupware-read-agent`. The committed endpoint uses the reserved
`.invalid` domain and therefore remains `NOT_CONFIGURED`. An operator must replace it with an
organization-owned HTTPS endpoint and provide the referenced environment secret.

Only `search_notices`, `search_mail`, and `list_calendar_events` are allowlisted. Sending mail,
posting notices, changing calendars, approvals, and every other write remain disabled.
