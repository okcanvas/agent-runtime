#!/usr/bin/env node
import { ServiceAgentCli } from './app.mjs';
import { HELP_TEXT, parseCliConfig } from './config.mjs';
import { renderError } from './render.mjs';

async function main() {
  const config = parseCliConfig();
  if (config.help) {
    console.log(HELP_TEXT);
    return 0;
  }
  return new ServiceAgentCli(config).run();
}

main().then(
  (code) => { process.exitCode = code; },
  (error) => { console.error(renderError(error)); process.exitCode = 1; },
);
