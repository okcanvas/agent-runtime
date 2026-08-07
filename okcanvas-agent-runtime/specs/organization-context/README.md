# Organization Context Remote Read Boundary

The production Organization Context service is database-SOT. The Runtime owns no organization
reference data and calls the external read-only MCP Connector through delegated tenant identity.
The connector example remains an optional JSON-fixture construction guide and is never a production
dependency.
