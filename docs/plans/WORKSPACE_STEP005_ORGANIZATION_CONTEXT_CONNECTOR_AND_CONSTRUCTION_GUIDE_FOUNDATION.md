# WORKSPACE STEP005 — Organization Context Connector and Construction Guide Foundation

## Goal

Add an independent, production-shaped read-only Organization Context MCP Connector and an optional
executable Organization Context product API construction guide under `okcanvas-connector-examples`.

## Scope

- add `okcanvas-connectors/organization-context-mcp-server`;
- add `okcanvas-connector-examples/organization-context/organization-context-api-fake`;
- demonstrate frequent add/change/delete through product API revision, CAS, change feed, and tombstone;
- preserve ambiguity instead of guessing when one alias has multiple organization-unit meanings;
- validate the actual Connector against the Example over HTTP;
- keep Runtime pre-routing and Agent grounding wiring explicitly deferred.

## Non-goals

- no Runtime source change;
- no replacement of the existing STEP084 local Organization Context catalog;
- no MCP mutation tools;
- no production database or management UI;
- no claim that the Example is a production Organization Context service.
