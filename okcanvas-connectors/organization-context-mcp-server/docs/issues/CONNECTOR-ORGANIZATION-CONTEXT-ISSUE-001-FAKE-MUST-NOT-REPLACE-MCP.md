# Connector Organization Context Issue 001 — Fake must not replace MCP

The construction-guide Example emulates the external Organization Context product API only. Product
Connector source must not import the Example, expose fake mode, or read Example fixtures directly.
The recurrence gate scans Connector product source and runs Connector-driven HTTP integration.
