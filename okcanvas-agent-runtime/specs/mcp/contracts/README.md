# MCP Contracts

Every enabled transport contract must define schema, read/write classification, timeout, result
limit, approval, authentication, audit and Runtime-binding fields.

Current contracts:

- local product-owned stdio server through schema v1;
- `REMOTE_STREAMABLE_HTTP_V1.md` through schema v2.

Write MCP, approval, OAuth lifecycle, prompts/resources and multi-server management remain deferred.
