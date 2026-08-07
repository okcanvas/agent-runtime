import { resolve } from 'node:path';
import { CliError } from './errors.mjs';

export const HELP_TEXT = `OKCanvas Agent Service CLI

Usage:
  node src/cli.mjs [options]

Options:
  --base-url <url>       Runtime Service API base URL
  --bearer <token>       External Service Bearer token
  --model <id>           Model override
  --session-id <id>      Resume an existing Assistant Session
  --script <file>        Read prompts and commands from a UTF-8 text file
  --yes                  Confirm governed Runs automatically
  --no-session           Run one-shot requests without an Assistant Session
  --debug                Print routing, event, and artifact diagnostics
  --help                 Show this help

Environment:
  OKCANVAS_SERVICE_BASE_URL
  OKCANVAS_SERVICE_BEARER
  OKCANVAS_AGENT_MODEL`;

function take(argv, index, flag) {
  const value = argv[index + 1];
  if (!value || value.startsWith('--')) {
    throw new CliError('CLI_ARGUMENT_INVALID', `${flag} requires a value`);
  }
  return value;
}

function normalizeBaseUrl(value) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new CliError('CLI_BASE_URL_INVALID', `Invalid Runtime URL: ${value}`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new CliError('CLI_BASE_URL_INVALID', 'Runtime URL must use http or https');
  }
  if (parsed.username || parsed.password) {
    throw new CliError('CLI_BASE_URL_INVALID', 'Runtime URL must not contain credentials');
  }
  parsed.pathname = parsed.pathname.replace(/\/+$/u, '');
  parsed.search = '';
  parsed.hash = '';
  return parsed.toString().replace(/\/$/u, '');
}

export function parseCliConfig(argv = process.argv.slice(2), env = process.env) {
  const options = {
    baseUrl: env.OKCANVAS_SERVICE_BASE_URL || 'http://127.0.0.1:8765',
    bearer: env.OKCANVAS_SERVICE_BEARER || '',
    model: env.OKCANVAS_AGENT_MODEL || undefined,
    sessionId: undefined,
    scriptFile: undefined,
    assumeYes: false,
    sessionEnabled: true,
    debug: false,
    help: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    switch (arg) {
      case '--base-url': options.baseUrl = take(argv, index, arg); index += 1; break;
      case '--bearer': options.bearer = take(argv, index, arg); index += 1; break;
      case '--model': options.model = take(argv, index, arg); index += 1; break;
      case '--session-id': options.sessionId = take(argv, index, arg); index += 1; break;
      case '--script': options.scriptFile = resolve(take(argv, index, arg)); index += 1; break;
      case '--yes': options.assumeYes = true; break;
      case '--no-session': options.sessionEnabled = false; break;
      case '--debug': options.debug = true; break;
      case '--help': case '-h': options.help = true; break;
      default: throw new CliError('CLI_ARGUMENT_INVALID', `Unknown option: ${arg}`);
    }
  }
  options.baseUrl = normalizeBaseUrl(options.baseUrl);
  if (!options.help && !options.bearer) {
    throw new CliError(
      'CLI_BEARER_REQUIRED',
      'Set OKCANVAS_SERVICE_BEARER or pass --bearer <token>'
    );
  }
  if (options.sessionId && !options.sessionEnabled) {
    throw new CliError('CLI_ARGUMENT_INVALID', '--session-id cannot be combined with --no-session');
  }
  return Object.freeze(options);
}

export function publicConfig(config) {
  return {
    baseUrl: config.baseUrl,
    model: config.model ?? null,
    sessionId: config.sessionId ?? null,
    scriptFile: config.scriptFile ?? null,
    assumeYes: config.assumeYes,
    sessionEnabled: config.sessionEnabled,
    debug: config.debug,
    bearerConfigured: Boolean(config.bearer),
  };
}
