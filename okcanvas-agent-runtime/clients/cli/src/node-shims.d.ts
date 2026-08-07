declare const process: {
  argv: string[];
  env: Record<string, string | undefined>;
  cwd(): string;
  exitCode?: number;
  stdin: any;
  stdout: any;
  stderr: any;
};

declare module "node:crypto" {
  export function randomUUID(): string;
}

declare module "node:fs" {
  export function existsSync(path: string): boolean;
  export function readFileSync(path: string, encoding: "utf8"): string;
}

declare module "node:path" {
  export function resolve(...paths: string[]): string;
}

declare module "node:readline/promises" {
  export function createInterface(options: any): {
    question(prompt: string): Promise<string>;
    close(): void;
  };
}
