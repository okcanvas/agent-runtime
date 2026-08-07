import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { CliOptions } from "./types.js";

export class CliError extends Error {
  readonly code: string;
  readonly statusCode?: number;

  constructor(code: string, message: string, statusCode?: number) {
    super(message);
    this.name = "CliError";
    this.code = code;
    if (statusCode !== undefined) this.statusCode = statusCode;
  }
}

const ALLOWED_ENV_KEYS = new Set([
  "OKCANVAS_CONTROL_ADMIN_KEY",
  "OKCANVAS_RUN_SUBMITTER_KEY",
  "OKCANVAS_CONTROL_BASE_URL",
  "OKCANVAS_API_HOST",
  "OKCANVAS_API_PORT",
  "OKCANVAS_AGENT_MODEL",
  "OKCANVAS_DEFAULT_AGENT_ID"
]);

export function parseArgs(argv: string[]): CliOptions {
  const options: CliOptions = { assumeYes: false, noColor: false, debug: false };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    const next = argv[index + 1];
    switch (value) {
      case "--base-url":
        if (!next) throw new CliError("CLI_ARGUMENT_INVALID", "--base-url requires a value");
        options.baseUrl = next;
        index += 1;
        break;
      case "--agent-id":
        if (!next) throw new CliError("CLI_ARGUMENT_INVALID", "--agent-id requires a value");
        options.agentId = next;
        index += 1;
        break;
      case "--session-id":
        if (!next) throw new CliError("CLI_ARGUMENT_INVALID", "--session-id requires a value");
        options.sessionId = next;
        index += 1;
        break;
      case "--model":
        if (!next) throw new CliError("CLI_ARGUMENT_INVALID", "--model requires a value");
        options.model = next;
        index += 1;
        break;
      case "--evaluation-case-id":
        if (!next) throw new CliError("CLI_ARGUMENT_INVALID", "--evaluation-case-id requires a value");
        options.evaluationCaseId = next;
        index += 1;
        break;
      case "--env-file":
        if (!next) throw new CliError("CLI_ARGUMENT_INVALID", "--env-file requires a value");
        options.envFile = next;
        index += 1;
        break;
      case "--script":
        if (!next) throw new CliError("CLI_ARGUMENT_INVALID", "--script requires a value");
        options.scriptFile = next;
        index += 1;
        break;
      case "--yes":
        options.assumeYes = true;
        break;
      case "--debug":
        options.debug = true;
        break;
      case "--no-color":
        options.noColor = true;
        break;
      case "--help":
      case "-h":
        throw new CliError("CLI_HELP", "help");
      default:
        throw new CliError("CLI_ARGUMENT_INVALID", `Unknown argument: ${value}`);
    }
  }
  return options;
}

export function loadCanonicalLocalEnvironment(pathOverride?: string): string | null {
  const path = resolve(pathOverride ?? ".env.local");
  if (!existsSync(path)) return null;
  const text = readFileSync(path, "utf8");
  for (const [lineIndex, rawLine] of text.split(/\r?\n/u).entries()) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.toLowerCase() === "@echo off" || line.toLowerCase().startsWith("set ")) {
      throw new CliError(
        "CLI_ENV_FILE_INVALID",
        `${path}:${lineIndex + 1}: use canonical NAME=value syntax; .env.local.cmd is not supported`
      );
    }
    const separator = line.indexOf("=");
    if (separator <= 0) {
      throw new CliError("CLI_ENV_FILE_INVALID", `${path}:${lineIndex + 1}: expected NAME=value`);
    }
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1);
    if (!ALLOWED_ENV_KEYS.has(key)) continue;
    if (process.env[key] === undefined) process.env[key] = value;
  }
  return path;
}

export function validateLoopbackBaseUrl(value: string): string {
  let parsed: URL;
  try {
    parsed = new URL(value.trim().replace(/\/$/u, ""));
  } catch {
    throw new CliError("CLI_BASE_URL_INVALID", "Control API URL is invalid");
  }
  if (!new Set(["http:", "https:"]).has(parsed.protocol)) {
    throw new CliError("CLI_BASE_URL_INVALID", "Control API URL must use http or https");
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash || (parsed.pathname && parsed.pathname !== "/")) {
    throw new CliError("CLI_BASE_URL_INVALID", "Control API URL must not contain credentials, path, query, or fragment");
  }
  const hostname = parsed.hostname.toLowerCase();
  const loopback = hostname === "localhost" || hostname === "::1" || hostname.startsWith("127.");
  if (!loopback) {
    throw new CliError("CLI_REMOTE_URL_FORBIDDEN", "Agent CLI credentials may only be sent to a loopback Control API");
  }
  if (!parsed.port) {
    throw new CliError("CLI_BASE_URL_INVALID", "Control API URL must include an explicit port");
  }
  return parsed.origin;
}

export interface RuntimeConfig {
  baseUrl: string;
  adminKey: string;
  submitterKey: string;
  model?: string;
  defaultAgentId?: string;
}

export function runtimeConfig(options: CliOptions): RuntimeConfig {
  const host = process.env.OKCANVAS_API_HOST || "127.0.0.1";
  const safeHost = host === "0.0.0.0" || host === "::" ? "127.0.0.1" : host;
  const port = process.env.OKCANVAS_API_PORT || "8765";
  const hostForUrl = safeHost.includes(":") ? `[${safeHost}]` : safeHost;
  const baseUrl = validateLoopbackBaseUrl(
    options.baseUrl ?? process.env.OKCANVAS_CONTROL_BASE_URL ?? `http://${hostForUrl}:${port}`
  );
  const adminKey = (process.env.OKCANVAS_CONTROL_ADMIN_KEY ?? "").trim();
  const submitterKey = (process.env.OKCANVAS_RUN_SUBMITTER_KEY ?? "").trim();
  if (adminKey.length < 16 || adminKey.toLowerCase().startsWith("replace-with")) {
    throw new CliError("CLI_ADMIN_KEY_INVALID", "Set a real OKCANVAS_CONTROL_ADMIN_KEY in .env.local");
  }
  if (submitterKey.length < 16 || submitterKey.toLowerCase().startsWith("replace-with")) {
    throw new CliError("CLI_SUBMITTER_KEY_INVALID", "Set a real OKCANVAS_RUN_SUBMITTER_KEY in .env.local");
  }
  if (adminKey === submitterKey) {
    throw new CliError("CLI_AUTHORITY_NOT_SEPARATED", "Administrator and Run-submitter keys must be distinct");
  }
  const model = options.model ?? process.env.OKCANVAS_AGENT_MODEL;
  const defaultAgentId = options.agentId ?? process.env.OKCANVAS_DEFAULT_AGENT_ID;
  return {
    baseUrl,
    adminKey,
    submitterKey,
    ...(model ? { model } : {}),
    ...(defaultAgentId ? { defaultAgentId } : {})
  };
}
