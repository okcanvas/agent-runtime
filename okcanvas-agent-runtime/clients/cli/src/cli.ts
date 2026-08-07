#!/usr/bin/env node
import { PersistentAgentCli } from "./app.js";
import { CliError, loadCanonicalLocalEnvironment, parseArgs, runtimeConfig } from "./config.js";

function printHelp(): void {
  console.log(`OKCanvas Agent CLI

Usage:
  okcanvas-agent [options]

Options:
  --agent-id <id>             initial Agent
  --session-id <id>           resume an existing Runtime Session
  --model <id>                model override
  --base-url <url>            loopback Control API
  --env-file <path>           canonical NAME=value file (default .env.local)
  --evaluation-case-id <id>   optional explicit Evaluation; off by default
  --script <path>             deterministic scripted input
  --yes                       confirm governed Run and clear prompts automatically
  --debug                     show preflight, SSE, Run, Artifact and Evaluation diagnostics
  --no-color                  reserved for stable terminal output
  -h, --help                  help
`);
}

async function main(): Promise<number> {
  try {
    const options = parseArgs(process.argv.slice(2));
    const loaded = loadCanonicalLocalEnvironment(options.envFile);
    if (loaded) console.log(`[INFO] Loaded local environment from ${loaded} without executing it.`);
    const config = runtimeConfig(options);
    return await new PersistentAgentCli(config, options).run();
  } catch (error) {
    if (error instanceof CliError && error.code === "CLI_HELP") {
      printHelp();
      return 0;
    }
    if (error instanceof CliError) {
      console.error(`[ERROR] ${error.code}: ${error.message}`);
      return 2;
    }
    console.error(`[ERROR] CLI_UNEXPECTED: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }
}

process.exitCode = await main();
