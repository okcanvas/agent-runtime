# CLI-ISSUE-001 — Development harness must not become the Product CLI by renaming

The Runtime-owned `clients/cli` uses administrator/development APIs. Rebranding it without replacing
its authority and transport boundary would expose the wrong product contract. The Product CLI is a
separate project and remains foundation-only until `/v1/service/**`, external Bearer, Session, routing,
and SSE are implemented and accepted.
