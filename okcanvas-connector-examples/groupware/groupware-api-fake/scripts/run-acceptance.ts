import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createGroupwareFake } from "../src/server.js";

process.env.OKCANVAS_EXAMPLE_AUTOSTART = "0";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const { server } = createGroupwareFake();
await new Promise<void>((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
const address = server.address();
if (!address || typeof address === "string") throw new Error("No address");
const baseUrl = `http://127.0.0.1:${address.port}`;
const headers = {
  Authorization: "Bearer example-groupware-api-token",
  "Content-Type": "application/json",
  "X-Tenant-ID": "tenant-a",
  "X-Principal-ID": "user-001",
  "X-Principal-Roles": "agent-user,employee",
  "X-Delegation-ID": "delegation_0123456789abcdef0123456789abcdef",
  "X-Request-ID": "acceptance-001",
};
const notice = await fetch(`${baseUrl}/api/v1/notices/search`, {
  method: "POST", headers, body: JSON.stringify({ query: "maintenance", limit: 5 }),
});
const noticePayload = await notice.json() as { records: Array<{ record_id: string }> };
const requests = await (await fetch(`${baseUrl}/_fake/requests`)).json() as { requests: Array<Record<string, unknown>> };
const source = await import("../src/server.js");
const packageJson = JSON.parse(readFileSync(resolve(root, "package.json"), "utf8")) as {
  version: string;
  devDependencies?: Record<string, string>;
};
const packageLock = JSON.parse(readFileSync(resolve(root, "package-lock.json"), "utf8")) as {
  packages?: Record<string, { version?: string; resolved?: string }>;
};
const typescriptDependency = packageJson.devDependencies?.typescript;
const lockedTypeScript = packageLock.packages?.["node_modules/typescript"];
const checks = {
  typescript_build_dependency_closed:
    packageJson.version === "0.1.1" &&
    typescriptDependency === "file:vendor/typescript-5.8.3.tgz" &&
    lockedTypeScript?.version === "5.8.3" &&
    lockedTypeScript?.resolved === "file:vendor/typescript-5.8.3.tgz" &&
    existsSync(resolve(root, "vendor/typescript-5.8.3.tgz")),
  product_api_passed: notice.status === 200 && noticePayload.records[0]?.record_id === "notice-001",
  request_capture_redacts_authorization: requests.requests[0]?.authorization_value_recorded === false && !JSON.stringify(requests).includes("example-groupware-api-token"),
  deterministic_identity: requests.requests[0]?.tenant_id === "tenant-a" && requests.requests[0]?.principal_id === "user-001",
  no_mcp_export: !("mcp" in source),
  example_only_health: (await (await fetch(`${baseUrl}/healthz`)).json() as { example_template_only: boolean }).example_template_only === true,
};
await new Promise<void>((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose()));
const payload = {
  schema_version: "okcanvas-connector-example-step001r1-acceptance-v1",
  step: "EXAMPLE_STEP001R1_TYPESCRIPT_BUILD_DEPENDENCY_CLOSURE",
  version: "0.1.1",
  state: Object.values(checks).every(Boolean) ? "PASSED" : "FAILED",
  checks,
  passed_checks: Object.values(checks).filter(Boolean).length,
  total_checks: Object.keys(checks).length,
};
const output = resolve(root, "docs/evidence/EXAMPLE_STEP001_ACCEPTANCE.json");
mkdirSync(dirname(output), { recursive: true });
writeFileSync(output, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(JSON.stringify(payload, null, 2));
if (payload.state !== "PASSED") process.exitCode = 1;
