import assert from "node:assert/strict";
import test from "node:test";
import { createGroupwareFake } from "../src/server.js";

async function withServer(run: (baseUrl: string) => Promise<void>): Promise<void> {
  process.env.OKCANVAS_EXAMPLE_AUTOSTART = "0";
  const { server } = createGroupwareFake();
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("No server address");
  try {
    await run(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

const headers = {
  Authorization: "Bearer example-groupware-api-token",
  "Content-Type": "application/json",
  "X-Tenant-ID": "tenant-a",
  "X-Principal-ID": "user-001",
  "X-Principal-Roles": "agent-user,employee",
  "X-Delegation-ID": "delegation_0123456789abcdef0123456789abcdef",
  "X-Request-ID": "request-001",
};

test("deterministic tenant-isolated product API and request capture", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/v1/notices/search`, {
      method: "POST",
      headers,
      body: JSON.stringify({ query: "maintenance", limit: 10 }),
    });
    assert.equal(response.status, 200);
    const payload = await response.json() as { records: Array<{ record_id: string }> };
    assert.deepEqual(payload.records.map((item) => item.record_id), ["notice-001"]);
    const captured = await (await fetch(`${baseUrl}/_fake/requests`)).json() as {
      requests: Array<Record<string, unknown>>;
    };
    assert.equal(captured.requests.length, 1);
    assert.equal(captured.requests[0]?.authorization_present, true);
    assert.equal(captured.requests[0]?.authorization_value_recorded, false);
    assert.equal(JSON.stringify(captured).includes("example-groupware-api-token"), false);
  });
});

test("mail is principal-scoped and reset is deterministic", async () => {
  await withServer(async (baseUrl) => {
    const first = await fetch(`${baseUrl}/api/v1/mail/search`, {
      method: "POST",
      headers,
      body: JSON.stringify({ query: "", limit: 20 }),
    });
    const payload = await first.json() as { records: Array<{ record_id: string }> };
    assert.deepEqual(payload.records.map((item) => item.record_id), ["mail-001"]);
    await fetch(`${baseUrl}/_fake/reset`, { method: "POST" });
    const state = await (await fetch(`${baseUrl}/_fake/state`)).json() as { clock: { now: string } };
    assert.equal(state.clock.now, "2026-08-04T09:00:00+09:00");
    const captured = await (await fetch(`${baseUrl}/_fake/requests`)).json() as { requests: unknown[] };
    assert.equal(captured.requests.length, 0);
  });
});

test("fault injection emits configured error once", async () => {
  await withServer(async (baseUrl) => {
    await fetch(`${baseUrl}/_fake/faults`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operation: "notices.search", mode: "RATE_LIMITED", count: 1 }),
    });
    const first = await fetch(`${baseUrl}/api/v1/notices/search`, {
      method: "POST", headers, body: JSON.stringify({ limit: 1 }),
    });
    assert.equal(first.status, 429);
    const second = await fetch(`${baseUrl}/api/v1/notices/search`, {
      method: "POST", headers, body: JSON.stringify({ limit: 1 }),
    });
    assert.equal(second.status, 200);
  });
});

test("importing server module has no listener side effect", async () => {
  const module = await import("../src/server.js");
  assert.equal(typeof module.createGroupwareFake, "function");
});


test("stable context_ref filter is additive to delegated visibility", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/v1/calendar/events/list`, {
      method: "POST",
      headers,
      body: JSON.stringify({ limit: 20, context_ref: { entity_type: "EMPLOYEE", entity_id: "employee-0017" } }),
    });
    const payload = await response.json() as { records: Array<{ record_id: string; context_refs: Array<{ entity_type: string; entity_id: string }> }> };
    assert.equal(response.status, 200);
    assert.deepEqual(payload.records.map((item) => item.record_id), ["event-001"]);
    assert.equal(payload.records[0]?.context_refs.some((item) => item.entity_type === "EMPLOYEE" && item.entity_id === "employee-0017"), true);
  });
});
