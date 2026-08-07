# EXAMPLE-ISSUE-001 — Fake must not bypass the real Connector

A Fake MCP server would test only Agent Runtime to MCP transport and omit the real
`groupware-mcp-server` mapping, delegated identity forwarding, error conversion and retry behavior.
This example therefore exposes only Groupware-like REST/API routes. A recurrence gate asserts that
no `/mcp` route or MCP Tool declaration exists in this repository.
