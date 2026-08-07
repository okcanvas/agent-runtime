import { type RuntimeConfig } from "./config.js";
import type { AgentDefinition, ExecutionObserver, JsonObject, ProductSession, RunOutcome } from "./types.js";
export declare class ControlApiClient {
    readonly config: RuntimeConfig;
    constructor(config: RuntimeConfig);
    health(): Promise<JsonObject>;
    listAgents(): Promise<AgentDefinition[]>;
    getAgent(agentId: string): Promise<AgentDefinition>;
    createSession(agentId: string): Promise<ProductSession>;
    listSessions(): Promise<ProductSession[]>;
    getSession(sessionId: string): Promise<ProductSession>;
    clearSession(sessionId: string): Promise<ProductSession>;
    evaluate(runId: string, caseId: string): Promise<JsonObject>;
    execute(agent: AgentDefinition, requestText: string, model: string | undefined, sessionId: string | undefined, confirm: (challenge: string) => Promise<boolean>, evaluationCaseId?: string, observer?: ExecutionObserver): Promise<RunOutcome | null>;
    private streamEvents;
    private headers;
    private request;
    private raiseApiError;
}
