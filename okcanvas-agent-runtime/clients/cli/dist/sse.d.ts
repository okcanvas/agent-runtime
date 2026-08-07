import type { RunEvent } from "./types.js";
export declare function parseSseJson(stream: ReadableStream<Uint8Array>): AsyncGenerator<RunEvent>;
