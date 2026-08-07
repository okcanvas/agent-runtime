# agent-cli

Planned service CLI for the multi-user OKCanvas Agent Runtime.

This directory intentionally contains no implementation in STEP069. The future client must use only
`/v1/service/**` HTTP/SSE contracts with an external Bearer token. It must not import Runtime Python
modules, read Runtime SQLite files, open Runtime workspaces, or access encrypted attachment/session
storage directly.

The existing `clients/cli` is a development and acceptance-test harness and is not the
service CLI.
