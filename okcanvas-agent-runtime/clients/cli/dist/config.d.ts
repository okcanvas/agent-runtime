import type { CliOptions } from "./types.js";
export declare class CliError extends Error {
    readonly code: string;
    readonly statusCode?: number;
    constructor(code: string, message: string, statusCode?: number);
}
export declare function parseArgs(argv: string[]): CliOptions;
export declare function loadCanonicalLocalEnvironment(pathOverride?: string): string | null;
export declare function validateLoopbackBaseUrl(value: string): string;
export interface RuntimeConfig {
    baseUrl: string;
    adminKey: string;
    submitterKey: string;
    model?: string;
    defaultAgentId?: string;
}
export declare function runtimeConfig(options: CliOptions): RuntimeConfig;
