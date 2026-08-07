import assert from "node:assert/strict";
import test from "node:test";
import { parseArgs, validateLoopbackBaseUrl } from "../dist/config.js";

test("accepts explicit loopback URLs", () => {
  assert.equal(validateLoopbackBaseUrl("http://127.0.0.1:8765/"), "http://127.0.0.1:8765");
  assert.equal(validateLoopbackBaseUrl("http://localhost:8765"), "http://localhost:8765");
});

test("rejects remote URLs", () => {
  assert.throws(() => validateLoopbackBaseUrl("https://example.com:8765"), /loopback Control API/u);
});

test("debug flag is explicit and off by default", () => {
  assert.equal(parseArgs([]).debug, false);
  assert.equal(parseArgs(["--debug"]).debug, true);
});

test("session resume argument is explicit", () => {
  const options = parseArgs(["--session-id", "session_0123456789abcdef0123456789abcdef"]);
  assert.equal(options.sessionId, "session_0123456789abcdef0123456789abcdef");
});
