declare module "node:http" {
  export type IncomingHttpHeaders = Record<string, string | string[] | undefined>;
  export interface IncomingMessage extends AsyncIterable<Uint8Array> {
    method?: string;
    url?: string;
    headers: IncomingHttpHeaders;
  }
  export interface ServerResponse {
    statusCode: number;
    setHeader(name: string, value: string): void;
    end(data?: string): void;
  }
  export interface AddressInfo { port: number; }
  export interface Server {
    listen(port: number, host?: string, callback?: () => void): Server;
    close(callback?: (error?: Error) => void): void;
    address(): AddressInfo | string | null;
  }
  export function createServer(handler: (request: IncomingMessage, response: ServerResponse) => void | Promise<void>): Server;
}
declare module "node:test" {
  type TestFn = (t?: unknown) => void | Promise<void>;
  export default function test(name: string, fn: TestFn): void;
}
declare module "node:assert/strict" {
  const assert: {
    equal(actual: unknown, expected: unknown): void;
    deepEqual(actual: unknown, expected: unknown): void;
    ok(value: unknown): void;
    match(value: string, pattern: RegExp): void;
  };
  export default assert;
}
declare module "node:fs" {
  export function existsSync(path: string): boolean;
  export function readFileSync(path: string, encoding: string): string;
  export function writeFileSync(path: string, data: string, encoding: string): void;
  export function mkdirSync(path: string, options?: { recursive?: boolean }): void;
}
declare module "node:path" {
  export function resolve(...paths: string[]): string;
  export function dirname(path: string): string;
}
declare module "node:url" {
  export function fileURLToPath(url: string): string;
}
declare const process: {
  env: Record<string, string | undefined>;
  cwd(): string;
  exitCode?: number;
};
declare const fetch: (input: string, init?: {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
}) => Promise<{
  status: number;
  json(): Promise<unknown>;
  text(): Promise<string>;
}>;
declare function setTimeout(callback: () => void, milliseconds: number): unknown;
declare function clearTimeout(handle: unknown): void;
declare const console: { log(message: string): void };
