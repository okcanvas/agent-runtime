# WORKSPACE-ISSUE-028 — Organization Context uses a dedicated Session root

The existing `organization-assistant-session-agent` has an accepted single-child Groupware delegation contract. Adding a second child would change a Windows Live accepted execution boundary. STEP007 therefore adds the independent `organization-context-session-agent → organization-context-read-agent → organization-context-read MCP` vertical. It reuses the existing generic Session and CLI resume capabilities and does not alter the Groupware path.
