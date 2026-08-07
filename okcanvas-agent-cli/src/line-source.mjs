import { readFileSync } from 'node:fs';
import { createInterface } from 'node:readline/promises';

export class InteractiveLineSource {
  constructor(input = process.stdin, output = process.stdout) {
    this.rl = createInterface({ input, output });
  }
  async next(prompt) {
    try { return await this.rl.question(prompt); } catch { return null; }
  }
  close() { this.rl.close(); }
}

export class ScriptLineSource {
  constructor(path, writer = (value) => process.stdout.write(value)) {
    this.lines = readFileSync(path, 'utf8').split(/\r?\n/u).filter((line) => line.trim().length > 0);
    this.index = 0;
    this.writer = writer;
  }
  async next(prompt) {
    const value = this.lines[this.index++];
    if (value === undefined) return null;
    this.writer(`${prompt}${value}\n`);
    return value;
  }
  close() {}
}
