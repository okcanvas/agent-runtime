# Groupware API Fake Example HANDOFF

```text
Step: EXAMPLE_STEP001R1_TYPESCRIPT_BUILD_DEPENDENCY_CLOSURE
Version: 0.1.1
State: LOCAL_DETERMINISTIC_ACCEPTED
Status: EXAMPLE_TEMPLATE_ONLY
Path: okcanvas-connector-examples/groupware/groupware-api-fake
```

This Node.js/TypeScript template emulates the Groupware **product REST/API**, not MCP. It must never
replace or bypass `okcanvas-connectors/groupware-mcp-server`.

Implemented example endpoints:

```text
POST /api/v1/notices/search
POST /api/v1/mail/search
POST /api/v1/calendar/events/list
POST /_fake/reset
PUT  /_fake/clock
PUT  /_fake/faults
GET  /_fake/requests
GET  /_fake/state
```

Properties:

- fixed clock and deterministic IDs;
- tenant/principal/role filtering;
- request capture with Authorization redaction;
- deterministic fault injection;
- product API and `/_fake/**` controls separated;
- no MCP route, MCP Tool or Connector import;
- importing `server.ts` does not open a listener; only `main.ts` starts the process.

Validation:

```text
Node tests: 4/4 PASS (clean offline install)
Example acceptance: 6/6 PASS
Connector-driven optional integration: 7/7 PASS (recorded in Connector evidence)
```

Issues:

```text
EXAMPLE-ISSUE-001 a fake MCP would bypass the actual Connector
EXAMPLE-ISSUE-002 server import initially opened a listener and kept tests alive
EXAMPLE-ISSUE-003 TypeScript build required undeclared global tsc and failed in a clean Windows workspace
```

This template is optional and must not be listed as a Runtime or production Connector dependency.


Dependency closure:

```text
TypeScript 5.8.3 is an exact local devDependency.
package-lock.json is retained.
vendor/typescript-5.8.3.tgz enables deterministic offline npm ci.
npm test and npm run acceptance install dependencies automatically.
```
