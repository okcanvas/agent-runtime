# OKCanvas Connector Examples — Groupware API Fake

`EXAMPLE_STEP001R1_TYPESCRIPT_BUILD_DEPENDENCY_CLOSURE` / `0.1.1`

```text
STATUS: EXAMPLE_TEMPLATE_ONLY
NOT A PRODUCT
NOT A PRODUCTION DEPENDENCY
NOT AN AUTHORITATIVE GROUPWARE IMPLEMENTATION
```

This optional Node.js/TypeScript template emulates the Groupware **product REST/API**, not MCP.
The real Connector code is always used:

```text
okcanvas-agent-runtime
  -> MCP
okcanvas-connectors/groupware-mcp-server
  -> Groupware REST/API
okcanvas-connector-examples/groupware/groupware-api-fake
```

Product-like endpoints:

- `POST /api/v1/notices/search`
- `POST /api/v1/mail/search`
- `POST /api/v1/calendar/events/list`

Example-only controls:

- `POST /_fake/reset`
- `PUT /_fake/clock`
- `PUT /_fake/faults`
- `GET /_fake/requests`
- `GET /_fake/state`

The template uses fixed IDs, a fixed clock, tenant and principal filtering, role checks, request
capture with Authorization value redaction, reset, and one-shot fault injection. It contains no MCP
endpoint and is never required by Runtime or Connector production deployment.


## Clean Windows setup and validation

The source package vendors the exact TypeScript compiler tarball used by this example. No global
`tsc` installation and no registry download are required. Both validation commands run an offline
`npm ci` automatically before compiling.

```cmd
npm test
npm run acceptance
```

The dependency contract is fixed by `package-lock.json` and
`vendor/typescript-5.8.3.tgz`. Do not replace it with an undeclared global compiler.
